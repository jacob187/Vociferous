"""
Audio capture service.

Handles microphone interaction, audio buffering, and real-time RMS
level metering for the UI.

The PortAudio C callback does only: copy frame, enqueue for the
recording loop, and compute cheap RMS for the level meter.
"""

import logging
from queue import Empty, Queue
from typing import Callable

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray

from src.core.constants import FlowTiming
from src.core.exceptions import AudioError
from src.core.settings import VociferousSettings

logger = logging.getLogger(__name__)


class AudioService:
    """Service for capturing audio from the microphone.

    The PortAudio C callback is kept minimal: copy frame, enqueue for
    the recording loop, and compute cheap RMS for the level meter.
    """

    def __init__(
        self,
        settings_provider: Callable[[], VociferousSettings],
        on_level_update: Callable[[float], None] | None = None,
    ) -> None:
        """
        Initialize the AudioService.

        Args:
            settings_provider: Callable that returns the current application settings.
            on_level_update: Optional callback for audio level updates (normalized 0-1).
        """
        self._settings_provider = settings_provider
        self.on_level_update = on_level_update
        self.sample_rate = 16000

    # ------------------------------------------------------------------
    # Microphone validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_microphone() -> tuple[bool, str]:
        """
        Validate that a working microphone is available.

        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        try:
            devices = sd.query_devices()
            if not devices:
                return False, "No audio devices detected"

            # Check for input devices
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if not input_devices:
                return (
                    False,
                    "No microphone detected. Please connect a microphone and try again.",
                )

            # Try to get default input device
            try:
                default_input = sd.query_devices(kind="input")
                if default_input is None:
                    return False, "No default microphone configured"
            except Exception as e:
                return False, f"Cannot access microphone: {e}"

            return True, ""

        except Exception as e:
            logger.error(f"Microphone validation failed: {e}")
            return False, f"Audio system error: {e}"

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_audio(self, should_stop: Callable[[], bool]) -> NDArray[np.int16] | None:
        """
        Record audio until should_stop() returns True.

        Args:
            should_stop: Callback that returns True when recording should stop.

        Returns:
            Recorded audio data or None if too short/failed.
        """
        s = self._settings_provider()
        self.sample_rate = s.recording.sample_rate
        frame_duration_ms = 30  # Frame size in ms for audio processing
        frame_size = int(self.sample_rate * (frame_duration_ms / 1000.0))
        # Skip initial audio to avoid capturing key press sounds
        initial_frames_to_skip = int(FlowTiming.HOTKEY_SOUND_SKIP * self.sample_rate / frame_size)
        max_recording_samples = int(s.recording.max_recording_minutes * 60 * self.sample_rate)

        # Thread-safe queue for audio callback data
        audio_queue: Queue[NDArray[np.int16]] = Queue()
        recording: list[np.int16] = []

        def audio_callback(indata, frames, time_info, status) -> None:
            """PortAudio C callback — kept minimal: copy, enqueue, RMS only."""
            try:
                if status:
                    logger.debug(f"Audio callback status: {status}")

                # Copy audio data — numpy arrays share memory with PortAudio
                frame_data = indata[:, 0].copy()
                audio_queue.put(frame_data, block=False)

                # Float conversion — reused for both RMS and spectrum enqueue
                float_data = frame_data.astype(np.float32) / 32768.0

                # Cheap RMS for the level meter (3 numpy ops, stays on callback)
                if self.on_level_update:
                    rms = np.sqrt(np.mean(float_data**2))
                    # Normalize based on measured loudness profile:
                    # Avg RMS: 0.054484, Max RMS: 0.377443
                    # Map 0.054 -> ~0.3-0.4 (visual baseline)
                    # Map 0.377 -> ~0.95 (near max)
                    normalized = min(1.0, (rms / 0.4) ** 0.7)
                    try:
                        self.on_level_update(normalized)
                    except Exception:
                        pass  # Ignore UI update errors during shutdown

            except Exception:
                # Don't let exceptions bubble up to C-layer (PortAudio)
                logger.debug("audio_callback error", exc_info=True)

        try:
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=frame_size,
                callback=audio_callback,
            )
        except Exception as e:
            logger.error(f"Failed to open audio stream: {e}")
            raise AudioError(f"Failed to open audio stream: {e}") from e

        # Robust recording loop
        try:
            with stream:
                while not should_stop():
                    try:
                        frame = audio_queue.get(timeout=FlowTiming.AUDIO_QUEUE_TIMEOUT)
                    except Empty:
                        continue

                    if len(frame) < frame_size:
                        continue

                    # Skip initial frames to avoid key press sounds
                    if initial_frames_to_skip > 0:
                        initial_frames_to_skip -= 1
                        continue

                    recording.extend(frame)

                    if len(recording) >= max_recording_samples:
                        logger.warning(
                            "Recording exceeded max duration (%.1f min) — stopping automatically",
                            s.recording.max_recording_minutes,
                        )
                        break
        except Exception as e:
            logger.error(f"Recording loop error: {e}")
            raise AudioError(f"Recording loop error: {e}") from e
        finally:
            # Drain any remaining frames that were captured by the audio
            # callback but not yet consumed by the recording loop.  Without
            # this the final fraction of a second can be silently lost,
            # causing sentence truncation at the end of recordings.
            drained = 0
            while not audio_queue.empty():
                try:
                    frame = audio_queue.get_nowait()
                    if len(frame) >= frame_size:
                        recording.extend(frame)
                        drained += 1
                except Empty:
                    break
            if drained:
                logger.debug("Drained %d residual frames from audio queue", drained)

        audio_data = np.array(recording, dtype=np.int16)
        duration = len(audio_data) / self.sample_rate
        min_duration_ms = self._settings_provider().recording.min_duration_ms

        logger.info(f"Recording finished: {audio_data.size} samples, {duration:.2f}s")

        if (duration * 1000) < min_duration_ms:
            logger.warning("Discarded: too short")
            return None

        return audio_data

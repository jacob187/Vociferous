"""
Idle Unload Manager — Reclaim RAM by unloading models after inactivity.

Monitors last-use timestamps for the SLM and ASR models.  When a model
has been idle longer than its configured timeout, it is unloaded from
memory.  Both models support transparent reload on next use:

    - SLM: SLMRuntime.enable() reloads the CTranslate2 Generator.
    - ASR: RecordingSession._transcribe_and_store() lazy-loads if
           _asr_model is None (lines 340-342, 444-447).

A single background timer thread checks every 60 seconds.  All state
is guarded by a threading.Lock for safety.

Memory savings (approximate, Apple Silicon int8):
    - SLM unload: ~3.8 GB freed
    - ASR unload: ~0.8 GB freed
"""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings

logger = logging.getLogger(__name__)

# How often the background thread wakes up to check idle timeouts.
_CHECK_INTERVAL_S = 60.0


class IdleUnloadManager:
    """Tracks model activity and unloads idle models to free memory.

    Usage:
        manager = IdleUnloadManager(
            settings_provider=...,
            slm_unloader=slm_runtime.disable,
            slm_state_checker=lambda: slm_runtime.state,
            asr_unloader=recording_session.unload_asr_model,
            asr_state_checker=lambda: recording_session._asr_model is not None,
            event_emitter=event_bus.emit,
        )
        manager.start()

        # Call these whenever the model is used:
        manager.touch_slm()
        manager.touch_asr()
    """

    def __init__(
        self,
        *,
        settings_provider: Callable[[], "VociferousSettings"],
        slm_unloader: Callable[[], None],
        slm_state_checker: Callable[[], bool],  # True if SLM is loaded
        asr_unloader: Callable[[], None],
        asr_state_checker: Callable[[], bool],  # True if ASR is loaded
        event_emitter: Callable[[str, dict], None],
    ) -> None:
        self._settings = settings_provider
        self._slm_unload = slm_unloader
        self._slm_is_loaded = slm_state_checker
        self._asr_unload = asr_unloader
        self._asr_is_loaded = asr_state_checker
        self._emit = event_emitter

        self._lock = threading.Lock()
        self._slm_last_used: float = time.monotonic()
        self._asr_last_used: float = time.monotonic()
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Activity markers — call these whenever a model is used
    # ------------------------------------------------------------------

    def touch_slm(self) -> None:
        """Mark the SLM as recently used (resets its idle timer)."""
        with self._lock:
            self._slm_last_used = time.monotonic()

    def touch_asr(self) -> None:
        """Mark the ASR model as recently used (resets its idle timer)."""
        with self._lock:
            self._asr_last_used = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background idle-check thread."""
        if self._thread is not None:
            return
        self._shutdown.clear()
        self._thread = threading.Thread(
            target=self._check_loop,
            daemon=True,
            name="idle-unload",
        )
        self._thread.start()
        logger.info("IdleUnloadManager started")

    def stop(self) -> None:
        """Signal the background thread to exit and wait for it to finish."""
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _check_loop(self) -> None:
        """Periodically check whether models have exceeded their idle timeout."""
        while not self._shutdown.wait(timeout=_CHECK_INTERVAL_S):
            try:
                self._check_idle()
            except Exception:
                logger.exception("Idle unload check failed")

    def _check_idle(self) -> None:
        """Evaluate each model's idle time against its configured timeout."""
        settings = self._settings()
        now = time.monotonic()

        with self._lock:
            slm_idle_s = now - self._slm_last_used
            asr_idle_s = now - self._asr_last_used

        # --- SLM ---
        slm_timeout_s = settings.memory.slm_idle_minutes * 60
        if slm_timeout_s > 0 and slm_idle_s >= slm_timeout_s and self._slm_is_loaded():
            logger.info(
                "SLM idle for %.0fs (limit: %.0fs) — unloading to free memory",
                slm_idle_s,
                slm_timeout_s,
            )
            self._slm_unload()
            self._emit("engine_status", {"slm": "unloaded_idle", "freed_mb_approx": 3800})

        # --- ASR ---
        asr_timeout_s = settings.memory.asr_idle_minutes * 60
        if asr_timeout_s > 0 and asr_idle_s >= asr_timeout_s and self._asr_is_loaded():
            logger.info(
                "ASR idle for %.0fs (limit: %.0fs) — unloading to free memory",
                asr_idle_s,
                asr_timeout_s,
            )
            self._asr_unload()
            self._emit("engine_status", {"asr": "unloaded_idle", "freed_mb_approx": 800})

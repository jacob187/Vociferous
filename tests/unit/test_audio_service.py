"""
AudioService unit tests.

Tests the pure computation and validation logic — NOT the PortAudio
hardware path (record_audio). Mocking an entire InputStream callback
chain would be testing mocks, not code.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.services.audio_service import AudioService


@pytest.fixture()
def audio_service(fresh_settings):
    """AudioService without callbacks — just the computation engine."""
    return AudioService(
        settings_provider=lambda: fresh_settings,
        on_level_update=None,
        on_spectrum_update=None,
    )


# ── _compute_speech_bins ──────────────────────────────────────────────────


class TestComputeSpeechBins:
    """Frequency bin computation — the FFT→display mapping."""

    def test_returns_correct_number_of_edges(self, audio_service):
        """Should be N_BINS+1 edges (64 bins → 65 edges)."""
        edges = audio_service._compute_speech_bins()
        assert len(edges) == audio_service._N_BINS + 1

    def test_edges_are_monotonically_increasing(self, audio_service):
        """Bin edges must be sorted — log spacing means no overlaps."""
        edges = audio_service._compute_speech_bins()
        for i in range(len(edges) - 1):
            assert edges[i] <= edges[i + 1]

    def test_edges_within_fft_range(self, audio_service):
        """All edges must be valid FFT bin indices."""
        edges = audio_service._compute_speech_bins()
        # 512-point FFT at 16kHz → 257 real bins (n//2 + 1)
        max_bin = audio_service._FFT_WINDOW_SIZE // 2 + 1
        assert all(0 <= e <= max_bin for e in edges)

    def test_first_edge_covers_speech_minimum(self, audio_service):
        """First edge should be at or near 100 Hz bin index."""
        edges = audio_service._compute_speech_bins()
        # 16kHz / 512 = 31.25 Hz per bin → 100 Hz ≈ bin 3
        assert edges[0] >= 2  # at least above DC and 31 Hz

    def test_deterministic(self, audio_service):
        """Same input → same output (no random state)."""
        a = audio_service._compute_speech_bins()
        b = audio_service._compute_speech_bins()
        np.testing.assert_array_equal(a, b)


# ── validate_microphone ──────────────────────────────────────────────────


class TestValidateMicrophone:
    """Static microphone validation with mocked sounddevice."""

    @patch("src.services.audio_service.sd")
    def test_no_devices(self, mock_sd):
        """Empty device list → invalid."""
        mock_sd.query_devices.return_value = []
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "no audio" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_no_input_devices(self, mock_sd):
        """Only output devices → invalid."""
        mock_sd.query_devices.return_value = [
            {"name": "Speakers", "max_input_channels": 0, "max_output_channels": 2},
        ]
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "no microphone" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_valid_input_device(self, mock_sd):
        """Working input device → valid."""
        mock_sd.query_devices.return_value = [
            {"name": "Built-in Mic", "max_input_channels": 1, "max_output_channels": 0},
        ]
        mock_sd.query_devices.side_effect = None  # allow the call_args variant

        # query_devices(kind="input") should also work
        def query_devices_side_effect(*args, **kwargs):
            if kwargs.get("kind") == "input":
                return {"name": "Built-in Mic", "max_input_channels": 1}
            return [{"name": "Built-in Mic", "max_input_channels": 1, "max_output_channels": 0}]

        mock_sd.query_devices = MagicMock(side_effect=query_devices_side_effect)

        valid, msg = AudioService.validate_microphone()
        assert valid is True
        assert msg == ""

    @patch("src.services.audio_service.sd")
    def test_default_input_fails(self, mock_sd):
        """Input devices exist but default can't be queried → invalid."""

        def query_devices_side_effect(*args, **kwargs):
            if kwargs.get("kind") == "input":
                raise RuntimeError("PulseAudio not running")
            return [{"name": "Mic", "max_input_channels": 1}]

        mock_sd.query_devices = MagicMock(side_effect=query_devices_side_effect)

        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "cannot access" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_default_input_returns_none(self, mock_sd):
        """query_devices(kind='input') returns None → invalid."""

        def query_devices_side_effect(*args, **kwargs):
            if kwargs.get("kind") == "input":
                return None
            return [{"name": "Mic", "max_input_channels": 1}]

        mock_sd.query_devices = MagicMock(side_effect=query_devices_side_effect)

        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "no default" in msg.lower()

    @patch("src.services.audio_service.sd")
    def test_sounddevice_completely_broken(self, mock_sd):
        """Total sounddevice failure → invalid with system error."""
        mock_sd.query_devices.side_effect = OSError("ALSA lib not found")
        valid, msg = AudioService.validate_microphone()
        assert valid is False
        assert "audio system error" in msg.lower()


# ── Constructor ─────────────────────────────────────────────────────────


class TestConstructor:
    """Init wires up bins and callbacks correctly."""

    def test_bin_edges_computed_on_init(self, audio_service):
        """_bin_edges should be populated at construction time."""
        assert audio_service._bin_edges is not None
        assert len(audio_service._bin_edges) == audio_service._N_BINS + 1

    def test_sample_rate_default(self, audio_service):
        assert audio_service.sample_rate == 16000

    def test_callbacks_stored(self, fresh_settings):
        on_level = MagicMock()
        on_spectrum = MagicMock()
        svc = AudioService(
            settings_provider=lambda: fresh_settings,
            on_level_update=on_level,
            on_spectrum_update=on_spectrum,
        )
        assert svc.on_level_update is on_level
        assert svc.on_spectrum_update is on_spectrum

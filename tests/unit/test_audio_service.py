"""
AudioService unit tests.

Tests the pure computation and validation logic — NOT the PortAudio
hardware path (record_audio). Mocking an entire InputStream callback
chain would be testing mocks, not code.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.services.audio_service import AudioService


@pytest.fixture()
def audio_service(fresh_settings):
    """AudioService without callbacks — just the computation engine."""
    return AudioService(
        settings_provider=lambda: fresh_settings,
        on_level_update=None,
    )


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
    """Init wires up callbacks correctly."""

    def test_sample_rate_default(self, audio_service):
        assert audio_service.sample_rate == 16000

    def test_callbacks_stored(self, fresh_settings):
        on_level = MagicMock()
        svc = AudioService(
            settings_provider=lambda: fresh_settings,
            on_level_update=on_level,
        )
        assert svc.on_level_update is on_level

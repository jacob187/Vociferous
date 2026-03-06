"""
Unit tests for usage_stats.compute_usage_stats().

Pure computation — real DB with known data, no mocks needed beyond the DB.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.usage_stats import compute_usage_stats
from src.database.db import TranscriptDB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> TranscriptDB:
    database = TranscriptDB(db_path=tmp_path / "stats_test.db")
    yield database
    database.close()


# ---------------------------------------------------------------------------
# Empty / edge-case inputs
# ---------------------------------------------------------------------------


class TestEmptyInputs:
    """Behavior when there are no transcripts."""

    def test_empty_db_returns_empty_dict(self, db):
        result = compute_usage_stats(db)
        assert result == {}


# ---------------------------------------------------------------------------
# Core statistics
# ---------------------------------------------------------------------------


class TestCoreStats:
    """Validate the arithmetic on known data."""

    def test_count_matches_transcript_count(self, db):
        db.add_transcript(raw_text="hello world", duration_ms=5000)
        db.add_transcript(raw_text="goodbye world", duration_ms=3000)

        stats = compute_usage_stats(db)
        assert stats["count"] == 2

    def test_total_words_counted_correctly(self, db):
        db.add_transcript(raw_text="one two three", duration_ms=5000)
        db.add_transcript(raw_text="four five", duration_ms=3000)

        stats = compute_usage_stats(db)
        assert stats["total_words"] == 5

    def test_recorded_seconds_from_duration_ms(self, db):
        db.add_transcript(raw_text="some words here", duration_ms=10_000)

        stats = compute_usage_stats(db)
        assert stats["recorded_seconds"] == 10.0

    def test_avg_seconds_per_transcript(self, db):
        db.add_transcript(raw_text="words", duration_ms=6000)
        db.add_transcript(raw_text="words", duration_ms=4000)

        stats = compute_usage_stats(db)
        assert stats["avg_seconds"] == 5.0

    def test_time_saved_positive_when_speaking_faster_than_typing(self, db):
        """With reasonable durations, time_saved should be positive."""
        # 150 words spoken in 60s (normal pace) vs typing 150 words at 40 WPM = 225s
        # time_saved = 225 - 60 = 165
        words = " ".join(["word"] * 150)
        db.add_transcript(raw_text=words, duration_ms=60_000)

        stats = compute_usage_stats(db)
        assert stats["time_saved_seconds"] > 0

    def test_fallback_duration_estimate_when_no_duration_ms(self, db):
        """If duration_ms is 0, estimate from word count at 150 WPM."""
        words = " ".join(["word"] * 150)  # 150 words = 60 seconds at 150 WPM
        db.add_transcript(raw_text=words, duration_ms=0)

        stats = compute_usage_stats(db)
        assert stats["recorded_seconds"] == pytest.approx(60.0, rel=0.01)


# ---------------------------------------------------------------------------
# Filler word detection
# ---------------------------------------------------------------------------


class TestFillerDetection:
    """Verify filler word counting (single + multi-word)."""

    def test_single_word_fillers_counted(self, db):
        db.add_transcript(raw_text="um like I basically um went", duration_ms=5000)

        stats = compute_usage_stats(db)
        # "um" x2, "like", "basically" = 4
        assert stats["filler_count"] == 4

    def test_multi_word_fillers_counted(self, db):
        db.add_transcript(raw_text="I mean you know it was sort of okay", duration_ms=5000)

        stats = compute_usage_stats(db)
        # "i mean", "you know", "sort of", "okay" (single) = 4
        assert stats["filler_count"] == 4

    def test_no_fillers_yields_zero(self, db):
        db.add_transcript(raw_text="The quarterly budget exceeded expectations", duration_ms=5000)

        stats = compute_usage_stats(db)
        assert stats["filler_count"] == 0

    def test_repeated_multi_word_fillers(self, db):
        db.add_transcript(raw_text="you know I mean you know I mean", duration_ms=5000)

        stats = compute_usage_stats(db)
        # "you know" x2, "i mean" x2 = 4
        assert stats["filler_count"] == 4


# ---------------------------------------------------------------------------
# Vocabulary ratio
# ---------------------------------------------------------------------------


class TestVocabRatio:
    """Vocabulary diversity metric."""

    def test_all_unique_words_ratio_one(self, db):
        db.add_transcript(raw_text="alpha beta gamma delta", duration_ms=5000)

        stats = compute_usage_stats(db)
        assert stats["vocab_ratio"] == pytest.approx(1.0)

    def test_all_same_word_ratio_low(self, db):
        db.add_transcript(raw_text="word word word word", duration_ms=5000)

        stats = compute_usage_stats(db)
        assert stats["vocab_ratio"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Silence estimation
# ---------------------------------------------------------------------------


class TestSilenceEstimation:
    """Silence is estimated as recorded_time - expected_speaking_time."""

    def test_silence_positive_when_recording_longer_than_speech(self, db):
        """10 words at 150 WPM = 4s of speech. 30s recording = 26s silence."""
        db.add_transcript(raw_text=" ".join(["word"] * 10), duration_ms=30_000)

        stats = compute_usage_stats(db)
        assert stats["total_silence_seconds"] > 0

    def test_silence_zero_when_no_slack(self, db):
        """If recording duration exactly matches expected speaking time, silence is 0."""
        # 150 words at 150 WPM = 60s
        words = " ".join(["word"] * 150)
        db.add_transcript(raw_text=words, duration_ms=60_000)

        stats = compute_usage_stats(db)
        assert stats["total_silence_seconds"] == pytest.approx(0.0, abs=0.1)


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------


class TestReturnShape:
    """Verify all expected keys are present."""

    def test_all_keys_present(self, db):
        db.add_transcript(raw_text="hello world test", duration_ms=5000)

        stats = compute_usage_stats(db)
        expected_keys = {
            "count",
            "total_words",
            "recorded_seconds",
            "time_saved_seconds",
            "avg_seconds",
            "vocab_ratio",
            "total_silence_seconds",
            "filler_count",
        }
        assert set(stats.keys()) == expected_keys

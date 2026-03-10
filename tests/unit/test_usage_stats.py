"""
Unit tests for usage_stats.compute_usage_stats().

Pure computation — real DB with known data, no mocks needed beyond the DB.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from src.core.usage_stats import compute_usage_stats
from src.database.db import TranscriptDB

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path: Path) -> Generator[TranscriptDB, None, None]:
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
            # Overall (backward-compatible)
            "count",
            "total_words",
            "recorded_seconds",
            "time_saved_seconds",
            "avg_seconds",
            "vocab_ratio",
            "total_silence_seconds",
            "filler_count",
            # Verbatim pipeline
            "verbatim_total_words",
            "verbatim_filler_count",
            "verbatim_filler_density",
            "verbatim_vocab_ratio",
            "verbatim_avg_fk_grade",
            "verbatim_avg_sentence_length",
            "verbatim_avg_word_length",
            "verbatim_long_word_ratio",
            # Refinement pipeline
            "refined_count",
            "refined_total_words",
            "refined_filler_count",
            "refined_filler_density",
            "refined_vocab_ratio",
            "refined_avg_fk_grade",
            "refined_avg_sentence_length",
            "refined_avg_word_length",
            "refined_long_word_ratio",
            # Distribution data
            "word_count_std_dev",
            "word_count_mean",
            "distribution_words",
            "distribution_fk_verbatim",
            "distribution_fk_refined",
            # Session-level (ISS-070)
            "today_count",
            "today_words",
            "days_active_this_week",
        }
        assert set(stats.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Verbatim / refined split
# ---------------------------------------------------------------------------


class TestVerbatimRefinedSplit:
    """Verify stats are correctly split between verbatim and refined pipelines."""

    def test_unrefined_transcript_counts_zero_refined(self, db):
        db.add_transcript(raw_text="Hello world.", duration_ms=5000)

        stats = compute_usage_stats(db)
        assert stats["refined_count"] == 0
        assert stats["refined_total_words"] == 0

    def test_refined_transcript_detected(self, db):
        t = db.add_transcript(raw_text="um hello um world", duration_ms=5000)
        db.update_normalized_text(t.id, "Hello world.")

        stats = compute_usage_stats(db)
        assert stats["refined_count"] == 1
        assert stats["refined_total_words"] == 2

    def test_verbatim_fillers_counted_from_raw(self, db):
        t = db.add_transcript(raw_text="um like I basically went um there", duration_ms=5000)
        db.update_normalized_text(t.id, "I went there.")

        stats = compute_usage_stats(db)
        assert stats["verbatim_filler_count"] == 4  # um x2, like, basically
        assert stats["refined_filler_count"] == 0

    def test_filler_density_ratio(self, db):
        t = db.add_transcript(raw_text="um um um um um um um um um um", duration_ms=5000)
        db.update_normalized_text(t.id, "Something meaningful.")

        stats = compute_usage_stats(db)
        assert stats["verbatim_filler_density"] == 1.0  # all words are fillers
        assert stats["refined_filler_density"] == 0.0

    def test_verbatim_stats_always_from_raw_text(self, db):
        """Even when refined, verbatim metrics should reflect raw_text."""
        t = db.add_transcript(
            raw_text="The quick brown fox jumped over the lazy dog.",
            duration_ms=5000,
        )
        db.update_normalized_text(t.id, "A nimble russet fox leaped across the indolent canine.")

        stats = compute_usage_stats(db)
        assert stats["verbatim_total_words"] == 9
        assert stats["refined_total_words"] == 9

    def test_mixed_refined_and_unrefined(self, db):
        db.add_transcript(raw_text="First entry here.", duration_ms=3000)
        t2 = db.add_transcript(raw_text="um second um entry", duration_ms=4000)
        db.update_normalized_text(t2.id, "Second entry.")

        stats = compute_usage_stats(db)
        assert stats["count"] == 2
        assert stats["refined_count"] == 1


# ---------------------------------------------------------------------------
# Text analysis metrics (FK grade, sentence length, etc.)
# ---------------------------------------------------------------------------


class TestTextAnalysisMetrics:
    """Verify Flesch-Kincaid and related metrics are computed."""

    def test_fk_grade_nonzero_for_real_text(self, db):
        db.add_transcript(
            raw_text="The committee convened to discuss the preliminary findings. "
            "Several members expressed reservations about the methodology.",
            duration_ms=10000,
        )
        stats = compute_usage_stats(db)
        assert stats["verbatim_avg_fk_grade"] > 0

    def test_refined_fk_grade_only_from_refined_transcripts(self, db):
        db.add_transcript(raw_text="Simple words here.", duration_ms=3000)

        stats = compute_usage_stats(db)
        # No refinement — refined FK should be 0
        assert stats["refined_avg_fk_grade"] == 0.0

    def test_avg_word_length_reasonable(self, db):
        db.add_transcript(raw_text="The cat sat on a mat.", duration_ms=3000)

        stats = compute_usage_stats(db)
        # Average word length should be in a sane range
        assert 2.0 <= stats["verbatim_avg_word_length"] <= 5.0

    def test_long_word_ratio(self, db):
        db.add_transcript(
            raw_text="Internationalization is a sophisticated concept.",
            duration_ms=5000,
        )
        stats = compute_usage_stats(db)
        # "Internationalization" and "sophisticated" are > 6 chars
        assert stats["verbatim_long_word_ratio"] > 0


# ---------------------------------------------------------------------------
# Distribution data
# ---------------------------------------------------------------------------


class TestDistributionData:
    """Verify distribution arrays for bell curve visualizations."""

    def test_distribution_words_length_matches_count(self, db):
        db.add_transcript(raw_text="Hello world.", duration_ms=3000)
        db.add_transcript(raw_text="Testing one two three.", duration_ms=4000)

        stats = compute_usage_stats(db)
        assert len(stats["distribution_words"]) == 2
        assert sorted(stats["distribution_words"]) == [2.0, 4.0]

    def test_distribution_fk_verbatim_populated(self, db):
        db.add_transcript(
            raw_text="The quick brown fox jumps over the lazy dog.",
            duration_ms=5000,
        )
        stats = compute_usage_stats(db)
        assert len(stats["distribution_fk_verbatim"]) == 1
        assert stats["distribution_fk_verbatim"][0] > 0

    def test_distribution_fk_refined_only_for_refined(self, db):
        t = db.add_transcript(raw_text="um hello um world", duration_ms=3000)
        db.update_normalized_text(t.id, "Hello, world.")
        db.add_transcript(raw_text="Plain entry.", duration_ms=3000)

        stats = compute_usage_stats(db)
        # Only the refined transcript should appear in refined FK distribution
        assert len(stats["distribution_fk_refined"]) == 1
        # Both should appear in verbatim FK distribution
        assert len(stats["distribution_fk_verbatim"]) == 2

    def test_word_count_std_dev(self, db):
        db.add_transcript(raw_text="Short.", duration_ms=2000)
        db.add_transcript(
            raw_text=" ".join(["word"] * 50),
            duration_ms=20000,
        )

        stats = compute_usage_stats(db)
        assert stats["word_count_std_dev"] > 0
        assert stats["word_count_mean"] > 0

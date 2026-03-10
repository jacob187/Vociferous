"""
Usage statistics computation for InsightManager and MOTD generation.

Extracted from ApplicationCoordinator._init_insight_manager() so it is
independently testable and not buried in an init closure.

Statistics are split into three views:
- **Overall**: Aggregate metrics across all transcripts (best-available text).
- **Verbatim**: Metrics computed from raw_text only.
- **Refined**: Metrics computed from normalized_text on transcripts that were
  actually refined (normalized_text != raw_text).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.core.text_analysis import compute_text_metrics, flesch_kincaid_grade, std_dev

if TYPE_CHECKING:
    from src.database.db import TranscriptDB

_SPEAKING_WPM = 150
_TYPING_WPM = 40

_FILLER_SINGLE: frozenset[str] = frozenset(
    {
        "um",
        "uh",
        "uhm",
        "umm",
        "er",
        "err",
        "like",
        "basically",
        "literally",
        "actually",
        "so",
        "well",
        "right",
        "okay",
    }
)
_FILLER_MULTI: tuple[str, ...] = ("you know", "i mean", "kind of", "sort of")


def _count_fillers(text: str) -> int:
    """Count filler words/phrases in a text string."""
    if not text:
        return 0
    lower = text.lower()
    count = 0

    # Multi-word fillers
    for phrase in _FILLER_MULTI:
        idx = 0
        while (idx := lower.find(phrase, idx)) != -1:
            count += 1
            idx += len(phrase)

    # Single-word fillers
    for w in lower.split():
        cleaned = w.strip(".,!?;:'\"()[]{}").lower()
        if cleaned and cleaned in _FILLER_SINGLE:
            count += 1

    return count


def _collect_cleaned_words(text: str) -> list[str]:
    """Extract cleaned lowercase words from text for vocabulary analysis."""
    words: list[str] = []
    for w in text.lower().split():
        cleaned = w.strip(".,!?;:'\"()[]{}").lower()
        if cleaned:
            words.append(cleaned)
    return words


def compute_usage_stats(db: TranscriptDB, typing_wpm: int = _TYPING_WPM) -> dict:
    """
    Compute speech usage statistics across all stored transcripts.

    Parameters
    ----------
    db : TranscriptDB
        Transcript database.
    typing_wpm : int
        Assumed manual typing speed in words-per-minute (default 40).

    Returns an empty dict if there are no transcripts or the DB is unavailable.
    Used as the stats_provider for both InsightManager and MOTDManager.
    """
    transcripts, _ = db.recent(limit=10000)
    if not transcripts:
        return {}

    count = len(transcripts)
    total_words = 0
    all_words: list[str] = []
    recorded_seconds = 0.0
    total_silence = 0.0
    filler_count = 0

    # Verbatim / refined accumulators
    verbatim_filler_count = 0
    refined_filler_count = 0
    refined_count = 0
    verbatim_total_words = 0
    refined_total_words = 0
    verbatim_all_words: list[str] = []
    refined_all_words: list[str] = []

    # Per-transcript distribution data
    per_transcript_word_counts: list[float] = []
    per_transcript_fk_verbatim: list[float] = []
    per_transcript_fk_refined: list[float] = []

    # Verbatim text metrics accumulators
    verbatim_fk_sum = 0.0
    verbatim_avg_sentence_len_sum = 0.0
    verbatim_avg_word_len_sum = 0.0
    verbatim_long_word_ratio_sum = 0.0
    verbatim_metrics_count = 0

    # Refined text metrics accumulators
    refined_fk_sum = 0.0
    refined_avg_sentence_len_sum = 0.0
    refined_avg_word_len_sum = 0.0
    refined_long_word_ratio_sum = 0.0

    for t in transcripts:
        raw = t.raw_text or ""
        norm = t.normalized_text or ""
        is_refined = bool(norm and norm != raw)
        text = norm or raw  # best-available

        words = text.split()
        total_words += len(words)
        per_transcript_word_counts.append(float(len(words)))

        # Overall filler count (best-available text)
        filler_count += _count_fillers(text)
        all_words.extend(_collect_cleaned_words(text))

        # Verbatim stats (always computed from raw_text)
        raw_words = raw.split()
        verbatim_total_words += len(raw_words)
        verbatim_filler_count += _count_fillers(raw)
        verbatim_all_words.extend(_collect_cleaned_words(raw))

        if raw.strip():
            v_metrics = compute_text_metrics(raw)
            verbatim_fk_sum += v_metrics["fk_grade"]
            verbatim_avg_sentence_len_sum += v_metrics["avg_sentence_length"]
            verbatim_avg_word_len_sum += v_metrics["avg_word_length"]
            verbatim_long_word_ratio_sum += v_metrics["long_word_ratio"]
            verbatim_metrics_count += 1
            per_transcript_fk_verbatim.append(v_metrics["fk_grade"])

        # Refined stats (only for actually-refined transcripts)
        if is_refined:
            refined_count += 1
            norm_words = norm.split()
            refined_total_words += len(norm_words)
            refined_filler_count += _count_fillers(norm)
            refined_all_words.extend(_collect_cleaned_words(norm))

            r_metrics = compute_text_metrics(norm)
            refined_fk_sum += r_metrics["fk_grade"]
            refined_avg_sentence_len_sum += r_metrics["avg_sentence_length"]
            refined_avg_word_len_sum += r_metrics["avg_word_length"]
            refined_long_word_ratio_sum += r_metrics["long_word_ratio"]
            per_transcript_fk_refined.append(r_metrics["fk_grade"])

        # Duration / silence
        dur = (t.duration_ms or 0) / 1000
        if dur > 0:
            recorded_seconds += dur
            expected = (len(words) / _SPEAKING_WPM) * 60
            total_silence += max(0.0, dur - expected)

    # Fallback estimate when no duration metadata is present
    if recorded_seconds == 0 and total_words > 0:
        recorded_seconds = (total_words / _SPEAKING_WPM) * 60

    typing_seconds = (total_words / typing_wpm) * 60
    time_saved = max(0.0, typing_seconds - recorded_seconds)
    avg_seconds = recorded_seconds / count if count > 0 else 0
    vocab_ratio = len(set(all_words)) / len(all_words) if all_words else 0

    # Verbatim averages
    v_count = verbatim_metrics_count or 1
    verbatim_vocab_ratio = len(set(verbatim_all_words)) / len(verbatim_all_words) if verbatim_all_words else 0
    verbatim_filler_density = verbatim_filler_count / verbatim_total_words if verbatim_total_words else 0

    # Refined averages
    r_count = refined_count or 1
    refined_vocab_ratio = len(set(refined_all_words)) / len(refined_all_words) if refined_all_words else 0
    refined_filler_density = refined_filler_count / refined_total_words if refined_total_words else 0

    # ── Session-level stats (for MOTD variety — ISS-070) ──
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    week_start = now.toordinal() - now.weekday()  # Monday = 0
    today_count = 0
    today_words = 0
    active_days: set[int] = set()
    for t in transcripts:
        try:
            dt = datetime.fromisoformat(t.created_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if dt.strftime("%Y-%m-%d") == today_str:
            today_count += 1
            today_words += len((t.normalized_text or t.raw_text or "").split())
        ordinal = dt.toordinal()
        if ordinal >= week_start:
            active_days.add(ordinal)

    return {
        # ── Overall (backward-compatible) ──
        "count": count,
        "total_words": total_words,
        "recorded_seconds": recorded_seconds,
        "time_saved_seconds": time_saved,
        "avg_seconds": avg_seconds,
        "vocab_ratio": vocab_ratio,
        "total_silence_seconds": total_silence,
        "filler_count": filler_count,
        # ── Verbatim pipeline ──
        "verbatim_total_words": verbatim_total_words,
        "verbatim_filler_count": verbatim_filler_count,
        "verbatim_filler_density": round(verbatim_filler_density, 4),
        "verbatim_vocab_ratio": round(verbatim_vocab_ratio, 3),
        "verbatim_avg_fk_grade": round(verbatim_fk_sum / v_count, 1),
        "verbatim_avg_sentence_length": round(verbatim_avg_sentence_len_sum / v_count, 1),
        "verbatim_avg_word_length": round(verbatim_avg_word_len_sum / v_count, 1),
        "verbatim_long_word_ratio": round(verbatim_long_word_ratio_sum / v_count, 3),
        # ── Refinement pipeline ──
        "refined_count": refined_count,
        "refined_total_words": refined_total_words,
        "refined_filler_count": refined_filler_count,
        "refined_filler_density": round(refined_filler_density, 4),
        "refined_vocab_ratio": round(refined_vocab_ratio, 3),
        "refined_avg_fk_grade": round(refined_fk_sum / r_count, 1),
        "refined_avg_sentence_length": round(refined_avg_sentence_len_sum / r_count, 1),
        "refined_avg_word_length": round(refined_avg_word_len_sum / r_count, 1),
        "refined_long_word_ratio": round(refined_long_word_ratio_sum / r_count, 3),
        # ── Distribution data (for bell curves) ──
        "word_count_std_dev": std_dev(per_transcript_word_counts),
        "word_count_mean": round(sum(per_transcript_word_counts) / count, 1),
        "distribution_words": per_transcript_word_counts,
        "distribution_fk_verbatim": per_transcript_fk_verbatim,
        "distribution_fk_refined": per_transcript_fk_refined,
        # ── Session-level (ISS-070 MOTD variety) ──
        "today_count": today_count,
        "today_words": today_words,
        "days_active_this_week": len(active_days),
    }

"""
Obsidian Vault Service — Auto-save transcripts as markdown notes.

Follows the TitleGenerator pattern: fire-and-forget background writes,
no blocking, emits events for frontend notification.

Trigger: EventBus events (transcription_complete, transcript_updated).

Design:
    - Each transcript becomes one .md file in vault_path/subfolder/.
    - YAML frontmatter includes vociferous_id for update lookups.
    - An in-memory dict[int, Path] maps transcript IDs to file paths.
    - Atomic writes via tempfile + os.replace (same as save_settings).
    - All errors are caught — never blocks the transcription pipeline.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.core.settings import VociferousSettings
    from src.database.db import Transcript, TranscriptDB

logger = logging.getLogger(__name__)

# Characters unsafe for filenames across Windows/macOS/Linux.
_UNSAFE_FILENAME_RE = re.compile(r'[/\\:*?"<>|]')

# Maximum length for the title portion of the filename.
_MAX_TITLE_LEN = 60


def _sanitize_filename(name: str) -> str:
    """Convert a display name into a filesystem-safe string.

    Replaces unsafe characters with underscores, collapses runs of
    underscores, strips leading/trailing whitespace and dots, and
    truncates to _MAX_TITLE_LEN characters.
    """
    sanitized = _UNSAFE_FILENAME_RE.sub("_", name)
    sanitized = re.sub(r"_+", "_", sanitized)  # collapse runs
    sanitized = sanitized.strip().strip(".")
    return sanitized[:_MAX_TITLE_LEN] if sanitized else "voice-memo"


def _format_duration(ms: int) -> str:
    """Format milliseconds as a human-readable duration string (e.g. '1m 23s')."""
    total_s = ms // 1000
    if total_s < 60:
        return f"{total_s}s"
    minutes, seconds = divmod(total_s, 60)
    return f"{minutes}m {seconds}s"


class ObsidianVaultService:
    """Writes and updates Obsidian-compatible markdown notes for transcripts.

    Constructed with lambda providers (same pattern as TitleGenerator) so it
    can access settings, DB, and emit events without tight coupling.
    """

    def __init__(
        self,
        *,
        settings_provider: Callable[[], "VociferousSettings"],
        db_provider: Callable[[], "TranscriptDB | None"],
        event_emitter: Callable[[str, dict], None],
    ) -> None:
        self._settings = settings_provider
        self._db = db_provider
        self._emit = event_emitter

        # transcript_id → Path of the written vault file
        self._path_cache: dict[int, Path] = {}
        self._lock = threading.Lock()

        # Re-entrancy guard: transcript IDs currently being written.
        # Prevents overlapping save/update for the same transcript.
        self._pending: set[int] = set()

        # Debounce timers for transcript_updated events.
        # Maps transcript_id → Timer so rapid-fire updates coalesce.
        self._debounce_timers: dict[int, threading.Timer] = {}

    # ------------------------------------------------------------------
    # Public API (called from event handlers)
    # ------------------------------------------------------------------

    def save_transcript(self, transcript_id: int) -> None:
        """Write a new transcript to the vault. Fire-and-forget on a daemon thread."""
        thread = threading.Thread(
            target=self._save_task,
            args=(transcript_id,),
            daemon=True,
            name=f"obsidian-save-{transcript_id}",
        )
        thread.start()

    def update_transcript(self, transcript_id: int) -> None:
        """Debounced update: coalesce rapid events into one write after 300ms."""
        with self._lock:
            existing = self._debounce_timers.pop(transcript_id, None)
            if existing is not None:
                existing.cancel()

            timer = threading.Timer(0.3, self._update_task, args=(transcript_id,))
            timer.daemon = True
            self._debounce_timers[transcript_id] = timer
            timer.start()

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    def _save_task(self, transcript_id: int) -> None:
        """Background: fetch transcript, format, write to vault."""
        # Re-entrancy guard — skip if already writing this transcript.
        with self._lock:
            if transcript_id in self._pending:
                return
            self._pending.add(transcript_id)

        try:
            settings = self._settings()
            obs = settings.obsidian
            if not obs.enabled or not obs.vault_path:
                return

            db = self._db()
            if db is None:
                logger.warning("Obsidian save: DB unavailable for transcript %d", transcript_id)
                return

            transcript = db.get_transcript(transcript_id)
            if transcript is None:
                logger.warning("Obsidian save: transcript %d not found", transcript_id)
                return

            vault_dir = Path(obs.vault_path).resolve()
            if not vault_dir.is_dir():
                self._emit(
                    "obsidian_error",
                    {
                        "message": f"Vault path does not exist: {obs.vault_path}",
                        "transcript_id": transcript_id,
                    },
                )
                return

            # Resolve and validate that the subfolder stays inside the vault
            # (prevents path traversal via "../" in the subfolder setting).
            output_dir = (vault_dir / obs.subfolder).resolve()
            if not str(output_dir).startswith(str(vault_dir)):
                self._emit(
                    "obsidian_error",
                    {
                        "message": "Subfolder path escapes vault directory",
                        "transcript_id": transcript_id,
                    },
                )
                return

            # Ensure subfolder exists.
            output_dir.mkdir(parents=True, exist_ok=True)

            # Generate collision-safe filename.
            filename = self._generate_filename(transcript, output_dir)
            output_path = output_dir / filename

            # Format and write.
            content = self._format_markdown(transcript, obs.include_frontmatter)
            self._write_atomic(output_path, content)

            # Cache the path for future updates.
            with self._lock:
                self._path_cache[transcript_id] = output_path

            self._emit(
                "obsidian_saved",
                {
                    "transcript_id": transcript_id,
                    "path": str(output_path),
                },
            )
            logger.info("Obsidian save: transcript %d → %s", transcript_id, output_path)

        except Exception:
            logger.exception("Obsidian save: failed for transcript %d", transcript_id)
            self._emit(
                "obsidian_error",
                {
                    "message": "Failed to save transcript to vault",
                    "transcript_id": transcript_id,
                },
            )
        finally:
            with self._lock:
                self._pending.discard(transcript_id)

    def _update_task(self, transcript_id: int) -> None:
        """Background: update an existing vault file with new content."""
        # Re-entrancy guard — skip if a save/update is already in flight.
        with self._lock:
            self._debounce_timers.pop(transcript_id, None)
            if transcript_id in self._pending:
                return
            self._pending.add(transcript_id)

        try:
            settings = self._settings()
            obs = settings.obsidian
            if not obs.enabled or not obs.vault_path:
                return

            db = self._db()
            if db is None:
                return

            transcript = db.get_transcript(transcript_id)
            if transcript is None:
                return

            # Look up existing file path.
            with self._lock:
                existing_path = self._path_cache.get(transcript_id)

            if existing_path is None:
                # Cache miss — scan the subfolder for a file with matching vociferous_id.
                existing_path = self._scan_for_file(transcript_id, obs.vault_path, obs.subfolder)

            if existing_path is None or not existing_path.is_file():
                # No existing file — create one instead.  Release the pending
                # guard first since _save_task acquires it independently.
                with self._lock:
                    self._pending.discard(transcript_id)
                self._save_task(transcript_id)
                return

            # Overwrite with updated content.
            content = self._format_markdown(transcript, obs.include_frontmatter)
            self._write_atomic(existing_path, content)

            with self._lock:
                self._path_cache[transcript_id] = existing_path

            self._emit(
                "obsidian_saved",
                {
                    "transcript_id": transcript_id,
                    "path": str(existing_path),
                },
            )
            logger.info("Obsidian update: transcript %d → %s", transcript_id, existing_path)

        except Exception:
            logger.exception("Obsidian update: failed for transcript %d", transcript_id)
            self._emit(
                "obsidian_error",
                {
                    "message": "Failed to update transcript in vault",
                    "transcript_id": transcript_id,
                },
            )
        finally:
            with self._lock:
                self._pending.discard(transcript_id)

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_markdown(self, transcript: "Transcript", include_frontmatter: bool) -> str:
        """Build an Obsidian-compatible markdown document for a transcript.

        Structure:
            - YAML frontmatter with vociferous_id, timestamps, tags, duration
            - H1 heading with display name
            - Transcript body text
        """

        title = transcript.display_name or "Untitled Voice Memo"
        text = transcript.text  # normalized_text if available, else raw_text
        tag_names = [t.name for t in transcript.tags] if transcript.tags else []

        # Always include "vociferous" tag for easy vault filtering.
        all_tags = sorted(set(["vociferous"] + tag_names))

        has_refinement = bool(transcript.normalized_text and transcript.normalized_text != transcript.raw_text)

        lines: list[str] = []

        if include_frontmatter:
            lines.append("---")
            lines.append(f"vociferous_id: {transcript.id}")
            lines.append(f"created: {transcript.timestamp}")
            lines.append(f"duration: {_format_duration(transcript.duration_ms)}")
            lines.append(f"speech_duration: {_format_duration(transcript.speech_duration_ms)}")
            if all_tags:
                lines.append("tags:")
                for tag in all_tags:
                    # Quote to prevent YAML injection from tag names with special chars.
                    safe_tag = tag.replace('"', '\\"')
                    lines.append(f'  - "{safe_tag}"')
            lines.append(f"refined: {str(has_refinement).lower()}")
            lines.append("---")
            lines.append("")

        lines.append(f"# {title}")
        lines.append("")
        lines.append(text)
        lines.append("")  # trailing newline

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Filename generation
    # ------------------------------------------------------------------

    def _generate_filename(self, transcript: "Transcript", output_dir: Path) -> str:
        """Generate a collision-safe filename from the transcript timestamp and title.

        Format: YYYY-MM-DD_HHMMSS_sanitized-title.md
        Appends _2, _3, etc. on collision.
        """
        # Parse the ISO timestamp to extract date/time components.
        try:
            dt = datetime.fromisoformat(transcript.timestamp)
        except (ValueError, TypeError):
            dt = datetime.now()

        date_prefix = dt.strftime("%Y-%m-%d_%H%M%S")
        title_part = _sanitize_filename(transcript.display_name or "voice-memo")
        base = f"{date_prefix}_{title_part}"

        candidate = f"{base}.md"
        if not (output_dir / candidate).exists():
            return candidate

        # Collision — append incrementing suffix.
        for i in range(2, 100):
            candidate = f"{base}_{i}.md"
            if not (output_dir / candidate).exists():
                return candidate

        # Extremely unlikely fallback.
        return f"{base}_{os.getpid()}.md"

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    @staticmethod
    def _write_atomic(path: Path, content: str) -> None:
        """Atomically write content to path using tempfile + os.replace.

        Same crash-safe pattern used by save_settings() in settings.py.
        """
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".md.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, str(path))
        except Exception:
            # Clean up temp file on failure.
            if Path(tmp).exists():
                Path(tmp).unlink(missing_ok=True)
            raise

    # ------------------------------------------------------------------
    # Cache rebuild (cold start)
    # ------------------------------------------------------------------

    def _scan_for_file(self, transcript_id: int, vault_path: str, subfolder: str) -> Path | None:
        """Scan the vault subfolder for a file whose frontmatter contains a matching vociferous_id.

        This handles the cold-start case after an app restart where the
        in-memory cache is empty. We parse just the first few lines of
        each .md file looking for 'vociferous_id: N'.
        """
        # Trailing newline prevents false positives (e.g. id 42 matching 420).
        target = f"vociferous_id: {transcript_id}\n"
        scan_dir = Path(vault_path) / subfolder

        if not scan_dir.is_dir():
            return None

        try:
            for md_file in scan_dir.glob("*.md"):
                try:
                    # Read only the first 512 bytes — frontmatter is small.
                    with md_file.open("r", encoding="utf-8") as f:
                        head = f.read(512)
                    if target in head:
                        with self._lock:
                            self._path_cache[transcript_id] = md_file
                        return md_file
                except OSError:
                    continue
        except OSError:
            logger.warning("Obsidian scan: failed to read directory %s", scan_dir)

        return None

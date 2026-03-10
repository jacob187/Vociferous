# Vociferous — Workboard

> Last updated: 2026-03-10 (Removed resolved ISS-047 duplicate; added ISS-080 to Resolved; added ISS-081 Refinement View Redesign)

---

## Kanban Overview

| ID | Title | Area | Status | Notes |
|----|-------|------|--------|-------|
| ISS-049 | Transcript continuation/append | Transcribe / Feature | Backlog | Compound transcriptions — append to existing transcript. New "Compound" system tag. |
| ISS-052 | Analytics exclusion controls | EditView + Settings | Backlog | Per-transcript include_in_analytics DB boolean (default true). Migration needed. Partially blocked on ISS-018 for imported-transcript default. |
| ISS-081 | Refinement View Redesign | RefineView / Design | Backlog | Design-first — no code until spec agreed. Prerequisite for ISS-011. |
| ISS-011 | Custom prompt save and quick-select | Refine + Settings | Backlog | Depends on ISS-010 ✅ and ISS-081 design. No AC written. |
| ISS-018 | Audio file input for transcription | Transcribe / Feature | Backlog | Large pipeline feature; no detailed spec. |
| ISS-025 | Advanced model settings | Settings / Feature | Backlog | Audit ctranslate2 params first; very low priority. |
| ISS-072 | First-time onboarding & in-app feature guide | Infrastructure / Far Future | Backlog | Per-view first-visit popup. "Don't show again" checkbox. Settings → Features tab as persistent reference. Design TBD. |

---

## Open Issues — Design TBD

### ISS-081 · [Design] Refinement View Redesign

**View**: RefineView
**Severity**: Design-first — no implementation until spec agreed
**Depends On**: Standalone (prerequisite for ISS-011)

Every other major view has received a significant design pass. The Refinement view remains the most powerful feature in the product but is the least developed visually and interactively. This issue tracks the design conversation and resulting spec before any code is written.

**Design considerations** (open questions):
- Layout: how should the prompt builder, action controls, and output relate spatially?
- Where does the saved-prompt quick-select (ISS-011) live in the UI?
- Does the refined output preview sit inline or in a separate panel?
- Action bar usage: consistent with the centralized ActionBar pattern (ISS-079)?
- Should raw vs. refined text be togglable in-view or always separate (EditView)?

**Acceptance Criteria**: _TBD — design conversation required. This issue is complete when a spec with mockup/description and AC for ISS-011 is written._

---

### ISS-011 · [Feature] Custom prompt save and quick-select

**View**: Transcription detail (Refine tab) + Settings
**Severity**: Planned feature
**Depends On**: ISS-010 ✅ (PromptBuilder extraction — done)

Users should be able to write, save, and quickly select custom prompts for the refinement feature. A saved prompt library accessible from the Refine tab. Settings may expose management (create, rename, delete).

**Acceptance Criteria**: _TBD — design conversation required._

---

### ISS-072 · [Feature] First-time onboarding & in-app feature guide

**View**: All views + new Settings → Features tab
**Severity**: Far future — polish, not core functionality

Per-view first-visit popup explaining what the view does and its key features. Behaviour:
- Shown automatically on first visit to each view.
- Contains a "Don't show again" checkbox.
- If dismissed, accessible forever via **Settings → Features** tab, which acts as a built-in quick-reference guide.

**Design considerations**:
- Popup style should match the existing confirmation dialog aesthetic.
- The Features tab in Settings is a read-only reference, not configurable settings.
- Should be the last significant feature before the product enters maintenance mode.

**Acceptance Criteria**: _TBD — design conversation required._

---

## Open Issues — Phase 4 (Larger Features)

### ISS-018 · [Feature] Audio file input for transcription (v5.1)

**View**: Transcribe

File picker or drag-and-drop as alternative input source. Supported formats: `.wav`, `.mp3`, `.m4a` minimum. File-sourced transcripts stored identically to mic-sourced. Reuse/extend pipeline, don't duplicate.

**System tag linkage**: File-sourced transcripts automatically receive the **"Imported" system tag** (ISS-044 ✅ infrastructure in place). This distinguishes them from mic-sourced transcripts for filtering/analytics. The Imported tag also drives the default analytics exclusion behavior (ISS-052).

**Acceptance Criteria**:
- File picker or drag-and-drop in Transcribe view.
- Supported: `.wav`, `.mp3`, `.m4a` minimum.
- Duration, word count, all metadata populated correctly.
- Pipeline reused or cleanly extended.

---

### ISS-025 · [Feature] Advanced model settings in Output & Processing (v5.2)

**View**: Settings (Output & Processing)

Power users get access to SLM generation params (temperature, top-p, repetition penalty) behind collapsible "Advanced" section. Audit which `ctranslate2` params have meaningful effect before designing UI.

**Acceptance Criteria**:
- Hidden by default behind collapsible toggle.
- Only params with real effect exposed.
- Sensible defaults, enforced valid ranges.
- Settings persist and apply to SLM inference.

### ISS-049 · [Feature] Transcript Continuation / Append

**View**: TranscribeView + TranscriptsView
**Severity**: Feature — compound transcriptions

Allow appending a new recording to an existing transcript instead of always creating a new one. The new content is appended on a new line, separated from the original text. A **"Compound" system tag** is auto-applied to mark transcripts that contain multiple recording segments (system tag infrastructure from ISS-044 ✅ is in place).

**UI entry points**:
- **TranscribeView** (post-transcription): After recording completes, offer an "Append to..." button alongside the current "New" flow. Targets the most recently viewed/created transcript, or opens a picker.
- **TranscriptsView**: For existing transcripts, a context action or action bar button to "Continue recording" — opens TranscribeView in append mode targeting that transcript.

**Backend implications**:
- Append to `normalized_text` (and `raw_text`?) with newline separator.
- Duration, word count, and all metadata must be recalculated for the combined transcript.
- Analytics: compound transcripts count as one session or multiple? **TBD — needs decision.**

**Acceptance Criteria**:
- New recording can be appended to an existing transcript.
- New content separated by newline from existing text.
- "Compound" system tag auto-applied on first append.
- Duration and word count recalculated.
- Entry points in both TranscribeView (post-transcription) and TranscriptsView.
- Analytics handling for compound transcripts decided and documented.

---

### ISS-052 · [Feature] Analytics Exclusion Controls

**View**: EditView + Settings
**Severity**: UX — prevents data pollution in analytics
**Depends On**: ISS-018 (imported transcripts default setting)

Not every transcript should count toward personal voice analytics. Transcribing a movie, a podcast, or someone else's speech pollutes WPM averages, vocabulary metrics, and session statistics.

**Two controls**:

1. **Per-transcript checkbox** (EditView): "Include in analytics" toggle on each transcript. Defaults to `true` for mic-sourced transcripts. User can manually exclude any transcript.

2. **Imported transcripts default** (Settings): "Include imported transcripts in analytics" toggle. Defaults to `false`. When a file-sourced transcript is created (ISS-018), its analytics inclusion flag is set based on this setting. User can still override per-transcript in EditView.

**Backend implications**:
- New column on transcript: `include_in_analytics BOOLEAN DEFAULT 1`.
- Analytics queries (UserView, stats strip, heatmap) must filter on this column.
- Import pipeline (ISS-018) reads the setting to set the default value.

**Acceptance Criteria**:
- Per-transcript "include in analytics" checkbox in EditView.
- Settings toggle for imported transcript default.
- Analytics queries respect the flag.
- Mic-sourced transcripts default to included.
- Imported transcripts default to the setting value.
- Existing transcripts default to included (migration).

---

## Deferred (revisit when touching adjacent code)

| Item | Location | Why Deferred |
|------|----------|--------------|
| `transcript_to_dict()` location | `src/api/transcripts.py` | Affects WebSocket broadcast paths. Don't touch in isolation. |
| Inline validation duplication | `refine_transcript`, `retitle_transcript` | Extract to helper or push into Intent `__post_init__`. Low priority. |
| `system.py` download_model thread | `src/api/system.py` | Touches EventBus. Evaluate when system.py is next touched. |
| Settings global singleton | `src/core/settings.py` | `listener.py` and `log_manager.py` bypass coordinator. Theoretical risk only. |
| DB None handling audit | `src/database/db.py` consumers | Audited — theoretical concern only. `NOT NULL` schema constraints + dataclass defaults make None impossible. No code changes needed. |
| Audio ingestion / chunked recording | `src/services/` | Future feature: file-path input (ISS-018), crash recovery, retry button. |

---

## Resolved ✅

| ID | Title | Version | Completion Date | Commit |
|----|-------|---------|-----------------|--------|
| ISS-044 | "Refined" system tag | v5.5.0 | 2026-02-28 | bfc38b6 |
| ISS-045 | EditView redesign | v5.6.0 | 2026-03-09 | — |
| ISS-046 | Session auto-tagging | v5.6.2 | 2026-03-09 | 1fc83cb |
| ISS-054 | TranscriptsView action bar alignment | v5.6.1 | 2026-03-09 | 0ff5c28 |
| ISS-020 | Bulk refinement of transcripts | v5.6.3 | 2026-03-09 | 82b40a3 |
| ISS-065 | UI reactivity crash (localStorage + WS validators) | v5.6.4 | 2026-03-09 | 4ae8acd |
| ISS-055 | Bulk-refine API 405 (routes not registered) | v5.6.5 | 2026-03-09 | 2c1607e |
| ISS-061 | Model-change toast indicates restart requirement | v5.6.7 | 2026-03-09 | 66df05e |
| ISS-062 | Drop sub-4B SLM model support | v5.6.7 | 2026-03-09 | 66df05e |
| ISS-056 | Name setting in wrong tab | v5.6.6 | 2026-03-09 | 9028d5e |
| ISS-057 | Action bar background edge misaligns | v5.6.6 | 2026-03-09 | 9028d5e |
| ISS-058 | Recording status bar inside mic button area | v5.6.6 | 2026-03-09 | 9028d5e |
| ISS-059 | Session tags strip left-aligned | v5.6.6 | 2026-03-09 | 9028d5e |
| ISS-060 | Transcript rename missing from EditView | v5.6.6 | 2026-03-09 | 9028d5e |
| ISS-070 | TranscribeView greeting/MOTD too static | v5.6.8 | 2026-03-09 | 5d57c23 |
| ISS-071 | Recording orrery animation stutters at full 4K | v5.6.8 | 2026-03-09 | 5d57c23 |
| ISS-047 | Toast positioning overhaul | v5.7.0 | 2026-03-09 | c8ff80e |
| ISS-063 | EditView metrics expanded | v5.6.9 | 2026-03-09 | 2cdc2a8 |
| ISS-064 | Analytics rationalization audit | v5.6.9 | 2026-03-09 | 2cdc2a8 |
| ISS-069 | Session tags tooltip | v5.6.9 | 2026-03-09 | 2cdc2a8 |
| ISS-073 | UserView silence metrics use VAD data | v5.6.10 | 2026-03-09 | db169f6 |
| ISS-074 | Action bar border + right-edge alignment | v5.7.1 | 2026-03-09 | eaf8e86 |
| ISS-075 | Scrollbar accent color | v5.7.1 | 2026-03-09 | eaf8e86 |
| ISS-076 | Scrollbar stutter on fast scroll | v5.7.1 | 2026-03-09 | eaf8e86 |
| ISS-077 | Recording amorphous blob animation | v5.7.1 | 2026-03-09 | eaf8e86 |
| ISS-035 | UserView simple/advanced view toggle | v5.8.0 | 2026-03-09 | a28ed79 |
| ISS-037 | Radar chart analytics for UserView | v5.8.0 | 2026-03-09 | a28ed79 |
| ISS-079 | Action bar component centralization | v5.8.1 | 2026-03-09 | 2c1f6a8 |
| ISS-080 | UI Polish and Interaction Fixes | v5.8.2 | 2026-03-10 | 04c110d |
| ISS-078 | Bulk refine skip-already-refined | v5.8.3 | 2026-03-10 | — |
| ISS-010 | PromptBuilder extraction (prerequisite) | v5.4.x | — | — |
| ISS-026 | Confirmation dialogs (prerequisite) | v5.4.x | — | db097df |


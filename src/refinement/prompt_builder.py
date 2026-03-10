"""
PromptBuilder — Centralised prompt construction for all SLM interactions.

Owns all prompt templates, ChatML formatting, and few-shot examples.
Used by RefinementEngine (grammar pipeline) and InsightManager (freeform generation).
"""

from __future__ import annotations


class PromptBuilder:
    """
    Builds ChatML-formatted prompts for CTranslate2 Generator.

    Two modes:
    - **Refinement**: Grammar-fix pipeline with invariants and few-shot examples.
    - **Custom generation**: Freeform system+user prompt (insight, MOTD, etc.).
    """

    # ── Insight / MOTD templates ────────────────────────────────────────────

    INSIGHT_TEMPLATE: str = """\
You are a witty, encouraging assistant embedded in Vociferous, a local AI-powered \
speech-to-text application. The user dictates speech into text on their own machine \
with full privacy — no cloud, no data collection.

Here are the user's current usage statistics:

Overall:
- Total transcriptions: {count}
- Total words captured: {total_words}
- Total recording time: {recorded_time}
- Estimated time saved vs typing: {time_saved}
- Average recording length: {avg_length}

Verbatim (raw speech-to-text output):
- Vocabulary diversity: {verbatim_vocab_pct}
- Filler words detected: {verbatim_fillers} ({verbatim_filler_density} of words)
- Average Flesch-Kincaid reading level: grade {verbatim_fk_grade}
- Average sentence length: {verbatim_avg_sentence_len} words

{refinement_section}\
Write exactly ONE short paragraph (2-3 sentences) giving the user personalized, \
specific feedback based on these statistics. Be warm, direct, and subtly witty. \
Reference concrete numbers. If refinement data is available, highlight the measurable \
improvement between verbatim and refined text — this demonstrates the value of the \
refinement pipeline. Do not use bullet points. Do not begin with "You" or "Your". \
Do not mention the app name. Do not use exclamation marks more than once. \
Write as a confident peer, not a cheerleader."""

    MOTD_TEMPLATE: str = """\
You are embedded in Vociferous, a local AI-powered speech-to-text desktop application.
The user has captured the following usage data:

All-time:
- Total transcriptions: {count}
- Total words captured: {total_words}
- Average pace: {avg_pace} wpm
- Vocabulary diversity: {vocab_pct}
- Filler words detected: {verbatim_fillers} ({verbatim_filler_density} of words)
- Transcripts refined by AI: {refined_count}
- Estimated time saved vs typing: {time_saved}

Today's session:
- Transcriptions today: {today_count}
- Words today: {today_words}
- Days active this week: {days_active_this_week}

Write 1–3 sentences reacting to these stats. Be warm, specific, and subtly witty. \
Think a sharp colleague glancing at your dashboard — direct, a little wry, never generic.

Rules:
- Pick ONE angle from the data above. Vary your angle — do not always comment on the same stat.
- Reference a concrete number.
- Do NOT begin with "You" or "Your".
- No exclamation marks. No app name. No preamble or meta-talk.
- Do NOT describe what the app does.
- If today's session data is zero, focus on all-time stats instead.

Bad example: "You've made 13 transcriptions with 2,071 words at 150 wpm."
Good example: "Four sessions before lunch — either a productive morning or a very long meeting."
Good example: "153 words per minute and still finding time to say 'um' 78 times."
Good example: "Five days active this week. The keyboard is starting to feel jealous."

Output only the sentences. Nothing else."""

    def __init__(
        self,
        system_prompt: str = "",
        invariants: list[str] | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self.invariants = invariants or []

    # ── Public: Refinement prompt ───────────────────────────────────────────

    def build_refinement_messages(
        self,
        user_text: str,
        user_instructions: str = "",
        use_thinking: bool = False,
    ) -> list[dict[str, str]]:
        """Build ChatML messages for the grammar-fix refinement pipeline.

        Two modes:
        - **Default (no custom instructions)**: Grammar-fix pipeline with
          invariants enforcing meaning-preservation and output discipline.
        - **Custom instructions provided**: The user's instructions become
          the ENTIRE task.  Invariants are NOT sent — the user is in control
          and the safety rails would only confuse the model or fight the
          user's intent.
        """
        custom = user_instructions.strip() if user_instructions else ""

        if custom:
            system_content = self.system_prompt
            task_directive = custom
        else:
            invariants_text = "\n".join(f"- {i}" for i in self.invariants)
            system_content = f"""{self.system_prompt}

Rules:
{invariants_text}
- Output ONLY the corrected text. No explanations, no preamble.""".strip()
            task_directive = "Fix all grammar, spelling, punctuation, and capitalization errors."

        think_directive = "" if use_thinking else "/no_think\n\n"

        user_content = f"""{think_directive}{task_directive}

Text:
{user_text}""".strip()

        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ]

    # ── Public: Custom / freeform prompt ────────────────────────────────────

    def build_custom_messages(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> list[dict[str, str]]:
        """Build ChatML messages for freeform generation (insight, MOTD, etc.)."""
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"/no_think\n\n{user_prompt}"},
        ]

    # ── Public: ChatML serialisation ────────────────────────────────────────

    @staticmethod
    def messages_to_chatml(messages: list[dict[str, str]]) -> str:
        """Convert a list of chat messages to a ChatML-formatted string.

        CTranslate2 Generator works at the token level — no built-in chat
        template support.  We apply the ChatML template ourselves, then
        tokenize, then generate.
        """
        parts: list[str] = []
        for msg in messages:
            parts.append(f"<|im_start|>{msg['role']}\n{msg['content']}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

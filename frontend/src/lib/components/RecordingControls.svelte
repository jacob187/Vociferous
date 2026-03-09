<script lang="ts">
    /**
     * RecordingControls — Mic button, recording orrery, cancel/status bar, and timer.
     *
     * Extracted from TranscribeView to reduce its line count. This component owns
     * the visual recording controls but delegates state transitions to the parent
     * via callbacks and bound props.
     */

    import { Mic, Trash2 } from "lucide-svelte";
    import RecordingOrrery from "./RecordingOrrery.svelte";
    import StyledButton from "./StyledButton.svelte";

    interface Props {
        /** Whether a recording is currently active. */
        isRecording: boolean;
        /** Current audio level (0–1) for the orrery visualizer. */
        audioLevel: number;
        /** Elapsed recording time in milliseconds. */
        elapsedMs: number;
        /** Called when the user clicks the idle mic button. */
        onstart: () => void;
        /** Called when the user clicks the orrery (stop recording). */
        onstop: () => void;
        /** Called when the user clicks the cancel button. */
        oncancel: () => void;
    }

    let { isRecording, audioLevel, elapsedMs, onstart, onstop, oncancel }: Props = $props();

    function formatElapsed(ms: number): string {
        const totalSec = Math.floor(ms / 1000);
        const m = Math.floor(totalSec / 60);
        const s = totalSec % 60;
        return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }
</script>

<!-- Mic / Orrery button -->
<div class="flex flex-col items-center justify-center gap-[var(--space-4)]">
    {#if isRecording}
        <button
            class="w-[160px] h-[160px] rounded-full cursor-pointer p-0 bg-transparent border-none focus:outline-none"
            onclick={onstop}
            aria-label="Stop recording"
            title="Stop recording and transcribe"
        >
            <RecordingOrrery {audioLevel} size={160} />
        </button>
    {:else}
        <button
            class="w-[160px] h-[160px] rounded-full border-2 border-[var(--accent)] bg-transparent text-[var(--accent)] cursor-pointer flex items-center justify-center transition-[background,border-color,color] duration-[var(--transition-fast)] hover:bg-[var(--hover-overlay-blue)] hover:border-[var(--accent-hover)] hover:text-[var(--accent-hover)]"
            onclick={onstart}
            aria-label="Start recording"
            title="Start recording"
        >
            <Mic size={56} strokeWidth={1.5} />
        </button>
        <p class="text-[var(--text-base)] text-[var(--text-tertiary)] m-0">Click to record</p>
    {/if}
</div>

<!-- Recording status bar (cancel + timer) — only visible while recording -->
{#if isRecording}
    <div class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] shrink-0">
        <StyledButton
            variant="danger-outline"
            size="sm"
            onclick={oncancel}
            ariaLabel="Cancel recording and discard audio"
            title="Cancel recording and discard captured audio"
        >
            <Trash2 size={15} /> Cancel
        </StyledButton>

        <div class="flex-1 flex items-center justify-center gap-[var(--space-2)]">
            <span
                class="w-2 h-2 rounded-full bg-[var(--color-danger)] shrink-0 animate-[pulse-dot_1.2s_ease-in-out_infinite]"
            ></span>
            <span class="text-[var(--text-sm)] text-[var(--color-danger)] whitespace-nowrap"
                >Recording in progress…</span
            >
        </div>

        <span
            class="text-[var(--text-sm)] font-[var(--font-mono)] text-[var(--text-tertiary)] tabular-nums whitespace-nowrap"
            >{formatElapsed(elapsedMs)}</span
        >
    </div>
{/if}

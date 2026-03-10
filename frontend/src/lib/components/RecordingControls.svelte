<script lang="ts">
    /**
     * RecordingControls — Mic button and active-recording pulse visualizer.
     *
     * Extracted from TranscribeView to reduce its line count. Owns the visual
     * recording controls and delegates state transitions to the parent via
     * callbacks. The recording status bar lives in TranscribeView.
     */

    import { Mic } from "lucide-svelte";
    import RecordingPulse from "./RecordingPulse.svelte";

    interface Props {
        /** Whether a recording is currently active. */
        isRecording: boolean;
        /** Current audio level (0–1) for the pulse visualizer. */
        audioLevel: number;
        /** Called when the user clicks the idle mic button. */
        onstart: () => void;
        /** Called when the user clicks the active recording button (stop). */
        onstop: () => void;
    }

    let { isRecording, audioLevel, onstart, onstop }: Props = $props();
</script>

<!-- Mic / Pulse button -->
<div class="flex flex-col items-center justify-center gap-[var(--space-4)]">
    {#if isRecording}
        <button
            class="w-[160px] h-[160px] rounded-full cursor-pointer p-0 bg-transparent border-none focus:outline-none overflow-visible"
            onclick={onstop}
            aria-label="Stop recording"
            title="Stop recording and transcribe"
        >
            <RecordingPulse {audioLevel} size={160} />
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

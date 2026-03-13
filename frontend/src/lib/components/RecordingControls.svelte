<script lang="ts">
    /**
     * RecordingControls — Single mic button for idle and recording states.
     *
     * ONE button element for both states. Idle: blue border + mic icon.
     * Recording: RecordingPulse overlay fades in (blob, glow, orange).
     * No DOM destruction/creation on state change — smooth visual transition.
     *
     * Uses ResizeObserver on its container to compute the button diameter
     * from actual available space (same pattern as ActivityHeatmap).
     * Viewport units (vmin) are NOT used — they break under CSS zoom.
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

    let containerEl: HTMLDivElement | undefined = $state();
    let btnSize = $state(160);

    // Watch the container and scale the button to 40% of the smaller dimension,
    // clamped between 80px and 160px.
    $effect(() => {
        if (!containerEl) return;
        const ro = new ResizeObserver(([e]) => {
            const { width, height } = e.contentRect;
            const side = Math.min(width, height);
            btnSize = Math.max(80, Math.min(160, Math.round(side * 0.4)));
        });
        ro.observe(containerEl);
        return () => ro.disconnect();
    });
</script>

<!-- Mic / Pulse button — single element, two visual states -->
<div
    bind:this={containerEl}
    class="flex flex-col items-center justify-center gap-[var(--space-4)] w-full h-full"
>
    <button
        class="relative rounded-full cursor-pointer p-0 border-2 flex items-center justify-center transition-[border-color,background-color,color] duration-300 focus:outline-none overflow-visible
            {isRecording
                ? 'border-transparent bg-transparent text-transparent'
                : 'border-[var(--accent)] bg-transparent text-[var(--accent)] hover:bg-[var(--hover-overlay-blue)] hover:border-[var(--accent-hover)] hover:text-[var(--accent-hover)]'}"
        style="width: {btnSize}px; height: {btnSize}px;"
        onclick={isRecording ? onstop : onstart}
        aria-label={isRecording ? "Stop recording" : "Start recording"}
        title={isRecording ? "Stop recording and transcribe" : "Start recording"}
    >
        <!-- Idle: Mic icon (fades out when recording) -->
        <Mic
            class="w-[35%] h-[35%] transition-opacity duration-300 {isRecording ? 'opacity-0' : 'opacity-100'}"
            strokeWidth={1.5}
        />
        <!-- Recording: Pulse overlay (fades in when recording) -->
        <div
            class="absolute inset-0 transition-opacity duration-300 {isRecording ? 'opacity-100' : 'opacity-0 pointer-events-none'}"
        >
            <RecordingPulse {audioLevel} size={btnSize} />
        </div>
    </button>
    <p
        class="text-[var(--text-base)] text-[var(--text-tertiary)] m-0 transition-opacity duration-300
            {isRecording ? 'opacity-0' : 'opacity-100'}"
    >
        {isRecording ? '\u00A0' : 'Click to record'}
    </p>
</div>

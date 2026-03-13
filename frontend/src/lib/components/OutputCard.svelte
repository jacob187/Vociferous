<script lang="ts">
    /**
     * OutputCard — Output behavior toggles.
     *
     * Manages: trailing space, auto-copy, markdown rendering.
     */

    import ToggleSwitch from "./ToggleSwitch.svelte";

    interface Props {
        config: Record<string, any>;
        getSafe: (obj: any, path: string, fallback?: any) => any;
        setSafe: (path: string, value: any) => void;
    }

    let { config, getSafe, setSafe }: Props = $props();
</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-trailing"
            data-tip="Appends a space after each transcription for seamless dictation into text fields."
            >Add Trailing Space</label
        >
        <ToggleSwitch
            checked={getSafe(config, "output.add_trailing_space", false)}
            onChange={() => setSafe("output.add_trailing_space", !getSafe(config, "output.add_trailing_space", false))}
        />
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-autocopy"
            data-tip="Automatically copies transcription to clipboard when complete. Works even when the window is not focused."
            >Auto-Copy to Clipboard</label
        >
        <ToggleSwitch
            checked={getSafe(config, "output.auto_copy_to_clipboard", true)}
            onChange={() =>
                setSafe("output.auto_copy_to_clipboard", !getSafe(config, "output.auto_copy_to_clipboard", true))}
        />
    </div>
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-markdown-editor"
            data-tip="Render transcript text as formatted markdown in the Edit View by default. You can still toggle per-session."
            >Markdown in Editor</label
        >
        <ToggleSwitch
            checked={getSafe(config, "display.render_markdown_in_editor", false)}
            onChange={() =>
                setSafe(
                    "display.render_markdown_in_editor",
                    !getSafe(config, "display.render_markdown_in_editor", false),
                )}
        />
    </div>
</div>

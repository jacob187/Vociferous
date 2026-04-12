<script lang="ts">
    /**
     * ObsidianCard — Obsidian Vault auto-save settings.
     *
     * Manages: enable/disable, vault path, subfolder, frontmatter toggle.
     * Follows the same props interface as OutputCard.
     */

    import { pickFolder } from "../api";
    import ToggleSwitch from "./ToggleSwitch.svelte";
    import { FolderOpen, Check, TriangleAlert } from "lucide-svelte";

    interface Props {
        config: Record<string, any>;
        getSafe: (obj: any, path: string, fallback?: any) => any;
        setSafe: (path: string, value: any) => void;
    }

    let { config, getSafe, setSafe }: Props = $props();

    let browsing = $state(false);

    async function handleBrowse() {
        browsing = true;
        try {
            const result = await pickFolder();
            if (result.path) {
                setSafe("obsidian.vault_path", result.path);
            }
        } finally {
            browsing = false;
        }
    }

    let vaultPath = $derived(getSafe(config, "obsidian.vault_path", ""));
    let isEnabled = $derived(getSafe(config, "obsidian.enabled", false));
</script>

<div class="flex flex-col gap-[var(--space-3)]">
    <!-- Enable toggle -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-obsidian-enabled"
            data-tip="Automatically save each transcription as a markdown note in your Obsidian vault."
            >Auto-Save to Vault</label
        >
        <ToggleSwitch
            checked={isEnabled}
            onChange={() => setSafe("obsidian.enabled", !isEnabled)}
        />
    </div>

    <!-- Vault path -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-obsidian-vault"
            data-tip="Absolute path to your Obsidian vault root folder (the folder containing the .obsidian directory)."
            >Vault Path</label
        >
        <div class="flex items-center gap-[var(--space-2)] max-w-[460px]">
            <input
                id="setting-obsidian-vault"
                type="text"
                class="h-9 flex-1 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)]"
                placeholder="/path/to/vault"
                value={vaultPath}
                oninput={(e) => setSafe("obsidian.vault_path", (e.target as HTMLInputElement).value)}
            />
            <button
                type="button"
                class="flex items-center justify-center w-9 h-9 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] text-[var(--accent)] cursor-pointer transition-colors duration-150 hover:bg-[var(--hover-overlay-blue)] disabled:opacity-40 disabled:cursor-not-allowed"
                aria-label="Browse for vault folder"
                disabled={browsing}
                onclick={handleBrowse}
            >
                <FolderOpen size={16} />
            </button>
            {#if vaultPath}
                <span class="flex items-center text-[var(--text-xs)]" title={vaultPath ? "Path set" : ""}>
                    <Check size={14} class="text-[var(--success)]" />
                </span>
            {/if}
        </div>
    </div>

    <!-- Subfolder -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-obsidian-subfolder"
            data-tip="Notes are saved inside this subfolder within your vault. Created automatically if it doesn't exist."
            >Subfolder</label
        >
        <input
            id="setting-obsidian-subfolder"
            type="text"
            maxlength="100"
            class="h-9 w-48 rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-primary)] px-[var(--space-2)] text-[var(--text-sm)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)]"
            placeholder="Vociferous"
            value={getSafe(config, "obsidian.subfolder", "Vociferous")}
            oninput={(e) => setSafe("obsidian.subfolder", (e.target as HTMLInputElement).value)}
        />
    </div>

    <!-- Include frontmatter -->
    <div class="grid grid-cols-[200px_minmax(0,1fr)] items-center gap-x-[var(--space-4)] min-h-[36px]">
        <label
            class="text-[var(--text-sm)] text-[var(--text-primary)]"
            for="setting-obsidian-frontmatter"
            data-tip="Include YAML frontmatter with metadata (date, duration, tags). Required for Obsidian Dataview queries."
            >Include Frontmatter</label
        >
        <ToggleSwitch
            checked={getSafe(config, "obsidian.include_frontmatter", true)}
            onChange={() =>
                setSafe(
                    "obsidian.include_frontmatter",
                    !getSafe(config, "obsidian.include_frontmatter", true),
                )}
        />
    </div>

    <!-- Info callout when enabled but no path set -->
    {#if isEnabled && !vaultPath}
        <div class="flex items-center gap-[var(--space-2)] mt-[var(--space-1)] px-[var(--space-3)] py-[var(--space-2)] rounded-[var(--radius-md)] bg-[var(--surface-secondary)] text-[var(--text-sm)] text-[var(--warning)]">
            <TriangleAlert size={14} />
            <span>Set a vault path to start auto-saving transcripts.</span>
        </div>
    {/if}
</div>

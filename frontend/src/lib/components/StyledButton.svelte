<script lang="ts">
    /**
     * Styled button — primary/secondary/destructive/ghost/danger-outline/neutral/danger-reveal variants.
     * Supports two sizes: "md" (dialogs / wizards) and "sm" (action bars).
     */

    import type { Snippet } from "svelte";

    interface Props {
        variant?: "primary" | "secondary" | "destructive" | "ghost" | "danger-outline" | "neutral" | "danger-reveal";
        size?: "sm" | "md";
        disabled?: boolean;
        onclick?: () => void;
        title?: string;
        ariaLabel?: string;
        children?: Snippet;
    }

    let { variant = "primary", size = "md", disabled = false, onclick, title, ariaLabel, children }: Props = $props();

    const baseClasses =
        "inline-flex items-center justify-center font-semibold cursor-pointer transition-all duration-150 whitespace-nowrap select-none rounded-lg disabled:opacity-40 disabled:cursor-not-allowed";

    /* Size classes — decoupled from color so we can mix freely */
    let sizeClasses = $derived.by(() => {
        if (size === "sm") {
            return variant === "ghost" ? "h-8 px-2 text-xs gap-1.5" : "h-8 px-3 text-xs gap-1.5";
        }
        /* md (default) — original sizing per variant */
        switch (variant) {
            case "primary":
                return "h-12 min-w-60 px-6 text-base gap-2";
            case "ghost":
                return "h-10 px-2 text-sm gap-2";
            default:
                return "h-10 px-4 text-sm gap-2";
        }
    });

    /* Color / hover classes — pure visual treatment */
    let variantClasses = $derived.by(() => {
        switch (variant) {
            case "primary":
                return "border-none bg-[var(--accent)] text-[var(--gray-0)] hover:not-disabled:bg-[var(--accent-hover)]";
            case "secondary":
                return "border-none bg-[var(--surface-tertiary)] text-[var(--text-primary)] hover:not-disabled:bg-[var(--gray-6)]";
            case "destructive":
                return "border-none bg-[var(--color-danger-surface)] text-[var(--color-danger)] hover:not-disabled:bg-[var(--red-8)]";
            case "ghost":
                return "border-none bg-transparent text-[var(--text-secondary)] hover:not-disabled:text-[var(--text-primary)] hover:not-disabled:bg-[var(--hover-overlay)]";
            case "danger-outline":
                return "border border-[var(--color-danger)] bg-transparent text-[var(--color-danger)] hover:not-disabled:bg-[var(--color-danger-surface)]";
            case "neutral":
                return "border border-[var(--shell-border)] bg-[var(--surface-secondary)] text-[var(--text-secondary)] hover:not-disabled:text-[var(--text-primary)] hover:not-disabled:border-[var(--accent)]";
            case "danger-reveal":
                return "border border-[var(--shell-border)] bg-[var(--surface-secondary)] text-[var(--text-secondary)] hover:not-disabled:text-[var(--color-danger)] hover:not-disabled:border-[var(--color-danger)] hover:not-disabled:bg-[var(--color-danger-surface)]";
            default:
                return "";
        }
    });
</script>

<button class="{baseClasses} {sizeClasses} {variantClasses}" {disabled} {onclick} {title} aria-label={ariaLabel}>
    {#if children}{@render children()}{/if}
</button>

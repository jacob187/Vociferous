<script lang="ts">
    /**
     * EmptyState — Centered placeholder for empty/loading/idle content areas.
     * Use instead of copy-pasting the flex-col centered pattern everywhere.
     */
    import type { Component, SvelteComponent, Snippet } from "svelte";

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    type IconComponent = Component<any> | (new (...args: any[]) => SvelteComponent);

    interface Props {
        icon?: IconComponent;
        message?: string;
        iconSize?: number;
        height?: "full" | "fixed";
        spinning?: boolean;
        children?: Snippet;
    }

    let { icon: Icon, message, iconSize = 28, height = "full", spinning = false, children }: Props = $props();
</script>

<div
    class="flex flex-col items-center justify-center gap-[var(--space-2)] text-[var(--text-tertiary)] text-[var(--text-sm)]"
    class:h-full={height === "full"}
    class:h-[200px]={height === "fixed"}
>
    {#if Icon}
        <div class:spin={spinning}>
            <Icon size={iconSize} strokeWidth={1.2} />
        </div>
    {/if}
    {#if message}
        <p class="m-0">{message}</p>
    {/if}
    {#if children}{@render children()}{/if}
</div>

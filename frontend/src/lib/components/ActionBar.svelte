<script lang="ts">
    import type { Snippet } from "svelte";

    interface Props {
        children: Snippet;
        gap?: string; // Tailwind gap class — default gap-2; pass "gap-3" for wider spacing
    }

    let { children, gap = "gap-2" }: Props = $props();
</script>

<div class="shrink-0 px-4 py-2 overflow-y-auto" style="scrollbar-gutter: stable">
    <div class="flex items-center {gap} bg-[var(--surface-secondary)] rounded-lg px-3 py-1.5">
        {@render children()}
    </div>
</div>

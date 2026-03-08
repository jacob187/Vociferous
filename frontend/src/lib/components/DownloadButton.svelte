<!--
    DownloadButton — ghost-outline accent button for model download actions.
    Used in AsrModelCard and OutputCard.
-->
<script lang="ts">
    import { Download } from "lucide-svelte";

    interface Props {
        onclick: () => void;
    }

    let { onclick }: Props = $props();
</script>

<button
    class="inline-flex items-center gap-1 py-1.5 px-3 border border-[var(--accent)] rounded-[var(--radius-sm)] bg-transparent text-[var(--accent)] font-[var(--font-family)] text-[var(--text-xs)] font-[var(--weight-emphasis)] cursor-pointer whitespace-nowrap transition-[background,color] duration-[var(--transition-fast)] hover:bg-[var(--accent)] hover:text-[var(--gray-0)]"
    {onclick}
>
    <Download size={14} /> Download
</button>

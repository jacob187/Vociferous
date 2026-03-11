<script lang="ts">
    import { onMount, onDestroy } from "svelte";
    import { getTranscripts, getTranscript, getTags, refineTranscript, commitRefinement, type Transcript, type Tag } from "../lib/api";
    import { toast } from "../lib/toast.svelte";
    import { ws } from "../lib/ws";
    import { nav } from "../lib/navigation.svelte";
    import WorkspacePanel from "../lib/components/WorkspacePanel.svelte";
    import MarkdownBody from "../lib/components/MarkdownBody.svelte";
    import StyledButton from "../lib/components/StyledButton.svelte";
    import EmptyState from "../lib/components/EmptyState.svelte";
    import ActionBar from "../lib/components/ActionBar.svelte";
    import {
        Sparkles,
        Copy,
        Check,
        RotateCcw,
        ThumbsUp,
        Pencil,
        X,
        Trash2,
        Loader2,
        FileText,
        ChevronDown,
    } from "lucide-svelte";

    const DEFAULT_REFINEMENT_LEVEL = 2;

    /* ── State ── */
    let transcripts: Transcript[] = $state([]);
    let selectedId: number | null = $state(null);
    let originalText = $state("");
    let refinedText = $state("");
    let customInstructions = $state("");
    let isRefining = $state(false);
    let hasRefined = $state(false);
    let copied = $state(false);
    let copiedOriginal = $state(false);
    let accepted = $state(false);
    let showPicker = $state(false);
    let loadingTranscripts = $state(true);
    let refineStatus = $state("");
    let refineElapsed = $state(0);
    let refineTimer: ReturnType<typeof setInterval> | null = $state(null);
    let refineError = $state("");

    /* ── Prompt System ── */
    let savedPrompts: Transcript[] = $state([]);
    let promptTagId: number | null = $state(null);

    /* ── Data ── */
    async function loadPrompts() {
        try {
            const tags = await getTags();
            const promptTag = tags.find((t: Tag) => t.name === "Prompt" && t.is_system);
            if (!promptTag) return;
            promptTagId = promptTag.id;
            const result = await getTranscripts({ limit: 100, tag_ids: [promptTag.id] });
            savedPrompts = result.items;
        } catch (e) {
            console.error("Failed to load saved prompts:", e);
        }
    }

    function handlePromptSelect(e: Event) {
        const val = (e.target as HTMLSelectElement).value;
        if (!val) return;
        const id = Number(val);
        const prompt = savedPrompts.find((p) => p.id === id);
        if (prompt) {
            customInstructions = prompt.text || prompt.normalized_text || prompt.raw_text || "";
        }
        // Reset select to placeholder so user can re-select the same prompt
        (e.target as HTMLSelectElement).value = "";
    }

    async function loadTranscripts() {
        try {
            transcripts = (await getTranscripts({ limit: 100 })).items;
        } catch (e) {
            console.error("Failed to load transcripts:", e);
        } finally {
            loadingTranscripts = false;
        }
    }

    async function selectTranscript(id: number) {
        selectedId = id;
        refinedText = "";
        hasRefined = false;
        showPicker = false;
        refineError = "";
        if (isRefining) {
            isRefining = false;
            stopRefineTimer();
        }
        try {
            const t = await getTranscript(id);
            originalText = t.text || t.normalized_text || t.raw_text || "";
        } catch (e) {
            console.error("Failed to load transcript:", e);
            originalText = "";
        }
    }

    /* ── Actions ── */
    function startRefineTimer() {
        refineElapsed = 0;
        refineStatus = "Preparing…";
        if (refineTimer) clearInterval(refineTimer);
        refineTimer = setInterval(() => {
            refineElapsed += 1;
        }, 1000);
    }

    function stopRefineTimer() {
        if (refineTimer) {
            clearInterval(refineTimer);
            refineTimer = null;
        }
        refineStatus = "";
    }

    async function handleRefine() {
        if (selectedId === null || isRefining) return;
        isRefining = true;
        refineError = "";
        startRefineTimer();
        try {
            await refineTranscript(selectedId, DEFAULT_REFINEMENT_LEVEL, customInstructions.trim());
            // Wait for WebSocket event to deliver result
        } catch (e) {
            console.error("Refinement failed:", e);
            refineError = e instanceof Error ? e.message : "Refinement request failed. Check that the model is loaded.";
            toast.error(refineError);
            isRefining = false;
            stopRefineTimer();
        }
    }

    async function handleAccept() {
        if (!refinedText || selectedId === null) return;
        try {
            await commitRefinement(selectedId, refinedText);
            navigator.clipboard.writeText(refinedText);
            originalText = refinedText;
            accepted = true;
            setTimeout(() => (accepted = false), 2000);
            toast.success("Refinement committed");
        } catch (e) {
            toast.error(e instanceof Error ? e.message : "Failed to commit refinement");
        }
    }

    function editSelectedTranscript() {
        if (selectedId == null) return;
        nav.navigateToEdit(selectedId, { view: "refine", transcriptId: selectedId });
    }

    function handleDiscard() {
        refinedText = "";
        hasRefined = false;
    }

    async function handleRerun() {
        refinedText = "";
        hasRefined = false;
        await handleRefine();
    }

    function handleCopyOriginal() {
        navigator.clipboard.writeText(originalText);
        copiedOriginal = true;
        setTimeout(() => (copiedOriginal = false), 2000);
    }

    function handleCopyRefined() {
        navigator.clipboard.writeText(refinedText);
        copied = true;
        setTimeout(() => (copied = false), 2000);
    }

    /* ── Formatting ── */
    function truncateText(text: string, max = 50): string {
        if (text.length <= max) return text;
        return text.slice(0, max) + "…";
    }

    /* ── WebSocket ── */
    let unsubRefinement: (() => void) | undefined;
    let unsubRefinementError: (() => void) | undefined;
    let unsubRefinementProgress: (() => void) | undefined;

    onMount(() => {
        loadTranscripts();
        loadPrompts();

        unsubRefinement = ws.on("refinement_complete", (data) => {
            if (data.transcript_id === selectedId) {
                refinedText = data.text;
                isRefining = false;
                hasRefined = true;
                refineError = "";
                stopRefineTimer();
                toast.success("Refinement complete");
            }
        });

        unsubRefinementError = ws.on("refinement_error", (data) => {
            if (!data.transcript_id || data.transcript_id === selectedId) {
                isRefining = false;
                stopRefineTimer();
                refineError = data.message || "Refinement failed unexpectedly.";
                toast.error(refineError);
                console.error("Refinement error:", data.message);
            }
        });

        unsubRefinementProgress = ws.on("refinement_progress", (data) => {
            if (data.transcript_id === selectedId) {
                refineStatus = data.message || "Processing…";
            }
        });
    });

    onDestroy(() => {
        unsubRefinement?.();
        unsubRefinementError?.();
        unsubRefinementProgress?.();
        stopRefineTimer();
    });

    $effect(() => {
        if (nav.current !== "refine") return;
        const pending = nav.consumePendingTranscriptRequest();
        if (!pending) return;
        if (pending.id === selectedId) return;
        void selectTranscript(pending.id);
    });
</script>

<div class="flex flex-col h-full bg-[var(--surface-primary)] overflow-hidden">
    <!-- Transcript Picker (compact top bar) -->
    <div
        class="relative py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)] flex justify-center"
    >
        <button
            class="flex items-center gap-[var(--space-2)] py-[var(--space-2)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-md)] bg-[var(--surface-secondary)] text-[var(--text-primary)] text-[var(--text-sm)] cursor-pointer w-full max-w-[400px] text-left transition-[border-color] duration-[var(--transition-fast)] hover:border-[var(--accent)]"
            onclick={() => (showPicker = !showPicker)}
        >
            <FileText size={15} />
            <span>
                {#if selectedId !== null}
                    {transcripts.find((t) => t.id === selectedId)?.display_name?.trim() || `Transcript #${selectedId}`}
                {:else}
                    Select a transcript to refine…
                {/if}
            </span>
            <ChevronDown size={14} />
        </button>

        {#if showPicker}
            <div
                class="absolute top-full left-1/2 -translate-x-1/2 w-full max-w-[400px] max-h-[280px] overflow-y-auto bg-[var(--surface-primary)] border border-[var(--shell-border)] rounded-[var(--radius-md)] shadow-[0_8px_24px_rgba(0,0,0,0.3)] z-10"
            >
                {#if loadingTranscripts}
                    <div
                        class="p-[var(--space-4)] text-center text-[var(--text-tertiary)] text-[var(--text-sm)] flex items-center justify-center gap-[var(--space-2)]"
                    >
                        <Loader2 size={16} class="spin" /> Loading…
                    </div>
                {:else if transcripts.length === 0}
                    <div
                        class="p-[var(--space-4)] text-center text-[var(--text-tertiary)] text-[var(--text-sm)] flex items-center justify-center gap-[var(--space-2)]"
                    >
                        No transcripts available
                    </div>
                {:else}
                    {#each transcripts as t (t.id)}
                        <button
                            class="flex items-center gap-[var(--space-2)] w-full py-[var(--space-2)] px-[var(--space-3)] border-none bg-transparent text-[var(--text-primary)] text-[var(--text-sm)] text-left cursor-pointer transition-[background] duration-[var(--transition-fast)] hover:bg-[var(--hover-overlay)] {selectedId ===
                            t.id
                                ? 'bg-[rgba(90,159,212,0.1)]'
                                : ''}"
                            onclick={() => selectTranscript(t.id)}
                        >
                            <span class="text-[var(--text-tertiary)] text-[var(--text-xs)] shrink-0 min-w-[32px]"
                                >#{t.id}</span
                            >
                            <span class="overflow-hidden text-ellipsis whitespace-nowrap"
                                >{t.display_name?.trim() || truncateText(t.text)}</span
                            >
                        </button>
                    {/each}
                {/if}
            </div>
        {/if}
    </div>

    <!-- Comparison Area -->
    <div class="flex-1 flex gap-[var(--space-4)] p-[var(--space-4)] min-h-0 overflow-hidden">
        <!-- Original Panel -->
        <div
            class="flex-1 flex flex-col border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] overflow-hidden"
        >
            <div
                class="flex items-center justify-between py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]"
            >
                <h3 class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]">
                    Original Transcript
                </h3>
                <div class="flex items-center gap-1">
                    {#if originalText}
                        <button
                            class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                            onclick={handleCopyOriginal}
                            title="Copy original"
                        >
                            {#if copiedOriginal}
                                <Check size={14} />
                            {:else}
                                <Copy size={14} />
                            {/if}
                        </button>
                        <button
                            class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                            onclick={editSelectedTranscript}
                            title="Edit transcript"
                        >
                            <Pencil size={14} />
                        </button>
                    {/if}
                </div>
            </div>
            <div class="flex-1 overflow-y-auto p-[var(--space-4)]">
                {#if originalText}
                    <WorkspacePanel>
                        <MarkdownBody text={originalText} className="text-[var(--text-sm)] text-[var(--text-primary)]" />
                    </WorkspacePanel>
                {:else}
                    <EmptyState icon={FileText} message="Select a transcript to begin" />
                {/if}
            </div>
        </div>

        <!-- Refined Panel -->
        <div
            class="flex-1 flex flex-col border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)] overflow-hidden"
        >
            <div
                class="flex items-center justify-between py-[var(--space-3)] px-[var(--space-4)] border-b border-[var(--shell-border)]"
            >
                <h3 class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)]">
                    Refined / AI Suggestion
                </h3>
                <div class="flex items-center gap-1">
                    {#if refinedText}
                        <button
                            class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                            onclick={handleCopyRefined}
                            title="Copy refined"
                        >
                            {#if copied}
                                <Check size={14} />
                            {:else}
                                <Copy size={14} />
                            {/if}
                        </button>
                        <button
                            class="bg-none border-none text-[var(--text-tertiary)] cursor-pointer p-[var(--space-1)] rounded-[var(--radius-sm)] flex transition-colors duration-[var(--transition-fast)] hover:text-[var(--accent)]"
                            onclick={editSelectedTranscript}
                            title="Edit transcript"
                        >
                            <Pencil size={14} />
                        </button>
                    {/if}
                </div>
            </div>
            <div class="flex-1 overflow-y-auto p-[var(--space-4)]">
                {#if isRefining}
                    <EmptyState icon={Loader2} spinning>
                        <p class="m-0 text-[var(--text-sm)] text-[var(--text-secondary)] font-[var(--weight-emphasis)]">
                            {refineStatus}
                        </p>
                        <p class="m-0 font-[var(--font-mono)] text-[var(--text-xs)] text-[var(--text-tertiary)]">
                            {refineElapsed}s elapsed
                        </p>
                    </EmptyState>
                {:else if refineError}
                    <EmptyState>
                        <div
                            class="rounded-[var(--radius-md)] bg-red-500/10 border border-red-500/30 px-[var(--space-4)] py-[var(--space-3)] max-w-md text-center"
                        >
                            <p class="m-0 text-[var(--text-sm)] text-red-400 font-[var(--weight-emphasis)]">
                                Refinement Failed
                            </p>
                            <p class="m-0 mt-[var(--space-1)] text-[var(--text-xs)] text-red-400/80">{refineError}</p>
                        </div>
                    </EmptyState>
                {:else if refinedText}
                    <WorkspacePanel>
                        <MarkdownBody text={refinedText} className="text-[var(--text-sm)] text-[var(--text-primary)]" />
                    </WorkspacePanel>
                {:else}
                    <EmptyState
                        icon={Sparkles}
                        message={selectedId !== null ? "Ready to refine" : "Refinement will appear here"}
                    />
                {/if}
            </div>
        </div>
    </div>

    <!-- Footer Controls -->
    <div class="px-[var(--space-4)]">
        <!-- Custom Instructions Card -->
        <div
            class="flex flex-col gap-[var(--space-2)] border border-[var(--shell-border)] rounded-[var(--radius-lg)] py-[var(--space-3)] px-[var(--space-4)] bg-[var(--surface-secondary)]"
        >
            <h4
                class="m-0 text-[var(--text-base)] font-[var(--weight-emphasis)] text-[var(--text-secondary)] text-center"
            >
                Instructions (Optional)
            </h4>
            <p class="m-0 text-[var(--text-xs)] text-[var(--text-tertiary)] text-center">
                Default behavior fixes grammar and punctuation with minimal wording changes.
            </p>
            {#if savedPrompts.length > 0}
                <div class="flex items-center gap-[var(--space-2)]">
                    <span class="text-[var(--text-xs)] text-[var(--text-tertiary)] shrink-0">Saved Prompts</span>
                    <select
                        class="flex-1 py-1.5 px-2 border border-[var(--shell-border)] rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-primary)] text-[var(--text-xs)] outline-none cursor-pointer transition-[border-color] duration-[var(--transition-fast)] focus:border-[var(--accent)]"
                        onchange={handlePromptSelect}
                    >
                        <option value="">Load a saved prompt…</option>
                        {#each savedPrompts as p (p.id)}
                            <option value={p.id}>{p.display_name || `Prompt #${p.id}`}</option>
                        {/each}
                    </select>
                </div>
            {/if}
            <textarea
                class="flex-1 resize-none py-[var(--space-2)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-sm)] bg-[var(--surface-primary)] text-[var(--text-primary)] text-[var(--text-sm)] font-[inherit] outline-none transition-[border-color] duration-[var(--transition-fast)] focus:border-[var(--accent)] disabled:opacity-50"
                placeholder="Add specific instructions (e.g., 'Make it bullet points', 'Fix technical jargon')…"
                bind:value={customInstructions}
                disabled={isRefining}
                rows="4"
            ></textarea>
        </div>
    </div>

    <!-- Action Bar -->
    <ActionBar>
        {#if hasRefined}
            <StyledButton
                variant="danger-reveal"
                size="sm"
                title="Clear this refinement result from the view"
                onclick={handleDiscard}
            >
                <Trash2 size={15} /> Discard Result
            </StyledButton>
            <div class="flex-1"></div>
            {#if !accepted}
                <StyledButton variant="neutral" size="sm" onclick={handleRerun}>
                    <RotateCcw size={15} /> Re-run
                </StyledButton>
            {/if}
            <StyledButton variant="primary" size="sm" onclick={handleAccept}>
                {#if accepted}
                    <Check size={15} /> Accepted!
                {:else}
                    <ThumbsUp size={15} /> Accept & Copy
                {/if}
            </StyledButton>
        {:else}
            <div class="flex-1"></div>
            <StyledButton
                variant="primary"
                size="sm"
                onclick={handleRefine}
                disabled={selectedId === null || isRefining}
            >
                {#if isRefining}
                    <Loader2 size={15} class="spin" /> Refining… {refineElapsed}s
                {:else}
                    <Sparkles size={15} /> Refine
                {/if}
            </StyledButton>
        {/if}
    </ActionBar>
</div>

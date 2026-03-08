<script lang="ts">
    import { onMount } from "svelte";
    import { getTranscripts, getHealth, getConfig, getInsight, refreshInsight, type Transcript } from "../lib/api";
    import { ws } from "../lib/ws";
    import { formatCount } from "../lib/formatters";
    import { computeTextMetrics, fleschKincaidGrade, countFillers, estimateSyllables } from "../lib/textAnalysis";
    import StatCard from "../lib/components/StatCard.svelte";
    import ActivityHeatmap from "../lib/components/ActivityHeatmap.svelte";
    import DistributionChart from "../lib/components/DistributionChart.svelte";
    import {
        Timer,
        MessageSquareText,
        BarChart3,
        Clock,
        Gauge,
        PauseCircle,
        BookOpen,
        Volume2,
        MessageCircle,
        ChevronDown,
        ChevronRight,
        Github,
        Linkedin,
        User,
        Loader2,
        Sparkles,
        GraduationCap,
        Eraser,
        FileCheck2,
    } from "lucide-svelte";

    /* ── Constants ── */
    const SPEAKING_SPEED_WPM = 150;
    const DEFAULT_TYPING_WPM = 40;
    const TRANSCRIPT_EXPORT_LIMIT = 10000;

    /* ── State ── */
    let entries: Transcript[] = $state([]);
    let loading = $state(true);
    let userName = $state("");
    let typingWpm = $state(DEFAULT_TYPING_WPM);
    let showExplanations = $state(false);
    let healthInfo: { version: string; transcripts: number } | null = $state(null);
    let slmInsight = $state("");
    let refreshingInsight = $state(false);

    /* ── Derived Metrics ── */
    function safeText(e: { text: string }): string {
        return e.text || "";
    }

    let hasData = $derived(entries.length > 0);
    let count = $derived(entries.length);
    let totalWords = $derived(entries.reduce((s, e) => s + safeText(e).split(/\s+/).filter(Boolean).length, 0));

    let recordedSeconds = $derived.by(() => {
        const dur = entries.reduce((s, e) => s + (e.duration_ms || 0), 0) / 1000;
        if (dur > 0) return dur;
        if (totalWords > 0) return (totalWords / SPEAKING_SPEED_WPM) * 60;
        return 0;
    });

    let typingSeconds = $derived((totalWords / typingWpm) * 60);
    let timeSavedSeconds = $derived(Math.max(0, typingSeconds - recordedSeconds));
    let avgSeconds = $derived(count > 0 ? recordedSeconds / count : 0);

    let lexicalComplexity = $derived.by(() => {
        const allWords: string[] = [];
        for (const e of entries) {
            const words = safeText(e).toLowerCase().split(/\s+/);
            for (const w of words) {
                const c = w.replace(/^[.,!?;:'"()\[\]{}]+|[.,!?;:'"()\[\]{}]+$/g, "");
                if (c) allWords.push(c);
            }
        }
        if (allWords.length === 0) return 0;
        return new Set(allWords).size / allWords.length;
    });

    let totalSilence = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            if (e.duration_ms && e.duration_ms > 0) {
                const dur = e.duration_ms / 1000;
                const expected = (safeText(e).split(/\s+/).filter(Boolean).length / SPEAKING_SPEED_WPM) * 60;
                total += Math.max(0, dur - expected);
            }
        }
        return total;
    });

    let avgSilence = $derived.by(() => {
        let total = 0;
        let withDuration = 0;
        for (const e of entries) {
            if (e.duration_ms && e.duration_ms > 0) {
                const dur = e.duration_ms / 1000;
                const expected = (safeText(e).split(/\s+/).filter(Boolean).length / SPEAKING_SPEED_WPM) * 60;
                total += Math.max(0, dur - expected);
                withDuration++;
            }
        }
        return withDuration > 0 ? total / withDuration : 0;
    });

    let fillerCount = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            total += countFillers(safeText(e));
        }
        return total;
    });

    /* ── Verbatim vs Refined Metrics ── */
    let refinedEntries = $derived(entries.filter((e) => e.normalized_text && e.normalized_text !== e.raw_text));
    let refinedCount = $derived(refinedEntries.length);
    let hasRefinements = $derived(refinedCount > 0);

    /* Filler count across ALL transcripts (for Speech Quality section) */
    let verbatimFillerCount = $derived.by(() => {
        let total = 0;
        for (const e of entries) {
            total += countFillers(e.raw_text || "");
        }
        return total;
    });

    /* Refinement Impact — compare the SAME transcripts before/after */
    let rawFillersInRefined = $derived.by(() => {
        let total = 0;
        for (const e of refinedEntries) {
            total += countFillers(e.raw_text || "");
        }
        return total;
    });

    let refinedFillerCount = $derived.by(() => {
        let total = 0;
        for (const e of refinedEntries) {
            total += countFillers(e.normalized_text || "");
        }
        return total;
    });

    let fillersRemoved = $derived(rawFillersInRefined - refinedFillerCount);

    /* FK Grade — overall verbatim average (all transcripts) */
    let verbatimAvgFkGrade = $derived.by(() => {
        const grades = entries.map((e) => fleschKincaidGrade(e.raw_text || "")).filter((g) => g > 0);
        if (!grades.length) return 0;
        return Math.round((grades.reduce((s, g) => s + g, 0) / grades.length) * 10) / 10;
    });

    /* FK Grade — refined average (refined transcripts' normalized text) */
    let refinedAvgFkGrade = $derived.by(() => {
        const grades = refinedEntries.map((e) => fleschKincaidGrade(e.normalized_text || "")).filter((g) => g > 0);
        if (!grades.length) return 0;
        return Math.round((grades.reduce((s, g) => s + g, 0) / grades.length) * 10) / 10;
    });

    /* FK delta — compare same population: raw vs refined for refined transcripts only */
    let verbatimFkForRefined = $derived.by(() => {
        const grades = refinedEntries.map((e) => fleschKincaidGrade(e.raw_text || "")).filter((g) => g > 0);
        if (!grades.length) return 0;
        return Math.round((grades.reduce((s, g) => s + g, 0) / grades.length) * 10) / 10;
    });

    let fkGradeDelta = $derived(hasRefinements ? Math.round((refinedAvgFkGrade - verbatimFkForRefined) * 10) / 10 : 0);

    /* ── Polysyllabic word ratio (vocabulary sophistication) ── */
    function polyRatio(texts: string[]): number {
        let poly = 0,
            total = 0;
        for (const t of texts) {
            for (const w of t.split(/\s+/).filter(Boolean)) {
                total++;
                if (estimateSyllables(w) >= 3) poly++;
            }
        }
        return total > 0 ? Math.round((poly / total) * 1000) / 10 : 0;
    }

    let verbatimPolyRatio = $derived(polyRatio(entries.map((e) => e.raw_text || "")));
    let verbatimPolyForRefined = $derived(polyRatio(refinedEntries.map((e) => e.raw_text || "")));
    let refinedPolyRatio = $derived(polyRatio(refinedEntries.map((e) => e.normalized_text || "")));

    /* ── Distribution data for bell curves ── */
    let perTranscriptWordCounts = $derived(entries.map((e) => safeText(e).split(/\s+/).filter(Boolean).length));

    let perTranscriptFkVerbatim = $derived(
        entries.map((e) => fleschKincaidGrade(e.raw_text || "")).filter((g) => g > 0),
    );

    let perTranscriptFkRefined = $derived(
        refinedEntries.map((e) => fleschKincaidGrade(e.normalized_text || "")).filter((g) => g > 0),
    );

    let insight = $derived.by(() => {
        if (slmInsight) return slmInsight;
        if (count < 3) return "Don't be shy! Record a bit more to see your Vociferous metrics!";
        const ratio = recordedSeconds > 0 ? typingSeconds / recordedSeconds : 0;
        if (ratio > 2.5) return `Speaking ${ratio.toFixed(1)}x faster than typing—voice is your superpower!`;
        if (ratio > 1.5) return "Dictation is significantly faster than typing for you! You're a certified yapper~";
        if (avgSeconds < 15) return "Quick-capture style: rapid-fire notes and thoughts. Keep that momentum going!";
        if (avgSeconds > 60)
            return "Deep-work style: long-form dictation sessions. Now that's what I'd call elite comms!";
        return "Consistent dictation is key—keep up the great work!";
    });

    let titleText = $derived(userName.trim() ? `${userName.trim()}'s Vociferous Journey` : "Your Vociferous Journey");

    /* ── Formatting ── */
    function formatDuration(seconds: number): string {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        const m = Math.floor(seconds / 60);
        if (m < 60) return `${m}m`;
        const h = Math.floor(m / 60);
        const rm = m % 60;
        return rm === 0 ? `${h}h` : `${h}h ${rm}m`;
    }

    function formatPercent(v: number): string {
        return `${Math.round(v * 100)}%`;
    }

    /* ── Data loading ── */
    async function loadData() {
        loading = true;
        try {
            const [transcriptResult, health, config, insightRes] = await Promise.all([
                getTranscripts({ limit: TRANSCRIPT_EXPORT_LIMIT }),
                getHealth().catch(() => null),
                getConfig().catch(() => ({})),
                getInsight().catch(() => ({ text: "" })),
            ]);
            entries = transcriptResult.items;
            healthInfo = health;
            slmInsight = insightRes.text || "";
            // Extract user name and typing WPM from config
            const u = config as Record<string, unknown>;
            const userSection = u?.user as Record<string, unknown> | undefined;
            userName = (userSection?.name as string) ?? "";
            const wpm = Number(userSection?.typing_wpm);
            if (wpm > 0) typingWpm = wpm;
        } catch (e) {
            console.error("Failed to load user data:", e);
        } finally {
            loading = false;
        }
    }

    /* ── Lifecycle ── */
    onMount(() => {
        loadData();
        const unsubs = [
            ws.on("transcription_complete", () => loadData()),
            ws.on("transcript_deleted", () => loadData()),
            ws.on("transcripts_batch_deleted", () => loadData()),
            ws.on("insight_ready", (data) => {
                slmInsight = data.text || "";
                refreshingInsight = false;
            }),
        ];
        return () => unsubs.forEach((fn) => fn());
    });

    /* ── Explanations content ── */
    let explanations = $derived([
        { title: "Transcriptions", text: "Total count of all transcription entries stored in your database." },
        {
            title: "Words Captured",
            text: "Sum of word counts across all transcriptions. Each entry's words are counted individually.",
        },
        {
            title: "Time Recording",
            text: `Total recording duration in seconds. If duration is unavailable, estimated as: words ÷ ${SPEAKING_SPEED_WPM} WPM × 60 = seconds`,
        },
        {
            title: "Time Saved",
            text: `Productivity gain vs. manual typing. Calculated as: (words ÷ ${typingWpm} WPM × 60) − recording_time = time_saved. Based on average typing speed of ${typingWpm} WPM.`,
        },
        { title: "Average Length", text: "Mean duration per transcription: total_time ÷ transcription_count" },
        {
            title: "Total Silence",
            text: `Total accumulated silence (pauses) across all recordings. Calculated by summing the difference between actual recording duration and expected speech time for each entry.`,
        },
        {
            title: "Vocabulary",
            text: "Lexical complexity calculated as the ratio of unique words to total words across all transcriptions. Higher percentages indicate more diverse vocabulary usage.",
        },
        {
            title: "Average Pauses",
            text: `Estimated average silence per recording based on word density. Calculated by comparing actual recording duration against expected speech time (based on ${SPEAKING_SPEED_WPM} WPM).`,
        },
        {
            title: "Filler Words",
            text: "Total count of common filler words and phrases detected across all transcriptions. Includes patterns like 'um', 'uh', 'like', 'you know', 'basically', 'literally', 'actually', etc.",
        },
        {
            title: "Transcripts Refined",
            text: "Number of transcripts that have been processed by the SLM refinement pipeline. A transcript counts as refined when its normalized text differs from the raw ASR output.",
        },
        {
            title: "Fillers Removed",
            text: "Difference in filler word count between verbatim (raw ASR) and refined (post-SLM) text across all refined transcripts. Measures how many filler words the refinement pipeline eliminated.",
        },
        {
            title: "Reading Level",
            text: "Flesch-Kincaid Grade Level comparing the same transcripts before and after refinement. A lower grade after refinement means cleaner, shorter sentences — not dumbed-down content. The formula penalises long sentences above all else.",
        },
        {
            title: "FK Grade (Sentence Complexity)",
            text: "Flesch-Kincaid Grade Level measures sentence structure complexity — how long and syllabically heavy your sentences are. It does NOT measure sophistication or quality. Lower = more readable. Hemingway scores ~4; a newspaper article ~8; the Harvard Law Review ~18. Raw speech scores high because Whisper produces long unpunctuated runs; refinement breaks these into proper sentences.",
        },
        {
            title: "Complex Words (Vocabulary)",
            text: "Percentage of words with 3 or more syllables. Measures vocabulary sophistication independently of sentence structure — FK grade can't distinguish a short sophisticated sentence from a short simple one. Higher = more precise, technical, or formal vocabulary. Unlike FK grade, there's no 'better' direction: technical writing is naturally polysyllabic; conversational prose isn't.",
        },
        {
            title: "Distribution Charts",
            text: "Bell curves fitted to per-transcript values using Gaussian probability density. The curve shape reflects how consistent your transcripts are — tight curves mean uniform output, wide curves mean high variance. Overlapping verbatim/refined curves show how refinement shifts the distribution.",
        },
    ]);
</script>

<div class="flex flex-col h-full bg-[var(--surface-primary)]">
    <div class="flex-1 overflow-y-auto">
        <div
            class="w-full max-w-4xl min-w-[var(--content-min-width)] mx-auto pt-[var(--space-5)] px-[var(--space-5)] pb-32 flex flex-col gap-[var(--space-5)]"
        >
            {#if loading}
                <div class="flex flex-col items-center gap-[var(--space-3)] py-[96px] text-[var(--text-tertiary)]">
                    <Loader2 size={32} class="spin" />
                    <p>Loading your statistics…</p>
                </div>
            {:else if !hasData}
                <div
                    class="flex flex-col items-center gap-[var(--space-3)] py-[96px] px-[var(--space-6)] text-[var(--text-tertiary)] text-center border border-[var(--shell-border)] rounded-[var(--radius-lg)] bg-[var(--surface-secondary)]"
                >
                    <User size={40} strokeWidth={1.2} />
                    <h3 class="m-0 text-[var(--text-primary)] text-[var(--text-lg)]">No metrics yet</h3>
                    <p class="m-0 text-[var(--text-sm)] leading-[1.6]">
                        Metrics appear after your first transcription is saved.<br />Try making a recording to see your
                        impact.
                    </p>
                </div>
            {:else}
                <!-- ═══ Header ═══ -->
                <div class="flex flex-col items-center gap-[var(--space-2)]">
                    <h2 class="text-2xl font-[var(--weight-emphasis)] text-[var(--accent)] text-center m-0">
                        {titleText}
                    </h2>
                    <div class="w-12 h-[2px] rounded-full bg-[var(--accent)]"></div>
                    <p class="text-center text-[var(--text-sm)] text-[var(--accent)] italic m-0 max-w-[760px]">
                        {insight}
                    </p>
                    <button
                        class="text-[var(--text-xs)] text-[var(--text-tertiary)] hover:text-[var(--accent)] transition-colors cursor-pointer bg-transparent border-none p-0 disabled:opacity-40 disabled:cursor-not-allowed"
                        disabled={refreshingInsight}
                        onclick={async () => {
                            refreshingInsight = true;
                            try {
                                const res = await refreshInsight();
                                if (res.status !== "generating") refreshingInsight = false;
                            } catch {
                                refreshingInsight = false;
                            }
                        }}
                    >
                        {refreshingInsight ? "Generating…" : "↻ Refresh insight"}
                    </button>
                </div>

                <!-- ═══ 1. Activity Heatmap ═══ -->
                {#if count >= 2}
                    <ActivityHeatmap {entries} />
                {/if}

                <!-- ═══ 2. Productivity Impact (lifetime) ═══ -->
                <div class="flex flex-col gap-[var(--space-3)]">
                    <span
                        class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                        >Productivity Impact</span
                    >
                    <div class="grid grid-cols-2 gap-[var(--space-4)]">
                        <StatCard
                            icon={Timer}
                            value={formatDuration(timeSavedSeconds)}
                            label="Time Saved"
                            sublabel="vs manual typing"
                            variant="featured"
                        />
                        <StatCard
                            icon={MessageSquareText}
                            value={formatCount(totalWords)}
                            label="Words Captured"
                            sublabel="Total transcribed words"
                            variant="featured"
                        />
                    </div>
                </div>

                <!-- ═══ 2b. Refinement Impact (only shown if refinements exist) ═══ -->
                {#if hasRefinements}
                    <div class="flex flex-col gap-[var(--space-3)]">
                        <span
                            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                            >Refinement Impact</span
                        >
                        <div class="grid grid-cols-3 gap-[var(--space-3)]">
                            <StatCard
                                icon={FileCheck2}
                                value={formatCount(refinedCount)}
                                label="Transcripts Refined"
                                sublabel="{Math.round((refinedCount / count) * 100)}% of total"
                            />
                            <StatCard
                                icon={Eraser}
                                value={formatCount(fillersRemoved)}
                                label="Fillers Removed"
                                sublabel="by refinement"
                            />
                            <StatCard
                                icon={GraduationCap}
                                value="{verbatimFkForRefined} → {refinedAvgFkGrade}"
                                label="Reading Level"
                                sublabel="Verbatim → Refined ({fkGradeDelta > 0 ? '+' : ''}{fkGradeDelta})"
                            />
                        </div>
                    </div>
                {/if}

                <!-- ═══ 3. Usage & Activity (lifetime) ═══ -->
                <div class="flex flex-col gap-[var(--space-3)]">
                    <span
                        class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                        >Usage & Activity</span
                    >
                    <div class="grid grid-cols-4 gap-[var(--space-3)]">
                        <StatCard
                            icon={BarChart3}
                            value={formatCount(count)}
                            label="Transcriptions"
                            sublabel="Total recordings"
                        />
                        <StatCard
                            icon={Clock}
                            value={formatDuration(recordedSeconds)}
                            label="Time Recorded"
                            sublabel="Total audio duration"
                        />
                        <StatCard
                            icon={Gauge}
                            value={formatDuration(avgSeconds)}
                            label="Avg. Length"
                            sublabel="Per recording"
                        />
                        <StatCard
                            icon={PauseCircle}
                            value={totalSilence > 0 ? formatDuration(totalSilence) : "—"}
                            label="Total Silence"
                            sublabel="Accumulated pauses"
                        />
                    </div>
                </div>

                <!-- ═══ 4. Speech Quality (lifetime) ═══ -->
                <div class="flex flex-col gap-[var(--space-3)]">
                    <span
                        class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                        >Speech Quality</span
                    >
                    <div class="grid grid-cols-3 gap-[var(--space-3)]">
                        <StatCard
                            icon={BookOpen}
                            value={lexicalComplexity > 0 ? formatPercent(lexicalComplexity) : "—"}
                            label="Vocabulary"
                            sublabel="Unique words ratio"
                        />
                        <StatCard
                            icon={Volume2}
                            value={avgSilence > 0 ? formatDuration(avgSilence) : "—"}
                            label="Avg. Pauses"
                            sublabel="Silence between speech"
                        />
                        <StatCard
                            icon={MessageCircle}
                            value={fillerCount > 0 ? formatCount(fillerCount) : "—"}
                            label="Filler Words"
                            sublabel="um, uh, like, you know"
                        />
                    </div>
                </div>

                <!-- ═══ 4b. Readability (lifetime) ═══ -->
                <div class="flex flex-col gap-[var(--space-3)]">
                    <span
                        class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
                        >Readability</span
                    >
                    <div class="grid grid-cols-2 gap-[var(--space-3)]">
                        <StatCard
                            icon={GraduationCap}
                            value="Grade {hasRefinements ? verbatimFkForRefined : verbatimAvgFkGrade}"
                            label="FK Grade (Sentence Complexity)"
                            sublabel={hasRefinements ? `Verbatim · lower = more readable` : "Lower = more readable"}
                        />
                        <StatCard
                            icon={BookOpen}
                            value="{hasRefinements ? verbatimPolyForRefined : verbatimPolyRatio}%"
                            label="Complex Words (Vocabulary)"
                            sublabel={hasRefinements ? `Verbatim · 3+ syllable words` : "3+ syllable words"}
                        />
                        {#if hasRefinements}
                            <StatCard
                                icon={Sparkles}
                                value="Grade {refinedAvgFkGrade}"
                                label="FK Grade (Sentence Complexity)"
                                sublabel="Refined · {fkGradeDelta > 0 ? '+' : ''}{fkGradeDelta} from verbatim"
                            />
                            <StatCard
                                icon={Sparkles}
                                value="{refinedPolyRatio}%"
                                label="Complex Words (Vocabulary)"
                                sublabel="Refined · {Math.round((refinedPolyRatio - verbatimPolyForRefined) * 10) / 10 >
                                0
                                    ? '+'
                                    : ''}{Math.round((refinedPolyRatio - verbatimPolyForRefined) * 10) /
                                    10}% from verbatim"
                            />
                        {/if}
                    </div>
                </div>

                <!-- ═══ 5. Distribution Charts ═══ -->
                <DistributionChart
                    title="Word Count Distribution"
                    series={[
                        { label: "Words per transcript", values: perTranscriptWordCounts, color: "var(--accent)" },
                    ]}
                    xLabel="Words"
                />

                {#if hasRefinements}
                    <DistributionChart
                        title="Reading Level Distribution"
                        series={[
                            { label: "Verbatim", values: perTranscriptFkVerbatim, color: "var(--text-tertiary)" },
                            { label: "Refined", values: perTranscriptFkRefined, color: "var(--accent)" },
                        ]}
                        xLabel="Flesch-Kincaid Grade"
                    />
                {:else if perTranscriptFkVerbatim.length >= 2}
                    <DistributionChart
                        title="Reading Level Distribution"
                        series={[{ label: "Verbatim", values: perTranscriptFkVerbatim, color: "var(--accent)" }]}
                        xLabel="Flesch-Kincaid Grade"
                    />
                {/if}

                <div class="h-px bg-[var(--shell-border)]"></div>

                <!-- ═══ 6. Calculation Details (collapsible) ═══ -->
                <section class="flex flex-col items-center gap-[var(--space-4)]">
                    <button
                        class="flex items-center gap-[var(--space-2)] bg-none border-none text-[var(--text-secondary)] text-[var(--text-sm)] cursor-pointer py-[var(--space-2)] px-[var(--space-4)] rounded-[var(--radius-md)] transition-[color,background] duration-[var(--transition-fast)] hover:text-[var(--accent)] hover:bg-[var(--hover-overlay)]"
                        onclick={() => (showExplanations = !showExplanations)}
                    >
                        {#if showExplanations}
                            <ChevronDown size={14} />
                            Hide Calculation Details
                        {:else}
                            <ChevronRight size={14} />
                            Show Calculation Details
                        {/if}
                    </button>

                    {#if showExplanations}
                        <div class="flex flex-col gap-[var(--space-2)] w-full">
                            {#each explanations as exp}
                                <div
                                    class="w-full rounded-[var(--radius-md)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] px-[var(--space-4)] py-[var(--space-3)] flex items-start gap-[var(--space-4)]"
                                >
                                    <strong
                                        class="min-w-[160px] text-[var(--text-sm)] text-accent font-semibold leading-[var(--leading-normal)]"
                                        >{exp.title}</strong
                                    >
                                    <span
                                        class="text-[var(--text-sm)] text-[var(--text-secondary)] leading-[var(--leading-relaxed)] text-left"
                                        >{exp.text}</span
                                    >
                                </div>
                            {/each}
                        </div>
                    {/if}
                </section>
            {/if}

            <div class="h-px bg-[var(--shell-border)]"></div>

            <!-- ═══ 6. About ═══ -->
            <footer
                class="rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] p-[var(--space-5)] flex flex-col items-center gap-[var(--space-3)]"
            >
                <h2 class="text-2xl font-[var(--weight-emphasis)] text-[var(--accent)] m-0">Vociferous</h2>
                <p class="text-[var(--text-sm)] text-[var(--text-secondary)] m-0">Local AI Speech to Text</p>

                <p
                    class="text-[var(--text-sm)] text-[var(--text-tertiary)] text-center leading-[var(--leading-relaxed)] max-w-[520px] m-0"
                >
                    Powered by CTranslate2 language models. Fully local, privacy-first speech-to-text that runs entirely
                    on your machine. No cloud, no data collection, no internet.
                </p>

                {#if healthInfo}
                    <p class="text-[var(--text-xs)] text-[var(--text-tertiary)] font-mono m-0">v{healthInfo.version}</p>
                {/if}

                <div class="flex gap-[var(--space-3)]">
                    <a
                        class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-md)] text-[var(--text-secondary)] text-[var(--text-sm)] no-underline transition-[color,border-color] duration-[var(--transition-fast)] hover:text-[var(--accent)] hover:border-[var(--accent)]"
                        href="https://www.linkedin.com/in/abrown7521/"
                        target="_blank"
                        rel="noopener"
                    >
                        <Linkedin size={15} /> LinkedIn
                    </a>
                    <a
                        class="flex items-center gap-[var(--space-1)] py-[var(--space-1)] px-[var(--space-3)] border border-[var(--shell-border)] rounded-[var(--radius-md)] text-[var(--text-secondary)] text-[var(--text-sm)] no-underline transition-[color,border-color] duration-[var(--transition-fast)] hover:text-[var(--accent)] hover:border-[var(--accent)]"
                        href="https://github.com/WanderingAstronomer/Vociferous"
                        target="_blank"
                        rel="noopener"
                    >
                        <Github size={15} /> GitHub
                    </a>
                </div>

                <p class="text-[var(--text-xs)] text-[var(--accent)] m-0">Created by Andrew Brown</p>
            </footer>
        </div>
    </div>
</div>

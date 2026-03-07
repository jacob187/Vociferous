<script lang="ts">
    /**
     * ActivityHeatmap — Month-sectioned activity grid.
     *
     * 7 rows (Mon–Sun) × variable columns per month. Each month section
     * shows calendar-aligned day cells. Cells outside month boundaries
     * are blacked out. Vertical gaps separate months.
     *
     * Data range: first transcript month → today, padded with future months
     * to fill the container. No partial months rendered. Cell size is
     * maximized for readability within the available width.
     */

    interface Props {
        entries: Array<{
            text: string;
            normalized_text?: string;
            timestamp?: string;
            created_at?: string;
        }>;
        title?: string;
    }

    let { entries, title = "Recent Activity" }: Props = $props();

    /* ── Layout constants ── */
    const TARGET_CELL = 16;
    const CELL_MIN = 12;
    const CELL_MAX = 22;
    const CELL_GAP = 3;
    const MONTH_GAP = 10;
    const DIVIDER_W = 1;
    const LABEL_W = 36;
    const MONTH_LABEL_H = 22;
    const FONT = "11px";
    const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

    /* ── Colors ── */
    const EMPTY_COLOR = "var(--surface-tertiary)";
    const BLACKOUT_COLOR = "var(--gray-9)";
    const LEVEL_COLORS = [
        EMPTY_COLOR,
        "var(--blue-8)",
        "var(--blue-6)",
        "var(--blue-4)",
        "var(--blue-3)",
    ];

    /* ── Resize tracking ── */
    let containerEl: HTMLDivElement | undefined = $state();
    let containerWidth = $state(0);

    $effect(() => {
        if (!containerEl) return;
        const ro = new ResizeObserver((es) => {
            containerWidth = es[0].contentRect.width;
        });
        ro.observe(containerEl);
        return () => ro.disconnect();
    });

    /* ── Aggregate words per day ── */
    let dailyWords = $derived.by(() => {
        const map = new Map<string, number>();
        for (const e of entries) {
            const raw = e.created_at ?? e.timestamp;
            if (!raw) continue;
            const key = new Date(raw).toLocaleDateString("sv");
            const w = (e.text || (e as any).normalized_text || "")
                .split(/\s+/)
                .filter(Boolean).length;
            map.set(key, (map.get(key) ?? 0) + w);
        }
        return map;
    });

    /* ── Find first transcript date ── */
    let firstDate = $derived.by(() => {
        let min: Date | null = null;
        for (const e of entries) {
            const raw = e.created_at ?? e.timestamp;
            if (!raw) continue;
            const d = new Date(raw);
            if (!min || d < min) min = d;
        }
        return min;
    });

    /* ── Summary stats ── */
    let totalWords = $derived(Array.from(dailyWords.values()).reduce((s, w) => s + w, 0));
    let activeDays = $derived(Array.from(dailyWords.values()).filter((w) => w > 0).length);

    /* ── Month block model ── */
    interface DayCell {
        dateStr: string;
        inMonth: boolean;
        future: boolean;
        words: number;
        level: number;
    }
    interface MonthBlock {
        year: number;
        month: number;
        label: string;
        columns: DayCell[][];
        numCols: number;
    }

    function daysInMonth(y: number, m: number): number {
        return new Date(y, m + 1, 0).getDate();
    }

    function buildMonthBlock(
        year: number,
        month: number,
        today: Date,
        dw: Map<string, number>,
        q: number[],
    ): MonthBlock {
        const first = new Date(year, month, 1);
        const dim = daysInMonth(year, month);
        const firstDow = (first.getDay() + 6) % 7; // Mon=0
        const numCols = Math.ceil((firstDow + dim) / 7);
        const label = first.toLocaleDateString(undefined, { month: "short" });
        const columns: DayCell[][] = [];

        for (let c = 0; c < numCols; c++) {
            const col: DayCell[] = [];
            for (let r = 0; r < 7; r++) {
                const dayIdx = c * 7 + r - firstDow;
                const dom = dayIdx + 1;
                const inMonth = dom >= 1 && dom <= dim;
                if (!inMonth) {
                    col.push({ dateStr: "", inMonth: false, future: false, words: 0, level: 0 });
                } else {
                    const d = new Date(year, month, dom);
                    const ds = d.toLocaleDateString("sv");
                    const isFuture = d > today;
                    const words = isFuture ? 0 : (dw.get(ds) ?? 0);
                    let level = 0;
                    if (!isFuture && words > 0) {
                        if (words <= q[0]) level = 1;
                        else if (words <= q[1]) level = 2;
                        else if (words <= q[2]) level = 3;
                        else level = 4;
                    }
                    col.push({ dateStr: ds, inMonth: true, future: isFuture, words, level });
                }
            }
            columns.push(col);
        }
        return { year, month, label, columns, numCols };
    }

    function computeThresholds(dw: Map<string, number>): number[] {
        const vals = Array.from(dw.values())
            .filter((v) => v > 0)
            .sort((a, b) => a - b);
        if (vals.length === 0) return [1, 2, 3];
        const at = (p: number) => vals[Math.floor(p * (vals.length - 1))];
        return [at(0.25), at(0.5), at(0.75)];
    }

    /* ── Iterating months ── */
    function nextMonth(y: number, m: number): [number, number] {
        return m === 11 ? [y + 1, 0] : [y, m + 1];
    }

    /* Width of a month section at a given cell size */
    function sectionWidth(numCols: number, cs: number): number {
        return numCols * (cs + CELL_GAP) - CELL_GAP;
    }

    /* ── Grid layout computation ── */
    interface GridLayout {
        blocks: MonthBlock[];
        cellSize: number;
    }

    let layout = $derived.by((): GridLayout | null => {
        if (containerWidth < 150 || !firstDate) return null;

        const today = new Date();
        today.setHours(23, 59, 59, 999);
        const q = computeThresholds(dailyWords);

        const startY = firstDate.getFullYear();
        const startM = firstDate.getMonth();
        const curY = today.getFullYear();
        const curM = today.getMonth();

        // Build mandatory months: first transcript → current
        const mandatoryKeys: [number, number][] = [];
        {
            let y = startY,
                m = startM;
            while (y < curY || (y === curY && m <= curM)) {
                mandatoryKeys.push([y, m]);
                [y, m] = nextMonth(y, m);
            }
        }

        // Mandatory column count (to check if they fit)
        const mandatoryCols = mandatoryKeys.map(([y, m]) => {
            const dow = (new Date(y, m, 1).getDay() + 6) % 7;
            return Math.ceil((dow + daysInMonth(y, m)) / 7);
        });

        const availableW = containerWidth - LABEL_W;

        // Compute total width for a set of column counts at a given cell size
        function totalW(colCounts: number[], cs: number): number {
            let w = 0;
            for (let i = 0; i < colCounts.length; i++) {
                w += sectionWidth(colCounts[i], cs);
                if (i < colCounts.length - 1) w += MONTH_GAP + DIVIDER_W;
            }
            return w;
        }

        // Start with target cell size — can we fit mandatory months?
        let cellSize = TARGET_CELL;
        if (totalW(mandatoryCols, cellSize) > availableW) {
            for (let cs = cellSize - 1; cs >= CELL_MIN; cs--) {
                if (totalW(mandatoryCols, cs) <= availableW) {
                    cellSize = cs;
                    break;
                }
                cellSize = cs;
            }
        }

        // Add future months to fill remaining space
        const allColCounts = [...mandatoryCols];
        const allKeys: [number, number][] = [...mandatoryKeys];
        {
            let [y, m] = nextMonth(curY, curM);
            const maxExtra = 24;
            for (let i = 0; i < maxExtra; i++) {
                const dow = (new Date(y, m, 1).getDay() + 6) % 7;
                const nc = Math.ceil((dow + daysInMonth(y, m)) / 7);
                if (totalW([...allColCounts, nc], cellSize) > availableW) break;
                allColCounts.push(nc);
                allKeys.push([y, m]);
                [y, m] = nextMonth(y, m);
            }
        }

        // Try to grow cell size with the blocks we have
        while (cellSize < CELL_MAX) {
            if (totalW(allColCounts, cellSize + 1) > availableW) break;
            cellSize++;
        }

        // Build actual month blocks
        const blocks = allKeys.map(([y, m]) => buildMonthBlock(y, m, today, dailyWords, q));

        return { blocks, cellSize };
    });

    function cellBg(cell: DayCell): string {
        if (!cell.inMonth) return BLACKOUT_COLOR;
        if (cell.future) return EMPTY_COLOR;
        return LEVEL_COLORS[cell.level];
    }

    function cellTooltip(cell: DayCell): string {
        if (!cell.inMonth || cell.future) return "";
        const d = new Date(cell.dateStr + "T12:00:00");
        const label = d.toLocaleDateString(undefined, {
            weekday: "short",
            month: "short",
            day: "numeric",
        });
        return cell.words > 0
            ? `${label}: ${cell.words.toLocaleString()} words`
            : `${label}: no activity`;
    }
</script>

<div
    bind:this={containerEl}
    class="w-full select-none"
    role="img"
    aria-label="Activity heatmap showing words transcribed per day"
>
    {#if layout}
        {@const cs = layout.cellSize}
        {@const stride = cs + CELL_GAP}

        <!-- Title -->
        {#if title}
            <div
                class="text-[{FONT}] font-medium text-[var(--text-tertiary)] uppercase tracking-widest mb-[var(--space-2)] pl-[{LABEL_W}px]"
            >
                {title}
            </div>
        {/if}

        <!-- Month labels row -->
        <div
            class="flex items-end"
            style="padding-left: {LABEL_W}px; height: {MONTH_LABEL_H}px;"
        >
            {#each layout.blocks as block, bi}
                {#if bi > 0}
                    <div style="width: {MONTH_GAP + DIVIDER_W}px; height: 1px;"></div>
                {/if}
                <div
                    class="text-[{FONT}] text-[var(--text-secondary)] leading-none text-center shrink-0"
                    style="width: {sectionWidth(block.numCols, cs)}px;"
                >
                    {block.label}
                </div>
            {/each}
        </div>

        <!-- Grid body -->
        <div class="flex">
            <!-- Day-of-week labels -->
            <div class="flex flex-col shrink-0" style="width: {LABEL_W}px; gap: {CELL_GAP}px;">
                {#each DAY_NAMES as name}
                    <div class="flex items-center justify-end pr-[6px]" style="height: {cs}px;">
                        <span class="text-[{FONT}] text-[var(--text-secondary)] leading-none">{name}</span>
                    </div>
                {/each}
            </div>

            <!-- Month sections with dividers -->
            <div class="flex items-stretch">
                {#each layout.blocks as block, bi}
                    {#if bi > 0}
                        <div
                            class="shrink-0 flex items-center justify-center"
                            style="width: {MONTH_GAP + DIVIDER_W}px;"
                        >
                            <div
                                class="h-full w-px bg-[var(--shell-border)] opacity-30"
                            ></div>
                        </div>
                    {/if}
                    <div class="flex shrink-0" style="gap: {CELL_GAP}px;">
                        {#each block.columns as col}
                            <div class="flex flex-col" style="gap: {CELL_GAP}px;">
                                {#each col as cell}
                                    <div
                                        class="rounded-[2px]"
                                        style="width: {cs}px; height: {cs}px; background: {cellBg(cell)};"
                                        title={cellTooltip(cell)}
                                    ></div>
                                {/each}
                            </div>
                        {/each}
                    </div>
                {/each}
            </div>
        </div>

        <!-- Legend -->
        <div
            class="flex items-center justify-between mt-[var(--space-2)]"
            style="padding-left: {LABEL_W}px;"
        >
            <span class="text-[{FONT}] text-[var(--text-muted)] whitespace-nowrap">
                {activeDays} active day{activeDays !== 1 ? "s" : ""}
                · {totalWords.toLocaleString()} words
            </span>
            <div class="flex items-center gap-1 shrink-0">
                <span class="text-[{FONT}] text-[var(--text-muted)]">Less</span>
                {#each LEVEL_COLORS as color}
                    <div
                        class="rounded-[2px]"
                        style="width: 10px; height: 10px; background: {color};"
                    ></div>
                {/each}
                <span class="text-[{FONT}] text-[var(--text-muted)]">More</span>
            </div>
        </div>
    {/if}
</div>

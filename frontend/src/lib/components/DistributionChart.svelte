<script lang="ts">
    /**
     * DistributionChart — Overlapping bell curve visualization.
     *
     * Renders one or two Gaussian-fitted distribution curves (via SVG) with a
     * legend. Designed for verbatim vs refined comparisons (FK grade, word count).
     */

    import { buildDistributionCurve, stdDev } from "../textAnalysis";

    interface DataSeries {
        label: string;
        values: number[];
        color: string;
    }

    interface Props {
        title: string;
        series: DataSeries[];
        xLabel?: string;
    }

    let { title, series, xLabel = "" }: Props = $props();

    const PADDING = { top: 20, right: 20, bottom: 36, left: 20 };
    const BUCKET_COUNT = 30;
    const W = 960;
    const H = 300;

    /* ── Derived curves ── */
    let curves = $derived(
        series
            .filter((s) => s.values.length >= 2)
            .map((s) => {
                const points = buildDistributionCurve(s.values, BUCKET_COUNT);
                const mean = s.values.reduce((a, b) => a + b, 0) / s.values.length;
                const sd = stdDev(s.values);
                return { ...s, points, mean, sd };
            }),
    );

    /* ── Scale computation ── */
    let xMin = $derived(Math.min(...curves.flatMap((c) => c.points.map((p) => p.x))));
    let xMax = $derived(Math.max(...curves.flatMap((c) => c.points.map((p) => p.x))));
    let yMax = $derived(Math.max(...curves.flatMap((c) => c.points.map((p) => p.y))));

    /* SVG coordinate space — aspect ratio maintained by browser */
    function scaleX(v: number): number {
        const range = xMax - xMin || 1;
        return PADDING.left + ((v - xMin) / range) * (W - PADDING.left - PADDING.right);
    }
    function scaleY(v: number): number {
        const plotH = H - PADDING.top - PADDING.bottom;
        return H - PADDING.bottom - (v / (yMax || 1)) * plotH;
    }

    /* ── SVG path builder ── */
    function curvePath(points: { x: number; y: number }[]): string {
        if (points.length < 2) return "";
        return points
            .map((p, i) => `${i === 0 ? "M" : "L"} ${scaleX(p.x).toFixed(1)} ${scaleY(p.y).toFixed(1)}`)
            .join(" ");
    }
    function filledPath(points: { x: number; y: number }[]): string {
        if (points.length < 2) return "";
        const base = curvePath(points);
        const last = points[points.length - 1];
        const first = points[0];
        return `${base} L ${scaleX(last.x).toFixed(1)} ${scaleY(0).toFixed(1)} L ${scaleX(first.x).toFixed(1)} ${scaleY(0).toFixed(1)} Z`;
    }

    /* For text elements: compute font-size that stays readable at any container width. */
    const TICK_FONT = 11;
    const LABEL_FONT = 11;

    /* ── X-axis tick marks ── */
    let xTicks = $derived.by(() => {
        const range = xMax - xMin;
        if (range === 0) return [xMin];
        // Pick a nice step that gives 4-8 ticks
        const rawStep = range / 5;
        const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
        const nice = [1, 2, 2.5, 5, 10];
        const step = nice.map((n) => n * magnitude).find((s) => range / s <= 8) || magnitude * 10;
        const ticks: number[] = [];
        let v = Math.ceil(xMin / step) * step;
        while (v <= xMax) {
            ticks.push(Math.round(v * 10) / 10);
            v += step;
        }
        return ticks.length >= 2 ? ticks : [Math.round(xMin * 10) / 10, Math.round(xMax * 10) / 10];
    });
</script>

{#if curves.length > 0}
    <div class="flex flex-col gap-[var(--space-2)]">
        <span
            class="font-[var(--weight-emphasis)] text-[var(--text-xs)] text-[var(--text-tertiary)] uppercase tracking-[1px] text-center"
        >
            {title}
        </span>

        <div
            class="rounded-[var(--radius-lg)] border border-[var(--shell-border)] bg-[var(--surface-secondary)] p-[var(--space-3)] overflow-hidden"
        >
            <!-- Legend -->
            <div class="flex items-center justify-center gap-[var(--space-4)] mb-[var(--space-2)]">
                {#each curves as curve}
                    <div class="flex items-center gap-[var(--space-1)] text-[var(--text-xs)]">
                        <span class="w-3 h-[3px] rounded-full" style="background: {curve.color}"></span>
                        <span class="text-[var(--text-secondary)]">{curve.label}</span>
                        <span class="text-[var(--text-tertiary)] font-mono">
                            μ={curve.mean.toFixed(1)} σ={curve.sd.toFixed(1)}
                        </span>
                    </div>
                {/each}
            </div>

            <!-- SVG Chart -->
            <svg viewBox="0 0 {W} {H}" class="w-full h-auto">
                <!-- Filled areas -->
                {#each curves as curve, i}
                    <path d={filledPath(curve.points)} fill={curve.color} opacity="0.12" />
                {/each}

                <!-- Lines -->
                {#each curves as curve, i}
                    <path
                        d={curvePath(curve.points)}
                        fill="none"
                        stroke={curve.color}
                        stroke-width="2"
                        stroke-linejoin="round"
                    />
                {/each}

                <!-- Mean markers -->
                {#each curves as curve}
                    <line
                        x1={scaleX(curve.mean)}
                        y1={PADDING.top}
                        x2={scaleX(curve.mean)}
                        y2={H - PADDING.bottom}
                        stroke={curve.color}
                        stroke-width="1"
                        stroke-dasharray="4 3"
                        opacity="0.5"
                    />
                {/each}

                <!-- X-axis -->
                <line
                    x1={PADDING.left}
                    y1={H - PADDING.bottom}
                    x2={W - PADDING.right}
                    y2={H - PADDING.bottom}
                    stroke="var(--shell-border)"
                    stroke-width="1"
                />
                {#each xTicks as tick}
                    <text
                        x={scaleX(tick)}
                        y={H - PADDING.bottom + 16}
                        text-anchor="middle"
                        fill="var(--text-tertiary)"
                        font-size={TICK_FONT}
                        font-family="var(--font-mono)"
                    >
                        {tick}
                    </text>
                {/each}

                <!-- X-axis label -->
                {#if xLabel}
                    <text x={W / 2} y={H - 4} text-anchor="middle" fill="var(--text-tertiary)" font-size={LABEL_FONT}>
                        {xLabel}
                    </text>
                {/if}
            </svg>
        </div>
    </div>
{/if}

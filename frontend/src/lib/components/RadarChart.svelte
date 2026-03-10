<!--
    RadarChart — Custom SVG radar/spider chart visualizing 6 speech analytics axes.

    Props: array of axes with label, display value, and normalized 0-1 metric.
    Pure SVG, no dependencies. Responsive within flex container.
-->
<script lang="ts">
    export interface RadarAxis {
        label: string;      // "Speed", "Activity", etc.
        value: string;      // Formatted display value (e.g., "142 WPM")
        normalized: number; // 0.0–1.0
    }

    interface Props {
        axes: RadarAxis[];
    }

    let { axes }: Props = $props();

    // SVG constants
    const SIZE = 300;
    const CENTER = SIZE / 2;
    const RADIUS = 110;
    const SCALE_RINGS = [0.25, 0.5, 0.75, 1.0];

    // Calculate angle for each axis (in degrees, starting at -90 to point up)
    function getAngle(index: number, total: number): number {
        return -90 + (index / total) * 360;
    }

    // Convert angle (degrees) and distance to SVG coordinates
    function polarToSvg(angle: number, distance: number): [number, number] {
        const rad = (angle * Math.PI) / 180;
        const x = CENTER + distance * Math.cos(rad);
        const y = CENTER + distance * Math.sin(rad);
        return [x, y];
    }

    // Generate SVG path data for the data polygon
    function getDataPath(axes: RadarAxis[]): string {
        if (axes.length === 0) return "";

        const points = axes.map((axis, i) => {
            const angle = getAngle(i, axes.length);
            const distance = Math.min(1, Math.max(0, axis.normalized)) * RADIUS;
            const [x, y] = polarToSvg(angle, distance);
            return `${x},${y}`;
        });

        return `M ${points.join(" L ")} Z`;
    }

    // Get text anchor for axis label based on x-position
    function getTextAnchor(angle: number): string {
        const normalized = angle % 360;
        if (normalized > 90 && normalized < 270) return "end";
        if (normalized < 90 || normalized > 270) return "start";
        return "middle";
    }

    // Offset for label positioning (slightly beyond the outer ring)
    const LABEL_OFFSET = 15;
</script>

<div class="flex justify-center w-full">
    <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        class="w-full max-w-96 aspect-square"
        role="img"
        aria-label="Speech analytics profile radar chart"
    >
        <!-- Background -->
        <rect width={SIZE} height={SIZE} fill="var(--surface-primary)" rx={8} />

        <!-- Scale rings -->
        {#each SCALE_RINGS as ring}
            <circle
                cx={CENTER}
                cy={CENTER}
                r={ring * RADIUS}
                fill="none"
                stroke="var(--shell-border)"
                stroke-width="1"
                opacity="0.4"
            />
        {/each}

        <!-- Scale ring labels (percentages) -->
        {#each SCALE_RINGS.slice(1) as ring}
            <text
                x={CENTER}
                y={CENTER - ring * RADIUS + 4}
                font-size="9"
                fill="var(--text-tertiary)"
                text-anchor="middle"
                opacity="0.5"
            >
                {Math.round(ring * 100)}%
            </text>
        {/each}

        <!-- Axis lines and labels -->
        {#each axes as axis, i (i)}
            {@const angle = getAngle(i, axes.length)}
            {@const [axisX, axisY] = polarToSvg(angle, RADIUS)}
            {@const [labelX, labelY] = polarToSvg(angle, RADIUS + LABEL_OFFSET)}

            <!-- Axis line -->
            <line
                x1={CENTER}
                y1={CENTER}
                x2={axisX}
                y2={axisY}
                stroke="var(--shell-border)"
                stroke-width="1"
                opacity="0.4"
            />

            <!-- Axis label -->
            <text
                x={labelX}
                y={labelY}
                font-size="11"
                font-weight="500"
                fill="var(--text-secondary)"
                text-anchor={getTextAnchor(angle)}
                dominant-baseline="middle"
            >
                {axis.label}
            </text>

            <!-- Axis value label (smaller, below label) -->
            <text
                x={labelX}
                y={labelY + 12}
                font-size="9"
                fill="var(--accent)"
                text-anchor={getTextAnchor(angle)}
                dominant-baseline="middle"
                font-weight="600"
            >
                {axis.value}
            </text>
        {/each}

        <!-- Data polygon -->
        <path
            d={getDataPath(axes)}
            fill="var(--accent)"
            fill-opacity="0.2"
            stroke="var(--accent)"
            stroke-width="2"
            stroke-linejoin="round"
        />

        <!-- Data points (small circles at each axis) -->
        {#each axes as axis, i (i)}
            {@const angle = getAngle(i, axes.length)}
            {@const distance = Math.min(1, Math.max(0, axis.normalized)) * RADIUS}
            {@const [x, y] = polarToSvg(angle, distance)}

            <circle cx={x} cy={y} r="3" fill="var(--accent)" />
        {/each}
    </svg>
</div>

<style>
    div {
        padding: 1rem 0;
    }
</style>

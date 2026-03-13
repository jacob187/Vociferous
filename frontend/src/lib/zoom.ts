/**
 * Returns the current CSS zoom factor applied to #app.
 *
 * Zoom lives on #app (not <html>) so percentage heights propagate
 * correctly through the viewport chain. Divide raw clientX /
 * getBoundingClientRect values by this before using as fixed offsets.
 */
export function getZoomFactor(): number {
    const el = document.getElementById("app");
    if (!el) return 1;
    return parseFloat(getComputedStyle(el).zoom) || 1;
}

/**
 * Shared reactive window dimensions.
 *
 * One listener, one place. Components that need to react to window
 * snap/tile/resize events read `windowSize.width` or `.height` inside
 * a reactive context ($effect, $derived) instead of each adding their
 * own window.addEventListener("resize").
 */

let _width = $state(window.innerWidth);
let _height = $state(window.innerHeight);

window.addEventListener(
    "resize",
    () => {
        _width = window.innerWidth;
        _height = window.innerHeight;
    },
    { passive: true },
);

export const windowSize = {
    get width() { return _width; },
    get height() { return _height; },
};

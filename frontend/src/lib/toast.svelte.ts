/**
 * Global toast notification system.
 *
 * Uses Svelte 5 runes ($state) for a dead-simple reactive store.
 * Any component can `import { toast } from '../lib/toast.svelte'` and fire
 * `toast.push("Something happened", "success")`.
 *
 * Also provides `toast.confirm()` for blocking confirmation dialogs
 * that return a Promise<boolean>. One confirm shown at a time; FIFO queue.
 *
 * ToastContainer.svelte reads `toast.items` and `toast.activeConfirm`.
 */

export type ToastVariant = "success" | "error" | "warning" | "info";

export interface ToastItem {
    id: number;
    message: string;
    variant: ToastVariant;
    expiresAt: number;
}

export interface ConfirmOptions {
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    danger?: boolean;
}

export interface ConfirmItem extends ConfirmOptions {
    id: number;
    resolve: (value: boolean) => void;
}

let _nextId = 0;
const DEFAULT_DURATION_MS = 4000;

/** Reactive array of active toasts. Read by ToastContainer. */
let items = $state<ToastItem[]>([]);

/** FIFO queue of pending confirmations. First element is active. */
let confirmQueue = $state<ConfirmItem[]>([]);

function push(message: string, variant: ToastVariant = "info", durationMs = DEFAULT_DURATION_MS): void {
    const id = ++_nextId;
    const expiresAt = Date.now() + durationMs;
    items = [...items, { id, message, variant, expiresAt }];

    setTimeout(() => {
        dismiss(id);
    }, durationMs);
}

function dismiss(id: number): void {
    items = items.filter((t) => t.id !== id);
}

function confirm(options: ConfirmOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
        const id = ++_nextId;
        confirmQueue = [...confirmQueue, { ...options, id, resolve }];
    });
}

function resolveConfirm(id: number, value: boolean): void {
    const item = confirmQueue.find((c) => c.id === id);
    if (!item) return;
    item.resolve(value);
    confirmQueue = confirmQueue.filter((c) => c.id !== id);
}

export const toast = {
    get items() {
        return items;
    },
    get activeConfirm(): ConfirmItem | null {
        return confirmQueue.length > 0 ? confirmQueue[0] : null;
    },
    push,
    dismiss,
    confirm,
    resolveConfirm,
    success: (msg: string, duration?: number) => push(msg, "success", duration),
    error: (msg: string, duration?: number) => push(msg, "error", duration),
    warning: (msg: string, duration?: number) => push(msg, "warning", duration),
    info: (msg: string, duration?: number) => push(msg, "info", duration),
};

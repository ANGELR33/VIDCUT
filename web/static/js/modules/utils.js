/**
 * AetherCut Studio - Utility Helpers & Formatters
 */
export const $ = (id) => document.getElementById(id);

export const fmtDuration = (seconds) => {
    const s = Math.max(0, Math.floor(seconds || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return h ? `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
        : `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
};

export const ageLabel = (seconds) => seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`;

export const eventTime = (value) => {
    const date = value ? new Date(value) : new Date();
    return Number.isNaN(date.valueOf()) ? "—" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
};

export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));

export const percent = (value, duration) => {
    return `${Math.max(0, Math.min(100, (Number(value || 0) / Math.max(1, Number(duration || 1))) * 100))}%`;
};

export const waitForEvent = (element, eventName) => {
    return new Promise((resolve, reject) => {
        element.addEventListener(eventName, resolve, { once: true });
        element.addEventListener("error", () => reject(new Error("No se pudo leer la vista previa.")), { once: true });
    });
};

/**
 * AetherCut / Prism Studio - Timeline Sequencer Module
 */
import { $, percent, fmtDuration, esc } from "./utils.js";

export function createTimelineManager(state) {
    let selectedEditorItem = null;
    let editorDirty = false;

    function markEditorDirty() {
        editorDirty = true;
        const saveBtn = $("saveTimelineBtn");
        const exportBtn = $("exportTimelineBtn");
        const saveState = $("editorSaveState");
        if (saveBtn) saveBtn.disabled = false;
        if (exportBtn) exportBtn.disabled = true;
        if (saveState) saveState.textContent = "Tienes cambios sin guardar en este proyecto.";
    }

    function getSelectedItem() {
        if (!state.editorState || !selectedEditorItem) return null;
        const list = selectedEditorItem.type === "card" ? state.editorState.cards : state.editorState.brolls;
        return list?.find((item) => item.id === selectedEditorItem.id) || null;
    }

    function renderInspector() {
        const inspector = $("editorInspector");
        if (!inspector) return;
        const item = getSelectedItem();
        if (!item) {
            inspector.innerHTML = "<b>Selecciona un elemento de la línea de tiempo</b><p>Podrás cambiar su momento, duración, posición o retirarlo antes de una nueva exportación.</p>";
            return;
        }
        const kind = selectedEditorItem.type === "card" ? "Tarjeta verificada" : "Apoyo B-Roll";
        const title = selectedEditorItem.type === "card" ? item.headline : item.concept;
        const end = selectedEditorItem.type === "card" ? Number(item.start) + Number(item.duration || 7) : item.end;
        const context = selectedEditorItem.type === "card" ? (item.body || item.note || item.claim) : item.status;
        inspector.innerHTML = `<b>${esc(kind)} · ${esc(title)}</b><p>${esc(context || "Aún se está preparando.")}</p>
            <div style="display:flex; gap:12px; margin-top:6px; align-items:center;">
                <label style="display:flex; align-items:center; gap:4px;">Activo <input id="editEnabled" type="checkbox" ${item.enabled === false ? "" : "checked"}></label>
                <label style="display:flex; align-items:center; gap:4px;">Inicio <input id="editStart" type="number" min="0" step="0.1" value="${Number(item.start || 0).toFixed(1)}" style="width:60px;"></label>
                <label style="display:flex; align-items:center; gap:4px;">Fin <input id="editEnd" type="number" min="0" step="0.1" value="${Number(end || 0).toFixed(1)}" style="width:60px;"></label>
            </div>`;

        $("editEnabled")?.addEventListener("change", (event) => {
            item.enabled = event.target.checked;
            markEditorDirty();
            renderTimeline();
        });

        $("editStart")?.addEventListener("change", (event) => {
            item.start = Math.max(0, Number(event.target.value || 0));
            markEditorDirty();
            renderTimeline();
        });

        $("editEnd")?.addEventListener("change", (event) => {
            const value = Math.max(Number(item.start || 0) + (selectedEditorItem.type === "card" ? 4.5 : 1), Number(event.target.value || 0));
            if (selectedEditorItem.type === "card") item.duration = Math.min(12, value - Number(item.start || 0));
            else item.end = value;
            markEditorDirty();
            renderTimeline();
        });
    }

    function timelineClip(item, type, duration) {
        const button = document.createElement("button");
        const end = type === "card" ? Number(item.start) + Number(item.duration || 7) : Number(item.end);
        button.type = "button";
        button.className = `clip clip-${type}${item.enabled === false ? " is-muted" : ""}${selectedEditorItem?.type === type && selectedEditorItem.id === item.id ? " is-selected" : ""}`;
        button.style.left = percent(item.start, duration);
        button.style.width = `max(2.2%, ${percent(Math.max(1, end - Number(item.start)), duration)})`;
        button.textContent = type === "card" ? item.headline : (type === "broll" ? item.concept : item.title);
        button.title = `${button.textContent} · ${fmtDuration(item.start)}`;
        button.addEventListener("click", () => {
            selectedEditorItem = (type === "card" || type === "broll") ? { type, id: item.id } : null;
            const preview = $("projectPreview");
            if (preview && Number.isFinite(Number(item.start))) {
                preview.currentTime = Math.max(0, Number(item.start));
            }
            renderTimeline();
            renderInspector();
        });
        return button;
    }

    function renderTimeline() {
        if (!state.editorState) return;
        const duration = Number(state.editorState.duration || 1);
        const ruler = $("timelineRuler");
        const tracks = $("timelineTracks");
        if (!ruler || !tracks) return;

        ruler.replaceChildren();
        tracks.replaceChildren();
        const marks = Math.max(4, Math.min(12, Math.ceil(duration / 60)));
        for (let i = 0; i <= marks; i += 1) {
            const label = document.createElement("span");
            label.style.left = `${(i / marks) * 100}%`;
            label.textContent = fmtDuration((duration / marks) * i);
            ruler.append(label);
        }

        const rows = [
            ["Tarjetas", "card", state.editorState.cards || []],
            ["B-Roll", "broll", state.editorState.brolls || []],
            ["Shorts", "short", state.editorState.shorts || []],
            ["Cortes", "cut", state.editorState.cuts || []],
        ];

        rows.forEach(([label, type, items]) => {
            const row = document.createElement("div"); row.className = "track";
            const name = document.createElement("span"); name.className = "track-name"; name.textContent = label;
            const lane = document.createElement("div"); lane.className = "track-lane";
            items.forEach((item, index) => {
                const mapped = type === "cut" ? { id: `cut-${index}`, start: item.start_sec, end: item.end_sec, title: "Pausa eliminada", enabled: true } : item;
                lane.append(timelineClip(mapped, type, duration));
            });
            row.append(name, lane);
            tracks.append(row);
        });
    }

    function renderStudio(editor, previewUrl) {
        if (!editor) return;
        state.editorState = JSON.parse(JSON.stringify(editor));
        const duration = Number(state.editorState.duration || 0);

        if ($("studioSection")) $("studioSection").hidden = false;
        if ($("studioSummary")) {
            $("studioSummary").textContent = `${(state.editorState.cards || []).length} tarjetas · ${(state.editorState.brolls || []).length} B-Rolls · ${(state.editorState.shorts || []).length} Shorts`;
        }
        if ($("previewDuration")) $("previewDuration").textContent = fmtDuration(duration);

        const preview = $("projectPreview");
        if (preview && previewUrl && preview.dataset.source !== previewUrl) {
            preview.dataset.source = previewUrl;
            preview.src = previewUrl;
            preview.load();
            if ($("previewEmpty")) $("previewEmpty").hidden = true;
        }

        renderTimeline();
        renderInspector();
    }

    return {
        renderTimeline,
        renderStudio,
        renderInspector,
        markEditorDirty,
    };
}

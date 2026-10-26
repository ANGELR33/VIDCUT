import { $, fmtDuration, ageLabel, eventTime, esc, percent, waitForEvent } from "./modules/utils.js";
import { setupHudPlayer } from "./modules/player.js";
import { AgentCopilot } from "./modules/agent_copilot.js?v=2";
import { initPublishStudio } from "./modules/publish_studio.js";
import { initTrendRadar } from "./modules/trend_radar.js";

document.addEventListener("DOMContentLoaded", () => {
    const form = $("uploadForm");
    const fileInput = $("videoFileInput");
    const dropzone = $("dropzone");
    const controls = $("uploadControls");
    const startBtn = $("startBtn");
    const startBtnText = $("startBtnText");
    const fileBadge = $("selectedFileBadge");
    const fileName = $("selectedFileName");
    const feed = $("activityFeed");
    const cancelBtn = $("cancelTaskBtn");
    const emptyFeed = $("emptyActivity");
    const results = $("resultsSection");
    const statusBadge = $("connectionStatus");
    const phaseIds = ["phase-input", "phase-analyze", "phase-cut", "phase-enrich", "phase-render"];
    const stageLabels = {
        init: "Preparando la tarea", queued: "En cola", inspect: "Revisando el archivo",
        transcribe: "Transcripción local", gemini: "Análisis con Gemini", silence: "Detección de pausas",
        visual: "Análisis visual local", enrich: "B-Roll y búsqueda de fuentes", cards: "Diseño de apoyos visuales", quality: "Control técnico",
        research: "Investigación web en vivo", script: "Redacción de guión KAI", voice: "Voz neural de KAI",
        avatar: "Animación y Lip-Sync KAI", broll: "Fondos y tarjetas Bento",
        render: "Render del video", subtitles: "Composición y subtítulos",
        finalizing: "Short vertical", done: "Edición terminada", error: "Edición detenida",
        cancelling: "Cancelando edición", cancelled: "Edición cancelada",
    };
    const stagePhase = {
        init: 0, queued: 0, inspect: 0, transcribe: 0, research: 0,
        gemini: 1, script: 1,
        silence: 2, visual: 2, voice: 2, avatar: 2,
        enrich: 3, cards: 3, quality: 3, broll: 3,
        render: 4, subtitles: 4, finalizing: 4, done: 4,
    };
    const fmtDuration = (seconds) => {
        const s = Math.max(0, Math.floor(seconds || 0));
        const h = Math.floor(s / 3600);
        const m = Math.floor((s % 3600) / 60);
        const sec = s % 60;
        return h ? `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`
            : `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
    };
    const ageLabel = (seconds) => seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
    const eventTime = (value) => {
        const date = value ? new Date(value) : new Date();
        return Number.isNaN(date.valueOf()) ? "—" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    };
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));

    let selectedFile = null;
    let activeStream = null;
    let currentState = null;
    let renderedEvents = "";
    let didShowResults = false;
    let connectionLost = false;
    let observedTaskId = "";
    let legacyStartedAt = null;
    let legacyStepStartedAt = null;
    let legacyUpdatedAt = null;
    let legacyStep = "";
    let legacyMessage = "";
    let legacyEvents = [];
    let editorState = null;
    let selectedEditorItem = null;
    let editorDirty = false;
    let thumbnailsKey = "";
    let activeMode = "streamer";

    // Estudio de Publicación: preview + miniatura IA + subida directa a YouTube
    const publishStudio = initPublishStudio();

    // Radar de Viralidad: ranking de videos virales por región + temas urgentes
    initTrendRadar();


    function percent(value, duration) {
        return `${Math.max(0, Math.min(100, (Number(value || 0) / Math.max(1, Number(duration || 1))) * 100))}%`;
    }

    function setPreviewTime(seconds) {
        const preview = $("projectPreview");
        if (!Number.isFinite(Number(seconds))) return;
        preview.currentTime = Math.max(0, Number(seconds));
    }

    function waitForEvent(element, eventName) {
        return new Promise((resolve, reject) => {
            element.addEventListener(eventName, resolve, { once: true });
            element.addEventListener("error", () => reject(new Error("No se pudo leer la vista previa.")), { once: true });
        });
    }

    async function buildTimelineThumbnails(source, duration) {
        const strip = $("timelineThumbnails");
        const status = $("thumbnailStatus");
        const key = `${source}|${duration}`;
        if (key === thumbnailsKey) return;
        thumbnailsKey = key;
        strip.replaceChildren();
        strip.hidden = true;
        if (!("VideoFrame" in window) || !source || duration <= 0) {
            status.textContent = "La vista previa está lista; este navegador no expone miniaturas WebCodecs.";
            return;
        }
        status.textContent = "Generando miniaturas locales con WebCodecs…";
        const sampler = document.createElement("video");
        sampler.preload = "auto";
        sampler.muted = true;
        sampler.src = source;
        try {
            await waitForEvent(sampler, "loadedmetadata");
            const count = Math.max(4, Math.min(10, Math.ceil(duration / 45)));
            for (let index = 0; index < count; index += 1) {
                sampler.currentTime = Math.min(Math.max(0, duration - 0.05), duration * (index + 0.5) / count);
                await waitForEvent(sampler, "seeked");
                const frame = new VideoFrame(sampler);
                const canvas = document.createElement("canvas");
                canvas.width = 160; canvas.height = 90;
                canvas.getContext("2d").drawImage(frame, 0, 0, canvas.width, canvas.height);
                frame.close();
                const button = document.createElement("button");
                button.type = "button";
                button.className = "timeline-thumbnail";
                const at = duration * (index + 0.5) / count;
                button.title = `Ir a ${fmtDuration(at)}`;
                button.append(canvas);
                button.addEventListener("click", () => setPreviewTime(at));
                strip.append(button);
            }
            strip.hidden = false;
            status.textContent = "Miniaturas listas: pulsa una para mover la previsualización.";
        } catch (_error) {
            if (key === thumbnailsKey) status.textContent = "La vista previa sigue disponible; no se pudieron generar las miniaturas.";
        } finally {
            sampler.removeAttribute("src"); sampler.load();
        }
    }

    function markEditorDirty() {
        editorDirty = true;
        $("saveTimelineBtn").disabled = false;
        $("exportTimelineBtn").disabled = true;
        $("editorSaveState").textContent = "Tienes cambios sin guardar en este proyecto.";
    }

    function getSelectedItem() {
        if (!editorState || !selectedEditorItem) return null;
        const list = selectedEditorItem.type === "card" ? editorState.cards : editorState.brolls;
        return list.find((item) => item.id === selectedEditorItem.id) || null;
    }

    // Tooltip flotante interactivo para vista previa de clips
    let timelineTooltipEl = null;

    function getOrCreateTimelineTooltip() {
        if (!timelineTooltipEl) {
            timelineTooltipEl = document.getElementById("prismTimelineTooltip");
            if (!timelineTooltipEl) {
                timelineTooltipEl = document.createElement("div");
                timelineTooltipEl.id = "prismTimelineTooltip";
                document.body.appendChild(timelineTooltipEl);
            }
        }
        return timelineTooltipEl;
    }

    function showTimelineTooltip(e, item, type, end) {
        const tip = getOrCreateTimelineTooltip();
        let badgeHtml = "";
        let bodyHtml = "";
        let thumbHtml = "";
        const durStr = `${fmtDuration(item.start)} - ${fmtDuration(end)} (${Math.max(1, Math.round(end - item.start))}s)`;

        if (type === "card") {
            badgeHtml = `<div class="pt-tip-badge card">📊 Tarjeta Bento HUD · Escena ${item.scene_id || 1}</div>`;
            if (item.card_url) {
                thumbHtml = `<img class="pt-tip-thumb" src="${item.card_url}" onerror="this.remove()">`;
            }
            bodyHtml = `
                ${badgeHtml}
                ${thumbHtml}
                <div class="pt-tip-title">${esc(item.headline || item.title || "Tarjeta Bento")}</div>
                ${item.stat_value ? `<div class="pt-tip-stat">⚡ ${esc(item.stat_value)}</div>` : ''}
                ${item.body ? `<div class="pt-tip-desc">${esc(item.body)}</div>` : ''}
                <div class="pt-tip-time">
                    <span>⏱️ ${durStr}</span>
                    <span>${esc(item.position || 'auto')}</span>
                </div>
            `;
        } else if (type === "scene") {
            badgeHtml = `<div class="pt-tip-badge scene">🎬 Escena ${item.scene_id || 1} · ${esc(item.camera || 'Avatar')}</div>`;
            if (item.thumb_url) {
                thumbHtml = `<img class="pt-tip-thumb" src="${item.thumb_url}" onerror="this.remove()">`;
            }
            bodyHtml = `
                ${badgeHtml}
                ${thumbHtml}
                <div class="pt-tip-title">${esc(item.title || item.name || "Escena")}</div>
                ${item.speech ? `<div class="pt-tip-desc">«${esc(item.speech)}»</div>` : ''}
                <div class="pt-tip-time">
                    <span>⏱️ ${durStr}</span>
                    <span>${esc(item.type || 'Modular')}</span>
                </div>
            `;
        } else if (type === "broll") {
            badgeHtml = `<div class="pt-tip-badge broll">🎞️ B-Roll de Apoyo Visual</div>`;
            if (item.thumb_url) {
                thumbHtml = `<img class="pt-tip-thumb" src="${item.thumb_url}" onerror="this.remove()">`;
            }
            bodyHtml = `
                ${badgeHtml}
                ${thumbHtml}
                <div class="pt-tip-title">${esc(item.concept || item.title || "B-Roll")}</div>
                <div class="pt-tip-time">
                    <span>⏱️ ${durStr}</span>
                    <span>✓ Material listo</span>
                </div>
            `;
        } else if (type === "speech") {
            badgeHtml = `<div class="pt-tip-badge speech">🎙️ Locución Neural KAI</div>`;
            bodyHtml = `
                ${badgeHtml}
                <div class="pt-tip-title" style="font-size:11.5px; font-weight:normal; line-height:1.45;">«${esc(item.text || item.title || "")}»</div>
                <div class="pt-tip-time">
                    <span>⏱️ ${durStr}</span>
                    <span>Voz sintetizada</span>
                </div>
            `;
        }

        tip.innerHTML = bodyHtml;
        tip.classList.add("active");
        positionTimelineTooltip(e);
    }

    function positionTimelineTooltip(e) {
        const tip = getOrCreateTimelineTooltip();
        if (!tip || !tip.classList.contains("active")) return;
        const tipW = 290;
        const tipH = tip.offsetHeight || 160;
        let left = e.clientX + 14;
        let top = e.clientY - tipH - 12;

        if (left + tipW > window.innerWidth - 10) {
            left = e.clientX - tipW - 14;
        }
        if (top < 10) {
            top = e.clientY + 20;
        }
        tip.style.left = `${Math.max(10, left)}px`;
        tip.style.top = `${Math.max(10, top)}px`;
    }

    function hideTimelineTooltip() {
        const tip = getOrCreateTimelineTooltip();
        if (tip) tip.classList.remove("active");
    }

    function renderInspector() {
        const inspector = $("editorInspector");
        const item = getSelectedItem();
        if (!item) {
            inspector.innerHTML = "<b>Selecciona un elemento de la línea de tiempo</b><p>Podrás cambiar su momento, duración, posición o retirarlo antes de una nueva exportación.</p>";
            return;
        }
        const kind = selectedEditorItem.type === "card" ? "Tarjeta Bento verificada" : "Apoyo B-Roll";
        const title = selectedEditorItem.type === "card" ? (item.headline || item.title) : item.concept;
        const end = selectedEditorItem.type === "card" ? Number(item.start) + Number(item.duration || 7) : item.end;
        const context = selectedEditorItem.type === "card" ? (item.body || item.note || item.claim) : item.status;
        const positions = ["auto", "upper_left", "upper_right", "lower_left", "lower_right"];
        inspector.innerHTML = `
            <b>${esc(kind)} · ${esc(title)}</b>
            ${item.card_url ? `<div style="margin: 8px 0; text-align:center;"><img src="${item.card_url}${item.card_url.includes('?') ? '&' : '?'}t=${Date.now()}" style="max-width: 100%; max-height: 120px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.15); box-shadow: 0 4px 16px rgba(0,0,0,0.5);"></div>` : ''}
            <p>${esc(context || "Aún se está preparando.")}</p>
            ${selectedEditorItem.type === "card" ? `
                <div style="margin: 8px 0; font-size: 11px; color: #38bdf8; background: rgba(56, 189, 248, 0.08); padding: 7px 10px; border-radius: 6px; border-left: 3px solid #38bdf8; line-height: 1.45;">
                    🤖 <b>AetherCopilot:</b> Tarjeta seleccionada para IA. Puedes pedirle al chat: <i>"Cambia el titular de esta tarjeta a ..."</i> o <i>"Actualiza la cifra a ..."</i>.
                </div>
            ` : ''}
            <label>Activo <input id="editEnabled" type="checkbox" ${item.enabled === false ? "" : "checked"}></label>
            <label>Inicio <input id="editStart" type="number" min="0" step="0.1" value="${Number(item.start || 0).toFixed(1)}"></label>
            <label>Fin <input id="editEnd" type="number" min="0" step="0.1" value="${Number(end || 0).toFixed(1)}"></label>
            ${selectedEditorItem.type === "card" ? `<label>Posición <select id="editPosition">${positions.map((position) => `<option value="${position}" ${item.position === position ? "selected" : ""}>${position.replace("_", " ")}</option>`).join("")}</select></label>
            ${item.avatar_spoken_text ? `<div style="margin:8px 0 4px 0; font-size:12px; color:#38bdf8; background:rgba(56,189,248,0.1); border-left:3px solid #38bdf8; padding:6px 10px; border-radius:6px; line-height:1.4;">⚡ <b>KAI Copilot (Voz Neural):</b><br>«${esc(item.avatar_spoken_text)}»</div>` : ""}` : ""}`;
        $("editEnabled").addEventListener("change", (event) => { item.enabled = event.target.checked; markEditorDirty(); renderTimeline(); });
        $("editStart").addEventListener("change", (event) => {
            item.start = Math.max(0, Number(event.target.value || 0));
            if (selectedEditorItem.type === "card") item.duration = Math.max(4.5, Number(item.duration || 7));
            else item.end = Math.max(item.start + 1, Number(item.end || item.start + 1));
            markEditorDirty(); renderTimeline();
        });
        $("editEnd").addEventListener("change", (event) => {
            const value = Math.max(Number(item.start || 0) + (selectedEditorItem.type === "card" ? 4.5 : 1), Number(event.target.value || 0));
            if (selectedEditorItem.type === "card") item.duration = Math.min(12, value - Number(item.start || 0));
            else item.end = value;
            markEditorDirty(); renderTimeline();
        });
        if (selectedEditorItem.type === "card") $("editPosition").addEventListener("change", (event) => { item.position = event.target.value; markEditorDirty(); });
    }

    function timelineClip(item, type, duration) {
        const button = document.createElement("button");
        const end = type === "card" ? Number(item.start) + Number(item.duration || 7) : Number(item.end);
        button.type = "button";
        button.className = `clip clip-${type}${item.enabled === false ? " is-muted" : ""}${selectedEditorItem?.type === type && selectedEditorItem.id === item.id ? " is-selected" : ""}`;
        button.style.left = percent(item.start, duration);
        button.style.width = `max(2.2%, ${percent(Math.max(1, end - Number(item.start)), duration)})`;
        if (item.scene_id) button.dataset.sceneId = item.scene_id;
        
        let label = item.title || "";
        if (type === "card") label = item.headline || item.title || "Tarjeta Bento";
        else if (type === "broll") label = item.concept || item.title || "Clip B-Roll";
        else if (type === "scene") label = item.title || item.name || `Escena ${item.scene_id}`;
        else if (type === "speech") label = item.title || item.text || "Locución";
        
        const thumbUrl = item.thumb_url || (type === "card" ? item.card_url : null);
        const icon = type === "card" ? "📊" : (type === "scene" ? "🎬" : (type === "broll" ? "🎞️" : "🎙️"));

        button.innerHTML = `
            ${thumbUrl ? `<img class="clip-mini-thumb" src="${thumbUrl}" onerror="this.remove()">` : `<span class="clip-icon-tag">${icon}</span>`}
            <span class="clip-text-label">${esc(label)}</span>
        `;
        button.title = ""; // Tooltip flotante nativo enriquecido

        button.addEventListener("mouseenter", (e) => showTimelineTooltip(e, item, type, end));
        button.addEventListener("mousemove", (e) => positionTimelineTooltip(e));
        button.addEventListener("mouseleave", () => hideTimelineTooltip());

        button.addEventListener("click", (e) => {
            e.stopPropagation();
            hideTimelineTooltip();
            selectedEditorItem = { type, id: item.id };
            window.selectedEditorItem = selectedEditorItem;
            setPreviewTime(item.start);
            renderTimeline();
            renderInspector();
            if (type === "scene") {
                const row = document.querySelector(`.prism-sb-scene-row[data-scene-id="${item.scene_id}"]`);
                if (row) {
                    row.scrollIntoView({ behavior: "smooth", block: "nearest" });
                }
            }
        });
        return button;
    }

    // Puente público para que AetherCopilot modifique tarjetas en tiempo real
    window.updateCardFromCopilot = function(action) {
        if (!editorState || !editorState.cards) return false;
        const targetId = action.card_id || selectedEditorItem?.id;
        const card = editorState.cards.find(c => c.id === targetId || String(c.scene_id) === String(action.scene_id) || c.headline === action.current_headline);
        if (!card) return false;
        if (action.headline) card.headline = action.headline;
        if (action.title) card.title = action.title || action.headline;
        if (action.stat_value) card.stat_value = action.stat_value;
        if (action.body) card.body = action.body;
        if (action.position) card.position = action.position;
        if (action.start !== undefined) card.start = Number(action.start);
        if (action.duration !== undefined) card.duration = Number(action.duration);
        if (action.card_url) card.card_url = action.card_url;
        markEditorDirty();
        renderTimeline();
        renderInspector();
        renderStudio(editorState);
        setPreviewTime(card.start);
        return true;
    };
    window.getSelectedItem = () => getSelectedItem();
    window.selectedEditorItem = selectedEditorItem;

    function renderTimeline() {
        if (!editorState) return;
        const duration = Number(editorState.duration || 1);
        const ruler = $("timelineRuler");
        const tracks = $("timelineTracks");
        const scrollable = $("timelineScrollable") || ruler?.parentElement;
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

        // Clic en la regla o pistas para mover el cabezal directamente
        function seekFromPointer(e) {
            const target = ruler.getBoundingClientRect();
            if (target.width <= 0) return;
            const ratio = Math.max(0, Math.min(1, (e.clientX - target.left) / target.width));
            setPreviewTime(ratio * duration);
        }
        ruler.onclick = seekFromPointer;
        if (scrollable) {
            scrollable.onclick = (e) => {
                if (e.target.closest(".clip") || e.target.closest(".track-name")) return;
                seekFromPointer(e);
            };
        }

        const rows = [];
        if (editorState.scenes && editorState.scenes.length > 0) {
            rows.push(["🎬 Escenas", "scene", editorState.scenes]);
        }
        if (editorState.cards && editorState.cards.length > 0) {
            rows.push(["📊 Tarjetas", "card", editorState.cards]);
        } else {
            rows.push(["📊 Tarjetas", "card", []]);
        }
        if (editorState.brolls && editorState.brolls.length > 0) {
            rows.push(["🎞️ B-Roll", "broll", editorState.brolls]);
        } else {
            rows.push(["🎞️ B-Roll", "broll", []]);
        }
        if (editorState.speech && editorState.speech.length > 0) {
            rows.push(["🎙️ Locución", "speech", editorState.speech]);
        }
        if (editorState.shorts && editorState.shorts.length > 0) {
            rows.push(["⚡ Shorts", "short", editorState.shorts]);
        }
        if (editorState.cuts && editorState.cuts.length > 0) {
            rows.push(["✂️ Cortes", "cut", editorState.cuts]);
        }

        rows.forEach(([label, type, items]) => {
            const row = document.createElement("div"); row.className = "track";
            const name = document.createElement("span"); name.className = "track-name"; name.textContent = label;
            const lane = document.createElement("div"); lane.className = "track-lane";
            items.forEach((item, index) => {
                const mapped = type === "cut" ? { id: `cut-${index}`, start: item.start_sec, end: item.end_sec, title: "Pausa eliminada", enabled: true } : item;
                lane.append(timelineClip(mapped, type, duration));
            });
            row.append(name, lane); tracks.append(row);
        });
    }

    function setStudioAspectRatio(aspect, isManual = false) {
        if (isManual) window._studioAspectManuallySet = true;
        const wrap = $("viewportScreenWrap");
        const badge = $("monitorAspectBadge");
        const btn169 = $("btnStudioAspect169");
        const btn916 = $("btnStudioAspect916");
        const is169 = (aspect === "16:9" || aspect === "horizontal" || aspect === "youtube");

        if (wrap) {
            wrap.classList.toggle("aspect-16-9", is169);
            wrap.classList.toggle("aspect-9-16", !is169);
        }
        if (badge) {
            badge.textContent = is169 ? "16:9" : "9:16";
        }
        if (btn169) btn169.classList.toggle("active", is169);
        if (btn916) btn916.classList.toggle("active", !is169);
    }
    window.setStudioAspectRatio = setStudioAspectRatio;

    function renderStudio(editor, previewUrl) {
        if (!editor) return;
        const changed = JSON.stringify(editor) !== JSON.stringify(editorState);
        if (changed && !editorDirty) editorState = JSON.parse(JSON.stringify(editor));
        if (!editorState) editorState = JSON.parse(JSON.stringify(editor));
        const duration = Number(editorState.duration || 0);
        if (activeMode === "studio") $("studioSection").hidden = false;
        $("exportTimelineBtn").disabled = editorDirty || !observedTaskId;

        if (!window._studioAspectManuallySet && (editorState.aspect_ratio || editor?.aspect_ratio)) {
            setStudioAspectRatio(editorState.aspect_ratio || editor?.aspect_ratio);
        }

        const scCount = (editorState.scenes || []).length;
        const cdCount = (editorState.cards || []).length;
        const brCount = (editorState.brolls || []).length;
        const parts = [];
        if (scCount) parts.push(`${scCount} escenas`);
        if (cdCount) parts.push(`${cdCount} tarjetas`);
        if (brCount) parts.push(`${brCount} B-Rolls`);
        if ($("studioSummary")) $("studioSummary").textContent = parts.join(" · ") || `${fmtDuration(duration)} · Master 1080p`;
        if ($("studioTitle")) $("studioTitle").textContent = editorState.summary || "Estudio de Producción KAI";
        if ($("studioIntro")) $("studioIntro").textContent = editorState.summary || "El agente está estructurando los elementos de la edición.";
        if ($("previewDuration")) $("previewDuration").textContent = fmtDuration(duration);

        // Actualizar sideboard de escenas
        const studioScenesList = $("studioLiveScenesList");
        const studioScenesCount = $("studioScenesCount");
        if (studioScenesCount) studioScenesCount.textContent = scCount;
        if (studioScenesList && scCount > 0) {
            studioScenesList.replaceChildren();
            editorState.scenes.forEach((sc, idx) => {
                const sNum = sc.scene_id || (idx + 1);
                const sRow = document.createElement("div");
                sRow.className = "prism-sb-scene-row";
                sRow.dataset.sceneId = sNum;
                sRow.dataset.start = sc.start;
                sRow.dataset.end = sc.end;
                sRow.innerHTML = `
                    <div class="prism-sb-scene-thumb"><img src="${sc.thumb_url}" onerror="this.src='/static/images/app_bg.jpg'"></div>
                    <div class="prism-sb-scene-info">
                        <div class="prism-sb-scene-name">E${sNum}: ${sc.name || sc.title}</div>
                        <div class="prism-sb-scene-sub">
                            <span>${sc.camera || "PIP"}</span>
                            <span>${sc.type || "Modular"}</span>
                            <span>${fmtDuration(sc.duration || 0)}</span>
                        </div>
                    </div>
                    <span class="prism-sb-scene-status done">✓ ${fmtDuration(sc.start)}</span>
                `;
                sRow.addEventListener("click", () => {
                    setPreviewTime(sc.start);
                    const preview = $("projectPreview");
                    if (preview && preview.paused) preview.play().catch(() => {});
                });
                studioScenesList.appendChild(sRow);
            });
        }

        // Actualizar sideboard de tarjetas Bento
        const studioCardsList = $("studioLiveCardsList");
        const studioCardsCount = $("studioCardsCount");
        if (studioCardsCount) studioCardsCount.textContent = cdCount;
        if (studioCardsList && cdCount > 0) {
            studioCardsList.replaceChildren();
            editorState.cards.forEach((cd) => {
                const cRow = document.createElement("div");
                cRow.className = "prism-sb-card-row";
                cRow.style.cursor = "pointer";
                cRow.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="prism-sb-card-badge">E${cd.scene_id || 1} · BENTO HUD</span>
                        ${cd.stat_value ? `<strong class="prism-sb-card-stat" style="color:#f59e0b;">${cd.stat_value}</strong>` : ""}
                    </div>
                    <div class="prism-sb-card-headline">${cd.headline || cd.title || "Dato Clave"}</div>
                    <div style="font-size:10px; color:#64748b; margin-top:3px;">${cd.body ? cd.body.slice(0, 70) + '...' : ''} · ${fmtDuration(cd.start)}</div>
                `;
                cRow.addEventListener("click", () => {
                    setPreviewTime(cd.start);
                });
                studioCardsList.appendChild(cRow);
            });
        }

        // Actualizar sideboard de hechos e investigación
        const studioFactsBox = $("studioLiveFactsBox");
        if (studioFactsBox) {
            studioFactsBox.replaceChildren();
            const factItem = document.createElement("div");
            factItem.style.padding = "8px 10px";
            factItem.style.fontSize = "11px";
            factItem.style.lineHeight = "1.5";
            factItem.style.color = "#cbd5e1";
            factItem.innerHTML = `
                <strong style="color:#38bdf8; display:block; margin-bottom:4px;">🎯 Producción Master Sincronizada:</strong>
                ${editorState.topic || editorState.summary || "Transmisión KAI"}
                <div style="margin-top:8px; font-size:10px; color:#64748b;">
                    Duración Total: <b>${fmtDuration(duration)}</b> · 1080p FHD Broadcast · 25 FPS
                </div>
            `;
            studioFactsBox.appendChild(factItem);
        }

        // Estado del monitor KAI
        if ($("studioTelemetryStepBadge")) $("studioTelemetryStepBadge").textContent = "● PRODUCCIÓN MASTER LISTA";
        if ($("studioTelemetryPct")) $("studioTelemetryPct").textContent = "100%";
        if ($("studioTelemetryMsg")) $("studioTelemetryMsg").textContent = "Todos los materiales y escenas sincronizados en la línea de tiempo.";

        // Cargar video en preview si es necesario
        const preview = $("projectPreview");
        if (previewUrl && preview.dataset.source !== previewUrl) {
            preview.dataset.source = previewUrl;
            preview.src = previewUrl;
            preview.load();
            // Descubrir el reproductor: la telemetría en vivo oculta el video y
            // muestra la miniatura de escena; al cargar el preview real hay que
            // restaurar el video y ocultar esa imagen. Antes nadie lo hacía y el
            // monitor quedaba congelado en la última miniatura ("no se muestra").
            preview.style.display = "block";
            const fallbackStage = $("telemetryStageImgStudio");
            if (fallbackStage) fallbackStage.style.display = "none";
            $("previewEmpty").hidden = true;
            preview.addEventListener("loadedmetadata", () => buildTimelineThumbnails(previewUrl, Number(preview.duration || duration)), { once: true });
        }
        $("timelineCursor").max = String(Math.max(1, duration));
        renderTimeline(); renderInspector();
    }

    async function openProject(projectId) {
        const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "No se pudo abrir el proyecto.");
        observedTaskId = projectId;
        editorDirty = false;
        selectedEditorItem = null;

        // Asegurar que el modo esté en Mesa & Timeline para ver el monitor y pistas
        switchMode("studio");

        // Configurar relación de aspecto del monitor (16:9 vs 9:16) según opciones del proyecto
        const projAspect = data.project?.options?.aspect_ratio || data.project?.aspect_ratio || (data.project?.options?.mode === "shorts" ? "9:16" : "16:9");
        window._studioAspectManuallySet = false;
        setStudioAspectRatio(projAspect);

        // Si el proyecto sigue en curso (ej: status render o running), activar escucha en vivo
        const projStatus = data.project?.status;
        if (projStatus && projStatus !== "done" && projStatus !== "error" && projStatus !== "cancelled") {
            listen(projectId);
        }

        // Reactivar y desbloquear botón de transmisión
        const startStreamerBtn = $("startStreamerBtn");
        const startStreamerBtnText = $("startStreamerBtnText");
        if (startStreamerBtn) {
            startStreamerBtn.disabled = false;
            if (startStreamerBtnText) startStreamerBtnText.textContent = "🚀 Iniciar Transmisión de KAI";
        }

        const previewUrl = `/api/projects/${encodeURIComponent(projectId)}/preview`;
        if (data.project?.result) {
            didShowResults = true;
            showResults(data.project.result, projectId);
        }

        const previewBox = $("previewContainer");
        if (previewBox) {
            previewBox.hidden = false;
            previewBox.style.display = "block";
        }
        const dropWrap = $("copilotDropWrap");
        if (dropWrap) {
            dropWrap.hidden = true;
            dropWrap.style.display = "none";
        }
        const preview = $("projectPreview");
        if (preview && previewUrl) {
            preview.hidden = false;
            preview.style.display = "block";
            preview.controls = false;
            preview.volume = 1;
            preview.muted = false;
            if (preview.src !== previewUrl && !preview.src.endsWith(previewUrl)) {
                preview.src = previewUrl;
                // Marcar la fuente cargada: la telemetría en vivo usa este marcador
                // para no volver a ocultar el reproductor una vez el video existe.
                preview.dataset.source = previewUrl;
                preview.load();
            }
            // Ocultar la imagen de escena en vivo: el monitor muestra el video real.
            const stageImgStudio = $("telemetryStageImgStudio");
            if (stageImgStudio) stageImgStudio.style.display = "none";
        }
        const monitorBar = $("monitorDownloadBar");
        if (monitorBar) {
            monitorBar.hidden = false;
            monitorBar.style.display = "flex";
        }
        const dlBtn = $("downloadMasterBtn");
        if (dlBtn) {
            dlBtn.href = "#";
            dlBtn.onclick = (e) => {
                e.preventDefault();
                triggerDownload(`/api/projects/${encodeURIComponent(projectId)}/download`, `KAI_${projectId}.mp4`);
            };
        }

        if (data.editor) {
            renderStudio(data.editor, previewUrl);
        }

        currentStudioProjectId = projectId;
        loadStudioClips(projectId);

        const url = new URL(window.location.href);
        url.searchParams.delete("task");
        url.searchParams.set("project", projectId);
        window.history.replaceState({}, "", url);
    }

    let allLoadedProjects = [];
    let currentProjectFilter = "all";
    let currentProjectSearch = "";

    function closeVideoModal() {
        const modal = $("videoPlayerModal");
        const video = $("modalVideoElement");
        if (video) {
            video.pause();
            video.removeAttribute("src");
            video.load();
        }
        if (modal) {
            modal.hidden = true;
        }
    }

    let currentModalProjectId = null;
    let currentStudioProjectId = null;

    function showToast(message, level = "info") {
        if (typeof window.showToast === "function") {
            window.showToast(message, level);
            return;
        }
        const colors = { success: "#10b981", error: "#ef4444", warning: "#f59e0b", info: "#38bdf8" };
        const icons = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };
        const color = colors[level] || colors.info;
        const el = document.createElement("div");
        el.style.cssText = `position: fixed; bottom: 88px; right: 24px; z-index: 99999;
            background: #1e293b; border: 1px solid ${color}55; border-left: 3px solid ${color};
            color: #e2e8f0; padding: 12px 18px; border-radius: 10px; font-size: 13px; font-weight: 500;
            max-width: 380px; box-shadow: 0 8px 32px rgba(0,0,0,.45); display: flex; gap: 10px; align-items: center;
            pointer-events: none; transition: opacity .4s ease, transform .4s ease;`;
        el.innerHTML = `<span>${icons[level] || icons.info}</span><span>${esc(message)}</span>`;
        document.body.appendChild(el);
        setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateX(20px)"; setTimeout(() => el.remove(), 450); }, 4200);
    }

    async function loadStudioClips(projectId) {
        if (!projectId) return;
        currentStudioProjectId = projectId;
        const grid = $("studioClipsGrid");
        const badge = $("studioClipsCountBadge");
        if (!grid) return;

        try {
            const resp = await fetch(`/api/projects/${encodeURIComponent(projectId)}/clips`);
            if (!resp.ok) return;
            const data = await resp.json();
            const clips = data.clips || [];

            if (badge) {
                badge.textContent = `${clips.length} ${clips.length === 1 ? "clip" : "clips"}`;
            }

            if (clips.length > 0) {
                grid.innerHTML = clips.map((c, i) => `
                    <article class="studio-clip-card">
                        <div class="studio-clip-media-wrap">
                            <video src="${c.url}" preload="metadata" playsinline controls></video>
                            <span class="studio-clip-badge-pill">📱 Short #${i + 1}</span>
                            <span class="studio-clip-size-badge">${c.size_mb || 0} MB</span>
                        </div>
                        <div class="studio-clip-body">
                            <h5 class="studio-clip-title" title="${esc(c.name || '')}">${esc(c.name || `Clip #${i+1}`)}</h5>
                            <div class="studio-clip-meta">
                                <span>⚡ 9:16 Vertical</span>
                                <span>·</span>
                                <span>TikTok &amp; Reels</span>
                            </div>
                        </div>
                        <div class="studio-clip-actions">
                            <a href="${c.url}" target="_blank" class="studio-clip-btn view" title="Ver en nueva ventana">
                                ▶ Ver Completo
                            </a>
                            <a href="${c.url}" download="${esc(c.filename || `short_${i+1}.mp4`)}" class="studio-clip-btn download" title="Descargar video vertical 9:16">
                                📥 Descargar .mp4
                            </a>
                        </div>
                    </article>
                `).join("");
            } else {
                grid.innerHTML = `
                    <div class="studio-clips-empty">
                        <div style="font-size: 32px;">📱✂️</div>
                        <strong style="color: #f1f5f9; font-size: 14px;">Aún no se han generado clips 9:16 de este video</strong>
                        <p style="color: #94a3b8; font-size: 12px; margin: 0; max-width: 480px;">
                            KAI puede analizar la línea de tiempo y recortar automáticamente ganchos y momentos clave en formato vertical 9:16 listos para TikTok, Instagram Reels y YouTube Shorts.
                        </p>
                        <button type="button" class="subcard-pill-btn active" id="studioClipsEmptyExtractBtn" style="background: linear-gradient(135deg, #a855f7, #6366f1); color: #fff; font-weight: 700; border: none; padding: 8px 18px; border-radius: 8px; cursor: pointer; box-shadow: 0 4px 14px rgba(168,85,247,0.35); margin-top: 6px;">
                            ⚡ Extraer Clips 9:16 con IA ahora
                        </button>
                    </div>
                `;
                $("studioClipsEmptyExtractBtn")?.addEventListener("click", () => extractStudioClipsHandler(projectId));
            }
        } catch (e) {
            console.error("Error loading studio clips:", e);
        }
    }

    async function extractStudioClipsHandler(projectId) {
        const targetId = projectId || currentStudioProjectId || observedTaskId;
        if (!targetId) {
            showToast("No hay un proyecto activo para extraer clips.", "warning");
            return;
        }

        const btn = $("studioExtractClipsBtn");
        const emptyBtn = $("studioClipsEmptyExtractBtn");
        const loading = $("studioClipsLoading");

        if (btn) btn.disabled = true;
        if (emptyBtn) emptyBtn.disabled = true;
        if (loading) {
            loading.hidden = false;
            loading.style.display = "flex";
        }

        showToast("✂️ Extrayendo y recortando clips 9:16 con subtítulos dinámicos...", "info");

        try {
            const resp = await fetch(`/api/projects/${encodeURIComponent(targetId)}/extract-clips`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await resp.json();
            if (resp.ok && data.success) {
                showToast(`🎉 ¡${data.clips?.length || 0} clips verticales 9:16 generados con éxito!`, "success");
                await loadStudioClips(targetId);
            } else {
                showToast(data.detail || data.message || "No se pudieron extraer clips.", "error");
            }
        } catch (err) {
            showToast("Error de conexión al extraer clips.", "error");
        } finally {
            if (btn) btn.disabled = false;
            if (emptyBtn) emptyBtn.disabled = false;
            if (loading) {
                loading.hidden = true;
                loading.style.display = "none";
            }
        }
    }

    // Botón de extracción de clips en la Mesa & Timeline
    $("studioExtractClipsBtn")?.addEventListener("click", () => extractStudioClipsHandler());

    window.loadStudioClips = loadStudioClips;
    window.extractStudioClips = extractStudioClipsHandler;

    async function loadProjectClips(projectId) {
        const grid = $("modalClipsGrid");
        const sec = $("modalClipsSection");
        if (!grid || !sec) return;
        try {
            const resp = await fetch(`/api/projects/${encodeURIComponent(projectId)}/clips`);
            if (!resp.ok) return;
            const data = await resp.json();
            const clips = data.clips || [];
            if (clips.length > 0) {
                sec.hidden = false;
                grid.innerHTML = clips.map((c, i) => `
                    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 6px;">
                        <div style="display: flex; align-items: center; justify-content: space-between;">
                            <span style="font-size: 11px; font-weight: 700; color: #fff;">📱 Short #${i+1}</span>
                            <span style="font-size: 10px; color: var(--text-muted);">${c.size_mb || 0} MB</span>
                        </div>
                        <span style="font-size: 11px; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${c.name}">${c.name}</span>
                        <div style="display: flex; gap: 6px; margin-top: 4px;">
                            <a href="${c.url}" target="_blank" class="yt-open-pill-btn" style="padding: 4px 8px; font-size: 10px; flex: 1; text-align: center; text-decoration: none;">▶ Ver 9:16</a>
                            <a href="${c.url}" download="${c.filename}" class="yt-open-pill-btn" style="padding: 4px 8px; font-size: 10px; flex: 1; text-align: center; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); text-decoration: none;">📥 Descargar</a>
                        </div>
                    </div>
                `).join("");
            } else {
                grid.innerHTML = "";
                sec.hidden = true;
            }
        } catch (e) {
            console.error("Error loading project clips:", e);
        }
    }

    async function extractClipsHandler() {
        if (!currentModalProjectId) return;
        const btn = $("modalExtractClipsBtn");
        const loading = $("modalClipsLoadingText");
        const sec = $("modalClipsSection");
        if (btn) btn.disabled = true;
        if (loading) loading.hidden = false;
        if (sec) sec.hidden = false;
        showToast("✂️ Extrayendo y recortando clips 9:16 para Shorts/Reels...", "info");

        try {
            const resp = await fetch(`/api/projects/${encodeURIComponent(currentModalProjectId)}/extract-clips`, {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const data = await resp.json();
            if (resp.ok && data.success) {
                showToast(`🎉 ¡${data.clips.length} clips verticales 9:16 listos!`, "success");
                await loadProjectClips(currentModalProjectId);
            } else {
                showToast(data.detail || data.message || "No se pudieron extraer clips.", "error");
            }
        } catch (err) {
            showToast("Error de conexión al extraer clips.", "error");
        } finally {
            if (btn) btn.disabled = false;
            if (loading) loading.hidden = true;
        }
    }

    function openVideoModal(project) {
        currentModalProjectId = project.id;
        const modal = $("videoPlayerModal");
        const video = $("modalVideoElement");
        const title = $("modalVideoTitle");
        const sub = $("modalVideoSub");
        const dlBtn = $("modalDownloadBtn");
        if (!modal || !video) return;

        const videoSrc = project.master_video_url || `/api/projects/${encodeURIComponent(project.id)}/preview`;
        video.src = videoSrc;
        video.load();

        if (title) title.textContent = project.name || "Producción KAI";
        if (sub) {
            const topic = project.topic ? `Tema: ${project.topic}` : "";
            const dur = project.duration ? ` · Duración: ${formatDurationSecs(project.duration)}` : "";
            const dt = project.updated_at ? ` · ${new Date(project.updated_at).toLocaleDateString([], { month: "short", day: "numeric" })}` : "";
            sub.textContent = `${topic}${dur}${dt}` || "Video Broadcast Master KAI";
        }

        if (dlBtn) {
            dlBtn.href = videoSrc;
            dlBtn.download = `${(project.name || "video_kai").replace(/[^a-zA-Z0-9_\-]/g, "_")}.mp4`;
        }

        modal.hidden = false;
        video.play().catch(() => {});
        loadProjectClips(project.id);
    }

    // Modal listeners
    $("modalExtractClipsBtn")?.addEventListener("click", extractClipsHandler);
    $("modalCloseBtn")?.addEventListener("click", closeVideoModal);
    $("videoPlayerModal")?.addEventListener("click", (e) => {
        if (e.target.id === "videoPlayerModal") {
            closeVideoModal();
        }
    });
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && $("videoPlayerModal") && !$("videoPlayerModal").hidden) {
            closeVideoModal();
        }
    });

    function formatDurationSecs(secs) {
        if (!secs || isNaN(secs)) return "00:00";
        const m = Math.floor(secs / 60);
        const s = Math.floor(secs % 60);
        return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
    }

    function renderProjectsGrid() {
        const list = $("savedProjectsList");
        if (!list) return;
        list.replaceChildren();

        let filtered = allLoadedProjects.filter(p => {
            const matchesSearch = !currentProjectSearch || (p.name || "").toLowerCase().includes(currentProjectSearch.toLowerCase()) || (p.topic || "").toLowerCase().includes(currentProjectSearch.toLowerCase());
            const st = (p.status || "").toLowerCase();
            let matchesFilter = true;
            if (currentProjectFilter === "done") matchesFilter = (st === "done" || p.has_result);
            else if (currentProjectFilter === "progress") matchesFilter = (st !== "done" && !p.has_result && st !== "error");
            return matchesSearch && matchesFilter;
        });

        if (!filtered.length) {
            const empty = document.createElement("div");
            empty.style.cssText = "grid-column: 1 / -1; color:var(--text-muted); font-size:13px; text-align:center; padding:48px 24px; background:rgba(255,255,255,0.02); border-radius:16px; border:1px dashed rgba(255,255,255,0.08);";
            empty.innerHTML = `
                <div style="font-size:32px; margin-bottom:10px; opacity:0.6;">📺</div>
                <strong style="color:#e2e8f0; font-size:15px; display:block; margin-bottom:4px;">No se encontraron videos</strong>
                <span>${currentProjectSearch ? "Intenta con otro término de búsqueda o cambia el filtro." : "Aún no hay producciones registradas en esta vista."}</span>
            `;
            list.append(empty);
            return;
        }

        filtered.forEach((project) => {
            const card = document.createElement("article");
            card.className = "yt-video-card";

            // 1. Contenedor de Miniatura 16:9
            const thumbWrap = document.createElement("div");
            thumbWrap.className = "yt-card-thumb-wrap";

            if (project.thumbnail_url) {
                const img = document.createElement("img");
                img.className = "yt-card-thumb-img";
                img.src = project.thumbnail_url;
                img.alt = project.name || "Video thumbnail";
                img.loading = "lazy";
                img.onerror = () => {
                    img.style.display = "none";
                    if (thumbFallback) thumbFallback.style.display = "flex";
                };
                thumbWrap.append(img);
            }

            const thumbFallback = document.createElement("div");
            thumbFallback.className = "yt-card-thumb-fallback";
            thumbFallback.style.display = project.thumbnail_url ? "none" : "flex";
            thumbFallback.innerHTML = `
                <span class="fallback-icon">🎬</span>
                <span>${project.has_result ? "Video Broadcast" : "Producción KAI"}</span>
            `;
            thumbWrap.append(thumbFallback);

            // Badge de Duración
            const durBadge = document.createElement("span");
            durBadge.className = "yt-card-duration-badge";
            durBadge.textContent = project.duration ? formatDurationSecs(project.duration) : "05:00";
            thumbWrap.append(durBadge);

            // Play Overlay en Hover
            const playOverlay = document.createElement("div");
            playOverlay.className = "yt-card-play-overlay";
            playOverlay.innerHTML = `<div class="yt-card-play-icon"><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg></div>`;
            thumbWrap.append(playOverlay);

            // 2. Cuerpo de metadatos (Estilo canal de YouTube)
            const body = document.createElement("div");
            body.className = "yt-card-body";

            const infoRow = document.createElement("div");
            infoRow.className = "yt-card-info-row";

            // Avatar del creador KAI
            const avatar = document.createElement("div");
            avatar.className = "yt-card-channel-avatar";
            avatar.title = "KAI Video Creator";
            const avImg = document.createElement("img");
            avImg.src = "/assets/avatars/kai/idle.jpg";
            avImg.alt = "KAI";
            avatar.append(avImg);

            // Textos y Título
            const texts = document.createElement("div");
            texts.className = "yt-card-texts";

            const title = document.createElement("h4");
            title.className = "yt-card-title";
            title.textContent = project.name || "Transmisión sin título";
            title.title = project.name || "";

            const channelName = document.createElement("div");
            channelName.className = "yt-card-channel-name";
            channelName.innerHTML = `<span>KAI Studio</span> <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>`;

            const metaLine = document.createElement("div");
            metaLine.className = "yt-card-meta-line";
            
            const dt = project.updated_at ? new Date(project.updated_at).toLocaleDateString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "Reciente";
            const dateSpan = document.createElement("span");
            dateSpan.textContent = dt;

            const dot = document.createElement("span");
            dot.className = "yt-card-meta-dot";

            const st = (project.status || "done").toLowerCase();
            const statusBadge = document.createElement("span");
            statusBadge.className = `saved-project-badge ${st === "done" ? "badge-done" : st === "error" ? "badge-error" : "badge-render"}`;
            statusBadge.style.fontSize = "10px";
            statusBadge.style.padding = "1px 6px";
            statusBadge.textContent = st === "done" ? "Listo" : st === "error" ? "Error" : "En curso";

            metaLine.append(dateSpan, dot, statusBadge);
            texts.append(title, channelName, metaLine);
            infoRow.append(avatar, texts);
            body.append(infoRow);

            // 3. Barra inferior de acciones (Publicar en YouTube / Abrir / Eliminar)
            const footer = document.createElement("div");
            footer.className = "yt-card-footer";

            const actionLeft = document.createElement("div");
            actionLeft.className = "yt-action-left";

            // Botón Publicar en YouTube
            const ytPublishBtn = document.createElement("button");
            ytPublishBtn.type = "button";
            ytPublishBtn.className = "yt-publish-btn";
            ytPublishBtn.title = "Subir y publicar directamente en YouTube Studio";
            ytPublishBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor">
                    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
                </svg>
                <span>Publicar</span>
            `;
            ytPublishBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                // Abre el Estudio de Publicación: ver qué se publica,
                // miniatura con IA y subida directa/asistida a YouTube.
                publishStudio.open(project);
            });

            // Botón Reanudar (Si el proyecto no está completado y se puede recuperar)
            const isFinished = (st === "done" || project.has_result);
            if (!isFinished) {
                const resumeBtn = document.createElement("button");
                resumeBtn.type = "button";
                resumeBtn.className = "yt-open-pill-btn";
                resumeBtn.style.background = "rgba(245, 158, 11, 0.18)";
                resumeBtn.style.borderColor = "rgba(245, 158, 11, 0.4)";
                resumeBtn.style.color = "#fbbf24";
                resumeBtn.title = "Reanudar este proyecto desde las escenas ya guardadas";
                resumeBtn.innerHTML = `<span>Reanudar</span> <span style="font-size:10px;">⚡</span>`;
                resumeBtn.addEventListener("click", async (e) => {
                    e.stopPropagation();
                    resumeBtn.disabled = true;
                    resumeBtn.textContent = "Reanudando...";
                    try {
                        const res = await fetch(`/api/projects/${encodeURIComponent(project.id)}/resume`, { method: "POST" });
                        if (res.ok) {
                            openProject(project.id).catch(() => {});
                        } else {
                            const err = await res.json();
                            alert(err.detail || "No se pudo reanudar.");
                            resumeBtn.disabled = false;
                            resumeBtn.innerHTML = `<span>Reanudar</span> <span>⚡</span>`;
                        }
                    } catch (err) {
                        alert("Error de conexión al reanudar.");
                        resumeBtn.disabled = false;
                    }
                });
                actionLeft.append(resumeBtn);

                // Botón Cancelar proceso activo desde la biblioteca
                const cancelPillBtn = document.createElement("button");
                cancelPillBtn.type = "button";
                cancelPillBtn.className = "yt-open-pill-btn";
                cancelPillBtn.style.background = "rgba(239, 68, 68, 0.18)";
                cancelPillBtn.style.borderColor = "rgba(239, 68, 68, 0.4)";
                cancelPillBtn.style.color = "#f87171";
                cancelPillBtn.title = "Cancelar este proceso en ejecución";
                cancelPillBtn.innerHTML = `<span>Cancelar</span> <span style="font-size:10px;">✕</span>`;
                cancelPillBtn.addEventListener("click", async (e) => {
                    e.stopPropagation();
                    if (!confirm(`¿Deseas cancelar el proceso de «${project.name || project.id}»?`)) return;
                    cancelPillBtn.disabled = true;
                    cancelPillBtn.textContent = "Cancelando...";
                    try {
                        const res = await fetch(`/api/cancel-task/${encodeURIComponent(project.id)}`, { method: "POST" });
                        if (res.ok) {
                            loadSavedProjects();
                        } else {
                            const err = await res.json();
                            alert(err.detail || "No se pudo cancelar.");
                            cancelPillBtn.disabled = false;
                            cancelPillBtn.innerHTML = `<span>Cancelar</span> <span style="font-size:10px;">✕</span>`;
                        }
                    } catch {
                        alert("Error de conexión al cancelar.");
                        cancelPillBtn.disabled = false;
                        cancelPillBtn.innerHTML = `<span>Cancelar</span> <span style="font-size:10px;">✕</span>`;
                    }
                });
                actionLeft.append(cancelPillBtn);
            }

            // Botón Encolar Tema
            const queueBtn = document.createElement("button");
            queueBtn.type = "button";
            queueBtn.className = "yt-card-del-btn";
            queueBtn.style.color = "#c084fc";
            queueBtn.title = "Añadir este tema a la cola de emisión de KAI";
            queueBtn.innerHTML = `📋`;
            queueBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                const topicToAdd = project.topic || (project.name || "").replace("KAI Stream: ", "");
                if (topicToAdd) {
                    window.__aetherQueue = window.__aetherQueue || [];
                    window.__aetherQueue.push(topicToAdd);
                    updateQueueBadge();
                    alert(`«${topicToAdd}» añadido a la cola de emisión (${window.__aetherQueue.length} temas en cola).`);
                }
            });

            // Botón Ver Video en Ventana Flotante
            const openBtn = document.createElement("button");
            openBtn.type = "button";
            openBtn.className = "yt-open-pill-btn";
            openBtn.title = "Reproducir este video en una ventana flotante";
            openBtn.innerHTML = `<span>Ver</span> <span style="font-size:11px;">▶</span>`;
            openBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openVideoModal(project);
            });

            // Botón Abrir en Estudio (Editar y ver Clips)
            const editStudioBtn = document.createElement("button");
            editStudioBtn.type = "button";
            editStudioBtn.className = "yt-open-pill-btn";
            editStudioBtn.style.color = "#38bdf8";
            editStudioBtn.style.borderColor = "rgba(56, 189, 248, 0.35)";
            editStudioBtn.style.background = "rgba(56, 189, 248, 0.12)";
            editStudioBtn.title = "Cargar en la mesa de edición y ver sus clips generados debajo";
            editStudioBtn.innerHTML = `<span>Mesa &amp; Clips</span> <span style="font-size:11px;">🛠️</span>`;
            editStudioBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openProject(project.id).catch((error) => console.error("Error abriendo en estudio:", error));
            });

            actionLeft.append(ytPublishBtn, openBtn, editStudioBtn, queueBtn);

            // Botón Eliminar
            const delBtn = document.createElement("button");
            delBtn.type = "button";
            delBtn.className = "yt-card-del-btn";
            delBtn.title = "Eliminar proyecto";
            delBtn.innerHTML = `✕`;
            delBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                if (!confirm(`¿Eliminar proyecto «${project.name}»? Se liberará el espacio en disco.`)) return;
                delBtn.disabled = true;
                delBtn.textContent = "…";
                try {
                    const res = await fetch(`/api/projects/${encodeURIComponent(project.id)}`, { method: "DELETE" });
                    if (res.ok) {
                        allLoadedProjects = allLoadedProjects.filter(p => p.id !== project.id);
                        renderProjectsGrid();
                        loadSavedProjects();
                    } else {
                        const errData = await res.json().catch(() => ({}));
                        alert(errData.detail || "No se pudo eliminar el proyecto.");
                        delBtn.disabled = false;
                        delBtn.innerHTML = `✕`;
                    }
                } catch (err) {
                    console.error("Error eliminando:", err);
                    alert("Error de conexión al eliminar el proyecto.");
                    delBtn.disabled = false;
                    delBtn.innerHTML = `✕`;
                }
            });

            footer.append(actionLeft, delBtn);
            body.append(footer);

            card.append(thumbWrap, body);
            card.addEventListener("click", () => {
                openVideoModal(project);
            });

            list.append(card);
        });
    }

    async function loadSavedProjects() {
        try {
            const response = await fetch("/api/projects");
            const data = await response.json();
            allLoadedProjects = Array.isArray(data.projects) ? data.projects : [];
            const card = $("savedProjectsCard");
            
            if ($("tabModeProjects")?.classList.contains("active")) {
                if (card) card.hidden = false;
            }
            renderProjectsGrid();
        } catch { /* ignorar fallo silencioso de red */ }
    }

    $("projectSearchInput")?.addEventListener("input", (e) => {
        currentProjectSearch = e.target.value.trim();
        renderProjectsGrid();
    });

    document.querySelectorAll("#projectFilterPills .subcard-pill-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#projectFilterPills .subcard-pill-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentProjectFilter = btn.dataset.filter || "all";
            renderProjectsGrid();
        });
    });

    $("refreshProjectsBtn")?.addEventListener("click", () => {
        loadSavedProjects();
    });

    const cleanupBtn = $("cleanupStorageBtn");
    if (cleanupBtn) {
        cleanupBtn.addEventListener("click", async () => {
            cleanupBtn.disabled = true;
            cleanupBtn.textContent = "Limpiando…";
            try {
                const res = await fetch("/api/cleanup", { method: "POST" });
                const data = await res.json();
                alert(`Limpieza completada:\n• Espacio liberado: ${data.freed_mb || 0} MB (${data.freed_gb || 0} GB)\n• Archivos temporales eliminados: ${data.deleted_files || 0}`);
            } catch (err) {
                alert("Error durante la limpieza: " + err.message);
            } finally {
                cleanupBtn.disabled = false;
                cleanupBtn.textContent = "🧹 Limpiar";
            }
        });
    }

    function setConnection(kind, label) {
        if (!statusBadge) return;
        statusBadge.className = `live-badge ${kind ? `is-${kind}` : ""}`.trim();
        const span = statusBadge.querySelector("span");
        if (span) {
            span.textContent = label;
        } else {
            statusBadge.textContent = label;
        }
    }

    function paintPhases(step, failedStep) {
        phaseIds.forEach((id, index) => {
            const item = $(id);
            if (!item) return; // El elemento puede no existir si la vista no está montada
            item.classList.remove("is-active", "is-complete", "is-error");
            if (step === "done") {
                item.classList.add("is-complete");
                return;
            }
            const current = stagePhase[step] ?? stagePhase[failedStep] ?? -1;
            if (step === "error" && index === (stagePhase[failedStep] ?? current)) item.classList.add("is-error");
            else if (current >= 0 && index < current) item.classList.add("is-complete");
            else if (current === index) item.classList.add("is-active");
        });
    }

    function renderActivity(events, error) {
        const list = Array.isArray(events) ? events.slice(-80) : [];
        if (error) list.push({ step: "error", message: `Error: ${error}`, at: new Date().toISOString() });
        const signature = JSON.stringify(list);
        if (signature === renderedEvents) return;
        renderedEvents = signature;
        feed.replaceChildren();
        if (!list.length) {
            feed.appendChild(emptyFeed);
            emptyFeed.hidden = false;
            $("activityCount").textContent = "0 eventos";
            const consoleFeed = $("telemetryConsoleFeed");
            const consoleFeedStudio = $("telemetryConsoleFeedStudio");
            if (consoleFeed) consoleFeed.innerHTML = '<div class="terminal-empty">Esperando el primer evento de la transmisión...</div>';
            if (consoleFeedStudio) consoleFeedStudio.innerHTML = '<div class="terminal-empty">Esperando el primer evento de la transmisión...</div>';
            const studioEvCount = $("studioEventCount");
            if (studioEvCount) studioEvCount.textContent = "0";
            return;
        }
        emptyFeed.hidden = true;
        list.forEach((event) => {
            const row = document.createElement("div");
            row.className = "activity-item";
            row.dataset.step = event.step || "";
            const marker = document.createElement("i");
            marker.className = "activity-marker";
            marker.setAttribute("aria-hidden", "true");
            const copy = document.createElement("div");
            copy.className = "activity-copy";
            const phase = document.createElement("span");
            phase.className = "activity-step";
            phase.textContent = stageLabels[event.step] || "Actividad";
            const message = document.createElement("span");
            message.textContent = event.message || "Actualización del proceso.";
            copy.append(phase, message);
            const time = document.createElement("time");
            time.dateTime = event.at || "";
            time.textContent = eventTime(event.at);
            row.append(marker, copy, time);
            feed.appendChild(row);
        });
        $("activityCount").textContent = `${list.length} ${list.length === 1 ? "evento" : "eventos"}`;
        feed.scrollTop = feed.scrollHeight;

        // ALIMENTAR EL TERMINAL DEDICADO DE MISSION CONTROL Y STUDIO SIDEBOARD
        const consoleFeed = $("telemetryConsoleFeed");
        const consoleFeedStudio = $("telemetryConsoleFeedStudio");
        const eventCountTag = $("telemetryEventCount");
        const studioEventCountTag = $("studioEventCount");
        if (eventCountTag) eventCountTag.textContent = `${list.length} eventos`;
        if (studioEventCountTag) studioEventCountTag.textContent = `${list.length}`;
        if (consoleFeed || consoleFeedStudio) {
            if (consoleFeed) consoleFeed.replaceChildren();
            if (consoleFeedStudio) consoleFeedStudio.replaceChildren();
            list.forEach((event, idx) => {
                const stepIcons = {
                    research: "🔍",
                    script: "📝",
                    voice: "🎙️",
                    avatar: "🎭",
                    render: "⚙️",
                    broll: "🎬",
                    done: "✅",
                    error: "❌",
                    cancelled: "⏹️",
                };
                const icon = stepIcons[event.step] || "⚡";
                const isHighlight = idx === list.length - 1;

                function createEntry() {
                    const entry = document.createElement("div");
                    entry.className = "terminal-log-entry" + (isHighlight ? " entry-highlight" : "");

                    const timeSpan = document.createElement("span");
                    timeSpan.className = "terminal-log-time";
                    timeSpan.textContent = `[${eventTime(event.at)}]`;

                    const iconSpan = document.createElement("span");
                    iconSpan.className = "terminal-log-icon";
                    iconSpan.textContent = icon;

                    const textSpan = document.createElement("span");
                    textSpan.className = "terminal-log-text";
                    textSpan.textContent = event.message || "Procesando...";

                    entry.append(timeSpan, iconSpan, textSpan);
                    return entry;
                }

                if (consoleFeed) consoleFeed.appendChild(createEntry());
                if (consoleFeedStudio) consoleFeedStudio.appendChild(createEntry());
            });
            if (consoleFeed) consoleFeed.scrollTop = consoleFeed.scrollHeight;
            if (consoleFeedStudio) consoleFeedStudio.scrollTop = consoleFeedStudio.scrollHeight;
        }

        // EXTRAER Y ACTUALIZAR TABLERO VISUAL DE ESCENAS Y MONITOR EN VIVO
        const scenesListEl = $("telemetryScenesList");
        const sceneRatioEl = $("telemetrySceneRatio");
        const stageImg = $("telemetryStageImg");
        const stageSceneTitle = $("telemetryStageSceneTitle");
        const stageSceneMeta = $("telemetryStageSceneMeta");

        if (scenesListEl) {
            const rawLiveScenes = (currentState && Array.isArray(currentState.live_scenes)) ? currentState.live_scenes : [];
            const sceneMatches = [];
            list.forEach((ev) => {
                const m = (ev.message || "").match(/Grabando Escena (\d+)\/(\d+):\s*([^(]+)\s*\(([^)]+)\)/i);
                if (m) {
                    sceneMatches.push({
                        idx: parseInt(m[1], 10),
                        total: parseInt(m[2], 10),
                        name: m[3].trim(),
                        type: m[4].trim(),
                    });
                }
            });

            const totalScenes = rawLiveScenes.length || (sceneMatches.length ? sceneMatches[0].total : 0);
            const currentSceneIdx = sceneMatches.length ? sceneMatches[sceneMatches.length - 1].idx : 1;

            if (totalScenes > 0) {
                if (sceneRatioEl) sceneRatioEl.textContent = `${currentSceneIdx} / ${totalScenes}`;
                const studioCountEl = $("studioScenesCount");
                if (studioCountEl) studioCountEl.textContent = totalScenes;

                // Actualizar monitor central de escena (tanto en telemetría como en el monitor de la mesa)
                const activeSceneData = rawLiveScenes[currentSceneIdx - 1] || sceneMatches.find((sc) => sc.idx === currentSceneIdx);
                const activeTaskId = currentTaskId || (currentState && currentState.id) || new URLSearchParams(window.location.search).get("project") || new URLSearchParams(window.location.search).get("task") || "";
                const activeThumbUrl = (activeSceneData && activeSceneData.thumb_url) ? activeSceneData.thumb_url : (activeTaskId ? `/storage/projects/${activeTaskId}/work/scene_${currentSceneIdx}/scene_thumb.jpg` : "/static/images/app_bg.jpg");

                if (activeSceneData) {
                    if (stageSceneTitle) stageSceneTitle.textContent = `Escena ${currentSceneIdx}: ${activeSceneData.name || "En render"}`;
                    if (stageSceneMeta) stageSceneMeta.textContent = `Encuadre: ${activeSceneData.camera || "PIP"} · ${activeSceneData.type || "Modular"}` + (activeSceneData.headline ? ` · «${activeSceneData.headline}»` : "");
                    if (stageImg) stageImg.src = activeThumbUrl;
                }

                // Sincronizar también el monitor de la mesa SOLO mientras no exista
                // un video final cargado. Antes se usaba preview.src.endsWith(".mp4"),
                // que jamás matchea la URL del preview (/api/projects/{id}/preview):
                // la telemetría volvía a ocultar el reproductor en cada tick aunque
                // el video ya estuviera disponible. El marcador dataset.source lo
                // resuelve: una vez cargado el preview del proyecto activo, el
                // monitor pertenece al reproductor.
                const stageImgStudio = $("telemetryStageImgStudio");
                const projectVideo = $("projectPreview");
                const loadedPreviewForTask = projectVideo
                    && projectVideo.dataset.source
                    && projectVideo.dataset.source.indexOf(`/api/projects/${activeTaskId}/preview`) !== -1;
                if (stageImgStudio && !loadedPreviewForTask) {
                    stageImgStudio.src = activeThumbUrl;
                    stageImgStudio.style.display = "block";
                    if (projectVideo) projectVideo.style.display = "none";
                }

                scenesListEl.replaceChildren();
                const studioScenesList = $("studioLiveScenesList");
                if (studioScenesList) studioScenesList.replaceChildren();

                for (let sNum = 1; sNum <= totalScenes; sNum++) {
                    const match = rawLiveScenes[sNum - 1] || sceneMatches.find((sc) => sc.idx === sNum);
                    const isDone = sNum < currentSceneIdx;
                    const isRendering = sNum === currentSceneIdx;

                    const item = document.createElement("div");
                    item.className = "telemetry-scene-item" + (isRendering ? " is-rendering" : isDone ? " is-done" : "");

                    // Miniatura gráfica: priorizar match.thumb_url, o reconstruir desde el ID de la tarea actual
                    const computedThumbUrl = (match && match.thumb_url) ? match.thumb_url : (activeTaskId ? `/storage/projects/${activeTaskId}/work/scene_${sNum}/scene_thumb.jpg` : "/static/images/app_bg.jpg");

                    const thumbWrap = document.createElement("div");
                    thumbWrap.className = "telemetry-scene-thumb-wrap";
                    const tImg = document.createElement("img");
                    tImg.alt = `Escena ${sNum}`;
                    tImg.src = computedThumbUrl;
                    tImg.onerror = () => { tImg.src = "/static/images/app_bg.jpg"; };
                    thumbWrap.appendChild(tImg);

                    const meta = document.createElement("div");
                    meta.className = "telemetry-scene-meta";

                    const nameEl = document.createElement("div");
                    nameEl.className = "telemetry-scene-name";
                    nameEl.textContent = `Escena ${sNum}: ` + (match ? match.name : `Escena ${sNum}`);

                    const typeEl = document.createElement("div");
                    typeEl.className = "telemetry-scene-type";
                    typeEl.textContent = match ? (match.type || "Modular") : "Modular";

                    meta.append(nameEl, typeEl);

                    const statusPill = document.createElement("span");
                    statusPill.className = "telemetry-scene-status " + (isDone ? "done" : isRendering ? "active" : "queued");
                    statusPill.textContent = isDone ? "✓ Lista" : isRendering ? "● Render" : "En cola";

                    item.append(thumbWrap, meta, statusPill);
                    
                    // Clic para inspeccionar miniatura en el monitor
                    item.addEventListener("click", () => {
                        if (stageImg) stageImg.src = computedThumbUrl;
                        if (stageImgStudio) stageImgStudio.src = computedThumbUrl;
                        if (stageSceneTitle) stageSceneTitle.textContent = `Escena ${sNum}: ` + (match ? match.name : `Escena ${sNum}`);
                        if (stageSceneMeta) stageSceneMeta.textContent = (match && match.type) ? `Tipo: ${match.type}` : "Modular";
                    });

                    scenesListEl.appendChild(item);

                    // Renderizar también en el tablero de la Mesa & Timeline
                    if (studioScenesList) {
                        const sRow = document.createElement("div");
                        sRow.className = "prism-sb-scene-row" + (isRendering ? " active" : "");
                        sRow.innerHTML = `
                            <div class="prism-sb-scene-thumb"><img src="${computedThumbUrl}" onerror="this.src='/static/images/app_bg.jpg'"></div>
                            <div class="prism-sb-scene-info">
                                <div class="prism-sb-scene-name">E${sNum}: ${match ? match.name : `Escena ${sNum}`}</div>
                                <div class="prism-sb-scene-sub">
                                    <span>${match ? (match.camera || "PIP") : "PIP"}</span>
                                    <span>${match ? (match.type || "Modular") : "Modular"}</span>
                                </div>
                            </div>
                            <span class="prism-sb-scene-status ${isDone ? "done" : isRendering ? "active" : "queued"}">
                                ${isDone ? "✓ Lista" : isRendering ? "● Grabando" : "En cola"}
                            </span>
                        `;
                        sRow.addEventListener("click", () => {
                            if (stageImgStudio) stageImgStudio.src = computedThumbUrl;
                        });
                        studioScenesList.appendChild(sRow);
                    }
                }

                // Renderizar Tarjetas Bento y Hechos en el tablero de la Mesa
                const studioCardsList = $("studioLiveCardsList");
                const studioCardsCount = $("studioCardsCount");
                const studioFactsBox = $("studioLiveFactsBox");

                if (rawLiveScenes.length > 0) {
                    const cardsWithContent = rawLiveScenes.filter(sc => sc.headline || sc.stat);
                    if (studioCardsCount) studioCardsCount.textContent = cardsWithContent.length;
                    if (studioCardsList && cardsWithContent.length > 0) {
                        studioCardsList.replaceChildren();
                        cardsWithContent.forEach(sc => {
                            const cRow = document.createElement("div");
                            cRow.className = "prism-sb-card-row";
                            cRow.innerHTML = `
                                <div style="display:flex; justify-content:space-between; align-items:center;">
                                    <span class="prism-sb-card-badge">E${sc.scene_id} · BENTO HUD</span>
                                    ${sc.stat ? `<strong class="prism-sb-card-stat">${sc.stat}</strong>` : ""}
                                </div>
                                <div class="prism-sb-card-headline">${sc.headline || "Dato Clave"}</div>
                            `;
                            studioCardsList.appendChild(cRow);
                        });
                    }
                }

                // Extraer hechos investigados de los eventos y mostrarlos en la pestaña de Hechos
                if (studioFactsBox) {
                    const researchEvents = list.filter(ev => (ev.message || "").toLowerCase().includes("investig") || (ev.message || "").toLowerCase().includes("fuente"));
                    if (researchEvents.length > 0) {
                        studioFactsBox.replaceChildren();
                        researchEvents.forEach(ev => {
                            const fRow = document.createElement("div");
                            fRow.className = "prism-sb-fact-row";
                            fRow.textContent = ev.message;
                            studioFactsBox.appendChild(fRow);
                        });
                    }
                }
            }
        }
    }

    function refreshClocks() {
        if (!currentState) return;
        const now = Date.now();
        const created = Date.parse(currentState.created_at || "");
        const stageStarted = Date.parse(currentState.step_started_at || "");
        const updated = Date.parse(currentState.updated_at || "");
        const active = !currentState.completed && !currentState.error;
        $("totalElapsedLabel").textContent = currentState.legacy_state ? "Desde reconexión" : "Tiempo total";
        $("totalElapsed").textContent = Number.isFinite(created) ? fmtDuration((now - created) / 1000) : "00:00";
        $("stageElapsed").textContent = Number.isFinite(stageStarted) ? fmtDuration((now - stageStarted) / 1000) : "00:00";
        const age = Number.isFinite(updated) ? Math.max(0, Math.floor((now - updated) / 1000)) : null;
        $("signalAge").textContent = age === null ? "—" : ageLabel(age);
        $("lastUpdateText").textContent = age === null ? "Esperando primera señal" : `Último reporte hace ${ageLabel(age)}`;

        const note = $("waitNote");
        if (active && age >= 25) {
            note.hidden = false;
            if (currentState.step === "gemini") {
                note.textContent = `Gemini aún no ha devuelto el plan de edición (${ageLabel(age)} desde la última respuesta real). Todavía no han empezado los cortes, la investigación ni el render. AetherCut cambiará de proyecto o detendrá esta etapa si se alcanza el límite de espera.`;
            } else {
                note.textContent = `Esta etapa sigue esperando una respuesta real desde hace ${ageLabel(age)}. La actividad de arriba muestra la última acción confirmada; no se están inventando avances.`;
            }
            setConnection("warning", "Sin señal reciente");
        } else if (active && connectionLost) {
            note.hidden = true;
            setConnection("warning", "Reconectando");
        } else if (active && activeStream) {
            note.hidden = true;
            setConnection("active", "Actualizando en vivo");
        } else if (!active) {
            note.hidden = true;
        }
    }

    function applyState(incomingState, taskId) {
        const state = { ...incomingState };
        state.legacy_state = !Array.isArray(state.events) || !state.updated_at;
        if (taskId !== observedTaskId) {
            observedTaskId = taskId;
            legacyStartedAt = null;
            legacyStepStartedAt = null;
            legacyUpdatedAt = null;
            legacyStep = "";
            legacyMessage = "";
            legacyEvents = [];
        }
        // Compatibilidad con tareas que empezaron antes de actualizar el servidor.
        if (!state.updated_at) {
            const now = new Date().toISOString();
            legacyStartedAt ||= now;
            const changed = state.step !== legacyStep || state.message !== legacyMessage;
            if (!legacyStepStartedAt || state.step !== legacyStep) legacyStepStartedAt = now;
            if (changed) {
                legacyUpdatedAt = now;
                legacyEvents.push({ step: state.step, progress: state.progress, message: state.message, at: now });
                legacyEvents = legacyEvents.slice(-80);
            }
            legacyStep = state.step || "";
            legacyMessage = state.message || "";
            state.created_at = legacyStartedAt;
            state.step_started_at = legacyStepStartedAt;
            state.updated_at = legacyUpdatedAt || now;
            state.events = legacyEvents;
        }
        currentState = state;
        const step = state.step || "init";
        const isError = Boolean(state.error);
        const isCancelled = Boolean(state.cancelled);
        const isDone = Boolean(state.completed) && !isCancelled;
        const cancelling = Boolean(state.cancel_requested);
        const active = !isError && !isDone && !isCancelled;
        const statusTitleEl = $("statusTitle");
        if (statusTitleEl) statusTitleEl.textContent = isError ? "No se pudo completar la edición"
            : isCancelled ? "Edición cancelada"
                : cancelling ? "Cancelando edición"
            : isDone ? "Edición terminada"
                : (stageLabels[step] || "Procesando video");
        const pipelineStatusEl = $("pipelineStatusText");
        if (pipelineStatusEl) pipelineStatusEl.textContent = isError ? state.error
            : isCancelled ? (state.message || "La edición se canceló.")
                : (state.message || "Esperando una actualización del proceso.");
        const jobFileEl = $("jobFileName");
        if (jobFileEl) jobFileEl.textContent = state.file_name || (selectedFile ? selectedFile.name : "Video en proceso");
        const percent = Math.max(0, Math.min(100, Number(state.progress || 0)));
        const pctTextEl = $("progressPctText");
        if (pctTextEl) pctTextEl.textContent = `${Math.round(percent)}%`;
        const barFill = $("progressBarFill");
        if (barFill) {
            barFill.style.width = `${percent}%`;
            barFill.parentElement.setAttribute("aria-valuenow", String(Math.round(percent)));
        }
        const donutText = $("donutPctText");
        const donutArc = $("donutProgressArc");
        const donutLabel = $("donutLabelText");
        if (donutText) donutText.textContent = `${Math.round(percent)}%`;
        if (donutArc) {
            donutArc.style.strokeDashoffset = 100 - percent;
        }
        if (donutLabel) donutLabel.textContent = isDone ? "Completado" : active ? "En emisión" : isError ? "Error" : "Listo";
        const icon = $("workIndicator");
        if (icon) {
            icon.classList.toggle("is-active", active);
            icon.classList.toggle("is-done", isDone);
            icon.classList.toggle("is-error", isError);
        }
        paintPhases(step === "cancelling" || step === "cancelled" ? state.cancelled_step : step, state.failed_step);
        // El renderizado de actividad/estudio nunca debe impedir la rama "done":
        // ahí se carga el reproductor de la Mesa (openProject). Un error aquí
        // antes dejaba el monitor sin video para siempre.
        try {
            renderActivity(state.events, state.error);
            renderStudio(state.editor, state.preview_url);
        } catch (renderError) {
            console.error("[applyState] Error renderizando estado:", renderError);
        }

        if (isCancelled) {
            setConnection("warning", "Cancelado");
            if ($("waitNote")) $("waitNote").hidden = true;
            controls.disabled = false;
            startBtn.disabled = !selectedFile;
            startBtnText.textContent = selectedFile ? "Procesar de nuevo" : "Selecciona un video";
            if (startStreamerBtn) {
                startStreamerBtn.disabled = false;
                startStreamerBtnText.textContent = "🚀 Iniciar Transmisión de KAI";
            }
            cancelBtn.hidden = true;
            localStorage.removeItem("currentTaskId");
            const url = new URL(window.location.href);
            url.searchParams.delete("task");
            window.history.replaceState({}, "", url);
        } else if (isError) {
            setConnection("error", "Requiere atención");
            if ($("waitNote")) $("waitNote").hidden = true;
            controls.disabled = false;
            startBtn.disabled = !selectedFile;
            startBtnText.textContent = selectedFile ? "Intentar de nuevo" : "Selecciona un video";
            if (startStreamerBtn) {
                startStreamerBtn.disabled = false;
                startStreamerBtnText.textContent = "🚀 Iniciar Transmisión de KAI";
            }
            cancelBtn.hidden = true;
            localStorage.removeItem("currentTaskId");
        } else if (isDone) {
            setConnection("", "Completado");
            if ($("waitNote")) $("waitNote").hidden = true;
            controls.disabled = false;
            startBtn.disabled = !selectedFile;
            startBtnText.textContent = selectedFile ? "Procesar de nuevo" : "Selecciona un video";
            if (startStreamerBtn) {
                startStreamerBtn.disabled = false;
                startStreamerBtnText.textContent = "🚀 Iniciar Transmisión de KAI";
            }
            cancelBtn.hidden = true;
            localStorage.removeItem("currentTaskId");
            const url = new URL(window.location.href);
            url.searchParams.delete("task");
            url.searchParams.set("project", taskId);
            window.history.replaceState({}, "", url);
            if (taskId) {
                openProject(taskId).catch(() => {
                    if (state.result && !didShowResults) {
                        didShowResults = true;
                        showResults(state.result, taskId);
                    }
                });
            } else if (state.result && !didShowResults) {
                didShowResults = true;
                showResults(state.result, taskId);
            }
            if ($("studioCancelBtn")) $("studioCancelBtn").style.display = "none";
        } else {
            controls.disabled = true;
            startBtn.disabled = true;
            startBtnText.textContent = "Procesando video…";
            if (startStreamerBtn) {
                startStreamerBtn.disabled = true;
                startStreamerBtnText.textContent = "Transmitiendo con KAI…";
            }
            cancelBtn.hidden = !state.cancel_supported;
            cancelBtn.disabled = cancelling;
            cancelBtn.textContent = cancelling ? "Cancelando…" : "Cancelar edición";

            const studioCancelBtn = $("studioCancelBtn");
            if (studioCancelBtn) {
                studioCancelBtn.style.display = "inline-flex";
                studioCancelBtn.disabled = cancelling;
                studioCancelBtn.textContent = cancelling ? "Cancelando…" : "✕ Cancelar Proceso";
            }
            const studioSummary = $("studioSummary");
            if (studioSummary && step !== "done") {
                studioSummary.textContent = `${stageLabels[step] || step} (${Math.round(percent)}%)`;
            }
        }

        // CONTROL VISUAL DE LA PANTALLA DEDICADA DE TELEMETRÍA (MISSION CONTROL)
        const telemetryCard = $("liveTelemetryCard");
        const streamerPane = $("streamerTabPane");
        if (telemetryCard) {
            const studioSec = $("studioSection");
            const studioCancelBtn = $("studioCancelBtn");

            if (active) {
                // Unificamos en la mesa de estudio (studioSection) para evitar tener 2 secciones gigantes duplicadas
                telemetryCard.hidden = true;
                if (studioSec) studioSec.hidden = false;
                if (streamerPane && !window._userMinimizedTelemetry) {
                    streamerPane.hidden = true;
                }
                const topicEl = $("telemetryTopicTitle");
                if (topicEl && state.file_name) {
                    topicEl.textContent = state.file_name;
                }
                const stepEl = $("telemetryCurrentStep");
                if (stepEl) {
                    stepEl.textContent = stageLabels[step] || step.toUpperCase();
                }
                const msgEl = $("telemetryCurrentMsg");
                if (msgEl) {
                    msgEl.textContent = state.message || "Procesando en vivo...";
                }
                const pctTag = $("telemetryPctTag");
                if (pctTag) {
                    pctTag.textContent = `${Math.round(percent)}%`;
                }
                const barFill = $("telemetryBarFill");
                if (barFill) {
                    barFill.style.width = `${percent}%`;
                }
                const timeEl = $("telemetryTimeElapsed");
                if (timeEl && $("totalElapsed")) {
                    timeEl.textContent = `⏱ ${$("totalElapsed").textContent}`;
                }

                // Sincronizar el Tablero de Telemetría integrado en la Mesa & Timeline
                const studioTitle = $("studioTitle");
                if (studioTitle && state.file_name) {
                    studioTitle.textContent = state.file_name;
                }
                const studioStepBadge = $("studioTelemetryStepBadge");
                if (studioStepBadge) {
                    studioStepBadge.textContent = (stageLabels[step] || step).toUpperCase();
                }
                const studioPct = $("studioTelemetryPct");
                if (studioPct) {
                    studioPct.textContent = `${Math.round(percent)}%`;
                }
                const studioBarFill = $("studioBarFill");
                if (studioBarFill) {
                    studioBarFill.style.width = `${percent}%`;
                }
                const studioMsg = $("studioTelemetryMsg");
                if (studioMsg) {
                    studioMsg.textContent = state.message || "KAI procesando en vivo...";
                }
                if (studioCancelBtn) {
                    studioCancelBtn.style.display = "inline-flex";
                }

                // Si la Mesa & Timeline no tiene pistas cargadas todavía, intentar poblar provisionalmente desde /api/projects/{taskId}/broadcast-plan
                if (!editorState && taskId) {
                    fetch(`/api/projects/${encodeURIComponent(taskId)}/broadcast-plan`).then(r => r.json()).then(bp => {
                        if (bp && bp.available && Array.isArray(bp.scenes) && bp.scenes.length > 0) {
                            const provisionalCards = [];
                            const provisionalBrolls = [];
                            let accTime = 0;
                            bp.scenes.forEach(sc => {
                                const dur = Number(sc.duration || 10);
                                if (sc.headline) {
                                    provisionalCards.push({
                                        id: `card-${sc.scene_id}`,
                                        start: accTime,
                                        duration: dur,
                                        headline: sc.headline,
                                        kind: "dato",
                                        verdict: "supported",
                                        stat_value: sc.stat || "",
                                        enabled: true
                                    });
                                }
                                provisionalBrolls.push({
                                    id: `broll-${sc.scene_id}`,
                                    start: accTime,
                                    end: accTime + dur,
                                    concept: sc.name || `Escena ${sc.scene_id}`,
                                    download_status: "COMPLETED",
                                    enabled: true
                                });
                                accTime += dur;
                            });
                            const provisionalEditor = {
                                summary: bp.title || state.file_name || "Transmisión en Emisión KAI",
                                duration: accTime,
                                cards: provisionalCards,
                                brolls: provisionalBrolls,
                                shorts: [],
                                cuts: []
                            };
                            editorState = provisionalEditor;
                            renderTimeline();
                        }
                    }).catch(() => {});
                }
            } else {
                telemetryCard.hidden = true;
                if (studioCancelBtn) {
                    studioCancelBtn.style.display = "none";
                }
                if (streamerPane) {
                    streamerPane.hidden = false;
                }
            }
        }

        refreshClocks();
    }

    function listen(taskId) {
        if (activeStream) activeStream.close();
        connectionLost = false;
        setConnection("active", "Conectando");
        activeStream = new EventSource(`/api/stream-progress/${encodeURIComponent(taskId)}`);
        activeStream.onopen = () => {
            connectionLost = false;
            setConnection("active", "Actualizando en vivo");
        };
        activeStream.onmessage = (event) => {
            let state;
            try { state = JSON.parse(event.data); }
            catch { return; }
            applyState(state, taskId);
            if (state.completed || state.error || state.cancelled) {
                activeStream.close();
                activeStream = null;
            }
        };
        activeStream.onerror = () => {
            connectionLost = true;
            setConnection("warning", "Reconectando");
            // EventSource vuelve a conectar por sí solo; se conserva el estado visible.
        };
    }

    cancelBtn.addEventListener("click", async () => {
        const targetId = observedTaskId || localStorage.getItem("currentTaskId") || new URL(window.location.href).searchParams.get("task");
        if (!targetId || cancelBtn.disabled) return;
        cancelBtn.disabled = true;
        cancelBtn.textContent = "Cancelando…";
        try {
            const response = await fetch(`/api/cancel-task/${encodeURIComponent(targetId)}`, { method: "POST" });
            let result = {};
            try { result = await response.json(); } catch { /* respuesta sin cuerpo JSON */ }
            if (!response.ok) throw new Error(result.detail || "No se pudo cancelar el proceso.");
            
            // Limpieza inmediata de UI y estado local para permitir iniciar otro video al instante
            cancelBtn.hidden = true;
            cancelBtn.disabled = false;
            cancelBtn.textContent = "Cancelar Transmisión";
            controls.disabled = false;
            if (startStreamerBtn) {
                startStreamerBtn.disabled = false;
                startStreamerBtnText.textContent = "🚀 Iniciar Transmisión de KAI";
            }
            startBtn.disabled = !selectedFile;
            $("statusTitle").textContent = "Transmisión cancelada";
            $("pipelineStatusText").textContent = "Listo para iniciar una nueva transmisión.";
            setConnection("warning", "Cancelado");
            
            localStorage.removeItem("currentTaskId");
            const url = new URL(window.location.href);
            url.searchParams.delete("task");
            window.history.replaceState({}, "", url);
            
            if (activeStream) {
                activeStream.close();
                activeStream = null;
            }
            observedTaskId = null;
        } catch (error) {
            cancelBtn.disabled = false;
            cancelBtn.textContent = "Cancelar Transmisión";
            $("pipelineStatusText").textContent = `No se pudo cancelar: ${error.message}`;
        }
    });

    function chooseFile(file) {
        if (!file) return;
        const allowed = [".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"];
        const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
        if (!allowed.includes(ext)) {
            selectedFile = null;
            fileBadge.hidden = true;
            startBtn.disabled = true;
            $("statusTitle").textContent = "Formato de video no admitido";
            $("pipelineStatusText").textContent = "Elige un archivo MP4, MOV, MKV, WEBM, AVI o M4V.";
            setConnection("error", "Revisa el archivo");
            return;
        }
        if (file.size > 2 * 1024 * 1024 * 1024) {
            selectedFile = null;
            fileBadge.hidden = true;
            startBtn.disabled = true;
            $("statusTitle").textContent = "El archivo supera el límite";
            $("pipelineStatusText").textContent = "El tamaño máximo de carga es 2 GB.";
            setConnection("error", "Revisa el tamaño");
            return;
        }
        selectedFile = file;
        fileName.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
        fileBadge.hidden = false;
        startBtn.disabled = false;
        startBtnText.textContent = "Iniciar edición";
        $("statusTitle").textContent = "Video listo para editar";
        $("pipelineStatusText").textContent = "Ajusta las opciones y comienza. El avance detallado aparecerá aquí.";
        $("jobFileName").textContent = file.name;
        $("progressPctText").textContent = "0%";
        $("progressBarFill").style.width = "0%";
        setConnection("", "Listo para iniciar");
    }

    function showResults(result, explicitTaskId) {
        results.hidden = true;
        const videoUrl = result.master_video_url || result.media_url || "";
        const taskId = explicitTaskId || observedTaskId || "";
        if (taskId) observedTaskId = taskId;
        const cleanTitle = (result.title || "KAI_Broadcast").replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "_").slice(0, 40);
        const mp4Filename = `${cleanTitle || "KAI_Broadcast"}.mp4`;
        const downloadEndpoint = taskId ? `/api/projects/${taskId}/download` : (videoUrl || "#");
        const zipEndpoint = taskId ? `/api/projects/${taskId}/materials-zip` : "#";
        
        // 1. Cambiar a modo Mesa & Timeline (studio) para ver el video completo y pistas
        switchMode("studio");

        // Reactivar y dejar listo el botón de emisión
        const startStreamerBtn = $("startStreamerBtn");
        const startStreamerBtnText = $("startStreamerBtnText");
        if (startStreamerBtn) {
            startStreamerBtn.disabled = false;
            if (startStreamerBtnText) startStreamerBtnText.textContent = "🚀 Iniciar Transmisión de KAI";
        }

        // Mostrar Banner de Éxito 바로 visible bajo la barra de progreso
        const banner = $("broadcastCompleteBanner");
        if (banner) {
            banner.style.display = "flex";
            const bannerWatchBtn = $("bannerWatchBtn");
            if (bannerWatchBtn) {
                bannerWatchBtn.onclick = () => {
                    results.hidden = true;
                    switchMode("studio");
                    const studioSec = $("studioSection");
                    if (studioSec) {
                        studioSec.hidden = false;
                        studioSec.scrollIntoView({ behavior: "smooth", block: "start" });
                    }
                    const preview = $("projectPreview");
                    if (preview) preview.play().catch(() => {});
                };
            }
            const bannerDlBtn = $("bannerDownloadBtn");
            if (bannerDlBtn) {
                bannerDlBtn.href = "#";
                bannerDlBtn.onclick = (e) => {
                    e.preventDefault();
                    const dlUrl = taskId ? `/api/projects/${taskId}/download/${encodeURIComponent(mp4Filename)}` : downloadEndpoint;
                    const a = document.createElement("a");
                    a.href = dlUrl;
                    a.download = mp4Filename;
                    document.body.appendChild(a);
                    a.click();
                    setTimeout(() => a.remove(), 1500);
                };
            }
        }

        // 2. Asegurarse absolutamente de que previewContainer esté visible y dropWrap oculto
        const previewBox = $("previewContainer");
        if (previewBox) {
            previewBox.hidden = false;
            previewBox.style.display = "block";
        }
        const dropWrap = $("copilotDropWrap");
        if (dropWrap) {
            dropWrap.hidden = true;
            dropWrap.style.display = "none";
        }

        // 3. Cargar video en el Monitor Principal superior (con Custom Studio HUD)
        const preview = $("projectPreview");
        const playUrl = taskId ? `/api/projects/${encodeURIComponent(taskId)}/preview` : videoUrl;
        if (preview && playUrl) {
            preview.hidden = false;
            preview.style.display = "block";
            preview.controls = false;
            preview.volume = 1;
            preview.muted = false;
            if (preview.src !== playUrl && !preview.src.endsWith(playUrl)) {
                preview.src = playUrl;
                preview.load();
            }
        }

        // 4. Cargar video en el Reproductor Cine Master del Apartado Exclusivo
        const masterPlayer = $("masterVideoPlayer");
        if (masterPlayer && playUrl) {
            masterPlayer.style.display = "block";
            masterPlayer.hidden = false;
            masterPlayer.controls = false;
            masterPlayer.volume = 1;
            masterPlayer.muted = false;
            if (masterPlayer.src !== playUrl && !masterPlayer.src.endsWith(playUrl)) {
                masterPlayer.src = playUrl;
                masterPlayer.load();
            }
        }

        // 5. Configurar botones de descarga con guardado directo y blob-fetch garantizando .MP4
        async function openFolder() {
            if (!taskId) return;
            try {
                const res = await fetch(`/api/projects/${taskId}/open-folder`, { method: "POST" });
                const d = await res.json();
                if (d.status === "ok") {
                    console.log("Carpeta abierta en Windows:", d.path);
                }
            } catch (err) {
                console.error("Error abriendo carpeta:", err);
            }
        }

        async function saveDirectToDownloads() {
            if (!taskId) return;
            try {
                const res = await fetch(`/api/projects/${taskId}/save-to-downloads`, { method: "POST" });
                const d = await res.json();
                if (d.status === "ok") {
                    alert(`✅ Video guardado directamente en Descargas:\n${d.path}`);
                    return;
                }
            } catch (err) {
                console.warn("Fallo guardado directo a Descargas, usando descarga de navegador:", err);
            }
            blobDownload(downloadEndpoint, mp4Filename);
        }

        function blobDownload(url, filename) {
            const cleanFile = (filename || "video.mp4").endsWith(".mp4") ? filename : `${filename}.mp4`;
            const dlUrl = taskId && url.includes("/download") ? `/api/projects/${taskId}/download/${encodeURIComponent(cleanFile)}` : url;
            // Intentar guardado directo en Windows si es proyecto activo
            if (taskId && url.includes("/download")) {
                fetch(`/api/projects/${taskId}/save-to-downloads`, { method: "POST" })
                    .then(r => r.json())
                    .then(d => {
                        if (d.status === "ok") {
                            console.log("Guardado en descargas local:", d.path);
                        }
                    })
                    .catch(() => {});
            }

            const a = document.createElement("a");
            a.href = dlUrl;
            a.download = cleanFile;
            document.body.appendChild(a);
            a.click();
            setTimeout(() => a.remove(), 1500);
        }

        const bannerFolderBtn = $("bannerFolderBtn");
        if (bannerFolderBtn) {
            bannerFolderBtn.onclick = (e) => { e.preventDefault(); openFolder(); };
        }

        const bannerDlBtn = $("bannerDownloadBtn");
        if (bannerDlBtn) {
            bannerDlBtn.href = downloadEndpoint;
            bannerDlBtn.onclick = (e) => { e.preventDefault(); saveDirectToDownloads(); };
        }

        const dlBtn = $("downloadMasterBtn");
        if (dlBtn) {
            dlBtn.href = downloadEndpoint;
            dlBtn.onclick = (e) => { e.preventDefault(); saveDirectToDownloads(); };
        }

        const dlSec = $("downloadMasterBtnSec");
        if (dlSec) {
            dlSec.href = downloadEndpoint;
            dlSec.onclick = (e) => { e.preventDefault(); saveDirectToDownloads(); };
        }

        const zipBtn = $("downloadZipBtn");
        if (zipBtn) {
            zipBtn.href = zipEndpoint;
            zipBtn.onclick = (e) => {
                e.preventDefault();
                const a = document.createElement("a");
                a.href = zipEndpoint;
                a.setAttribute("download", `${cleanTitle}_Materiales.zip`);
                document.body.appendChild(a);
                a.click();
                setTimeout(() => a.remove(), 1000);
            };
            zipBtn.hidden = !taskId;
        }

        const openFBtn = $("openFolderBtn");
        if (openFBtn) {
            openFBtn.hidden = !taskId;
            openFBtn.onclick = (e) => { e.preventDefault(); openFolder(); };
        }

        // Acciones Master integradas en el Studio de Video
        const studioDlBtn = $("studioDownloadMasterBtn");
        if (studioDlBtn) {
            studioDlBtn.href = downloadEndpoint;
            studioDlBtn.onclick = (e) => { e.preventDefault(); saveDirectToDownloads(); };
            studioDlBtn.hidden = !taskId;
        }

        const studioZipBtn = $("studioDownloadZipBtn");
        if (studioZipBtn) {
            studioZipBtn.href = zipEndpoint;
            studioZipBtn.onclick = (e) => {
                e.preventDefault();
                const a = document.createElement("a");
                a.href = zipEndpoint;
                a.setAttribute("download", `${cleanTitle}_Materiales.zip`);
                document.body.appendChild(a);
                a.click();
                setTimeout(() => a.remove(), 1000);
            };
            studioZipBtn.hidden = !taskId;
        }

        const studioFolderBtn = $("studioOpenFolderBtn");
        if (studioFolderBtn) {
            studioFolderBtn.hidden = !taskId;
            studioFolderBtn.onclick = (e) => { e.preventDefault(); openFolder(); };
        }

        // 6. Barra de descarga del monitor superior
        const monitorBar = $("monitorDownloadBar");
        if (monitorBar) {
            monitorBar.hidden = false;
            monitorBar.style.display = "flex";
        }

        // 7. Textos y métricas del Apartado Exclusivo
        if ($("resVideoTitle")) $("resVideoTitle").textContent = result.title || "Producción KAI Master";
        if ($("resVideoSub")) $("resVideoSub").textContent = `Tema: ${result.topic || ""} · Duración: ${fmtDuration(result.duration || 0)} · Formato: 1080p FHD Broadcast`;
        if ($("resScenesCount")) $("resScenesCount").textContent = (result.scenes || []).length || (result.scenes_count || 0);

        // 8. Desglose visual de escenas dirigidas
        const scenesList = $("resScenesList");
        const scenes = Array.isArray(result.scenes) ? result.scenes : [];
        if (scenesList) {
            scenesList.replaceChildren();
            const typeBadges = {
                "avatar_cam": "👤 Presentador KAI",
                "video_reaction": "🎬 Video Reacción (PIP)",
                "card_focus": "📊 Tarjeta Bento Clave",
                "chat_debate": "💬 Debate en Vivo",
                "breaking_news": "🚨 Titular Urgente"
            };
            scenes.forEach((sc, idx) => {
                const scCard = document.createElement("div");
                scCard.style.cssText = "background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:10px 12px; display:flex; flex-direction:column; gap:4px; transition:border-color 0.2s;";
                const typeLabel = typeBadges[sc.type] || sc.type;
                scCard.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong style="font-size:12px; color:#fff;">Escena ${sc.id || (idx + 1)}: ${sc.name || "Escena"}</strong>
                        <span style="font-size:10px; background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px; color:var(--accent-ivory); font-weight:600;">${sc.emotion || "normal"}</span>
                    </div>
                    <span style="font-size:11px; color:var(--text-muted);">${typeLabel}</span>
                `;
                scenesList.append(scCard);
            });
        }

        // 9. Cargar lista de materiales generados desde el servidor
        if (taskId) {
            fetch(`/api/projects/${taskId}/materials`).then(r => r.json()).then(mat => {
                const filesList = $("resFilesList");
                if (filesList && Array.isArray(mat.files) && mat.files.length) {
                    filesList.replaceChildren();
                    mat.files.forEach(f => {
                        const pill = document.createElement("a");
                        pill.className = "subcard-pill-btn";
                        pill.style.cssText = "font-size:11px; padding:5px 10px; text-decoration:none; display:inline-flex; align-items:center; gap:6px; background:rgba(255,255,255,0.04);";
                        pill.href = `/storage/projects/${taskId}/work/${f.rel_path}`;
                        pill.setAttribute("download", f.name);
                        pill.download = f.name;
                        const icon = f.ext === ".mp4" ? "🎬" : f.ext === ".mp3" ? "🎙️" : f.ext === ".srt" ? "💬" : f.ext === ".png" ? "🖼️" : f.ext === ".jpg" ? "📷" : "📄";
                        pill.textContent = `${icon} ${f.name} (${f.size_kb} KB)`;
                        filesList.append(pill);
                    });
                }
            }).catch(() => {});
        }

        // 10. Vista previa y descargas de Portada HD y Short Vertical 9:16
        const thumbCard = $("resThumbnailCard");
        const thumbImg = $("resThumbnailImg");
        const thumbBtn = $("btnDownloadThumbnail");
        const thumbUrl = result.thumbnail_url || (taskId ? `/media/${taskId}_thumbnail.jpg` : null);
        if (thumbCard && thumbUrl) {
            thumbCard.style.display = "flex";
            if (thumbImg) thumbImg.src = thumbUrl;
            if (thumbBtn) {
                thumbBtn.href = thumbUrl;
                thumbBtn.setAttribute("download", `${cleanTitle}_Portada_HD.jpg`);
            }
        }

        const shortCard = $("resShortCard");
        const shortVideo = $("resShortVideo");
        const shortBtn = $("btnDownloadShort");
        const shortUrl = result.short_video_url || (taskId ? `/media/${taskId}_short.mp4` : null);
        if (shortCard && shortUrl) {
            shortCard.style.display = "flex";
            if (shortVideo) {
                shortVideo.src = shortUrl;
                shortVideo.load();
            }
            if (shortBtn) {
                shortBtn.href = shortUrl;
                shortBtn.setAttribute("download", `${cleanTitle}_Short_9_16.mp4`);
            }
        }

        // 11. Conectar botón de Webhook y Copiar Ficha Técnica
        const btnSendWebhook = $("btnSendWebhook");
        if (btnSendWebhook && taskId) {
            btnSendWebhook.onclick = async () => {
                const whUrl = ($("webhookInputUrl")?.value || "").trim();
                const statusMsg = $("webhookStatusMsg");
                if (!whUrl) {
                    alert("Por favor ingresa la URL del Webhook (Make, Discord, Zapier, etc.)");
                    return;
                }
                btnSendWebhook.disabled = true;
                btnSendWebhook.textContent = "Enviando…";
                if (statusMsg) {
                    statusMsg.style.display = "block";
                    statusMsg.style.color = "#38bdf8";
                    statusMsg.textContent = "Despachando datos al webhook...";
                }
                try {
                    const r = await fetch(`/api/projects/${taskId}/webhook`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ webhook_url: whUrl })
                    });
                    const d = await r.json();
                    if (!r.ok) throw new Error(d.detail || "Error despachando webhook");
                    if (statusMsg) {
                        statusMsg.style.color = "#22c55e";
                        statusMsg.textContent = "✅ ¡Datos y videos enviados con éxito al Webhook!";
                    }
                } catch (err) {
                    if (statusMsg) {
                        statusMsg.style.color = "#ef4444";
                        statusMsg.textContent = `❌ ${err.message}`;
                    }
                } finally {
                    btnSendWebhook.disabled = false;
                    btnSendWebhook.textContent = "Enviar";
                }
            };
        }

        const btnCopyMeta = $("btnCopyMeta");
        if (btnCopyMeta) {
            btnCopyMeta.onclick = () => {
                const metaText = `🎬 Título: ${result.title || "KAI Broadcast"}\n` +
                    `📌 Tema: ${result.topic || ""}\n` +
                    `⏱️ Duración: ${fmtDuration(result.duration || 0)}\n` +
                    `📹 Video Master: ${window.location.origin}${downloadEndpoint}\n` +
                    (thumbUrl ? `🖼️ Portada HD: ${window.location.origin}${thumbUrl}\n` : "") +
                    (shortUrl ? `📱 Short Vertical: ${window.location.origin}${shortUrl}\n` : "");
                navigator.clipboard.writeText(metaText).then(() => {
                    alert("📋 ¡Ficha técnica copiada al portapapeles!");
                }).catch(() => {
                    prompt("Copia la ficha técnica:", metaText);
                });
            };
        }

        // Estado de Publicación Automática
        if (result.youtube_upload && result.youtube_upload.video_url) {
            if ($("topbarSaveStatus")) {
                $("topbarSaveStatus").innerHTML = `<a href="${result.youtube_upload.video_url}" target="_blank" style="color:#22c55e; text-decoration:none; font-weight:700;">🚀 PUBLICADO EN YOUTUBE</a>`;
            }
        } else if (result.auto_publish_prepared) {
            const chName = (result.auto_publish_prepared.channel && result.auto_publish_prepared.channel.name) || "Canal";
            if ($("topbarSaveStatus")) {
                $("topbarSaveStatus").innerHTML = `<span style="color:#38bdf8; font-weight:600;">🧭 Listo para ${chName}</span>`;
            }
        }

        // 12. Comprobar Cola de Transmisiones (Broadcast Queue)
        if (window.__aetherQueue && window.__aetherQueue.length > 0) {
            const nextTopic = window.__aetherQueue.shift();
            updateQueueBadge();
            const queueDelay = 3000;
            console.log(`[Queue] Próximo tema en ${queueDelay/1000}s: ${nextTopic}`);
            setTimeout(() => {
                const streamerTopic = $("streamerTopic");
                if (streamerTopic) streamerTopic.value = nextTopic;
                const streamerForm = $("streamerForm");
                if (streamerForm) {
                    console.log("[Queue] Despachando siguiente tema automáticamente...");
                    const submitEvent = new Event("submit", { cancelable: true });
                    streamerForm.dispatchEvent(submitEvent);
                }
            }, queueDelay);
        }

        // Métricas de corte y tarjetas
        if ($("statCuts")) $("statCuts").textContent = result.silences_cut_count ?? 0;
        if ($("statBRolls")) $("statBRolls").textContent = result.brolls_count ?? 0;
        if ($("statCards")) $("statCards").textContent = result.cards_shown ?? 0;
        if ($("statTimeSaved")) $("statTimeSaved").textContent = `${Number(result.time_saved_sec || 0).toFixed(1)} s`;
        renderFacts(result.cards || []);

        // En lugar del diseño viejo, mantener results oculto y sincronizar Mesa & Timeline
        results.hidden = true;
        switchMode("studio");
        if (taskId) {
            currentStudioProjectId = taskId;
            loadStudioClips(taskId);
        }
        setTimeout(() => {
            const studioSec = $("studioSection");
            if (studioSec) {
                studioSec.hidden = false;
                studioSec.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        }, 80);
    }

    $("projectPreview").addEventListener("timeupdate", () => {
        const preview = $("projectPreview");
        const cur = preview.currentTime || 0;
        const dur = preview.duration || (editorState ? editorState.duration : 0) || 1;
        $("previewCurrentTime").textContent = fmtDuration(cur);
        $("timelineCursor").value = String(cur);

        // Aguja Playhead interactiva
        const playhead = $("timelinePlayhead");
        if (playhead && dur > 0) {
            playhead.style.left = `${Math.min(100, Math.max(0, (cur / dur) * 100))}%`;
        }

        // Timecode del monitor Studio
        const hudTimecode = $("hudTimecode");
        if (hudTimecode && dur > 0) {
            hudTimecode.innerHTML = `${fmtDuration(cur)} <span>/</span> ${fmtDuration(dur)}`;
        }

        // Sincronizar escena activa en tiempo real (sideboard y clip de pista)
        if (editorState && editorState.scenes && editorState.scenes.length > 0) {
            editorState.scenes.forEach((sc) => {
                const isActive = cur >= sc.start && cur < sc.end;
                const scRow = document.querySelector(`.prism-sb-scene-row[data-scene-id="${sc.scene_id}"]`);
                if (scRow) scRow.classList.toggle("active", isActive);
                const scClip = document.querySelector(`.clip.clip-scene[data-scene-id="${sc.scene_id}"]`);
                if (scClip) scClip.classList.toggle("is-active", isActive);
                if (isActive) {
                    const recBadge = $("stageBadgeRec");
                    if (recBadge) recBadge.innerHTML = `<i></i> E${sc.scene_id}: ${sc.name || sc.title}`;
                }
            });
        }
    });

    // Botones de salto a clip/escena anterior o siguiente
    $("hudPrevBtn")?.addEventListener("click", () => {
        if (!editorState?.scenes?.length) return;
        const cur = $("projectPreview").currentTime || 0;
        const prev = [...editorState.scenes].reverse().find(s => s.start < cur - 1);
        if (prev) setPreviewTime(prev.start);
        else setPreviewTime(0);
    });
    $("hudNextBtn")?.addEventListener("click", () => {
        if (!editorState?.scenes?.length) return;
        const cur = $("projectPreview").currentTime || 0;
        const next = editorState.scenes.find(s => s.start > cur + 0.5);
        if (next) setPreviewTime(next.start);
    });

    $("timelineCursor").addEventListener("input", (event) => setPreviewTime(event.target.value));

    $("saveTimelineBtn").addEventListener("click", async () => {
        if (!observedTaskId || !editorState || !editorDirty) return;
        const button = $("saveTimelineBtn");
        button.disabled = true;
        $("editorSaveState").textContent = "Guardando cambios de edición…";
        const payload = {
            cards: (editorState.cards || []).map((card) => ({ id: card.id, enabled: card.enabled !== false, start: card.start, duration: card.duration, position: card.position || "auto", avatar_spoken_text: card.avatar_spoken_text, avatar_enabled: card.avatar_enabled !== false })),
            brolls: (editorState.brolls || []).map((broll) => ({ id: broll.id, enabled: broll.enabled !== false, start: broll.start, end: broll.end })),
        };
        try {
            const response = await fetch(`/api/projects/${encodeURIComponent(observedTaskId)}/timeline`, {
                method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "No se pudieron guardar los cambios.");
            editorState = data.editor;
            editorDirty = false;
            $("exportTimelineBtn").disabled = false;
            $("editorSaveState").textContent = data.message || "Cambios guardados en este proyecto.";
            renderTimeline(); renderInspector();
        } catch (error) {
            $("editorSaveState").textContent = `No se guardaron los cambios: ${error.message}`;
            button.disabled = false;
        }
    });

    $("exportTimelineBtn").addEventListener("click", async () => {
        if (!observedTaskId || editorDirty) return;
        const button = $("exportTimelineBtn");
        button.disabled = true;
        $("editorSaveState").textContent = "Iniciando una nueva exportación…";
        try {
            const response = await fetch(`/api/projects/${encodeURIComponent(observedTaskId)}/export`, { method: "POST" });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || "No se pudo iniciar la exportación.");
            didShowResults = false;
            listen(data.task_id);
        } catch (error) {
            $("editorSaveState").textContent = `No se pudo exportar: ${error.message}`;
            button.disabled = false;
        }
    });

    function renderFacts(cards) {
        const list = $("factsList");
        list.replaceChildren();
        $("factsWrap").hidden = !cards.length;
        const supported = cards.filter((card) => card.verdict === "supported").length;
        $("factsSummary").textContent = `${supported} de ${cards.length} confirmados`;
        const verdicts = {
            supported: ["ok", "Confirmado"],
            contradicted: ["bad", "Corregido"],
            insufficient: ["na", "Sin evidencia"],
        };
        cards.forEach((card) => {
            const [style, label] = verdicts[card.verdict] || verdicts.insufficient;
            const item = document.createElement("li");
            item.className = "fact";
            const sources = (card.sources || []).map((source) => {
                const link = /^https:\/\//i.test(source.url || "") ? source.url : "#";
                return `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(source.domain || "fuente")}</a>`;
            }).join("");
            const detail = card.verdict === "supported" ? card.body
                : card.verdict === "contradicted" ? (card.note || "Se detectó una diferencia con las fuentes consultadas.")
                : (card.note || "No se encontró evidencia suficiente.");
            const avatarHtml = card.avatar_spoken_text
                ? `<div class="avatar-voice" style="margin-top:8px; font-size:12px; color:#38bdf8; background:rgba(56,189,248,0.08); padding:6px 10px; border-radius:6px; border-left:3px solid #38bdf8; display:flex; align-items:center; gap:6px;"><span>⚡ <b>KAI Copilot:</b></span> <span>«${esc(card.avatar_spoken_text)}»</span></div>`
                : "";
            item.innerHTML = `<div class="fact-top"><b>${esc(card.headline)}</b><span class="badge ${style}">${label}${card.shown ? " · en el video" : ""}</span></div>
                <p class="claim">Afirmación (${esc(card.at_sec)} s): ${esc(card.claim)}</p>
                <p>${esc(detail)}</p>${avatarHtml}${sources ? `<div class="srcs">${sources}</div>` : ""}`;
            list.appendChild(item);
        });
    }

    dropzone?.addEventListener("click", () => fileInput?.click());
    dropzone?.addEventListener("dragover", (event) => { event.preventDefault(); dropzone.classList.add("drag-active"); });
    dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("drag-active"));
    dropzone?.addEventListener("drop", (event) => {
        event.preventDefault();
        dropzone.classList.remove("drag-active");
        chooseFile(event.dataTransfer.files?.[0]);
    });
    fileInput?.addEventListener("change", () => chooseFile(fileInput.files?.[0]));
    $("removeFileBtn")?.addEventListener("click", () => {
        selectedFile = null;
        if (fileInput) fileInput.value = "";
        if (fileBadge) fileBadge.hidden = true;
        if (startBtn) startBtn.disabled = true;
        if (startBtnText) startBtnText.textContent = "Selecciona un video";
        if ($("jobFileName")) $("jobFileName").textContent = "Sin archivo seleccionado";
        if ($("statusTitle")) $("statusTitle").textContent = "Carga un video para empezar";
        if ($("pipelineStatusText")) $("pipelineStatusText").textContent = "Aquí verás qué etapa está activa y la última acción reportada por el proceso.";
    });
    $("silenceThreshold")?.addEventListener("input", (event) => {
        if ($("silenceVal")) $("silenceVal").textContent = `${Number(event.target.value).toFixed(1)} s`;
    });

    form?.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!selectedFile) return;
        controls.disabled = true;
        startBtn.disabled = true;
        results.hidden = true;
        didShowResults = false;
        renderedEvents = "";
        feed.replaceChildren(emptyFeed);
        emptyFeed.hidden = false;
        $("totalElapsed").textContent = "00:00";
        $("stageElapsed").textContent = "00:00";
        $("signalAge").textContent = "—";
        $("waitNote").hidden = true;
        setConnection("active", "Subiendo video");
        $("statusTitle").textContent = "Subiendo el video";
        $("pipelineStatusText").textContent = "La carga se envía al servidor local; al terminar comenzará el análisis.";
        $("jobFileName").textContent = selectedFile.name;
        $("progressPctText").textContent = "5%";
        $("progressBarFill").style.width = "5%";

        const body = new FormData();
        body.append("video", selectedFile);
        body.append("silence_threshold", $("silenceThreshold").value);
        body.append("enable_broll", $("enableBRoll").checked);
        body.append("enable_cards", $("enableCards").checked);
        body.append("enable_captions", $("enableCaptions").checked);
        body.append("enable_shorts", $("enableShorts").checked);
        try {
            const data = await new Promise((resolve, reject) => {
                const request = new XMLHttpRequest();
                request.open("POST", "/api/process-video");
                request.upload.onprogress = (progress) => {
                    if (!progress.lengthComputable) return;
                    const uploadPct = progress.loaded / progress.total;
                    $("statusTitle").textContent = "Subiendo el video al servidor local";
                    $("pipelineStatusText").textContent = `${(progress.loaded / 1024 / 1024).toFixed(1)} de ${(progress.total / 1024 / 1024).toFixed(1)} MB recibidos.`;
                    $("progressPctText").textContent = `${Math.round(uploadPct * 100)}%`;
                    $("progressBarFill").style.width = `${uploadPct * 100}%`;
                };
                request.onload = () => {
                    let payload = {};
                    try { payload = JSON.parse(request.responseText); } catch { /* error de respuesta */ }
                    if (request.status >= 200 && request.status < 300) resolve(payload);
                    else reject(new Error(payload.detail || "No se pudo cargar el video."));
                };
                request.onerror = () => reject(new Error("Se perdió la conexión durante la carga."));
                request.send(body);
            });
            localStorage.setItem("currentTaskId", data.task_id);
            const curUrl = new URL(window.location.href);
            curUrl.searchParams.set("task", data.task_id);
            curUrl.searchParams.delete("project");
            window.history.replaceState({}, "", curUrl);
            listen(data.task_id);
        } catch (error) {
            controls.disabled = false;
            startBtn.disabled = false;
            startBtnText.textContent = "Intentar de nuevo";
            setConnection("error", "Error de carga");
            $("statusTitle").textContent = "No se pudo iniciar la tarea";
            $("pipelineStatusText").textContent = error.message;
        }
    });

    setInterval(refreshClocks, 1000);
    const currentUrl = new URLSearchParams(window.location.search);
    const taskFromUrl = currentUrl.get("task");
    const projectFromUrl = currentUrl.get("project");

    if (projectFromUrl) {
        localStorage.removeItem("currentTaskId");
        openProject(projectFromUrl).catch(err => {
            console.error("Error abriendo proyecto de URL:", err);
            switchMode("streamer");
        });
    } else {
        const savedTaskId = localStorage.getItem("currentTaskId") || taskFromUrl;
        if (taskFromUrl) localStorage.setItem("currentTaskId", taskFromUrl);
        if (savedTaskId) {
            controls.disabled = true;
            startBtn.disabled = true;
            $("statusTitle").textContent = "Recuperando el estado de la edición";
            $("pipelineStatusText").textContent = "Reconectando con el servidor local…";
            listen(savedTaskId);
        } else {
            switchMode("streamer");
        }
    }


    function setPhaseLabels(labels) {
        const ids = ["phase-input", "phase-analyze", "phase-cut", "phase-enrich", "phase-render"];
        ids.forEach((id, idx) => {
            const el = $(id);
            if (el && labels[idx]) {
                const span = el.querySelector("span:not(.phase-dot)");
                if (span) {
                    span.textContent = labels[idx];
                } else {
                    el.textContent = `${idx + 1}. ${labels[idx]}`;
                }
            }
        });
    }

    function switchMode(mode) {
        activeMode = mode;
        // Recordar dónde se quedó el usuario: al recargar la página vuelve aquí.
        try { localStorage.setItem("aetherLastMode", mode); } catch { /* storage bloqueado */ }
        const tabStreamer = $("tabModeStreamer");
        const tabCopilot = $("tabModeCopilot");
        const tabStudio = $("tabModeStudio");
        const tabProjects = $("tabModeProjects");
        const tabMultiAgent = $("tabModeMultiAgent");
        const dockStreamer = $("dockStreamer");
        const dockCopilot = $("dockCopilot");
        const dockStudio = $("dockStudio");
        const dockProjects = $("dockProjects");
        const heroTitle = $("heroTitle");
        const heroSubtitle = $("heroSubtitle");
        const bentoTitle = $("bentoCardTitle");
        const bentoSub = $("bentoCardSub");
        const previewBox = $("previewContainer");
        const dropWrap = $("copilotDropWrap");
        const streamerForm = $("streamerForm");
        const uploadForm = $("uploadForm");
        const studioSec = $("studioSection");
        const projectsCard = $("savedProjectsCard");
        const multiAgentSec = $("multiAgentSection");
        const radarSec = $("trendRadarSection");

        // Limpiar clases activas
        [tabStreamer, tabCopilot, tabStudio, tabProjects, tabMultiAgent, $("tabModeRadar")].forEach(t => t && t.classList.remove("active"));
        [dockStreamer, dockCopilot, dockStudio, dockProjects, $("dockRadar")].forEach(d => d && d.classList.remove("active"));
        if (studioSec) studioSec.hidden = true;
        if (projectsCard) projectsCard.hidden = true;
        if (multiAgentSec) multiAgentSec.hidden = true;
        if (radarSec) radarSec.hidden = true;
        if (results) results.hidden = true;

        const bentoPane = $("streamerTabPane");
        const trendingRow = $("trendingChipsRow");

        if (mode === "streamer") {
            if (tabStreamer) tabStreamer.classList.add("active");
            if (dockStreamer) dockStreamer.classList.add("active");
            if (trendingRow) trendingRow.hidden = false;
            if (bentoPane) bentoPane.hidden = false;
            if (studioSec) studioSec.hidden = true;
            if (results) results.hidden = true;
            if (dropWrap) {
                dropWrap.hidden = true;
                dropWrap.style.display = "none";
            }
            if (streamerForm) streamerForm.hidden = false;
            if (uploadForm) uploadForm.hidden = true;
            setPhaseLabels(["Investigar", "Guión IA", "Voz Neural", "B-Roll & Bento", "Broadcast"]);
        } else if (mode === "copilot") {
            if (tabCopilot) tabCopilot.classList.add("active");
            if (dockCopilot) dockCopilot.classList.add("active");
            if (trendingRow) trendingRow.hidden = true;
            if (bentoPane) bentoPane.hidden = false;
            if (studioSec) studioSec.hidden = true;
            if (dropWrap) { dropWrap.hidden = false; dropWrap.style.display = "block"; }
            if (streamerForm) streamerForm.hidden = true;
            if (uploadForm) uploadForm.hidden = false;
            setPhaseLabels(["Preparar", "Analizar", "Detectar pausas", "Buscar recursos", "Renderizar"]);
        } else if (mode === "studio") {
            if (tabStudio) tabStudio.classList.add("active");
            if (dockStudio) dockStudio.classList.add("active");
            if (trendingRow) trendingRow.hidden = true;
            if (bentoPane) bentoPane.hidden = true;
            if (studioSec) studioSec.hidden = false;
            if (previewBox) {
                previewBox.hidden = false;
                previewBox.style.display = "flex";
            }
            renderStudio(editorState, $("projectPreview")?.src);
            if ($("topbarSectionBadge")) $("topbarSectionBadge").textContent = "Mesa & Timeline";
            if ($("topbarSectionDesc")) $("topbarSectionDesc").textContent = "Secuenciador multicapa y edición no destructiva";
        } else if (mode === "projects") {
            if (tabProjects) tabProjects.classList.add("active");
            if (dockProjects) dockProjects.classList.add("active");
            if (heroTitle) heroTitle.textContent = "Biblioteca de Proyectos";
            if (heroSubtitle) heroSubtitle.textContent = "Historial completo de producciones transmitidas y videos editados";
            if (trendingRow) trendingRow.hidden = true;
            if (bentoPane) bentoPane.hidden = true;
            if (previewBox) previewBox.hidden = true;
            if (results) results.hidden = true;
            if (projectsCard) projectsCard.hidden = false;
            if ($("topbarSectionBadge")) $("topbarSectionBadge").textContent = "Biblioteca de Proyectos";
            if ($("topbarSectionDesc")) $("topbarSectionDesc").textContent = "Colección de emisiones finalizadas y videos guardados";
            loadSavedProjects();
        } else if (mode === "radar") {
            const tabRadar = $("tabModeRadar");
            const dockRadarBtn = $("dockRadar");
            if (tabRadar) tabRadar.classList.add("active");
            if (dockRadarBtn) dockRadarBtn.classList.add("active");
            if (heroTitle) heroTitle.textContent = "Radar de Viralidad";
            if (heroSubtitle) heroSubtitle.textContent = "Ranking viral por región y temas urgentes aún sin video, listos para replicar en español";
            if (trendingRow) trendingRow.hidden = true;
            if (bentoPane) bentoPane.hidden = true;
            if (previewBox) previewBox.hidden = true;
            if (results) results.hidden = true;
            if (radarSec) radarSec.hidden = false;
            if ($("topbarSectionBadge")) $("topbarSectionBadge").textContent = "Radar de Viralidad";
            if ($("topbarSectionDesc")) $("topbarSectionDesc").textContent = "Barrido automático cada 3 horas: qué sube, qué baja y qué emerge";
        } else if (mode === "multiagent") {
            if (tabMultiAgent) tabMultiAgent.classList.add("active");
            if (heroTitle) heroTitle.textContent = "Multi-Agent Dev Studio";
            if (heroSubtitle) heroSubtitle.textContent = "Orquestación autónoma de desarrollo con GLM-5.3, GLM-5.3-flash y Kimi-k3";
            if (trendingRow) trendingRow.hidden = true;
            if (bentoPane) bentoPane.hidden = true;
            if (previewBox) previewBox.hidden = true;
            if (results) results.hidden = true;
            if (multiAgentSec) multiAgentSec.hidden = false;
            if ($("topbarSectionBadge")) $("topbarSectionBadge").textContent = "Dev Studio";
            if ($("topbarSectionDesc")) $("topbarSectionDesc").textContent = "Agentes autónomos de desarrollo";
        }
        if (mode === "streamer") {
            if ($("topbarSectionBadge")) $("topbarSectionBadge").textContent = "KAI Streamer";
            if ($("topbarSectionDesc")) $("topbarSectionDesc").textContent = "Transmisión Autónoma & Edición Neural";
        }
    }

    // Navegación por tabs y por dock flotante
    $("tabModeStreamer")?.addEventListener("click", () => switchMode("streamer"));
    $("tabModeCopilot")?.addEventListener("click", () => switchMode("copilot"));
    $("tabModeStudio")?.addEventListener("click", () => switchMode("studio"));
    $("tabModeProjects")?.addEventListener("click", () => switchMode("projects"));
    $("tabModeRadar")?.addEventListener("click", () => switchMode("radar"));
    $("tabModeMultiAgent")?.addEventListener("click", () => switchMode("multiagent"));

    // Dictado por voz (Micro) para el requerimiento multi-agente
    let maSpeechRecognition = null;
    let isRecordingMaVoice = false;

    $("btnMicMultiAgent")?.addEventListener("click", () => {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        const micBtn = $("btnMicMultiAgent");
        const micText = $("maMicText");
        const micIcon = $("maMicIcon");
        const voiceStatus = $("maVoiceStatus");
        const reqInput = $("maRequirementInput");

        if (!SpeechRec) {
            alert("Tu navegador no soporta Web Speech Recognition API de manera nativa. Usa Chrome o Edge para hablarle directamente.");
            return;
        }

        if (isRecordingMaVoice) {
            if (maSpeechRecognition) maSpeechRecognition.stop();
            return;
        }

        try {
            maSpeechRecognition = new SpeechRec();
            maSpeechRecognition.lang = "es-ES";
            maSpeechRecognition.continuous = true;
            maSpeechRecognition.interimResults = true;

            maSpeechRecognition.onstart = () => {
                isRecordingMaVoice = true;
                if (micBtn) {
                    micBtn.style.background = "rgba(239,68,68,0.2)";
                    micBtn.style.borderColor = "rgba(239,68,68,0.5)";
                    micBtn.style.color = "#ef4444";
                }
                if (micText) micText.textContent = "Detener Micro";
                if (micIcon) micIcon.textContent = "⏹️";
                if (voiceStatus) {
                    voiceStatus.textContent = "🎙️ Escuchando... habla tu requerimiento";
                    voiceStatus.style.display = "inline";
                }
            };

            maSpeechRecognition.onresult = (evt) => {
                let fullTranscript = "";
                for (let i = 0; i < evt.results.length; ++i) {
                    fullTranscript += evt.results[i][0].transcript;
                }
                if (reqInput) {
                    reqInput.value = fullTranscript;
                }
            };

            maSpeechRecognition.onerror = (err) => {
                console.warn("Speech recognition error:", err);
                if (voiceStatus) voiceStatus.textContent = `Error mic: ${err.error || "desconocido"}`;
            };

            maSpeechRecognition.onend = () => {
                isRecordingMaVoice = false;
                if (micBtn) {
                    micBtn.style.background = "rgba(56,189,248,0.1)";
                    micBtn.style.borderColor = "rgba(56,189,248,0.3)";
                    micBtn.style.color = "#38bdf8";
                }
                if (micText) micText.textContent = "Hablar por Micro";
                if (micIcon) micIcon.textContent = "🎙️";
                if (voiceStatus) {
                    voiceStatus.textContent = "✓ Voz capturada";
                    setTimeout(() => { if (voiceStatus) voiceStatus.style.display = "none"; }, 3000);
                }
            };

            maSpeechRecognition.start();
        } catch (e) {
            console.error(e);
            alert("No se pudo iniciar el micrófono: " + e.message);
        }
    });

    // Manejo de Modo de Auditoría (Análisis vs Administrador)
    let currentAuditMode = "analysis";
    const btnAnalysis = $("btnModeAnalysis");
    const btnAdmin = $("btnModeAdmin");
    const auditorBadge = $("agModeAuditorBadge");

    btnAnalysis?.addEventListener("click", () => {
        currentAuditMode = "analysis";
        btnAnalysis.classList.add("active");
        btnAdmin?.classList.remove("active");
        if (auditorBadge) {
            auditorBadge.textContent = "Modo Análisis";
            auditorBadge.style.color = "#38bdf8";
            auditorBadge.style.background = "rgba(56,189,248,0.15)";
        }
    });

    btnAdmin?.addEventListener("click", () => {
        currentAuditMode = "admin";
        btnAdmin.classList.add("active");
        btnAnalysis?.classList.remove("active");
        if (auditorBadge) {
            auditorBadge.textContent = "Modo Administrador";
            auditorBadge.style.color = "#ef4444";
            auditorBadge.style.background = "rgba(239,68,68,0.15)";
        }
    });

    // Event handler para iniciar desarrollo multiagente
    $("btnStartMultiAgent")?.addEventListener("click", async () => {
        const reqInput = $("maRequirementInput");
        const statusTxt = $("maStatusText");
        const monitor = $("maMonitorContainer");
        const logsFeed = $("maLogsFeed");
        const pctEl = $("maProgressPercent");
        const barEl = $("maProgressBar");

        const text = (reqInput?.value || "").trim();
        if (!text) {
            alert("Por favor ingresa un requerimiento o módulo a desarrollar.");
            return;
        }

        statusTxt.textContent = `Iniciando orquestación con GLM-5.3 (${currentAuditMode === "analysis" ? "Modo Análisis" : "Modo Administrador"})...`;
        monitor.style.display = "block";
        logsFeed.innerHTML = "";
        pctEl.textContent = "5%";
        barEl.style.width = "5%";

        try {
            const resp = await fetch("/api/multiagent/run", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ requirement: text, audit_mode: currentAuditMode })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.detail || "Error iniciando sesión");

            const sessionId = data.session_id;
            statusTxt.textContent = `Sesión activa: ${sessionId}`;

            // Polling en vivo del estado de los 3 agentes
            const pollTimer = setInterval(async () => {
                try {
                    const stResp = await fetch(`/api/multiagent/status/${sessionId}`);
                    if (!stResp.ok) return;
                    const st = await stResp.json();

                    statusTxt.textContent = st.message;
                    pctEl.textContent = `${st.progress}%`;
                    barEl.style.width = `${st.progress}%`;

                    // Renderizar logs
                    if (st.logs && st.logs.length) {
                        logsFeed.innerHTML = st.logs.map(l => 
                            `<div style="padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.05); color:#cbd5e1;">` +
                            `<span style="color:#38bdf8;">[${l.pct}%]</span> ${l.msg}</div>`
                        ).join("");
                        logsFeed.scrollTop = logsFeed.scrollHeight;
                    }

                    // Actualizar las tarjetas individuales y razonamiento en vivo de cada modelo
                    if (st.agents) {
                        const agMap = [
                            { key: "planner", actId: "agActionPlanner", rzId: "agReasoningPlanner", tagId: "agTagPlanner", color: "#10b981" },
                            { key: "implementer", actId: "agActionImplementer", rzId: "agReasoningImplementer", tagId: "agTagImplementer", color: "#38bdf8" },
                            { key: "auditor", actId: "agActionAuditor", rzId: "agReasoningAuditor", tagId: "agTagAuditor", color: "#f59e0b" },
                        ];
                        agMap.forEach(item => {
                            const info = st.agents[item.key];
                            if (!info) return;
                            const actEl = $(item.actId);
                            const rzEl = $(item.rzId);
                            const tagEl = $(item.tagId);
                            if (actEl && info.action) actEl.textContent = info.action;
                            if (rzEl && info.reasoning) {
                                rzEl.textContent = info.reasoning;
                                rzEl.scrollTop = rzEl.scrollHeight;
                            }
                            if (tagEl) {
                                tagEl.textContent = info.status || "Activo";
                                tagEl.style.color = info.status === "Activo" ? item.color : "#64748b";
                            }
                        });
                    }

                    if (st.status === "done" || st.status === "error") {
                        clearInterval(pollTimer);
                        if (st.status === "done") {
                            statusTxt.innerHTML = `<span style="color:#10b981; font-weight:700;">✓ Proyecto completado y auditado</span>`;
                            if (st.result && st.result.report_markdown) {
                                logsFeed.innerHTML += `<div style="margin-top:12px; padding:10px; background:rgba(16,185,129,0.1); border:1px solid rgba(16,185,129,0.3); border-radius:8px; color:#fff;">` +
                                    `<strong>Informe Final:</strong><br><pre style="white-space:pre-wrap; margin-top:6px;">${st.result.report_markdown.substring(0, 500)}...</pre></div>`;
                            }
                        } else {
                            statusTxt.innerHTML = `<span style="color:#ef4444; font-weight:700;">❌ Error: ${st.message}</span>`;
                        }
                    }
                } catch (_e) {}
            }, 2500);

        } catch (err) {
            statusTxt.textContent = `Fallo: ${err.message}`;
        }
    });

    $("dockStreamer")?.addEventListener("click", () => switchMode("streamer"));
    $("dockCopilot")?.addEventListener("click", () => switchMode("copilot"));
    $("dockStudio")?.addEventListener("click", () => switchMode("studio"));
    $("dockProjects")?.addEventListener("click", () => switchMode("projects"));
    $("dockRadar")?.addEventListener("click", () => switchMode("radar"));

    // Pills de formato 16:9 vs 9:16 (Compatible con .kai-pill-btn y .subcard-pill-btn)
    document.querySelectorAll("#formatPillsWrap button").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#formatPillsWrap button").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const fmt = btn.dataset.fmt;
            if ($("streamerFormat")) $("streamerFormat").value = fmt;
            if ($("readoutFormat")) $("readoutFormat").textContent = fmt === "9:16" ? "9:16 Short" : "16:9 FHD";
            if ($("heroResolutionVal")) $("heroResolutionVal").innerHTML = fmt === "9:16" ? "9:16<sup>Vertical</sup>" : "1080p<sup>FHD</sup>";
        });
    });

    // Sincronización del selector desplegable de duración
    $("streamerDuration")?.addEventListener("change", (e) => {
        const min = Math.round(parseInt(e.target.value, 10) / 60);
        if ($("readoutDuration")) $("readoutDuration").textContent = `${min} min`;
    });

    // Pills de Tonalidad & Estilo (soporte multi-selección interactiva)
    document.querySelectorAll("#stylePillsWrap button").forEach(btn => {
        btn.addEventListener("click", (e) => {
            btn.classList.toggle("active");
            // Asegurar que al menos uno esté seleccionado
            const activeBtns = Array.from(document.querySelectorAll("#stylePillsWrap button.active"));
            if (activeBtns.length === 0) {
                btn.classList.add("active");
                activeBtns.push(btn);
            }
            const selectedStyles = activeBtns.map(b => b.dataset.style).filter(Boolean);
            const combinedVal = selectedStyles.join(",");
            const styleSelect = $("streamerStyle");
            if (styleSelect) {
                let opt = Array.from(styleSelect.options).find(o => o.value === combinedVal);
                if (!opt) {
                    opt = new Option(combinedVal, combinedVal, true, true);
                    styleSelect.add(opt);
                }
                styleSelect.value = combinedVal;
            }
        });
    });

    // Selector de Estilos de Subtítulos (.kai-sub-card)
    document.querySelectorAll("#subStylesWrap .kai-sub-card").forEach(card => {
        card.addEventListener("click", () => {
            document.querySelectorAll("#subStylesWrap .kai-sub-card").forEach(c => c.classList.remove("active"));
            card.classList.add("active");
        });
    });

    // =========================================================================
    // CONTROLES DE PRODUCCIÓN PROFESIONAL
    // =========================================================================

    // Pills de Color Grading (exclusivo: solo uno activo a la vez)
    document.querySelectorAll("#colorGradePillsWrap button").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#colorGradePillsWrap button").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            if ($("kaiColorGrade")) $("kaiColorGrade").value = btn.dataset.grade;
        });
    });

    // Pills de FPS (exclusivo)
    document.querySelectorAll("#fpsPillsWrap button").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("#fpsPillsWrap button").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            if ($("kaiVideoFps")) $("kaiVideoFps").value = btn.dataset.fps;
        });
    });

    // Slider de volumen BGM con label reactivo
    $("kaiBgmVolume")?.addEventListener("input", (e) => {
        const pct = Math.round(parseFloat(e.target.value) * 100);
        if ($("bgmVolLabel")) $("bgmVolLabel").textContent = pct === 0 ? "🔇 Silenciado" : `${pct}%`;
    });

    // Slider CRF con label descriptivo reactivo
    $("kaiCrfQuality")?.addEventListener("input", (e) => {
        const crf = parseInt(e.target.value, 10);
        let lbl = "";
        if (crf <= 15) lbl = "Máxima (archivo grande)";
        else if (crf <= 18) lbl = "Alta";
        else if (crf <= 21) lbl = "Buena";
        else if (crf <= 24) lbl = "Media";
        else lbl = "Comprimida";
        if ($("crfLabel")) $("crfLabel").textContent = `${crf} — ${lbl}`;
    });

    // Reproductor Inline rápido de audio para escuchar voces en el compositor
    const btnInlineVoicePreview = $("btnInlineVoicePreview");
    if (btnInlineVoicePreview) {
        btnInlineVoicePreview.addEventListener("click", async () => {
            const voice = $("streamerVoice")?.value || "es-MX-JorgeNeural";
            const sampleText = "¡Hola! Soy KAI. Esta es una muestra de audio para tu video. El ritmo, la dicción y la entonación se adaptarán perfectamente a tu contenido.";
            const audioEl = $("inlineVoiceAudioPlayer");
            const wrapEl = $("inlineVoiceAudioPlayerWrap");
            const statusEl = $("inlineVoiceStatus");
            const iconEl = $("btnInlineVoicePreviewIcon");

            btnInlineVoicePreview.disabled = true;
            if (iconEl) iconEl.textContent = "⏳";
            if (wrapEl) wrapEl.style.display = "block";
            if (statusEl) statusEl.textContent = "Sintetizando muestra de voz...";

            try {
                const resp = await fetch("/api/tts-preview", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ voice, text: sampleText })
                });
                if (!resp.ok) throw new Error("Error generando audio.");
                const blob = await resp.blob();
                const url = URL.createObjectURL(blob);
                if (audioEl) {
                    audioEl.src = url;
                    audioEl.play().catch(() => {});
                }
                if (statusEl) statusEl.textContent = `✓ Reproduciendo muestra de voz: ${voice}`;
            } catch (err) {
                if (statusEl) statusEl.textContent = "No se pudo generar la muestra de voz.";
            } finally {
                btnInlineVoicePreview.disabled = false;
                if (iconEl) iconEl.textContent = "▶";
            }
        });
    }

    // Botón desplegable de Ajustes Creativos & Tonalidad
    const btnToggleSettings = $("btnToggleCreativeSettings");
    const settingsPanel = $("creativeSettingsPanel");
    const settingsChevron = $("creativeSettingsChevron");
    if (btnToggleSettings && settingsPanel) {
        btnToggleSettings.addEventListener("click", () => {
            const isHidden = settingsPanel.style.display === "none";
            settingsPanel.style.display = isHidden ? "block" : "none";
            btnToggleSettings.classList.toggle("active", isHidden);
            if (settingsChevron) {
                settingsChevron.textContent = isHidden ? "▴" : "▾";
            }
        });
    }

    $("btnCloseAudioPreview")?.addEventListener("click", () => {
        const wrapEl = $("inlineVoiceAudioPlayerWrap");
        const audioEl = $("inlineVoiceAudioPlayer");
        if (audioEl) audioEl.pause();
        if (wrapEl) wrapEl.style.display = "none";
    });

    // Botón directo para el Laboratorio de Voces
    $("btnComposerVoiceTester")?.addEventListener("click", () => {
        $("btnOpenVoiceTester")?.click();
    });

    // Chips dinámicos de tendencias web reales
    async function loadTrendingTopics() {
        const row = $("trendingChipsRow");
        if (!row) return;
        try {
            const resp = await fetch("/api/trending-topics");
            if (!resp.ok) return;
            const data = await resp.json();
            const topics = data.topics || [];
            if (!topics.length) return;

            // Conservar etiqueta inicial y botón de refresh
            row.innerHTML = `<span style="font-size:11px; font-weight:700; color:var(--text-muted); display:inline-flex; align-items:center; gap:4px; margin-right:4px;">🔥 Tendencias Web:</span>`;
            
            const fallbackEmojis = ["⚛️", "🚀", "🧠", "⚡", "🔭", "🔋", "🧬", "🌐"];
            topics.slice(0, 7).forEach((item, i) => {
                const titleText = (typeof item === "object" && item.title) ? item.title : String(item);
                const emoji = (typeof item === "object" && item.emoji) ? item.emoji : fallbackEmojis[i % fallbackEmojis.length];
                
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "filter-chip chip-trend-btn";
                btn.dataset.topic = titleText;
                
                // Título abreviado estético para el chip
                const shortLabel = titleText.length > 28 ? (titleText.slice(0, 26) + "…") : titleText;
                btn.textContent = `${emoji} ${shortLabel}`;
                btn.title = titleText;
                btn.addEventListener("click", () => {
                    document.querySelectorAll("#trendingChipsRow .filter-chip").forEach(c => c.classList.remove("active"));
                    btn.classList.add("active");
                    const input = $("streamerTopic");
                    if (input) {
                        input.value = titleText;
                        input.focus();
                        if ($("readoutTopicShort")) $("readoutTopicShort").textContent = titleText.slice(0, 18) + "…";
                    }
                });
                row.appendChild(btn);
            });

            // Botón de recargar tendencias con feedback visual
            const refreshBtn = document.createElement("button");
            refreshBtn.type = "button";
            refreshBtn.className = "filter-chip filter-chip-add";
            refreshBtn.title = "Actualizar tendencias web con nuevos temas, noticias y descubrimientos";
            refreshBtn.textContent = "↻";
            refreshBtn.addEventListener("click", async (e) => {
                e.preventDefault();
                refreshBtn.style.transform = "rotate(360deg)";
                refreshBtn.style.transition = "transform 0.4s ease";
                await loadTrendingTopics();
            });
            row.appendChild(refreshBtn);
        } catch (err) {
            console.log("[Trending] Error cargando tendencias:", err);
        }
    }

    // Inicializar tendencias al arrancar
    loadTrendingTopics();
    $("refreshTrendingBtn")?.addEventListener("click", (e) => {
        e.preventDefault();
        loadTrendingTopics();
    });

    // Sincronizar topic input con readout en vivo
    $("streamerTopic")?.addEventListener("input", (e) => {
        const val = e.target.value.trim();
        if ($("readoutTopicShort")) {
            $("readoutTopicShort").textContent = val ? (val.slice(0, 16) + "…") : "Tema Libre";
        }
    });

    // Sincronizar selector de voz con readout
    $("streamerVoice")?.addEventListener("change", (e) => {
        const sel = e.target;
        const text = sel.options[sel.selectedIndex]?.text || "Álvaro Neural";
        const cleanName = text.replace(/^[🎙️\s]+/, "").split("(")[0].trim() + " Neural";
        if ($("readoutVoiceName")) {
            $("readoutVoiceName").textContent = cleanName;
        }
    });

    // Configuración interactiva de RTMP en Vivo (YouTube Live, Twitch, Kick, Personalizado)
    const livePlatform = $("streamerLivePlatform");
    const streamKey = $("streamerStreamKey");
    const customRtmp = $("streamerCustomRtmp");
    if (livePlatform && streamKey && customRtmp) {
        livePlatform.addEventListener("change", () => {
            const val = livePlatform.value;
            if (val === "none") {
                streamKey.style.display = "none";
                customRtmp.style.display = "none";
            } else if (val === "custom") {
                streamKey.style.display = "none";
                customRtmp.style.display = "block";
            } else {
                streamKey.style.display = "block";
                customRtmp.style.display = "none";
                if (val === "youtube") {
                    streamKey.placeholder = "Clave de emisión de YouTube Live (xxxx-xxxx-xxxx-xxxx)";
                } else if (val === "twitch") {
                    streamKey.placeholder = "Clave de emisión de Twitch (live_...)";
                } else if (val === "kick") {
                    streamKey.placeholder = "Clave de emisión de Kick (sk_...)";
                }
            }
        });
    }

    // Toggle para cajón de opciones avanzadas (organizado y expandible según solicitud)
    const toggleDrawerBtn = $("toggleAdvancedDrawer");
    const drawer = $("advancedDrawer");
    if (toggleDrawerBtn && drawer) {
        toggleDrawerBtn.addEventListener("click", () => {
            drawer.hidden = !drawer.hidden;
            toggleDrawerBtn.classList.toggle("expanded", !drawer.hidden);
        });
    }

    // Botón para pantalla completa en la esquina inferior derecha
    $("fullscreenExpandBtn")?.addEventListener("click", () => {
        const masterPlayer = $("masterVideoPlayer");
        const preview = $("projectPreview");
        const targetVideo = (masterPlayer && !$("resultsSection").hidden && masterPlayer.src) 
            ? masterPlayer 
            : (preview && preview.src ? preview : ($("mainStudioWindow") || document.documentElement));
            
        if (!document.fullscreenElement) {
            targetVideo.requestFullscreen?.().catch(() => {
                document.documentElement.requestFullscreen?.().catch(() => {});
            });
        } else {
            document.exitFullscreen?.().catch(() => {});
        }
    });

    // Control de la vista dedicada de telemetría (Mission Control)
    window._userMinimizedTelemetry = false;
    const telemetryMinimizeBtn = $("telemetryMinimizeBtn");
    if (telemetryMinimizeBtn) {
        telemetryMinimizeBtn.addEventListener("click", () => {
            window._userMinimizedTelemetry = !window._userMinimizedTelemetry;
            const streamerPane = $("streamerTabPane");
            if (streamerPane) streamerPane.hidden = !window._userMinimizedTelemetry ? true : false;
            telemetryMinimizeBtn.textContent = window._userMinimizedTelemetry 
                ? "↗ Expandir Mission Control" 
                : "↙ Minimizar a Segundo Plano";
        });
    }

    const telemetryCancelBtn = $("telemetryCancelBtn");
    if (telemetryCancelBtn) {
        telemetryCancelBtn.addEventListener("click", () => {
            const cancelBtn = $("cancelTaskBtn");
            if (cancelBtn) cancelBtn.click();
        });
    }

    const studioCancelBtn = $("studioCancelBtn");
    if (studioCancelBtn) {
        studioCancelBtn.addEventListener("click", () => {
            const cancelBtn = $("cancelTaskBtn");
            if (cancelBtn) cancelBtn.click();
        });
    }

    // Manejo de Cola de Emisiones (Queue)
    window.__aetherQueue = window.__aetherQueue || [];
    function updateQueueBadge() {
        const count = (window.__aetherQueue || []).length;
        const badge = $("queueBadgeInfo");
        if (badge) {
            if (count > 0) {
                badge.style.display = "block";
                badge.textContent = `📋 ${count} tema(s) restante(s) en la cola automática.`;
            } else {
                badge.style.display = "none";
            }
        }
        const studioBadge = $("studioQueueBadge");
        if (studioBadge) {
            if (count > 0) {
                studioBadge.style.display = "inline-flex";
                studioBadge.textContent = `📋 Cola: ${count}`;
            } else {
                studioBadge.style.display = "none";
            }
        }
    }

    const studioQueueBadge = $("studioQueueBadge");
    if (studioQueueBadge) {
        studioQueueBadge.addEventListener("click", () => {
            const currentList = (window.__aetherQueue || []).join("\n• ");
            const promptText = (window.__aetherQueue && window.__aetherQueue.length > 0)
                ? `Temas actualmente en cola:\n• ${currentList}\n\nIngresa un nuevo tema para añadirlo a la cola (o cancela para salir):`
                : "La cola está vacía.\n\nIngresa un tema para añadirlo a la cola automática:";
            const newTopic = prompt(promptText);
            if (newTopic && newTopic.trim()) {
                window.__aetherQueue.push(newTopic.trim());
                updateQueueBadge();
                alert(`«${newTopic.trim()}» añadido a la cola de emisión (${window.__aetherQueue.length} en espera).`);
            }
        });
    }

    const btnToggleQueue = $("btnToggleQueue");
    const queueInputWrap = $("queueInputWrap");
    if (btnToggleQueue && queueInputWrap) {
        btnToggleQueue.addEventListener("click", () => {
            const isHidden = queueInputWrap.style.display === "none";
            queueInputWrap.style.display = isHidden ? "block" : "none";
            btnToggleQueue.textContent = isHidden ? "— Ocultar Cola" : "+ Modo Cola de Temas";
        });
    }

    if (streamerForm) {
        streamerForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const topic = ($("streamerTopic")?.value || "").trim();
            if (!topic) {
                alert("Por favor escribe o selecciona un tema para la transmisión de KAI.");
                $("streamerTopic")?.focus();
                return;
            }

            startStreamerBtn.disabled = true;
            startStreamerBtnText.textContent = "Iniciando transmisión…";
            if (results) results.hidden = true;
            didShowResults = false;
            renderedEvents = "";
            if (feed && emptyFeed) {
                feed.replaceChildren(emptyFeed);
                emptyFeed.hidden = false;
            }
            if ($("totalElapsed")) $("totalElapsed").textContent = "00:00";
            if ($("stageElapsed")) $("stageElapsed").textContent = "00:00";
            if ($("signalAge")) $("signalAge").textContent = "—";
            if ($("waitNote")) $("waitNote").hidden = true;
            setConnection("active", "Iniciando KAI Streamer");
            if ($("statusTitle")) $("statusTitle").textContent = `Investigando «${topic}»`;
            if ($("pipelineStatusText")) $("pipelineStatusText").textContent = "KAI está buscando fuentes web reales para redactar el guión.";
            if ($("jobFileName")) $("jobFileName").textContent = `KAI Live: ${topic.slice(0, 35)}`;
            if ($("progressPctText")) $("progressPctText").textContent = "10%";
            if ($("progressBarFill")) $("progressBarFill").style.width = "10%";
            if ($("donutPctText")) $("donutPctText").textContent = "10%";
            if ($("donutProgressArc")) $("donutProgressArc").style.strokeDashoffset = 90;
            if ($("donutLabelText")) $("donutLabelText").textContent = "Investigando";

            // Leer temas adicionales en cola si existen y no están ya cargados
            if (!window.__aetherQueue || window.__aetherQueue.length === 0) {
                const rawQueue = ($("streamerQueueTopics")?.value || "").trim();
                if (rawQueue) {
                    window.__aetherQueue = rawQueue
                        .split("\n")
                        .map(t => t.trim())
                        .filter(t => t.length > 2);
                    if ($("streamerQueueTopics")) $("streamerQueueTopics").value = "";
                }
            }
            updateQueueBadge();

            // Obtener RTMP si está configurado para transmisión directa
            const platform = $("streamerLivePlatform")?.value || "none";
            let rtmpUrl = null;
            if (platform === "youtube") {
                const key = $("streamerStreamKey")?.value?.trim();
                if (key) rtmpUrl = `rtmp://a.rtmp.youtube.com/live2/${key}`;
            } else if (platform === "twitch") {
                const key = $("streamerStreamKey")?.value?.trim();
                if (key) rtmpUrl = `rtmp://live.twitch.tv/app/${key}`;
            } else if (platform === "kick") {
                const key = $("streamerStreamKey")?.value?.trim();
                if (key) rtmpUrl = `rtmps://fa723fc1b171.global-contribute.live-video.net:443/app/${key}`;
            } else if (platform === "custom") {
                const custom = $("streamerCustomRtmp")?.value?.trim();
                if (custom) rtmpUrl = custom;
            }

            // Opciones creativas del nuevo compositor KAI
            const visualModeRadio = document.querySelector('input[name="kaiVisualModeRadio"]:checked');
            const visualMode = visualModeRadio ? visualModeRadio.value : "mixed";
            const subActiveCard = document.querySelector("#subStylesWrap .kai-sub-card.active");
            const subStyle = subActiveCard ? subActiveCard.dataset.sub : "classic";
            const subsEnabled = $("kaiToggleSubs") ? $("kaiToggleSubs").checked : true;
            const enableBroll = $("kaiToggleBRoll") ? $("kaiToggleBRoll").checked : true;
            const enableCards = $("kaiToggleBentoCards") ? $("kaiToggleBentoCards").checked : true;
            const flashAudit = $("kaiToggleFlashAudit") ? $("kaiToggleFlashAudit").checked : true;

            // Parámetros de producción profesional
            const colorGrade = $("kaiColorGrade")?.value || "cinema";
            const videoFps = parseInt($("kaiVideoFps")?.value || "30", 10);
            const bgmVolume = parseFloat($("kaiBgmVolume")?.value || "0.12");
            const bgmTrack = $("kaiBgmTrack")?.value || "default";
            const audioNormalize = $("kaiAudioNormalize") ? $("kaiAudioNormalize").checked : true;
            const outroEnabled = $("kaiOutroEnabled") ? $("kaiOutroEnabled").checked : true;
            const crfQuality = parseInt($("kaiCrfQuality")?.value || "18", 10);

            const payload = {
                topic: topic,
                style: $("streamerStyle")?.value || "divulgacion",
                duration_sec: parseInt($("streamerDuration")?.value || "300", 10),
                aspect_ratio: $("streamerFormat")?.value || "9:16",
                card_theme: $("streamerCardTheme")?.value || "dark",
                voice: $("streamerVoice")?.value || "es-MX-JorgeNeural",
                rtmp_url: rtmpUrl,
                // Modo análisis de caso: video concreto que KAI examina (fotogramas reales)
                video_url: ($("streamerCaseUrl")?.value || "").trim(),
                sub_style: subStyle,
                subs_enabled: subsEnabled,
                visual_mode: visualMode,
                enable_broll: enableBroll,
                enable_cards: enableCards,
                flash_audit: flashAudit,
                // Parámetros profesionales
                color_grade: colorGrade,
                fps: videoFps,
                bgm_volume: bgmVolume,
                bgm_track: bgmTrack,
                audio_normalize: audioNormalize,
                outro_enabled: outroEnabled,
                crf: crfQuality,
                auto_publish: $("kaiAutoPublish") ? $("kaiAutoPublish").checked : false,
            };

            try {
                const response = await fetch("/api/streamer/create", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail || "No se pudo iniciar la transmisión.");
                observedTaskId = data.task_id;
                localStorage.setItem("currentTaskId", data.task_id);
                const curUrl = new URL(window.location.href);
                curUrl.searchParams.set("task", data.task_id);
                curUrl.searchParams.delete("project");
                window.history.replaceState({}, "", curUrl);

                // Trasladar automáticamente la vista a Mesa & Timeline para monitorear en vivo
                if (typeof switchMode === "function") {
                    switchMode("studio");
                }
                setStudioAspectRatio(payload.aspect_ratio || "16:9");
                if ($("topbarProjectTitle")) $("topbarProjectTitle").textContent = topic;
                if ($("topbarSaveStatus")) {
                    $("topbarSaveStatus").innerHTML = `<span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#ef4444; box-shadow:0 0 8px #ef4444; margin-right:4px;"></span> EN EMISIÓN`;
                    $("topbarSaveStatus").style.color = "#ef4444";
                    $("topbarSaveStatus").style.borderColor = "rgba(239, 68, 68, 0.4)";
                    $("topbarSaveStatus").style.background = "rgba(239, 68, 68, 0.12)";
                }

                listen(data.task_id);
            } catch (error) {
                console.error("Error al iniciar streamer:", error);
                startStreamerBtn.disabled = false;
                startStreamerBtnText.textContent = "🚀 Iniciar Transmisión de KAI";
                setConnection("error", "Error al iniciar");
                if ($("statusTitle")) $("statusTitle").textContent = "No se pudo iniciar la transmisión";
                if ($("pipelineStatusText")) $("pipelineStatusText").textContent = error.message;
            }
        });
    }


    // =========================================================================
    // CUSTOM STUDIO HUD VIDEO PLAYER CONTROLLER (UI/UX PROMAX)
    // =========================================================================
    function setupHudPlayer(videoEl, options) {
        if (!videoEl) return;
        const playBtn = $(options.playBtn);
        const muteBtn = $(options.muteBtn);
        const timecode = $(options.timecode);
        const scrubberWrap = $(options.scrubberWrap);
        const scrubberBar = $(options.scrubberBar);
        const speedBtn = $(options.speedBtn);
        const fullscreenBtn = $(options.fullscreenBtn);
        const downloadBtn = $(options.downloadBtn);
        const container = videoEl.closest(".stage-preview-box");

        function updatePlayState() {
            if (playBtn) playBtn.textContent = videoEl.paused ? "▶" : "⏸";
            if (container) {
                container.classList.toggle("is-paused", videoEl.paused);
            }
        }

        if (playBtn) {
            playBtn.addEventListener("click", () => {
                if (videoEl.paused) videoEl.play().catch(() => {});
                else videoEl.pause();
                updatePlayState();
            });
        }

        videoEl.addEventListener("play", updatePlayState);
        videoEl.addEventListener("pause", updatePlayState);
        videoEl.addEventListener("ended", updatePlayState);

        if (muteBtn) {
            muteBtn.addEventListener("click", () => {
                videoEl.muted = !videoEl.muted;
                muteBtn.textContent = videoEl.muted ? "🔇" : "🔊";
            });
        }

        // Actualizar timecode y barra scrubber
        function updateTimeline() {
            const cur = videoEl.currentTime || 0;
            const dur = videoEl.duration || 0;
            if (timecode) {
                timecode.textContent = `${fmtDuration(cur)} / ${fmtDuration(dur)}`;
            }
            if (scrubberBar && dur > 0) {
                const pct = (cur / dur) * 100;
                scrubberBar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
            }
        }

        videoEl.addEventListener("timeupdate", updateTimeline);
        videoEl.addEventListener("loadedmetadata", updateTimeline);
        videoEl.addEventListener("durationchange", updateTimeline);

        // Control scrubber: clic directo y arrastre suave
        if (scrubberWrap) {
            let isScrubbing = false;

            function scrub(e) {
                const rect = scrubberWrap.getBoundingClientRect();
                if (rect.width <= 0) return;
                const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                if (videoEl.duration) {
                    videoEl.currentTime = pos * videoEl.duration;
                }
                if (scrubberBar) {
                    scrubberBar.style.width = `${pos * 100}%`;
                }
            }

            scrubberWrap.addEventListener("mousedown", (e) => {
                isScrubbing = true;
                scrub(e);
            });

            window.addEventListener("mousemove", (e) => {
                if (isScrubbing) scrub(e);
            });

            window.addEventListener("mouseup", () => {
                isScrubbing = false;
            });

            // Soporte táctil en pantalla móvil / tablet
            scrubberWrap.addEventListener("touchstart", (e) => {
                isScrubbing = true;
                if (e.touches[0]) scrub(e.touches[0]);
            }, { passive: true });

            window.addEventListener("touchmove", (e) => {
                if (isScrubbing && e.touches[0]) scrub(e.touches[0]);
            }, { passive: true });

            window.addEventListener("touchend", () => {
                isScrubbing = false;
            });
        }

        const speeds = [1, 1.25, 1.5, 2];
        let speedIdx = 0;
        if (speedBtn) {
            speedBtn.addEventListener("click", () => {
                speedIdx = (speedIdx + 1) % speeds.length;
                const spd = speeds[speedIdx];
                videoEl.playbackRate = spd;
                speedBtn.textContent = `${spd}x`;
            });
        }

        if (fullscreenBtn) {
            fullscreenBtn.addEventListener("click", () => {
                if (container?.requestFullscreen) {
                    if (document.fullscreenElement) document.exitFullscreen();
                    else container.requestFullscreen();
                } else if (videoEl.requestFullscreen) {
                    if (document.fullscreenElement) document.exitFullscreen();
                    else videoEl.requestFullscreen();
                }
            });
        }

        if (downloadBtn) {
            downloadBtn.addEventListener("click", (e) => {
                e.preventDefault();
                const taskId = observedTaskId || "";
                const titleSource = $("resVideoTitle")?.textContent || $("bentoCardTitle")?.textContent || "KAI_Broadcast";
                const cleanTitle = titleSource.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "_") || "KAI_Broadcast";
                const mp4Filename = `${cleanTitle}.mp4`;
                const endpoint = taskId ? `/api/projects/${taskId}/download/${encodeURIComponent(mp4Filename)}` : (videoEl.src || "#");

                if (taskId) {
                    fetch(`/api/projects/${taskId}/save-to-downloads`, { method: "POST" })
                        .then(r => r.json())
                        .then(d => {
                            if (d.status === "ok") {
                                console.log("Video guardado en Descargas de Windows:", d.path);
                            }
                        })
                        .catch(() => {});
                }

                const a = document.createElement("a");
                a.href = endpoint;
                a.download = mp4Filename;
                document.body.appendChild(a);
                a.click();
                setTimeout(() => a.remove(), 1500);
            });
        }
    }

    // Inicializar HUDs
    setupHudPlayer($("projectPreview"), {
        playBtn: "hudPlayBtn",
        muteBtn: "hudMuteBtn",
        timecode: "hudTimecode",
        scrubberWrap: "hudScrubberWrap",
        scrubberBar: "hudScrubberBar",
        speedBtn: "hudSpeedBtn",
        fullscreenBtn: "hudFullscreenBtn",
        downloadBtn: "hudDownloadBtn"
    });

    setupHudPlayer($("masterVideoPlayer"), {
        playBtn: "masterPlayBtn",
        muteBtn: "masterMuteBtn",
        timecode: "masterTimecode",
        scrubberWrap: "masterScrubberWrap",
        scrubberBar: "masterScrubberBar",
        speedBtn: "masterSpeedBtn",
        fullscreenBtn: "masterFullscreenBtn",
        downloadBtn: "masterDownloadHudBtn"
    });

    // ── Botones de modo de preview: 16:9 (YouTube) / 9:16 (Shorts) ──
    const previewMode169 = $("previewMode169");
    const previewMode916 = $("previewMode916");
    const masterStageWrap = $("masterStageWrap");
    if (previewMode169 && previewMode916 && masterStageWrap) {
        previewMode169.addEventListener("click", () => {
            masterStageWrap.classList.remove("preview-vertical");
            previewMode169.classList.add("active");
            previewMode916.classList.remove("active");
        });
        previewMode916.addEventListener("click", () => {
            masterStageWrap.classList.add("preview-vertical");
            previewMode916.classList.add("active");
            previewMode169.classList.remove("active");
        });
    }

    // ── Botones de modo de relación de aspecto en Studio (16:9 / 9:16) ──
    const btnStudioAspect169 = $("btnStudioAspect169");
    const btnStudioAspect916 = $("btnStudioAspect916");
    if (btnStudioAspect169) {
        btnStudioAspect169.addEventListener("click", () => setStudioAspectRatio("16:9", true));
    }
    if (btnStudioAspect916) {
        btnStudioAspect916.addEventListener("click", () => setStudioAspectRatio("9:16", true));
    }
    const monitorAspectBadge = $("monitorAspectBadge");
    if (monitorAspectBadge) {
        monitorAspectBadge.addEventListener("click", () => {
            const wrap = $("viewportScreenWrap");
            const is169 = wrap ? wrap.classList.contains("aspect-16-9") : true;
            setStudioAspectRatio(is169 ? "9:16" : "16:9", true);
        });
    }

    // Sincronizar dimensiones reales si el video carga metadatos
    const studioPreviewVid = $("projectPreview");
    if (studioPreviewVid) {
        studioPreviewVid.addEventListener("loadedmetadata", () => {
            if (!window._studioAspectManuallySet && studioPreviewVid.videoWidth && studioPreviewVid.videoHeight) {
                const isWide = studioPreviewVid.videoWidth >= studioPreviewVid.videoHeight;
                setStudioAspectRatio(isWide ? "16:9" : "9:16");
            }
        });
    }

    // Interactividad de pestañas del tablero de telemetría en la Mesa
    const btnSbTabScenes = $("btnSbTabScenes");
    const btnSbTabTerminal = $("btnSbTabTerminal");
    const btnSbTabCards = $("btnSbTabCards");
    const btnSbTabFacts = $("btnSbTabFacts");
    const studioSbPaneScenes = $("studioSbPaneScenes");
    const studioSbPaneTerminal = $("studioSbPaneTerminal");
    const studioSbPaneCards = $("studioSbPaneCards");
    const studioSbPaneFacts = $("studioSbPaneFacts");

    function setStudioSideboardTab(activeTab) {
        const tabs = [
            { btn: btnSbTabScenes, pane: studioSbPaneScenes, id: "scenes" },
            { btn: btnSbTabTerminal, pane: studioSbPaneTerminal, id: "terminal" },
            { btn: btnSbTabCards, pane: studioSbPaneCards, id: "cards" },
            { btn: btnSbTabFacts, pane: studioSbPaneFacts, id: "facts" },
        ];
        tabs.forEach(t => {
            const isMatch = t.id === activeTab;
            if (t.btn) t.btn.classList.toggle("active", isMatch);
            if (t.pane) {
                t.pane.hidden = !isMatch;
                t.pane.classList.toggle("active", isMatch);
            }
        });
    }

    if (btnSbTabScenes) btnSbTabScenes.addEventListener("click", () => setStudioSideboardTab("scenes"));
    if (btnSbTabTerminal) btnSbTabTerminal.addEventListener("click", () => setStudioSideboardTab("terminal"));
    if (btnSbTabCards) btnSbTabCards.addEventListener("click", () => setStudioSideboardTab("cards"));
    if (btnSbTabFacts) btnSbTabFacts.addEventListener("click", () => setStudioSideboardTab("facts"));

    // Framer Motion Micro-Animations
    if (window.Motion) {
        try {
            const { animate } = window.Motion;
            document.querySelectorAll(".dock-btn, .subcard-pill-btn, .cta-broadcast-btn, .hud-btn").forEach(el => {
                el.addEventListener("mouseenter", () => animate(el, { scale: 1.05 }, { duration: 0.18 }));
                el.addEventListener("mouseleave", () => animate(el, { scale: 1 }, { duration: 0.18 }));
                el.addEventListener("mousedown", () => animate(el, { scale: 0.95 }, { duration: 0.1 }));
                el.addEventListener("mouseup", () => animate(el, { scale: 1.05 }, { duration: 0.1 }));
            });
        } catch (e) {
            console.log("Motion init info:", e);
        }
    }

    loadSavedProjects();

    // =========================================================================
    // MODAL FLOTANTE DE AUDICIÓN DE VOCES & PRUEBA DE ORACIONES LARGAS
    // =========================================================================
    const btnOpenVoiceTester = $("btnOpenVoiceTester");
    const voiceTesterModal = $("voiceTesterModal");
    const voiceTesterCloseBtn = $("voiceTesterCloseBtn");
    const modalVoiceSelect = $("modalVoiceSelect");
    const modalVoiceText = $("modalVoiceText");
    const btnSynthesizeVoiceTest = $("btnSynthesizeVoiceTest");
    const voiceTesterStatus = $("voiceTesterStatus");
    const voicePlayerContainer = $("voicePlayerContainer");
    const modalVoiceAudioPlayer = $("modalVoiceAudioPlayer");
    const btnApplyVoiceToStudio = $("btnApplyVoiceToStudio");
    const streamerVoice = $("streamerVoice");

    if (btnOpenVoiceTester && voiceTesterModal) {
        btnOpenVoiceTester.addEventListener("click", () => {
            // Sincronizar voz actual seleccionada en la UI
            if (streamerVoice && modalVoiceSelect) {
                modalVoiceSelect.value = streamerVoice.value;
            }
            voiceTesterModal.hidden = false;
        });

        const closeVoiceTester = () => {
            voiceTesterModal.hidden = true;
            if (modalVoiceAudioPlayer) {
                modalVoiceAudioPlayer.pause();
                modalVoiceAudioPlayer.src = "";
            }
            if (voicePlayerContainer) {
                voicePlayerContainer.style.display = "none";
            }
            if (voiceTesterStatus) {
                voiceTesterStatus.textContent = "Presiona «Escuchar Voz» para generar la prueba en directo.";
                voiceTesterStatus.style.color = "#94a3b8";
            }
        };

        if (voiceTesterCloseBtn) {
            voiceTesterCloseBtn.addEventListener("click", closeVoiceTester);
        }

        voiceTesterModal.addEventListener("click", (e) => {
            if (e.target === voiceTesterModal) closeVoiceTester();
        });

        // Botones de frases de muestra rápida
        document.querySelectorAll(".sample-phrase-btn").forEach((btn) => {
            btn.addEventListener("click", () => {
                const phrase = btn.getAttribute("data-phrase");
                if (phrase && modalVoiceText) {
                    modalVoiceText.value = phrase;
                }
            });
        });

        // Sintetizar y reproducir audio en tiempo real
        if (btnSynthesizeVoiceTest) {
            btnSynthesizeVoiceTest.addEventListener("click", async () => {
                const selectedVoice = modalVoiceSelect?.value || "es-MX-JorgeNeural";
                const textToTest = modalVoiceText?.value?.trim() || "";

                if (!textToTest) {
                    if (voiceTesterStatus) {
                        voiceTesterStatus.textContent = "Por favor escribe un texto para probar.";
                        voiceTesterStatus.style.color = "#f87171";
                    }
                    return;
                }

                btnSynthesizeVoiceTest.disabled = true;
                btnSynthesizeVoiceTest.innerHTML = "<span>⏳ Sintetizando audio...</span>";
                if (voiceTesterStatus) {
                    voiceTesterStatus.textContent = `Generando voz neuronal con ${selectedVoice}...`;
                    voiceTesterStatus.style.color = "#38bdf8";
                }

                try {
                    const response = await fetch("/api/tts-preview", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ voice: selectedVoice, text: textToTest }),
                    });

                    if (!response.ok) {
                        throw new Error(`Error en servidor (${response.status})`);
                    }

                    const audioBlob = await response.blob();
                    const audioUrl = URL.createObjectURL(audioBlob);

                    if (modalVoiceAudioPlayer && voicePlayerContainer) {
                        modalVoiceAudioPlayer.src = audioUrl;
                        voicePlayerContainer.style.display = "flex";
                        modalVoiceAudioPlayer.play().catch(() => {});
                    }

                    if (voiceTesterStatus) {
                        voiceTesterStatus.textContent = "✓ Audio generado con éxito. Escucha el ritmo y la dicción.";
                        voiceTesterStatus.style.color = "#4ade80";
                    }
                } catch (err) {
                    console.error("Error probando voz:", err);
                    if (voiceTesterStatus) {
                        voiceTesterStatus.textContent = `Error generando audio: ${err.message}`;
                        voiceTesterStatus.style.color = "#f87171";
                    }
                } finally {
                    btnSynthesizeVoiceTest.disabled = false;
                    btnSynthesizeVoiceTest.innerHTML = "<span>▶ Escuchar Voz</span>";
                }
            });
        }

        // Botón "Usar esta voz en el Studio"
        if (btnApplyVoiceToStudio) {
            btnApplyVoiceToStudio.addEventListener("click", () => {
                const chosen = modalVoiceSelect?.value;
                if (chosen && streamerVoice) {
                    streamerVoice.value = chosen;
                }
                closeVoiceTester();
            });
        }
    }

    // Exponer funciones globales para que el Agente Copilot pueda controlar la app
    window.switchMode = switchMode;

    // Puente para el Radar de Viralidad: al replicar un tema/video, la nueva
    // producción de KAI se monitorea en vivo igual que una emisión manual.
    window.__startRadarTask = (taskId, topic) => {
        observedTaskId = taskId;
        localStorage.setItem("currentTaskId", taskId);
        try {
            const curUrl = new URL(window.location.href);
            curUrl.searchParams.set("task", taskId);
            curUrl.searchParams.delete("project");
            window.history.replaceState({}, "", curUrl);
        } catch { /* URL API no disponible */ }
        switchMode("studio");
        setStudioAspectRatio("16:9");
        if ($("topbarProjectTitle")) $("topbarProjectTitle").textContent = topic;
        if ($("topbarSaveStatus")) {
            $("topbarSaveStatus").innerHTML = `<span style="display:inline-block; width:7px; height:7px; border-radius:50%; background:#ef4444; box-shadow:0 0 8px #ef4444; margin-right:4px;"></span> EN EMISIÓN`;
            $("topbarSaveStatus").style.color = "#ef4444";
            $("topbarSaveStatus").style.borderColor = "rgba(239, 68, 68, 0.4)";
            $("topbarSaveStatus").style.background = "rgba(239, 68, 68, 0.12)";
        }
        listen(taskId);
    };
    window.openProject = openProject;
    window.listen = listen;

    // Inicializar Agente Copilot Autónomo (Clon ChatGPT Multi-Modelo)
    try {
        window.agentCopilot = new AgentCopilot();
    } catch (e) {
        console.error("Error inicializando AgentCopilot:", e);
    }

    // Auto-abrir proyecto o tarea si está presente en la URL o en localStorage
    const initialUrl = new URL(window.location.href);
    const urlProjectId = initialUrl.searchParams.get("project");
    const urlTaskId = initialUrl.searchParams.get("task");
    const savedTaskId = localStorage.getItem("currentTaskId");

    if (urlProjectId) {
        openProject(urlProjectId).catch((e) => console.log("No se pudo cargar proyecto inicial:", e));
    } else if (urlTaskId) {
        listen(urlTaskId);
    } else if (savedTaskId) {
        listen(savedTaskId);
    } else {
        // Sin tarea en curso: volver a la sección donde el usuario se quedó.
        try {
            const lastMode = localStorage.getItem("aetherLastMode");
            if (lastMode && ["radar", "projects", "studio", "copilot", "multiagent", "streamer"].includes(lastMode) && lastMode !== "streamer") {
                switchMode(lastMode);
            }
        } catch { /* storage bloqueado */ }
    // Control interactivo de Piloto de Anime y Recorrido Universal
    const btnToggleAnime = $("btnToggleAnimeAutopilot");
    const animeLabel = $("animeAutopilotStateLabel");
    const updateAnimeButtonUI = (enabled) => {
        if (!animeLabel || !btnToggleAnime) return;
        if (enabled) {
            animeLabel.textContent = "ACTIVO";
            btnToggleAnime.style.background = "rgba(168, 85, 247, 0.2)";
            btnToggleAnime.style.borderColor = "rgba(168, 85, 247, 0.6)";
            btnToggleAnime.style.color = "#c084fc";
        } else {
            animeLabel.textContent = "PAUSADO";
            btnToggleAnime.style.background = "rgba(148, 163, 184, 0.12)";
            btnToggleAnime.style.borderColor = "rgba(148, 163, 184, 0.3)";
            btnToggleAnime.style.color = "#94a3b8";
        }
    };

    fetch("/api/anime-series/status")
        .then((r) => r.json())
        .then((st) => updateAnimeButtonUI(st?.config?.enabled !== false))
        .catch(() => {});

    if (btnToggleAnime) {
        btnToggleAnime.addEventListener("click", async () => {
            try {
                const res = await fetch("/api/anime-series/toggle", { method: "POST" }).then((r) => r.json());
                updateAnimeButtonUI(res.enabled);
            } catch (err) {
                console.error("Error al alternar estado de anime:", err);
            }
        });
    }

    const btnUniversalTour = $("btnRunUniversalTour");
    if (btnUniversalTour) {
        btnUniversalTour.addEventListener("click", async () => {
            try {
                btnUniversalTour.disabled = true;
                const prev = btnUniversalTour.innerHTML;
                btnUniversalTour.innerHTML = `<span>⏳ Iniciando...</span>`;
                const res = await fetch("/api/universal-tour/run-now", { method: "POST" }).then((r) => r.json());
                alert(res.message || "Recorrido Secuencial Universal iniciado.");
                setTimeout(() => {
                    btnUniversalTour.disabled = false;
                    btnUniversalTour.innerHTML = prev;
                }, 3000);
            } catch (err) {
                alert("Error al iniciar recorrido: " + err.message);
                btnUniversalTour.disabled = false;
            }
        });
    }
});

/**
 * AetherCut - Estudio de Publicación
 * Ver qué se va a publicar, generar miniatura con IA (Nano Banana),
 * metadatos SEO y subir directamente a YouTube (OAuth) o modo asistido.
 */
import { $, esc } from "./utils.js";

const state = {
    project: null,
    info: null,
    youtube: { configured: false, connected: false, channel: null },
    uploading: false,
    pollTimer: null,
    statusTimer: null,
    metaLoading: false,
};

/* --------------------------------------------------------------- helpers */

function toast(message, level = "info") {
    const colors = { success: "#10b981", error: "#ef4444", warning: "#f59e0b", info: "#38bdf8" };
    const icons = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };
    const color = colors[level] || colors.info;
    const el = document.createElement("div");
    el.style.cssText = `position: fixed; bottom: 88px; right: 24px; z-index: 99999;
        background: #1e293b; border: 1px solid ${color}55; border-left: 3px solid ${color};
        color: #e2e8f0; padding: 12px 18px; border-radius: 10px; font-size: 13px; font-weight: 500;
        max-width: 340px; box-shadow: 0 8px 32px rgba(0,0,0,.45); display: flex; gap: 10px; align-items: center;
        pointer-events: none; transition: opacity .4s ease, transform .4s ease;`;
    el.innerHTML = `<span>${icons[level] || icons.info}</span><span>${esc(message)}</span>`;
    document.body.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateX(20px)"; setTimeout(() => el.remove(), 450); }, 3800);
}

async function api(url, { method = "POST", body = null } = {}) {
    const res = await fetch(url, {
        method,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
        let detail = res.statusText;
        try { detail = (await res.json()).detail || detail; } catch { /* respuesta sin JSON */ }
        throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return res.json();
}

function setStatus(message) {
    const line = $("pubStatusLine");
    if (!line) return;
    line.hidden = !message;
    line.textContent = message || "";
}

function setThumbLoading(active, text) {
    const wrap = $("pubThumbLoading");
    const label = $("pubThumbLoadingText");
    const btn = $("pubThumbGenBtn");
    if (!wrap) return;
    wrap.hidden = !active;
    if (label && text) label.textContent = text;
    if (btn) { btn.disabled = active; btn.style.opacity = active ? ".5" : "1"; }
}

function showThumb(url, { download = false, note = "" } = {}) {
    const img = $("pubThumbImg");
    const empty = $("pubThumbEmpty");
    const dl = $("pubThumbDownload");
    const noteEl = $("pubThumbNote");
    if (!img) return;
    img.hidden = false;
    img.src = `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;
    if (empty) empty.style.display = "none";
    if (dl) { dl.hidden = false; dl.href = url; }
    if (noteEl) { noteEl.hidden = !note; noteEl.textContent = note; }
}

/* ------------------------------------------------------------ contadores */

function bindCounters() {
    const title = $("pubTitle");
    const desc = $("pubDescription");
    const tags = $("pubTags");
    const update = () => {
        if ($("pubTitleCount")) $("pubTitleCount").textContent = `${(title?.value || "").length}/100`;
        if ($("pubDescCount")) $("pubDescCount").textContent = `${(desc?.value || "").length}/5000`;
        if ($("pubTagsCount")) $("pubTagsCount").textContent = `${(tags?.value || "").length}/500`;
    };
    [title, desc, tags].forEach(el => el?.addEventListener("input", update));
    update();
}

/* ---------------------------------------------------------- canal youtube */

function renderChannelBox() {
    const info = $("pubChannelInfo");
    const connectBtn = $("pubConnectBtn");
    const refreshBtn = $("pubRefreshChannelBtn");
    const discBtn = $("pubDisconnectBtn");
    if (!info) return;
    const { configured, connected, channel } = state.youtube;

    if (!configured) {
        info.innerHTML = `<span class="pub-channel-scan">⚠️ Subida directa deshabilitada: falta YOUTUBE_CLIENT_ID en el servidor. Puedes usar la publicación asistida.</span>`;
        connectBtn.hidden = true; refreshBtn.hidden = true; discBtn.hidden = true;
    } else if (connected && channel) {
        info.innerHTML = `
            <img src="${esc(channel.thumbnail || "")}" alt="" style="width:34px;height:34px;border-radius:50%;object-fit:cover;border:2px solid #ef4444;">
            <div style="min-width:0;">
                <strong style="display:block;font-size:13px;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(channel.title)}</strong>
                <span style="font-size:11px;color:#94a3b8;">✅ Conectado · ${Number(channel.subscribers || 0).toLocaleString("es")} suscriptores</span>
            </div>`;
        connectBtn.hidden = true; refreshBtn.hidden = true; discBtn.hidden = false;
    } else if (connected) {
        info.innerHTML = `<span class="pub-channel-scan">✅ Canal conectado (sin datos de canal).</span>`;
        connectBtn.hidden = true; refreshBtn.hidden = true; discBtn.hidden = false;
    } else {
        info.innerHTML = `<span class="pub-channel-scan">🔗 Conecta tu canal para publicar en 1 clic (OAuth seguro de Google).</span>`;
        connectBtn.hidden = false; refreshBtn.hidden = false; discBtn.hidden = true;
    }
    const uploadBtn = $("pubUploadBtn");
    if (uploadBtn) {
        uploadBtn.disabled = state.uploading || !connected;
        uploadBtn.title = connected
            ? "Sube el video master directamente a tu canal"
            : "Conecta primero tu canal de YouTube";
    }
}

async function refreshChannelStatus({ silent = true } = {}) {
    try {
        state.youtube = await api("/api/publish/youtube/status", { method: "GET" });
        renderChannelBox();
    } catch { /* el estado se muestra como no conectado */ }
    if (!silent) toast("Estado del canal actualizado.", "info");
}

/* ------------------------------------------------------------------ abrir */

async function openPublishModal(project) {
    const modal = $("publishModal");
    if (!modal) return;
    state.project = project;
    state.uploading = false;
    stopPolls();

    const video = $("pubVideoElement");
    if (video) {
        video.src = project.master_video_url || `/api/projects/${encodeURIComponent(project.id)}/preview`;
        video.load();
    }

    const title = $("pubModalTitle");
    const sub = $("pubModalSub");
    if (title) title.textContent = project.name || "Producción KAI";
    if (sub) sub.textContent = "Revisa exactamente lo que se va a publicar antes de subirlo a YouTube";

    // Reset visual
    setStatus("");
    if ($("pubResultBox")) { $("pubResultBox").hidden = true; $("pubResultBox").replaceChildren(); }
    if ($("pubProgressWrap")) $("pubProgressWrap").hidden = true;
    if ($("pubThumbImg")) $("pubThumbImg").hidden = true;
    const empty = $("pubThumbEmpty");
    if (empty) empty.style.display = "flex";
    const dl = $("pubThumbDownload");
    if (dl) dl.hidden = true;
    const noteEl = $("pubThumbNote");
    if (noteEl) { noteEl.hidden = true; noteEl.textContent = ""; }
    if ($("pubTitle")) $("pubTitle").value = project.name || "";
    if ($("pubDescription")) $("pubDescription").value = "";
    if ($("pubTags")) $("pubTags").value = "";
    if ($("pubThumbText")) $("pubThumbText").value = "";
    if ($("pubVideoMeta")) $("pubVideoMeta").textContent = "Cargando datos del video...";
    if ($("pubChannelInfo")) $("pubChannelInfo").innerHTML = `<span class="pub-channel-scan">Comprobando canal de YouTube...</span>`;
    bindCounters();

    modal.hidden = false;
    renderChannelBox();

    // 1) Preparación: qué se va a publicar
    try {
        const info = await api("/api/publish/prepare", { body: { project_id: project.id } });
        state.info = info;
        state.youtube = info.youtube || state.youtube;

        const styleSel = $("pubThumbStyle");
        if (styleSel) {
            styleSel.replaceChildren();
            (info.styles || []).forEach(s => {
                const opt = document.createElement("option");
                opt.value = s.id; opt.textContent = s.label;
                styleSel.append(opt);
            });
        }
        if (!info.video_found) {
            setStatus("⚠️ Este proyecto aún no tiene un video master final. Puedes preparar metadatos y miniatura, pero no publicarlo todavía.");
        }
        const meta = $("pubVideoMeta");
        if (meta) {
            const mins = Math.floor((info.duration || 0) / 60);
            const secs = Math.floor((info.duration || 0) % 60);
            meta.textContent = [
                `🎬 Video: ${info.video_found ? "listo para publicar" : "no encontrado"}`,
                info.video_size_mb ? `· ${info.video_size_mb} MB` : "",
                info.duration ? `· ${mins}:${String(secs).padStart(2, "0")} min` : "",
                info.topic ? `· Tema: ${info.topic}` : "",
            ].filter(Boolean).join(" ");
        }
        if (info.thumbnail_url) showThumb(info.thumbnail_url);
        renderChannelBox();

        if (info.channels && $("pubChannelSelect")) {
            const chSel = $("pubChannelSelect");
            chSel.innerHTML = "";
            info.channels.forEach(ch => {
                const opt = document.createElement("option");
                opt.value = ch.id;
                opt.textContent = `${ch.badge || "📺"} ${ch.name}`;
                chSel.appendChild(opt);
            });
            if (info.channel_classification?.channel?.id) {
                chSel.value = info.channel_classification.channel.id;
                if ($("pubChannelBadge")) {
                    $("pubChannelBadge").textContent = info.channel_classification.channel.badge || "Nicho Detectado";
                }
                if ($("pubClassifyChip")) {
                    $("pubClassifyChip").textContent = `✨ ${Math.round((info.channel_classification.confidence || 0.85) * 100)}% Coincidencia`;
                }
            }
            chSel.onchange = () => {
                const selected = (info.channels || []).find(c => c.id === chSel.value);
                if (selected && $("pubChannelBadge")) {
                    $("pubChannelBadge").textContent = selected.badge || selected.name;
                }
            };
        }
    } catch (err) {
        setStatus(`⚠️ ${err.message}`);
        toast(`No se pudo preparar la publicación: ${err.message}`, "error");
    }

    // 2) Metadatos SEO con IA (relleno automático la primera vez)
    if (!$("pubDescription").value) await generateMetadata();

    // 3) Auto-miniatura si el proyecto no tiene ninguna
    if (!state.info?.thumbnail_url) generateThumbnail({ silentToast: true }).catch(() => {});
}

function closePublishModal() {
    const modal = $("publishModal");
    const video = $("pubVideoElement");
    if (video) { try { video.pause(); } catch { /* el video puede ya estar descargado */ } }
    if (modal) modal.hidden = true;
    stopPolls();
}

function stopPolls() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
    if (state.statusTimer) { clearInterval(state.statusTimer); state.statusTimer = null; }
}

/* -------------------------------------------------------- generación IA */

async function generateMetadata() {
    const btn = $("pubMetaBtn");
    const title = $("pubTitle");
    const desc = $("pubDescription");
    const tags = $("pubTags");
    if (state.metaLoading) return;
    state.metaLoading = true;
    if (btn) { btn.disabled = true; btn.textContent = "⏳ Generando..."; }
    setStatus("✨ Redactando metadatos SEO optimizados para YouTube...");
    try {
        const meta = await api("/api/publish/metadata", {
            body: { project_id: state.project?.id, instructions: "" },
        });
        if (meta.title) title.value = meta.title;
        if (meta.description) desc.value = meta.description;
        if (Array.isArray(meta.tags)) tags.value = meta.tags.join(", ");
        if (meta.thumbnail_text && !$("pubThumbText").value) $("pubThumbText").value = meta.thumbnail_text;
        title.dispatchEvent(new Event("input"));
        desc.dispatchEvent(new Event("input"));
        tags.dispatchEvent(new Event("input"));
        setStatus("");
        toast("📝 Metadatos SEO generados con IA.", "success");
    } catch (err) {
        setStatus(`⚠️ Metadatos: ${err.message}`);
        toast(`No se pudieron generar los metadatos: ${err.message}`, "error");
    } finally {
        state.metaLoading = false;
        if (btn) { btn.disabled = false; btn.textContent = "✨ Regenerar con IA"; }
    }
}

async function generateThumbnail({ silentToast = false } = {}) {
    if (!state.project) return;
    setThumbLoading(true, "Generando miniatura con Nano Banana...");
    setStatus("🖼️ Dibujando la miniatura 1280×720 con IA...");
    try {
        const res = await api("/api/publish/thumbnail", {
            body: {
                project_id: state.project.id,
                title: $("pubTitle")?.value || state.project.name || "",
                topic: state.info?.topic || state.project.topic || "",
                style: $("pubThumbStyle")?.value || "cinematic",
                thumbnail_text: $("pubThumbText")?.value || "",
                use_frame: $("pubUseFrame")?.checked || false,
            },
        });
        if (state.info) state.info.thumbnail_url = res.url;
        showThumb(res.url, { note: res.note || `Motor: ${res.model}` });
        setStatus("");
        if (!silentToast) toast(`🖼️ Miniatura generada con ${res.model}.`, "success");
    } catch (err) {
        setStatus(`⚠️ Miniatura: ${err.message}`);
        toast(`No se pudo generar la miniatura: ${err.message}`, "error");
    } finally {
        setThumbLoading(false);
    }
}

/* ------------------------------------------------------------- publicación */

async function publishDirect() {
    if (!state.project || state.uploading) return;
    const title = $("pubTitle")?.value.trim();
    if (!title) { toast("Ponle un título antes de publicar.", "warning"); return; }
    if (!state.info?.video_found) { toast("Este proyecto no tiene video final para subir.", "error"); return; }
    if (!state.youtube.connected) { toast("Conecta primero tu canal de YouTube.", "warning"); return; }

    state.uploading = true;
    renderChannelBox();
    $("pubUploadBtn").disabled = true;
    $("pubAssistBtn").disabled = true;
    if ($("pubResultBox")) { $("pubResultBox").hidden = true; $("pubResultBox").replaceChildren(); }
    const progressWrap = $("pubProgressWrap");
    const fill = $("pubProgressFill");
    const progressText = $("pubProgressText");
    if (progressWrap) progressWrap.hidden = false;
    if (fill) fill.style.width = "0%";
    if (progressText) progressText.textContent = "0%";

    try {
        const { task_id } = await api("/api/publish/youtube/upload", {
            body: {
                project_id: state.project.id,
                channel_id: $("pubChannelSelect")?.value || "divulgacion",
                title,
                description: $("pubDescription")?.value || "",
                tags: ($("pubTags")?.value || "").split(",").map(t => t.trim().replace(/^#/, "")).filter(Boolean),
                privacy: $("pubPrivacy")?.value || "public",
                made_for_kids: $("pubKids")?.checked || false,
                notify_subscribers: $("pubNotify")?.checked !== false,
                thumbnail_url: state.info?.thumbnail_url || "",
            },
        });
        toast("🚀 Subida a YouTube iniciada...", "info");

        state.pollTimer = setInterval(async () => {
            let st;
            try {
                const res = await fetch(`/api/progress/${encodeURIComponent(task_id)}`);
                st = await res.json();
            } catch { return; }
            const pct = Math.max(0, Math.min(100, Number(st.progress || 0)));
            if (fill) fill.style.width = `${pct}%`;
            if (progressText) progressText.textContent = `${pct.toFixed(0)}% · ${st.message || ""}`;
            setStatus(st.message || "");

            if (st.completed && st.result) {
                stopPolls();
                state.uploading = false;
                $("pubUploadBtn").disabled = false;
                $("pubAssistBtn").disabled = false;
                renderUploadResult(st.result);
                setStatus("");
            } else if (st.error) {
                stopPolls();
                state.uploading = false;
                $("pubUploadBtn").disabled = false;
                $("pubAssistBtn").disabled = false;
                if (progressText) progressText.textContent = "Error";
                setStatus(`❌ ${st.error}`);
                toast(`No se pudo publicar: ${st.error}`, "error");
            }
        }, 1500);
    } catch (err) {
        state.uploading = false;
        $("pubUploadBtn").disabled = false;
        $("pubAssistBtn").disabled = false;
        renderChannelBox();
        setStatus(`❌ ${err.message}`);
        toast(`No se pudo iniciar la subida: ${err.message}`, "error");
    }
}

function renderUploadResult(result) {
    const box = $("pubResultBox");
    if (!box) return;
    box.replaceChildren();
    const link = document.createElement("a");
    link.href = result.video_url || "#";
    link.target = "_blank";
    link.rel = "noopener";
    link.className = "pub-result-link";
    link.textContent = `🎉 ¡Publicado! Ver en YouTube ↗`;
    const studio = document.createElement("a");
    studio.href = result.studio_url || "https://studio.youtube.com";
    studio.target = "_blank";
    studio.rel = "noopener";
    studio.className = "yt-open-pill-btn";
    studio.style.cssText = "display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:7px 12px;";
    studio.textContent = "🛠 Editar en YouTube Studio";
    box.append(link, studio);
    if (result.thumbnail_set === false) {
        const warn = document.createElement("span");
        warn.style.cssText = "display:block;font-size:11px;color:#fbbf24;margin-top:8px;";
        warn.textContent = "⚠️ La miniatura personalizada fue rechazada (el canal requiere verificación). Súbela desde YouTube Studio.";
        box.append(warn);
    }
    box.hidden = false;
    toast("🎉 ¡Video publicado en YouTube con éxito!", "success");
}

async function publishAssisted() {
    const title = $("pubTitle")?.value || state.project?.name || "";
    const description = $("pubDescription")?.value || "";
    const tags = ($("pubTags")?.value || "").trim();
    const payload = [
        title ? `TÍTULO:\n${title}` : "",
        description ? `\nDESCRIPCIÓN:\n${description}` : "",
        tags ? `\nETIQUETAS:\n${tags}` : "",
    ].filter(Boolean).join("\n");
    try {
        if (navigator.clipboard && payload) {
            await navigator.clipboard.writeText(payload);
            toast("📋 Metadatos copiados al portapapeles.", "success");
        }
    } catch { /* el portapapeles puede estar bloqueado */ }

    if (state.info?.thumbnail_url) {
        const dl = $("pubThumbDownload");
        if (dl) dl.click();
    }
    let targetStudioUrl = "https://studio.youtube.com/channel/UC/videos/upload?d=pt";
    let channelName = "YouTube Studio";
    const selectedChId = $("pubChannelSelect")?.value;
    if (state.info?.channels && selectedChId) {
        const foundCh = state.info.channels.find(c => c.id === selectedChId);
        if (foundCh) {
            channelName = foundCh.name;
            if (foundCh.studio_url) targetStudioUrl = foundCh.studio_url;
        }
    }
    window.open(targetStudioUrl, "_blank");
    setStatus(`🧳 Metadatos preparados para ${channelName}. Pega con Ctrl+V y sube la miniatura.`);
    toast(`🧭 ${channelName} abierto: pega los metadatos y la miniatura.`, "info");
}

/* -------------------------------------------------------------------- init */

export function initPublishStudio() {
    $("pubCloseBtn")?.addEventListener("click", closePublishModal);
    $("publishModal")?.addEventListener("click", (e) => {
        if (e.target.id === "publishModal") closePublishModal();
    });
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !$("publishModal")?.hidden) closePublishModal();
    });

    $("pubMetaBtn")?.addEventListener("click", generateMetadata);
    $("pubThumbGenBtn")?.addEventListener("click", () => generateThumbnail());
    $("pubUploadBtn")?.addEventListener("click", publishDirect);
    $("pubAssistBtn")?.addEventListener("click", publishAssisted);
    bindCounters();

    $("pubConnectBtn")?.addEventListener("click", () => {
        window.open("/api/publish/youtube/connect", "_blank");
        // Mientras la pestaña de Google está abierta, vigilar el estado.
        if (state.statusTimer) clearInterval(state.statusTimer);
        let tries = 0;
        state.statusTimer = setInterval(async () => {
            tries += 1;
            await refreshChannelStatus();
            if (state.youtube.connected || tries > 45) {
                clearInterval(state.statusTimer);
                state.statusTimer = null;
                if (state.youtube.connected) {
                    toast("🔗 ¡Canal de YouTube conectado! Ya puedes publicar en 1 clic.", "success");
                    renderChannelBox();
                }
            }
        }, 4000);
    });
    $("pubRefreshChannelBtn")?.addEventListener("click", () => refreshChannelStatus({ silent: false }));
    $("pubDisconnectBtn")?.addEventListener("click", async () => {
        try {
            await api("/api/publish/youtube/disconnect");
            toast("Canal desconectado.", "info");
            await refreshChannelStatus();
        } catch (err) { toast(err.message, "error"); }
    });

    // Aterrizar aquí el redirect de OAuth (éxito o error)
    const params = new URLSearchParams(window.location.search);
    if (params.get("publish_connected")) {
        toast("🔗 ¡Canal de YouTube conectado correctamente!", "success");
        refreshChannelStatus();
        window.history.replaceState({}, document.title, window.location.pathname);
    }
    const pubError = params.get("publish_error");
    if (pubError) {
        toast(`❌ YouTube: ${pubError}`, "error");
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    return { open: openPublishModal };
}

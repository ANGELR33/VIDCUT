/**
 * AetherCut - Radar de Viralidad
 * Ranking 24-72h de videos virales por región (score + movimiento cada 10 min)
 * y temas urgentes sin cobertura. Réplica en español con mejoras en 1 clic.
 */
import { $, esc } from "./utils.js";

let pollTimer = null;
let countdownTimer = null;
let currentTab = "videos";
let data = null;

/* --------------------------------------------------------------- helpers */

function toast(message, level = "info") {
    const colors = { success: "#10b981", error: "#ef4444", warning: "#f59e0b", info: "#38bdf8" };
    const icons = { success: "✅", error: "❌", warning: "⚠️", info: "ℹ️" };
    const color = colors[level] || colors.info;
    const el = document.createElement("div");
    el.style.cssText = `position: fixed; bottom: 88px; right: 24px; z-index: 99999;
        background: #1e293b; border: 1px solid ${color}55; border-left: 3px solid ${color};
        color: #e2e8f0; padding: 12px 18px; border-radius: 10px; font-size: 13px; font-weight: 500;
        max-width: 360px; box-shadow: 0 8px 32px rgba(0,0,0,.45); display: flex; gap: 10px; align-items: center;
        pointer-events: none; transition: opacity .4s ease, transform .4s ease;`;
    el.innerHTML = `<span>${icons[level] || icons.info}</span><span>${esc(message)}</span>`;
    document.body.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateX(20px)"; setTimeout(() => el.remove(), 450); }, 4200);
}

function fmtViews(n) {
    n = Number(n || 0);
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${Math.round(n / 1_000)}K`;
    return String(n);
}

function timeAgo(iso) {
    if (!iso) return "";
    const mins = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
    if (mins < 60) return `hace ${mins} min`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `hace ${hours} h`;
    return `hace ${Math.floor(hours / 24)} d`;
}

/* ------------------------------------------------------------- renderizado */

function renderUpdatedBadge() {
    const badge = $("radarUpdatedBadge");
    if (!badge) return;
    if (!data?.updated_at) { badge.textContent = "Cargando radar…"; return; }
    let base = `Actualizado ${timeAgo(data.updated_at)}`;
    if (data.refreshing) base += " · 🔄 barriendo ahora";
    else if (data.next_update_at) {
        const mins = Math.max(0, Math.round((new Date(data.next_update_at).getTime() - Date.now()) / 60000));
        if (mins < 90) base += ` · próxima revisión en ${Math.max(1, mins)} min`;
        else base += ` · próxima revisión en ${Math.floor(mins / 60)} h ${mins % 60} min`;
    }
    badge.textContent = base;
}

const filterState = {
    category: "all",
    region: "all",
    recency: "all",
    search: "",
};

function getFilteredVideos() {
    let videos = data?.videos || [];

    // 1. Filtrar por categoría / tipo de contenido
    if (filterState.category && filterState.category !== "all") {
        const catTarget = filterState.category.toLowerCase();
        videos = videos.filter(v => {
            const cat = (v.category || "").toLowerCase();
            const title = (v.title || "").toLowerCase();
            if (catTarget === "entretenimiento") {
                return cat.includes("entretenimiento") || cat.includes("viral") || cat.includes("comedia") || cat.includes("cine") || cat.includes("vlogs") || title.includes("viral");
            }
            if (catTarget === "divulgacion") {
                return cat.includes("divulgacion") || cat.includes("ciencia") || cat.includes("educacion") || cat.includes("documental") || cat.includes("misterio") || title.includes("ciencia") || title.includes("universo") || title.includes("documental") || title.includes("misterio") || title.includes("descubrimiento");
            }
            if (catTarget === "noticias") {
                return cat.includes("noticias") || cat.includes("news") || cat.includes("urgente") || title.includes("noticia") || title.includes("última hora") || title.includes("debate") || title.includes("urgente");
            }
            if (catTarget === "tecnologia") {
                return cat.includes("tecnologia") || cat.includes("tech") || cat.includes("ia") || title.includes("technology") || title.includes("inteligencia artificial") || title.includes("ia") || title.includes("ai");
            }
            if (catTarget === "musica") {
                return cat.includes("musica") || cat.includes("music") || title.includes("song") || title.includes("canción") || title.includes("music");
            }
            if (catTarget === "gaming") {
                return cat.includes("gaming") || title.includes("gameplay");
            }
            if (catTarget === "deportes") {
                return cat.includes("deportes") || title.includes("fútbol") || title.includes("futbol");
            }
            return cat.includes(catTarget) || title.includes(catTarget);
        });
    }

    // 2. Filtrar por país / región
    if (filterState.region && filterState.region !== "all") {
        const regTarget = filterState.region.toUpperCase();
        videos = videos.filter(v => {
            const reg = (v.region || "").toUpperCase();
            if (regTarget === "GLOBAL") {
                return reg === "GLOBAL" || reg === "WORLD" || reg === "" || reg === "🌍" || reg === "🌐";
            }
            if (regTarget === "MX" || regTarget === "LATAM") {
                return reg === "MX" || reg === "LATAM";
            }
            return reg === regTarget;
        });
    }

    // 3. Filtrar por antigüedad / frescura (recientes o no tan recientes)
    if (filterState.recency && filterState.recency !== "all") {
        videos = videos.filter(v => {
            const hours = Number(v.hours_old ?? (v.published_at ? Math.max(1, (Date.now() - new Date(v.published_at).getTime()) / 3600000) : 24));
            if (filterState.recency === "fresh") {
                return hours <= 24; // Muy recientes (< 24 horas / Hoy)
            }
            if (filterState.recency === "recent") {
                return hours > 24 && hours <= 72; // Recientes (1 a 3 días)
            }
            if (filterState.recency === "older") {
                return hours > 72; // No tan recientes / En tendencia continua (> 3 días)
            }
            return true;
        });
    }

    // 4. Filtrar por búsqueda libre
    if (filterState.search && filterState.search.trim().length > 0) {
        const q = filterState.search.trim().toLowerCase();
        videos = videos.filter(v => {
            return (v.title || "").toLowerCase().includes(q) ||
                   (v.channel || "").toLowerCase().includes(q) ||
                   (v.category || "").toLowerCase().includes(q) ||
                   (v.region || "").toLowerCase().includes(q);
        });
    }

    return videos;
}

function updateFilterStatus(shownCount, totalCount) {
    const countEl = $("radarFilterCount");
    const resetBtn = $("radarFilterResetBtn");
    const searchClear = $("radarSearchClearBtn");
    
    const isFiltered = filterState.category !== "all" || 
                       filterState.region !== "all" || 
                       filterState.recency !== "all" || 
                       filterState.search.trim().length > 0;

    if (countEl) {
        if (isFiltered) {
            countEl.textContent = `Mostrando ${shownCount} de ${totalCount} videos`;
        } else {
            countEl.textContent = `${totalCount} videos virales`;
        }
    }

    if (resetBtn) resetBtn.hidden = !isFiltered;
    if (searchClear) searchClear.hidden = !(filterState.search.trim().length > 0);
}

function renderVideos() {
    const list = $("radarVideosList");
    if (!list) return;
    list.replaceChildren();
    
    const allVideos = data?.videos || [];
    const filteredVideos = getFilteredVideos();
    
    updateFilterStatus(filteredVideos.length, allVideos.length);
    
    const regions = $("radarRegionsLabel");
    if (regions) regions.textContent = data?.regions?.length ? `Regiones: ${data.regions.join(" · ")}` : "";

    if (!allVideos.length) {
        const empty = document.createElement("div");
        empty.className = "radar-empty";
        empty.innerHTML = `<span style="font-size:28px;">📡</span><strong>Radar calibrando…</strong>
            <span>El primer barrido (charts de YouTube + análisis IA) está en marcha. Vuelve en un minuto.</span>`;
        list.append(empty);
        return;
    }

    if (!filteredVideos.length) {
        const empty = document.createElement("div");
        empty.className = "radar-empty";
        empty.innerHTML = `<span style="font-size:28px;">🔍</span><strong>Sin resultados para los filtros seleccionados</strong>
            <span>Prueba cambiando el tipo de contenido, país o rango de fecha para ver más videos virales.</span>`;
        list.append(empty);
        return;
    }

    filteredVideos.forEach(v => {
        const row = document.createElement("article");
        row.className = "radar-video-row";

        // Rango + movimiento
        const rankBox = document.createElement("div");
        rankBox.className = "radar-rank-box";
        rankBox.innerHTML = `<span class="radar-rank-num">#${v.rank}</span>`;
        const move = document.createElement("span");
        if (v.is_new) { move.className = "radar-move new"; move.textContent = "🆕"; move.title = "Nuevo en el ranking"; }
        else if (v.movement > 0) { move.className = "radar-move up"; move.textContent = `↑${v.movement}`; move.title = `Subió ${v.movement} puestos`; }
        else if (v.movement < 0) { move.className = "radar-move down"; move.textContent = `↓${Math.abs(v.movement)}`; move.title = `Bajó ${Math.abs(v.movement)} puestos`; }
        else { move.className = "radar-move steady"; move.textContent = "•"; move.title = "Sin cambios"; }
        rankBox.append(move);

        // Miniatura
        const thumbWrap = document.createElement("a");
        thumbWrap.className = "radar-thumb";
        thumbWrap.href = v.url;
        thumbWrap.target = "_blank";
        thumbWrap.rel = "noopener";
        thumbWrap.title = "Ver el video original en YouTube";
        thumbWrap.innerHTML = v.thumb
            ? `<img src="${esc(v.thumb)}" alt="" loading="lazy">`
            : `<span class="radar-thumb-ph">🎬</span>`;

        // Textos
        const body = document.createElement("div");
        body.className = "radar-video-body";
        const title = document.createElement("a");
        title.className = "radar-video-title";
        title.href = v.url;
        title.target = "_blank";
        title.rel = "noopener";
        title.textContent = v.title;
        const meta = document.createElement("div");
        meta.className = "radar-video-meta";
        const velocity = v.measured_velocity ?? v.views_per_hour;
        const durTxt = v.duration_sec ? `${Math.floor(v.duration_sec / 60)}:${String(v.duration_sec % 60).padStart(2, "0")}` : "—";
        
        // Badge de antigüedad visual
        const ageHours = Number(v.hours_old ?? (v.published_at ? Math.max(1, (Date.now() - new Date(v.published_at).getTime()) / 3600000) : 24));
        let ageBadge = "";
        if (ageHours <= 24) {
            ageBadge = `<span title="Publicado en las últimas 24h" style="color: #38bdf8; font-weight:600;">🔥 Hace ${Math.round(ageHours)}h</span>`;
        } else if (ageHours <= 72) {
            ageBadge = `<span title="Publicado hace 1 a 3 días" style="color: #c084fc; font-weight:500;">⚡ Hace ${Math.round(ageHours / 24)}d</span>`;
        } else {
            ageBadge = `<span title="En tendencia continuada (+3 días)" style="color: #94a3b8;">📅 Hace ${Math.round(ageHours / 24)}d</span>`;
        }

        meta.innerHTML =
            `<span>${v.region_flag} ${esc(v.region)}</span>` +
            `<span title="Categoría del video">${v.category_emoji || "🔥"} ${esc(v.category || "viral")}</span>` +
            ageBadge +
            `<span title="Duración del original">⏱ ${durTxt}${v.is_short ? " (Short)" : ""}</span>` +
            `<span>👁 ${fmtViews(v.views)} vistas</span>` +
            `<span class="radar-hot" title="Velocidad: vistas por hora">⚡ ${fmtViews(velocity)}/h</span>` +
            `<span>❤️ ${(v.like_ratio * 100).toFixed(1)}%</span>`;
        body.append(title, meta);

        // Score
        const scoreBox = document.createElement("div");
        scoreBox.className = "radar-score-box";
        scoreBox.innerHTML =
            `<span class="radar-score-num ${v.score >= 70 ? "hot" : v.score >= 45 ? "warm" : ""}">${v.score}</span>` +
            `<span class="radar-score-label">SCORE</span>`;
        scoreBox.append(scoreBar(v.score));

        // Botón replicar: primero la IA analiza y propone enfoques
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "radar-replicate-btn";
        btn.title = "La IA analiza el original, propone enfoques y tú eliges qué producir";
        btn.innerHTML = `<span>⚡ Replicar 🇪🇸</span>`;
        btn.addEventListener("click", () => openStrategyModal(v));

        row.append(rankBox, thumbWrap, body, scoreBox, btn);
        list.append(row);
    });
}

function scoreBar(score) {
    const wrap = document.createElement("div");
    wrap.className = "radar-score-bar";
    const fill = document.createElement("div");
    fill.className = "radar-score-fill";
    fill.style.width = `${Math.max(4, Math.min(100, score))}%`;
    wrap.append(fill);
    return wrap;
}

/* ------------------------------------------------------------- favoritos y temas */

let topicFavorites = [];

function getTopicKey(t) {
    return (t?.title || "").trim().toLowerCase();
}

function isTopicFavorited(t) {
    const key = getTopicKey(t);
    return topicFavorites.some(f => getTopicKey(f) === key);
}

async function loadFavorites() {
    try {
        const cached = localStorage.getItem("radar_topic_favorites");
        if (cached) {
            topicFavorites = JSON.parse(cached);
            updateFavoritesCount();
        }
    } catch {}

    try {
        const res = await fetch("/api/trend-radar/favorites");
        if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data.favorites)) {
                topicFavorites = data.favorites;
                try { localStorage.setItem("radar_topic_favorites", JSON.stringify(topicFavorites)); } catch {}
                updateFavoritesCount();
            }
        }
    } catch (e) {
        console.warn("No se pudieron cargar favoritos del servidor:", e);
    }
}

async function toggleFavoriteTopic(topic) {
    const key = getTopicKey(topic);
    const index = topicFavorites.findIndex(f => getTopicKey(f) === key);
    let isFav = false;
    if (index >= 0) {
        topicFavorites.splice(index, 1);
        toast(`Quitado de favoritos: «${topic.title?.slice(0, 35)}…»`, "info");
    } else {
        const itemToSave = { ...topic, saved_at: new Date().toISOString() };
        topicFavorites.unshift(itemToSave);
        isFav = true;
        toast(`⭐ Guardado en Favoritos: «${topic.title?.slice(0, 35)}…»`, "success");
    }

    try { localStorage.setItem("radar_topic_favorites", JSON.stringify(topicFavorites)); } catch {}
    updateFavoritesCount();
    renderTopics();

    try {
        await fetch("/api/trend-radar/favorites", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: isFav ? "add" : "remove", topic })
        });
    } catch (e) {
        console.warn("No se pudo sincronizar favoritos con el servidor:", e);
    }
}

function updateFavoritesCount() {
    const count = topicFavorites.length;
    const badge = $("radarFavCountBadge");
    if (badge) badge.textContent = count;
}

const topicFilterState = {
    view: "all", // "all" | "favorites"
    category: "all",
    search: "",
};

function getFilteredTopics() {
    let list = topicFilterState.view === "favorites" ? [...topicFavorites] : (data?.topics || []);

    // 1. Filtrar por categoría de tema
    if (topicFilterState.category && topicFilterState.category !== "all") {
        const catTarget = topicFilterState.category.toLowerCase();
        list = list.filter(t => {
            const cat = (t.category || "").toLowerCase();
            const title = (t.title || "").toLowerCase();
            const angle = (t.angle || "").toLowerCase();
            const why = (t.why || "").toLowerCase();
            const full = `${cat} ${title} ${angle} ${why}`;

            if (catTarget === "divulgacion") {
                return cat.includes("descubrimiento") || cat.includes("concepto") || cat.includes("ciencia") || full.includes("ciencia") || full.includes("descubrimiento") || full.includes("estudio");
            }
            if (catTarget === "tecnologia") {
                return cat.includes("tecnologia") || full.includes("ia") || full.includes("inteligencia artificial") || full.includes("tecnolog");
            }
            if (catTarget === "espacio") {
                return cat.includes("espacio") || full.includes("espacio") || full.includes("luna") || full.includes("marte") || full.includes("nasa") || full.includes("universo");
            }
            if (catTarget === "noticias") {
                return cat.includes("urgente") || cat.includes("noticias") || full.includes("urgente") || full.includes("última hora");
            }
            if (catTarget === "arqueologia") {
                return cat.includes("arqueologia") || cat.includes("misterio") || full.includes("arqueolog") || full.includes("misterio") || full.includes("hallazgo");
            }
            if (catTarget === "salud") {
                return cat.includes("salud") || full.includes("médic") || full.includes("salud") || full.includes("cuerpo") || full.includes("cerebro");
            }
            if (catTarget === "entretenimiento") {
                return cat.includes("entretenimiento") || cat.includes("viral") || full.includes("viral");
            }
            return full.includes(catTarget);
        });
    }

    // 2. Filtrar por búsqueda libre
    if (topicFilterState.search && topicFilterState.search.trim().length > 0) {
        const q = topicFilterState.search.trim().toLowerCase();
        list = list.filter(t => {
            return (t.title || "").toLowerCase().includes(q) ||
                   (t.why || "").toLowerCase().includes(q) ||
                   (t.angle || "").toLowerCase().includes(q) ||
                   (t.category || "").toLowerCase().includes(q);
        });
    }

    return list;
}

function updateTopicFilterStatus(shownCount, totalCount) {
    const countEl = $("radarTopicFilterCount");
    const resetBtn = $("radarTopicFilterResetBtn");
    const searchClear = $("radarTopicSearchClearBtn");

    const isFiltered = topicFilterState.category !== "all" || 
                       topicFilterState.search.trim().length > 0;

    if (countEl) {
        if (topicFilterState.view === "favorites") {
            countEl.textContent = isFiltered ? `Mostrando ${shownCount} de ${totalCount} favoritos` : `${totalCount} favoritos guardados`;
        } else {
            countEl.textContent = isFiltered ? `Mostrando ${shownCount} de ${totalCount} temas` : `${totalCount} temas analizados`;
        }
    }

    if (resetBtn) resetBtn.hidden = !isFiltered;
    if (searchClear) searchClear.hidden = !(topicFilterState.search.trim().length > 0);
}

function renderTopics() {
    const grid = $("radarTopicsGrid");
    if (!grid) return;
    grid.replaceChildren();

    const isFavView = topicFilterState.view === "favorites";
    const allTopics = isFavView ? [...topicFavorites] : (data?.topics || []);
    const filteredTopics = getFilteredTopics();

    updateTopicFilterStatus(filteredTopics.length, allTopics.length);
    updateFavoritesCount();

    if (isFavView && !allTopics.length) {
        const empty = document.createElement("div");
        empty.className = "radar-empty";
        empty.style.gridColumn = "1 / -1";
        empty.innerHTML = `<span style="font-size:32px;">⭐</span>
            <strong>No tienes temas guardados en Favoritos todavía</strong>
            <span>Explora la pestaña «Temas sin video» y haz clic en el botón ⭐ Guardar de cualquier tarjeta para tenerlo a mano y producirlo cuando quieras.</span>`;
        grid.append(empty);
        return;
    }

    if (!allTopics.length) {
        const empty = document.createElement("div");
        empty.className = "radar-empty";
        empty.style.gridColumn = "1 / -1";
        empty.innerHTML = `<span style="font-size:28px;">🚨</span><strong>Sin temas urgentes aún</strong>
            <span>El barrido de noticias + análisis IA todavía no devuelve candidatos.</span>`;
        grid.append(empty);
        return;
    }

    if (!filteredTopics.length) {
        const empty = document.createElement("div");
        empty.className = "radar-empty";
        empty.style.gridColumn = "1 / -1";
        empty.innerHTML = `<span style="font-size:28px;">🔍</span><strong>Sin temas que coincidan con los filtros</strong>
            <span>Prueba cambiando la categoría seleccionada o el término de búsqueda.</span>`;
        grid.append(empty);
        return;
    }

    filteredTopics.forEach((t, idx) => {
        const card = document.createElement("article");
        card.className = "radar-topic-card";

        const isFav = isTopicFavorited(t);

        const head = document.createElement("div");
        head.className = "radar-topic-head";
        head.innerHTML =
            `<span class="radar-topic-score ${t.score >= 80 ? "hot" : t.score >= 60 ? "warm" : ""}" title="Fuerza de viralidad estimada por la IA">${t.score}</span>
             <div class="radar-topic-chips">
                 <div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">
                     <span class="radar-chip cat">${esc(t.category)}</span>
                     <span class="radar-chip ${t.urgency >= 8 ? "urg-high" : t.urgency >= 5 ? "urg-mid" : "urg-low"}" title="Urgencia de publicación">⚡ ${t.urgency}/10</span>
                     ${idx === 0 && !isFavView ? `<span class="radar-chip top1">#1 OPORTUNIDAD</span>` : ""}
                     ${isFav ? `<span class="radar-chip fav">⭐ GUARDADO</span>` : ""}
                 </div>
             </div>`;

        // Botón de Favorito interactivo
        const favBtn = document.createElement("button");
        favBtn.type = "button";
        favBtn.className = `radar-topic-fav-btn ${isFav ? "active" : ""}`;
        favBtn.title = isFav ? "Quitar de favoritos" : "Guardar en favoritos para otro día";
        favBtn.innerHTML = isFav ? `<span>⭐ Guardado</span>` : `<span>☆ Guardar</span>`;
        favBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            toggleFavoriteTopic(t);
        });
        head.append(favBtn);

        head.append(scoreBar(t.score));

        const title = document.createElement("h4");
        title.className = "radar-topic-title";
        title.textContent = t.title;

        const why = document.createElement("p");
        why.className = "radar-topic-why";
        why.innerHTML = `<strong>Por qué explota:</strong> ${esc(t.why)}`;

        const angle = document.createElement("p");
        angle.className = "radar-topic-angle";
        angle.innerHTML = `<strong>Ángulo para KAI:</strong> ${esc(t.angle)}`;

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "radar-replicate-btn wide";
        btn.innerHTML = `<span>🎬 Producir con KAI ahora</span>`;
        btn.addEventListener("click", () => openStrategyModal(t, "topic"));

        card.append(head, title, why, angle, btn);
        grid.append(card);
    });
}

/* ------------------------------------------------------------- réplica KAI */

let strategyCtx = null; // { item, kind, choice, auto } del modal de estrategia

async function openStrategyModal(item, kind = "video") {
    const modal = $("radarStrategyModal");
    if (!modal) { replicate(null, kind, item); return; }
    strategyCtx = { item, kind, choice: null, auto: null };
    modal.hidden = false;
    if ($("radarStrategyTitle")) $("radarStrategyTitle").textContent = item.title || (kind === "topic" ? "Tema urgente" : "Video viral");
    if ($("radarStrategySub")) {
        if (kind === "topic") {
            $("radarStrategySub").textContent = `⚡ Urgencia: ${item.urgency || 8}/10 · 🔥 Viralidad: ${item.score || 80}/100 · 🏷️ ${item.category || "urgente"}`;
        } else {
            $("radarStrategySub").textContent = `${item.region_flag || ""} ${item.channel || ""} · ${item.category_emoji || ""} ${item.category || ""} · ${fmtViews(item.views)} vistas`;
        }
    }
    if ($("radarStrategyLoading")) $("radarStrategyLoading").hidden = false;
    if ($("radarStrategyAnalysis")) $("radarStrategyAnalysis").hidden = true;
    if ($("radarStrategyCustom")) $("radarStrategyCustom").hidden = true;
    if ($("radarStrategyInstructions")) $("radarStrategyInstructions").value = "";
    if ($("radarStrategyOptions")) $("radarStrategyOptions").replaceChildren();
    const produceBtn = $("radarStrategyProduceBtn");
    if (produceBtn) { produceBtn.disabled = true; produceBtn.innerHTML = `<span>🧠 Calculando estrategia y duración óptima…</span>`; }

    try {
        const res = await fetch("/api/trend-radar/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind, item }),
        });
        const analysis = await res.json();
        if (!res.ok) throw new Error(analysis.detail || "El análisis falló.");
        renderStrategy(analysis);
    } catch (err) {
        closeStrategyModal();
        toast(`Estrategia: ${err.message}`, "error");
    }
}

function renderStrategy(analysis) {
    if ($("radarStrategyLoading")) $("radarStrategyLoading").hidden = true;
    const why = $("radarStrategyWhy");
    const aud = $("radarStrategyAudience");
    if (why) why.innerHTML = `<strong style="color:#e2e8f0;">📊 Por qué funciona:</strong> ${esc(analysis.why_works || "")}`;
    if (aud) aud.innerHTML = `🎯 <strong>Audiencia:</strong> ${esc(analysis.audience || "")}`;
    if ($("radarStrategyAnalysis")) $("radarStrategyAnalysis").hidden = false;

    const wrap = $("radarStrategyOptions");
    if (!wrap) return;
    wrap.replaceChildren();

    const select = (card, choice) => {
        wrap.querySelectorAll(".radar-option-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        strategyCtx.choice = choice;
    };

    // Opción "la IA decide": usa el enfoque de mayor puntaje de viralidad.
    const autoCard = document.createElement("button");
    autoCard.type = "button";
    autoCard.className = "radar-option-card selected";
    const recommended = (analysis.options || []).find(o => o.recommended)
        || (analysis.options || []).slice().sort((a, b) => (b.viral_estimate || 0) - (a.viral_estimate || 0))[0];
    if (recommended) strategyCtx.auto = recommended;
    const autoDurTxt = recommended?.duration_sec ? `${Math.floor(recommended.duration_sec / 60)}m ${recommended.duration_sec % 60 ? (recommended.duration_sec % 60) + 's' : ''}` : "";
    autoCard.innerHTML = `
        <div class="radar-option-head">
            <span class="radar-chip cat" style="background:rgba(168,85,247,.2); color:#c084fc;">✨ IA DECIDE (MAYOR PUNTAJE)</span>
            ${recommended ? `<span class="radar-chip urg-high">⭐ ${esc(recommended.format || "recomendado")} · ${recommended.viral_estimate} pts</span>` : ""}
        </div>
        <strong class="radar-option-title">Que la IA produzca el enfoque de mayor impacto y retención</strong>
        <span class="radar-option-pitch">${recommended ? `Irá con: «${esc(recommended.title)}» · ⏱️ ${autoDurTxt} (${recommended.duration_sec}s)` : "Estrategia profunda óptima calculada"}</span>`;
    autoCard.addEventListener("click", () => select(autoCard, null));
    wrap.append(autoCard);

    (analysis.options || []).forEach(opt => {
        const card = document.createElement("button");
        card.type = "button";
        card.className = "radar-option-card";
        const durMin = opt.duration_sec ? `${Math.floor(opt.duration_sec / 60)}m ${opt.duration_sec % 60 ? (opt.duration_sec % 60) + 's' : ''}` : "";
        card.innerHTML = `
            <div class="radar-option-head">
                <span class="radar-chip cat">${esc(opt.format || "enfoque")}</span>
                <span class="radar-chip ${opt.viral_estimate >= 80 ? "urg-high" : opt.viral_estimate >= 60 ? "urg-mid" : "urg-low"}">🔥 ${opt.viral_estimate}</span>
                <span class="radar-chip top1" style="margin-left:auto;">⏱ ${durMin} (${opt.duration_sec}s)</span>
            </div>
            <strong class="radar-option-title">${esc(opt.title)}</strong>
            <span class="radar-option-pitch">${esc(opt.pitch)}</span>
            <div class="radar-score-bar"><div class="radar-score-fill" style="width:${Math.max(6, Math.min(100, opt.viral_estimate))}%;"></div></div>`;
        card.addEventListener("click", () => select(card, opt));
        wrap.append(card);
    });

    if ($("radarStrategyCustom")) $("radarStrategyCustom").hidden = false;
    const produceBtn = $("radarStrategyProduceBtn");
    if (produceBtn) { produceBtn.disabled = false; produceBtn.innerHTML = `<span>🎬 Producir con KAI</span>`; }
}

function closeStrategyModal() {
    const modal = $("radarStrategyModal");
    if (modal) modal.hidden = true;
}

async function produceFromStrategy(btn) {
    if (!strategyCtx) return;
    const instructions = $("radarStrategyInstructions")?.value?.trim() || "";
    // "IA decide" (choice null) usa el enfoque de mayor puntaje detectado.
    const choice = strategyCtx.choice || strategyCtx.auto;
    const kind = strategyCtx.kind || "video";
    closeStrategyModal();
    await replicate(btn, kind, strategyCtx.item, { choice, instructions });
}

async function replicate(btn, kind, item, extra = {}) {
    if (btn?.dataset?.busy) return;
    if (btn) { btn.dataset.busy = "1"; btn.style.opacity = ".55"; }
    const original = btn?.innerHTML;
    if (btn) btn.innerHTML = `<span>🧠 Diseñando réplica…</span>`;
    try {
        const res = await fetch("/api/trend-radar/replicate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ kind, item, ...extra }), // la IA elige formato y duración
        });
        const out = await res.json();
        if (!res.ok) throw new Error(out.detail || "No se pudo preparar la réplica.");
        toast(`🚀 KAI está produciendo: «${out.topic}»`, "success");
        if (typeof window.__startRadarTask === "function") {
            window.__startRadarTask(out.task_id, out.topic);
        }
        load(); // refrescar temas (el producido se descuenta)
    } catch (err) {
        toast(`Error al replicar: ${err.message}`, "error");
        if (btn) btn.innerHTML = original;
    } finally {
        if (btn) { btn.style.opacity = "1"; delete btn.dataset.busy; }
    }
}

/* --------------------------------------------------------------- datos/poll */

function renderUnavailable(message) {
    const list = $("radarVideosList");
    const grid = $("radarTopicsGrid");
    const badge = $("radarUpdatedBadge");
    const box = document.createElement("div");
    box.className = "radar-empty";
    box.innerHTML = `<span style="font-size:30px;">📡</span>
        <strong>Radar no disponible ahora</strong>
        <span>${esc(message)}</span>`;
    if (list) { list.replaceChildren(box.cloneNode(true)); }
    if (grid) { grid.replaceChildren(box.cloneNode(true)); }
    if (badge) badge.textContent = "Sin conexión con el radar";
}

async function load({ silent = true } = {}) {
    try {
        const res = await fetch("/api/trend-radar");
        if (!res.ok) {
            throw new Error(res.status === 404
                ? "El servidor está corriendo código anterior. Detén uvicorn (Ctrl+C), vuelve a arrancarlo con «uvicorn server:app --port 8000» y recarga esta página (Ctrl+F5)."
                : `El radar respondió HTTP ${res.status}. Revisa la consola del servidor.`);
        }
        data = await res.json();
        renderVideos();
        renderTopics();
        renderUpdatedBadge();
    } catch (err) {
        if (!silent) toast(`Radar: ${err.message}`, "error");
        renderUnavailable(err.message || "Error de conexión con el servidor.");
    }
}

export function initTrendRadar() {
    // Cargar favoritos guardados (localStorage + backend)
    loadFavorites();

    document.querySelectorAll("[data-radar-tab]").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll("[data-radar-tab]").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentTab = btn.dataset.radarTab;
            const videos = $("radarVideosPane");
            const topics = $("radarTopicsPane");

            if (currentTab === "videos") {
                if (videos) videos.hidden = false;
                if (topics) topics.hidden = true;
            } else if (currentTab === "topics") {
                if (videos) videos.hidden = true;
                if (topics) topics.hidden = false;
                topicFilterState.view = "all";
                const viewSel = $("radarTopicViewFilter");
                if (viewSel) viewSel.value = "all";
                renderTopics();
            } else if (currentTab === "favorites") {
                if (videos) videos.hidden = true;
                if (topics) topics.hidden = false;
                topicFilterState.view = "favorites";
                const viewSel = $("radarTopicViewFilter");
                if (viewSel) viewSel.value = "favorites";
                renderTopics();
            }
        });
    });

    $("radarRefreshBtn")?.addEventListener("click", async () => {
        try {
            await fetch("/api/trend-radar/refresh", { method: "POST" });
            toast("📡 Barriendo charts y noticias… listo en ~1 min.", "info");
            if ($("radarUpdatedBadge")) $("radarUpdatedBadge").textContent = "🔄 Barriendo charts + IA ahora…";
        } catch {
            toast("No se pudo iniciar el refresco.", "error");
        }
    });

    // Revisión silenciosa cada 2 min mientras la pestaña exista.
    pollTimer = setInterval(() => {
        const section = $("trendRadarSection");
        if (section && !section.hidden) load();
    }, 2 * 60 * 1000);

    // Modal de estrategia: cerrar y producir
    $("radarStrategyCloseBtn")?.addEventListener("click", closeStrategyModal);
    $("radarStrategyModal")?.addEventListener("click", (e) => {
        if (e.target.id === "radarStrategyModal") closeStrategyModal();
    });
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !$("radarStrategyModal")?.hidden) closeStrategyModal();
    });
    $("radarStrategyProduceBtn")?.addEventListener("click", (e) => produceFromStrategy(e.currentTarget));

    // Countdown del badge cada 30 s.
    countdownTimer = setInterval(renderUpdatedBadge, 30_000);

    // Filtros interactivos de Videos Virales
    $("radarCategoryFilter")?.addEventListener("change", (e) => {
        filterState.category = e.target.value;
        renderVideos();
    });

    $("radarRegionFilter")?.addEventListener("change", (e) => {
        filterState.region = e.target.value;
        renderVideos();
    });

    $("radarRecencyFilter")?.addEventListener("change", (e) => {
        filterState.recency = e.target.value;
        renderVideos();
    });

    $("radarSearchInput")?.addEventListener("input", (e) => {
        filterState.search = e.target.value;
        renderVideos();
    });

    $("radarSearchClearBtn")?.addEventListener("click", () => {
        filterState.search = "";
        const input = $("radarSearchInput");
        if (input) input.value = "";
        renderVideos();
    });

    $("radarFilterResetBtn")?.addEventListener("click", () => {
        filterState.category = "all";
        filterState.region = "all";
        filterState.recency = "all";
        filterState.search = "";
        const cat = $("radarCategoryFilter");
        const reg = $("radarRegionFilter");
        const rec = $("radarRecencyFilter");
        const inp = $("radarSearchInput");
        if (cat) cat.value = "all";
        if (reg) reg.value = "all";
        if (rec) rec.value = "all";
        if (inp) inp.value = "";
        renderVideos();
    });

    // Filtros interactivos de Temas & Favoritos
    $("radarTopicViewFilter")?.addEventListener("change", (e) => {
        topicFilterState.view = e.target.value;
        document.querySelectorAll("[data-radar-tab]").forEach(b => {
            if (e.target.value === "favorites") {
                b.classList.toggle("active", b.dataset.radarTab === "favorites");
            } else {
                b.classList.toggle("active", b.dataset.radarTab === "topics");
            }
        });
        renderTopics();
    });

    $("radarTopicCategoryFilter")?.addEventListener("change", (e) => {
        topicFilterState.category = e.target.value;
        renderTopics();
    });

    $("radarTopicSearchInput")?.addEventListener("input", (e) => {
        topicFilterState.search = e.target.value;
        renderTopics();
    });

    $("radarTopicSearchClearBtn")?.addEventListener("click", () => {
        topicFilterState.search = "";
        const input = $("radarTopicSearchInput");
        if (input) input.value = "";
        renderTopics();
    });

    $("radarTopicFilterResetBtn")?.addEventListener("click", () => {
        topicFilterState.category = "all";
        topicFilterState.search = "";
        const cat = $("radarTopicCategoryFilter");
        const inp = $("radarTopicSearchInput");
        if (cat) cat.value = "all";
        if (inp) inp.value = "";
        renderTopics();
    });

    load();

    return { load };
}

/**
 * AetherCut / Prism Studio - Projects Library Module
 */
import { $ } from "./utils.js";

export function createProjectsManager({ onOpenProject, onOpenModal }) {
    let allLoadedProjects = [];
    let currentProjectSearch = "";
    let currentProjectFilter = "all";

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

        const filtered = allLoadedProjects.filter(p => {
            const matchesSearch = !currentProjectSearch || 
                (p.name || "").toLowerCase().includes(currentProjectSearch.toLowerCase()) || 
                (p.topic || "").toLowerCase().includes(currentProjectSearch.toLowerCase());
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

            const thumbWrap = document.createElement("div");
            thumbWrap.className = "yt-card-thumb-wrap";

            if (project.thumbnail_url) {
                const img = document.createElement("img");
                img.className = "yt-card-thumb-img";
                img.src = project.thumbnail_url;
                img.alt = project.name || "Video thumbnail";
                img.loading = "lazy";
                thumbWrap.append(img);
            } else {
                const thumbFallback = document.createElement("div");
                thumbFallback.className = "yt-card-thumb-fallback";
                thumbFallback.innerHTML = `<span>🎬 Video KAI</span>`;
                thumbWrap.append(thumbFallback);
            }

            const durBadge = document.createElement("span");
            durBadge.className = "yt-card-duration-badge";
            durBadge.textContent = project.duration ? formatDurationSecs(project.duration) : "05:00";
            thumbWrap.append(durBadge);

            const body = document.createElement("div");
            body.className = "yt-card-body";

            const title = document.createElement("h4");
            title.className = "yt-card-title";
            title.textContent = project.name || project.topic || "Producción KAI";

            const metaLine = document.createElement("div");
            metaLine.className = "yt-card-meta-line";
            const st = (project.status || "done").toLowerCase();
            metaLine.innerHTML = `<span style="font-size:11px; color:#38bdf8;">${st === "done" ? "Listo" : "En curso"}</span>`;

            body.append(title, metaLine);
            card.append(thumbWrap, body);

            card.addEventListener("click", () => {
                if (onOpenModal) onOpenModal(project);
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
            if ($("tabModeProjects")?.classList.contains("active") && card) {
                card.hidden = false;
            }
            renderProjectsGrid();
        } catch { /* ignorar fallo de red */ }
    }

    // Bindings de búsqueda y filtros
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

    return {
        loadSavedProjects,
        renderProjectsGrid,
    };
}

import { useEffect, useState, useRef } from "react";
import { useEditor } from "@/lib/store";
import { PLATFORMS } from "@/lib/data";
import { Hairline, IconButton } from "./ui";
import {
  IconChevron,
  IconDownload,
  IconRedo,
  IconUndo,
  IconSparkle,
  IconMenu,
  IconClose,
  IconShare,
  IconLayers,
  IconPlus,
} from "./Icons";
import { ExportModal } from "./ExportModal";
import { ProjectDetailsModal } from "./ProjectDetailsModal";
import { ClipsModal } from "./ClipsModal";
import { AutopilotModal } from "./AutopilotModal";
import { MultiChannelPublishModal } from "./MultiChannelPublishModal";
import { cn } from "@/utils/cn";

function Mark() {
  return (
    <div className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/[0.03] text-white/80">
      <svg viewBox="0 0 24 24" className="h-4 w-4">
        <circle cx="12" cy="12" r="7.2" fill="none" stroke="currentColor" strokeWidth="1.2" opacity=".4" />
        <path d="M12 4.8V12l5.2 3" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="12" cy="12" r="1.6" fill="currentColor" opacity=".9" />
      </svg>
    </div>
  );
}

export function TopBar() {
  const {
    platform,
    setPlatform,
    projects,
    activeProjectId,
    activeProjectTitle,
    selectProject,
    exportMaster,
    exportProgress,
    duration,
    ratio,
    subtitleStyle,
    overlays,
    mobileMenuOpen,
    setMobileMenuOpen,
    leftPanelCollapsed,
    toggleLeftPanel,
    setImportModalOpen,
  } = useEditor();
  const [projectOpen, setProjectOpen] = useState(false);
  const [actionsOpen, setActionsOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [clipsOpen, setClipsOpen] = useState(false);
  const [autopilotOpen, setAutopilotOpen] = useState(false);
  const [autopilotOn, setAutopilotOn] = useState(false);
  const [multiChannelOpen, setMultiChannelOpen] = useState(false);

  // Indicador discreto de si el piloto automático está activo
  useEffect(() => {
    let alive = true;
    const check = () =>
      fetch("/api/autopilot/status")
        .then((r) => (r.ok ? r.json() : null))
        .then((s) => alive && s && setAutopilotOn(Boolean(s.config?.enabled)))
        .catch(() => {});
    check();
    const t = window.setInterval(check, 20000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, [autopilotOpen]);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setProjectOpen(false);
        setActionsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleExportClick = () => {
    if (exportProgress !== null && exportProgress < 100) return;
    setModalOpen(true);
  };

  const handleModalConfirm = (opts: {
    burnSubtitles: boolean;
    resolution: "1080p" | "4k" | "720p";
    fps: 30 | 60;
    title: string;
  }) => {
    setModalOpen(false);
    exportMaster({
      burnSubtitles: opts.burnSubtitles,
      style: subtitleStyle,
      title: opts.title,
    });
  };

  const openCopilot = () => {
    const copilot = (window as any).agentCopilot;
    if (copilot) {
      if (typeof copilot.toggle === "function") {
        copilot.toggle();
      } else if (typeof copilot.open === "function") {
        copilot.open();
      }
    } else {
      const fab = document.getElementById("agentFabLauncher");
      if (fab) fab.click();
    }
  };

  return (
    <header className="relative z-30 shrink-0">
      <div className="flex h-14 items-center gap-3 border-b border-white/[0.08] bg-black px-3 sm:gap-4 sm:px-4">
        {/* Mobile Hamburger menu toggle */}
        <button
          type="button"
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-white/80 hover:text-white hover:bg-white/[0.08] md:hidden shrink-0"
          title={mobileMenuOpen ? "Cerrar menú" : "Abrir menú de herramientas y proyectos"}
        >
          {mobileMenuOpen ? <IconClose className="h-4 w-4" /> : <IconMenu className="h-4 w-4" />}
        </button>

        {/* brand */}
        <div className="flex items-center gap-3">
          <Mark />
          <div className="hidden sm:block">
            <div className="flex items-baseline gap-1.5">
              <span className="text-[13px] font-medium tracking-[0.2em] text-white">LUMEN</span>
              <span className="serif-display text-[15px] italic leading-none text-white/90">studio</span>
            </div>
            <div className="micro-sm mt-1 text-white/25">Neural video suite · v4.2</div>
          </div>
          <button
            type="button"
            onClick={toggleLeftPanel}
            className={cn(
              "hidden md:grid h-8 w-8 place-items-center rounded-xl border transition-all duration-200 shrink-0 ml-1",
              leftPanelCollapsed
                ? "border-white/25 bg-white/[0.10] text-white shadow-sm"
                : "border-white/10 bg-white/[0.04] text-white/50 hover:text-white hover:bg-white/[0.08]",
            )}
            title={leftPanelCollapsed ? "Expandir menú de herramientas (Ctrl+B)" : "Ocultar menú lateral (Ctrl+B)"}
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
              <path d={leftPanelCollapsed ? "M14 9l3 3-3 3" : "M16 15l-3-3 3-3"} />
            </svg>
          </button>
        </div>

        <div className="mx-1 hidden h-6 w-px bg-white/[0.07] md:block" />

        {/* project selector & actions */}
        <div className="relative hidden items-center gap-1.5 md:flex" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setProjectOpen(!projectOpen)}
            className="group min-w-0 flex items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.02] px-2.5 py-1.5 transition-colors hover:border-white/15 hover:bg-white/[0.05]"
            title="Seleccionar proyecto"
          >
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-signal-400 anim-ping" />
            <span className="max-w-[180px] truncate text-[11px] text-white/80">
              {activeProjectTitle || "Ritmo Nocturno — EP.02"}
            </span>
            <span className="micro-sm shrink-0 text-white/30">
              {activeProjectId ? "En vivo" : "Autoguardado"}
            </span>
            <IconChevron
              className={cn(
                "h-3 w-3 text-white/30 transition-transform duration-200",
                projectOpen && "rotate-180 text-white/70",
              )}
            />
          </button>

          {/* acciones del proyecto: menú expandible */}
          {activeProjectId && (
            <div className="relative">
              <button
                type="button"
                onClick={() => setActionsOpen((o) => !o)}
                aria-expanded={actionsOpen}
                className={cn(
                  "flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-[11px] transition-all",
                  actionsOpen
                    ? "border-white/20 bg-white/[0.08] text-white"
                    : "border-white/[0.08] bg-white/[0.02] text-white/70 hover:border-white/15 hover:text-white",
                )}
              >
                <span>Proyecto</span>
                <IconChevron
                  className={cn("h-3 w-3 transition-transform duration-200", actionsOpen && "rotate-180 text-white")}
                />
              </button>
              {actionsOpen && (
                <div className="absolute left-0 top-full z-50 mt-1.5 w-56 overflow-hidden rounded-xl border border-white/10 bg-black/95 p-1 shadow-[0_16px_40px_rgba(0,0,0,0.9)] backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150">
                  <button
                    type="button"
                    onClick={() => {
                      setDetailsOpen(true);
                      setActionsOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[11px] text-white/75 hover:bg-white/[0.08] hover:text-white transition-colors"
                    title="Ver y copiar título, descripción y hashtags para redes"
                  >
                    <IconShare className="h-3.5 w-3.5 text-white/60" />
                    <span>Info y redes</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setClipsOpen(true);
                      setActionsOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-[11px] text-white/75 hover:bg-white/[0.08] hover:text-white transition-colors"
                    title="Ver, reproducir y descargar los Reels y Shorts 9:16 extraídos de este video"
                  >
                    <IconLayers className="h-3.5 w-3.5 text-white/60" />
                    <span>Reels 9:16</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {projectOpen && (
            <div className="absolute left-0 top-full z-50 mt-1.5 w-72 overflow-hidden rounded-xl border border-white/10 bg-black/95 p-1.5 shadow-[0_20px_50px_rgba(0,0,0,0.9)] backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150">
              <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06]">
                <span className="micro-sm text-white/40 font-semibold tracking-wider uppercase">
                  Proyectos en Servidor
                </span>
                <span className="tnum text-[10px] text-beam-200">{projects.length}</span>
              </div>
              <div className="max-h-64 overflow-y-auto py-1">
                {projects.length === 0 ? (
                  <div className="px-3 py-4 text-center text-[11px] text-white/35">
                    No hay proyectos en el servidor aún.
                  </div>
                ) : (
                  projects.map((p) => {
                    const isCurrent = activeProjectId === p.id;
                    return (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => {
                          selectProject(p.id);
                          setProjectOpen(false);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors",
                          isCurrent
                            ? "border border-beam-400/30 bg-beam-500/15 text-white"
                            : "text-white/70 hover:bg-white/[0.05] hover:text-white",
                        )}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-[11px] font-medium text-white/90">
                            {p.name}
                          </div>
                          <div className="micro-sm mt-0.5 text-white/30">
                            {p.status} · {p.duration ? `${Math.round(p.duration)}s` : "En proceso"}
                          </div>
                        </div>
                        {isCurrent && (
                          <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-signal-400" />
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex-1" />

        {/* platform picker */}
        <div className="hidden items-center gap-0.5 rounded-lg border border-white/[0.08] bg-black p-0.5 sm:flex">
          {PLATFORMS.map((p) => (
            <button
              key={p.id}
              onClick={() => setPlatform(p.id)}
              className={
                "rounded-md px-2.5 py-[6px] text-[10px] font-medium tracking-wide transition-colors duration-200 " +
                (platform === p.id
                  ? "bg-beam-500 text-white"
                  : "text-white/35 hover:text-white/70")
              }
            >
              {p.name}
            </button>
          ))}
        </div>

        {/* history */}
        <div className="hidden items-center gap-1 md:flex">
          <IconButton size="sm" title="Deshacer">
            <IconUndo className="h-3.5 w-3.5" />
          </IconButton>
          <IconButton size="sm" title="Rehacer">
            <IconRedo className="h-3.5 w-3.5" />
          </IconButton>
        </div>

        {/* Botón de Descarga / Exportar Principal: sutil, sin verde chillón, borde fino y ancho estable */}
        <button
          type="button"
          onClick={handleExportClick}
          disabled={exportProgress !== null && exportProgress < 100}
          title="Descargar video máster en MP4 a tu computadora"
          className="relative flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-[11px] font-medium text-white/80 transition-colors hover:border-white/20 hover:bg-white/[0.08] hover:text-white disabled:cursor-not-allowed disabled:opacity-70 active:scale-95 cursor-pointer"
        >
          {exportProgress !== null && exportProgress < 100 ? (
            <>
              <svg className="h-3.5 w-3.5 animate-spin text-beam-300 shrink-0" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Descargando...</span>
            </>
          ) : (
            <>
              <IconDownload className="h-3.5 w-3.5 text-white/60 shrink-0" />
              <span>Descargar</span>
            </>
          )}
        </button>

        {/* Import button */}
        <button
          type="button"
          onClick={() => setImportModalOpen(true)}
          title="Importar video o enlace URL (YouTube/Web)"
          className="relative hidden h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.04] px-2.5 text-[11px] font-medium text-white/80 transition-colors hover:border-white/20 hover:bg-white/[0.08] hover:text-white sm:flex cursor-pointer"
        >
          <IconPlus className="h-3.5 w-3.5" />
          <span>Importar</span>
        </button>

        {/* Piloto automático */}
        <button
          type="button"
          onClick={() => setAutopilotOpen(true)}
          title="Piloto automático: crea y publica videos solo"
          className="relative hidden h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-white/10 bg-white/[0.04] px-2 text-[11px] font-medium text-white/70 transition-colors hover:border-white/20 hover:bg-white/[0.08] hover:text-white md:flex cursor-pointer"
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", autopilotOn ? "bg-signal-400" : "bg-white/25")} />
          <span className="hidden xl:inline">Piloto</span>
        </button>

        {/* Multi-Channel Distribution button (replaces shortcuts button as requested) */}
        <button
          type="button"
          onClick={() => setMultiChannelOpen(true)}
          title="Difusión Multi-Canal: Publicar en Canales de YouTube y Páginas de Facebook"
          className="relative flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-beam-400/40 bg-beam-500/10 px-2.5 text-[11px] font-medium text-beam-200 transition-all hover:border-beam-300 hover:bg-beam-500/20 hover:text-white cursor-pointer shadow-[0_0_15px_rgba(59,130,246,0.15)]"
        >
          <IconShare className="h-3.5 w-3.5 text-beam-300 shrink-0" />
          <span>Publicar</span>
        </button>

        {/* Copilot Chat trigger */}
        <button
          type="button"
          onClick={openCopilot}
          title="Abrir AetherCopilot AI (Chat multi-modelo)"
          className="relative flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg border border-beam-400/50 bg-black px-3 text-[11px] font-medium text-beam-200 transition-colors duration-200 hover:bg-beam-500/15 hover:text-white"
        >
          <IconSparkle className="h-3.5 w-3.5 shrink-0 text-beam-300" />
          <span className="whitespace-nowrap">Copilot IA</span>
        </button>

        {/* avatar */}
        <div className="hidden h-8 w-8 shrink-0 place-items-center rounded-full border border-white/10 bg-gradient-to-br from-abyss-700 to-ink-900 text-[10px] font-medium text-beam-200 sm:grid">
          MR
        </div>
      </div>
      <Hairline className="absolute inset-x-0 bottom-0" />

      {/* Export Specifications Modal */}
      <ExportModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirm={handleModalConfirm}
        defaultTitle={activeProjectTitle || "KAI_Video_Master"}
        durationSec={duration}
        ratio={ratio}
        subtitleStyle={subtitleStyle}
        subtitlesActive={overlays.captions}
      />

      {/* Project Publication Details Modal */}
      <ProjectDetailsModal
        isOpen={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        projectId={activeProjectId}
        projectTitle={activeProjectTitle || "Video KAI"}
        durationSec={duration}
      />

      {/* Shorts & Reels 9:16 Modal */}
      <ClipsModal
        isOpen={clipsOpen}
        onClose={() => setClipsOpen(false)}
        projectId={activeProjectId}
        projectTitle={activeProjectTitle || "Video KAI"}
      />

      {/* Piloto automático */}
      <AutopilotModal isOpen={autopilotOpen} onClose={() => setAutopilotOpen(false)} />

      {/* Difusión Multi-Canal & Páginas con Recomendación IA */}
      <MultiChannelPublishModal
        isOpen={multiChannelOpen}
        onClose={() => setMultiChannelOpen(false)}
        projectId={activeProjectId}
        projectTitle={activeProjectTitle || "Video KAI"}
        thumbnailUrl={projects.find((p) => p.id === activeProjectId)?.thumbnail_url || (activeProjectId ? `/media/${activeProjectId}_thumbnail.jpg` : null)}
        durationSec={duration}
      />
    </header>
  );
}

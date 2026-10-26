import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { IconDownload, IconCheck } from "./Icons";
import { cn } from "@/utils/cn";

export type ExportModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (options: {
    burnSubtitles: boolean;
    resolution: "1080p" | "4k" | "720p";
    fps: 30 | 60;
    title: string;
  }) => void;
  defaultTitle: string;
  durationSec: number;
  ratio: string;
  subtitleStyle: string;
  subtitlesActive: boolean;
};

export function ExportModal({
  isOpen,
  onClose,
  onConfirm,
  defaultTitle,
  durationSec,
  ratio,
  subtitleStyle,
  subtitlesActive,
}: ExportModalProps) {
  const [title, setTitle] = useState(defaultTitle || "Video_Master");
  const [resolution, setResolution] = useState<"1080p" | "4k" | "720p">("1080p");
  const [burnSubtitles, setBurnSubtitles] = useState(subtitlesActive);
  const [fps, setFps] = useState<30 | 60>(30);

  useEffect(() => {
    if (isOpen) {
      if (defaultTitle) setTitle(defaultTitle);
      setBurnSubtitles(subtitlesActive);
    }
  }, [isOpen, defaultTitle, subtitlesActive]);

  if (!isOpen) return null;

  // Cálculo de tamaño aproximado en MB
  const bitrateMbps = resolution === "4k" ? 18 : resolution === "1080p" ? 7 : 3.5;
  const fpsMultiplier = fps === 60 ? 1.3 : 1.0;
  const estMb = Math.max(2, Math.round(((durationSec || 45) * bitrateMbps * fpsMultiplier) / 8));

  const handleDownload = () => {
    onConfirm({
      burnSubtitles,
      resolution,
      fps,
      title: title.trim() || defaultTitle || "video_master",
    });
  };

  const modalContent = (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      {/* Click outside to close */}
      <div className="absolute inset-0" onClick={onClose} />

      <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-white/12 bg-ink-950/95 p-5 sm:p-6 shadow-[0_25px_80px_rgba(0,0,0,0.95)] backdrop-blur-2xl z-10 text-left">
        {/* Glow ambient sutil */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-white/[0.02] blur-3xl" />
        <div className="pointer-events-none absolute -left-20 -bottom-20 h-48 w-48 rounded-full bg-white/[0.02] blur-3xl" />

        {/* Modal Header */}
        <div className="flex items-start justify-between pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-white/15 bg-white/[0.05] text-white">
              <IconDownload className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-white tracking-tight">
                Exportar Video Máster MP4
              </h3>
              <p className="text-xs text-beam-300/80 mt-0.5">
                Se descargará directamente en tu computadora a través de tu navegador
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-white/40 hover:text-white hover:bg-white/10 transition-colors"
            title="Cerrar"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Modal Content */}
        <div className="space-y-4 py-4 max-h-[72vh] overflow-y-auto pr-1 subtle-scrollbar">
          {/* 1. Vista previa / Resumen del video */}
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5 space-y-2.5">
            <span className="text-[10px] font-semibold text-beam-300 uppercase tracking-wider block">
              1. Video a descargar
            </span>
            <div>
              <label className="text-[11px] text-white/50 block mb-1">Nombre del archivo:</label>
              <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/40 px-3 py-1.5 focus-within:border-beam-400/50">
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Título del video..."
                  className="w-full bg-transparent text-xs text-white placeholder-white/20 focus:outline-none"
                />
                <span className="text-xs text-white/30 font-mono">.mp4</span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-1 text-[10.5px]">
              <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-white/80">
                {ratio === "9:16" ? "9:16 Vertical (Reel/TikTok)" : ratio === "16:9" ? "16:9 Horizontal" : `${ratio}`}
              </span>
              <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-white/80 font-mono">
                {durationSec ? `${Math.round(durationSec)}s` : "45s"} de duración
              </span>
              <span className="rounded-md border border-beam-400/20 bg-beam-500/10 px-2 py-0.5 text-beam-200">
                H.264 + AAC Estándar
              </span>
              <span className="rounded-md border border-signal-400/20 bg-signal-400/10 px-2 py-0.5 text-signal-400">
                Audio -16 LUFS
              </span>
            </div>
          </div>

          {/* 2. Opciones de Resolución */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold text-white/70 block">
              2. Resolución del video
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: "1080p", label: "1080p FHD", desc: "Recomendado redes", badge: "Óptimo" },
                { id: "4k", label: "4K UHD", desc: "Máxima fidelidad", badge: "2160p" },
                { id: "720p", label: "720p HD", desc: "Descarga rápida", badge: "Ligero" },
              ].map((r) => {
                const active = resolution === r.id;
                return (
                  <button
                    key={r.id}
                    type="button"
                    onClick={() => setResolution(r.id as any)}
                    className={cn(
                      "flex flex-col text-left p-2.5 rounded-xl border transition-all duration-200",
                      active
                        ? "border-beam-400/60 bg-beam-500/15 shadow-[0_0_15px_-3px_rgba(79,123,255,0.35)]"
                        : "border-white/[0.07] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-white">{r.label}</span>
                      {active && <IconCheck className="h-3 w-3 text-beam-300" />}
                    </div>
                    <span className="text-[10px] text-white/40 mt-0.5">{r.desc}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 3. Subtítulos (Incrustados vs Limpio) */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold text-white/70 block">
              3. Modo de Subtítulos
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setBurnSubtitles(true)}
                className={cn(
                  "p-2.5 rounded-xl border text-left transition-all duration-200 flex flex-col justify-between",
                  burnSubtitles
                    ? "border-beam-400/60 bg-beam-500/15 shadow-[0_0_15px_-3px_rgba(79,123,255,0.35)]"
                    : "border-white/[0.07] bg-white/[0.02] hover:border-white/20",
                )}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-white">Subtítulos Incrustados</span>
                    {burnSubtitles && <IconCheck className="h-3 w-3 text-beam-300" />}
                  </div>
                  <p className="text-[10px] text-white/40 mt-1">
                    Quemados en el video con estilo{" "}
                    <span className="text-beam-300 font-medium capitalize">{subtitleStyle || "Kinetic"}</span>
                  </p>
                </div>
                <span className="mt-2 text-[9px] text-beam-200/70 font-mono">Listo para publicar en TikTok/Reels</span>
              </button>

              <button
                type="button"
                onClick={() => setBurnSubtitles(false)}
                className={cn(
                  "p-2.5 rounded-xl border text-left transition-all duration-200 flex flex-col justify-between",
                  !burnSubtitles
                    ? "border-beam-400/60 bg-beam-500/15 shadow-[0_0_15px_-3px_rgba(79,123,255,0.35)]"
                    : "border-white/[0.07] bg-white/[0.02] hover:border-white/20",
                )}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-white">Video Limpio</span>
                    {!burnSubtitles && <IconCheck className="h-3 w-3 text-beam-300" />}
                  </div>
                  <p className="text-[10px] text-white/40 mt-1">
                    Pista visual pura sin texto sobreimpreso
                  </p>
                </div>
                <span className="mt-2 text-[9px] text-white/30 font-mono">Ideal para editar o archivar</span>
              </button>
            </div>
          </div>

          {/* 4. FPS & Peso Estimado */}
          <div className="flex items-center justify-between p-3 rounded-xl border border-white/[0.06] bg-black/30">
            <div className="flex items-center gap-3">
              <span className="text-xs text-white/70">Fotogramas:</span>
              <div className="flex items-center gap-1 bg-white/[0.05] p-0.5 rounded-lg border border-white/10">
                <button
                  type="button"
                  onClick={() => setFps(30)}
                  className={cn(
                    "px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors",
                    fps === 30 ? "bg-beam-500/30 text-white border border-beam-400/40" : "text-white/40 hover:text-white",
                  )}
                >
                  30 FPS
                </button>
                <button
                  type="button"
                  onClick={() => setFps(60)}
                  className={cn(
                    "px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors",
                    fps === 60 ? "bg-beam-500/30 text-white border border-beam-400/40" : "text-white/40 hover:text-white",
                  )}
                >
                  60 FPS
                </button>
              </div>
            </div>

            <div className="text-right">
              <span className="text-[10px] text-white/40 block">Tamaño estimado</span>
              <span className="text-xs font-semibold text-beam-200 font-mono">~{estMb} MB</span>
            </div>
          </div>
        </div>

        {/* Modal Footer Actions */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-white/10 px-4 py-2 text-xs font-medium text-white/60 hover:bg-white/[0.05] hover:text-white transition-colors"
          >
            Cancelar
          </button>

          <button
            type="button"
            onClick={handleDownload}
            className="relative flex items-center gap-2 overflow-hidden rounded-xl border border-beam-400/40 bg-gradient-to-r from-beam-600 via-beam-500 to-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-[0_0_30px_rgba(79,123,255,0.45)] hover:from-beam-500 hover:to-indigo-500 transition-all duration-200"
          >
            <IconDownload className="h-4 w-4" />
            <span>Descargar Video Máster</span>
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined"
    ? createPortal(modalContent, document.body)
    : modalContent;
}

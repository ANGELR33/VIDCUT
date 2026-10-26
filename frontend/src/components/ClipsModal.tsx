import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { IconDownload, IconCheck, IconClose, IconCrop } from "./Icons";
import { cn } from "@/utils/cn";

export interface ProjectClip {
  filename: string;
  name: string;
  url: string;
  duration: number;
  size_mb: number;
  hook_type?: string;
  has_subtitles?: boolean;
}

export interface ClipsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string | null;
  projectTitle: string;
}

export function ClipsModal({
  isOpen,
  onClose,
  projectId,
  projectTitle,
}: ClipsModalProps) {
  const [clips, setClips] = useState<ProjectClip[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const fetchClips = async (pid: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(pid)}/clips`);
      if (res.ok) {
        const data = await res.json();
        setClips(data.clips || []);
      }
    } catch (e) {
      console.error("Error cargando clips:", e);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && projectId) {
      fetchClips(projectId);
    } else {
      setClips([]);
      setMessage(null);
    }
  }, [isOpen, projectId]);

  const handleExtractNow = async () => {
    if (!projectId || isExtracting) return;
    setIsExtracting(true);
    setMessage("Analizando la línea de tiempo y extrayendo todos los momentos virales con subtítulos...");
    try {
      const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/extract-clips`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error al extraer clips");
      setMessage(data.message || `¡${data.clips?.length || 0} Reels generados con éxito con subtítulos!`);
      if (data.clips && data.clips.length > 0) {
        setClips(data.clips);
      } else {
        await fetchClips(projectId);
      }
    } catch (err: any) {
      setMessage(`Aviso: ${err.message || "No se pudieron extraer clips"}`);
    } finally {
      setIsExtracting(false);
    }
  };

  const handleCopyLink = (url: string, idx: number) => {
    const fullUrl = `${window.location.origin}${url}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(fullUrl);
    } else {
      const el = document.createElement("textarea");
      el.value = fullUrl;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopiedIdx(idx);
    window.setTimeout(() => setCopiedIdx(null), 2000);
  };

  if (!isOpen) return null;

  const modalContent = (
    <div className="fixed inset-0 z-[110] flex items-center justify-center p-3 sm:p-5 bg-black/85 backdrop-blur-md animate-in fade-in duration-200">
      {/* Click outside to close */}
      <div className="absolute inset-0" onClick={onClose} />

      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden rounded-2xl border border-white/12 bg-ink-950/98 p-5 sm:p-6 shadow-[0_25px_80px_rgba(0,0,0,0.95)] backdrop-blur-2xl z-10 text-left">
        {/* Glow ambient sutil */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-white/[0.02] blur-3xl" />
        <div className="pointer-events-none absolute -left-20 -bottom-20 h-56 w-56 rounded-full bg-white/[0.02] blur-3xl" />

        {/* Modal Header */}
        <div className="flex items-start justify-between pb-4 border-b border-white/[0.08] shrink-0">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-white/15 bg-white/[0.06] text-white">
              <IconCrop className="w-5 h-5 text-white/80" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-semibold text-white tracking-tight">
                  Shorts &amp; Reels 9:16 Extraídos
                </h3>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-white/[0.06] text-white/80 border border-white/15">
                  {clips.length} {clips.length === 1 ? "Clip" : "Clips"}
                </span>
              </div>
              <p className="text-xs text-white/50 mt-0.5 truncate max-w-lg">
                {projectTitle || "Video Máster KAI"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => projectId && fetchClips(projectId)}
              disabled={isLoading || isExtracting}
              className="px-2.5 py-1.5 rounded-xl border border-white/10 bg-white/5 text-white/60 hover:text-white hover:bg-white/10 transition-colors text-xs flex items-center gap-1"
              title="Refrescar lista de clips"
            >
              <span className="hidden sm:inline">Refrescar</span>
            </button>

            <button
              type="button"
              onClick={handleExtractNow}
              disabled={isExtracting}
              className={cn(
                "text-xs font-semibold px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5",
                isExtracting
                  ? "border-white/10 bg-white/5 text-white/40 cursor-not-allowed"
                  : "border-beam-400 bg-beam-500 text-white hover:bg-beam-400 shadow-none",
              )}
              title="Analizar y extraer todos los clips virales con IA"
            >
              <span>{isExtracting ? "Analizando y Extrayendo..." : "Analizar & Extraer Clips"}</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-white/40 hover:text-white hover:bg-white/10 transition-colors"
              title="Cerrar ventana"
            >
              <IconClose className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Feedback message banner if extracting */}
        {message && (
          <div className="my-2 p-2.5 rounded-lg border border-white/15 bg-white/[0.04] text-xs text-white/80 flex items-center justify-between shrink-0">
            <span>{message}</span>
            {isExtracting && <span className="text-xs text-white/50">Procesando...</span>}
          </div>
        )}

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto py-4 pr-1 subtle-scrollbar min-h-0">
          {isLoading ? (
            <div className="py-20 text-center flex flex-col items-center justify-center gap-3">
              <div className="w-8 h-8 rounded-full border-2 border-white/20 border-t-white animate-spin" />
              <p className="text-xs text-white/50">Cargando clips verticales generados...</p>
            </div>
          ) : clips.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {clips.map((clip, idx) => {
                const label = clip.hook_type || `Momento Viral #${idx + 1}`;
                return (
                  <div
                    key={clip.filename || idx}
                    className="flex flex-col rounded-xl border border-white/10 bg-black/40 overflow-hidden hover:border-white/25 transition-all duration-200 group"
                  >
                    {/* Header del Clip */}
                    <div className="p-2.5 bg-white/[0.03] border-b border-white/[0.06] flex items-center justify-between">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="text-[10px] font-bold text-white/80 uppercase tracking-wider shrink-0">
                          Reel #{idx + 1}
                        </span>
                        <span className="text-white/30 text-[10px] shrink-0">·</span>
                        <span className="text-[10px] font-semibold text-amber-300/90 truncate max-w-[140px]" title={label}>
                          {label}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0 ml-2">
                        {clip.has_subtitles !== false && (
                          <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-400/30" title="Subtítulos virales quemados en el video">
                            CC
                          </span>
                        )}
                        <span className="text-[10px] font-mono text-white/40">
                          {clip.duration}s
                        </span>
                      </div>
                    </div>

                    {/* Stage de Video 9:16 */}
                    <div className="relative aspect-[9/16] bg-black flex items-center justify-center overflow-hidden">
                      <video
                        src={`${clip.url}?v=${clip.size_mb || Date.now()}`}
                        controls
                        playsInline
                        preload="metadata"
                        className="w-full h-full object-contain"
                      />
                    </div>

                    {/* Metadata y Acciones */}
                    <div className="p-3 bg-white/[0.02] border-t border-white/[0.06] space-y-2.5">
                      <div>
                        <span className="text-xs font-semibold text-white/90 line-clamp-1" title={clip.name}>
                          {clip.name}
                        </span>
                        <div className="flex items-center gap-2 text-[10px] text-white/40 mt-0.5">
                          <span>{clip.size_mb} MB</span>
                          <span>•</span>
                          <span>1080x1920 (9:16)</span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2 pt-1">
                        <a
                          href={`${clip.url}?download=1`}
                          download={clip.filename}
                          className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/20 bg-white/[0.06] text-white text-xs font-semibold hover:bg-white/[0.1] transition-colors"
                          title="Descargar este clip en formato MP4"
                        >
                          <IconDownload className="w-3.5 h-3.5" />
                          <span>Descargar</span>
                        </a>

                        <button
                          type="button"
                          onClick={() => handleCopyLink(clip.url, idx)}
                          className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-white/[0.04] text-white/70 text-xs font-medium hover:bg-white/[0.08] hover:text-white transition-colors"
                          title="Copiar enlace directo del video"
                        >
                          {copiedIdx === idx ? (
                            <>
                              <IconCheck className="w-3.5 h-3.5 text-emerald-400" />
                              <span className="text-emerald-400">¡Copiado!</span>
                            </>
                          ) : (
                            <span>Copiar Link</span>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-16 text-center flex flex-col items-center justify-center gap-4 px-4 border border-dashed border-white/10 rounded-2xl bg-white/[0.01]">
              <div className="w-16 h-16 rounded-2xl bg-white/[0.04] border border-white/10 grid place-items-center text-white/60">
                <IconCrop className="w-8 h-8" />
              </div>
              <div className="max-w-md space-y-1">
                <h4 className="text-sm font-semibold text-white">
                  Aún no se han generado Reels de este video
                </h4>
                <p className="text-xs text-white/50">
                  KAI analiza la línea de tiempo, localiza las 3 frases y picos de retención más potentes del video y recorta clips 9:16 listos para publicar en TikTok, Reels y Shorts.
                </p>
              </div>

              <button
                type="button"
                onClick={handleExtractNow}
                disabled={isExtracting}
                className="mt-2 flex items-center gap-2 rounded-xl border border-beam-400 bg-beam-500 px-5 py-2.5 text-xs font-semibold text-white hover:bg-beam-400 transition-all duration-200"
              >
                <span>{isExtracting ? "Procesando..." : "Extraer 3 Reels con IA Ahora"}</span>
              </button>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-white/[0.08] shrink-0 text-[11px] text-white/40">
          <span>Formato oficial: 9:16 vertical con subtítulos dinámicos integrados</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/10 px-3 py-1 text-white/60 hover:text-white hover:bg-white/[0.05] transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined"
    ? createPortal(modalContent, document.body)
    : modalContent;
}

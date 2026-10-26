import { useState, useRef } from "react";
import { IconClose, IconPlus } from "./Icons";
import { useEditor } from "@/lib/store";
import { cn } from "@/utils/cn";

type Props = {
  isOpen: boolean;
  onClose: () => void;
};

export function ImportModal({ isOpen, onClose }: Props) {
  const { importVideo, importVideoUrl, isUploading } = useEditor();
  const [mode, setMode] = useState<"file" | "url">("file");
  const [urlInput, setUrlInput] = useState("");
  const [titleInput, setTitleInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileSelected = (file: File) => {
    importVideo(file);
    onClose();
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!urlInput.trim()) return;
    await importVideoUrl(urlInput.trim(), titleInput.trim() || undefined);
    setUrlInput("");
    setTitleInput("");
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 transition-all duration-200"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-white/10 bg-[#080808] p-6 shadow-[0_25px_70px_rgba(0,0,0,0.95)] animate-in fade-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-xl border border-white/10 bg-white/[0.04] text-white/80">
              <IconPlus className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-[14px] font-semibold text-white tracking-tight">
                Importar Video a LUMEN Studio
              </h3>
              <p className="text-[11px] text-white/40">
                Sube un archivo de tu equipo o introduce un enlace web
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-xl text-white/40 hover:bg-white/[0.06] hover:text-white transition-colors cursor-pointer"
            title="Cerrar (Esc)"
          >
            <IconClose className="h-4 w-4" />
          </button>
        </div>

        {/* Tabs: Archivo Local vs Enlace Web */}
        <div className="mt-5 flex items-center rounded-xl border border-white/[0.08] bg-white/[0.02] p-1">
          <button
            type="button"
            onClick={() => setMode("file")}
            className={cn(
              "flex-1 py-1.5 rounded-lg text-[11px] font-medium transition-all cursor-pointer",
              mode === "file"
                ? "bg-white/[0.12] text-white shadow-sm font-semibold"
                : "text-white/45 hover:text-white",
            )}
          >
            📁 Archivo local (MP4, MOV, MKV)
          </button>
          <button
            type="button"
            onClick={() => setMode("url")}
            className={cn(
              "flex-1 py-1.5 rounded-lg text-[11px] font-medium transition-all cursor-pointer",
              mode === "url"
                ? "bg-white/[0.12] text-white shadow-sm font-semibold"
                : "text-white/45 hover:text-white",
            )}
          >
            🔗 Enlace YouTube / Web
          </button>
        </div>

        {/* Tab 1: Archivo local */}
        {mode === "file" && (
          <div className="mt-5 space-y-4">
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileSelected(file);
              }}
            />

            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                const file = e.dataTransfer.files?.[0];
                if (file) handleFileSelected(file);
              }}
              onClick={() => fileInputRef.current?.click()}
              className={cn(
                "group flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-all cursor-pointer",
                isDragging
                  ? "border-beam-400 bg-beam-500/10"
                  : "border-white/15 bg-white/[0.015] hover:border-white/30 hover:bg-white/[0.03]",
              )}
            >
              <div className="grid h-12 w-12 place-items-center rounded-2xl border border-white/10 bg-white/[0.04] text-white/60 group-hover:text-white group-hover:scale-105 transition-all mb-3">
                <svg
                  viewBox="0 0 24 24"
                  className="h-6 w-6"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
              </div>
              <p className="text-[12.5px] font-medium text-white/90">
                Arrastra tu archivo aquí o haz clic para buscar
              </p>
              <p className="mt-1 text-[11px] text-white/40">
                Soporta MP4, MOV, MKV, WebM de hasta 2 GB
              </p>
            </div>
          </div>
        )}

        {/* Tab 2: Enlace YouTube / Web */}
        {mode === "url" && (
          <form onSubmit={handleUrlSubmit} className="mt-5 space-y-4">
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-white/70">
                URL del video (YouTube, TikTok, Twitter o enlace directo MP4)
              </label>
              <input
                type="url"
                required
                placeholder="https://www.youtube.com/watch?v=..."
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                className="w-full rounded-xl border border-white/15 bg-white/[0.03] px-3.5 py-2.5 text-[12px] text-white placeholder:text-white/25 focus:border-white/35 focus:outline-none transition-all"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-white/70">
                Título opcional para el proyecto
              </label>
              <input
                type="text"
                placeholder="Ej: Análisis de Mercado 2026"
                value={titleInput}
                onChange={(e) => setTitleInput(e.target.value)}
                className="w-full rounded-xl border border-white/15 bg-white/[0.03] px-3.5 py-2 text-[12px] text-white placeholder:text-white/25 focus:border-white/35 focus:outline-none transition-all"
              />
            </div>

            <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-3 text-[10.5px] text-white/50 leading-relaxed">
              Nota: El motor de LUMEN descargará el video en streaming en máxima calidad y lo colocará de inmediato en la línea de tiempo para comenzar a editar.
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl text-[11px] font-medium text-white/50 hover:text-white transition-colors cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={isUploading || !urlInput.trim()}
                className="px-5 py-2 rounded-xl border border-white/20 bg-white/[0.12] hover:bg-white/[0.2] text-white text-[11px] font-semibold transition-all shadow-sm disabled:opacity-40 cursor-pointer"
              >
                {isUploading ? "Iniciando descarga..." : "Importar video"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

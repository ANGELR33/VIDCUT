import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { IconClose, IconSparkle, IconCheck, IconSend } from "./Icons";
import { cn } from "@/utils/cn";

// Professional SVG Icons without emojis
const IconBroadcast = ({ className = "w-4 h-4" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9" />
    <path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5" />
    <circle cx="12" cy="12" r="2" fill="currentColor" />
    <path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5" />
    <path d="M19.1 4.9C23 8.8 23 15.2 19.1 19.1" />
  </svg>
);

const IconPhone = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <rect x="5" y="2" width="14" height="20" rx="2.5" />
    <line x1="12" y1="18" x2="12" y2="18.01" strokeWidth={2.5} />
  </svg>
);

const IconScreen = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="3" width="20" height="14" rx="2" />
    <line x1="8" y1="21" x2="16" y2="21" />
    <line x1="12" y1="17" x2="12" y2="21" />
  </svg>
);

const IconYouTube = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
  </svg>
);

const IconFacebook = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
  </svg>
);

const IconClock = ({ className = "w-3 h-3" }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 6 12 12 16 14" />
  </svg>
);

export interface ChannelRecommendation {
  id: string;
  target_key: string;
  platform: "youtube" | "facebook";
  name: string;
  tag: string;
  category: string;
  subscribers: string;
  avatar: string;
  connected: boolean;
  badge: string;
  affinity_pct: number;
  is_recommended: boolean;
  recommendation_reason: string;
  matched_keywords: string[];
}

export interface PublishReport {
  channel_key: string;
  name: string;
  platform: "youtube" | "facebook";
  success: boolean;
  url?: string | null;
  thumbnail_applied?: boolean;
  message?: string;
  error?: string;
}

interface Props {
  isOpen: boolean;
  onClose: () => void;
  projectId?: string | null;
  projectTitle?: string;
  thumbnailUrl?: string | null;
  durationSec?: number;
}

export function MultiChannelPublishModal({
  isOpen,
  onClose,
  projectId,
  projectTitle,
  thumbnailUrl,
  durationSec,
}: Props) {
  const [channels, setChannels] = useState<ChannelRecommendation[]>([]);
  const [aiSummary, setAiSummary] = useState<string>("");
  const [_topRecommendation, setTopRecommendation] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  // Formulario de publicación
  const [title, setTitle] = useState<string>("");
  const [description, setDescription] = useState<string>("");
  const [tags, setTags] = useState<string[]>([]);
  const [tagsInput, setTagsInput] = useState<string>("");
  const [isReel, setIsReel] = useState<boolean>(true);
  const [privacy] = useState<string>("public");

  // Estado de publicación
  const [isPublishing, setIsPublishing] = useState<boolean>(false);
  const [publishReports, setPublishReports] = useState<PublishReport[] | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");

  // Cargar canales y recomendaciones de IA al abrir
  useEffect(() => {
    if (!isOpen) return;

    setLoading(true);
    setErrorMsg("");
    setPublishReports(null);

    const taskParam = projectId ? `?task_id=${encodeURIComponent(projectId)}` : "";

    // 1. Obtener canales y afinidad de IA
    fetch(`/api/publish/multichannel/channels${taskParam}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.channels) {
          setChannels(data.channels);
          setAiSummary(data.ai_summary || "");
          setTopRecommendation(data.top_recommendation || "");

          // Pre-seleccionar por defecto los canales recomendados por la IA
          const autoSelected = new Set<string>();
          data.channels.forEach((c: ChannelRecommendation) => {
            if (c.is_recommended && c.connected !== false) {
              autoSelected.add(c.target_key);
            }
          });
          if (autoSelected.size === 0 && data.channels.length > 0) {
            autoSelected.add(data.channels[0].target_key);
          }
          setSelectedKeys(autoSelected);
        }
      })
      .catch((err) => {
        console.error("Error al cargar canales:", err);
        setErrorMsg("No se pudieron cargar los canales de difusión.");
      })
      .finally(() => setLoading(false));

    // 2. Obtener metadatos optimizados del proyecto si existe
    if (projectId) {
      fetch(`/api/projects/${encodeURIComponent(projectId)}/publish-info`)
        .then((res) => (res.ok ? res.json() : null))
        .then((info) => {
          if (info) {
            setTitle(info.title || projectTitle || "");
            const fullDesc = [info.description, info.hashtags_str].filter(Boolean).join("\n\n");
            setDescription(fullDesc);
            setTags(info.tags || []);
            setTagsInput((info.tags || []).join(", "));
          }
        })
        .catch(() => {
          setTitle(projectTitle || "Video AetherCut");
        });
    } else {
      setTitle(projectTitle || "Video AetherCut");
    }
  }, [isOpen, projectId, projectTitle]);

  const toggleChannel = (key: string) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectAiRecommended = () => {
    const next = new Set<string>();
    channels.forEach((c) => {
      if (c.is_recommended && c.connected !== false) {
        next.add(c.target_key);
      }
    });
    setSelectedKeys(next);
  };

  const selectAll = () => {
    const next = new Set<string>();
    channels.forEach((c) => {
      if (c.connected !== false) next.add(c.target_key);
    });
    setSelectedKeys(next);
  };

  const clearSelection = () => {
    setSelectedKeys(new Set());
  };

  const handlePublish = async () => {
    if (!projectId) {
      setErrorMsg("No hay un proyecto activo seleccionado para publicar.");
      return;
    }
    if (selectedKeys.size === 0) {
      setErrorMsg("Selecciona al menos un canal o página para publicar.");
      return;
    }

    setIsPublishing(true);
    setErrorMsg("");
    setPublishReports(null);

    const parsedTags = tagsInput
      .split(",")
      .map((t) => t.trim().replace(/^#/, ""))
      .filter(Boolean);

    try {
      const res = await fetch("/api/publish/multichannel/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: projectId,
          channel_keys: Array.from(selectedKeys),
          title: title.trim(),
          description: description.trim(),
          tags: parsedTags.length > 0 ? parsedTags : tags,
          is_reel: isReel,
          privacy,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Error en la publicación");
      }

      setPublishReports(data.reports || []);
    } catch (err: any) {
      console.error("Error al despachar:", err);
      setErrorMsg(err.message || "Error al comunicar con los servidores de publicación.");
    } finally {
      setIsPublishing(false);
    }
  };

  if (!isOpen) return null;

  const ytChannels = channels.filter((c) => c.platform === "youtube");
  const fbChannels = channels.filter((c) => c.platform === "facebook");

  const modalContent = (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 backdrop-blur-md p-3 sm:p-5 animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div
        className="relative z-10 flex flex-col w-full max-w-4xl max-h-[88vh] rounded-2xl border border-white/10 bg-[#07090e] shadow-[0_25px_80px_rgba(0,0,0,0.95)] overflow-hidden text-white"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Glow ambient sutil con la paleta beam */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-beam-500/[0.04] blur-3xl" />
        <div className="pointer-events-none absolute -left-20 -bottom-20 h-48 w-48 rounded-full bg-beam-500/[0.04] blur-3xl" />

        {/* MODAL HEADER */}
        <div className="flex items-center justify-between border-b border-white/[0.08] px-5 py-3.5 bg-white/[0.015] shrink-0">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-xl border border-beam-400/30 bg-beam-500/10 text-beam-300">
              <IconBroadcast className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold tracking-tight text-white">
                  Difusión Multi-Canal
                </h2>
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono font-medium bg-beam-500/15 text-beam-200 border border-beam-400/25">
                  AI Matcher
                </span>
              </div>
              <p className="text-[11px] text-white/45">
                Distribuye tu video en YouTube y Facebook optimizando la retención por nicho
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg border border-white/10 text-white/40 hover:text-white hover:bg-white/[0.06] transition-colors cursor-pointer"
            title="Cerrar"
          >
            <IconClose className="w-4 h-4" />
          </button>
        </div>

        {/* BODY (SCROLLABLE) */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 min-h-0 subtle-scrollbar">

          {/* COMPACT UNIFIED CONTROL BAR: Miniatura + Formato + Sugerencia IA */}
          <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-2.5">
            {/* Fila 1: Miniatura, Título y Selector de Formato */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                {thumbnailUrl ? (
                  <div className="relative shrink-0">
                    <img
                      src={thumbnailUrl}
                      alt="Miniatura del Video"
                      className="w-14 h-9 object-cover rounded-lg border border-white/10 shadow-sm"
                    />
                    <span className="absolute -bottom-1 -right-1 flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-signal-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-signal-400" />
                    </span>
                  </div>
                ) : (
                  <div className="w-14 h-9 rounded-lg border border-white/10 bg-white/[0.04] flex items-center justify-center text-[10px] text-white/40 shrink-0 font-mono">
                    MP4
                  </div>
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase font-semibold tracking-wider text-beam-300">
                      Video Máster
                    </span>
                    {durationSec && (
                      <span className="inline-flex items-center gap-1 text-[10px] text-white/40 font-mono">
                        <IconClock className="w-2.5 h-2.5" />
                        {Math.round(durationSec)}s
                      </span>
                    )}
                    <span className="text-[9.5px] px-1.5 py-0.2 rounded border border-signal-400/25 bg-signal-400/10 text-signal-400">
                      Miniatura vinculada
                    </span>
                  </div>
                  <h3 className="text-xs font-medium text-white truncate max-w-lg mt-0.5">
                    {title || projectTitle || "Video de AetherCut"}
                  </h3>
                </div>
              </div>

              {/* Segmented Format Selector */}
              <div className="flex items-center rounded-lg border border-white/[0.08] bg-black/40 p-0.5 shrink-0 self-end sm:self-auto">
                <button
                  type="button"
                  onClick={() => setIsReel(true)}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer",
                    isReel
                      ? "bg-beam-500/25 text-beam-200 border border-beam-400/40 shadow-sm"
                      : "text-white/45 hover:text-white border border-transparent",
                  )}
                >
                  <IconPhone className="w-3 h-3" />
                  <span>Reels 9:16</span>
                </button>
                <button
                  type="button"
                  onClick={() => setIsReel(false)}
                  className={cn(
                    "flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium rounded-md transition-all cursor-pointer",
                    !isReel
                      ? "bg-beam-500/25 text-beam-200 border border-beam-400/40 shadow-sm"
                      : "text-white/45 hover:text-white border border-transparent",
                  )}
                >
                  <IconScreen className="w-3 h-3" />
                  <span>Horizontal 16:9</span>
                </button>
              </div>
            </div>

            {/* Fila 2: Tira compacta de Recomendación IA */}
            {aiSummary && (
              <div className="flex items-center justify-between gap-3 pt-2 border-t border-white/[0.05]">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="p-1 rounded-md bg-beam-500/15 border border-beam-400/30 text-beam-300 shrink-0">
                    <IconSparkle className="w-3.5 h-3.5" />
                  </div>
                  <p className="text-[11px] text-white/75 truncate">
                    <span className="font-semibold text-beam-300">Sugerencia IA: </span>
                    {aiSummary}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={selectAiRecommended}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10.5px] font-medium bg-beam-500/15 border border-beam-400/30 text-beam-200 hover:bg-beam-500/25 hover:border-beam-400/50 transition-all cursor-pointer shrink-0"
                >
                  <IconSparkle className="w-3 h-3 text-beam-300" />
                  <span>Auto-seleccionar sugeridos</span>
                </button>
              </div>
            )}
          </div>

          {/* LISTA ORGANIZADA DE DESTINOS */}
          <div className="space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-white/50">
                Destinos Conectados ({channels.length})
              </span>
              <div className="flex items-center gap-2 text-[10.5px]">
                <button
                  type="button"
                  onClick={selectAll}
                  className="text-white/45 hover:text-white transition-colors cursor-pointer"
                >
                  Marcar todos
                </button>
                <span className="text-white/20">·</span>
                <button
                  type="button"
                  onClick={clearSelection}
                  className="text-white/45 hover:text-white transition-colors cursor-pointer"
                >
                  Limpiar
                </button>
              </div>
            </div>

            {loading ? (
              <div className="py-10 text-center text-white/40 text-xs">
                Analizando afinidad de audiencia por IA...
              </div>
            ) : (
              <div className="space-y-3.5">
                {/* 1. SECCIÓN YOUTUBE */}
                {ytChannels.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2 text-[11px] font-medium text-red-400">
                      <IconYouTube className="w-3.5 h-3.5" />
                      <span>Canales de YouTube</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      {ytChannels.map((c) => {
                        const isSelected = selectedKeys.has(c.target_key);
                        return (
                          <div
                            key={c.target_key}
                            onClick={() => toggleChannel(c.target_key)}
                            className={cn(
                              "relative p-3 rounded-xl border transition-all cursor-pointer select-none flex flex-col justify-between gap-2",
                              isSelected
                                ? "border-beam-400/50 bg-beam-500/[0.08] shadow-[0_0_20px_rgba(37,99,235,0.12)]"
                                : "border-white/[0.07] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]",
                            )}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-center gap-2.5 min-w-0">
                                {c.avatar ? (
                                  <img
                                    src={c.avatar}
                                    alt={c.name}
                                    className="w-7 h-7 rounded-full border border-white/10 shrink-0"
                                  />
                                ) : (
                                  <div className="w-7 h-7 rounded-full bg-red-600/20 border border-red-500/30 flex items-center justify-center text-[10px] font-bold text-red-400 shrink-0">
                                    YT
                                  </div>
                                )}
                                <div className="min-w-0">
                                  <h5 className="text-xs font-semibold text-white truncate">
                                    {c.name}
                                  </h5>
                                  <p className="text-[10px] text-white/40 truncate">
                                    {c.tag}
                                  </p>
                                </div>
                              </div>

                              {/* Afinidad + Checkbox */}
                              <div className="flex items-center gap-1.5 shrink-0">
                                <span
                                  className={cn(
                                    "px-1.5 py-0.5 rounded text-[10px] font-mono border",
                                    c.affinity_pct >= 80
                                      ? "bg-beam-500/20 text-beam-200 border-beam-400/40 font-semibold"
                                      : c.affinity_pct >= 50
                                      ? "bg-white/[0.05] text-white/70 border-white/10"
                                      : "bg-white/[0.02] text-white/35 border-white/[0.06]",
                                  )}
                                >
                                  {c.affinity_pct}%
                                </span>
                                <div
                                  className={cn(
                                    "w-4 h-4 rounded border flex items-center justify-center transition-colors",
                                    isSelected
                                      ? "bg-beam-500 border-beam-400 text-white"
                                      : "border-white/20 bg-transparent",
                                  )}
                                >
                                  {isSelected && <IconCheck className="w-3 h-3 stroke-[3]" />}
                                </div>
                              </div>
                            </div>

                            {/* Razón IA */}
                            <p className="text-[10.5px] text-white/50 leading-relaxed border-t border-white/[0.04] pt-1.5">
                              {c.recommendation_reason.replace(/^⭐\s*/, "")}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 2. SECCIÓN FACEBOOK */}
                {fbChannels.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2 text-[11px] font-medium text-blue-400">
                      <IconFacebook className="w-3.5 h-3.5" />
                      <span>Páginas de Facebook</span>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      {fbChannels.map((c) => {
                        const isSelected = selectedKeys.has(c.target_key);
                        return (
                          <div
                            key={c.target_key}
                            onClick={() => toggleChannel(c.target_key)}
                            className={cn(
                              "relative p-3 rounded-xl border transition-all cursor-pointer select-none flex flex-col justify-between gap-2",
                              isSelected
                                ? "border-beam-400/50 bg-beam-500/[0.08] shadow-[0_0_20px_rgba(37,99,235,0.12)]"
                                : "border-white/[0.07] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]",
                            )}
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex items-center gap-2.5 min-w-0">
                                {c.avatar ? (
                                  <img
                                    src={c.avatar}
                                    alt={c.name}
                                    className="w-7 h-7 rounded-full border border-white/10 shrink-0"
                                  />
                                ) : (
                                  <div className="w-7 h-7 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-[10px] font-bold text-blue-400 shrink-0">
                                    FB
                                  </div>
                                )}
                                <div className="min-w-0">
                                  <h5 className="text-xs font-semibold text-white truncate">
                                    {c.name}
                                  </h5>
                                  <p className="text-[10px] text-white/40 truncate">
                                    {c.tag}
                                  </p>
                                </div>
                              </div>

                              {/* Afinidad + Checkbox */}
                              <div className="flex items-center gap-1.5 shrink-0">
                                <span
                                  className={cn(
                                    "px-1.5 py-0.5 rounded text-[10px] font-mono border",
                                    c.affinity_pct >= 80
                                      ? "bg-beam-500/20 text-beam-200 border-beam-400/40 font-semibold"
                                      : c.affinity_pct >= 50
                                      ? "bg-white/[0.05] text-white/70 border-white/10"
                                      : "bg-white/[0.02] text-white/35 border-white/[0.06]",
                                  )}
                                >
                                  {c.affinity_pct}%
                                </span>
                                <div
                                  className={cn(
                                    "w-4 h-4 rounded border flex items-center justify-center transition-colors",
                                    isSelected
                                      ? "bg-beam-500 border-beam-400 text-white"
                                      : "border-white/20 bg-transparent",
                                  )}
                                >
                                  {isSelected && <IconCheck className="w-3 h-3 stroke-[3]" />}
                                </div>
                              </div>
                            </div>

                            {/* Razón IA */}
                            <p className="text-[10.5px] text-white/50 leading-relaxed border-t border-white/[0.04] pt-1.5">
                              {c.recommendation_reason.replace(/^⭐\s*/, "")}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* INFORMES DE PUBLICACIÓN COMPLETADA */}
          {publishReports && (
            <div className="p-4 rounded-xl border border-beam-400/30 bg-beam-500/10 space-y-2.5 animate-in fade-in">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-white">
                  Resultados de Difusión
                </span>
                <span className="text-[11px] font-mono text-beam-300">
                  {publishReports.filter((r) => r.success).length} / {publishReports.length} exitosos
                </span>
              </div>
              <div className="space-y-1.5">
                {publishReports.map((r) => (
                  <div
                    key={r.channel_key}
                    className="flex items-center justify-between p-2 rounded-lg bg-black/40 border border-white/[0.06] text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <span className={r.success ? "text-signal-400 font-bold" : "text-rose-400 font-bold"}>
                        {r.success ? "✓" : "✗"}
                      </span>
                      <span className="font-medium text-white">{r.name}</span>
                      <span className="text-[10px] text-white/40 uppercase">({r.platform})</span>
                    </div>
                    {r.url ? (
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-beam-300 hover:text-beam-200 hover:underline text-[11px] flex items-center gap-1"
                      >
                        <span>Ver publicación</span>
                        <span>↗</span>
                      </a>
                    ) : (
                      <span className="text-white/40 text-[11px]">{r.message || r.error}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {errorMsg && (
            <div className="p-3 rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-300 text-xs">
              {errorMsg}
            </div>
          )}
        </div>

        {/* MODAL FOOTER */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 border-t border-white/[0.08] px-5 py-3.5 bg-white/[0.015] shrink-0">
          <div className="flex items-center gap-2 text-xs text-white/50">
            <span className="font-semibold text-white font-mono">{selectedKeys.size}</span>
            <span>canal(es) seleccionado(s)</span>
            <span className="text-white/20">·</span>
            <span className="text-[11px] text-white/40">Miniatura oficial incluida</span>
          </div>

          <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
            <button
              type="button"
              onClick={onClose}
              disabled={isPublishing}
              className="px-4 py-2 text-xs rounded-xl border border-white/10 bg-white/[0.04] text-white/70 hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer"
            >
              Cerrar
            </button>

            <button
              type="button"
              onClick={handlePublish}
              disabled={isPublishing || selectedKeys.size === 0}
              className={cn(
                "relative flex items-center gap-2 overflow-hidden rounded-xl px-5 py-2 text-xs font-semibold text-white transition-all duration-200 cursor-pointer shadow-lg",
                isPublishing || selectedKeys.size === 0
                  ? "bg-white/10 text-white/40 border border-white/5 cursor-not-allowed"
                  : "border border-beam-400/40 bg-gradient-to-r from-beam-600 via-beam-500 to-indigo-600 hover:from-beam-500 hover:to-indigo-500 shadow-[0_0_25px_rgba(37,99,235,0.35)]",
              )}
            >
              {isPublishing ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-3.5 w-3.5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Publicando en {selectedKeys.size} canales...</span>
                </>
              ) : (
                <>
                  <IconSend className="w-3.5 h-3.5" />
                  <span>Publicar en {selectedKeys.size} canales</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return typeof document !== "undefined"
    ? createPortal(modalContent, document.body)
    : modalContent;
}

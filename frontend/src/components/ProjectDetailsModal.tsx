import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { IconCheck, IconClose, IconCopy, IconShare } from "./Icons";
import {
  Privacy,
  YouTubeStatus,
  YouTubeAccount,
  ChannelKind,
  PublishFormat,
  PublishSuggestion,
  fetchYouTubeStatus,
  connectYouTube,
  disconnectYouTube,
  updateYouTubeAccount,
  suggestPublishTarget,
  publishProject,
  readAutoPublish,
  saveAutoPublish,
} from "@/lib/youtubePublish";

interface ProjectDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string | null;
  projectTitle: string;
  thumbnailUrl?: string | null;
  durationSec?: number | null;
}

interface PublishInfo {
  title: string;
  description: string;
  tags: string[];
  hashtags: string[];
  hashtags_str: string;
}

export function ProjectDetailsModal({
  isOpen,
  onClose,
  projectId,
  projectTitle,
  thumbnailUrl,
  durationSec,
}: ProjectDetailsModalProps) {
  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState<PublishInfo | null>(null);
  const [copiedSection, setCopiedSection] = useState<string | null>(null);

  // Publicación en YouTube
  const [yt, setYt] = useState<YouTubeStatus | null>(null);
  const [privacy, setPrivacy] = useState<Privacy>("private");
  const [autoPublish, setAutoPublish] = useState(false);
  const [pubBusy, setPubBusy] = useState(false);
  const [pubPct, setPubPct] = useState(0);
  const [pubMsg, setPubMsg] = useState("");
  const [pubError, setPubError] = useState("");
  const [pubUrl, setPubUrl] = useState("");
  const [channelId, setChannelId] = useState("");
  const [formatSel, setFormatSel] = useState<PublishFormat>("auto");
  const [suggestion, setSuggestion] = useState<PublishSuggestion | null>(null);
  const [editTag, setEditTag] = useState("");
  const [editKeywords, setEditKeywords] = useState("");

  const accounts: YouTubeAccount[] = yt?.accounts || [];
  const selectedAccount = accounts.find((a) => a.channel_id === channelId) || accounts[0];
  const effectiveFormat: "short" | "video" =
    formatSel === "auto" ? suggestion?.format || "video" : formatSel;

  useEffect(() => {
    if (!isOpen) return;
    const saved = readAutoPublish();
    setAutoPublish(saved.enabled);
    setPrivacy(saved.privacy);
    setPubError("");
    setPubUrl("");
    setFormatSel("auto");
    setSuggestion(null);
    fetchYouTubeStatus()
      .then((st) => {
        setYt(st);
        setChannelId((cur) => cur || st.accounts?.[0]?.channel_id || "");
      })
      .catch(() => setYt(null));
  }, [isOpen]);

  // Detecta Short/Video y sugiere el canal por etiquetas cuando ya hay datos del proyecto
  useEffect(() => {
    if (!isOpen || !projectId || !info || accounts.length === 0) return;
    let alive = true;
    suggestPublishTarget(projectId, {
      title: info.title,
      description: info.description,
      tags: info.tags,
    }).then((s) => {
      if (!alive || !s) return;
      setSuggestion(s);
      if (s.channel_id) setChannelId(s.channel_id);
    });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, projectId, info, accounts.length]);

  useEffect(() => {
    setEditTag(selectedAccount?.tag || "");
    setEditKeywords((selectedAccount?.keywords || []).join(", "));
  }, [selectedAccount?.channel_id, selectedAccount?.tag, selectedAccount?.keywords]);

  const saveAccount = async (patch: { tag?: string; keywords?: string; kind?: ChannelKind }) => {
    if (!selectedAccount) return;
    try {
      await updateYouTubeAccount(selectedAccount.channel_id, patch);
      setYt(await fetchYouTubeStatus());
    } catch (e: any) {
      setPubError(e?.message || "No se pudo guardar el canal");
    }
  };

  const handlePublish = async () => {
    if (!projectId || pubBusy) return;
    setPubBusy(true);
    setPubError("");
    setPubUrl("");
    setPubPct(0);
    try {
      const res = await publishProject(projectId, {
        privacy,
        title: info?.title,
        description: info ? [info.description, info.hashtags_str].filter(Boolean).join("\n\n") : undefined,
        tags: info?.tags,
        channelId: channelId || undefined,
        format: formatSel,
        onProgress: (pct, msg) => {
          setPubPct(pct);
          setPubMsg(msg);
        },
      });
      setPubUrl(res.videoUrl);
    } catch (e: any) {
      setPubError(e?.message || "No se pudo publicar");
    } finally {
      setPubBusy(false);
    }
  };

  useEffect(() => {
    if (!isOpen || !projectId) {
      setInfo(null);
      return;
    }

    let isMounted = true;
    setLoading(true);

    fetch(`/api/projects/${projectId}/publish-info`)
      .then((res) => {
        if (!res.ok) throw new Error("Error cargando detalles");
        return res.json();
      })
      .then((data: PublishInfo) => {
        if (isMounted) {
          setInfo(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (isMounted) {
          // Fallback con datos locales disponibles
          const baseTags = ["#Viral", "#Tendencias", "#AetherCut", "#Shorts", "#Reels", "#IA"];
          setInfo({
            title: projectTitle || "Video KAI",
            description: `${projectTitle}\n\n🎬 Video producido con Inteligencia Artificial.\n🔔 ¡Suscríbete y activa la campana!\n💬 ¿Qué opinas? Déjamelo en los comentarios.`,
            tags: ["Viral", "Tendencias", "AetherCut", "Shorts", "Reels", "IA"],
            hashtags: baseTags,
            hashtags_str: baseTags.join(" "),
          });
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, projectId, projectTitle]);

  if (!isOpen) return null;

  const copyToClipboard = (text: string, sectionId: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
    } else {
      const el = document.createElement("textarea");
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }

    setCopiedSection(sectionId);
    window.setTimeout(() => {
      setCopiedSection((cur) => (cur === sectionId ? null : cur));
    }, 2200);
  };

  const currentTitle = info?.title || projectTitle || "Video KAI";
  const currentDesc = info?.description || "";
  const currentTags = info?.hashtags_str || "";

  const handleCopyAll = () => {
    const fullText = `${currentTitle}\n\n${currentDesc}\n\n${currentTags}`.trim();
    copyToClipboard(fullText, "all");
  };

  const durStr = durationSec
    ? durationSec >= 60
      ? `${Math.floor(durationSec / 60)}m ${Math.round(durationSec % 60)}s`
      : `${Math.round(durationSec)}s`
    : null;

  const modalContent = (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      {/* Backdrop */}
      <div className="absolute inset-0" onClick={onClose} />

      <div className="relative w-full max-w-xl max-h-[90vh] overflow-hidden rounded-2xl border border-white/12 bg-ink-950/98 p-5 sm:p-6 shadow-[0_25px_80px_rgba(0,0,0,0.95)] backdrop-blur-2xl z-10 flex flex-col text-left">
        {/* Glow ambient sutil */}
        <div className="pointer-events-none absolute -right-20 -top-20 h-44 w-44 rounded-full bg-white/[0.02] blur-3xl" />
        <div className="pointer-events-none absolute -left-20 -bottom-20 h-44 w-44 rounded-full bg-white/[0.02] blur-3xl" />

        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-white/[0.08] shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/15 bg-white/[0.05] text-white">
              <IconShare className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-white truncate">Detalles y Publicación</h3>
              <p className="text-[11px] text-white/40 truncate">
                Copia título, descripción y hashtags listos para TikTok, Shorts y Reels
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-white/40 hover:text-white hover:bg-white/[0.05] transition-colors shrink-0"
          >
            <IconClose className="h-4 w-4" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4 pr-1">
          {/* Card Preview Banner */}
          <div className="flex items-center gap-3 p-2.5 rounded-xl border border-white/[0.06] bg-white/[0.02]">
            {thumbnailUrl ? (
              <img
                src={thumbnailUrl}
                alt=""
                className="h-14 w-10 object-cover rounded-lg border border-white/10 shrink-0"
              />
            ) : null}
            <div className="min-w-0 flex-1">
              <div className="text-[12px] font-medium text-white truncate">{currentTitle}</div>
              <div className="mt-1 flex items-center gap-2 text-[10px] text-white/40">
                {durStr && <span className="font-mono bg-white/[0.05] px-1.5 py-0.5 rounded">⏱ {durStr}</span>}
                <span className="text-emerald-400/90 font-medium">✓ Listo para publicar</span>
              </div>
            </div>
          </div>

          {/* Botón Principal: Copiar TODO */}
          <button
            type="button"
            onClick={handleCopyAll}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl font-medium text-[12px] text-white border border-beam-400 bg-beam-500 hover:bg-beam-400 transition-all active:scale-[0.99]"
          >
            {copiedSection === "all" ? (
              <>
                <IconCheck className="h-4 w-4 text-emerald-300" />
                <span className="text-emerald-200">¡Todo copiado al portapapeles!</span>
              </>
            ) : (
              <>
                <IconCopy className="h-4 w-4" />
                <span>Copiar Todo (Título + Descripción + Hashtags)</span>
              </>
            )}
          </button>

          {/* Sección 1: TÍTULO */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold uppercase tracking-wider text-white/50">Título del Video</span>
              <button
                type="button"
                onClick={() => copyToClipboard(currentTitle, "title")}
                className="flex items-center gap-1 text-beam-300 hover:text-beam-200 text-[10.5px] font-medium"
              >
                {copiedSection === "title" ? (
                  <>
                    <IconCheck className="h-3 w-3 text-emerald-400" />
                    <span className="text-emerald-300">Copiado</span>
                  </>
                ) : (
                  <>
                    <IconCopy className="h-3 w-3" />
                    <span>Copiar Título</span>
                  </>
                )}
              </button>
            </div>
            <div className="p-3 rounded-xl border border-white/[0.08] bg-black/40 text-[12px] text-white/90 font-medium select-all">
              {loading ? "Cargando..." : currentTitle}
            </div>
          </div>

          {/* Sección 2: DESCRIPCIÓN */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold uppercase tracking-wider text-white/50">Descripción / Gancho</span>
              <button
                type="button"
                onClick={() => copyToClipboard(currentDesc, "desc")}
                className="flex items-center gap-1 text-beam-300 hover:text-beam-200 text-[10.5px] font-medium"
              >
                {copiedSection === "desc" ? (
                  <>
                    <IconCheck className="h-3 w-3 text-emerald-400" />
                    <span className="text-emerald-300">Copiado</span>
                  </>
                ) : (
                  <>
                    <IconCopy className="h-3 w-3" />
                    <span>Copiar Descripción</span>
                  </>
                )}
              </button>
            </div>
            <div className="p-3 rounded-xl border border-white/[0.08] bg-black/40 text-[11.5px] text-white/80 whitespace-pre-line leading-relaxed select-all max-h-36 overflow-y-auto">
              {loading ? "Generando descripción estructurada..." : currentDesc}
            </div>
          </div>

          {/* Sección 3: HASHTAGS */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold uppercase tracking-wider text-white/50">Hashtags Virales (#)</span>
              <button
                type="button"
                onClick={() => copyToClipboard(currentTags, "tags")}
                className="flex items-center gap-1 text-beam-300 hover:text-beam-200 text-[10.5px] font-medium"
              >
                {copiedSection === "tags" ? (
                  <>
                    <IconCheck className="h-3 w-3 text-emerald-400" />
                    <span className="text-emerald-300">Copiado</span>
                  </>
                ) : (
                  <>
                    <IconCopy className="h-3 w-3" />
                    <span>Copiar Hashtags</span>
                  </>
                )}
              </button>
            </div>
            <div className="p-3 rounded-xl border border-white/[0.08] bg-black/40 text-[11px] text-beam-200/90 font-mono select-all flex flex-wrap gap-1.5">
              {loading ? (
                <span className="text-white/40">Cargando hashtags...</span>
              ) : info?.hashtags && info.hashtags.length > 0 ? (
                info.hashtags.map((tag, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded-md bg-beam-500/10 border border-beam-400/20 text-beam-200 text-[10.5px]"
                  >
                    {tag}
                  </span>
                ))
              ) : (
                <span>{currentTags}</span>
              )}
            </div>
          </div>

          {/* Sección 4: PUBLICAR EN YOUTUBE */}
          <div className="space-y-2.5 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-semibold uppercase tracking-wider text-white/50">Publicar en YouTube</span>
              {yt?.connected ? (
                <span className="flex items-center gap-1.5 text-white/60">
                  <span className="h-1.5 w-1.5 rounded-full bg-signal-400" />
                  {accounts.length > 1 ? `${accounts.length} canales` : selectedAccount?.title || yt.channel?.title || "Canal conectado"}
                </span>
              ) : (
                <span className="text-white/35">Sin conectar</span>
              )}
            </div>

            {!yt ? (
              <p className="text-[11px] text-white/40">Consultando estado de YouTube...</p>
            ) : !yt.configured ? (
              <p className="text-[11px] leading-relaxed text-white/50">
                Falta configurar <span className="font-mono text-white/70">YOUTUBE_CLIENT_ID</span> (y opcionalmente
                <span className="font-mono text-white/70"> YOUTUBE_CLIENT_SECRET</span>) en el archivo .env y reiniciar el servidor.
              </p>
            ) : !yt.connected ? (
              <button
                type="button"
                onClick={connectYouTube}
                className="w-full rounded-lg border border-white/15 bg-white/[0.06] py-2 text-[11.5px] font-medium text-white hover:bg-white/[0.1] transition-colors cursor-pointer"
              >
                Conectar canal de YouTube
              </button>
            ) : (
              <>
                {/* Formato detectado: Short o Video */}
                <div className="flex flex-wrap items-center gap-1.5 text-[10.5px]">
                  <span className="rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-medium text-white/70">
                    {effectiveFormat === "short" ? "Short" : "Video largo"}
                  </span>
                  {suggestion && (
                    <span className="text-white/35">
                      {suggestion.width}x{suggestion.height} · {Math.round(suggestion.duration)} s
                    </span>
                  )}
                  <select
                    value={formatSel}
                    onChange={(e) => setFormatSel(e.target.value as PublishFormat)}
                    disabled={pubBusy}
                    title="Cómo se publicará en YouTube"
                    className="ml-auto rounded-md border border-white/10 bg-black/60 px-1.5 py-0.5 text-[10.5px] text-white/60 focus:outline-none"
                  >
                    <option value="auto">Detectar automático</option>
                    <option value="short">Forzar Short</option>
                    <option value="video">Forzar video largo</option>
                  </select>
                </div>

                {/* Canales conectados */}
                <div className="flex flex-wrap gap-1.5">
                  {accounts.map((a) => {
                    const active = a.channel_id === selectedAccount?.channel_id;
                    return (
                      <button
                        key={a.channel_id}
                        type="button"
                        onClick={() => setChannelId(a.channel_id)}
                        disabled={pubBusy}
                        className={`flex items-center gap-1.5 rounded-lg border px-2 py-1 text-[11px] transition-colors cursor-pointer ${
                          active
                            ? "border-white/25 bg-white/[0.1] text-white"
                            : "border-white/[0.08] bg-white/[0.02] text-white/55 hover:text-white/80"
                        }`}
                      >
                        <span className="max-w-[120px] truncate">{a.title || "Canal"}</span>
                        {a.tag && (
                          <span className="rounded border border-white/10 px-1 text-[9.5px] text-white/50">{a.tag}</span>
                        )}
                      </button>
                    );
                  })}
                  <button
                    type="button"
                    onClick={connectYouTube}
                    disabled={pubBusy}
                    className="rounded-lg border border-dashed border-white/15 px-2 py-1 text-[11px] text-white/45 hover:text-white/80 transition-colors cursor-pointer"
                  >
                    Agregar canal
                  </button>
                </div>
                {suggestion?.reason && suggestion.channel_id === selectedAccount?.channel_id && accounts.length > 1 && (
                  <p className="text-[10px] text-white/35">Canal sugerido. {suggestion.reason}</p>
                )}

                {/* Etiqueta, palabras clave y tipo del canal seleccionado */}
                {selectedAccount && (
                  <div className="grid grid-cols-2 gap-1.5">
                    <input
                      value={editTag}
                      onChange={(e) => setEditTag(e.target.value)}
                      onBlur={() => editTag !== (selectedAccount.tag || "") && saveAccount({ tag: editTag })}
                      placeholder="Etiqueta (ej. Historia)"
                      maxLength={40}
                      className="rounded-lg border border-white/10 bg-black/60 px-2 py-1.5 text-[11px] text-white/80 placeholder:text-white/25 focus:outline-none focus:border-white/25"
                    />
                    <select
                      value={selectedAccount.kind || "any"}
                      onChange={(e) => saveAccount({ kind: e.target.value as ChannelKind })}
                      className="rounded-lg border border-white/10 bg-black/60 px-2 py-1.5 text-[11px] text-white/70 focus:outline-none"
                    >
                      <option value="any">Shorts y videos</option>
                      <option value="short">Solo Shorts</option>
                      <option value="video">Solo videos largos</option>
                    </select>
                    <input
                      value={editKeywords}
                      onChange={(e) => setEditKeywords(e.target.value)}
                      onBlur={() => saveAccount({ keywords: editKeywords })}
                      placeholder="Palabras clave separadas por coma: roma, imperio, filosofia"
                      className="col-span-2 rounded-lg border border-white/10 bg-black/60 px-2 py-1.5 text-[11px] text-white/80 placeholder:text-white/25 focus:outline-none focus:border-white/25"
                    />
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <select
                    value={privacy}
                    onChange={(e) => {
                      const v = e.target.value as Privacy;
                      setPrivacy(v);
                      saveAutoPublish(autoPublish, v);
                    }}
                    disabled={pubBusy}
                    className="rounded-lg border border-white/10 bg-black/60 px-2 py-2 text-[11.5px] text-white/80 focus:outline-none"
                  >
                    <option value="private">Privado</option>
                    <option value="unlisted">No listado</option>
                    <option value="public">Público</option>
                  </select>
                  <button
                    type="button"
                    onClick={handlePublish}
                    disabled={pubBusy || loading || !info}
                    className="flex-1 rounded-lg border border-white/15 bg-white/[0.08] py-2 text-[11.5px] font-medium text-white hover:bg-white/[0.14] transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                  >
                    {pubBusy ? `Publicando ${Math.round(pubPct)}%` : "Publicar ahora"}
                  </button>
                </div>

                {pubBusy && (
                  <div className="space-y-1">
                    <div className="h-1 overflow-hidden rounded-full bg-white/[0.07]">
                      <div className="h-full bg-beam-400 transition-[width] duration-300" style={{ width: `${pubPct}%` }} />
                    </div>
                    <p className="text-[10px] text-white/40">{pubMsg}</p>
                  </div>
                )}

                {pubUrl && (
                  <a
                    href={pubUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="block truncate text-[11.5px] text-beam-300 hover:text-beam-200 underline underline-offset-2"
                  >
                    Publicado: {pubUrl}
                  </a>
                )}
                {pubError && <p className="text-[11px] leading-relaxed text-ember-400">{pubError}</p>}

                <label className="flex cursor-pointer items-center gap-2 pt-1 text-[11px] text-white/55">
                  <input
                    type="checkbox"
                    checked={autoPublish}
                    onChange={(e) => {
                      setAutoPublish(e.target.checked);
                      saveAutoPublish(e.target.checked, privacy);
                    }}
                    className="h-3.5 w-3.5 accent-[#2f5cff]"
                  />
                  Publicar automáticamente cada video al terminar de crearse
                </label>
                <button
                  type="button"
                  onClick={async () => {
                    if (!selectedAccount) return;
                    await disconnectYouTube(selectedAccount.channel_id);
                    const st = await fetchYouTubeStatus();
                    setYt(st);
                    setChannelId(st.accounts?.[0]?.channel_id || "");
                  }}
                  className="text-[10px] text-white/30 hover:text-white/60 transition-colors cursor-pointer"
                >
                  Desconectar este canal
                </button>
              </>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-white/[0.08] flex justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-xl border border-white/10 bg-white/[0.04] text-[11.5px] font-medium text-white/80 hover:bg-white/[0.08]"
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

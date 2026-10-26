import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { IconClose, IconCpu, IconSparkle } from "./Icons";

interface AutopilotConfig {
  enabled: boolean;
  shorts_per_day: number;
  longs_per_day: number;
  publish_mode: "schedule" | "private";
  max_uploads_per_day: number;
  min_retention_score: number;
}

interface AutopilotChannel {
  channel_id: string;
  title?: string;
  tag?: string;
  kind?: string;
  today_shorts: number;
  today_longs: number;
  scheduled_total: number;
}

interface AutopilotJob {
  id: string;
  channel_id: string;
  channel_title?: string;
  channel_tag?: string;
  kind: "short" | "long";
  slot_at: string;
  status: string;
  progress?: number;
  message?: string;
  topic?: string;
  title?: string;
  retention_score?: number;
  video_url?: string;
  publish_at?: string;
  error?: string;
}

interface AutopilotStatus {
  config: AutopilotConfig;
  channels: AutopilotChannel[];
  jobs: AutopilotJob[];
  running: AutopilotJob | null;
  uploads_24h: number;
  hours: { short: number[]; long: number[] };
}

const STATUS_LABEL: Record<string, string> = {
  planned: "En cola",
  researching: "Investigando",
  polishing: "Puliendo con datos",
  creating: "Creando video",
  uploading: "Subiendo",
  scheduled: "Programado",
  uploaded_private: "Subido en privado",
  failed: "Con error",
};

const ACTIVE = ["researching", "polishing", "creating", "uploading"];

function fmtHour(h: number) {
  return `${String(h).padStart(2, "0")}:00`;
}

function fmtSlot(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const today = new Date();
  const same = d.toDateString() === today.toDateString();
  const tomorrow = new Date(today.getTime() + 86400000).toDateString() === d.toDateString();
  const day = same ? "Hoy" : tomorrow ? "Mañana" : d.toLocaleDateString("es", { day: "2-digit", month: "short" });
  return `${day} ${d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit", hour12: false })}`;
}

async function api<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, body === undefined ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.detail || `Error ${res.status}`);
  return data as T;
}

export function AutopilotModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [status, setStatus] = useState<AutopilotStatus | null>(null);
  const [animeState, setAnimeState] = useState<any>(null);
  const [animeBusy, setAnimeBusy] = useState(false);
  const [tourBusy, setTourBusy] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api<AutopilotStatus>("/api/autopilot/status"));
      fetch("/api/anime-series/status")
        .then((r) => r.json())
        .then((d) => setAnimeState(d))
        .catch(() => {});
      setError("");
    } catch (e: any) {
      setError(e?.message || "No se pudo leer el estado del piloto");
    }
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    refresh();
    const t = window.setInterval(refresh, 6000);
    return () => window.clearInterval(t);
  }, [isOpen, refresh]);

  if (!isOpen) return null;

  const cfg = status?.config;

  const saveConfig = async (patch: Partial<AutopilotConfig>) => {
    setBusy(true);
    try {
      setStatus(await api<AutopilotStatus>("/api/autopilot/config", patch));
      setError("");
    } catch (e: any) {
      setError(e?.message || "No se pudo guardar");
    } finally {
      setBusy(false);
    }
  };

  const jobAction = async (id: string, action: "retry" | "cancel") => {
    try {
      setStatus(await api<AutopilotStatus>(`/api/autopilot/jobs/${id}/${action}`, {}));
    } catch (e: any) {
      setError(e?.message || "No se pudo completar la acción");
    }
  };

  const selectCls =
    "rounded-lg border border-white/10 bg-black/60 px-2 py-1.5 text-[11px] text-white/80 focus:outline-none focus:border-white/25";

  const modalContent = (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="absolute inset-0" onClick={onClose} />
      <div className="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/12 bg-ink-950/98 p-5 text-left shadow-[0_25px_80px_rgba(0,0,0,0.95)] backdrop-blur-2xl sm:p-6">
        {/* Header */}
        <div className="flex shrink-0 items-start justify-between border-b border-white/[0.08] pb-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-white/15 bg-white/[0.05] text-white">
              <IconCpu className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold text-white">Piloto automático</h3>
              <p className="truncate text-[11px] text-white/40">
                Investiga, pule con datos, crea, programa y publica en cada canal
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <button
              type="button"
              role="switch"
              aria-checked={!!cfg?.enabled}
              disabled={!cfg || busy}
              onClick={() => saveConfig({ enabled: !cfg?.enabled })}
              title={cfg?.enabled ? "Pausar piloto" : "Activar piloto"}
              className={`relative h-5 w-9 rounded-full border transition-colors cursor-pointer disabled:opacity-50 ${
                cfg?.enabled ? "border-white/30 bg-white/25" : "border-white/10 bg-white/[0.05]"
              }`}
            >
              <span
                className={`absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white transition-all ${
                  cfg?.enabled ? "left-[18px]" : "left-0.5 opacity-60"
                }`}
              />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-white/40 transition-colors hover:bg-white/[0.05] hover:text-white"
            >
              <IconClose className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto py-4 pr-1">
          {error && <p className="text-[11px] text-ember-400">{error}</p>}

          {!status ? (
            <p className="text-[11px] text-white/40">Cargando estado...</p>
          ) : (
            <>
              {/* Estado general */}
              <div className="flex flex-wrap items-center gap-2 text-[11px]">
                <span className="flex items-center gap-1.5 rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-white/70">
                  <span className={`h-1.5 w-1.5 rounded-full ${cfg?.enabled ? "bg-signal-400" : "bg-white/25"}`} />
                  {cfg?.enabled ? "Activo, trabajando solo" : "En pausa"}
                </span>
                <span className="text-white/35">
                  Subidas en 24 h: {status.uploads_24h} de {cfg?.max_uploads_per_day}
                </span>
                {status.running && (
                  <span className="ml-auto truncate text-white/50">
                    Ahora: {STATUS_LABEL[status.running.status] || status.running.status}
                    {status.running.topic ? ` · ${status.running.topic.slice(0, 48)}` : ""}
                  </span>
                )}
              </div>

              {status.channels.length === 0 && (
                <p className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3 text-[11px] leading-relaxed text-white/55">
                  Conecta al menos un canal en Proyecto, Info y redes, sección Publicar en YouTube. El piloto reparte los
                  videos entre los canales conectados según su etiqueta.
                </p>
              )}

              {/* Configuración */}
              {cfg && (
                <div className="grid grid-cols-2 gap-2 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3 sm:grid-cols-4">
                  <label className="space-y-1 text-[10px] uppercase tracking-wider text-white/40">
                    Shorts por canal al día
                    <select
                      className={`${selectCls} w-full normal-case tracking-normal`}
                      value={cfg.shorts_per_day}
                      onChange={(e) => saveConfig({ shorts_per_day: Number(e.target.value) })}
                    >
                      {[0, 1, 2, 3, 4, 5, 6].map((n) => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-[10px] uppercase tracking-wider text-white/40">
                    Largos por canal al día
                    <select
                      className={`${selectCls} w-full normal-case tracking-normal`}
                      value={cfg.longs_per_day}
                      onChange={(e) => saveConfig({ longs_per_day: Number(e.target.value) })}
                    >
                      {[0, 1, 2].map((n) => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-[10px] uppercase tracking-wider text-white/40">
                    Publicación
                    <select
                      className={`${selectCls} w-full normal-case tracking-normal`}
                      value={cfg.publish_mode}
                      onChange={(e) => saveConfig({ publish_mode: e.target.value as any })}
                    >
                      <option value="schedule">Programar a su hora</option>
                      <option value="public">Público directo</option>
                      <option value="private">Dejar privado para revisar</option>
                    </select>
                  </label>
                  <label className="space-y-1 text-[10px] uppercase tracking-wider text-white/40">
                    Máx. subidas al día
                    <select
                      className={`${selectCls} w-full normal-case tracking-normal`}
                      value={cfg.max_uploads_per_day}
                      onChange={(e) => saveConfig({ max_uploads_per_day: Number(e.target.value) })}
                    >
                      {[2, 4, 6, 8, 12, 20, 40].map((n) => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </label>
                  <p className="col-span-2 text-[10.5px] leading-relaxed text-white/35 sm:col-span-4">
                    Horas estratégicas (hora local): Shorts {status.hours.short.map(fmtHour).join(", ") || "ninguno"}.
                    Largos {status.hours.long.map(fmtHour).join(", ") || "ninguno"}. La cuota gratuita de la API de YouTube
                    permite unas 6 subidas al día; pide más cuota en Google Cloud para subir el límite.
                  </p>
                </div>
              )}

              {/* Canales */}
              {status.channels.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-white/40">Canales</p>
                  {status.channels.map((ch) => (
                    <div
                      key={ch.channel_id}
                      className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-1.5 text-[11px]"
                    >
                      <span className="max-w-[160px] truncate text-white/80">{ch.title || "Canal"}</span>
                      {ch.tag && (
                        <span className="rounded border border-white/10 px-1 text-[9.5px] text-white/50">{ch.tag}</span>
                      )}
                      <span className="ml-auto text-white/40">
                        Hoy: {ch.today_shorts} Shorts, {ch.today_longs} largos · Programados: {ch.scheduled_total}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Serie de Anime por Partes */}
              {animeState && (
                <div className="space-y-1.5 rounded-lg border border-purple-500/25 bg-purple-950/20 p-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-purple-500/25">
                        <IconSparkle className="h-3 w-3 text-purple-300" />
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <p className="text-[11px] font-semibold text-white truncate">
                            Serie Anime: <span className="text-purple-300">{animeState.active_series}</span>
                          </p>
                          <span className="inline-flex items-center px-1.5 py-0.2 text-[8.5px] font-medium bg-purple-500/20 text-purple-300 border border-purple-500/30 rounded-full">
                            3-4 partes/día · {animeState.config?.default_duration_min || 8} min
                          </span>
                        </div>
                        <p className="text-[9.5px] text-white/40 truncate">
                          Página Facebook: <span className="text-white/60">{animeState.facebook_page?.page_name}</span>
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={animeBusy || animeState.is_producing}
                      onClick={async () => {
                        setAnimeBusy(true);
                        try {
                          await fetch("/api/anime-series/trigger-next", { method: "POST" });
                          const s = await (await fetch("/api/anime-series/status")).json();
                          setAnimeState(s);
                        } finally {
                          setAnimeBusy(false);
                        }
                      }}
                      className="shrink-0 rounded-lg border border-purple-500/40 bg-purple-500/25 px-2.5 py-1 text-[10.5px] font-medium text-purple-200 transition-colors hover:bg-purple-500/40 disabled:opacity-50 cursor-pointer"
                    >
                      {animeState.is_producing ? "Produciendo..." : `Producir Parte ${animeState.current_part || 1}`}
                    </button>
                  </div>
                  {animeState.series_outline && (
                    <div className="mt-1 flex items-center gap-1.5 overflow-x-auto text-[10px] text-white/50">
                      <span className="shrink-0 text-white/30">Próxima en cola:</span>
                      <span className="rounded bg-white/[0.06] px-1.5 py-0.5 text-white/80 font-mono truncate">
                        Parte {animeState.current_part}: {animeState.series_outline.find((o: any) => o.part === animeState.current_part)?.subtitle || "Siguiente arco"}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Recorrido Secuencial Universal */}
              <div className="space-y-1.5 rounded-lg border border-cyan-500/25 bg-cyan-950/20 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-cyan-500/20 text-xs">🌐</span>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <p className="text-[11px] font-semibold text-white truncate">Recorrido Secuencial Universal</p>
                        <span className="inline-flex items-center px-1.5 py-0.2 text-[8.5px] font-medium bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 rounded-full">
                          5 Canales y Páginas en Cadena
                        </span>
                      </div>
                      <p className="text-[9.5px] text-white/40 truncate">
                        Recorre: the Deep dife · PixelGrama · Black Clover · Huellas Sagradas · Palabras con Peso
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={tourBusy}
                    onClick={async () => {
                      setTourBusy(true);
                      try {
                        await fetch("/api/universal-tour/run-now", { method: "POST" });
                        refresh();
                      } finally {
                        setTourBusy(false);
                      }
                    }}
                    className="shrink-0 rounded-lg border border-cyan-500/40 bg-cyan-500/25 px-2.5 py-1 text-[10.5px] font-medium text-cyan-200 transition-colors hover:bg-cyan-500/35 disabled:opacity-50 cursor-pointer"
                  >
                    {tourBusy ? "Iniciando..." : "Lanzar Ronda Ahora"}
                  </button>
                </div>
              </div>

              {/* Cola */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-white/40">Cola de producción</p>
                  <button
                    type="button"
                    onClick={() => api("/api/autopilot/run", {}).then(refresh)}
                    className="text-[10px] text-white/40 transition-colors hover:text-white/80 cursor-pointer"
                  >
                    Revisar ahora
                  </button>
                </div>
                {status.jobs.length === 0 ? (
                  <p className="text-[11px] text-white/35">
                    {cfg?.enabled
                      ? "Planificando los próximos huecos..."
                      : "Activa el piloto para que empiece a planificar videos."}
                  </p>
                ) : (
                  status.jobs.map((job) => {
                    const active = ACTIVE.includes(job.status);
                    return (
                      <div key={job.id} className="space-y-1 rounded-lg border border-white/[0.06] bg-white/[0.02] px-2.5 py-2">
                        <div className="flex items-center gap-2 text-[11px]">
                          <span className="w-[78px] shrink-0 text-white/50">{fmtSlot(job.publish_at || job.slot_at)}</span>
                          <span className="shrink-0 rounded border border-white/10 px-1 text-[9.5px] text-white/60">
                            {job.kind === "short" ? "Short" : "Largo"}
                          </span>
                          <span className="max-w-[110px] shrink-0 truncate text-white/45">
                            {job.channel_tag || job.channel_title || "Canal"}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-white/75">
                            {job.title || job.topic || "Tema por elegir"}
                          </span>
                          <span
                            className={`shrink-0 text-[10px] ${
                              job.status === "failed" ? "text-ember-400" : active ? "text-beam-300" : "text-white/45"
                            }`}
                          >
                            {STATUS_LABEL[job.status] || job.status}
                          </span>
                          {job.video_url && (
                            <a
                              href={job.video_url}
                              target="_blank"
                              rel="noreferrer"
                              className="shrink-0 text-[10px] text-beam-300 underline underline-offset-2 hover:text-beam-200"
                            >
                              Ver
                            </a>
                          )}
                          {job.status === "failed" && (
                            <button
                              type="button"
                              onClick={() => jobAction(job.id, "retry")}
                              className="shrink-0 text-[10px] text-white/50 hover:text-white cursor-pointer"
                            >
                              Reintentar
                            </button>
                          )}
                          {(job.status === "planned" || active || job.status === "failed") && (
                            <button
                              type="button"
                              onClick={() => jobAction(job.id, "cancel")}
                              className="shrink-0 text-[10px] text-white/30 hover:text-white/70 cursor-pointer"
                            >
                              Quitar
                            </button>
                          )}
                        </div>
                        {active && (
                          <div className="space-y-0.5">
                            <div className="h-0.5 overflow-hidden rounded-full bg-white/[0.07]">
                              <div
                                className="h-full bg-beam-400 transition-[width] duration-500"
                                style={{ width: `${job.progress || 0}%` }}
                              />
                            </div>
                            {job.message && <p className="truncate text-[10px] text-white/35">{job.message}</p>}
                          </div>
                        )}
                        {job.status === "failed" && job.message && (
                          <p className="truncate text-[10px] text-ember-400/80">{job.message}</p>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </>
          )}
        </div>

        <div className="flex shrink-0 justify-end border-t border-white/[0.08] pt-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-1.5 text-[11.5px] font-medium text-white/80 hover:bg-white/[0.08]"
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

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  AUTOMATIONS,
  BASE_RETENTION,
  CLIPS,
  CAPTIONS,
  DURATION,
  PLATFORMS,
  type Clip,
  type Caption,
  type PlatformId,
  type Ratio,
  retentionAt,
  type Automation,
} from "./data";

export type LogEntry = {
  id: number;
  text: string;
  kind: "ai" | "info" | "warn";
  at: string;
};

export type BackendProject = {
  id: string;
  name: string;
  topic?: string;
  status: string;
  duration: number;
  updated_at?: string;
  thumbnail_url?: string | null;
  master_video_url?: string | null;
  has_plan?: boolean;
  has_result?: boolean;
};

export interface ProducerPlan {
  retention_score: number;
  original_critique: string;
  master_hook: string;
  supporting_facts: Array<{ fact: string; source_tag: string }>;
  visual_atmosphere: string;
  recommended_bgm: string;
  recommended_format: "reel" | "long";
  recommended_duration_sec: number;
  polished_prompt: string;
  latency_sec: number;
  channel_learning_applied?: boolean;
  chosen_structure?: string;
  chosen_hook_type?: string;
  channel_name?: string;
}

type Ctx = {
  /* playback */
  playing: boolean;
  setPlaying: (p: boolean) => void;
  time: number;
  duration: number;
  rate: number;
  loop: boolean;
  play: () => void;
  pause: () => void;
  toggle: () => void;
  seek: (t: number) => void;
  setRate: (r: number) => void;
  setLoop: (v: boolean) => void;
  setDuration: (d: number) => void;

  /* viewer */
  ratio: Ratio;
  setRatio: (r: Ratio) => void;
  fitMode: "cover" | "contain";
  setFitMode: (m: "cover" | "contain") => void;
  toggleFitMode: () => void;
  overlays: Record<string, boolean>;
  toggleOverlay: (k: string) => void;
  previewVideoUrl: string | null;
  videoRef: React.RefObject<HTMLVideoElement | null>;

  /* timeline */
  clips: Clip[];
  selected: string | null;
  select: (id: string | null) => void;
  updateClip: (id: string, patch: Partial<Clip>) => void;
  removeClip: (id: string) => void;
  addClip: (clip: Clip) => void;
  duplicateClip: (id: string) => void;
  pxPerSec: number;
  setPxPerSec: (v: number) => void;

  /* ai */
  progress: Record<string, number>;
  applied: string[];
  run: (id: string) => void;
  running: boolean;

  /* metrics */
  platform: PlatformId;
  setPlatform: (p: PlatformId) => void;
  score: number;
  boost: number;
  metrics: {
    reach: number;
    views: number;
    saves: number;
    comments: number;
    shares: number;
    watch: number;
    ctr: number;
    avg: number;
    velocity: number;
  };

  /* ai producer & facts */
  producerPlan: ProducerPlan | null;
  setProducerPlan: React.Dispatch<React.SetStateAction<ProducerPlan | null>>;
  isAuditingTopic: boolean;
  setIsAuditingTopic: React.Dispatch<React.SetStateAction<boolean>>;
  metricsPanelCollapsed: boolean;
  setMetricsPanelCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  auditAndEnrichTopic: (topic: string, format?: "reel" | "long", durationSec?: number) => Promise<ProducerPlan | null>;

  /* channel intelligence */
  activeChannelId: string;
  setActiveChannelId: (id: string) => void;

  /* backend integration */
  projects: BackendProject[];
  activeProjectId: string | null;
  activeProjectTitle: string;
  isUploading: boolean;
  isCreating: boolean;
  createProgress: number;
  createStatusMessage: string;
  selectProject: (id: string) => void;
  loadProjects: () => Promise<void>;
  loadProject: (id: string) => Promise<void>;
  exportProgress: number | null;
  exportStatusText: string;
  mobileMenuOpen: boolean;
  setMobileMenuOpen: React.Dispatch<React.SetStateAction<boolean>>;
  leftPanelCollapsed: boolean;
  setLeftPanelCollapsed: React.Dispatch<React.SetStateAction<boolean>>;
  toggleLeftPanel: () => void;
  exportMaster: (opts?: { burnSubtitles?: boolean; style?: string; title?: string }) => Promise<void>;
  importVideo: (file: File) => Promise<void>;
  importVideoUrl: (url: string, title?: string) => Promise<void>;
  splitClipAtPlayhead: () => void;
  saveTimeline: () => Promise<void>;
  applyJumpCutSilences: (silences: { start: number; end: number; duration: number }[]) => void;
  insertTtsClip: (text: string, voice?: string) => Promise<void>;
  createVideo: (topic: string, opts?: { duration?: number; style?: string; aspect_ratio?: Ratio }) => Promise<string | null>;
  deleteProject: (id: string) => Promise<void>;
  cancelCreation: () => Promise<void>;
  resumeProject: (taskId: string) => Promise<void>;
  shortcutsModalOpen: boolean;
  setShortcutsModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  importModalOpen: boolean;
  setImportModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  silenceModalOpen: boolean;
  setSilenceModalOpen: React.Dispatch<React.SetStateAction<boolean>>;
  theaterMode: boolean;
  setTheaterMode: React.Dispatch<React.SetStateAction<boolean>>;
  toggleTheaterMode: () => void;

  /* voice */
  selectedVoice: string;
  setSelectedVoice: (v: string) => void;
  playingVoiceId: string | null;
  previewVoice: (voiceId: string) => void;

  /* subtitles */
  captions: Caption[];
  setCaptions: React.Dispatch<React.SetStateAction<Caption[]>>;
  updateCaption: (index: number, text: string) => void;
  subtitleStyle: string;
  setSubtitleStyle: (s: string) => void;
  subtitleFont: string;
  setSubtitleFont: (f: string) => void;

  /* audio / sound */
  isMuted: boolean;
  setIsMuted: (m: boolean) => void;
  toggleMute: () => void;

  flash: (msg: string) => void;
  log: LogEntry[];
  toast: string | null;
};

const EditorCtx = createContext<Ctx | null>(null);

let logId = 0;

export function EditorProvider({ children }: { children: ReactNode }) {
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(DURATION);
  const [rate, setRate] = useState(1);
  const [loop, setLoop] = useState(true);

  const [ratio, setRatio] = useState<Ratio>("9:16");
  const [fitMode, setFitMode] = useState<"cover" | "contain">("cover");
  const toggleFitMode = useCallback(() => {
    setFitMode((m) => (m === "cover" ? "contain" : "cover"));
  }, []);
  const [overlays, setOverlays] = useState<Record<string, boolean>>({
    safe: false,
    captions: true,
    grid: false,
    tracking: false,
    scopes: false,
  });

  const [clips, setClips] = useState<Clip[]>(CLIPS);
  const [selected, setSelected] = useState<string | null>("c1");
  const [pxPerSec, setPxPerSec] = useState(46);

  const [progress, setProgress] = useState<Record<string, number>>({});
  const [applied, setApplied] = useState<string[]>(["silence", "captions"]);
  const [platform, setPlatform] = useState<PlatformId>("tiktok");
  const [log, setLog] = useState<LogEntry[]>([
    { id: logId++, kind: "ai", at: "00:00", text: "Estudio iniciado · Conectado al backend" },
  ]);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);

  /* Backend project state */
  const [projects, setProjects] = useState<BackendProject[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      return urlParams.get("project") || urlParams.get("task") || localStorage.getItem("lumen_active_project") || null;
    }
    return null;
  });
  const [activeProjectTitle, setActiveProjectTitle] = useState<string>("Ritmo Nocturno — EP.02");
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createProgress, setCreateProgress] = useState(0);
  const [createStatusMessage, setCreateStatusMessage] = useState("");
  const [exportProgress, setExportProgress] = useState<number | null>(null);
  const [exportStatusText, setExportStatusText] = useState<string>("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [leftPanelCollapsed, setLeftPanelCollapsed] = useState(false);
  const [shortcutsModalOpen, setShortcutsModalOpen] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [silenceModalOpen, setSilenceModalOpen] = useState(false);
  const [theaterMode, setTheaterMode] = useState(false);
  const toggleLeftPanel = useCallback(() => {
    setLeftPanelCollapsed((prev) => !prev);
  }, []);
  const toggleTheaterMode = useCallback(() => {
    setTheaterMode((prev) => {
      const next = !prev;
      if (next) {
        setLeftPanelCollapsed(true);
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        const active = document.activeElement;
        const isEditing =
          active &&
          (active.tagName === "INPUT" ||
            active.tagName === "TEXTAREA" ||
            (active as HTMLElement).isContentEditable);
        if (!isEditing) {
          e.preventDefault();
          toggleLeftPanel();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggleLeftPanel]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const activeEsRef = useRef<EventSource | null>(null);

  /* Subtitle & Sound interactive state */
  const [captions, setCaptions] = useState<Caption[]>(CAPTIONS);
  const [subtitleStyle, setSubtitleStyle] = useState<string>("kinetic");
  const [subtitleFont, setSubtitleFont] = useState<string>("Inter Tight");
  const [isMuted, setIsMuted] = useState<boolean>(false);

  /* AI Producer & Hard Facts state */
  const [producerPlan, setProducerPlan] = useState<ProducerPlan | null>(null);
  const [isAuditingTopic, setIsAuditingTopic] = useState<boolean>(false);
  const [metricsPanelCollapsed, setMetricsPanelCollapsed] = useState<boolean>(false);
  const [activeChannelId, setActiveChannelId] = useState<string>("UC_8-TffWIAoiUMMDfiMUm2Q");

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      if (videoRef.current) {
        videoRef.current.muted = next;
        if (!next) {
          videoRef.current.volume = 1.0;
        }
      }
      return next;
    });
  }, []);

  const updateCaption = useCallback((index: number, text: string) => {
    setCaptions((prev) => {
      const copy = [...prev];
      if (copy[index]) {
        copy[index] = { ...copy[index], text };
      }
      return copy;
    });
  }, []);

  const pushLog = useCallback((text: string, kind: LogEntry["kind"] = "ai") => {
    const now = new Date();
    const at = `${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
    setLog((l) => [{ id: logId++, text, kind, at }, ...l].slice(0, 30));
  }, []);

  const flash = useCallback((text: string) => {
    setToast(text);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 2600);
  }, []);

  /* Voice selection with persistent localStorage */
  const [selectedVoice, setSelectedVoiceState] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("lumen_selected_voice") || "speechify:alejandro";
    }
    return "speechify:alejandro";
  });

  const setSelectedVoice = useCallback(
    (voiceId: string) => {
      setSelectedVoiceState(voiceId);
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("lumen_selected_voice", voiceId);
        } catch (_) {}
      }
      pushLog(`Voz de locución activa: ${voiceId}`, "info");
      flash("Voz seleccionada para los próximos videos");
    },
    [pushLog, flash],
  );

  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const audioPreviewRef = useRef<HTMLAudioElement | null>(null);

  const previewVoice = useCallback(
    (voiceId: string) => {
      try {
        if (audioPreviewRef.current) {
          audioPreviewRef.current.pause();
          audioPreviewRef.current.currentTime = 0;
          audioPreviewRef.current = null;
        }

        if (playingVoiceId === voiceId) {
          setPlayingVoiceId(null);
          return;
        }

        setPlayingVoiceId(voiceId);
        pushLog(`Escuchando muestra de locución: ${voiceId}`, "info");

        const audioUrl = `/api/tts-preview?voice=${encodeURIComponent(voiceId)}&t=${Date.now()}`;
        const audio = new Audio(audioUrl);
        audioPreviewRef.current = audio;

        audio.onended = () => {
          setPlayingVoiceId(null);
          audioPreviewRef.current = null;
        };

        audio.onerror = () => {
          setPlayingVoiceId(null);
          audioPreviewRef.current = null;
          pushLog("No se pudo reproducir la muestra de voz", "warn");
        };

        audio.play().catch((e) => {
          console.warn("Reproducción de audio prevenida:", e);
          setPlayingVoiceId(null);
        });
      } catch (err: any) {
        setPlayingVoiceId(null);
        console.warn("Error en previewVoice:", err);
      }
    },
    [playingVoiceId, pushLog],
  );

  /* ---------------- playback engine ---------------- */
  const raf = useRef<number>(0);
  const last = useRef<number>(0);

  useEffect(() => {
    if (!playing) return;
    last.current = performance.now();
    const tick = (now: number) => {
      if (videoRef.current && previewVideoUrl) {
        setTime(videoRef.current.currentTime);
        if (videoRef.current.ended) {
          if (loop) {
            videoRef.current.currentTime = 0;
            videoRef.current.play().catch(() => {});
          } else {
            setPlaying(false);
          }
        }
      } else {
        const dt = ((now - last.current) / 1000) * rate;
        last.current = now;
        setTime((t) => {
          const n = t + dt;
          if (n >= duration) {
            if (loop) return n - duration;
            setPlaying(false);
            return duration;
          }
          return n;
        });
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, rate, loop, duration, previewVideoUrl]);

  const seek = useCallback(
    (t: number) => {
      const target = Math.max(0, Math.min(duration, t));
      setTime(target);
      if (videoRef.current) {
        videoRef.current.currentTime = target;
      }
    },
    [duration],
  );

  const play = useCallback(async () => {
    if (videoRef.current && previewVideoUrl) {
      try {
        videoRef.current.volume = 1.0;
        videoRef.current.muted = isMuted;
        await videoRef.current.play();
        setPlaying(true);
      } catch (err: any) {
        console.warn("[Player] Playback rejected by browser, checking autoplay policy:", err);
        if (err?.name === "NotAllowedError") {
          try {
            videoRef.current.muted = true;
            setIsMuted(true);
            await videoRef.current.play();
            setPlaying(true);
          } catch (_) {
            setPlaying(false);
          }
        } else {
          setPlaying(false);
        }
      }
    } else {
      setPlaying(true);
    }
  }, [previewVideoUrl, isMuted]);

  const pause = useCallback(() => {
    if (videoRef.current && previewVideoUrl) {
      videoRef.current.pause();
    }
    setPlaying(false);
  }, [previewVideoUrl]);

  const toggle = useCallback(() => {
    if (videoRef.current && previewVideoUrl) {
      if (videoRef.current.paused) {
        play();
      } else {
        pause();
      }
    } else {
      setPlaying((p) => !p);
    }
  }, [play, pause, previewVideoUrl]);

  const handleSetRate = useCallback((r: number) => {
    setRate(r);
    if (videoRef.current) {
      videoRef.current.playbackRate = r;
    }
  }, []);

  /* ---------------- backend project loading ---------------- */
  const loadProject = useCallback(
    async (id: string) => {
      try {
        pushLog(`Cargando proyecto ${id}...`, "info");
        const res = await fetch(`/api/projects/${id}`);
        if (!res.ok) throw new Error("Proyecto no encontrado");
        const data = await res.json();
        const proj = data.project || {};
        const title = (proj.result && proj.result.title) || proj.title || proj.original_name || `Proyecto ${id}`;
        setActiveProjectId(id);
        setActiveProjectTitle(title);
        const projRatio = proj.options?.aspect_ratio || proj.aspect_ratio || data.aspect_ratio;
        if (projRatio === "16:9" || projRatio === "9:16" || projRatio === "1:1" || projRatio === "4:5") {
          setRatio(projRatio as Ratio);
        }
        if (typeof window !== "undefined") {
          try {
            localStorage.setItem("lumen_active_project", id);
            const url = new URL(window.location.href);
            if (url.searchParams.get("project") !== id) {
              url.searchParams.set("project", id);
              window.history.replaceState({}, "", url.toString());
            }
          } catch (_) {}
        }

        const sceneSum = data.editor?.scenes
          ? data.editor.scenes.reduce((acc: number, s: any) => acc + (s.duration || 0), 0)
          : 0;
        const dur =
          (data.editor?.duration && data.editor.duration > 0 ? data.editor.duration : null) ||
          (sceneSum > 0 ? sceneSum : null) ||
          proj.result?.duration ||
          45;
        if (dur && dur > 0) {
          setDuration(Math.round(dur));
        }

        // Reset de reproducción limpio para proyecto nuevo
        setTime(0);
        setPlaying(false);
        if (videoRef.current) {
          videoRef.current.currentTime = 0;
          videoRef.current.pause();
        }

        // Conectar url de previsualización sin subtítulos quemados
        setPreviewVideoUrl(`/api/projects/${id}/preview?v=${Date.now()}`);

        // Construir pistas sincronizadas desde el editor real
        if (data.editor && data.editor.scenes && data.editor.scenes.length > 0) {
          const editor = data.editor;
          const mappedClips: Clip[] = [];

          // 1. Pista V1: Escenas de video
          editor.scenes.forEach((sc: any, i: number) => {
            const scDur = sc.duration || 6;
            const scStart = typeof sc.start === "number" ? sc.start : 0;
            mappedClips.push({
              id: `sc-${sc.scene_id || i}`,
              track: "v1",
              start: scStart,
              duration: scDur,
              label: sc.headline || sc.name || `Escena ${i + 1}`,
              kind: "scene",
              frame: sc.thumb_url,
            });
          });

          // 2. Pista V2: B-rolls y Tarjetas informativas separados individualmente
          if (editor.brolls && editor.brolls.length > 0) {
            editor.brolls.forEach((br: any, i: number) => {
              mappedClips.push({
                id: br.id || `broll-${i}`,
                track: "v2",
                start: typeof br.start === "number" ? br.start : 0,
                duration: Math.max(1.5, br.duration || 4),
                label: `B-Roll · ${br.concept || br.title || `Clip ${i + 1}`}`,
                kind: "broll",
                frame: br.card_url || br.thumb_url,
                ai: true,
              });
            });
          }

          if (editor.cards && editor.cards.length > 0) {
            editor.cards.forEach((cd: any, i: number) => {
              mappedClips.push({
                id: cd.id || `card-${i}`,
                track: "v2",
                start: typeof cd.start === "number" ? cd.start : 0,
                duration: Math.max(1.8, cd.duration || 4.5),
                label: `Inserto · ${cd.headline || cd.title || "Dato clave"}`,
                kind: "broll",
                frame: cd.card_url,
                ai: true,
              });
            });
          }

          // 3. Pista T1: Subtítulos cinéticos sincronizados
          if (editor.captions && editor.captions.length > 0) {
            editor.scenes.forEach((sc: any, i: number) => {
              const sid = sc.scene_id || (i + 1);
              const scCaps = editor.captions.filter((c: any) => c.scene_id === sid);
              if (scCaps.length > 0) {
                const cStart = scCaps[0].start;
                const cEnd = scCaps[scCaps.length - 1].end;
                mappedClips.push({
                  id: `cap-sc-${sid}`,
                  track: "t1",
                  start: cStart,
                  duration: Math.max(1, cEnd - cStart),
                  label: "Subtítulos cinéticos",
                  kind: "caption",
                  ai: true,
                });
              } else {
                mappedClips.push({
                  id: `cap-sc-${sid}`,
                  track: "t1",
                  start: sc.start + 0.3,
                  duration: Math.max(1, (sc.duration || 6) - 0.6),
                  label: "Subtítulos cinéticos",
                  kind: "caption",
                  ai: true,
                });
              }
            });
            setCaptions(
              editor.captions.map((c: any) => ({
                start: c.start,
                end: c.end,
                text: c.text,
                hot: c.text.length < 35,
              }))
            );
          } else {
            editor.scenes.forEach((sc: any, i: number) => {
              const sid = sc.scene_id || (i + 1);
              mappedClips.push({
                id: `cap-sc-${sid}`,
                track: "t1",
                start: sc.start + 0.3,
                duration: Math.max(1, (sc.duration || 6) - 0.6),
                label: "Subtítulos cinéticos",
                kind: "caption",
                ai: true,
              });
            });
          }

          // 4. Pista A1: Locución de audio sincronizada por escena sin solapamientos
          editor.scenes.forEach((sc: any, i: number) => {
            const sid = sc.scene_id || (i + 1);
            const speechText = sc.speech || "";
            const shortLabel = speechText ? speechText.slice(0, 24) + "..." : (sc.name || `E${sid}`);
            mappedClips.push({
              id: `voice-${sid}`,
              track: "a1",
              start: sc.start,
              duration: sc.duration,
              label: `Locución · E${sid}: ${shortLabel}`,
              kind: "voice",
              ai: true,
            });
          });

          setClips(mappedClips);
        }

        pushLog(`✓ Proyecto cargado: ${title}`, "ai");
        flash(`Cargado: ${title}`);
        (window as any).currentProjectId = id;
      } catch (err: any) {
        pushLog(`Error cargando proyecto: ${err.message}`, "warn");
      }
    },
    [pushLog, flash],
  );

  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch("/api/projects");
      if (!res.ok) return;
      const data = await res.json();
      if (data.projects && Array.isArray(data.projects)) {
        setProjects(data.projects);

        const urlParams = new URLSearchParams(window.location.search);
        const qProj =
          urlParams.get("project") ||
          urlParams.get("task") ||
          (typeof window !== "undefined" ? localStorage.getItem("lumen_active_project") : null);
        if (qProj) {
          loadProject(qProj);
        } else if (data.projects.length > 0 && !activeProjectId) {
          const ready = data.projects.find((p: any) => p.has_result) || data.projects[0];
          if (ready && ready.id) {
            loadProject(ready.id);
          }
        }
      }
    } catch (err) {
      console.warn("[EditorProvider] No se pudieron cargar proyectos:", err);
    }
  }, [activeProjectId, loadProject]);

  const attachCreationStream = useCallback(
    (taskId: string) => {
      if (activeEsRef.current) {
        try {
          activeEsRef.current.close();
        } catch (_) {}
        activeEsRef.current = null;
      }

      setIsCreating(true);
      if (typeof window !== "undefined") {
        try {
          localStorage.setItem("lumen_active_creation_task", taskId);
          localStorage.setItem("lumen_active_project", taskId);
          const url = new URL(window.location.href);
          url.searchParams.set("project", taskId);
          window.history.replaceState({}, "", url.toString());
        } catch (_) {}
      }

      const es = new EventSource(`/api/stream-progress/${encodeURIComponent(taskId)}`);
      activeEsRef.current = es;

      es.onmessage = (ev) => {
        try {
          const p = JSON.parse(ev.data);
          if (typeof p.progress === "number") {
            setCreateProgress(Math.max(10, Math.min(100, p.progress)));
          }
          if (p.message) {
            setCreateStatusMessage(p.message);
            pushLog(p.message, "ai");
          }
          if (p.completed) {
            es.close();
            activeEsRef.current = null;
            setCreateProgress(100);
            setCreateStatusMessage("¡Video creado con éxito!");
            setIsCreating(false);
            if (typeof window !== "undefined") {
              try {
                localStorage.removeItem("lumen_active_creation_task");
              } catch (_) {}
            }
            flash("¡Video creado y masterizado!");
            loadProjects();
            loadProject(taskId);
            import("./youtubePublish")
              .then(async (yp) => {
                const auto = yp.readAutoPublish();
                if (!auto.enabled) return;
                const st = await yp.fetchYouTubeStatus();
                if (!st.connected) return;
                pushLog("Publicación automática en YouTube iniciada...", "ai");
                flash("Publicando automáticamente en YouTube...");
                const res = await yp.publishProject(taskId, {
                  privacy: auto.privacy,
                  onProgress: (pct, msg) => setCreateStatusMessage(`YouTube ${Math.round(pct)}%: ${msg}`),
                });
                pushLog(`Publicado en YouTube: ${res.videoUrl}`, "ai");
                flash(`Publicado en YouTube: ${res.videoUrl}`);
              })
              .catch((err: any) => {
                pushLog(`No se pudo publicar automáticamente: ${err?.message || err}`, "warn");
                flash("No se pudo publicar automáticamente en YouTube");
              });
          } else if (p.error) {
            es.close();
            activeEsRef.current = null;
            setIsCreating(false);
            if (typeof window !== "undefined") {
              try {
                localStorage.removeItem("lumen_active_creation_task");
              } catch (_) {}
            }
            setCreateStatusMessage(p.error);
            pushLog(`Aviso tarea: ${p.error}`, "warn");
            flash(`Aviso: ${p.error}`);
            loadProjects();
          }
        } catch (_) {}
      };

      es.onerror = () => {
        // Desconexión transitoria: consultar endpoint de progreso directamente como respaldo
        fetch(`/api/progress/${encodeURIComponent(taskId)}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((p) => {
            if (!p) return;
            if (typeof p.progress === "number") {
              setCreateProgress(Math.max(10, Math.min(100, p.progress)));
            }
            if (p.message) {
              setCreateStatusMessage(p.message);
            }
            if (p.completed) {
              try { es.close(); } catch (_) {}
              activeEsRef.current = null;
              setCreateProgress(100);
              setCreateStatusMessage("¡Video creado con éxito!");
              setIsCreating(false);
              if (typeof window !== "undefined") {
                try { localStorage.removeItem("lumen_active_creation_task"); } catch (_) {}
              }
              flash("¡Video creado y masterizado!");
              loadProjects();
              loadProject(taskId);
            }
          })
          .catch(() => {});
      };
    },
    [pushLog, flash, loadProjects, loadProject],
  );

  const cancelCreation = useCallback(async () => {
    const taskId =
      (typeof window !== "undefined" ? localStorage.getItem("lumen_active_creation_task") : null) ||
      activeProjectId;
    if (!taskId) {
      setIsCreating(false);
      return;
    }
    try {
      pushLog(`Cancelando tarea ${taskId}...`, "warn");
      await fetch(`/api/cancel-task/${taskId}`, { method: "POST" });
      if (activeEsRef.current) {
        try {
          activeEsRef.current.close();
        } catch (_) {}
        activeEsRef.current = null;
      }
      setIsCreating(false);
      if (typeof window !== "undefined") {
        try {
          localStorage.removeItem("lumen_active_creation_task");
        } catch (_) {}
      }
      flash("Proceso cancelado.");
      loadProjects();
    } catch (err: any) {
      setIsCreating(false);
      flash(`Error al cancelar: ${err.message}`);
    }
  }, [activeProjectId, pushLog, flash, loadProjects]);

  const resumeProject = useCallback(
    async (taskId: string) => {
      try {
        setIsCreating(true);
        setCreateStatusMessage("Reanudando proceso...");
        pushLog(`Reanudando proyecto ${taskId}...`, "ai");
        flash("Reanudando proyecto...");
        const res = await fetch(`/api/projects/${taskId}/resume`, { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error al reanudar proyecto");
        attachCreationStream(taskId);
      } catch (err: any) {
        setIsCreating(false);
        flash(`Error al reanudar: ${err.message}`);
        pushLog(`Error al reanudar: ${err.message}`, "warn");
      }
    },
    [pushLog, flash, attachCreationStream],
  );

  const deleteProject = useCallback(
    async (id: string) => {
      try {
        pushLog(`Eliminando proyecto ${id}...`, "info");
        const res = await fetch(`/api/projects/${id}`, { method: "DELETE" });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || "Error al eliminar proyecto");
        }
        flash("Proyecto eliminado.");
        pushLog(`✓ Proyecto ${id} eliminado y espacio liberado`, "ai");
        await loadProjects();
        if (activeProjectId === id) {
          const remaining = projects.filter((p) => p.id !== id);
          if (remaining.length > 0) {
            loadProject(remaining[0].id);
          }
        }
      } catch (err: any) {
        flash(`Error al eliminar: ${err.message}`);
        pushLog(`Fallo al eliminar proyecto: ${err.message}`, "warn");
      }
    },
    [activeProjectId, projects, flash, pushLog, loadProjects, loadProject],
  );

  useEffect(() => {
    loadProjects();
    (window as any).openProject = (id: string) => {
      loadProject(id);
    };

    const checkActiveTasks = async () => {
      try {
        const res = await fetch("/api/tasks/active");
        if (res.ok) {
          const data = await res.json();
          if (data.active_tasks && data.active_tasks.length > 0) {
            const active = data.active_tasks[0];
            pushLog(`Reconectado a tarea activa: ${active.task_id}`, "ai");
            setCreateProgress(active.progress || 10);
            setCreateStatusMessage(active.message || "Procesando video...");
            attachCreationStream(active.task_id);
            return;
          }
        }

        const savedTaskId =
          typeof window !== "undefined" ? localStorage.getItem("lumen_active_creation_task") : null;
        if (savedTaskId) {
          const pRes = await fetch(`/api/progress/${savedTaskId}`);
          if (pRes.ok) {
            const pData = await pRes.json();
            if (pData.is_running) {
              attachCreationStream(savedTaskId);
            } else if (pData.completed) {
              if (typeof window !== "undefined") {
                try {
                  localStorage.removeItem("lumen_active_creation_task");
                } catch (_) {}
              }
              setIsCreating(false);
              loadProject(savedTaskId);
            } else {
              if (typeof window !== "undefined") {
                try {
                  localStorage.removeItem("lumen_active_creation_task");
                } catch (_) {}
              }
              setIsCreating(false);
            }
          } else {
            if (typeof window !== "undefined") {
              try {
                localStorage.removeItem("lumen_active_creation_task");
              } catch (_) {}
            }
            setIsCreating(false);
          }
        }
      } catch (_) {}
    };

    checkActiveTasks();

    return () => {
      if (activeEsRef.current) {
        try {
          activeEsRef.current.close();
        } catch (_) {}
      }
    };
  }, [loadProjects, loadProject, attachCreationStream, pushLog]);

  const selectProject = useCallback(
    (id: string) => {
      loadProject(id);
    },
    [loadProject],
  );

  const exportMaster = useCallback(
    async (opts?: { burnSubtitles?: boolean; style?: string; title?: string }) => {
      const targetId = activeProjectId || (projects.length > 0 ? projects[0].id : null);
      if (!targetId) {
        flash("No hay proyectos en el servidor para exportar");
        return;
      }
      const burnSubs = typeof opts?.burnSubtitles === "boolean" ? opts.burnSubtitles : overlays.captions;
      const subStyle = opts?.style || subtitleStyle;
      const downloadTitle = (opts?.title || activeProjectTitle || "video_master").trim();
      const safeBase = downloadTitle.replace(/[\\/:*?"<>|]+/g, "").trim().replace(/\s+/g, "_").slice(0, 120) || `master_${targetId}`;
      const finalMp4Name = safeBase.toLowerCase().endsWith(".mp4") ? safeBase : `${safeBase}.mp4`;

      try {
        setExportProgress(50);
        setExportStatusText("Descargando...");
        pushLog(`Iniciando descarga: ${downloadTitle} (${burnSubs ? "Con subtítulos" : "Video limpio"})...`, "info");
        flash(`Preparando ${finalMp4Name}...`);

        const isLocalhost = typeof window !== "undefined" &&
          (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

        // 1. En el mismo equipo: el servidor guarda el MP4 directo en Descargas con nombre real
        let savedDirectly = false;
        if (isLocalhost) {
          try {
            const r = await fetch(`/api/projects/${targetId}/export-to-downloads`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                burn_subtitles: burnSubs,
                style: subStyle,
                title: downloadTitle,
              }),
            });
            const data = await r.json();
            if (r.ok && data?.ok) {
              savedDirectly = true;
              pushLog(`✓ Video guardado en Descargas: ${data.path}`, "ai");
              flash(`¡Guardado en Descargas!: ${data.filename}`);
            }
          } catch (_) {
            savedDirectly = false;
          }
        }

        // 2. Otros dispositivos (celular) o si falló la copia local: descarga estándar del navegador
        if (!savedDirectly) {
          const downloadUrl = `/api/projects/${targetId}/download/${encodeURIComponent(finalMp4Name)}?burn_subtitles=${burnSubs ? "true" : "false"}&style=${encodeURIComponent(subStyle)}&v=${Date.now()}`;
          const a = document.createElement("a");
          a.href = downloadUrl;
          a.download = finalMp4Name;
          document.body.appendChild(a);
          a.click();
          setTimeout(() => a.remove(), 2500);
          pushLog(`✓ Descargando video máster: ${finalMp4Name}`, "ai");
          flash(`¡Descargando video!: ${finalMp4Name}`);
        }

        setExportProgress(100);
        setTimeout(() => {
          setExportProgress(null);
          setExportStatusText("");
        }, 2500);
      } catch (e: any) {
        setExportProgress(null);
        setExportStatusText("");
        pushLog(`Fallo en exportación: ${e.message}`, "warn");
        flash(`Error al exportar: ${e.message}`);
      }
    },
    [activeProjectId, projects, activeProjectTitle, overlays.captions, subtitleStyle, pushLog, flash],
  );

  const importVideo = useCallback(
    async (file: File) => {
      try {
        setIsUploading(true);
        pushLog(`Iniciando subida: ${file.name}...`, "info");
        flash(`Subiendo ${file.name}...`);
        const form = new FormData();
        form.append("video", file);
        form.append("silence_threshold", "1.5");
        form.append("broll", "true");
        form.append("cards", "true");
        form.append("captions", "true");
        form.append("shorts", "true");
        form.append("voice", selectedVoice);

        const res = await fetch("/api/process-video", {
          method: "POST",
          body: form,
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error en el servidor al recibir video");

        const taskId = data.task_id;
        pushLog(`Procesando video (Tarea: ${taskId})...`, "ai");
        flash(`Tarea ${taskId} en proceso`);
        attachCreationStream(taskId);
      } catch (err: any) {
        setIsUploading(false);
        pushLog(`Fallo al importar video: ${err.message}`, "warn");
        flash(`Error: ${err.message}`);
      }
    },
    [pushLog, flash, selectedVoice, attachCreationStream],
  );

  const importVideoUrl = useCallback(
    async (url: string, title?: string) => {
      const cleanUrl = url.trim();
      if (!cleanUrl) {
        flash("Ingresa una URL válida");
        return;
      }
      try {
        setIsUploading(true);
        pushLog(`Iniciando importación remota: ${cleanUrl.slice(0, 50)}...`, "info");
        flash(`Conectando con enlace...`);

        const res = await fetch("/api/v1/videos/process-url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            video_url: cleanUrl,
            title: title || undefined,
            voice: selectedVoice,
            silence_threshold: 1.5,
            enable_broll: true,
            enable_captions: true,
            enable_shorts: true,
          }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.message || "Error al procesar URL remota");

        const taskId = data.data?.task_id || data.task_id;
        pushLog(`Descargando y procesando video (Tarea: ${taskId})...`, "ai");
        flash(`Tarea ${taskId} en descarga remota`);
        attachCreationStream(taskId);
      } catch (err: any) {
        setIsUploading(false);
        pushLog(`Fallo al importar URL: ${err.message}`, "warn");
        flash(`Error: ${err.message}`);
      }
    },
    [pushLog, flash, selectedVoice, attachCreationStream],
  );

  const splitClipAtPlayhead = useCallback(() => {
    setClips((prev) => {
      let target = prev.find(
        (c) => c.id === selected && time > c.start + 0.15 && time < c.start + c.duration - 0.15,
      );

      if (!target) {
        target =
          prev.find((c) => c.track === "v1" && time > c.start + 0.15 && time < c.start + c.duration - 0.15) ||
          prev.find((c) => c.track === "v2" && time > c.start + 0.15 && time < c.start + c.duration - 0.15) ||
          prev.find((c) => time > c.start + 0.15 && time < c.start + c.duration - 0.15);
      }

      if (!target) {
        flash("Coloca el cabezal sobre un clip para dividirlo (S)");
        return prev;
      }

      const splitPoint = Math.round(time * 100) / 100;
      const firstDuration = Math.round((splitPoint - target.start) * 100) / 100;
      const secondDuration = Math.round((target.duration - firstDuration) * 100) / 100;

      if (firstDuration < 0.2 || secondDuration < 0.2) {
        flash("El fragmento resultante es demasiado corto para dividir");
        return prev;
      }

      const clipA: Clip = {
        ...target,
        duration: firstDuration,
      };

      const clipB: Clip = {
        ...target,
        id: `${target.id}-split-${Date.now().toString(36)}`,
        start: splitPoint,
        duration: secondDuration,
        label: `${target.label} (Parte 2)`,
      };

      flash(`✂ Clip dividido en ${splitPoint.toFixed(1)}s`);
      return prev.map((c) => (c.id === target!.id ? clipA : c)).concat(clipB);
    });
  }, [time, selected, flash]);

  const saveTimeline = useCallback(async () => {
    if (!activeProjectId) {
      flash("Abre un proyecto para guardar el timeline");
      return;
    }
    const cards = clips
      .filter((c) => c.id.startsWith("card-"))
      .map((c) => ({ id: c.id, start: c.start, duration: c.duration, enabled: true }));
    const brolls = clips
      .filter((c) => c.id.startsWith("broll-"))
      .map((c) => ({ id: c.id, start: c.start, end: c.start + c.duration, enabled: true }));
    try {
      const res = await fetch(`/api/projects/${activeProjectId}/timeline`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cards, brolls }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || data.message || "No se pudo guardar el timeline");
      flash("Timeline guardado");
      pushLog("Cambios del timeline guardados", "ai");
    } catch (err: any) {
      flash(`Error al guardar timeline: ${err.message}`);
      pushLog(`Error guardando timeline: ${err.message}`, "warn");
    }
  }, [activeProjectId, clips, flash, pushLog]);

  const applyJumpCutSilences = useCallback(
    (silences: { start: number; end: number; duration: number }[]) => {
      if (!silences || silences.length === 0) {
        flash("No se detectaron pausas de silencio que requieran corte");
        return;
      }

      const sortedSilences = [...silences].sort((a, b) => a.start - b.start);

      setClips((prevClips) => {
        let updatedClips = [...prevClips];

        for (const silence of sortedSilences) {
          const sStart = silence.start;
          const sEnd = silence.end;
          const sDur = silence.duration;
          if (sDur <= 0.1) continue;

          const nextClips: Clip[] = [];

          for (const clip of updatedClips) {
            const clipEnd = clip.start + clip.duration;

            if (clipEnd <= sStart) {
              nextClips.push(clip);
            } else if (clip.start >= sEnd) {
              nextClips.push({
                ...clip,
                start: Math.max(0, Math.round((clip.start - sDur) * 100) / 100),
              });
            } else {
              if (sStart - clip.start >= 0.2) {
                nextClips.push({
                  ...clip,
                  duration: Math.round((sStart - clip.start) * 100) / 100,
                });
              }
              if (clipEnd - sEnd >= 0.2) {
                nextClips.push({
                  ...clip,
                  id: `${clip.id}-cut-${Date.now().toString(36)}`,
                  start: Math.max(0, Math.round(sStart * 100) / 100),
                  duration: Math.round((clipEnd - sEnd) * 100) / 100,
                });
              }
            }
          }

          updatedClips = nextClips;
        }

        const maxEnd = updatedClips.reduce((acc, c) => Math.max(acc, c.start + c.duration), 0);
        if (maxEnd > 0) {
          setDuration(Math.round(maxEnd));
        }

        const totalSaved = sortedSilences.reduce((acc, s) => acc + s.duration, 0);
        flash(`✂ ¡Auto-JumpCut aplicado! Se eliminaron ${sortedSilences.length} pausas (${totalSaved.toFixed(1)}s reducidos)`);
        pushLog(`Auto-JumpCut completado: ${sortedSilences.length} pausas eliminadas, ${totalSaved.toFixed(1)}s recortados.`, "ai");

        return updatedClips;
      });
    },
    [flash, pushLog],
  );

  const insertTtsClip = useCallback(
    async (text: string, voice?: string) => {
      const cleanText = text.trim();
      if (!cleanText) {
        flash("Escribe el texto que deseas sintetizar");
        return;
      }
      const v = voice || selectedVoice || "es-MX-JorgeNeural";
      try {
        flash("Sintetizando locución neuronal...");
        pushLog(`Sintetizando locución con ${v}...`, "ai");

        const res = await fetch("/api/v1/tts/synthesize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: cleanText,
            voice: v,
          }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || data.message || "Error en síntesis TTS");

        const estDuration = Math.max(2.0, Math.round((cleanText.length / 14) * 10) / 10);
        const clipStart = Math.round(time * 10) / 10;

        const newClip: Clip = {
          id: `tts-${Date.now().toString(36)}`,
          track: "a1",
          start: clipStart,
          duration: estDuration,
          label: `Voz · ${cleanText.slice(0, 24)}${cleanText.length > 24 ? "..." : ""}`,
          kind: "voice",
          ai: true,
        };

        setClips((prev) => [...prev, newClip]);
        setSelected(newClip.id);
        flash(`✓ Locución añadida a la línea de tiempo en ${clipStart}s`);
        pushLog(`Locución insertada en timeline (${estDuration}s)`, "ai");
      } catch (err: any) {
        flash(`Error al generar voz: ${err.message}`);
        pushLog(`Error en locución: ${err.message}`, "warn");
      }
    },
    [time, selectedVoice, flash, pushLog],
  );

  useEffect(() => {
    const handleGlobalShortcuts = (e: KeyboardEvent) => {
      const active = document.activeElement;
      const isEditing =
        active &&
        (active.tagName === "INPUT" ||
          active.tagName === "TEXTAREA" ||
          (active as HTMLElement).isContentEditable);
      if (isEditing) return;

      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setShortcutsModalOpen((prev) => !prev);
        return;
      }

      if (e.code === "Space") {
        e.preventDefault();
        toggle();
        return;
      }

      if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        seek(Math.max(0, time - 5));
        return;
      }

      if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        pause();
        return;
      }

      if (e.key === "l" || e.key === "L") {
        e.preventDefault();
        seek(Math.min(duration, time + 5));
        return;
      }

      if (e.key === "s" || e.key === "S" || e.key === "c" || e.key === "C") {
        e.preventDefault();
        splitClipAtPlayhead();
        return;
      }

      if (e.key === "Home") {
        e.preventDefault();
        seek(0);
        return;
      }

      if (e.key === "End") {
        e.preventDefault();
        seek(duration);
        return;
      }
    };

    window.addEventListener("keydown", handleGlobalShortcuts);
    return () => window.removeEventListener("keydown", handleGlobalShortcuts);
  }, [toggle, seek, pause, time, duration, splitClipAtPlayhead]);

  const createVideo = useCallback(
    async (topic: string, opts?: { duration?: number; style?: string; aspect_ratio?: Ratio }) => {
      const cleanTopic = topic.trim();
      if (!cleanTopic) return null;

      try {
        const targetRatio = opts?.aspect_ratio || ratio || "16:9";
        if (opts?.aspect_ratio && opts.aspect_ratio !== ratio) {
          setRatio(opts.aspect_ratio);
        }
        setIsCreating(true);
        setCreateProgress(10);
        setCreateStatusMessage(`Investigando: «${cleanTopic}»...`);
        pushLog(`Iniciando creación de video: ${cleanTopic}`, "ai");
        flash(`Creando video: ${cleanTopic.slice(0, 30)}...`);

        const res = await fetch("/api/streamer/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            topic: cleanTopic,
            duration_sec: opts?.duration || 45,
            aspect_ratio: targetRatio,
            style: opts?.style || "divulgacion",
            voice: selectedVoice,
          }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error al iniciar la creación");

        const taskId = data.task_id || data.project_id;
        pushLog(`Tarea iniciada con ID: ${taskId}`, "info");
        attachCreationStream(taskId);
        return taskId;
      } catch (err: any) {
        setIsCreating(false);
        setCreateStatusMessage(`Fallo: ${err.message}`);
        pushLog(`Error al crear video: ${err.message}`, "warn");
        flash(`Error: ${err.message}`);
        return null;
      }
    },
    [ratio, selectedVoice, pushLog, flash, attachCreationStream],
  );

  const auditAndEnrichTopic = useCallback(
    async (topic: string, format: "reel" | "long" = "reel", durationSec?: number) => {
      const rawTopic = topic.trim();
      if (!rawTopic) {
        flash("Escribe primero un tema o idea para auditar y fundamentar con datos");
        return null;
      }
      try {
        setIsAuditingTopic(true);
        setMetricsPanelCollapsed(false);
        const durDisplay = durationSec ? (durationSec >= 60 ? `${Math.round(durationSec / 60)}m` : `${durationSec}s`) : (format === "reel" ? "60s" : "5m");
        flash(`Productor IA: Investigando datos reales y retención (${format === "reel" ? "Reel 9:16" : "16:9"} · ${durDisplay})...`);
        const res = await fetch("/api/ai-producer/enrich-and-audit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            topic: rawTopic,
            format: format,
            duration_sec: durationSec,
            channel_id: activeChannelId,
          }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error al auditar el tema");
        setProducerPlan(data);
        flash(`¡Auditoría lista en panel derecho! Retención: ${data.retention_score}/100`);
        return data;
      } catch (err: any) {
        flash(`Aviso: ${err.message || "No se pudo auditar el tema"}`);
        return null;
      } finally {
        setIsAuditingTopic(false);
      }
    },
    [flash, activeChannelId],
  );

  /* ---------------- keyboard ---------------- */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") {
        e.preventDefault();
        toggle();
      }
      if (e.code === "ArrowRight") seek(time + (e.shiftKey ? 1 : 1 / 12));
      if (e.code === "ArrowLeft") seek(time - (e.shiftKey ? 1 : 1 / 12));
      if (e.key === "l") handleSetRate(Math.min(2, rate + 0.25));
      if (e.key === "j") handleSetRate(Math.max(0.25, rate - 0.25));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [seek, time, toggle, handleSetRate, rate]);

  /* ---------------- AI engine ---------------- */
  const running = Object.keys(progress).length > 0 || isUploading || isCreating;

  const run = useCallback(
    (id: string) => {
      const auto = AUTOMATIONS.find((a) => a.id === id);
      if (!auto || applied.includes(id) || progress[id] !== undefined) return;
      setProgress((p) => ({ ...p, [id]: 0 }));
      pushLog(`Ejecutando · ${auto.name}`);
      const step = 100 / (auto.ms / 80);
      let v = 0;
      const timer = window.setInterval(() => {
        v += step;
        if (v >= 100) {
          window.clearInterval(timer);
          setProgress((p) => {
            const { [id]: _drop, ...rest } = p;
            return rest;
          });
          setApplied((a) => (a.includes(id) ? a : [...a, id]));
          pushLog(`✓ ${auto.name} aplicado`, "info");
          flash(`${auto.name} · aplicado al máster`);
          return;
        }
        setProgress((p) => ({ ...p, [id]: v }));
      }, 80);
    },
    [applied, progress, pushLog, flash],
  );

  /* ---------------- metrics ---------------- */
  const { score, boost } = useMemo(() => {
    const s = applied.reduce(
      (acc, id) => acc + (AUTOMATIONS.find((a) => a.id === id)?.score ?? 0),
      0,
    );
    const r = applied.reduce(
      (acc, id) => acc + (AUTOMATIONS.find((a) => a.id === id)?.retention ?? 0),
      0,
    );
    return { score: Math.min(99, 58 + s), boost: Math.min(0.46, r * 0.012) };
  }, [applied]);

  const metrics = useMemo(() => {
    const mult = PLATFORMS.find((p) => p.id === platform)?.mult ?? 1;
    const reachSum = applied.reduce(
      (acc, id) => acc + (AUTOMATIONS.find((a) => a.id === id)?.reach ?? 0),
      0,
    );
    const reachMul = 1 + reachSum / 46;
    const reach = 96_000 * mult * reachMul;
    const samples = BASE_RETENTION.map((_, i) => retentionAt(i, boost));
    const avg = samples.reduce((a, b) => a + b, 0) / samples.length;
    const hook = samples.slice(0, 12).reduce((a, b) => a + b, 0) / 12;
    return {
      reach,
      views: reach * 1.34,
      saves: reach * 0.061 * (1 + boost),
      comments: reach * 0.014,
      shares: reach * 0.019 * (1 + boost * 1.4),
      watch: samples[samples.length - 1],
      ctr: 6.4 + score * 0.14,
      avg,
      velocity: hook * 100,
    };
  }, [applied, boost, platform, score]);

  const value: Ctx = {
    playing,
    setPlaying,
    time,
    duration,
    rate,
    loop,
    play,
    pause,
    toggle,
    seek,
    setRate: handleSetRate,
    setLoop,
    ratio,
    setRatio,
    fitMode,
    setFitMode,
    toggleFitMode,
    overlays,
    toggleOverlay: (k) => setOverlays((o) => ({ ...o, [k]: !o[k] })),
    previewVideoUrl,
    videoRef,
    clips,
    selected,
    select: setSelected,
    updateClip: (id, patch) =>
      setClips((cs) => cs.map((c) => (c.id === id ? { ...c, ...patch } : c))),
    removeClip: (id) => {
      setClips((cs) => cs.filter((c) => c.id !== id));
      setSelected((curr) => (curr === id ? null : curr));
    },
    addClip: (clip) => {
      setClips((cs) => [...cs, clip]);
      setSelected(clip.id);
    },
    duplicateClip: (id) => {
      setClips((cs) => {
        const item = cs.find((c) => c.id === id);
        if (!item) return cs;
        const newClip: Clip = {
          ...item,
          id: `${item.kind}-${Date.now().toString(36)}`,
          start: Math.round((item.start + item.duration + 0.1) * 100) / 100,
          label: `${item.label} (Copia)`,
        };
        return [...cs, newClip];
      });
    },
    pxPerSec,
    setPxPerSec,
    progress,
    applied,
    run,
    running,
    platform,
    setPlatform,
    score,
    boost,
    metrics,
    projects,
    activeProjectId,
    activeProjectTitle,
    isUploading,
    isCreating,
    createProgress,
    createStatusMessage,
    selectProject,
    loadProjects,
    loadProject,
    exportProgress,
    exportStatusText,
    mobileMenuOpen,
    setMobileMenuOpen,
    leftPanelCollapsed,
    setLeftPanelCollapsed,
    toggleLeftPanel,
    exportMaster,
    importVideo,
    importVideoUrl,
    splitClipAtPlayhead,
    saveTimeline,
    applyJumpCutSilences,
    insertTtsClip,
    createVideo,
    deleteProject,
    cancelCreation,
    resumeProject,
    shortcutsModalOpen,
    setShortcutsModalOpen,
    importModalOpen,
    setImportModalOpen,
    silenceModalOpen,
    setSilenceModalOpen,
    theaterMode,
    setTheaterMode,
    toggleTheaterMode,
    selectedVoice,
    setSelectedVoice,
    playingVoiceId,
    previewVoice,
    captions,
    setCaptions,
    updateCaption,
    subtitleStyle,
    setSubtitleStyle,
    subtitleFont,
    setSubtitleFont,
    isMuted,
    setIsMuted,
    toggleMute,
    setDuration,
    activeChannelId,
    setActiveChannelId,
    producerPlan,
    setProducerPlan,
    isAuditingTopic,
    setIsAuditingTopic,
    metricsPanelCollapsed,
    setMetricsPanelCollapsed,
    auditAndEnrichTopic,
    flash,
    log,
    toast,
  };

  return <EditorCtx.Provider value={value}>{children}</EditorCtx.Provider>;
}

export function useEditor() {
  const ctx = useContext(EditorCtx);
  if (!ctx) throw new Error("useEditor must be used inside EditorProvider");
  return ctx;
}

export type { Automation };

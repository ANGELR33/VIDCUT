import { useState, useRef, useEffect } from "react";
import { ASSET_FOLDERS, PRESETS, AUTOMATIONS, type Clip } from "@/lib/data";
import {
  generateDailyTopics,
  getStoredPinnedIds,
  savePinnedIds,
  syncLiveTopics,
  CATEGORY_LABELS,
  ALL_CATEGORIES,
  type ViralTopic,
  type ViralCategory,
} from "@/lib/viralTopics";
import { useEditor } from "@/lib/store";
import { cn } from "@/utils/cn";
import { Hairline, IconButton, Meter, SectionLabel, Toggle } from "./ui";
import {
  IconChevron,
  IconCrop,
  IconLayers,
  IconMusic,
  IconPlus,
  IconScissors,
  IconSparkle,
  IconType,
  IconPin,
  IconRefresh,
  IconFolder,
  IconTrash,
  IconPlay,
  IconShare,
  IconMic,
  IconFlame,
} from "./Icons";
import { ProjectDetailsModal } from "./ProjectDetailsModal";
import { ClipsModal } from "./ClipsModal";

const TABS = [
  { id: "project", label: "Proyecto", icon: IconFolder },
  { id: "research", label: "Investigación", icon: IconFlame },
  { id: "media", label: "Medios", icon: IconLayers },
  { id: "ai", label: "IA", icon: IconSparkle },
  { id: "effects", label: "Efectos", icon: IconCrop },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function LeftPanel() {
  const [tab, setTab] = useState<TabId>("ai");
  const [panelWide, setPanelWide] = useState(false);
  const [sharedPrompt, setSharedPrompt] = useState("");
  const [sharedFormat, setSharedFormat] = useState<"long" | "reel">("long");
  const {
    importVideo,
    isUploading,
    leftPanelCollapsed,
    setLeftPanelCollapsed,
    toggleLeftPanel,
    setImportModalOpen,
    theaterMode,
  } = useEditor();
  const isCollapsed = leftPanelCollapsed || theaterMode;
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex h-full min-h-0 shrink-0">
      {/* ---- rail ---- */}
      <nav className="flex h-full min-h-0 w-[54px] shrink-0 flex-col items-center gap-1 border-r border-white/[0.05] bg-black/40 py-3">
        {/* Botón principal para expandir/ocultar el panel lateral */}
        <button
          type="button"
          onClick={toggleLeftPanel}
          title={leftPanelCollapsed ? "Expandir menú (Ctrl+B)" : "Ocultar menú (Ctrl+B)"}
          className={cn(
            "group relative mb-2 grid h-9 w-9 place-items-center rounded-xl border transition-all duration-200",
            leftPanelCollapsed
              ? "border-white/25 bg-white/[0.10] text-white shadow-sm"
              : "border-white/[0.08] text-white/40 hover:border-white/20 hover:bg-white/[0.05] hover:text-white",
          )}
        >
          <svg
            viewBox="0 0 24 24"
            className={cn("h-3.5 w-3.5 transition-transform duration-300", leftPanelCollapsed && "rotate-180")}
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="11 17 6 12 11 7" />
            <polyline points="18 17 13 12 18 7" />
          </svg>
          <span className="pointer-events-none absolute left-[48px] z-50 hidden whitespace-nowrap rounded-md border border-white/10 bg-black/95 px-2.5 py-1 text-[11px] text-white/90 shadow-2xl group-hover:block">
            {leftPanelCollapsed ? "Expandir menú (Ctrl+B)" : "Ocultar menú (Ctrl+B)"}
          </span>
        </button>

        <div className="mb-1 h-px w-6 bg-white/[0.08]" />

        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.id && !leftPanelCollapsed;
          return (
            <button
              key={t.id}
              onClick={() => {
                if (leftPanelCollapsed) {
                  setTab(t.id);
                  setLeftPanelCollapsed(false);
                } else if (tab === t.id) {
                  // Clic en pestaña activa la oculta para dar todo el espacio a preview y timeline
                  setLeftPanelCollapsed(true);
                } else {
                  setTab(t.id);
                }
              }}
              title={leftPanelCollapsed ? `Abrir ${t.label}` : t.label}
              className={cn(
                "group relative grid h-10 w-10 place-items-center rounded-xl transition-all duration-200",
                active
                  ? "border border-white/15 bg-white/[0.10] text-white shadow-[0_2px_8px_rgba(0,0,0,0.5)]"
                  : "text-white/35 hover:bg-white/[0.04] hover:text-white/80",
              )}
            >
              {active && (
                <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-[2.5px] rounded-r-full bg-white/90" />
              )}
              <Icon className="h-[18px] w-[18px]" />
              <span className="pointer-events-none absolute left-[48px] z-50 hidden whitespace-nowrap rounded-md border border-white/10 bg-black/95 px-2.5 py-1 text-[11px] text-white/90 shadow-2xl group-hover:block">
                {t.label}
              </span>
            </button>
          );
        })}
        <div className="mt-auto flex flex-col items-center gap-2">
          {leftPanelCollapsed && (
            <button
              type="button"
              onClick={() => setLeftPanelCollapsed(false)}
              className="group relative grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-white/40 hover:text-white hover:border-white/25 transition-colors"
              title="Expandir menú lateral"
            >
              <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
          )}
          <div className="micro-sm rotate-180 whitespace-nowrap text-white/15 [writing-mode:vertical-rl]">
            Estudio
          </div>
        </div>
      </nav>

      {/* ---- panel ---- */}
      <aside
        className={cn(
          "glass-soft h-full min-h-0 flex flex-col rounded-none border-y-0 border-l-0 transition-all duration-300 ease-in-out",
          isCollapsed
            ? "w-0 border-r-0 opacity-0 pointer-events-none overflow-hidden"
            : panelWide
              ? "w-[390px] lg:w-[440px] opacity-100 border-r border-white/[0.05]"
              : "w-[268px] lg:w-[286px] opacity-100 border-r border-white/[0.05]",
        )}
      >
        <div className={cn("flex h-full shrink-0 flex-col min-h-0 transition-all duration-300", panelWide ? "w-[390px] lg:w-[440px]" : "w-[268px] lg:w-[286px]")}>
          <div className="flex items-center justify-between px-4 pb-3 pt-4 shrink-0">
            <div>
              <h2 className="serif-display text-[17px] leading-none text-white">
                {TABS.find((t) => t.id === tab)?.label}
              </h2>
              <p className="micro-sm mt-1.5 text-white/25">
                {tab === "project" && "Proyectos recientes y escenas"}
                {tab === "research" && "Catálogo de 1479 nichos virales e ideas"}
                {tab === "media" && "Biblioteca de clips, b-roll y subidas"}
                {tab === "ai" && "Generador asistido y pipeline neuronal"}
                {tab === "effects" && "Subtítulos cinéticos, audio y LUTs"}
              </p>
            </div>
            <div className="flex items-center gap-1.5">
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    importVideo(file);
                    e.target.value = "";
                  }
                }}
              />
              <IconButton
                size="sm"
                title={isUploading ? "Importando..." : "Importar video o enlace URL (YouTube/Web)"}
                onClick={() => setImportModalOpen(true)}
              >
                <IconPlus className={cn("h-3.5 w-3.5", isUploading && "anim-spin text-beam-300")} />
              </IconButton>
              <IconButton
                size="sm"
                title={panelWide ? "Contraer a ancho estándar (286px)" : "Expandir panel a pantalla ancha (440px) para ver todo el catálogo cómodo"}
                onClick={() => setPanelWide(!panelWide)}
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-3.5 w-3.5 text-white/70 hover:text-white"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  {panelWide ? (
                    <>
                      <polyline points="4 14 10 14 10 20" />
                      <polyline points="20 10 14 10 14 4" />
                      <line x1="14" y1="10" x2="21" y2="3" />
                      <line x1="3" y1="21" x2="10" y2="14" />
                    </>
                  ) : (
                    <>
                      <polyline points="15 3 21 3 21 9" />
                      <polyline points="9 21 3 21 3 15" />
                      <line x1="21" y1="3" x2="14" y2="10" />
                      <line x1="3" y1="21" x2="10" y2="14" />
                    </>
                  )}
                </svg>
              </IconButton>
              <IconButton
                size="sm"
                title="Ocultar menú para ampliar preview y timeline (Ctrl+B)"
                onClick={() => setLeftPanelCollapsed(true)}
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-3.5 w-3.5 text-white/60 transition-colors hover:text-white"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="15 18 9 12 15 6" />
                </svg>
              </IconButton>
            </div>
          </div>

          <div
            className={cn(
              "min-h-0 flex-1 px-3",
              tab === "ai" || tab === "research" ? "flex flex-col overflow-hidden pb-1" : "overflow-y-auto pb-4",
            )}
          >
            {tab === "project" && <ProjectTab />}
            {tab === "research" && (
              <ResearchTab
                onUseTopic={(topicText, fmt) => {
                  setSharedPrompt(topicText);
                  if (fmt) setSharedFormat(fmt);
                  setTab("ai");
                }}
              />
            )}
            {tab === "media" && <MediaTab />}
            {tab === "ai" && (
              <AITab
                sharedPrompt={sharedPrompt}
                setSharedPrompt={setSharedPrompt}
                sharedFormat={sharedFormat}
                setSharedFormat={setSharedFormat}
              />
            )}
            {tab === "effects" && <EffectsTab />}
          </div>
        </div>
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------ */

const NEURAL_VOICES = [
  { id: "speechify:alejandro", n: "Alejandro · Speechify", d: "Cálida · 1.0×" },
  { id: "speechify:aitana", n: "Aitana · Speechify", d: "Brillante · 1.0×" },
  { id: "es-MX-JorgeNeural", n: "Jorge · México", d: "Conversacional" },
  { id: "es-US-AlonsoNeural", n: "Alonso · Latino", d: "Broadcast" },
  { id: "es-CO-GonzaloNeural", n: "Gonzalo · Colombia", d: "Neutro & Calmo" },
  { id: "es-AR-TomasNeural", n: "Tomás · Argentina", d: "Directo & Enérgico" },
  { id: "es-MX-DaliaNeural", n: "Dalia · México", d: "Femenina Cálida" },
  { id: "es-AR-ElenaNeural", n: "Elena · Argentina", d: "Femenina Expresiva" },
  { id: "es-ES-AlvaroNeural", n: "Álvaro · España", d: "Tech & Divulgación" },
  { id: "clon-propio", n: "Clon de voz propio", d: "Muestra de estudio" },
];

function AITab({
  sharedPrompt,
  setSharedPrompt: _setSharedPrompt,
  sharedFormat,
  setSharedFormat: _setSharedFormat,
}: {
  sharedPrompt: string;
  setSharedPrompt?: (p: string) => void;
  sharedFormat: "long" | "reel";
  setSharedFormat?: (f: "long" | "reel") => void;
}) {
  const {
    isCreating,
    createProgress,
    createStatusMessage,
    createVideo,
    cancelCreation,
    resumeProject,
    flash,
    projects,
    activeProjectId,
    activeProjectTitle,
    selectedVoice,
    setSelectedVoice,
    previewVoice,
    playingVoiceId,
    setRatio,
    producerPlan,
    isAuditingTopic,
    auditAndEnrichTopic,
    progress,
    applied,
    run,
  } = useEditor();

  const [topicPrompt, setTopicPrompt] = useState(sharedPrompt || "");
  const [videoFormat, setVideoFormat] = useState<"long" | "reel">(sharedFormat || "long");
  const [targetDurationMin, setTargetDurationMin] = useState<number>(15);
  const [targetReelSec, setTargetReelSec] = useState<number>(60);
  const [isExtractingClips, setIsExtractingClips] = useState(false);
  const [clipsModalOpen, setClipsModalOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (sharedPrompt) {
      setTopicPrompt(sharedPrompt);
    }
  }, [sharedPrompt]);

  useEffect(() => {
    if (sharedFormat) {
      setVideoFormat(sharedFormat);
      setRatio(sharedFormat === "reel" ? "9:16" : "16:9");
    }
  }, [sharedFormat, setRatio]);

  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);
  const isListeningRef = useRef(false);
  const baseTextRef = useRef("");
  const promptRef = useRef("");
  const [voiceDropdownOpen, setVoiceDropdownOpen] = useState(false);
  const voiceDropdownRef = useRef<HTMLDivElement>(null);

  // Mantener promptRef sincronizado con topicPrompt
  useEffect(() => {
    promptRef.current = topicPrompt;
  }, [topicPrompt]);

  // Cerrar dropdown de voces al hacer clic fuera
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (voiceDropdownRef.current && !voiceDropdownRef.current.contains(e.target as Node)) {
        setVoiceDropdownOpen(false);
      }
    }
    if (voiceDropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [voiceDropdownOpen]);

  // Limpieza de reconocimiento de voz al desmontar
  useEffect(() => {
    return () => {
      isListeningRef.current = false;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (_) {}
      }
    };
  }, []);

  const toggleVoiceInput = () => {
    if (isListeningRef.current) {
      isListeningRef.current = false;
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (_) {}
      }
      setIsListening(false);
      flash("Dictado por voz finalizado");
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (!SpeechRecognition) {
      flash("Tu navegador no soporta dictado directo (usa Google Chrome o Microsoft Edge)");
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.lang = "es-ES";
      recognition.continuous = true;
      recognition.interimResults = true;

      isListeningRef.current = true;
      baseTextRef.current = promptRef.current.trim();

      recognition.onstart = () => {
        setIsListening(true);
        flash("Micrófono activo · Puedes hablar de forma continua todo lo que desees...");
      };

      recognition.onresult = (event: any) => {
        let sessionFinal = "";
        let sessionInterim = "";

        // Iterar SIEMPRE todos los resultados acumulados de la sesión para no perder oraciones previas
        for (let i = 0; i < event.results.length; ++i) {
          const item = event.results[i];
          if (item.isFinal) {
            sessionFinal += item[0].transcript + " ";
          } else {
            sessionInterim += item[0].transcript;
          }
        }

        const dictation = (sessionFinal + sessionInterim).trim();
        if (dictation) {
          const prefix = baseTextRef.current ? `${baseTextRef.current} ` : "";
          const fullText = prefix + dictation;
          setTopicPrompt(fullText);
          promptRef.current = fullText;
        }
      };

      recognition.onerror = (event: any) => {
        console.warn("[Voice Dictation]", event.error);
        if (event.error === "not-allowed" || event.error === "service-not-allowed") {
          isListeningRef.current = false;
          setIsListening(false);
          flash("Permiso de micrófono denegado en el navegador");
        } else if (event.error === "no-speech") {
          // Pausa natural en el habla, no detener
        } else {
          console.log("[Voice Dictation] Transient event:", event.error);
        }
      };

      recognition.onend = () => {
        // Si el navegador finalizó por timeout o pausa prolongada, pero el usuario no ha cancelado:
        if (isListeningRef.current) {
          // El texto acumulado pasa a ser el nuevo baseText
          baseTextRef.current = promptRef.current.trim();
          try {
            recognition.start();
          } catch (_) {
            isListeningRef.current = false;
            setIsListening(false);
          }
        } else {
          setIsListening(false);
        }
      };

      recognition.start();
    } catch (err: any) {
      console.error("[Voice Dictation] Error starting:", err);
      isListeningRef.current = false;
      setIsListening(false);
      flash("No se pudo iniciar el dictado por voz");
    }
  };

  const handleAuditAndEnrich = (topicOverride?: string) => {
    const rawTopic = (topicOverride || topicPrompt).trim();
    if (!rawTopic) {
      flash("Escribe primero un tema o idea para auditar y fundamentar con datos");
      if (textareaRef.current) textareaRef.current.focus();
      return;
    }
    const targetDur = videoFormat === "reel" ? targetReelSec : targetDurationMin * 60;
    auditAndEnrichTopic(rawTopic, videoFormat, targetDur);
  };

  const handlePromptSubmit = () => {
    if (!topicPrompt.trim() || isCreating) return;
    const text = topicPrompt.trim();
    if (isListening && recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch (_) {}
      setIsListening(false);
    }
    setTopicPrompt("");
    if (videoFormat === "reel") {
      createVideo(text, {
        duration: targetReelSec,
        style: "shorts",
        aspect_ratio: "9:16",
      });
      flash(`Generando Reel 9:16 (${targetReelSec}s)...`);
    } else {
      createVideo(text, {
        duration: targetDurationMin * 60,
        style: "divulgacion",
        aspect_ratio: "16:9",
      });
      flash(`Generando video documental 16:9 (${targetDurationMin}m)...`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handlePromptSubmit();
    }
  };

  const handleExtractMasterClips = async () => {
    if (!activeProjectId || isExtractingClips) return;
    try {
      setIsExtractingClips(true);
      flash("Analizando la estructura del video y extrayendo momentos virales con subtítulos...");
      const res = await fetch(`/api/projects/${activeProjectId}/extract-clips`, {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Error al extraer clips");
      flash(data.message || "¡Clips y Reels 9:16 con subtítulos listos!");
      setClipsModalOpen(true);
    } catch (err: any) {
      flash(`Aviso: ${err.message || "No se pudieron extraer clips"}`);
    } finally {
      setIsExtractingClips(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* 1. SECCIÓN PRINCIPAL: Card de Prompt, Formato, Voz y Pipeline */}
      <div className="shrink-0 rounded-2xl border border-white/[0.08] bg-black/60 p-3 mb-2.5 shadow-[0_4px_24px_-4px_rgba(0,0,0,0.6)] flex flex-col gap-2.5">
        {/* Cabecera: Switcher de formato (Largo 16:9 vs Reel 9:16) y Stepper de Duración */}
        <div className="flex items-center justify-between gap-1.5">
          <div className="flex items-center p-0.5 rounded-xl border border-white/[0.08] bg-white/[0.03] shrink-0">
            <button
              type="button"
              onClick={() => {
                setVideoFormat("long");
                setRatio("16:9");
              }}
              className={cn(
                "px-2.5 py-1 rounded-lg text-[9.5px] font-medium transition-all select-none whitespace-nowrap",
                videoFormat === "long"
                  ? "bg-white/[0.12] text-white shadow-sm font-semibold"
                  : "text-white/40 hover:text-white/80",
              )}
              title="Modo Largo / Documental: 10 a 40 minutos en formato panorámico 16:9"
            >
              Largo 16:9
            </button>
            <button
              type="button"
              onClick={() => {
                setVideoFormat("reel");
                setRatio("9:16");
              }}
              className={cn(
                "px-2.5 py-1 rounded-lg text-[9.5px] font-medium transition-all select-none whitespace-nowrap",
                videoFormat === "reel"
                  ? "bg-white/[0.12] text-white shadow-sm font-semibold"
                  : "text-white/40 hover:text-white/80",
              )}
              title="Modo Reel / Short: 30 a 90 segundos en formato vertical 9:16 con gancho viral"
            >
              Reel 9:16
            </button>
          </div>

          {/* Stepper de Duración */}
          <div className="flex items-center rounded-xl border border-white/[0.08] bg-white/[0.03] px-1 py-0.5 shrink-0">
            <button
              type="button"
              onClick={() => {
                if (videoFormat === "long") {
                  setTargetDurationMin((prev) => Math.max(1, prev - 1));
                } else {
                  setTargetReelSec((prev) => Math.max(10, prev - 5));
                }
              }}
              className="h-5 w-5 grid place-items-center rounded-md text-[12px] font-bold text-white/50 hover:text-white hover:bg-white/[0.08] active:scale-90 transition-all select-none"
              title={videoFormat === "long" ? "Restar 1 minuto" : "Restar 5 segundos"}
            >
              −
            </button>

            <div className="flex items-center gap-0.5 px-1">
              {videoFormat === "long" ? (
                <>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={targetDurationMin || ""}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      if (!isNaN(val)) {
                        setTargetDurationMin(Math.max(1, Math.min(60, val)));
                      } else if (e.target.value === "") {
                        setTargetDurationMin(1);
                      }
                    }}
                    className="w-6 text-center bg-transparent border-0 p-0 text-[11px] font-bold text-white focus:outline-none focus:ring-0 tnum [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    title="Minutos del video (ej: 1-2 pruebas rápidas, o 10-40 documental)"
                  />
                  <span className="text-[9px] font-medium text-white/40 select-none">m</span>
                </>
              ) : (
                <>
                  <input
                    type="number"
                    min={10}
                    max={300}
                    value={targetReelSec || ""}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      if (!isNaN(val)) {
                        setTargetReelSec(Math.max(5, Math.min(300, val)));
                      } else if (e.target.value === "") {
                        setTargetReelSec(15);
                      }
                    }}
                    className="w-7 text-center bg-transparent border-0 p-0 text-[11px] font-bold text-white focus:outline-none focus:ring-0 tnum [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                    title="Segundos del Reel (ej: 15, 30, 60, 90)"
                  />
                  <span className="text-[9px] font-medium text-white/40 select-none">s</span>
                </>
              )}
            </div>

            <button
              type="button"
              onClick={() => {
                if (videoFormat === "long") {
                  setTargetDurationMin((prev) => Math.min(60, prev + 1));
                } else {
                  setTargetReelSec((prev) => Math.min(300, prev + 5));
                }
              }}
              className="h-5 w-5 grid place-items-center rounded-md text-[12px] font-bold text-white/50 hover:text-white hover:bg-white/[0.08] active:scale-90 transition-all select-none"
              title={videoFormat === "long" ? "Sumar 1 minuto" : "Sumar 5 segundos"}
            >
              +
            </button>
          </div>
        </div>

        {/* Selector y muestra de voz neuronal (Custom Dark Dropdown) */}
        <div className="relative" ref={voiceDropdownRef}>
          <div className="flex items-center justify-between h-7 rounded-lg border border-white/[0.07] bg-white/[0.02] px-2 transition-colors hover:border-white/15">
            <button
              type="button"
              onClick={() => setVoiceDropdownOpen((o) => !o)}
              className="flex items-center gap-1.5 min-w-0 flex-1 text-left cursor-pointer mr-1"
              title="Seleccionar voz neuronal para el video"
            >
              <IconMic className="h-3 w-3 text-white/40 shrink-0" />
              {(() => {
                const cur = NEURAL_VOICES.find((v) => v.id === selectedVoice) || NEURAL_VOICES[0];
                return (
                  <div className="flex items-center gap-1 truncate">
                    <span className="truncate text-[10px] font-medium text-white/85">
                      {cur.n}
                    </span>
                    <span className="text-[8.5px] text-white/30 shrink-0">
                      ({cur.d})
                    </span>
                  </div>
                );
              })()}
              <IconChevron
                className={cn(
                  "h-2.5 w-2.5 text-white/30 shrink-0 transition-transform duration-200 ml-auto",
                  voiceDropdownOpen && "rotate-180 text-white/70",
                )}
              />
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                previewVoice(selectedVoice);
              }}
              className={cn(
                "shrink-0 h-5 px-1.5 rounded-md text-[9px] font-medium flex items-center gap-1 transition-all select-none",
                playingVoiceId === selectedVoice
                  ? "bg-beam-500/20 text-beam-300 border border-beam-400/30"
                  : "text-white/45 hover:text-white hover:bg-white/[0.06]",
              )}
              title="Escuchar muestra de esta voz"
            >
              <span className="text-[8px] leading-none">{playingVoiceId === selectedVoice ? "⏹" : "▶"}</span>
              <span>{playingVoiceId === selectedVoice ? "Probando..." : "Muestra"}</span>
            </button>
          </div>

          {/* Menú desplegable elegante, redondeado y oscuro (sin el popover blanco nativo del sistema) */}
          {voiceDropdownOpen && (
            <div className="absolute left-0 right-0 top-full z-50 mt-1.5 max-h-56 overflow-y-auto rounded-xl border border-white/10 bg-black/95 p-1 shadow-[0_16px_40px_rgba(0,0,0,0.9)] backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150">
              {NEURAL_VOICES.map((v) => {
                const isSelected = v.id === selectedVoice;
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={() => {
                      setSelectedVoice(v.id);
                      setVoiceDropdownOpen(false);
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-[10px] transition-colors",
                      isSelected
                        ? "bg-white/[0.12] text-white font-medium"
                        : "text-white/70 hover:bg-white/[0.05] hover:text-white",
                    )}
                  >
                    <div className="flex items-center gap-2 truncate">
                      <span className={cn("truncate", isSelected ? "text-white font-semibold" : "text-white/85")}>
                        {v.n}
                      </span>
                      <span className="text-[9px] text-white/35">· {v.d}</span>
                    </div>
                    {isSelected && (
                      <span className="text-white text-[11px] font-bold shrink-0 ml-1">✓</span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Barra de progreso de generación (únicamente visible durante la creación activa) */}
        {isCreating && (
          <div className="flex flex-col gap-1.5 py-1 animate-in fade-in duration-200">
            <Meter value={createProgress} height={3} />
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-beam-200 truncate" title={createStatusMessage}>
                {createStatusMessage || "Procesando video con IA..."}
              </span>
              <button
                type="button"
                onClick={cancelCreation}
                className="text-[9px] font-medium text-red-300 hover:text-red-100 bg-red-500/15 hover:bg-red-500/30 border border-red-500/30 px-2 py-0.5 rounded-lg transition-all"
                title="Cancelar creación activa"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}

        {/* Caja de Prompt interactiva con Micrófono de dictado por voz */}
        {!isCreating && (
          <div
            className={cn(
              "rounded-xl border transition-all duration-200 p-2.5 flex flex-col gap-2",
              isListening
                ? "border-red-500/40 bg-red-500/[0.03] shadow-[0_0_15px_-3px_rgba(239,68,68,0.2)]"
                : "border-white/[0.08] bg-white/[0.02] hover:border-white/15 focus-within:border-white/20 focus-within:bg-white/[0.03]",
            )}
          >
            <textarea
              ref={textareaRef}
              value={topicPrompt}
              onChange={(e) => setTopicPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={isListening || topicPrompt.length > 55 ? 3 : 2}
              placeholder={
                isListening
                  ? "Escuchando... habla sobre el tema o detalles de tu video..."
                  : videoFormat === "reel"
                    ? "Escribe o habla sobre el tema para tu Reel vertical 9:16 (30-90s)..."
                    : "Escribe o habla sobre el tema para tu video documental de 10 a 40 min..."
              }
              className="w-full resize-none border-0 bg-transparent p-0 text-[10.5px] leading-relaxed text-white/90 placeholder:text-white/30 focus:outline-none focus:ring-0"
            />

            {/* Barra de herramientas inferior del prompt */}
            <div className="flex items-center justify-between gap-1 pt-1.5 border-t border-white/[0.04] min-w-0">
              {/* Botón de Micrófono (Dictado por Voz) y Botón Pulir con Datos */}
              <div className="flex items-center gap-1 min-w-0">
                <button
                  type="button"
                  onClick={toggleVoiceInput}
                  title={isListening ? "Detener dictado por voz" : "Hablar con micrófono (dictado por voz para prompts largos)"}
                  className={cn(
                    "flex items-center gap-1 h-6 px-1.5 rounded-md text-[9.5px] font-medium transition-all select-none whitespace-nowrap shrink-0",
                    isListening
                      ? "border border-red-500/50 bg-red-500/20 text-red-200 shadow-[0_0_10px_rgba(239,68,68,0.35)] animate-pulse"
                      : "border border-white/[0.06] bg-white/[0.02] text-white/55 hover:text-white hover:border-white/15 hover:bg-white/[0.06]",
                  )}
                >
                  <IconMic className={cn("h-3 w-3", isListening ? "text-red-300" : "text-white/50")} />
                  <span>{isListening ? "Escuchando..." : "Hablar"}</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleAuditAndEnrich()}
                  disabled={isAuditingTopic || isCreating}
                  title="Auditar tema con datos duros reales de la web en el panel de Escenario Viral"
                  className={cn(
                    "flex items-center gap-1 h-6 px-1.5 rounded-md text-[9.5px] font-medium transition-all select-none whitespace-nowrap shrink-0",
                    isAuditingTopic
                      ? "border border-amber-500/50 bg-amber-500/20 text-amber-200 animate-pulse"
                      : producerPlan
                        ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                        : "border border-white/[0.08] bg-white/[0.03] text-white/60 hover:text-white hover:border-white/18 hover:bg-white/[0.06]",
                  )}
                >
                  <IconSparkle className="h-3 w-3 text-amber-400 shrink-0" />
                  <span>{isAuditingTopic ? "Auditando..." : "Pulir"}</span>
                </button>

                {topicPrompt.trim().length > 0 && (
                  <button
                    type="button"
                    onClick={() => setTopicPrompt("")}
                    className="h-6 w-5 grid place-items-center rounded-md text-white/30 hover:text-white/70 hover:bg-white/[0.06] text-[10px] transition-colors shrink-0"
                    title="Borrar texto del prompt"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* Botón de crear o formato */}
              {topicPrompt.trim().length > 0 ? (
                <button
                  type="button"
                  onClick={handlePromptSubmit}
                  className="flex items-center gap-1 h-6 px-2 rounded-md bg-beam-500 hover:bg-beam-400 text-white text-[9.5px] font-semibold border border-beam-400/40 shadow-sm transition-all active:scale-95 whitespace-nowrap shrink-0"
                  title="Crear video con IA ahora"
                >
                  <span>Crear</span>
                  <span className="text-white/60 text-[9px] font-mono">↵</span>
                </button>
              ) : (
                <span className="text-[9px] text-white/25 select-none pr-1 whitespace-nowrap shrink-0 font-mono">
                  {videoFormat === "reel" ? "9:16" : `${targetDurationMin}m`}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Acceso a proyectos y extracción de clips en timeline */}
        {activeProjectId && (
          <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between gap-1.5">
            <div className="flex items-center gap-1.5 min-w-0 flex-1">
              <span className="h-1.5 w-1.5 rounded-full bg-signal-400 shrink-0" />
              <span className="text-[9.5px] text-white/40 truncate" title={activeProjectTitle}>
                {activeProjectTitle || "Video activo"}
              </span>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              {(() => {
                const activeProj = projects?.find((p) => p.id === activeProjectId);
                const isInterrupted =
                  Boolean(activeProjectId) &&
                  !isCreating &&
                  Boolean(
                    activeProj &&
                      !activeProj.has_result &&
                      (activeProj.status === "render" ||
                        activeProj.status === "running" ||
                        activeProj.status === "script" ||
                        activeProj.status === "error"),
                  );
                return (
                  isInterrupted && (
                    <button
                      type="button"
                      onClick={() => resumeProject(activeProjectId)}
                      className="text-[9px] font-medium px-2 py-0.5 rounded-md border border-amber-400/40 bg-amber-500/15 text-amber-200 hover:bg-amber-500/30 transition-all flex items-center gap-1"
                      title="Reanudar generación de este video"
                    >
                      <span>Reanudar</span>
                    </button>
                  )
                );
              })()}
              <div className="inline-flex items-center rounded-md border border-white/[0.08] bg-white/[0.02] divide-x divide-white/[0.08] overflow-hidden">
                <button
                  type="button"
                  onClick={() => setClipsModalOpen(true)}
                  className="px-2 py-0.5 text-[9px] font-medium text-white/60 hover:text-white hover:bg-white/[0.06] transition-colors whitespace-nowrap"
                  title="Ver, reproducir y descargar los Reels verticales 9:16 generados para este video"
                >
                  Ver Reels
                </button>
                <button
                  type="button"
                  onClick={handleExtractMasterClips}
                  disabled={isExtractingClips}
                  className={cn(
                    "px-2 py-0.5 text-[9px] font-medium transition-colors whitespace-nowrap",
                    isExtractingClips
                      ? "text-white/25 cursor-not-allowed"
                      : "text-white/60 hover:text-white hover:bg-white/[0.06]",
                  )}
                  title="Extraer 3 Reels verticales 9:16 con subtítulos de este video largo"
                >
                  {isExtractingClips ? "Extrayendo..." : "Extraer Clips"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 2. AUTOMATIZACIONES NEURONALES RÁPIDAS 1-CLIC */}
      <div className="space-y-2 pt-2 border-t border-white/[0.06]">
        <div className="flex items-center justify-between px-0.5">
          <SectionLabel>Automatización Neuronal 1-Clic</SectionLabel>
        </div>
        <div className="grid grid-cols-1 gap-1.5">
          {AUTOMATIONS.slice(0, 5).map((a) => {
            const p = progress[a.id];
            const done = applied.includes(a.id);
            return (
              <button
                key={a.id}
                onClick={() => run(a.id)}
                disabled={done || p !== undefined}
                className={cn(
                  "flex items-center justify-between rounded-xl border p-2 text-left transition-all",
                  done
                    ? "border-signal-400/30 bg-signal-400/[0.06] text-signal-400/90"
                    : p !== undefined
                    ? "border-beam-400/40 bg-beam-500/15 text-beam-100"
                    : "border-white/[0.06] bg-white/[0.015] hover:border-white/[0.14] text-white/70 hover:text-white cursor-pointer",
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="text-[12px]">{a.glyph}</span>
                  <div>
                    <span className="text-[10.5px] font-medium block">{a.name}</span>
                    <span className="micro-sm text-white/30 block">{a.detail}</span>
                  </div>
                </div>
                <span className="text-[9px] font-mono text-beam-300">
                  {done ? "Listo" : p !== undefined ? `${Math.round(p)}%` : `+${Math.round(a.score)} pts`}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Modal de visualización y descarga de Reels 9:16 */}
      <ClipsModal
        isOpen={clipsModalOpen}
        onClose={() => setClipsModalOpen(false)}
        projectId={activeProjectId}
        projectTitle={activeProjectTitle}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ESPACIO DE TRABAJO: INVESTIGACIÓN (Catálogo de Nichos Virales)     */
/* ------------------------------------------------------------------ */

function ResearchTab({ onUseTopic }: { onUseTopic: (topicText: string, fmt?: "reel" | "long") => void }) {
  const { createVideo, flash } = useEditor();
  const [selectedCategory, setSelectedCategory] = useState<ViralCategory | "all">("all");
  const [pinnedIds, setPinnedIds] = useState<string[]>(() => getStoredPinnedIds());
  const [topics, setTopics] = useState<ViralTopic[]>(() =>
    generateDailyTopics(getStoredPinnedIds()),
  );
  const [expandedTopicId, setExpandedTopicId] = useState<string | null>(null);
  const [isCrawlerActive, setIsCrawlerActive] = useState<boolean>(false);
  const [isCrawlerPaused, setIsCrawlerPaused] = useState<boolean>(false);
  const [isTogglingCrawler, setIsTogglingCrawler] = useState<boolean>(false);
  const [isRefreshingTopics, setIsRefreshingTopics] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    const fetchSnapshot = async () => {
      try {
        const res = await fetch("/api/viral-niches");
        if (res.ok && isMounted) {
          const data = await res.json();
          if (data && Array.isArray(data.topics)) {
            const synced = syncLiveTopics(data.topics, pinnedIds);
            setTopics(synced);
            setIsCrawlerActive(Boolean(data.is_crawling));
            setIsCrawlerPaused(Boolean(data.is_paused));
          }
        }
      } catch (err) {}
    };

    fetchSnapshot();

    const pollLoop = async () => {
      await fetchSnapshot();
      if (isMounted) {
        pollTimer = setTimeout(pollLoop, 2500);
      }
    };
    pollTimer = setTimeout(pollLoop, 2500);

    return () => {
      isMounted = false;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [pinnedIds]);

  const handleToggleCrawler = async () => {
    if (isTogglingCrawler) return;
    setIsTogglingCrawler(true);
    try {
      const shouldStop = isCrawlerActive || !isCrawlerPaused;
      const endpoint = shouldStop ? "/api/viral-niches/stop" : "/api/viral-niches/resume";
      const res = await fetch(endpoint, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setIsCrawlerActive(Boolean(data.is_crawling));
        setIsCrawlerPaused(Boolean(data.is_paused));
        flash(
          shouldStop
            ? "⏹ Rastreo pausado: se conservan todos los temas descubiertos."
            : "▶ Rastreo reanudado: buscando nuevos temas en la web..."
        );
      }
    } catch (err) {
      console.error("Error al pausar/reanudar rastreador:", err);
    } finally {
      setIsTogglingCrawler(false);
    }
  };

  const handleRefresh = async () => {
    if (isRefreshingTopics) return;
    setIsRefreshingTopics(true);
    const catParam = selectedCategory && selectedCategory !== "all" ? `?category=${encodeURIComponent(selectedCategory)}` : "";
    flash(`Buscando tendencias ${selectedCategory !== "all" ? `de ${selectedCategory}` : "en Internet"} con IA...`);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 20000);
    try {
      const res = await fetch(`/api/viral-niches/refresh${catParam}`, {
        method: "POST",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data.topics)) {
          const synced = syncLiveTopics(data.topics, pinnedIds);
          setTopics(synced);
          setIsCrawlerActive(Boolean(data.is_crawling));
          flash("✓ ¡Nuevas tendencias de Internet descubiertas e incorporadas!");
          return;
        }
      }
    } catch (e) {
      console.warn("Fallo en búsqueda en vivo de temas:", e);
    } finally {
      clearTimeout(timeoutId);
      setIsRefreshingTopics(false);
    }

    const fresh = generateDailyTopics(pinnedIds, true);
    setTopics(fresh);
    flash("Temas sincronizados · Favoritos intactos");
  };

  const togglePin = (topic: ViralTopic) => {
    const isPinned = pinnedIds.includes(topic.id);
    const nextPinned = isPinned
      ? pinnedIds.filter((id) => id !== topic.id)
      : [topic.id, ...pinnedIds];

    setPinnedIds(nextPinned);
    savePinnedIds(nextPinned, topic, !isPinned);
    flash(
      isPinned
        ? `«${topic.title.slice(0, 24)}...» desanclado`
        : `«${topic.title.slice(0, 24)}...» anclado de primero`,
    );
  };

  const activeCategories: ViralCategory[] =
    selectedCategory === "all" ? ALL_CATEGORIES : [selectedCategory];

  const displayedTopics =
    selectedCategory === "all"
      ? topics
      : topics.filter((t) => t.category === selectedCategory);

  return (
    <div className="flex flex-col h-full min-h-0 space-y-2">
      {/* Controles del Rastreador y Cabecera */}
      <div className="shrink-0 flex items-center justify-between px-1">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="micro-sm text-white/35 font-medium tracking-wider">
            NICHOS VIRALES
          </span>
          <span className="rounded-full bg-beam-500/10 border border-beam-400/20 px-1.5 py-0.2 text-[9px] font-semibold text-beam-300">
            {displayedTopics.length} disponibles
          </span>
          {isCrawlerActive && (
            <span className="inline-flex items-center gap-1 text-[8px] text-beam-300/80 font-medium px-1.5 py-0.2 rounded-full bg-beam-400/10 border border-beam-400/20" title="Rastreador continuo buscando temas en Internet">
              <span className="h-1.5 w-1.5 rounded-full bg-beam-400 animate-ping" />
              <span>Rastreando web...</span>
            </span>
          )}
          {isCrawlerPaused && (
            <span className="inline-flex items-center gap-1 text-[8px] text-amber-300/80 font-medium px-1.5 py-0.2 rounded-full bg-amber-400/10 border border-amber-400/20" title="Rastreador en pausa">
              <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              <span>Pausado</span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={handleToggleCrawler}
            disabled={isTogglingCrawler}
            title={isCrawlerPaused ? "Reanudar rastreo de temas en Internet" : "Parar búsqueda continua (ya hay suficientes temas)"}
            className={cn(
              "flex items-center gap-1 text-[9px] font-semibold px-2 py-0.5 rounded border transition-all duration-200 cursor-pointer",
              isCrawlerPaused
                ? "bg-emerald-500/15 border-emerald-500/35 text-emerald-300 hover:bg-emerald-500/25"
                : "bg-red-500/15 border-red-500/35 text-red-300 hover:bg-red-500/25",
              isTogglingCrawler && "opacity-50"
            )}
          >
            {isCrawlerPaused ? (
              <>
                <span className="text-[9px]">▶</span>
                <span>Reanudar</span>
              </>
            ) : (
              <>
                <span className="text-[8px]">⏹</span>
                <span>Parar</span>
              </>
            )}
          </button>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={isRefreshingTopics}
            title="Buscar tendencias reales en Internet con IA y recalcular puntuaciones virales"
            className="flex items-center gap-1 text-[9.5px] text-white/40 hover:text-beam-300 transition-colors px-1.5 py-0.5 rounded hover:bg-white/[0.04] disabled:opacity-50 cursor-pointer"
          >
            <IconRefresh className={cn("h-3 w-3", (isRefreshingTopics || isCrawlerActive) && "animate-spin text-beam-300")} />
            <span>{isRefreshingTopics ? "Buscando..." : "Actualizar"}</span>
          </button>
        </div>
      </div>

      {/* Selector Horizontal de Categorías */}
      <div
        onWheel={(e) => {
          if (e.deltaY !== 0) {
            e.currentTarget.scrollLeft += e.deltaY;
          }
        }}
        className="shrink-0 flex items-center gap-1 overflow-x-auto no-scrollbar py-1 px-0.5 scroll-smooth"
      >
        <button
          type="button"
          onClick={() => setSelectedCategory("all")}
          className={cn(
            "rounded-full px-2.5 py-0.8 text-[9px] font-medium transition-all duration-200 shrink-0 whitespace-nowrap cursor-pointer",
            selectedCategory === "all"
              ? "bg-beam-500/20 text-beam-200 border border-beam-400/40 shadow-sm"
              : "border border-white/[0.08] bg-white/[0.02] text-white/45 hover:text-white/80 hover:border-white/15",
          )}
        >
          <span>Todos ({topics.length})</span>
        </button>
        {ALL_CATEGORIES.map((catKey) => {
          const catInfo = CATEGORY_LABELS[catKey];
          const count = topics.filter((t) => t.category === catKey).length;
          const isSelected = selectedCategory === catKey;
          return (
            <button
              key={catKey}
              type="button"
              onClick={() => setSelectedCategory(catKey)}
              title={catInfo.desc}
              className={cn(
                "rounded-full px-2.5 py-0.8 text-[9px] font-medium transition-all duration-200 shrink-0 whitespace-nowrap flex items-center gap-1 cursor-pointer",
                isSelected
                  ? "bg-beam-500/20 text-beam-200 border border-beam-400/40 shadow-sm"
                  : "border border-white/[0.08] bg-white/[0.02] text-white/45 hover:text-white/80 hover:border-white/15",
              )}
            >
              <IconFlame className="h-2.5 w-2.5 text-beam-400" />
              <span>{catInfo.label}</span>
              <span className="text-[8px] opacity-60 font-mono">({count})</span>
            </button>
          );
        })}
      </div>

      {/* Lista Desplazable de Temas */}
      <div className="min-h-0 flex-1 overflow-y-auto space-y-2.5 pr-1 pb-4 pt-1">
        {activeCategories.map((g) => {
          const items = topics.filter((a) => a.category === g);
          const catInfo = CATEGORY_LABELS[g];
          if (!items.length) return null;

          const sortedItems = [...items].sort((a, b) => {
            const aPinned = pinnedIds.includes(a.id);
            const bPinned = pinnedIds.includes(b.id);
            if (aPinned && !bPinned) return -1;
            if (!aPinned && bPinned) return 1;
            if (a.isLive && !b.isLive) return -1;
            if (!a.isLive && b.isLive) return 1;
            return b.score - a.score;
          });

          return (
            <div key={g} className="space-y-2">
              <div className="flex items-center justify-between">
                <SectionLabel>
                  <span className="flex items-center gap-1.5">
                    <span>{catInfo.icon}</span>
                    <span>{catInfo.label}</span>
                  </span>
                </SectionLabel>
                <span className="text-[9px] text-white/30 font-mono">
                  {sortedItems.length} temas
                </span>
              </div>
              {sortedItems.map((topic) => {
                const isPinned = pinnedIds.includes(topic.id);
                const isExpanded = expandedTopicId === topic.id;
                const isShortTopic =
                  topic.durationMin <= 2 ||
                  topic.category === "motivacion" ||
                  topic.category === "cristiano_cine" ||
                  topic.category === "versiculos";

                return (
                  <div
                    key={topic.id}
                    className={cn(
                      "group relative overflow-hidden rounded-xl border transition-all duration-300 p-2.5 flex flex-col gap-2",
                      isPinned
                        ? "border-amber-400/30 bg-amber-400/[0.035] shadow-[0_0_12px_rgba(251,191,36,0.06)]"
                        : "border-white/[0.07] bg-white/[0.018] hover:border-white/18 hover:bg-white/[0.035]",
                    )}
                  >
                    {isPinned && (
                      <span className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-amber-400/40 via-amber-300/80 to-amber-400/40" />
                    )}

                    <div className="flex items-center justify-between gap-1.5 text-[9px]">
                      <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
                        <span className="text-[8.5px] font-medium text-white/50 bg-white/[0.04] px-1.5 py-0.5 rounded border border-white/[0.06]">
                          {isShortTopic ? "Reel 9:16" : `${topic.durationMin}m`}
                        </span>
                        {topic.isLive && (
                          <span className="text-[8px] font-semibold text-emerald-300 bg-emerald-500/15 px-1.5 py-0.5 rounded border border-emerald-400/30">
                            En Vivo IA
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-1 shrink-0">
                        <span className="tnum text-[9.5px] font-semibold text-beam-200 bg-beam-500/15 px-1.5 py-0.5 rounded border border-beam-400/25">
                          +{topic.score}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            togglePin(topic);
                          }}
                          className={cn(
                            "p-1 rounded-md transition-all cursor-pointer",
                            isPinned
                              ? "text-amber-400 bg-amber-400/15 border border-amber-400/35 shadow-[0_0_8px_rgba(251,191,36,0.25)]"
                              : "text-white/25 hover:text-amber-300/80 hover:bg-white/[0.06]",
                          )}
                          title={isPinned ? "Quitar de favoritos" : "Guardar en favoritos"}
                        >
                          <IconPin className={cn("h-3 w-3", isPinned ? "rotate-[-45deg] scale-110" : "opacity-60")} filled={isPinned} />
                        </button>
                      </div>
                    </div>

                    <h4
                      onClick={() => setExpandedTopicId(isExpanded ? null : topic.id)}
                      className="text-[11.5px] font-semibold leading-snug text-white/95 cursor-pointer hover:text-white transition-colors"
                    >
                      {topic.title}
                    </h4>

                    <div className="relative">
                      <p className={cn("text-[10px] leading-relaxed text-white/50", !isExpanded && "line-clamp-2")}>
                        {topic.nuances}
                      </p>
                      {topic.nuances.length > 75 && (
                        <button
                          type="button"
                          onClick={() => setExpandedTopicId(isExpanded ? null : topic.id)}
                          className="mt-0.5 text-[8.5px] text-beam-300/70 hover:text-beam-200 font-medium"
                        >
                          {isExpanded ? "▲ Menos" : "▼ Más"}
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 pt-1.5 border-t border-white/[0.05]">
                      <button
                        type="button"
                        onClick={() => onUseTopic(`${topic.title}\n\nGancho: ${topic.nuances}`, isShortTopic ? "reel" : "long")}
                        className="rounded-lg border border-beam-400/30 bg-beam-500/15 text-[9.5px] font-semibold text-beam-200 hover:bg-beam-500/25 px-2.5 py-1 transition-all flex items-center gap-1 cursor-pointer"
                        title="Transferir este tema al generador de IA"
                      >
                        <IconSparkle className="h-2.5 w-2.5" />
                        <span>Cargar en IA</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          const promptText = `Crea un Reel vertical 9:16 de alto impacto sobre: ${topic.title}. Hook inicial: ${topic.nuances}`;
                          createVideo(promptText, { duration: 60, aspect_ratio: "9:16", style: "shorts" });
                          flash(`Generando Reel 9:16: «${topic.title.slice(0, 24)}...»`);
                        }}
                        className="flex-1 rounded-lg border border-white/10 bg-white/[0.025] hover:border-white/20 hover:bg-white/[0.06] text-white/70 hover:text-white py-1 px-2 text-[9.5px] font-medium transition-all text-center truncate cursor-pointer"
                      >
                        Reel 9:16
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const durSec = (topic.durationMin || 15) * 60;
                          const promptText = `Crea un video documental 16:9 con investigación profunda sobre: ${topic.title}. Hook inicial: ${topic.nuances}`;
                          createVideo(promptText, { duration: durSec, aspect_ratio: "16:9", style: "divulgacion" });
                          flash(`Generando Documental 16:9 (${Math.round(durSec / 60)}m): «${topic.title.slice(0, 24)}...»`);
                        }}
                        className="rounded-lg border border-white/10 bg-white/[0.025] hover:border-white/20 hover:bg-white/[0.06] text-white/70 hover:text-white py-1 px-2 text-[9.5px] font-medium transition-all text-center truncate cursor-pointer"
                      >
                        Largo 16:9
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ESPACIO DE TRABAJO: PROYECTO (Proyectos y Escenas en Disco)        */
/* ------------------------------------------------------------------ */

function ProjectTab() {
  const { seek, clips, projects, activeProjectId, selectProject, deleteProject, setImportModalOpen } = useEditor();
  const [detailsProject, setDetailsProject] = useState<any | null>(null);
  const [clipsProject, setClipsProject] = useState<any | null>(null);
  const realScenes = clips.filter((c) => c.kind === "scene");
  const recentProjects = (projects || []).slice(0, 20);

  return (
    <div className="space-y-4">
      {/* Botón rápido de importación */}
      <button
        type="button"
        onClick={() => setImportModalOpen(true)}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-white/20 bg-white/[0.02] p-2.5 text-[11px] font-medium text-white/70 hover:border-white/40 hover:bg-white/[0.05] hover:text-white transition-all cursor-pointer"
      >
        <span className="grid h-5 w-5 place-items-center rounded-lg border border-white/10 bg-white/[0.05] text-white font-mono text-[11px]">
          +
        </span>
        <span>Subir archivo o pegar enlace YouTube</span>
      </button>

      {/* 1. PROYECTOS RECIENTES EN DISCO (MÁXIMO 20) */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-0.5">
          <SectionLabel
            right={
              <span className="rounded-full bg-beam-500/10 border border-beam-400/20 px-1.5 py-0.2 text-[9px] font-semibold text-beam-300 font-mono">
                {recentProjects.length}/20 en disco
              </span>
            }
          >
            Proyectos Recientes
          </SectionLabel>
        </div>

        {recentProjects.length === 0 ? (
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-4 text-center">
            <IconFolder className="mx-auto h-6 w-6 text-white/20 mb-1.5" />
            <p className="text-[11px] text-white/50">No hay proyectos recientes</p>
            <p className="text-[9.5px] text-white/25 mt-0.5">Genera uno desde la pestaña IA</p>
          </div>
        ) : (
          <div className="space-y-1.5">
            {recentProjects.map((p) => {
              const isActive = p.id === activeProjectId;
              const title = p.name || p.topic || `Proyecto ${p.id}`;
              const durSec = p.duration ? Math.round(p.duration) : null;
              const durStr = durSec
                ? durSec >= 60
                  ? `${Math.floor(durSec / 60)}m ${durSec % 60}s`
                  : `${durSec}s`
                : null;

              return (
                <div
                  key={p.id}
                  onClick={() => selectProject(p.id)}
                  className={cn(
                    "group relative flex w-full items-center gap-2.5 rounded-xl border p-2 text-left transition-all duration-200 cursor-pointer",
                    isActive
                      ? "border-beam-400/50 bg-beam-500/15 shadow-[0_0_15px_-3px_rgba(79,123,255,0.3)] ring-1 ring-beam-400/30"
                      : "border-white/[0.06] bg-white/[0.015] hover:border-white/[0.15] hover:bg-white/[0.04]",
                  )}
                >
                  {/* Thumbnail / Frame */}
                  <div className="relative h-12 w-[34px] shrink-0 overflow-hidden rounded-md border border-white/10 bg-black/50">
                    {p.thumbnail_url ? (
                      <img
                        src={p.thumbnail_url}
                        alt=""
                        className="no-drag h-full w-full object-cover opacity-85 transition-opacity group-hover:opacity-100"
                      />
                    ) : (
                      <div className="h-full w-full flex items-center justify-center bg-gradient-to-br from-beam-900/40 via-ink-900 to-black text-beam-300/40">
                        <IconPlay className="h-3.5 w-3.5" />
                      </div>
                    )}
                    {isActive && (
                      <div className="absolute inset-x-0 bottom-0 h-1 bg-beam-400" />
                    )}
                  </div>

                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={cn(
                          "truncate text-[11px] font-medium leading-tight",
                          isActive ? "text-white" : "text-white/80 group-hover:text-white",
                        )}
                        title={title}
                      >
                        {title}
                      </span>
                    </div>

                    <div className="mt-1 flex items-center gap-2 text-[9.5px]">
                      {durStr && (
                        <span className="font-mono text-white/50 bg-white/[0.04] px-1 py-0.2 rounded border border-white/[0.04]">
                          ⏱ {durStr}
                        </span>
                      )}
                      <span
                        className={cn(
                          "flex items-center gap-1",
                          p.has_result ? "text-emerald-400/90" : "text-amber-400/90",
                        )}
                      >
                        <span
                          className={cn(
                            "h-1.5 w-1.5 rounded-full",
                            p.has_result ? "bg-emerald-400" : "bg-amber-400",
                          )}
                        />
                        {p.has_result ? "Listo" : p.status || "En proceso"}
                      </span>
                      {isActive && (
                        <span className="text-beam-300 font-semibold text-[8.5px] uppercase tracking-wider ml-auto">
                          Activo
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Acciones: botón reels 9:16, botón info/copiar y botón eliminar */}
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setClipsProject(p);
                      }}
                      className="px-1.5 py-0.5 rounded text-[10px] text-white/50 hover:text-white hover:bg-white/[0.08] border border-transparent hover:border-white/10 transition-all"
                      title="Ver y descargar los Reels y Shorts 9:16 extraídos de este video"
                    >
                      <span>Reels</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDetailsProject(p);
                      }}
                      className="p-1.5 rounded-lg text-white/40 hover:text-beam-300 hover:bg-beam-500/15 transition-all"
                      title="Ver y copiar título, descripción y hashtags para redes"
                    >
                      <IconShare className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`¿Eliminar «${title.slice(0, 30)}...» de disco?`)) {
                          deleteProject(p.id);
                        }
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg text-white/30 hover:text-red-400 hover:bg-red-500/10 transition-all"
                      title="Eliminar proyecto de disco y liberar espacio"
                    >
                      <IconTrash className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modal de detalles de publicación */}
      <ProjectDetailsModal
        isOpen={Boolean(detailsProject)}
        onClose={() => setDetailsProject(null)}
        projectId={detailsProject?.id || null}
        projectTitle={detailsProject?.name || detailsProject?.topic || "Video KAI"}
        thumbnailUrl={detailsProject?.thumbnail_url}
        durationSec={detailsProject?.duration}
      />

      {/* Modal de Reels 9:16 para proyectos de la lista */}
      <ClipsModal
        isOpen={Boolean(clipsProject)}
        onClose={() => setClipsProject(null)}
        projectId={clipsProject?.id || null}
        projectTitle={clipsProject?.name || clipsProject?.topic || "Video KAI"}
      />

      {/* 2. ESCENAS DEL PROYECTO ACTIVO */}
      {realScenes.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-white/[0.06]">
          <SectionLabel
            right={<span className="tnum text-[9px] text-white/25">{realScenes.length}</span>}
          >
            Escenas del Proyecto Activo
          </SectionLabel>
          <div className="space-y-1.5">
            {realScenes.map((sc) => (
              <button
                key={sc.id}
                onClick={() => seek(sc.start)}
                className="group flex w-full items-center gap-2.5 rounded-xl border border-white/[0.05] bg-white/[0.012] p-2 text-left transition-all duration-200 hover:border-beam-300/25 hover:bg-white/[0.04]"
              >
                <div className="relative h-11 w-[30px] shrink-0 overflow-hidden rounded-md border border-white/10 bg-black/40">
                  {sc.frame ? (
                    <img
                      src={sc.frame}
                      alt=""
                      className="no-drag h-full w-full object-cover opacity-80 transition-opacity group-hover:opacity-100"
                    />
                  ) : (
                    <div className="h-full w-full bg-gradient-to-br from-abyss-700 to-ink-900" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[11px] text-white/80 group-hover:text-white">
                    {sc.label}
                  </div>
                  <div className="micro-sm mt-1 text-white/30">
                    {Math.round(sc.start)}s · {Math.round(sc.duration)}s dur
                  </div>
                </div>
                <IconChevron className="h-3 w-3 shrink-0 text-white/15 transition-transform group-hover:translate-x-0.5 group-hover:text-white/40" />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ESPACIO DE TRABAJO: MEDIOS (B-Roll, Tomas Maestras y Biblioteca)   */
/* ------------------------------------------------------------------ */

function MediaTab() {
  const { setImportModalOpen, addClip, select, time, flash } = useEditor();
  const [activeFolder, setActiveFolder] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const allFolders = ASSET_FOLDERS;
  const filteredFolders = allFolders
    .map((f) => ({
      ...f,
      items: f.items.filter(
        (item) =>
          item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.meta.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    }))
    .filter((f) => (activeFolder === "all" || f.name === activeFolder) && f.items.length > 0);

  const handleInsertClip = (item: any, folderName: string) => {
    const isAudio = folderName === "Audio";
    const track = isAudio ? "a1" : folderName === "Generado por IA" ? "v2" : "v1";
    const kind = isAudio ? "voice" : folderName === "Generado por IA" ? "broll" : "scene";
    const newId = `asset-${Date.now().toString(36)}`;
    const newClip: Clip = {
      id: newId,
      track,
      start: Math.round(time * 10) / 10,
      duration: isAudio ? 6 : 4,
      label: item.name,
      kind,
      frame: item.frame,
      ai: folderName === "Generado por IA",
    };
    addClip(newClip);
    select(newId);
    flash(`Insertado «${item.name}» en pista ${track.toUpperCase()} (${time.toFixed(1)}s)`);
  };

  return (
    <div className="space-y-3.5">
      {/* Botón rápido de importación / YouTube */}
      <button
        type="button"
        onClick={() => setImportModalOpen(true)}
        className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-white/20 bg-white/[0.02] p-2.5 text-[11px] font-medium text-white/70 hover:border-white/40 hover:bg-white/[0.05] hover:text-white transition-all cursor-pointer"
      >
        <span className="grid h-5 w-5 place-items-center rounded-lg border border-white/10 bg-white/[0.05] text-white font-mono text-[11px]">
          +
        </span>
        <span>Subir archivo o pegar enlace YouTube</span>
      </button>

      {/* Buscador de medios */}
      <div className="relative">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Buscar tomas, b-roll o audios..."
          className="w-full rounded-lg border border-white/[0.08] bg-white/[0.025] px-2.5 py-1.5 text-[11px] text-white/90 placeholder:text-white/25 focus:border-beam-400/50 focus:outline-none transition-colors"
        />
        {searchQuery && (
          <button
            type="button"
            onClick={() => setSearchQuery("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-white/40 hover:text-white"
          >
            ×
          </button>
        )}
      </div>

      {/* Filtros de carpetas */}
      <div className="flex items-center gap-1 overflow-x-auto pb-1 subtle-scrollbar">
        <button
          type="button"
          onClick={() => setActiveFolder("all")}
          className={cn(
            "rounded-full px-2.5 py-0.5 text-[9.5px] font-medium transition-all shrink-0 cursor-pointer",
            activeFolder === "all"
              ? "bg-beam-500/20 text-beam-200 border border-beam-400/40 shadow-sm"
              : "border border-white/[0.08] bg-white/[0.02] text-white/50 hover:text-white/80",
          )}
        >
          Todos
        </button>
        {allFolders.map((f) => (
          <button
            key={f.name}
            type="button"
            onClick={() => setActiveFolder(f.name)}
            className={cn(
              "rounded-full px-2.5 py-0.5 text-[9.5px] font-medium transition-all shrink-0 cursor-pointer flex items-center gap-1",
              activeFolder === f.name
                ? "bg-beam-500/20 text-beam-200 border border-beam-400/40 shadow-sm"
                : "border border-white/[0.08] bg-white/[0.02] text-white/50 hover:text-white/80",
            )}
          >
            <span>{f.name}</span>
            <span className="text-[8.5px] opacity-50 font-mono">({f.items.length})</span>
          </button>
        ))}
      </div>

      {/* Listado de recursos */}
      <div className="space-y-3">
        {filteredFolders.map((f) => (
          <div key={f.name} className="space-y-1.5">
            <div className="flex items-center justify-between px-0.5">
              <SectionLabel>{f.name}</SectionLabel>
              <span className="text-[9px] text-white/30 font-mono">{f.items.length} clips</span>
            </div>

            <div className="space-y-1.5">
              {f.items.map((item, idx) => (
                <div
                  key={idx}
                  className="group flex items-center gap-2.5 rounded-xl border border-white/[0.06] bg-white/[0.015] p-2 transition-all duration-200 hover:border-beam-400/30 hover:bg-white/[0.035]"
                >
                  <div className="relative h-10 w-12 shrink-0 overflow-hidden rounded-lg border border-white/10 bg-black/50">
                    {item.frame ? (
                      <img src={item.frame} alt="" className="h-full w-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                    ) : (
                      <div className="h-full w-full flex items-center justify-center bg-gradient-to-br from-beam-950/40 to-ink-950">
                        <IconMusic className="h-4 w-4 text-beam-300/60" />
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[11px] font-medium text-white/85 group-hover:text-white">
                      {item.name}
                    </div>
                    <div className="text-[9.5px] text-white/35 truncate mt-0.5">
                      {item.meta}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleInsertClip(item, f.name)}
                    className="shrink-0 rounded-lg border border-beam-400/30 bg-beam-500/10 hover:bg-beam-500/20 text-beam-200 px-2 py-1 text-[9.5px] font-medium transition-all flex items-center gap-1 cursor-pointer"
                    title={`Insertar en el cabezal (${time.toFixed(1)}s)`}
                  >
                    <span>+</span>
                    <span>Insertar</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TextTab() {
  const {
    overlays,
    toggleOverlay,
    subtitleStyle,
    setSubtitleStyle,
    subtitleFont,
    setSubtitleFont,
    captions,
    updateCaption,
    seek,
  } = useEditor();

  const styles = [
    { id: "kinetic", name: "Kinetic Bold", detail: "Palabra activa resaltada" },
    { id: "karaoke", name: "Karaoke Flow", detail: "Relleno progresivo" },
    { id: "minimal", name: "Minimal Line", detail: "Banda inferior fina" },
    { id: "outline", name: "Outline Pop", detail: "Contorno + sombra" },
  ];

  const fonts = ["Inter Tight", "Instrument", "Neue Haas", "Söhne Mono"];

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <SectionLabel>Estilo de subtítulo</SectionLabel>
        {styles.map((s) => {
          const isActive = subtitleStyle === s.id;
          return (
            <button
              key={s.id}
              onClick={() => setSubtitleStyle(s.id)}
              className={cn(
                "flex w-full items-center justify-between rounded-xl border p-2.5 text-left transition-all duration-300",
                isActive
                  ? "border-beam-400/40 bg-beam-500/[0.12] shadow-[0_0_15px_-3px_rgba(79,123,255,0.3)]"
                  : "border-white/[0.06] bg-white/[0.015] hover:border-white/[0.14]",
              )}
            >
              <span>
                <span className="block text-[11.5px] font-medium text-white/90">{s.name}</span>
                <span className="micro-sm mt-0.5 block text-white/35">{s.detail}</span>
              </span>
              <span
                className={cn(
                  "h-2 w-2 rounded-full transition-all duration-300",
                  isActive ? "bg-beam-300 shadow-[0_0_10px_2px_rgba(126,163,255,0.8)] scale-110" : "bg-white/15",
                )}
              />
            </button>
          );
        })}
      </div>

      <Hairline />

      <div className="space-y-1.5">
        <SectionLabel>Superposición</SectionLabel>
        <Toggle
          on={overlays.captions}
          onChange={() => toggleOverlay("captions")}
          label="Subtítulos"
          hint={`${captions.length} frases sincronizadas`}
        />
        <Toggle
          on={overlays.tracking}
          onChange={() => toggleOverlay("tracking")}
          label="Caja de seguimiento"
          hint="Rostro principal"
        />
        <Toggle
          on={overlays.safe}
          onChange={() => toggleOverlay("safe")}
          label="Zonas seguras"
          hint="UI de plataforma"
        />
      </div>

      <Hairline />

      <div className="space-y-2">
        <SectionLabel>Tipografía</SectionLabel>
        <div className="grid grid-cols-2 gap-2">
          {fonts.map((f) => {
            const isActive = subtitleFont === f;
            return (
              <button
                key={f}
                onClick={() => setSubtitleFont(f)}
                className={cn(
                  "rounded-lg border px-2.5 py-2 text-left text-[10.5px] font-medium transition-all duration-200",
                  isActive
                    ? "border-beam-400/40 bg-beam-500/[0.12] text-white shadow-[0_0_12px_-2px_rgba(79,123,255,0.4)]"
                    : "border-white/[0.06] text-white/50 hover:border-white/15 hover:text-white/80",
                )}
              >
                {f}
              </button>
            );
          })}
        </div>
      </div>

      {captions.length > 0 && (
        <>
          <Hairline />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <SectionLabel>Líneas de subtítulo ({captions.length})</SectionLabel>
              <span className="text-[9px] text-white/30">Clic para saltar</span>
            </div>
            <div className="max-h-52 overflow-y-auto space-y-1.5 pr-1 text-left">
              {captions.map((c, idx) => (
                <div
                  key={idx}
                  onClick={() => seek(c.start)}
                  className="group flex flex-col gap-1 rounded-lg border border-white/[0.05] bg-white/[0.02] p-2 transition-colors hover:border-beam-400/30 hover:bg-white/[0.04] cursor-pointer"
                >
                  <div className="flex items-center justify-between text-[9px] text-beam-300/70">
                    <span className="font-mono">{c.start.toFixed(1)}s → {c.end.toFixed(1)}s</span>
                    <span className="text-white/20 group-hover:text-white/50 text-[8px]">Editar</span>
                  </div>
                  <input
                    type="text"
                    value={c.text}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => updateCaption(idx, e.target.value)}
                    className="w-full bg-transparent text-[10.5px] text-white/85 outline-none focus:border-b focus:border-beam-400 focus:text-white"
                  />
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function AudioTab() {
  const { selectedVoice, setSelectedVoice, playingVoiceId, previewVoice, flash, time, insertTtsClip } = useEditor();
  const [speechifyCredits, setSpeechifyCredits] = useState<boolean>(true);
  const [ttsText, setTtsText] = useState("");
  const [isSynthesizing, setIsSynthesizing] = useState(false);

  useEffect(() => {
    fetch("/api/speechify/status")
      .then((r) => r.json())
      .then((d) => {
        if (typeof d.has_credits === "boolean") {
          setSpeechifyCredits(d.has_credits);
        }
      })
      .catch(() => {});
  }, []);

  const bars = [0.4, 0.75, 0.55, 0.9, 0.35, 0.65, 1, 0.5, 0.8, 0.45, 0.7, 0.3, 0.6, 0.95, 0.4, 0.68];

  const voices = [
    // --- Voces VoiceStudio (Español) ---
    { id: "es-MX-JorgeNeural", n: "Jorge · México", d: "Conversacional & Dinámico · 1.0×", provider: "voicestudio" },
    { id: "es-US-AlonsoNeural", n: "Alonso · Latino", d: "Broadcast Internacional · 1.0×", provider: "voicestudio" },
    { id: "es-CO-GonzaloNeural", n: "Gonzalo · Colombia", d: "Neutro & Calmo · 0.95×", provider: "voicestudio" },
    { id: "es-AR-TomasNeural", n: "Tomás · Argentina", d: "Directo & Enérgico · 1.0×", provider: "voicestudio" },
    { id: "es-MX-DaliaNeural", n: "Dalia · México", d: "Femenina Cálida · 1.0×", provider: "voicestudio" },
    { id: "es-AR-ElenaNeural", n: "Elena · Argentina", d: "Femenina Expresiva · 0.95×", provider: "voicestudio" },
    { id: "es-ES-AlvaroNeural", n: "Álvaro · España", d: "Tech & Divulgación · 0.95×", provider: "voicestudio" },
    { id: "voicestudio-omni-es", n: "OmniVoice · Neutro", d: "VoiceStudio Multilingüe · 1.0×", provider: "voicestudio" },
    { id: "voicestudio-piper-dave", n: "Piper Dave · Docu", d: "VoiceStudio Locutor · 0.95×", provider: "voicestudio" },
    { id: "clon-propio", n: "Clon de voz propio", d: "Muestra de estudio 12 s", provider: "voicestudio" },
    // --- Voces Speechify (Español) ---
    { id: "speechify:alejandro", n: "Alejandro", d: "Speechify · Cálida · 1.0×", provider: "speechify" },
    { id: "speechify:aitana", n: "Aitana", d: "Speechify · Brillante · 1.0×", provider: "speechify" },
    { id: "speechify:alejandra", n: "Alejandra", d: "Speechify · Narrativa · 0.95×", provider: "speechify" },
    { id: "speechify:alexa", n: "Alexa", d: "Speechify · Estudio · 1.0×", provider: "speechify" },
    { id: "speechify:alondra", n: "Alondra", d: "Speechify · Documental · 0.95×", provider: "speechify" },
  ];

  return (
    <div className="space-y-4">
      {/* Herramienta Agilidad: Locución Rápida en el Cabezal (TTS Snippet) */}
      <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <SectionLabel>Insertar locución en cabezal</SectionLabel>
          <span className="font-mono text-[9.5px] text-white/50 bg-white/[0.05] px-1.5 py-0.5 rounded border border-white/[0.06]">
            {time.toFixed(1)}s
          </span>
        </div>
        <textarea
          rows={2}
          value={ttsText}
          onChange={(e) => setTtsText(e.target.value)}
          placeholder="Escribe la frase que dirá la voz en este segundo..."
          className="w-full resize-none rounded-lg border border-white/10 bg-white/[0.025] p-2 text-[11px] text-white/90 placeholder:text-white/25 focus:border-white/30 focus:outline-none"
        />
        <button
          type="button"
          disabled={isSynthesizing || !ttsText.trim()}
          onClick={async () => {
            if (!ttsText.trim()) return;
            setIsSynthesizing(true);
            await insertTtsClip(ttsText.trim());
            setTtsText("");
            setIsSynthesizing(false);
          }}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-white/15 bg-white/[0.08] hover:bg-white/[0.14] py-1.5 text-[10.5px] font-semibold text-white transition-all shadow-sm disabled:opacity-40 cursor-pointer"
        >
          <span>{isSynthesizing ? "Generando audio neuronal..." : `+ Insertar voz en ${time.toFixed(1)}s`}</span>
        </button>
      </div>

      <div className="rounded-xl border border-white/[0.06] bg-white/[0.015] p-3">
        <div className="flex items-center justify-between">
          <span className="text-[11.5px] text-white/85">Pulso Nocturno</span>
          <span className="micro-sm text-signal-400/80">Activa</span>
        </div>
        <div className="mt-3 flex h-10 items-end gap-[3px]">
          {bars.map((b, i) => (
            <div
              key={i}
              className="flex-1 rounded-sm bg-gradient-to-t from-beam-500/25 to-beam-300/70"
              style={{ height: `${b * 100}%` }}
            />
          ))}
        </div>
        <div className="mt-3 flex justify-between">
          <span className="micro-sm text-white/25">92 BPM</span>
          <span className="micro-sm text-white/25">-14 LUFS</span>
          <span className="micro-sm text-white/25">Reverb 18%</span>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <SectionLabel>Locución neuronal</SectionLabel>
          <span className="micro-sm text-white/30 tracking-wider">
            {voices.length} VOCES
          </span>
        </div>

        <div className="relative">
          <div className="max-h-[178px] overflow-y-auto space-y-2 pr-1.5 subtle-scrollbar">
            {voices.map((v) => {
              const isSelected = selectedVoice === v.id || (v.id === "speechify:alejandro" && !voices.some((x) => x.id === selectedVoice));
              const isPlaying = playingVoiceId === v.id;
              const isBlocked = v.provider === "speechify" && !speechifyCredits;

              return (
                <div
                  key={v.id}
                  onClick={() => {
                    if (isBlocked) {
                      flash("Créditos agotados en Speechify. Clave bloqueada.");
                      return;
                    }
                    setSelectedVoice(v.id);
                  }}
                  className={cn(
                    "group flex items-center justify-between rounded-xl border p-2.5 transition-colors",
                    isBlocked
                      ? "cursor-not-allowed opacity-40 border-white/[0.04] bg-white/[0.008]"
                      : isSelected
                      ? "cursor-pointer border-beam-400/30 bg-beam-500/[0.07]"
                      : "cursor-pointer border-white/[0.06] bg-white/[0.012] hover:border-white/[0.12]",
                  )}
                >
                  <span className="min-w-0 pr-2">
                    <span className="flex items-center gap-1.5">
                      <span className={cn("block text-[11px] truncate", isSelected ? "text-white/95 font-medium" : "text-white/80")}>
                        {v.n}
                      </span>
                      {v.provider === "speechify" && (
                        <span
                          className={cn(
                            "rounded-[4px] px-1 py-0.5 text-[8.5px] uppercase tracking-wider font-mono",
                            isBlocked
                              ? "border border-rose-500/25 bg-rose-500/10 text-rose-300/80"
                              : "border border-beam-500/25 bg-beam-500/15 text-beam-300",
                          )}
                        >
                          {isBlocked ? "Agotada" : "Speechify"}
                        </span>
                      )}
                      {v.provider === "voicestudio" && (
                        <span className="rounded-[4px] px-1 py-0.5 text-[8.5px] uppercase tracking-wider font-mono border border-cyan-500/25 bg-cyan-500/10 text-cyan-300">
                          VoiceStudio
                        </span>
                      )}
                    </span>
                    <span className="micro-sm mt-1 block text-white/25 truncate">{v.d}</span>
                  </span>

                  <button
                    type="button"
                    disabled={isBlocked}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (isBlocked) {
                        flash("Voz bloqueada sin créditos.");
                        return;
                      }
                      previewVoice(v.id);
                    }}
                    title={isBlocked ? "Voz bloqueada sin créditos" : isPlaying ? "Pausar muestra" : "Reproducir muestra de voz"}
                    className={cn(
                      "shrink-0 rounded-md p-1 transition-colors",
                      isBlocked
                        ? "cursor-not-allowed text-white/10 opacity-30"
                        : isPlaying
                        ? "text-beam-400"
                        : "text-white/25 hover:text-white/70",
                    )}
                  >
                    <IconMusic className={cn("h-3.5 w-3.5", isPlaying && "animate-pulse text-beam-400")} />
                  </button>
                </div>
              );
            })}
          </div>

          {/* Gradiente degradé inferior suave */}
          <div className="pointer-events-none absolute -bottom-0.5 left-0 right-0 h-6 bg-gradient-to-t from-[#0e0f15]/95 via-[#0e0f15]/60 to-transparent" />
        </div>
      </div>

      <Hairline />
      <div className="space-y-1.5">
        <SectionLabel>Mezcla inteligente</SectionLabel>
        <Toggle on label="Ducking automático" hint="-9 dB bajo la voz" onChange={() => {}} />
        <Toggle on label="Reducción de ruido" hint="Perfil de sala" onChange={() => {}} />
        <Toggle on={false} label="Beat detect" hint="92 BPM confirmado" onChange={() => {}} />
      </div>
    </div>
  );
}

function FxTab() {
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <SectionLabel>Look & LUT</SectionLabel>
        <div className="grid grid-cols-2 gap-2">
          {PRESETS.map((p, i) => (
            <button
              key={p.id}
              className={cn(
                "group overflow-hidden rounded-xl border text-left transition-all duration-300",
                i === 1 ? "border-beam-400/40 glow-beam" : "border-white/[0.07] hover:border-white/20",
              )}
            >
              <div className="h-14 w-full" style={{ background: p.swatch }} />
              <div className="p-2">
                <div className="text-[10.5px] text-white/80">{p.name}</div>
                <div className="micro-sm mt-1 text-white/25">{p.detail}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
      <Hairline />
      <div className="space-y-3">
        <SectionLabel>Ajustes finos</SectionLabel>
        {[
          { l: "Grano de película", v: 34 },
          { l: "Halación azul", v: 58 },
          { l: "Recorte vertical", v: 82 },
          { l: "Estabilización", v: 96 },
        ].map((s) => (
          <div key={s.l}>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[10.5px] text-white/55">{s.l}</span>
              <span className="tnum text-[9.5px] text-white/35">{s.v}%</span>
            </div>
            <Meter value={s.v} height={2} />
          </div>
        ))}
      </div>
      <Hairline />
      <div className="flex items-center gap-2.5 rounded-xl border border-white/[0.06] bg-white/[0.012] p-2.5">
        <IconScissors className="h-4 w-4 shrink-0 text-beam-200/70" />
        <div>
          <div className="text-[11px] text-white/80">Reencuadre inteligente</div>
          <div className="micro-sm mt-1 text-white/25">Sigue al sujeto en 9:16</div>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ESPACIO DE TRABAJO: EFECTOS (Subtítulos, Audio/Voz y Look & LUT)  */
/* ------------------------------------------------------------------ */

function EffectsTab() {
  const [effectSubTab, setEffectSubTab] = useState<"subtitles" | "audio" | "lut">("subtitles");

  return (
    <div className="space-y-4">
      {/* Sub-selector segmentado de efectos */}
      <div className="grid grid-cols-3 gap-1 rounded-xl border border-white/[0.08] bg-white/[0.02] p-1">
        <button
          type="button"
          onClick={() => setEffectSubTab("subtitles")}
          className={cn(
            "flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-[10px] font-medium transition-all cursor-pointer",
            effectSubTab === "subtitles"
              ? "bg-beam-500/20 text-beam-200 border border-beam-400/35 shadow-sm"
              : "text-white/45 hover:text-white/80 hover:bg-white/[0.04]",
          )}
        >
          <IconType className="h-3 w-3" />
          <span>Subtítulos</span>
        </button>

        <button
          type="button"
          onClick={() => setEffectSubTab("audio")}
          className={cn(
            "flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-[10px] font-medium transition-all cursor-pointer",
            effectSubTab === "audio"
              ? "bg-beam-500/20 text-beam-200 border border-beam-400/35 shadow-sm"
              : "text-white/45 hover:text-white/80 hover:bg-white/[0.04]",
          )}
        >
          <IconMusic className="h-3 w-3" />
          <span>Audio & Voz</span>
        </button>

        <button
          type="button"
          onClick={() => setEffectSubTab("lut")}
          className={cn(
            "flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-[10px] font-medium transition-all cursor-pointer",
            effectSubTab === "lut"
              ? "bg-beam-500/20 text-beam-200 border border-beam-400/35 shadow-sm"
              : "text-white/45 hover:text-white/80 hover:bg-white/[0.04]",
          )}
        >
          <IconCrop className="h-3 w-3" />
          <span>Look & LUT</span>
        </button>
      </div>

      {/* Vista según el subtab seleccionado */}
      {effectSubTab === "subtitles" && <TextTab />}
      {effectSubTab === "audio" && <AudioTab />}
      {effectSubTab === "lut" && <FxTab />}
    </div>
  );
}


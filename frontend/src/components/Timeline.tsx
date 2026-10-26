import { useEffect, useRef, useState } from "react";
import { DURATION, MOMENTS, TRACKS, type Clip, type TrackId } from "@/lib/data";
import { useEditor } from "@/lib/store";
import { cn } from "@/utils/cn";
import {
  IconChevron,
  IconClose,
  IconCopy,
  IconLock,
  IconMagnet,
  IconPlus,
  IconScissors,
  IconSparkle,
  IconTrash,
  IconVolume,
} from "./Icons";

const TRACK_H: Record<TrackId, number> = { v2: 30, v1: 48, t1: 24, a1: 34 };

const KIND_STYLE: Record<Clip["kind"], string> = {
  scene: "border-white/[0.14] bg-[#101010]",
  broll: "border-beam-400/50 bg-[#0d1a45]",
  caption: "border-white/[0.14] bg-[#0b0b0b]",
  music: "border-white/[0.12] bg-[#0f1220]",
  voice: "border-beam-400/40 bg-[#0a1230]",
  fx: "border-white/10 bg-white/[0.05]",
};

function wave(seed: number, n: number) {
  return Array.from({ length: n }, (_, i) => {
    const a = Math.abs(Math.sin(i * 0.42 + seed) * 0.6 + Math.sin(i * 0.17 + seed * 2) * 0.4);
    return 0.18 + a * 0.8;
  });
}

export function Timeline() {
  const {
    clips,
    time,
    duration,
    seek,
    playing,
    selected,
    select,
    updateClip,
    removeClip,
    addClip,
    duplicateClip,
    splitClipAtPlayhead,
    saveTimeline,
    setSilenceModalOpen,
    setShortcutsModalOpen,
    pxPerSec,
    setPxPerSec,
  } = useEditor();

  const safeDuration = duration || DURATION;
  const [snap, setSnap] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const [open, setOpen] = useState(true);
  const [timelineHeight, setTimelineHeight] = useState(230);
  const [isResizing, setIsResizing] = useState(false);
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const [editingClip, setEditingClip] = useState<Clip | null>(null);
  const [isAddingClip, setIsAddingClip] = useState(false);
  const [newClipTrack, setNewClipTrack] = useState<TrackId>("v2");
  const [newClipLabel, setNewClipLabel] = useState("");
  const [newClipDuration, setNewClipDuration] = useState(4.0);

  const startResize = (e: React.PointerEvent) => {
    e.preventDefault();
    setIsResizing(true);
    const startY = e.clientY;
    const startH = timelineHeight;

    const onPointerMove = (ev: PointerEvent) => {
      const deltaY = startY - ev.clientY;
      const newH = Math.max(150, Math.min(560, startH + deltaY));
      setTimelineHeight(newH);
    };

    const onPointerUp = () => {
      setIsResizing(false);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
  };

  const toggleExpandHeight = () => {
    if (timelineHeight < 310) {
      setTimelineHeight(380);
      setOpen(true);
    } else if (timelineHeight < 460) {
      setTimelineHeight(500);
      setOpen(true);
    } else {
      setTimelineHeight(230);
    }
  };

  const currentTrackH: Record<TrackId, number> =
    timelineHeight >= 460
      ? { v2: 56, v1: 96, t1: 38, a1: 60 }
      : timelineHeight >= 310
      ? { v2: 40, v1: 72, t1: 30, a1: 46 }
      : TRACK_H;

  const scrollRef = useRef<HTMLDivElement>(null);
  const width = safeDuration * pxPerSec;

  const snapVal = (v: number) => (snap ? Math.round(v * 4) / 4 : v);

  // 1. AUTO-SCROLL DE LA LÍNEA DE TIEMPO DURANTE LA REPRODUCCIÓN
  useEffect(() => {
    if (!autoScroll || !playing || !scrollRef.current) return;
    const el = scrollRef.current;
    const playheadPx = time * pxPerSec;
    const currentScroll = el.scrollLeft;
    const clientW = el.clientWidth;

    // Si la cabeza lectora sobrepasa el 70% de la ventana visible o queda fuera a la izquierda
    if (playheadPx > currentScroll + clientW * 0.72 || playheadPx < currentScroll) {
      el.scrollTo({
        left: Math.max(0, playheadPx - clientW * 0.25),
        behavior: "smooth",
      });
    }
  }, [time, playing, pxPerSec, autoScroll]);

  // 2. ATAJO DE TECLADO: SUPRIMIR O RETROCESO PARA QUITAR CLIP SELECCIONADO
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.key === "Delete" || e.key === "Backspace") && selected) {
        const target = e.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) return;
        removeClip(selected);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selected, removeClip]);

  const dragClip = (e: React.PointerEvent, clip: Clip, mode: "move" | "start" | "end") => {
    e.stopPropagation();
    select(clip.id);
    const x0 = e.clientX;
    const s0 = clip.start;
    const d0 = clip.duration;
    const onMove = (ev: PointerEvent) => {
      const dt = (ev.clientX - x0) / pxPerSec;
      if (mode === "move") {
        updateClip(clip.id, { start: Math.max(0, snapVal(s0 + dt)) });
      } else if (mode === "end") {
        updateClip(clip.id, { duration: Math.max(0.5, snapVal(d0 + dt)) });
      } else {
        const ns = Math.max(0, snapVal(s0 + dt));
        updateClip(clip.id, { start: ns, duration: Math.max(0.5, d0 + (s0 - ns)) });
      }
    };
    const up = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", up);
  };

  const scrub = (e: React.PointerEvent) => {
    const el = scrollRef.current;
    if (!el) return;
    const move = (cx: number) => {
      const r = el.getBoundingClientRect();
      seek((cx - r.left + el.scrollLeft) / pxPerSec);
    };
    move(e.clientX);
    const onMove = (ev: PointerEvent) => move(ev.clientX);
    const up = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", up);
  };

  const selectedClip = clips.find((c) => c.id === selected);

  const ticks = Array.from({ length: Math.ceil(safeDuration) + 1 }, (_, i) => i);
  const step = pxPerSec < 26 ? 4 : pxPerSec < 46 ? 2 : 1;

  const handleCreateClip = () => {
    const kindMap: Record<TrackId, Clip["kind"]> = {
      v2: "broll",
      v1: "scene",
      t1: "caption",
      a1: "voice",
    };
    const newId = `${kindMap[newClipTrack]}-${Date.now().toString(36)}`;
    const newClip: Clip = {
      id: newId,
      track: newClipTrack,
      start: Math.round(time * 100) / 100,
      duration: Math.max(0.5, newClipDuration),
      label: newClipLabel.trim() || `${TRACKS.find((t) => t.id === newClipTrack)?.name || "Clip"} #${clips.length + 1}`,
      kind: kindMap[newClipTrack],
      ai: true,
    };
    addClip(newClip);
    setIsAddingClip(false);
    setNewClipLabel("");
  };

  return (
    <section
      style={{ height: open ? `${timelineHeight}px` : "36px" }}
      className={cn(
        "relative z-20 flex shrink-0 flex-col border-t border-white/[0.08] bg-black transition-[height]",
        isResizing ? "duration-0" : "duration-200",
      )}
    >
      {/* Maneta superior para arrastrar y cambiar altura libremente */}
      {/* Maneta superior sutil para arrastrar y cambiar altura */}
      <div
        onPointerDown={startResize}
        className={cn(
          "absolute -top-1 inset-x-0 h-2 cursor-row-resize z-40 transition-colors select-none",
          isResizing ? "bg-beam-400/40" : "hover:bg-white/10",
        )}
        title="Arrastra verticalmente para ajustar la altura de la línea de tiempo"
      />

      {/* header limpio y ultra-delgado */}
      <div className="flex h-9 shrink-0 items-center justify-between gap-2 px-3 select-none">
        {/* Zona Izquierda: Título + Metadata + Selector de Expansión */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            title={open ? "Ocultar línea de tiempo" : "Mostrar línea de tiempo"}
            className="group flex items-center gap-1.5 text-white/70 hover:text-white transition-colors cursor-pointer"
          >
            <IconChevron
              className={cn(
                "h-3 w-3 text-white/40 transition-transform duration-200 group-hover:text-beam-300",
                open ? "rotate-0" : "-rotate-90",
              )}
            />
            <span className="text-[12px] font-medium leading-none text-white whitespace-nowrap">Línea de tiempo</span>
          </button>

          <span className="rounded border border-white/[0.08] bg-white/[0.02] px-1.5 py-0.5 text-[9px] font-mono text-white/40 whitespace-nowrap">
            {Math.round(safeDuration)}s · 24fps
          </span>

          {open && (
            <button
              type="button"
              onClick={toggleExpandHeight}
              className={cn(
                "flex h-6 items-center gap-1 rounded-md border px-1.5 text-[10px] font-medium transition-all cursor-pointer whitespace-nowrap shrink-0",
                timelineHeight >= 310
                  ? "border-beam-400/50 bg-beam-500/15 text-beam-200"
                  : "border-white/[0.09] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20",
              )}
              title={
                timelineHeight < 310
                  ? "Expandir pistas (380px)"
                  : timelineHeight < 460
                  ? "Modo Enfoque Máximo (500px)"
                  : "Restaurar altura normal (230px)"
              }
            >
              <span className="text-[10px] leading-none">{timelineHeight >= 310 ? "⤥" : "⤢"}</span>
              <span className="hidden sm:inline">
                {timelineHeight >= 460 ? "500px" : timelineHeight >= 310 ? "380px" : "Expandir"}
              </span>
            </button>
          )}
        </div>

        {/* Zona Central: Zoom ultra-delgado */}
        {open && (
          <div className="flex h-6 items-center rounded-md border border-white/10 bg-white/[0.03] px-1 shrink-0">
            <button
              onClick={() => setPxPerSec(Math.max(18, pxPerSec - 8))}
              className="h-full px-1 text-[11px] leading-none text-white/40 hover:text-white transition-colors cursor-pointer"
              title="Reducir zoom"
            >
              −
            </button>
            <span className="w-10 text-center text-[9.5px] font-mono text-white/50 whitespace-nowrap">{pxPerSec}px</span>
            <button
              onClick={() => setPxPerSec(Math.min(90, pxPerSec + 8))}
              className="h-full px-1 text-[11px] leading-none text-white/40 hover:text-white transition-colors cursor-pointer"
              title="Aumentar zoom"
            >
              +
            </button>
          </div>
        )}

        {/* Zona Derecha: Barra de Herramientas Segmentada y Ultra-Fina */}
        {open && (
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Grupo de herramientas unificado */}
            <div className="flex h-6 items-center rounded-md border border-white/10 bg-white/[0.03] p-0.5 divide-x divide-white/10 shrink-0">
              {/* 1. Dividir */}
              <button
                type="button"
                onClick={splitClipAtPlayhead}
                className="flex items-center gap-1 px-2 h-full text-[10px] font-medium text-white/70 hover:text-white hover:bg-white/[0.08] transition-all cursor-pointer whitespace-nowrap"
                title="Dividir clip en el cabezal (Atajo: S o C)"
              >
                <IconScissors className="h-2.5 w-2.5 text-white/50" />
                <span>Dividir</span>
              </button>

              {/* 2. Auto-JumpCut Silencios */}
              <button
                type="button"
                onClick={() => setSilenceModalOpen(true)}
                className="flex items-center gap-1 px-2 h-full text-[10px] font-medium text-white/70 hover:text-white hover:bg-white/[0.08] transition-all cursor-pointer whitespace-nowrap"
                title="Auto-JumpCut: Escanear y recortar silencios"
              >
                <IconSparkle className="h-2.5 w-2.5 text-beam-300" />
                <span>Silencios</span>
              </button>

              {/* 3. Insertar Clip */}
              <button
                type="button"
                onClick={() => {
                  setNewClipTrack("v2");
                  setNewClipDuration(4.0);
                  setNewClipLabel("");
                  setIsAddingClip(true);
                }}
                className="flex items-center gap-1 px-2 h-full text-[10px] font-medium text-white/70 hover:text-white hover:bg-white/[0.08] transition-all cursor-pointer whitespace-nowrap"
                title="Insertar clip manual en el cabezal"
              >
                <IconPlus className="h-2.5 w-2.5 text-white/50" />
                <span>Clip</span>
              </button>
            </div>

            {/* Guardar cambios del timeline en el proyecto */}
            <button
              type="button"
              onClick={saveTimeline}
              className="flex h-6 items-center gap-1 rounded-md border border-emerald-400/40 bg-emerald-500/15 px-2 text-[10px] font-semibold text-emerald-200 hover:bg-emerald-500/25 transition-all cursor-pointer whitespace-nowrap"
              title="Guardar posiciones y duraciones de cards y B-Roll"
            >
              <span>Guardar</span>
            </button>

            {/* 4. Opciones */}
            <div className="relative shrink-0">
              <button
                type="button"
                onClick={() => setOptionsOpen((o) => !o)}
                aria-expanded={optionsOpen}
                className={cn(
                  "flex h-6 items-center gap-1 rounded-md border px-1.5 text-[10px] font-medium transition-all cursor-pointer whitespace-nowrap",
                  optionsOpen
                    ? "border-beam-400/60 bg-beam-500/15 text-beam-200"
                    : "border-white/10 bg-white/[0.03] text-white/60 hover:text-white hover:border-white/20",
                )}
                title="Opciones de edición"
              >
                <span>Opciones</span>
                <IconChevron className={cn("h-2.5 w-2.5 transition-transform", optionsOpen && "rotate-180")} />
              </button>
              {optionsOpen && (
                <div className="absolute right-0 top-full z-50 mt-1.5 w-60 rounded-xl border border-white/15 bg-[#0a0a0a] p-1.5 shadow-[0_20px_50px_rgba(0,0,0,1)]">
                  <button
                    onClick={() => setAutoScroll(!autoScroll)}
                    className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left text-[11px] text-white/80 hover:bg-white/[0.06]"
                  >
                    <span>Seguir cabezal (auto-scroll)</span>
                    <span className={cn("text-[10px] font-mono", autoScroll ? "text-beam-300" : "text-white/30")}>
                      {autoScroll ? "Activo" : "Inactivo"}
                    </span>
                  </button>
                  <button
                    onClick={() => setSnap(!snap)}
                    className="flex w-full items-center justify-between gap-3 rounded-lg px-2.5 py-2 text-left text-[11px] text-white/80 hover:bg-white/[0.06]"
                  >
                    <span className="flex items-center gap-2">
                      <IconMagnet className="h-3.5 w-3.5" />
                      Ajuste magnético
                    </span>
                    <span className={cn("text-[10px] font-mono", snap ? "text-beam-300" : "text-white/30")}>
                      {snap ? "Activo" : "Inactivo"}
                    </span>
                  </button>
                </div>
              )}
            </div>

            {/* 5. Atajos HUD */}
            <button
              type="button"
              onClick={() => setShortcutsModalOpen(true)}
              className="grid h-6 w-6 place-items-center rounded-md border border-white/10 bg-white/[0.03] text-white/50 hover:text-white hover:border-white/20 transition-all cursor-pointer shrink-0"
              title="Atajos de teclado (?)"
            >
              <span className="text-[10px] font-mono font-medium leading-none">?</span>
            </button>
          </div>
        )}
      </div>
      <div className="h-px w-full bg-white/[0.07]" />

      {/* body */}
      <div className={cn("min-h-0 flex-1", open ? "flex" : "hidden")}>
        {/* track heads */}
        <div className="flex w-[116px] shrink-0 flex-col border-r border-white/[0.06] bg-black">
          <div className="h-7 shrink-0 border-b border-white/[0.05]" />
          {TRACKS.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-2 border-b border-white/[0.04] px-2.5"
              style={{ height: currentTrackH[t.id] }}
            >
              <span className="micro-sm font-semibold text-beam-200/70">{t.tag}</span>
              <span className="micro-sm truncate text-white/50">{t.name}</span>
              <div className="ml-auto flex items-center gap-1.5 text-white/20">
                {t.id === "a1" ? (
                  <IconVolume className="h-3 w-3 text-beam-300/60" />
                ) : (
                  <IconLock className="h-3 w-3 opacity-30" />
                )}
              </div>
            </div>
          ))}
          <div className="flex min-h-0 flex-1 items-end px-2.5 pb-2">
            <span className="micro-sm text-[10px] text-white/25">
              {clips.length} elementos
            </span>
          </div>
        </div>

        {/* lanes */}
        <div
          ref={scrollRef}
          className="relative min-h-0 flex-1 overflow-x-auto overflow-y-auto subtle-scrollbar select-none"
        >
          <div className="relative" style={{ width }}>
            {/* ruler */}
            <div
              className="relative h-7 cursor-ew-resize border-b border-white/[0.06] bg-black"
              onPointerDown={scrub}
              onPointerMove={(e) => {
                const r = e.currentTarget.getBoundingClientRect();
                setHover(Math.max(0, Math.min(safeDuration, (e.clientX - r.left) / pxPerSec)));
              }}
              onPointerLeave={() => setHover(null)}
            >
              {ticks.map((i) =>
                i % step === 0 ? (
                  <div
                    key={i}
                    className="absolute top-0 h-full"
                    style={{ left: i * pxPerSec }}
                  >
                    <span className="absolute left-0 top-0 h-2 w-px bg-white/15" />
                    <span className="tnum absolute left-1 top-2 text-[9px] text-white/30">
                      {i}s
                    </span>
                    <span className="absolute bottom-0 left-0 h-2.5 w-px bg-white/[0.07]" />
                  </div>
                ) : (
                  <span
                    key={i}
                    className="absolute bottom-0 h-1.5 w-px bg-white/[0.07]"
                    style={{ left: i * pxPerSec }}
                  />
                ),
              )}
              {/* key moments */}
              {MOMENTS.map((m) => (
                <div
                  key={m.t}
                  className="group absolute bottom-[3px] z-10 -translate-x-1/2"
                  style={{ left: m.t * pxPerSec }}
                >
                  <span
                    className={cn(
                      "block h-1.5 w-1.5 rounded-full ring-2 ring-black/40",
                      m.kind === "risk" ? "bg-ember-400" : "bg-signal-400",
                    )}
                  />
                  <span className="pointer-events-none absolute bottom-4 left-1/2 z-30 hidden -translate-x-1/2 whitespace-nowrap rounded-md border border-white/10 bg-ink-900/95 px-2 py-1 text-[9px] text-white/70 shadow-xl group-hover:block">
                    {m.label} · {m.t}s
                  </span>
                </div>
              ))}
              {hover !== null && (
                <span
                  className="tnum pointer-events-none absolute top-2 text-[9px] text-beam-200/80 font-medium"
                  style={{ left: hover * pxPerSec + 4 }}
                >
                  {hover.toFixed(1)}s
                </span>
              )}
            </div>

            {/* lanes */}
            {TRACKS.map((t) => (
              <div
                key={t.id}
                className="relative border-b border-white/[0.04]"
                style={{ height: currentTrackH[t.id] }}
                onPointerDown={() => select(null)}
              >
                {clips
                  .filter((c) => c.track === t.id)
                  .map((c) => {
                    const isSel = selected === c.id;
                    const w = c.duration * pxPerSec;
                    return (
                      <div
                        key={c.id}
                        onPointerDown={(e) => dragClip(e, c, "move")}
                        onDoubleClick={(e) => {
                          e.stopPropagation();
                          setEditingClip(c);
                        }}
                        className={cn(
                          "group absolute top-[3px] cursor-grab overflow-hidden rounded-[7px] border transition-all duration-150 active:cursor-grabbing",
                          KIND_STYLE[c.kind],
                          isSel
                            ? "ring-2 ring-beam-400 border-beam-300 z-10"
                            : "hover:border-white/35 z-0",
                        )}
                        style={{ left: c.start * pxPerSec, width: Math.max(16, w), height: currentTrackH[t.id] - 6 }}
                        title={`${c.label} (${c.duration.toFixed(1)}s) - Doble clic para editar`}
                      >
                        {/* video thumbnail strip */}
                        {c.frame && (
                          <div className="absolute inset-0 flex pointer-events-none">
                            {Array.from({ length: Math.max(1, Math.ceil(w / 44)) }).map((_, i) => (
                              <img
                                key={i}
                                src={c.frame}
                                alt=""
                                className="no-drag h-full w-[44px] shrink-0 object-cover opacity-45"
                                style={{ filter: "saturate(0.75)" }}
                              />
                            ))}
                          </div>
                        )}

                        {/* waveform for audio */}
                        {(c.kind === "music" || c.kind === "voice") && (
                          <div className="absolute inset-x-1 bottom-0 flex h-[65%] items-end gap-[1.5px] opacity-75 pointer-events-none">
                            {wave(c.start + c.duration, Math.max(6, Math.floor(w / 3))).map((h, i) => (
                              <span
                                key={i}
                                className="flex-1 rounded-[1px] bg-beam-400/80"
                                style={{ height: `${h * 100}%` }}
                              />
                            ))}
                          </div>
                        )}

                        {/* captions indicator */}
                        {c.kind === "caption" && (
                          <div className="absolute inset-0 flex items-center gap-[2px] px-2 opacity-65 pointer-events-none">
                            {Array.from({ length: Math.max(3, Math.floor(w / 9)) }).map((_, i) => (
                              <span
                                key={i}
                                className="h-[3px] rounded-full bg-beam-300/80"
                                style={{ width: 3 + ((i * 7) % 9) }}
                              />
                            ))}
                          </div>
                        )}

                        {/* label and info */}
                        <div className="relative flex h-full items-center gap-1.5 px-2 pointer-events-none">
                          {c.ai && <IconSparkle className="h-3 w-3 shrink-0 text-beam-200/90" />}
                          <span className="truncate text-[10px] font-medium tracking-wide text-white/90 drop-shadow-sm">
                            {c.label}
                          </span>
                          {w > 110 && (
                            <span className="tnum ml-auto shrink-0 text-[9px] font-mono text-white/60">
                              {c.duration.toFixed(1)}s
                            </span>
                          )}
                        </div>

                        {/* TRIM HANDLE LEFT (Alargar / Acortar inicio) */}
                        <div
                          onPointerDown={(e) => dragClip(e, c, "start")}
                          title="Arrastrar para alargar o acortar inicio"
                          className={cn(
                            "absolute inset-y-0 left-0 w-2.5 z-20 cursor-ew-resize flex items-center justify-center transition-all",
                            isSel
                              ? "bg-beam-400/40 opacity-100 border-r border-beam-300"
                              : "opacity-0 group-hover:opacity-100 bg-white/20 hover:bg-beam-400/50"
                          )}
                        >
                          <span className="h-3.5 w-0.5 rounded-full bg-white/90" />
                        </div>

                        {/* TRIM HANDLE RIGHT (Alargar / Acortar final) */}
                        <div
                          onPointerDown={(e) => dragClip(e, c, "end")}
                          title="Arrastrar para alargar o acortar final"
                          className={cn(
                            "absolute inset-y-0 right-0 w-2.5 z-20 cursor-ew-resize flex items-center justify-center transition-all",
                            isSel
                              ? "bg-beam-400/40 opacity-100 border-l border-beam-300"
                              : "opacity-0 group-hover:opacity-100 bg-white/20 hover:bg-beam-400/50"
                          )}
                        >
                          <span className="h-3.5 w-0.5 rounded-full bg-white/90" />
                        </div>
                      </div>
                    );
                  })}
              </div>
            ))}

            {/* playhead line */}
            <div
              className="pointer-events-none absolute top-0 bottom-0 z-30 w-px bg-beam-300"
              style={{ left: time * pxPerSec }}
            >
              <span className="absolute -left-[5px] -top-[1px] h-3 w-[11px] rounded-b-sm bg-beam-300" />
            </div>
          </div>
        </div>
      </div>

      {/* FOOTER: CONTROLES DEL ELEMENTO SELECCIONADO */}
      <div className={cn("h-9 shrink-0 items-center justify-between border-t border-white/[0.06] bg-black px-3", open ? "flex" : "hidden")}>
        {selectedClip ? (
          <div className="flex w-full items-center gap-2 overflow-x-auto text-xs">
            <span className="rounded bg-white/[0.08] px-1.5 py-0.5 text-[9.5px] font-semibold text-white/80 uppercase">
              {TRACKS.find((t) => t.id === selectedClip.track)?.tag || "V1"}
            </span>
            <span className="max-w-[220px] truncate text-[11px] font-medium text-white/90">
              {selectedClip.label}
            </span>
            <span className="text-[10px] font-mono text-white/40">
              {selectedClip.start.toFixed(1)}s → {(selectedClip.start + selectedClip.duration).toFixed(1)}s ({selectedClip.duration.toFixed(1)}s)
            </span>

            <div className="h-3 w-px bg-white/10 mx-1" />

            {/* Acciones principales del clip */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setEditingClip(selectedClip)}
                className="flex items-center gap-1 rounded-md border border-white/15 bg-white/[0.07] px-2 py-0.5 text-[10.5px] font-medium text-white hover:bg-white/[0.14] transition-all cursor-pointer"
                title="Editar propiedades y contenido del clip"
              >
                <span>✎ Editar</span>
              </button>

              <button
                onClick={() => duplicateClip(selectedClip.id)}
                className="flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10.5px] text-white/70 hover:text-white hover:border-white/25 transition-all cursor-pointer"
                title="Duplicar este elemento"
              >
                <IconCopy className="h-3 w-3" />
                <span>Duplicar</span>
              </button>

              <button
                onClick={() => setAdjustOpen((o) => !o)}
                className={cn(
                  "flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10.5px] transition-all cursor-pointer",
                  adjustOpen
                    ? "border-beam-400/60 bg-beam-500/15 text-beam-200"
                    : "border-white/10 bg-white/[0.03] text-white/60 hover:text-white",
                )}
                title="Ajustar duración y desplazamiento fino"
              >
                <span>Ajustar</span>
                <IconChevron className={cn("h-2.5 w-2.5 transition-transform", adjustOpen && "rotate-180")} />
              </button>

              {adjustOpen && (
                <div className="flex items-center gap-1 rounded-md border border-white/10 bg-[#0a0a0a] px-1 py-0.5">
                  <button
                    onClick={() => updateClip(selectedClip.id, { duration: Math.max(0.5, selectedClip.duration - 1) })}
                    className="rounded px-1.5 py-0.2 text-[9.5px] text-white/60 hover:text-white hover:bg-white/10"
                    title="Acortar 1s"
                  >
                    −1s
                  </button>
                  <button
                    onClick={() => updateClip(selectedClip.id, { duration: Math.max(0.5, selectedClip.duration - 0.25) })}
                    className="rounded px-1 py-0.2 text-[9.5px] text-white/60 hover:text-white hover:bg-white/10"
                    title="Acortar 0.25s"
                  >
                    −0.25s
                  </button>
                  <span className="px-1 text-[9.5px] font-mono text-white/40">Duración</span>
                  <button
                    onClick={() => updateClip(selectedClip.id, { duration: selectedClip.duration + 0.25 })}
                    className="rounded px-1 py-0.2 text-[9.5px] text-white/60 hover:text-white hover:bg-white/10"
                    title="Alargar 0.25s"
                  >
                    +0.25s
                  </button>
                  <button
                    onClick={() => updateClip(selectedClip.id, { duration: selectedClip.duration + 1 })}
                    className="rounded px-1.5 py-0.2 text-[9.5px] text-white/60 hover:text-white hover:bg-white/10"
                    title="Alargar 1s"
                  >
                    +1s
                  </button>
                </div>
              )}
            </div>

            {/* Quitar: botón sutil */}
            <button
              onClick={() => removeClip(selectedClip.id)}
              className="ml-auto flex items-center gap-1 rounded-md border border-white/10 bg-transparent px-2 py-0.5 text-[10.5px] text-white/50 hover:text-red-400 hover:border-red-500/30 hover:bg-red-500/[0.08] transition-all cursor-pointer"
              title="Quitar este elemento (Supr)"
            >
              <IconTrash className="h-3 w-3" />
              <span>Quitar</span>
            </button>
          </div>
        ) : (
          <div className="flex w-full items-center justify-between text-[10.5px] text-white/35">
            <span>Selecciona un elemento para editarlo</span>
            <span className="font-mono text-[9.5px] text-white/25">
              Espacio: Reproducir · S: Dividir · Supr: Eliminar · Doble clic: Editar
            </span>
          </div>
        )}
      </div>

      {/* MODAL: EDITAR / PONER OTRO ELEMENTO */}
      {editingClip && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-ink-900 p-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <IconSparkle className="h-4 w-4 text-beam-300" />
                Editar / Reemplazar contenido
              </h3>
              <button
                onClick={() => setEditingClip(null)}
                className="text-white/40 hover:text-white"
              >
                <IconClose className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4 py-4 text-xs">
              <div>
                <label className="block text-white/50 mb-1">Nombre o concepto visual</label>
                <input
                  type="text"
                  value={editingClip.label}
                  onChange={(e) => setEditingClip({ ...editingClip, label: e.target.value })}
                  className="w-full rounded-xl border border-white/15 bg-black/40 px-3 py-2 text-white focus:border-beam-400 focus:outline-none"
                  placeholder="Ej: Inserto de gráficos, B-Roll, etc."
                />
              </div>

              <div>
                <label className="block text-white/50 mb-1">Pista de destino</label>
                <select
                  value={editingClip.track}
                  onChange={(e) => setEditingClip({ ...editingClip, track: e.target.value as TrackId })}
                  className="w-full rounded-xl border border-white/15 bg-black/40 px-3 py-2 text-white focus:border-beam-400 focus:outline-none"
                >
                  <option value="v2">V2 - B-ROLL / INSERTOS / TARJETAS</option>
                  <option value="v1">V1 - VIDEO PRINCIPAL / ESCENAS</option>
                  <option value="t1">TX - SUBTÍTULOS / TEXTOS</option>
                  <option value="a1">A1 - AUDIO / LOCUCIÓN</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-white/50 mb-1">Segundo de inicio (s)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={editingClip.start}
                    onChange={(e) => setEditingClip({ ...editingClip, start: Math.max(0, parseFloat(e.target.value) || 0) })}
                    className="w-full rounded-xl border border-white/15 bg-black/40 px-3 py-2 text-white focus:border-beam-400 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-white/50 mb-1">Duración (s)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.5"
                    value={editingClip.duration}
                    onChange={(e) => setEditingClip({ ...editingClip, duration: Math.max(0.5, parseFloat(e.target.value) || 0.5) })}
                    className="w-full rounded-xl border border-white/15 bg-black/40 px-3 py-2 text-white focus:border-beam-400 focus:outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-white/10">
              <button
                onClick={() => {
                  removeClip(editingClip.id);
                  setEditingClip(null);
                }}
                className="flex items-center gap-1.5 rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-red-300 hover:bg-red-500/20 text-xs transition-colors"
              >
                <IconTrash className="h-3.5 w-3.5" />
                <span>Quitar elemento</span>
              </button>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setEditingClip(null)}
                  className="rounded-xl border border-white/10 px-3 py-1.5 text-white/60 hover:text-white text-xs transition-colors"
                >
                  Cancelar
                </button>
                <button
                  onClick={() => {
                    updateClip(editingClip.id, {
                      label: editingClip.label,
                      track: editingClip.track,
                      start: editingClip.start,
                      duration: editingClip.duration,
                    });
                    setEditingClip(null);
                  }}
                  className="rounded-xl border border-beam-400 bg-beam-500 px-4 py-1.5 font-medium text-white shadow-lg text-xs hover:bg-beam-400 transition-colors"
                >
                  Guardar cambios
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL: INSERTAR NUEVO CLIP */}
      {isAddingClip && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-fade-in">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-ink-900 p-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-white/10">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <IconPlus className="h-4 w-4 text-beam-300" />
                Insertar nuevo elemento en {time.toFixed(1)}s
              </h3>
              <button
                onClick={() => setIsAddingClip(false)}
                className="text-white/40 hover:text-white"
              >
                <IconClose className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4 py-4 text-xs">
              <div>
                <label className="block text-white/50 mb-1">Pista donde colocarlo</label>
                <select
                  value={newClipTrack}
                  onChange={(e) => setNewClipTrack(e.target.value as TrackId)}
                  className="w-full rounded-xl border border-white/15 bg-black/40 px-3 py-2 text-white focus:border-beam-400 focus:outline-none"
                >
                  <option value="v2">V2 - B-ROLL / INSERTOS / APOYO VISUAL</option>
                  <option value="v1">V1 - VIDEO / ESCENA</option>
                  <option value="t1">TX - SUBTÍTULOS / TEXTO</option>
                  <option value="a1">A1 - AUDIO / LOCUCIÓN</option>
                </select>
              </div>

              <div>
                <label className="block text-white/50 mb-1">Nombre o descripción del contenido</label>
                <input
                  type="text"
                  value={newClipLabel}
                  onChange={(e) => setNewClipLabel(e.target.value)}
                  className="w-full rounded-xl border border-white/15 bg-black/40 px-3 py-2 text-white focus:border-beam-400 focus:outline-none"
                  placeholder="Ej: B-Roll toma aérea, Inserto gráfico..."
                />
              </div>

              <div>
                <label className="block text-white/50 mb-1">Duración (segundos)</label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  value={newClipDuration}
                  onChange={(e) => setNewClipDuration(Math.max(0.5, parseFloat(e.target.value) || 0.5))}
                  className="w-full rounded-xl border border-white/15 bg-black/40 px-3 py-2 text-white focus:border-beam-400 focus:outline-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/10">
              <button
                onClick={() => setIsAddingClip(false)}
                className="rounded-xl border border-white/10 px-3 py-1.5 text-white/60 hover:text-white text-xs transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateClip}
                className="rounded-xl border border-beam-400 bg-beam-500 px-4 py-1.5 font-medium text-white shadow-lg text-xs hover:bg-beam-400 transition-colors"
              >
                Insertar en Línea de Tiempo
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

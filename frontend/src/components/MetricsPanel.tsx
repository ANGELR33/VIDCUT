import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AUDIENCE,
  AUTOMATIONS,
  BASE_RETENTION,
  HEATMAP,
  MOMENTS,
  PLATFORMS,
  compact,
  retentionAt,
} from "@/lib/data";
import { useEditor } from "@/lib/store";
import { cn } from "@/utils/cn";
import { Collapsible, Meter, SectionLabel } from "./ui";
import {
  IconBookmark,
  IconChart,
  IconCheck,
  IconClock,
  IconComment,
  IconCopy,
  IconEye,
  IconFlame,
  IconLock,
  IconPlay,
  IconScissors,
  IconSend,
  IconSparkle,
  IconTrash,
} from "./Icons";

function IconRefresh({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M23 4v6h-6" />
      <path d="M1 20v-6h6" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function IconExternalLink({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

function IconBrain({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-2.04z" />
      <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-2.04z" />
    </svg>
  );
}

function IconYouTube({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  );
}

function IconFacebook({ className = "w-3.5 h-3.5" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  );
}

interface ChannelVideoItem {
  project_id: string;
  video_id: string;
  title: string;
  channel_id: string;
  channel_title: string;
  channel_tag: string;
  published_at?: string;
  structure_type?: string;
  hook_type?: string;
  metrics: {
    views: number;
    likes: number;
    comments: number;
    shares?: number;
    saves?: number;
    retention_pct: number;
    viral_score: number;
    hook_pct: number;
    ctr_pct: number;
  };
}

interface RankedStructure {
  structure_type: string;
  name: string;
  avg_score: number;
  video_count: number;
}

interface RankedHook {
  hook_type: string;
  name: string;
  avg_retention_pct: number;
  sample_count: number;
}

interface ChannelIntel {
  channel_id: string;
  channel_title: string;
  channel_tag: string;
  total_videos_analyzed: number;
  total_views: number;
  avg_retention_pct: number;
  avg_viral_score: number;
  best_structure?: RankedStructure;
  ranked_structures?: RankedStructure[];
  best_hook?: RankedHook;
  ranked_hooks?: RankedHook[];
  top_video_example?: {
    title: string;
    structure: string;
    score: number;
  };
  anti_patterns?: string[];
}

interface MetricsOverviewData {
  channels: ChannelIntel[];
  total_tracked_videos: number;
  recent_videos: ChannelVideoItem[];
}

/* ---------- animated counter ---------- */
function Counter({ value, format }: { value: number; format: (n: number) => string }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    const b = value;
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - start) / 700);
      const e = 1 - Math.pow(1 - p, 3);
      setShown(a + (b - a) * e);
      if (p < 1) raf = requestAnimationFrame(tick);
      else from.current = b;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <>{format(shown)}</>;
}

/* ---------- gauge ---------- */
function ScoreGauge({
  overrideScore,
  customLabel,
  customGrade,
  color = "#2f5cff",
  customHook,
  customRetention,
  customBounce,
}: {
  overrideScore?: number;
  customLabel?: string;
  customGrade?: string;
  color?: string;
  customHook?: number;
  customRetention?: number;
  customBounce?: number;
} = {}) {
  const { score, boost } = useEditor();
  const currentScore = overrideScore !== undefined ? overrideScore : score;
  const L = Math.PI * 64;
  const angle = -90 + (currentScore / 100) * 180;
  const grade =
    customGrade ||
    (currentScore >= 90 ? "Élite" : currentScore >= 80 ? "Alto potencial" : currentScore >= 70 ? "Sólido" : "En desarrollo");

  const hookVal = customHook !== undefined ? customHook : Math.min(98, 58 + boost * 80);
  const retVal = customRetention !== undefined ? customRetention : Math.min(92, (0.41 + boost) * 100);
  const bounceVal = customBounce !== undefined ? customBounce : Math.max(5, 32 - boost * 48);

  return (
    <div className="relative overflow-hidden rounded-xl border border-white/[0.09] bg-black p-3.5">
      <div className="flex items-start justify-between">
        <div>
          <span className="micro-sm text-white/30">{customLabel || "Score viral"}</span>
          <div className="mt-1.5 flex items-baseline gap-1.5">
            <span className="text-glow tnum text-[30px] font-light leading-none text-white">
              <Counter value={currentScore} format={(n) => String(Math.round(n))} />
            </span>
            <span className="text-[11px] text-white/30">/ 100</span>
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <IconFlame className={cn("h-3 w-3", color === "#10b981" ? "text-emerald-400" : "text-ember-400/80")} />
            <span className="text-[10px] text-white/55">{grade}</span>
          </div>
        </div>
        <svg viewBox="0 0 160 96" className="h-[86px] w-[142px]">
          <defs>
            <linearGradient id={`gg-${color.replace('#', '')}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={color} />
              <stop offset="100%" stopColor={color} />
            </linearGradient>
          </defs>
          <path d="M16 84 A64 64 0 1 1 144 84" fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="7" strokeLinecap="round" />
          <path
            d="M16 84 A64 64 0 1 1 144 84"
            fill="none"
            stroke={`url(#gg-${color.replace('#', '')})`}
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={L}
            strokeDashoffset={L * (1 - currentScore / 100)}
            style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.8,.2,1)" }}
          />
          {Array.from({ length: 11 }).map((_, i) => {
            const a = ((-90 + i * 18) * Math.PI) / 180;
            const r1 = 50;
            const r2 = i % 5 === 0 ? 43 : 47;
            return (
              <line
                key={i}
                x1={80 + Math.sin(a) * r1}
                y1={84 - Math.cos(a) * r1}
                x2={80 + Math.sin(a) * r2}
                y2={84 - Math.cos(a) * r2}
                stroke="rgba(255,255,255,0.16)"
                strokeWidth="1"
              />
            );
          })}
          <g style={{ transform: `rotate(${angle}deg)`, transformOrigin: "80px 84px", transition: "transform 900ms cubic-bezier(.2,.8,.2,1)" }}>
            <line x1="80" y1="84" x2="80" y2="34" stroke="#a9c2ff" strokeWidth="1.4" strokeLinecap="round" />
          </g>
          <circle cx="80" cy="84" r="3.4" fill="#0b0f18" stroke="#7ea3ff" strokeWidth="1.2" />
        </svg>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        {[
          { l: "Hook", v: hookVal, u: "%" },
          { l: "Retención", v: retVal, u: "%" },
          { l: "Rebote", v: bounceVal, u: "%" },
        ].map((k) => (
          <div key={k.l} className="rounded-lg border border-white/[0.05] bg-black/25 px-2 py-1.5">
            <div className="micro-sm text-white/25">{k.l}</div>
            <div className="tnum mt-1 text-[12px] font-light text-white/90">
              {Math.round(k.v)}
              <span className="text-[9px] text-white/30">{k.u}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- retention chart ---------- */
function RetentionChart() {
  const { boost, time, seek, applied } = useEditor();
  const [hover, setHover] = useState<number | null>(null);
  const n = BASE_RETENTION.length;
  const W = 300;
  const H = 104;

  const cur = useMemo(() => BASE_RETENTION.map((_, i) => retentionAt(i, boost)), [boost]);
  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => H - v * (H - 10) - 4;

  const line = cur.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${W},${H} L0,${H} Z`;
  const baseLine = BASE_RETENTION.map(
    (v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`,
  ).join(" ");

  const idx = hover ?? Math.round((time / 32) * (n - 1));
  const activeIdx = Math.max(0, Math.min(n - 1, idx));
  const t = (activeIdx / (n - 1)) * 32;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3 px-1">
        <span className="flex items-center gap-1">
          <span className="h-[2px] w-3 rounded-full bg-beam-300" />
          <span className="micro-sm text-white/35">Proyectada</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="h-[2px] w-3 rounded-full bg-white/20" />
          <span className="micro-sm text-white/25">Base</span>
        </span>
      </div>

      <div
        className="relative overflow-hidden rounded-xl border border-white/[0.08] bg-black p-2"
        onPointerMove={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setHover(Math.round(((e.clientX - r.left) / r.width) * (n - 1)));
        }}
        onPointerLeave={() => setHover(null)}
        onPointerDown={() => seek(t)}
      >
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="none">
          <defs>
            <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2f5cff" stopOpacity="0.42" />
              <stop offset="100%" stopColor="#2f5cff" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75].map((g) => (
            <line key={g} x1="0" y1={y(g)} x2={W} y2={y(g)} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
          ))}
          <path d={area} fill="url(#fill)" />
          <path d={baseLine} fill="none" stroke="rgba(255,255,255,0.16)" strokeWidth="1" strokeDasharray="3 3" />
          <path d={line} fill="none" stroke="#7ea3ff" strokeWidth="1.5" strokeLinecap="round" />
          {MOMENTS.map((m) => (
            <circle
              key={m.t}
              cx={x((m.t / 32) * (n - 1))}
              cy={y(retentionAt(Math.round((m.t / 32) * (n - 1)), boost))}
              r="2.6"
              fill={m.kind === "risk" ? "#ff7a59" : "#46e0c0"}
            />
          ))}
          <line
            x1={x((time / 32) * (n - 1))}
            y1="0"
            x2={x((time / 32) * (n - 1))}
            y2={H}
            stroke="#7ea3ff"
            strokeWidth="0.8"
            opacity="0.5"
          />
          <circle
            cx={x(activeIdx)}
            cy={y(cur[activeIdx])}
            r="3.4"
            fill="#0b0f18"
            stroke="#a9c2ff"
            strokeWidth="1.4"
          />
        </svg>
        <div className="mt-1 flex justify-between px-0.5">
          {["0s", "8s", "16s", "24s", "32s"].map((l) => (
            <span key={l} className="tnum text-[8.5px] text-white/20">
              {l}
            </span>
          ))}
        </div>
        <div className="pointer-events-none absolute right-2 top-2 rounded-md border border-white/10 bg-ink-950/85 px-2 py-1 text-right backdrop-blur-sm">
          <div className="tnum text-[13px] font-light leading-none text-white">
            {Math.round(cur[activeIdx] * 100)}%
          </div>
          <div className="micro-sm mt-1 text-white/30">{t.toFixed(1)}s</div>
        </div>
        <div className="pointer-events-none absolute bottom-6 left-2 flex items-center gap-1 rounded-md border border-signal-400/20 bg-signal-400/[0.07] px-1.5 py-0.5">
          <IconSparkle className="h-2.5 w-2.5 text-signal-400/80" />
          <span className="micro-sm text-signal-400/80">
            +{Math.round(boost * 100)} pts por IA ({applied.length})
          </span>
        </div>
      </div>
    </div>
  );
}

/* ---------- moments ---------- */
function Moments() {
  const { seek } = useEditor();
  const tone: Record<string, string> = {
    peak: "text-signal-400 border-signal-400/25",
    risk: "text-ember-400 border-ember-400/25",
    reveal: "text-beam-200 border-beam-400/25",
    cta: "text-white/70 border-white/12",
  };
  return (
    <div className="space-y-1.5">
      {MOMENTS.map((m) => (
        <button
          key={m.t}
          onClick={() => seek(m.t)}
          className="group flex w-full items-center gap-2.5 rounded-lg border border-white/[0.08] bg-black p-2 text-left transition-colors duration-200 hover:border-beam-400/40"
        >
          <span className={cn("tnum w-9 shrink-0 rounded-md border px-1 py-0.5 text-center text-[9.5px]", tone[m.kind])}>
            {m.t}s
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[11px] text-white/80">{m.label}</span>
            <span className="block truncate text-[9.5px] text-white/30">{m.note}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

/* ---------- audience + heatmap ---------- */
function Audience() {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="space-y-2">
        <SectionLabel>Audiencia</SectionLabel>
        {AUDIENCE.map((a) => (
          <div key={a.label} className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[9.5px] text-white/45">{a.label}</span>
              <span className="tnum text-[9px] text-white/30">{a.value}%</span>
            </div>
            <Meter value={a.value * 2} height={2} />
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <SectionLabel>Mejor hora</SectionLabel>
        <div className="space-y-[3px]">
          {HEATMAP.slice(0, 7).map((d) => (
            <div key={d.day} className="flex items-center gap-[3px]">
              <span className="micro-sm w-2.5 text-white/25">{d.day}</span>
              {d.slots.map((s, i) => (
                <span
                  key={i}
                  className="h-2.5 flex-1 rounded-[2px] transition-transform duration-300 hover:scale-125"
                  style={{
                    background: `rgba(47,92,255,${0.08 + (s / 100) * 0.72})`,
                  }}
                />
              ))}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-1.5 pt-1">
          <IconClock className="h-3 w-3 text-beam-200/60" />
          <span className="micro-sm text-white/35">Pico 21:00</span>
        </div>
      </div>
    </div>
  );
}

/* ---------- next best actions ---------- */
function NextActions() {
  const { applied, run, progress } = useEditor();
  const pending = AUTOMATIONS.filter((a) => !applied.includes(a.id))
    .sort((a, b) => b.score + b.reach - (a.score + a.reach))
    .slice(0, 3);

  if (!pending.length)
    return (
      <div className="flex items-center gap-2.5 rounded-xl border border-signal-400/20 bg-signal-400/[0.05] p-3">
        <IconCheck className="h-4 w-4 shrink-0 text-signal-400" />
        <div>
          <div className="text-[11px] text-white/85">Pipeline completo</div>
          <div className="micro-sm mt-1 text-white/30">Máster optimizado al máximo</div>
        </div>
      </div>
    );

  return (
    <div className="space-y-1.5">
      {pending.map((a, i) => {
        const p = progress[a.id];
        return (
          <div
            key={a.id}
            className={cn(
              "relative overflow-hidden rounded-lg border p-2.5",
              i === 0
                ? "border-beam-400/40 bg-black"
                : "border-white/[0.08] bg-black",
            )}
          >
            <div className="flex items-center gap-2.5">
              <span className="grid h-6 w-6 shrink-0 place-items-center rounded-lg border border-beam-400/25 bg-beam-500/10 text-[11px] text-beam-200">
                {a.glyph}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[11px] text-white/85">{a.name}</div>
                <div className="micro-sm mt-1 text-white/25">
                  +{a.score} score · +{a.reach} alcance
                </div>
              </div>
              <button
                onClick={() => run(a.id)}
                disabled={p !== undefined}
                className="shrink-0 rounded-md border border-beam-400 bg-beam-500 px-2.5 py-1.5 text-[10px] font-medium text-white transition-colors duration-200 hover:bg-beam-400 disabled:opacity-70"
              >
                {p !== undefined ? `${Math.round(p)}%` : "Aplicar"}
              </button>
            </div>
            {p !== undefined && (
              <div className="mt-2">
                <Meter value={p} height={2} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ---------- producer plan section ---------- */
function ProducerPlanSection() {
  const { producerPlan, setProducerPlan, createVideo, setRatio, flash } = useEditor();
  if (!producerPlan) return null;

  const [selectedFormat, setSelectedFormat] = useState<"reel" | "long">(
    producerPlan.recommended_format || "long",
  );
  const [selectedDuration, setSelectedDuration] = useState<number>(
    producerPlan.recommended_duration_sec || (producerPlan.recommended_format === "reel" ? 60 : 300),
  );

  useEffect(() => {
    if (producerPlan) {
      setSelectedFormat(producerPlan.recommended_format || "long");
      setSelectedDuration(
        producerPlan.recommended_duration_sec ||
          (producerPlan.recommended_format === "reel" ? 60 : 300),
      );
    }
  }, [producerPlan]);

  const handleApply = (autoCreate: boolean = true) => {
    const isReel = selectedFormat === "reel";
    setRatio(isReel ? "9:16" : "16:9");
    const dur = selectedDuration;
    const durLabel = dur >= 60 ? `${Math.round(dur / 60)}m` : `${dur}s`;

    if (autoCreate) {
      createVideo(producerPlan.polished_prompt, {
        duration: dur,
        style: isReel ? "shorts" : "divulgacion",
        aspect_ratio: isReel ? "9:16" : "16:9",
      });
      flash(`Creando video ${isReel ? "Reel 9:16" : "16:9"} (${durLabel}) con datos reales...`);
    }
  };

  const durDisplay = selectedDuration >= 60 ? `${Math.round(selectedDuration / 60)}m` : `${selectedDuration}s`;

  return (
    <div className="space-y-3 pb-6 animate-in fade-in duration-300">
      {/* Indicador de Aprendizaje del Canal */}
      {producerPlan.channel_learning_applied && (
        <div className="rounded-xl border border-beam-400/30 bg-beam-500/10 p-3 text-[11px] space-y-1.5">
          <div className="flex items-center gap-1.5 text-beam-200 font-medium">
            <IconSparkle className="h-3.5 w-3.5" />
            <span>Fórmula Ganadora del Canal: {producerPlan.channel_name || "Activo"}</span>
          </div>
          <div className="text-[10px] text-white/70 leading-relaxed">
            Estructura optimizada: <span className="text-white font-medium">{producerPlan.chosen_structure}</span> con gancho inicial estilo <span className="text-white font-medium">{producerPlan.chosen_hook_type}</span>.
          </div>
        </div>
      )}

      {/* 1. Medidor de retención auditada */}
      <Collapsible title="Retención Auditada" defaultOpen={true}>
        <ScoreGauge
          overrideScore={producerPlan.retention_score}
          customLabel="Retención estimada"
          customGrade="Élite · Retención > 70%"
          color="#2f5cff"
        />
        {/* Metadatos rápidos */}
        <div className="mt-2 grid grid-cols-2 gap-2 text-[10px]">
          <div className="rounded-lg border border-white/[0.08] bg-black p-2">
            <span className="micro-sm text-white/35">Formato sugerido</span>
            <div className="mt-1 font-semibold text-white/90">
              {producerPlan.recommended_format === "reel" ? "Reel 9:16 vertical" : "Documental 16:9"}
            </div>
          </div>
          <div className="rounded-lg border border-white/[0.08] bg-black p-2">
            <span className="micro-sm text-white/35">Duración sugerida</span>
            <div className="mt-1 font-semibold text-white/90">
              {producerPlan.recommended_duration_sec} segundos
            </div>
          </div>
        </div>
      </Collapsible>

      {/* 2. Gancho 3 Segundos */}
      <Collapsible title="Gancho Inicial (3s)" defaultOpen={true}>
        <div className="rounded-xl border border-white/[0.08] bg-black/50 p-3">
          <div className="micro-sm text-white/35 mb-1.5 flex items-center gap-1.5">
            <span className="h-1 w-1 rounded-full bg-beam-300" />
            <span>Gancho de apertura</span>
          </div>
          <p className="text-[11px] font-normal italic text-white/90 leading-relaxed">
            "{producerPlan.master_hook}"
          </p>
        </div>
      </Collapsible>

      {/* 3. AJUSTE PERSONALIZADO DE FORMATO Y DURACIÓN ANTES DE CREAR */}
      <div className="rounded-xl border border-white/[0.1] bg-white/[0.02] p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-[10.5px] font-semibold text-white/80 uppercase tracking-wider">
            Ajustar Formato y Tiempo
          </span>
          <span className="font-mono text-[10px] text-beam-300 bg-beam-500/15 border border-beam-400/25 px-1.5 py-0.5 rounded">
            {selectedFormat === "reel" ? "Reel 9:16" : "Largo 16:9"} · {durDisplay}
          </span>
        </div>

        {/* Switch Formato */}
        <div className="grid grid-cols-2 gap-1 rounded-lg border border-white/[0.08] bg-white/[0.02] p-0.5">
          <button
            type="button"
            onClick={() => {
              setSelectedFormat("reel");
              if (selectedDuration > 180) setSelectedDuration(60);
            }}
            className={cn(
              "py-1 text-[10px] font-medium rounded-md transition-all text-center cursor-pointer",
              selectedFormat === "reel"
                ? "bg-beam-500/20 text-beam-200 border border-beam-400/35 shadow-sm"
                : "text-white/45 hover:text-white",
            )}
          >
            Reel 9:16 (Short)
          </button>
          <button
            type="button"
            onClick={() => {
              setSelectedFormat("long");
              if (selectedDuration < 120) setSelectedDuration(480);
            }}
            className={cn(
              "py-1 text-[10px] font-medium rounded-md transition-all text-center cursor-pointer",
              selectedFormat === "long"
                ? "bg-beam-500/20 text-beam-200 border border-beam-400/35 shadow-sm"
                : "text-white/45 hover:text-white",
            )}
          >
            Largo 16:9 (Docu)
          </button>
        </div>

        {/* Presets Rápidos de Tiempo */}
        <div className="flex items-center gap-1.5">
          <span className="text-[9px] text-white/35 shrink-0">Tiempo:</span>
          {selectedFormat === "reel" ? (
            <div className="flex items-center gap-1 flex-1">
              {[30, 45, 60, 90].map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setSelectedDuration(s)}
                  className={cn(
                    "flex-1 py-0.5 rounded text-[9.5px] font-mono transition-all text-center cursor-pointer border",
                    selectedDuration === s
                      ? "border-beam-400/40 bg-beam-500/20 text-beam-200 font-semibold"
                      : "border-white/[0.06] bg-white/[0.015] text-white/45 hover:text-white/80",
                  )}
                >
                  {s}s
                </button>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-1 flex-1">
              {[
                { label: "3m", sec: 180 },
                { label: "5m", sec: 300 },
                { label: "8m", sec: 480 },
                { label: "10m", sec: 600 },
                { label: "15m", sec: 900 },
              ].map((item) => (
                <button
                  key={item.sec}
                  type="button"
                  onClick={() => setSelectedDuration(item.sec)}
                  className={cn(
                    "flex-1 py-0.5 rounded text-[9.5px] font-mono transition-all text-center cursor-pointer border",
                    selectedDuration === item.sec
                      ? "border-beam-400/40 bg-beam-500/20 text-beam-200 font-semibold"
                      : "border-white/[0.06] bg-white/[0.015] text-white/45 hover:text-white/80",
                  )}
                >
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 4. Barra de Acciones del Productor */}
      <div className="pt-1 flex flex-col gap-2">
        <button
          type="button"
          onClick={() => handleApply(true)}
          className="w-full flex items-center justify-center gap-2 rounded-xl border border-beam-400/40 bg-gradient-to-r from-beam-600 to-indigo-600 hover:from-beam-500 hover:to-indigo-500 py-2.5 text-[11px] font-semibold text-white shadow-[0_0_20px_rgba(79,123,255,0.35)] transition-all active:scale-98 cursor-pointer"
        >
          <IconSparkle className="h-3.5 w-3.5 text-white" />
          <span>Crear video ({selectedFormat === "reel" ? "Reel 9:16" : "16:9"} · {durDisplay})</span>
        </button>
        <button
          type="button"
          onClick={() => setProducerPlan(null)}
          className="w-full rounded-lg border border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.06] py-1 text-[10px] font-medium text-white/45 hover:text-white/80 transition-all text-center cursor-pointer"
        >
          Cerrar auditoría
        </button>
      </div>

      {/* 5. Diagnóstico & Estrategia Anti-Abandono */}
      <Collapsible title="Diagnóstico de Retención" defaultOpen={false}>
        <div className="rounded-xl border border-white/[0.08] bg-black/60 p-3 text-[10.5px] leading-relaxed text-white/70">
          <p>{producerPlan.original_critique}</p>
        </div>
      </Collapsible>

      {/* 6. 3 Datos Avalados por la Web */}
      <Collapsible title={`Datos Avalados (${producerPlan.supporting_facts?.length || 0})`} defaultOpen={false}>
        <div className="space-y-2">
          {producerPlan.supporting_facts?.map((f, idx) => (
            <div key={idx} className="rounded-xl border border-white/[0.08] bg-black p-2.5 text-[10.5px] leading-relaxed">
              <div className="text-white/85">{f.fact}</div>
              <div className="mt-1.5 flex items-center gap-1 text-[9px] text-cyan-300/80 font-mono">
                <span className="text-white/30">Fuente:</span>
                <span className="truncate">{f.source_tag}</span>
              </div>
            </div>
          ))}
        </div>
      </Collapsible>

      {/* 7. Dirección Artística */}
      <Collapsible title="Dirección de Arte y Música" defaultOpen={false}>
        <div className="space-y-2 text-[10px]">
          <div className="rounded-xl border border-white/[0.08] bg-black p-2.5">
            <div className="micro-sm text-white/35 mb-1">Atmósfera Visual</div>
            <div className="text-white/70 leading-relaxed">{producerPlan.visual_atmosphere}</div>
          </div>
          <div className="rounded-xl border border-white/[0.08] bg-black p-2.5">
            <div className="micro-sm text-white/35 mb-1">Música Recomendada</div>
            <div className="text-white/70 leading-relaxed">{producerPlan.recommended_bgm}</div>
          </div>
        </div>
      </Collapsible>

      {/* 8. Guión Maestro Pulido */}
      <Collapsible title="Guión Maestro Pulido" defaultOpen={false}>
        <div className="rounded-xl border border-white/[0.08] bg-black p-3 text-[10.5px] text-white/80 leading-relaxed font-mono">
          {producerPlan.polished_prompt}
        </div>
      </Collapsible>
    </div>
  );
}

/* ---------- inspector contextual ---------- */
function InspectorSection({ onGoToAnalytics }: { onGoToAnalytics: () => void }) {
  const {
    clips,
    selected,
    updateClip,
    removeClip,
    duplicateClip,
    splitClipAtPlayhead,
    seek,
    duration,
    activeProjectTitle,
    ratio,
    fitMode,
    toggleFitMode,
    subtitleStyle,
  } = useEditor();

  const selectedClip = useMemo(() => clips.find((c) => c.id === selected), [clips, selected]);

  if (!selectedClip) {
    const v1Count = clips.filter((c) => c.track === "v1").length;
    const v2Count = clips.filter((c) => c.track === "v2").length;
    const txCount = clips.filter((c) => c.track === "t1").length;
    const a1Count = clips.filter((c) => c.track === "a1").length;

    return (
      <div className="space-y-4">
        {/* Cabecera Master */}
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-3.5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-white/50">
              Video Master
            </span>
            <span className="rounded-full bg-beam-500/10 border border-beam-400/20 px-2 py-0.5 text-[9px] font-mono text-beam-300">
              24 fps
            </span>
          </div>

          <div>
            <h4 className="text-[12.5px] font-medium text-white/95 truncate" title={activeProjectTitle || "Proyecto de video KAI"}>
              {activeProjectTitle || "Proyecto de video KAI"}
            </h4>
            <div className="flex items-center gap-2 mt-1 text-[10px] text-white/40">
              <span>Formato {ratio}</span>
              <span>•</span>
              <span>Duración {Math.round(duration || 32)}s</span>
              <span>•</span>
              <span>{clips.length} clips</span>
            </div>
          </div>

          {/* Desglose de pistas */}
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/[0.06]">
            <div className="rounded-xl border border-white/[0.06] bg-black/40 p-2 flex items-center justify-between">
              <span className="text-[10px] text-white/40">Video (V1)</span>
              <span className="text-[11px] font-mono font-medium text-white/80">{v1Count}</span>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-black/40 p-2 flex items-center justify-between">
              <span className="text-[10px] text-white/40">B-Roll (V2)</span>
              <span className="text-[11px] font-mono font-medium text-beam-300">{v2Count}</span>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-black/40 p-2 flex items-center justify-between">
              <span className="text-[10px] text-white/40">Subtítulos (TX)</span>
              <span className="text-[11px] font-mono font-medium text-emerald-300">{txCount}</span>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-black/40 p-2 flex items-center justify-between">
              <span className="text-[10px] text-white/40">Audio (A1)</span>
              <span className="text-[11px] font-mono font-medium text-amber-300">{a1Count}</span>
            </div>
          </div>
        </div>

        {/* Llamada a la acción contextual */}
        <div className="rounded-2xl border border-dashed border-white/15 bg-white/[0.015] p-5 text-center space-y-2.5">
          <div className="h-8 w-8 mx-auto grid place-items-center rounded-xl bg-white/[0.04] border border-white/10 text-white/40">
            <IconScissors className="h-4 w-4" />
          </div>
          <div>
            <p className="text-[11.5px] font-medium text-white/80">Propiedades del elemento</p>
            <p className="text-[10px] text-white/40 mt-1 leading-relaxed max-w-[240px] mx-auto">
              Haz clic en cualquier clip de la línea de tiempo para ajustar duración, recorte, pista, volumen o subtítulos.
            </p>
          </div>
          <button
            type="button"
            onClick={onGoToAnalytics}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 bg-white/[0.05] text-[10.5px] font-medium text-white/70 hover:text-white hover:bg-white/[0.1] transition-all cursor-pointer"
          >
            <span>Ver Canales y Analítica</span>
            <span>→</span>
          </button>
        </div>
      </div>
    );
  }

  // Cuando HAY un clip seleccionado: Inspector completo
  const kindLabels: Record<string, { name: string; color: string; border: string; bg: string }> = {
    v2: { name: "B-ROLL · APOYO", color: "text-beam-300", border: "border-beam-400/30", bg: "bg-beam-500/10" },
    v1: { name: "VIDEO PRINCIPAL", color: "text-white/80", border: "border-white/20", bg: "bg-white/[0.06]" },
    t1: { name: "SUBTÍTULOS Y TEXTO", color: "text-emerald-300", border: "border-emerald-400/30", bg: "bg-emerald-500/10" },
    a1: { name: "AUDIO Y LOCUCIÓN", color: "text-amber-300", border: "border-amber-400/30", bg: "bg-amber-500/10" },
  };

  const badge = kindLabels[selectedClip.track] || {
    name: selectedClip.kind.toUpperCase(),
    color: "text-white/70",
    border: "border-white/10",
    bg: "bg-white/[0.04]",
  };

  const startSec = Math.round(selectedClip.start * 100) / 100;
  const durSec = Math.round(selectedClip.duration * 100) / 100;
  const endSec = Math.round((startSec + durSec) * 100) / 100;

  return (
    <div className="space-y-3.5 select-none">
      {/* Cabecera del Inspector */}
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-2.5">
        <div className="flex items-center justify-between">
          <span className={cn("rounded-md border px-2 py-0.5 text-[9px] font-semibold tracking-wider", badge.border, badge.bg, badge.color)}>
            {badge.name}
          </span>
          <span className="text-[9.5px] font-mono text-white/30 truncate max-w-[120px]">
            #{selectedClip.id}
          </span>
        </div>

        {/* Acciones principales en grupo estilizado */}
        <div className="flex items-center justify-between pt-1 border-t border-white/[0.06]">
          <button
            type="button"
            onClick={() => seek(selectedClip.start)}
            className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] text-white/60 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer"
            title="Mover cabezal al inicio de este clip"
          >
            <IconPlay className="h-2.5 w-2.5" />
            <span>Ir al inicio</span>
          </button>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => duplicateClip(selectedClip.id)}
              className="p-1.5 rounded-md text-white/40 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer"
              title="Duplicar clip"
            >
              <IconCopy className="h-3 w-3" />
            </button>
            <button
              type="button"
              onClick={() => splitClipAtPlayhead()}
              className="p-1.5 rounded-md text-white/40 hover:text-white hover:bg-white/[0.06] transition-all cursor-pointer"
              title="Dividir clip en el cabezal"
            >
              <IconScissors className="h-3 w-3" />
            </button>
            <button
              type="button"
              onClick={() => removeClip(selectedClip.id)}
              className="p-1.5 rounded-md text-white/40 hover:text-rose-400 hover:bg-rose-500/10 transition-all cursor-pointer"
              title="Eliminar clip (Supr)"
            >
              <IconTrash className="h-3 w-3" />
            </button>
          </div>
        </div>
      </div>

      {/* 1. Nombre / Etiqueta del clip */}
      <div className="space-y-1.5">
        <label className="text-[10px] font-medium text-white/40 uppercase tracking-wider block">
          Nombre de la pista
        </label>
        <input
          type="text"
          value={selectedClip.label}
          onChange={(e) => updateClip(selectedClip.id, { label: e.target.value })}
          className="w-full rounded-xl border border-white/[0.09] bg-white/[0.02] px-3 py-1.5 text-[11.5px] text-white/90 outline-none focus:border-beam-400/50 focus:bg-black transition-all"
          placeholder="Nombre del clip..."
        />
      </div>

      {/* 2. Pista Asignada */}
      <div className="space-y-1.5">
        <label className="text-[10px] font-medium text-white/40 uppercase tracking-wider block">
          Pista de la línea de tiempo
        </label>
        <div className="grid grid-cols-4 gap-1 p-0.5 rounded-xl border border-white/[0.08] bg-white/[0.02]">
          {[
            { id: "v2", label: "V2 B-Roll" },
            { id: "v1", label: "V1 Video" },
            { id: "t1", label: "TX Texto" },
            { id: "a1", label: "A1 Audio" },
          ].map((trk) => {
            const isTrk = selectedClip.track === trk.id;
            return (
              <button
                key={trk.id}
                type="button"
                onClick={() => {
                  const kindMap: Record<string, any> = { v2: "broll", v1: "scene", t1: "caption", a1: "voice" };
                  updateClip(selectedClip.id, { track: trk.id as any, kind: kindMap[trk.id] });
                }}
                className={cn(
                  "py-1 rounded-lg text-[9.5px] font-medium transition-all text-center cursor-pointer",
                  isTrk
                    ? "bg-white/[0.12] text-white font-semibold shadow-sm"
                    : "text-white/40 hover:text-white/80 hover:bg-white/[0.03]",
                )}
              >
                {trk.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Tiempos y Recorte (Inicio, Duración, Fin) */}
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-3">
        <span className="text-[10px] font-medium text-white/40 uppercase tracking-wider block">
          Tiempos y Recorte (Segundos)
        </span>

        {/* Inicio */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-white/60">Tiempo de inicio</span>
          <div className="flex items-center rounded-lg border border-white/[0.08] bg-white/[0.03] p-0.5">
            <button
              type="button"
              onClick={() => updateClip(selectedClip.id, { start: Math.max(0, startSec - 0.5) })}
              className="h-6 w-6 grid place-items-center text-[12px] font-bold text-white/40 hover:text-white transition-colors cursor-pointer"
            >
              −
            </button>
            <input
              type="number"
              step="0.1"
              min="0"
              value={startSec}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val)) updateClip(selectedClip.id, { start: Math.max(0, val) });
              }}
              className="w-12 text-center bg-transparent border-0 p-0 text-[11px] font-mono text-white focus:outline-none"
            />
            <button
              type="button"
              onClick={() => updateClip(selectedClip.id, { start: startSec + 0.5 })}
              className="h-6 w-6 grid place-items-center text-[12px] font-bold text-white/40 hover:text-white transition-colors cursor-pointer"
            >
              +
            </button>
          </div>
        </div>

        {/* Duración */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-white/60">Duración</span>
          <div className="flex items-center rounded-lg border border-white/[0.08] bg-white/[0.03] p-0.5">
            <button
              type="button"
              onClick={() => updateClip(selectedClip.id, { duration: Math.max(0.5, durSec - 0.5) })}
              className="h-6 w-6 grid place-items-center text-[12px] font-bold text-white/40 hover:text-white transition-colors cursor-pointer"
            >
              −
            </button>
            <input
              type="number"
              step="0.1"
              min="0.5"
              value={durSec}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                if (!isNaN(val)) updateClip(selectedClip.id, { duration: Math.max(0.5, val) });
              }}
              className="w-12 text-center bg-transparent border-0 p-0 text-[11px] font-mono text-white focus:outline-none"
            />
            <button
              type="button"
              onClick={() => updateClip(selectedClip.id, { duration: durSec + 0.5 })}
              className="h-6 w-6 grid place-items-center text-[12px] font-bold text-white/40 hover:text-white transition-colors cursor-pointer"
            >
              +
            </button>
          </div>
        </div>

        {/* Fin calculado */}
        <div className="flex items-center justify-between pt-1 border-t border-white/[0.06] text-[10.5px]">
          <span className="text-white/40">Punto final en línea de tiempo</span>
          <span className="font-mono text-white/70">{endSec}s</span>
        </div>
      </div>

      {/* 4. Propiedades contextuales por tipo */}
      {selectedClip.track === "t1" || selectedClip.kind === "caption" ? (
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-medium text-white/40 uppercase tracking-wider">
              Texto del Subtítulo
            </span>
            <span className="text-[9px] text-beam-300">Kinetic</span>
          </div>
          <textarea
            rows={2}
            value={selectedClip.label}
            onChange={(e) => updateClip(selectedClip.id, { label: e.target.value })}
            className="w-full rounded-xl border border-white/[0.08] bg-black/60 p-2 text-[11px] text-white/90 outline-none focus:border-beam-400/50 resize-none"
            placeholder="Escribe el texto del subtítulo..."
          />
          <div className="flex items-center justify-between text-[10px] text-white/40 pt-1">
            <span>Estilo activo:</span>
            <span className="text-white/70 capitalize font-medium">{subtitleStyle || "Kinetic Bold"}</span>
          </div>
        </div>
      ) : selectedClip.track === "a1" || selectedClip.kind === "voice" || selectedClip.kind === "music" ? (
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-medium text-white/40 uppercase tracking-wider">
              Control de Audio
            </span>
            <span className="text-[9px] text-amber-300">Ducking -9dB</span>
          </div>
          <div className="space-y-1">
            <div className="flex justify-between text-[10px] text-white/50">
              <span>Ganancia / Volumen</span>
              <span className="font-mono text-white/80">100%</span>
            </div>
            <input
              type="range"
              min="0"
              max="150"
              defaultValue="100"
              className="w-full accent-beam-400 h-1 bg-white/10 rounded-lg cursor-pointer"
            />
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-2.5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-medium text-white/40 uppercase tracking-wider">
              Ajuste Visual
            </span>
            <span className="text-[9px] text-beam-300">4K HDR</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-white/60">Encuadre</span>
            <button
              type="button"
              onClick={toggleFitMode}
              className="px-2 py-1 rounded-lg border border-white/10 bg-white/[0.03] text-[10px] font-medium text-white/80 hover:text-white transition-colors"
            >
              {fitMode === "cover" ? "Cover (Llenar pantalla)" : "Contain (Ajustar)"}
            </button>
          </div>
        </div>
      )}

      {/* Bloqueo del clip */}
      <div className="flex items-center justify-between p-2.5 rounded-xl border border-white/[0.06] bg-white/[0.015]">
        <div className="flex items-center gap-2">
          <IconLock className="h-3.5 w-3.5 text-white/40" />
          <span className="text-[11px] text-white/70">Bloquear clip</span>
        </div>
        <button
          type="button"
          onClick={() => updateClip(selectedClip.id, { locked: !selectedClip.locked })}
          className={cn(
            "px-2 py-0.5 rounded text-[10px] font-medium transition-all cursor-pointer",
            selectedClip.locked
              ? "bg-amber-500/20 text-amber-200 border border-amber-400/30"
              : "bg-white/[0.05] text-white/40 hover:text-white border border-white/10",
          )}
        >
          {selectedClip.locked ? "Bloqueado" : "Desbloqueado"}
        </button>
      </div>
    </div>
  );
}

/* ---------- panel ---------- */
export function MetricsPanel() {
  const {
    metrics,
    platform,
    applied,
    running,
    theaterMode,
    setTheaterMode,
    producerPlan,
    metricsPanelCollapsed,
    setMetricsPanelCollapsed,
    activeChannelId,
    setActiveChannelId,
    selected,
    flash,
  } = useEditor();
  const isHidden = metricsPanelCollapsed || theaterMode;
  const pf = PLATFORMS.find((p) => p.id === platform)!;
  const [activeTab, setActiveTab] = useState<"inspector" | "analytics" | "producer">("inspector");

  const [overview, setOverview] = useState<MetricsOverviewData | null>(null);
  const [fbCorrelations, setFbCorrelations] = useState<Record<string, any>>({});
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [selectedChannelId, setSelectedChannelId] = useState<string>(activeChannelId || "UC_8-TffWIAoiUMMDfiMUm2Q");

  // Al seleccionar un elemento en la línea de tiempo, el panel muestra automáticamente sus propiedades contextuales
  useEffect(() => {
    if (selected) {
      setActiveTab("inspector");
    }
  }, [selected]);

  useEffect(() => {
    if (activeChannelId) setSelectedChannelId(activeChannelId);
  }, [activeChannelId]);

  const loadOverview = useCallback(async () => {
    try {
      const res = await fetch("/api/metrics/overview");
      if (res.ok) {
        const data = await res.json();
        setOverview(data);
      }
      fetch("/api/facebook/correlations")
        .then((r) => r.json())
        .then((data) => setFbCorrelations(data))
        .catch(() => {});
    } catch (e) {
      console.warn("No se pudo cargar métricas generales:", e);
    }
  }, []);

  useEffect(() => {
    loadOverview();
  }, [loadOverview]);

  const handleSyncYouTube = async () => {
    try {
      setIsSyncing(true);
      flash("Conectando con YouTube Data API v3...");
      const res = await fetch("/api/metrics/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel_id: selectedChannelId }),
      });
      const data = await res.json();
      if (data.success) {
        flash(`¡Métricas sincronizadas en vivo! ${data.synced_videos_count} videos actualizados.`);
        await loadOverview();
      } else {
        flash("Sincronización finalizada sin cambios nuevos.");
      }
    } catch (err: any) {
      flash(`Error al sincronizar con YouTube: ${err.message}`);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleSelectChannel = (cid: string) => {
    setSelectedChannelId(cid);
    setActiveChannelId(cid);
  };

  useEffect(() => {
    if (producerPlan) {
      setActiveTab("producer");
      setMetricsPanelCollapsed(false);
    }
  }, [producerPlan, setMetricsPanelCollapsed]);

  const currentChannel = overview?.channels?.find((c) => c.channel_id === selectedChannelId) 
    || overview?.channels?.[0];

  const channelVideos = useMemo(() => {
    if (!overview?.recent_videos) return [];
    if (!currentChannel) return overview.recent_videos;
    return overview.recent_videos.filter((v) => v.channel_id === currentChannel.channel_id);
  }, [overview, currentChannel]);

  const totalViews = channelVideos.reduce((acc, v) => acc + (v.metrics?.views || 0), 0);
  const totalLikes = channelVideos.reduce((acc, v) => acc + (v.metrics?.likes || 0), 0);
  const totalComments = channelVideos.reduce((acc, v) => acc + (v.metrics?.comments || 0), 0);

  if (isHidden) {
    return (
      <aside className="hidden h-full min-h-0 w-11 shrink-0 flex-col items-center border-l border-white/[0.08] bg-black py-3 xl:flex">
        <button
          type="button"
          onClick={() => {
            setMetricsPanelCollapsed(false);
            if (theaterMode) setTheaterMode(false);
          }}
          title="Mostrar inspector y analítica"
          className="grid h-8 w-8 place-items-center rounded-lg border border-white/[0.09] text-white/60 transition-colors hover:border-beam-400/50 hover:text-beam-200 cursor-pointer"
        >
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </button>
        <span className="micro-sm mt-4 text-white/35 [writing-mode:vertical-rl]">
          {selected ? "Inspector activo" : "Propiedades y analítica"}
        </span>
      </aside>
    );
  }

  return (
    <aside className="hidden h-full min-h-0 w-[340px] shrink-0 flex-col border-l border-white/[0.08] bg-black xl:flex">
      <div className="flex items-center justify-between px-3.5 pb-2.5 pt-3.5 shrink-0 border-b border-white/[0.06]">
        {/* Pestañas de alternancia superior: Inspector vs Publicación y analítica */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setActiveTab("inspector")}
            className={cn(
              "px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all cursor-pointer flex items-center gap-1.5",
              activeTab === "inspector"
                ? "bg-white/[0.10] text-white border border-white/15"
                : "text-white/40 hover:text-white hover:bg-white/[0.04]",
            )}
          >
            <span>Inspector</span>
            {selected && (
              <span className="h-1.5 w-1.5 rounded-full bg-beam-400 animate-pulse" />
            )}
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("analytics")}
            className={cn(
              "px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all cursor-pointer",
              activeTab === "analytics"
                ? "bg-white/[0.10] text-white border border-white/15"
                : "text-white/40 hover:text-white hover:bg-white/[0.04]",
            )}
          >
            Publicación y analítica
          </button>

          {producerPlan && (
            <button
              type="button"
              onClick={() => setActiveTab("producer")}
              className={cn(
                "px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all flex items-center gap-1.5 cursor-pointer",
                activeTab === "producer"
                  ? "bg-white/[0.10] text-white border border-white/15"
                  : "text-white/40 hover:text-white hover:bg-white/[0.04]",
              )}
            >
              <span>Auditoría IA</span>
              <span className="tnum text-[9px] px-1 py-0.2 rounded bg-white/[0.08] text-white/70 border border-white/10">
                {producerPlan.retention_score}
              </span>
            </button>
          )}
        </div>

        <div className="flex items-center gap-2">
          {activeTab === "analytics" && (
            <div className="flex items-center gap-1.5 rounded-full border border-white/[0.1] bg-black px-2 py-0.5">
              <span
                className={cn(
                  "h-1 w-1 rounded-full",
                  isSyncing ? "bg-beam-300 anim-ping" : (running ? "bg-beam-300 anim-ping" : "bg-signal-400"),
                )}
              />
              <span className="micro-sm text-white/45">
                {isSyncing ? "Sincronizando..." : (running ? "Recalculando" : "YouTube en vivo")}
              </span>
            </div>
          )}
          <button
            type="button"
            onClick={() => setMetricsPanelCollapsed(true)}
            title="Ocultar panel"
            className="grid h-7 w-7 place-items-center rounded-lg border border-white/[0.09] text-white/50 transition-colors hover:border-beam-400/50 hover:text-beam-200 cursor-pointer"
          >
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 6l6 6-6 6" />
            </svg>
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3.5 pb-10 pt-3 space-y-3 subtle-scrollbar overscroll-contain">
        {activeTab === "inspector" ? (
          <InspectorSection onGoToAnalytics={() => setActiveTab("analytics")} />
        ) : activeTab === "producer" && producerPlan ? (
          <ProducerPlanSection />
        ) : (
          <>
            {/* 1. Selector de Canal Conectado & Botón Sincronizar en Vivo */}
            <div className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-3 space-y-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-signal-400 animate-pulse" />
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-white/50">Canal Conectado</span>
                </div>
                <button
                  type="button"
                  onClick={handleSyncYouTube}
                  disabled={isSyncing}
                  className="flex items-center gap-1.5 h-6 px-2 rounded-lg text-[9.5px] font-medium border border-white/10 bg-white/[0.03] text-white/70 hover:text-white hover:bg-white/[0.08] hover:border-white/20 transition-all cursor-pointer disabled:opacity-50"
                  title="Sincronizar métricas en tiempo real con YouTube Data API"
                >
                  <IconRefresh className={cn("h-3 w-3 text-beam-300", isSyncing && "animate-spin")} />
                  <span>{isSyncing ? "Sincronizando..." : "Sincronizar"}</span>
                </button>
              </div>

              {/* Bento Switcher de Canales YouTube */}
              <div className="grid grid-cols-2 gap-2">
                {[
                  {
                    id: "UC_8-TffWIAoiUMMDfiMUm2Q",
                    title: "the Deep dife",
                    tag: "Historia & Ciencia",
                  },
                  {
                    id: "UChQZ2TvHifQBrDzbZRjGDkA",
                    title: "PixelGrama",
                    tag: "Tecnología & IA",
                  },
                ].map((c) => {
                  const isSelected = (currentChannel?.channel_id || selectedChannelId) === c.id;
                  return (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => handleSelectChannel(c.id)}
                      className={cn(
                        "group relative flex flex-col justify-between p-2.5 rounded-xl border transition-all cursor-pointer text-left select-none",
                        isSelected
                          ? "border-beam-400/50 bg-gradient-to-b from-beam-500/[0.16] to-beam-500/[0.05] shadow-[0_0_20px_rgba(37,99,235,0.15)] ring-1 ring-beam-400/20"
                          : "border-white/[0.06] bg-white/[0.015] hover:bg-white/[0.04] hover:border-white/15",
                      )}
                    >
                      <div className="flex items-center justify-between w-full mb-1">
                        <div className="flex items-center gap-1.5">
                          <IconYouTube className="w-3.5 h-3.5 text-red-500" />
                          <span className="text-[9px] font-mono text-white/40 uppercase">YT</span>
                        </div>
                        {isSelected ? (
                          <div className="flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-beam-400 shadow-[0_0_8px_rgba(59,130,246,0.9)]" />
                            <span className="text-[8.5px] font-mono font-semibold text-beam-200">Activo</span>
                          </div>
                        ) : (
                          <span className="text-[8.5px] font-mono text-white/25 group-hover:text-white/50">Cambiar</span>
                        )}
                      </div>
                      <div className="min-w-0">
                        <span className={cn("text-xs font-semibold tracking-tight truncate block", isSelected ? "text-white" : "text-white/75 group-hover:text-white")}>
                          {c.title}
                        </span>
                        <span className="text-[9px] text-white/40 truncate block mt-0.5">
                          {c.tag}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Tarjeta Página Hermana Facebook */}
              {(() => {
                const activeCid = currentChannel?.channel_id || selectedChannelId;
                const fb = fbCorrelations[activeCid]?.facebook_page;
                if (!fb || !fb.enabled) return null;
                return (
                  <div className="rounded-xl border border-white/[0.07] bg-white/[0.015] p-2.5 flex items-center justify-between transition-all hover:bg-white/[0.03] hover:border-white/12">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-400/25 flex items-center justify-center shrink-0 text-blue-400">
                        <IconFacebook className="w-3.5 h-3.5" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[9px] uppercase tracking-wider font-semibold text-white/40 font-mono">
                            Página Facebook
                          </span>
                        </div>
                        <p className="text-xs font-semibold text-white truncate mt-0.5">
                          {fb.page_name}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-signal-400/10 border border-signal-400/25 text-signal-400 text-[9.5px] font-medium font-mono shrink-0">
                      <span className="h-1.5 w-1.5 rounded-full bg-signal-400 anim-ping" />
                      <span>Auto Reels</span>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* 2. Puntuación Real del Canal */}
            <Collapsible title="Puntuación del Canal" defaultOpen={true}>
              <ScoreGauge
                overrideScore={currentChannel?.avg_viral_score || 74}
                customLabel={currentChannel ? `Score Canal · ${currentChannel.channel_title}` : "Score viral"}
                customGrade={currentChannel ? `${currentChannel.avg_retention_pct}% Retención Promedio` : undefined}
                customRetention={currentChannel?.avg_retention_pct || 75.7}
                customHook={currentChannel?.best_hook?.avg_retention_pct || 83.4}
                customBounce={24}
              />
            </Collapsible>

            {/* 3. Métricas Reales Sincronizadas */}
            <Collapsible title="Métricas Reales de YouTube" defaultOpen={true}>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { l: "Visualizaciones", v: totalViews || metrics.views, f: compact, g: <IconEye className="h-3 w-3" /> },
                  { l: "Me gusta (Likes)", v: totalLikes, f: compact, g: <IconFlame className="h-3 w-3" /> },
                  { l: "Comentarios", v: totalComments, f: compact, g: <IconComment className="h-3 w-3" /> },
                  { l: "Videos en Canal", v: channelVideos.length || 3, f: (n: number) => String(n), g: <IconChart className="h-3 w-3" /> },
                  { l: "CTR Portada Est.", v: 14.8, f: (n: number) => `${n.toFixed(1)}%`, g: <IconSend className="h-3 w-3" /> },
                  { l: "Retención Promedio", v: currentChannel?.avg_retention_pct || 75.7, f: (n: number) => `${n.toFixed(0)}%`, g: <IconBookmark className="h-3 w-3" /> },
                ].map((s) => (
                  <div key={s.l} className="group relative overflow-hidden rounded-lg border border-white/[0.08] bg-black p-2.5 transition-colors hover:border-beam-400/40">
                    <div className="flex items-center justify-between">
                      <span className="micro-sm text-white/30">{s.l}</span>
                      <span className="text-white/20">{s.g}</span>
                    </div>
                    <div className="tnum mt-2 text-[16px] font-light leading-none text-white">
                      <Counter value={s.v} format={s.f} />
                    </div>
                  </div>
                ))}
              </div>
            </Collapsible>

            {/* 4. Cerebro del Modelo: Feedback Inteligente por Canal */}
            <Collapsible title="Aprendizaje del Modelo por Canal" defaultOpen={true}>
              <div className="space-y-2.5">
                {/* Estructura ganadora */}
                <div className="rounded-xl border border-white/[0.09] bg-black p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="micro-sm text-beam-300 font-medium">ESTRUCTURA GANADORA</span>
                    <span className="micro-sm text-signal-400 border border-signal-400/25 bg-signal-400/10 px-1.5 py-0.5 rounded">
                      {currentChannel?.best_structure?.avg_score || 82}% retención
                    </span>
                  </div>
                  <div className="text-[11.5px] font-semibold text-white/95">
                    {currentChannel?.best_structure?.name || "Revelación de Shock / Misterio Oculto"}
                  </div>
                  <p className="text-[10px] text-white/50 leading-relaxed">
                    Esta estructura maximiza la permanencia en «{currentChannel?.channel_title}» al plantear un quiebre de expectativa en los primeros 3 segundos.
                  </p>
                </div>

                {/* Gancho más efectivo */}
                <div className="rounded-xl border border-white/[0.09] bg-black p-3 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="micro-sm text-ember-300 font-medium">GANCHO (HOOK) DE ALTA RETENCIÓN</span>
                    <span className="micro-sm text-ember-400 border border-ember-400/25 bg-ember-400/10 px-1.5 py-0.5 rounded">
                      +35% retención inicial
                    </span>
                  </div>
                  <div className="text-[11.5px] font-semibold text-white/95">
                    {currentChannel?.best_hook?.name || "Declaración de Shock / Revelación Directa"}
                  </div>
                  <p className="text-[10px] text-white/50 leading-relaxed">
                    Evita saludos o intros lentas; inicia con afirmaciones directas que activan el bucle Zeigarnik.
                  </p>
                </div>

                {/* Nota de retroalimentación activa al modelo */}
                <div className="rounded-xl border border-beam-400/30 bg-beam-500/10 p-3 space-y-1.5">
                  <div className="flex items-center gap-1.5 text-beam-200 font-medium text-[11px]">
                    <IconBrain className="h-3.5 w-3.5 shrink-0" />
                    <span>Retroalimentación Activa al Modelo</span>
                  </div>
                  <p className="text-[10px] text-white/70 leading-relaxed">
                    El <strong className="text-white">Productor IA</strong> y el <strong className="text-white">Autopilot</strong> inyectan este aprendizaje en cada nuevo guión generado para este canal. El modelo descarta automáticamente estructuras que no retienen.
                  </p>
                </div>

                {/* Anti-patrones */}
                <div className="rounded-lg border border-white/[0.06] bg-black/60 p-2.5 text-[10px] text-white/45 space-y-1">
                  <span className="micro-sm text-ember-400/80">DESCARTADO POR EL MODELO:</span>
                  <div className="text-white/60">• Introducciones lentas sin revelación en primeros 3s</div>
                  <div className="text-white/60">• Estructuras genéricas sin tarjetas sólidas de datos</div>
                </div>
              </div>
            </Collapsible>

            {/* 5. Videos Publicados y Rendimiento Real */}
            <Collapsible title={`Videos en Canal (${channelVideos.length})`} defaultOpen={true}>
              <div className="space-y-1.5">
                {channelVideos.length === 0 ? (
                  <div className="p-3 text-center text-[10.5px] text-white/40 border border-white/[0.06] rounded-lg">
                    No hay videos sincronizados aún para este canal. Haz clic en "Sincronizar YouTube".
                  </div>
                ) : (
                  channelVideos.map((v) => (
                    <div
                      key={v.video_id}
                      className="group flex flex-col gap-1.5 rounded-lg border border-white/[0.08] bg-black p-2.5 transition-colors hover:border-beam-400/40"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-[11px] font-medium text-white/90 line-clamp-1 leading-snug">
                          {v.title}
                        </span>
                        <a
                          href={`https://youtu.be/${v.video_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="shrink-0 text-beam-300 hover:text-beam-100 p-0.5"
                          title="Ver en YouTube"
                        >
                          <IconExternalLink className="h-3 w-3" />
                        </a>
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-white/40 pt-0.5">
                        <div className="flex items-center gap-2">
                          <span className="text-white/70 font-medium">
                            {v.metrics?.views ?? 0} {v.metrics?.views === 1 ? "vista" : "vistas"}
                          </span>
                          <span>•</span>
                          <span>{v.metrics?.likes ?? 0} likes</span>
                        </div>
                        <span className="micro-sm text-beam-300/80 bg-beam-500/10 border border-beam-400/20 px-1.5 py-0.2 rounded">
                          {v.structure_type === "revelacion_shock"
                            ? "Revelación"
                            : v.structure_type === "comparativa_versus"
                            ? "Comparativa"
                            : "Problema/Solución"}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Collapsible>

            {/* Curva de retención */}
            <Collapsible title="Curva de retención proyectada" defaultOpen={false}>
              <RetentionChart />
            </Collapsible>

            {/* Momentos clave */}
            <Collapsible title="Momentos clave" defaultOpen={false}>
              <Moments />
            </Collapsible>

            {/* Audiencia y horarios */}
            <Collapsible title="Audiencia y horarios" defaultOpen={false}>
              <Audience />
            </Collapsible>

            {/* Siguiente acción óptima */}
            <Collapsible title="Siguiente acción óptima" defaultOpen={false}>
              <NextActions />
            </Collapsible>

            {/* Publicación sugerida */}
            <Collapsible title="Publicación sugerida" defaultOpen={false}>
              <div className="rounded-lg border border-white/[0.08] bg-black p-3">
                <div className="flex items-center justify-between">
                  <span className="micro-sm text-white/30">Mejor ventana</span>
                  <span className="micro-sm text-beam-200/80">{pf.peak}</span>
                </div>
                <p className="mt-2 text-[10px] leading-relaxed text-white/35">
                  Ventana óptima detectada con {applied.length} optimizaciones aplicadas.
                  Retención media estimada {Math.round(metrics.avg * 100)} %.
                </p>
              </div>
            </Collapsible>
          </>
        )}
      </div>
    </aside>
  );
}

export function ActivityBar() {
  const { log, toast } = useEditor();
  return (
    <>
      <footer className="glass-deep hidden h-8 shrink-0 items-center gap-3 rounded-none border-x-0 border-b-0 px-3 lg:flex">
        <span className="micro-sm text-white/25">Registro neuronal</span>
        <div className="h-3 w-px bg-white/10" />
        <div className="flex min-w-0 flex-1 items-center gap-4 overflow-hidden">
          {log.slice(0, 5).map((l, i) => (
            <span
              key={l.id}
              className={cn(
                "flex shrink-0 items-center gap-1.5 text-[10px] transition-opacity",
                i === 0 ? "text-white/70" : "text-white/25",
              )}
            >
              <span
                className={cn(
                  "h-1 w-1 rounded-full",
                  l.kind === "warn" ? "bg-ember-400" : l.kind === "info" ? "bg-signal-400" : "bg-beam-400",
                )}
              />
              <span className="tnum text-white/20">{l.at}</span>
              {l.text}
            </span>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <span className="micro-sm text-white/20">GPU 41 %</span>
          <span className="micro-sm text-white/20">VRAM 6.2 / 16 GB</span>
          <span className="micro-sm text-beam-200/70">48 núcleos tensor</span>
        </div>
      </footer>

      <div
        className={cn(
          "pointer-events-none fixed bottom-16 left-1/2 z-50 -translate-x-1/2 transition-all duration-500",
          toast ? "translate-y-0 opacity-100" : "translate-y-3 opacity-0",
        )}
      >
        <div className="glass flex items-center gap-2.5 rounded-full px-4 py-2.5">
          <IconSparkle className="h-3.5 w-3.5 text-beam-200" />
          <span className="text-[11px] text-white/85">{toast}</span>
        </div>
      </div>
    </>
  );
}

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type NarrativeSceneProps = {
  kind: string;
  title: string;
  labelA: string;
  labelB: string;
  spokenPhrase?: string;
  words?: Array<{ word: string; start: number; end: number }>;
  durationSec: number;
  width: number;
  height: number;
  fps: number;
  vertical: boolean;
  theme?: { primary?: string; accent?: string; bg?: string; textColor?: string };
};

const clamp = { extrapolateLeft: "clamp" as const, extrapolateRight: "clamp" as const };
const safeText = (s: string, fallback: string) => (s || fallback).trim().slice(0, 72);

export const NarrativeScene: React.FC<NarrativeSceneProps> = (p) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const total = Math.max(1, Math.round(p.durationSec * fps));
  const t = Math.max(0, Math.min(1, frame / total));
  const elapsedSec = frame / fps;
  const alignedWords = (p.words || []).filter((w) => Number.isFinite(w.start) && Number.isFinite(w.end) && w.end > w.start);
  const foundWordIndex = alignedWords.findIndex((w) => elapsedSec <= w.end);
  const activeWordIndex = alignedWords.length ? (foundWordIndex < 0 ? alignedWords.length - 1 : foundWordIndex) : -1;
  const visualT = alignedWords.length > 1 && activeWordIndex >= 0 ? activeWordIndex / (alignedWords.length - 1) : t;
  const enter = spring({ frame, fps, config: { damping: 20, stiffness: 110, mass: 0.85 }, durationInFrames: 22 });
  const exit = interpolate(frame, [total - Math.min(12, Math.floor(total / 4)), total], [1, 0], clamp);
  const opacity = Math.min(1, enter * 1.2) * exit;
  const accent = p.theme?.accent || "#F46B45";
  const cyan = p.theme?.primary || "#70C8F2";
  const ink = "#0B1017";
  const paper = "#F4F2EC";
  const muted = "#A6B2C0";
  const title = safeText(p.title, "UNA IDEA, EXPLICADA");
  const a = safeText(p.labelA, "ORIGEN");
  const b = safeText(p.labelB, "RESULTADO");
  const slide = interpolate(enter, [0, 1], [34, 0]);

  const labelStyle: React.CSSProperties = {
    fontFamily: "Inter, Arial, sans-serif", fontSize: Math.max(17, width * 0.018),
    fontWeight: 650, letterSpacing: "0.11em", textTransform: "uppercase",
  };

  return (
    <AbsoluteFill style={{ opacity, overflow: "hidden", color: paper, fontFamily: "Inter, Arial, sans-serif", background: "transparent" }}>
      <AbsoluteFill style={{ opacity: 0.12, backgroundImage: "linear-gradient(rgba(160,180,200,.22) 1px, transparent 1px), linear-gradient(90deg, rgba(160,180,200,.22) 1px, transparent 1px)", backgroundSize: `${Math.max(28, width / 36)}px ${Math.max(28, width / 36)}px` }} />
      <div style={{ position: "absolute", left: "7%", right: "7%", top: "9%", display: "flex", alignItems: "center", gap: 14, color: accent, ...labelStyle, fontSize: Math.max(12, width * 0.009), opacity: interpolate(t, [0, .18], [0, 1], clamp) }}>
        <span style={{ width: 30, height: 3, background: accent, display: "inline-block" }} />
        {p.kind.replace(/_/g, " ")}
        <span style={{ marginLeft: "auto", color: muted, fontSize: Math.max(11, width * .007), letterSpacing: ".16em" }}>VISUAL EXPLAINER / {String(Math.floor(t * 100)).padStart(2, "0")}</span>
      </div>

      {p.kind === "title_card" ? (
        <div style={{ position: "absolute", left: "11%", right: "11%", top: "29%", transform: `translateY(${slide}px)`, textAlign: "center" }}>
          <div style={{ ...labelStyle, fontSize: Math.max(15, width * .014), color: accent, marginBottom: "2.5%" }}>{a}</div>
          <div style={{ fontSize: `clamp(36px, ${width * .044}px, 92px)`, fontWeight: 780, lineHeight: 1.02, letterSpacing: "-.045em", textShadow: "0 8px 42px rgba(0,0,0,.45)" }}>{title}</div>
          <div style={{ width: interpolate(t, [0.15, .55], [0, width * .10], clamp), height: 4, margin: "3% auto", background: accent }} />
          <div style={{ color: muted, fontSize: Math.max(17, width * .016), letterSpacing: ".025em" }}>{b}</div>
        </div>
      ) : null}

      {p.kind === "code_terminal" ? (
        <div style={{ position: "absolute", left: "12%", right: "12%", top: "23%", bottom: "17%", border: "1px solid rgba(166,190,210,.42)", borderRadius: 16, background: "rgba(7,11,17,.94)", boxShadow: "0 26px 90px rgba(0,0,0,.5)", overflow: "hidden", transform: `translateY(${slide}px)` }}>
          <div style={{ height: "12%", background: "#202833", display: "flex", alignItems: "center", padding: "0 3%", gap: 9, color: muted, fontSize: Math.max(12, width * .009) }}>
            {["#F46B45", "#E5BB62", "#6FC69A"].map((c, i) => <span key={i} style={{ width: 9, height: 9, borderRadius: 99, background: c }} />)}
            <span style={{ marginLeft: 12 }}>{a || "analysis.py"}</span><span style={{ marginLeft: "auto" }}>● RUNNING</span>
          </div>
          <div style={{ padding: "3% 4%", display: "grid", gap: "2.3%", fontFamily: "ui-monospace, SFMono-Regular, Consolas, monospace", fontSize: `clamp(13px, ${width * .014}px, 28px)` }}>
            {[
              ["01", "def analizar(entrada):"],
              ["02", "    datos = extraer_patrones(entrada)"],
              ["03", "    conexiones = detectar_relaciones(datos)"],
              ["04", "    return explicar(conexiones)"],
            ].map((line, i) => {
              const active = Math.min(3, Math.floor(visualT * 4)) === i;
              return <div key={line[0]} style={{ display: "flex", gap: "3%", padding: "1.1% 1.5%", borderRadius: 6, background: active ? "rgba(244,107,69,.17)" : "transparent", borderLeft: active ? `3px solid ${accent}` : "3px solid transparent", color: active ? paper : "#9BA8B6", opacity: interpolate(t, [i * .12, Math.min(.9, i * .12 + .18)], [0.35, 1], clamp) }}>
                <span style={{ color: cyan }}>{line[0]}</span><span>{line[1]}</span><span style={{ marginLeft: "auto", color: accent }}>{active ? "▌" : ""}</span>
              </div>;
            })}
            <div style={{ marginTop: "1%", color: "#7CD6A6", fontSize: ".75em" }}>› {b}</div>
          </div>
        </div>
      ) : null}

      {p.kind === "cyber_diagram" || p.kind === "flow" || p.kind === "network" || p.kind === "sequence" || p.kind === "cause_effect" || p.kind === "automation" ? (
        <div style={{ position: "absolute", left: "8%", right: "8%", top: "26%", height: "52%", transform: `translateY(${slide}px)` }}>
          <div style={{ textAlign: "center", fontSize: `clamp(20px, ${width * .026}px, 46px)`, fontWeight: 760, letterSpacing: "-.025em", marginBottom: "1.8%", textShadow: "0 8px 34px rgba(0,0,0,.5)" }}>{title}</div>
          <svg viewBox="0 0 1000 420" width="100%" height="82%" style={{ overflow: "visible" }}>
            {p.kind === "cyber_diagram" ? <rect x="42" y="62" width="916" height="292" rx="22" fill="rgba(13,21,31,.45)" stroke={cyan} strokeDasharray="9 9" strokeOpacity=".7" /> : null}
            {[150, 325, 500, 675, 850].slice(0, p.kind === "cause_effect" || p.kind === "automation" ? 3 : 5).map((x, i, arr) => {
              const active = Math.min(arr.length - 1, Math.floor(visualT * arr.length)) === i;
              const labels = [a, "ANÁLISIS", "SEÑAL", "CONEXIÓN", b];
              return <g key={x}>
                {i < arr.length - 1 ? <line x1={x + 54} y1="210" x2={arr[i + 1] - 54} y2="210" stroke={accent} strokeWidth="3" strokeDasharray="8 7" strokeDashoffset={-visualT * 80} opacity=".85" /> : null}
                <rect x={x - 58} y="166" width="116" height="88" rx="13" fill={active ? "rgba(244,107,69,.22)" : "rgba(9,15,23,.94)"} stroke={active ? accent : "#536575"} strokeWidth={active ? 3 : 1.5} />
                <text x={x} y="205" fill={paper} fontSize="15" fontWeight="700" textAnchor="middle">{(labels[i] || b).slice(0, 14)}</text>
                <text x={x} y="230" fill={muted} fontSize="10" textAnchor="middle">STEP 0{i + 1}</text>
              </g>;
            })}
            <circle cx={150 + visualT * 700} cy="210" r="10" fill={paper} stroke={accent} strokeWidth="4" />
            <circle cx={150 + visualT * 700} cy="210" r="23" fill={accent} opacity=".12" />
          </svg>
        </div>
      ) : null}

      {p.kind === "pixel_team" ? (
        <div style={{ position: "absolute", left: "9%", right: "9%", top: "24%", bottom: "13%", display: "grid", gridTemplateColumns: "repeat(6, minmax(0, 1fr))", gridTemplateRows: "repeat(2, 1fr)", gap: "2%", transform: `translateY(${slide}px)` }}>
          {Array.from({ length: 12 }, (_, i) => {
            const hue = [18, 198, 145, 265, 42, 175, 345, 220, 28, 135, 300, 205][i];
            const active = i <= Math.floor(visualT * 12);
            return <div key={i} style={{ background: "rgba(9,14,22,.9)", border: `1px solid hsla(${hue},65%,65%,${active ? .9 : .3})`, borderRadius: 10, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 9, boxShadow: active ? `0 0 24px hsla(${hue},75%,60%,.13)` : "none" }}>
              <svg viewBox="0 0 64 76" width="46%" height="56%">
                <rect x="22" y="5" width="20" height="20" fill="#EBC9A8" />
                <rect x="18" y="25" width="28" height="25" fill={`hsl(${hue},58%,55%)`} />
                <rect x="10" y="29" width="8" height="20" fill={`hsl(${hue},58%,55%)`} />
                <rect x="46" y="29" width="8" height="20" fill={`hsl(${hue},58%,55%)`} />
                <rect x="20" y="50" width="10" height="20" fill="#C8D1DA" />
                <rect x="34" y="50" width="10" height="20" fill="#C8D1DA" />
                <rect x="26" y="12" width="4" height="4" fill={ink} /><rect x="35" y="12" width="4" height="4" fill={ink} />
              </svg>
              <div style={{ color: active ? paper : muted, fontSize: `clamp(9px, ${width * .006}px, 14px)`, letterSpacing: ".07em" }}>AGENTE {String(i + 1).padStart(2, "0")}</div>
            </div>;
          })}
        </div>
      ) : null}

      {!["title_card", "code_terminal", "cyber_diagram", "flow", "network", "sequence", "cause_effect", "automation", "pixel_team"].includes(p.kind) ? (
        <div style={{ position: "absolute", left: "12%", right: "12%", top: "34%", textAlign: "center", transform: `translateY(${slide}px)` }}>
          <div style={{ ...labelStyle, color: accent, fontSize: Math.max(13, width * .013), marginBottom: 20 }}>{a}</div>
          <div style={{ fontSize: `clamp(34px, ${width * .04}px, 84px)`, fontWeight: 780, letterSpacing: "-.04em", lineHeight: 1.05 }}>{title}</div>
          <div style={{ margin: "28px auto", width: interpolate(t, [.1, .65], [0, width * .12], clamp), height: 4, background: accent }} />
          <div style={{ fontSize: Math.max(18, width * .017), color: muted }}>{b}</div>
        </div>
      ) : null}

      <div style={{ position: "absolute", bottom: "8%", left: "7%", right: "7%", height: 2, background: "rgba(160,180,200,.18)" }}>
        <div style={{ width: `${t * 100}%`, height: "100%", background: accent, boxShadow: `0 0 16px ${accent}` }} />
      </div>
    </AbsoluteFill>
  );
};

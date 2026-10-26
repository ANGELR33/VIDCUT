import f1 from "@/assets/frame-01.jpg";
import f2 from "@/assets/frame-02.jpg";
import f3 from "@/assets/frame-03.jpg";

export const FRAMES = [f1, f2, f3];

export type Ratio = "9:16" | "1:1" | "4:5" | "16:9";
export type TrackId = "v2" | "v1" | "a1" | "t1";

export type Clip = {
  id: string;
  track: TrackId;
  start: number;
  duration: number;
  label: string;
  kind: "scene" | "broll" | "music" | "voice" | "caption" | "fx";
  frame?: string;
  ai?: boolean;
  locked?: boolean;
};

export const TRACKS: { id: TrackId; name: string; tag: string }[] = [
  { id: "v2", name: "B-ROLL", tag: "V2" },
  { id: "v1", name: "VIDEO", tag: "V1" },
  { id: "t1", name: "TEXTO", tag: "TX" },
  { id: "a1", name: "AUDIO", tag: "A1" },
];

export const DURATION = 32;

export const SCENES = [
  {
    id: "sc-1",
    name: "A. Hook directo",
    camera: "Plano medio · 35mm",
    frame: f1,
    tint: "rgba(10,22,58,0.34)",
    hook: "El error que\nninguno te dice",
    note: "Retención inicial fuerte · mirada a cámara",
  },
  {
    id: "sc-2",
    name: "B. Prueba en pantalla",
    camera: "Macro · 85mm",
    frame: f2,
    tint: "rgba(6,14,40,0.4)",
    hook: "Esto es lo que\nhice en 14 días",
    note: "Ritmo alto · inserto de apoyo",
  },
  {
    id: "sc-3",
    name: "C. Cierre + CTA",
    camera: "Gran angular · 24mm",
    frame: f3,
    tint: "rgba(12,20,54,0.3)",
    hook: "Guárdalo antes\nde que lo borre",
    note: "Cierre abierto · loop natural",
  },
];

export const CLIPS: Clip[] = [
  { id: "c1", track: "v1", start: 0, duration: 11.5, label: "A. Hook directo", kind: "scene", frame: f1 },
  { id: "c2", track: "v1", start: 11.5, duration: 12, label: "B. Prueba en pantalla", kind: "scene", frame: f2 },
  { id: "c3", track: "v1", start: 23.5, duration: 8.5, label: "C. Cierre + CTA", kind: "scene", frame: f3 },

  { id: "b1", track: "v2", start: 3.2, duration: 2.6, label: "Inserto · dato clave", kind: "broll", ai: true },
  { id: "b2", track: "v2", start: 9.8, duration: 2.2, label: "Inserto · gráfico", kind: "broll", ai: true },
  { id: "b3", track: "v2", start: 18.4, duration: 3.1, label: "Inserto · antes/después", kind: "broll", ai: true },

  { id: "t1", track: "t1", start: 0.4, duration: 10.4, label: "Subtítulos cinéticos", kind: "caption", ai: true },
  { id: "t2", track: "t1", start: 12.1, duration: 10.9, label: "Subtítulos cinéticos", kind: "caption", ai: true },
  { id: "t3", track: "t1", start: 23.9, duration: 7.4, label: "CTA animado", kind: "caption", ai: true },

  { id: "a1", track: "a1", start: 0, duration: 11.5, label: "Locución · A. Hook directo", kind: "voice", ai: true },
  { id: "a2", track: "a1", start: 11.5, duration: 12, label: "Locución · B. Prueba en pantalla", kind: "voice", ai: true },
  { id: "a3", track: "a1", start: 23.5, duration: 8.5, label: "Locución · C. Cierre + CTA", kind: "voice", ai: true },
];

export type Caption = { start: number; end: number; text: string; hot?: boolean };

export const CAPTIONS: Caption[] = [
  { start: 0.4, end: 2.9, text: "Nadie te dice esto del algoritmo", hot: true },
  { start: 2.9, end: 5.4, text: "y por eso tu video muere en 3 horas" },
  { start: 5.4, end: 8.2, text: "Los primeros 2 segundos lo deciden todo", hot: true },
  { start: 8.2, end: 11.2, text: "así que corta la intro. Directo al punto." },
  { start: 11.6, end: 14.4, text: "Mira lo que pasó cuando lo apliqué" },
  { start: 14.4, end: 17.6, text: "la retención subió un 41 por ciento", hot: true },
  { start: 17.6, end: 21.0, text: "sin grabar un solo segundo extra." },
  { start: 21.0, end: 24.0, text: "La IA reordena, corta y subtitula" },
  { start: 24.2, end: 27.4, text: "tú solo eliges el estilo", hot: true },
  { start: 27.4, end: 31.0, text: "Guárdalo antes de que lo borre." },
];

/* ------------------------------------------------------------------ */
/*  AI automations                                                     */
/* ------------------------------------------------------------------ */

export type Automation = {
  id: string;
  name: string;
  detail: string;
  glyph: string;
  ms: number;
  score: number;
  retention: number;
  reach: number;
  category: "narrativa" | "ritmo" | "acabado" | "distribución";
};

export const AUTOMATIONS: Automation[] = [
  { id: "hook", name: "Reencuadre del hook", detail: "Recorta 1.8 s y realza el primer plano", glyph: "◈", ms: 2400, score: 7, retention: 9, reach: 6, category: "narrativa" },
  { id: "silence", name: "Silencios fuera", detail: "4 pausas detectadas · umbral -34 dB", glyph: "◍", ms: 1800, score: 3, retention: 5, reach: 2, category: "ritmo" },
  { id: "captions", name: "Subtítulos cinéticos", detail: "92 palabras · estilo Kinetic Bold", glyph: "❝", ms: 2100, score: 6, retention: 8, reach: 5, category: "acabado" },
  { id: "broll", name: "B-roll generativo", detail: "3 inserts coherentes con la escena", glyph: "▣", ms: 3200, score: 5, retention: 6, reach: 4, category: "narrativa" },
  { id: "beat", name: "Corte a ritmo", detail: "Sincroniza cortes al BPM detectado", glyph: "≋", ms: 1500, score: 4, retention: 6, reach: 3, category: "ritmo" },
  { id: "color", name: "Color match LUT", detail: "Unifica paleta azul / noche", glyph: "◐", ms: 2600, score: 2, retention: 1, reach: 2, category: "acabado" },
  { id: "dub", name: "Locución neuronal", detail: "Voz clonada es-LA · Neural v4", glyph: "◉", ms: 3000, score: 3, retention: 3, reach: 3, category: "acabado" },
  { id: "thumb", name: "Portada predictiva", detail: "3 opciones · la #1 gana +12 % CTR", glyph: "◫", ms: 2000, score: 5, retention: 0, reach: 9, category: "distribución" },
  { id: "algo", name: "Ajuste por algoritmo", detail: "Longitud, hashtags y hora óptima", glyph: "⬡", ms: 1700, score: 4, retention: 2, reach: 8, category: "distribución" },
];

/* ------------------------------------------------------------------ */
/*  Viral metrics                                                      */
/* ------------------------------------------------------------------ */

export type PlatformId = "tiktok" | "reels" | "shorts";

export const PLATFORMS: {
  id: PlatformId;
  name: string;
  handle: string;
  mult: number;
  best: string;
  peak: string;
}[] = [
  { id: "tiktok", name: "TikTok", handle: "@lumen.studio", mult: 1, best: "19:40", peak: "Mar · 21:00" },
  { id: "reels", name: "Reels", handle: "@lumenstudio", mult: 0.72, best: "12:10", peak: "Mié · 13:00" },
  { id: "shorts", name: "Shorts", handle: "@lumen", mult: 0.58, best: "07:30", peak: "Jue · 08:00" },
];

/** Retención base (0..1) muestreada cada 0.5 s */
export const BASE_RETENTION = [
  1.0, 0.955, 0.938, 0.912, 0.881, 0.862, 0.848, 0.801, 0.772, 0.741, 0.719, 0.702, 0.688,
  0.664, 0.641, 0.628, 0.617, 0.604, 0.596, 0.577, 0.552, 0.536, 0.521, 0.509, 0.498, 0.481,
  0.466, 0.452, 0.441, 0.433, 0.427, 0.419, 0.408, 0.391, 0.374, 0.361, 0.352, 0.347, 0.344,
  0.341, 0.337, 0.332, 0.326, 0.318, 0.309, 0.301, 0.296, 0.292, 0.289, 0.286, 0.283, 0.279,
  0.276, 0.272, 0.268, 0.264, 0.261, 0.258, 0.255, 0.251, 0.248, 0.245, 0.242, 0.239, 0.236,
  0.233, 0.23,
];

export type Moment = {
  t: number;
  label: string;
  kind: "peak" | "risk" | "reveal" | "cta";
  note: string;
};

export const MOMENTS: Moment[] = [
  { t: 0.6, label: "Hook", kind: "peak", note: "Pico de atención · 96 %" },
  { t: 8.4, label: "Valle de riesgo", kind: "risk", note: "Caída del 22 % · falta apoyo visual" },
  { t: 14.6, label: "Revelación", kind: "reveal", note: "Sube 41 % de retención esperada" },
  { t: 24.2, label: "Cierre / CTA", kind: "cta", note: "Momento de guardado estimado" },
];

export const AUDIENCE = [
  { label: "18-24", value: 38 },
  { label: "25-34", value: 41 },
  { label: "35-44", value: 14 },
  { label: "45+", value: 7 },
];

export const HEATMAP = [
  { day: "L", slots: [12, 22, 34, 48, 62, 74, 88, 71] },
  { day: "M", slots: [18, 28, 40, 52, 68, 82, 94, 78] },
  { day: "X", slots: [14, 26, 38, 56, 72, 86, 90, 66] },
  { day: "J", slots: [20, 32, 44, 58, 76, 88, 82, 60] },
  { day: "V", slots: [26, 38, 50, 64, 80, 92, 78, 54] },
  { day: "S", slots: [34, 48, 62, 74, 88, 96, 70, 44] },
  { day: "D", slots: [24, 36, 46, 60, 72, 80, 58, 36] },
];

export type AssetItem = { name: string; meta: string; frame?: string };

export const ASSET_FOLDERS: { name: string; count: number; items: AssetItem[] }[] = [
  {
    name: "Tomas maestras",
    count: 24,
    items: [
      { name: "A. Hook directo", meta: "00:11 · 4K · 24 fps", frame: f1 },
      { name: "B. Prueba en pantalla", meta: "00:12 · 4K · 24 fps", frame: f2 },
      { name: "C. Cierre + CTA", meta: "00:08 · 4K · 24 fps", frame: f3 },
    ],
  },
  {
    name: "Generado por IA",
    count: 6,
    items: [
      { name: "Inserto · dato clave", meta: "Generado · 00:02", frame: f2 },
      { name: "Inserto · antes / después", meta: "Generado · 00:03", frame: f3 },
      { name: "Inserto · gráfico viral", meta: "Generado · 00:02", frame: f1 },
    ],
  },
  {
    name: "Audio",
    count: 9,
    items: [
      { name: "Pulso Nocturno", meta: "92 BPM · loop · -14 LUFS" },
      { name: "Locución IA · Neural v4", meta: "es-LA · 29 s" },
    ],
  },
];

export const PRESETS = [
  { id: "p1", name: "Nocturno", detail: "Azul mate · contraste alto", swatch: "linear-gradient(135deg,#0a142c,#2f5cff)" },
  { id: "p2", name: "Cine Índigo", detail: "Sombras profundas · film grain", swatch: "linear-gradient(135deg,#060d1e,#7ea3ff)" },
  { id: "p3", name: "Viral Pop", detail: "Brillo alto · saturación +18", swatch: "linear-gradient(135deg,#142a5e,#46e0c0)" },
  { id: "p4", name: "Documental", detail: "Neutro · latitud amplia", swatch: "linear-gradient(135deg,#0f141f,#8b96ad)" },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

export function timecode(t: number, fps = 24) {
  const safe = Math.max(0, t);
  const m = Math.floor(safe / 60);
  const s = Math.floor(safe % 60);
  const f = Math.floor((safe % 1) * fps);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}:${String(f).padStart(2, "0")}`;
}

export function clock(t: number) {
  const s = Math.max(0, t);
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}

export function compact(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(n >= 100_000 ? 0 : 1)}K`;
  return `${Math.round(n)}`;
}

export function retentionAt(idx: number, boost: number) {
  const base = BASE_RETENTION[Math.min(idx, BASE_RETENTION.length - 1)];
  const decay = 0.55 + 0.45 * (idx / BASE_RETENTION.length);
  return Math.min(1, base + boost * 0.9 * decay);
}

export function sceneAt(t: number) {
  if (t < 11.5) return SCENES[0];
  if (t < 23.5) return SCENES[1];
  return SCENES[2];
}

export function captionAt(t: number) {
  const c = CAPTIONS.find((x) => t >= x.start && t <= x.end);
  if (!c) return null;
  const words = c.text.split(" ");
  const p = (t - c.start) / (c.end - c.start);
  const i = Math.min(words.length - 1, Math.floor(p * words.length));
  return { words, index: i, hot: c.hot };
}

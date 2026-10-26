/* ------------------------------------------------------------------ */
/*  Motor de Temas Virales por Nicho para Videos de 10 a 40 Minutos   */
/* ------------------------------------------------------------------ */

export type ViralCategory =
  | "motivacion"
  | "cristiano_cine"
  | "versiculos"
  | "finanzas"
  | "amor"
  | "religion"
  | "versus"
  | "terror"
  | "misterio"
  | "politica"
  | "ciencia"
  | "curiosidades"
  | "historia"
  | "psicologia"
  | "crimen"
  | "tecnologia"
  | "narrativa";

export interface ViralTopic {
  id: string;
  title: string;
  nuances: string;
  category: ViralCategory;
  score: number; // Puntuación de viralidad (ej: +98)
  glyph: string;
  hookType: string;
  durationMin: number; // Duración recomendada: 1 para Shorts/Reels, 10 a 40 para documental
  isLive?: boolean; // Marca si fue generado en vivo por IA/Web
  added_at?: string;
}

export const CATEGORY_LABELS: Record<ViralCategory, { label: string; icon: string; desc: string }> = {
  motivacion: {
    label: "Motivación & Estoicismo",
    icon: "⚡",
    desc: "Frases de impacto, mentalidad imparable, disciplina estoica y música orquestal épica (Reels cortos)",
  },
  cristiano_cine: {
    label: "Cine Cristiano & Fe",
    icon: "🎬",
    desc: "Escenas conmovedoras de películas cristianas, perdón, milagros y testimonios con orquesta emotiva",
  },
  versiculos: {
    label: "Versículos Bíblicos",
    icon: "📖",
    desc: "Promesas de Dios, paz mental contra la ansiedad, salmos y adoración instrumental (Reels y Shorts)",
  },
  finanzas: { label: "Finanzas", icon: "💰", desc: "Dinero, negocios e inversiones" },
  amor: { label: "Amor & Pareja", icon: "❤️", desc: "Relaciones, psicología y seducción" },
  religion: { label: "Religión & Misterios", icon: "✝️", desc: "Fe cristiana, enigmas bíblicos y manuscritos" },
  versus: { label: "Versus", icon: "⚔️", desc: "Comparativas de productos y personas" },
  terror: { label: "Terror", icon: "👻", desc: "Casos oscuros, creepypastas y terror psicológico" },
  misterio: { label: "Misterio", icon: "👁️", desc: "Enigmas mundiales y fenómenos inexplicables" },
  politica: { label: "Política", icon: "🏛️", desc: "Geopolítica, guerras de poder y secretos de estado" },
  ciencia: { label: "Ciencia", icon: "🔬", desc: "Astrofísica, cuántica y descubrimientos" },
  curiosidades: { label: "Curiosidades", icon: "💡", desc: "Datos increíbles que desafían la lógica" },
  historia: { label: "Historia", icon: "🏺", desc: "Civilizaciones, archivos y secretos de reyes" },
  psicologia: { label: "Psicología", icon: "🧠", desc: "Mente humana, sesgos y manipulación" },
  crimen: { label: "True Crime", icon: "🔍", desc: "Casos reales, secuestros y robos maestros" },
  tecnologia: { label: "Tecnología", icon: "🤖", desc: "IA, futuro y computación" },
  narrativa: { label: "Narrativa", icon: "📽️", desc: "Historias y técnicas de documental" },
};

export const ALL_CATEGORIES: ViralCategory[] = [
  "motivacion",
  "cristiano_cine",
  "versiculos",
  "finanzas",
  "amor",
  "religion",
  "versus",
  "terror",
  "misterio",
  "politica",
  "ciencia",
  "curiosidades",
  "historia",
  "psicologia",
  "crimen",
  "tecnologia",
  "narrativa",
];

// Catálogo maestro inicial con semillas de alta retención
export const VIRAL_MASTER_POOL: ViralTopic[] = [
  {
    id: "vtl-mot-seed-01",
    title: "Marco Aurelio y el Control de la Mente: Cómo ser inmune a la provocación",
    nuances: "Estudio de las Meditaciones: la dicotomía del control aplicada a 2026. Gancho: 'Nadie puede perturbar tu paz sin tu consentimiento'. Fondo cinematográfico de estatuas romanas y contraste 35mm. Música: Orquesta épica motivacional.",
    category: "motivacion",
    score: 98,
    glyph: "⚡",
    hookType: "Estoicismo & Disciplina",
    durationMin: 1,
    isLive: true,
  },
  {
    id: "vtl-mot-seed-02",
    title: "La Regla de los 5 Segundos de Mel Robbins: Hackea la parálisis antes de dudar",
    nuances: "Mecanismo neuroquímico: cómo activar la corteza prefrontal contando 5-4-3-2-1 para vencer la amígdala. Gancho: 'El momento en que dudas, tu cerebro mata la idea'. Fondo dinámico acelerado en 4K. Música: Electrónica motivacional de foco.",
    category: "motivacion",
    score: 96,
    glyph: "🔥",
    hookType: "Neurociencia & Acción",
    durationMin: 1,
    isLive: true,
  },
  {
    id: "vtl-cri-seed-01",
    title: "Hasta el Último Hombre (Hacksaw Ridge): La oración de Desmond Doss bajo fuego enemigo",
    nuances: "Análisis del momento culmen donde un joven desarmado rescata a 75 soldados heridos clamando 'Señor, ayúdame a salvar a uno más'. La fe que desafía la lógica militar. Fondo cinematográfico dramático con neblina y rayos de luz. Música: Orquesta emotiva y violonchelo celestial.",
    category: "cristiano_cine",
    score: 99,
    glyph: "🎬",
    hookType: "Fe Bajo Fuego",
    durationMin: 1,
    isLive: true,
  },
  {
    id: "vtl-cri-seed-02",
    title: "Cuarto de Guerra (War Room): La escena donde la batalla se gana de rodillas",
    nuances: "La revelación de Elizabeth cuando deja de pelear con su esposo y lleva su batalla al armario de oración: 'El enemigo no es la persona, es el plano espiritual'. Gancho profundo sobre el poder de la intercesión. Fondo en penumbra con rayos dorados de luz. Música: Piano de adoración íntimo.",
    category: "cristiano_cine",
    score: 98,
    glyph: "✝️",
    hookType: "Poder de la Oración",
    durationMin: 1,
    isLive: true,
  },
  {
    id: "vtl-ver-seed-01",
    title: "Filipenses 4:6-7: El antídoto bíblico infalible contra la ansiedad y el insomnio",
    nuances: "'Por nada estéis afanosos, sino sean conocidas vuestras peticiones delante de Dios en oración... y la paz de Dios que sobrepasa todo entendimiento guardará vuestros corazones'. Contexto de Pablo en prisión. Fondo: olas suaves y puesta de sol en cámara lenta. Música: Piano de adoración pacífica.",
    category: "versiculos",
    score: 99,
    glyph: "📖",
    hookType: "Paz Sobrenatural",
    durationMin: 1,
    isLive: true,
  },
  {
    id: "vtl-ver-seed-02",
    title: "Salmo 91: El escudo de protección sobrenatural para ti y tu familia",
    nuances: "'El que habita al abrigo del Altísimo morará bajo la sombra del Omnipotente... con sus plumas te cubrirá'. La promesa de refugio seguro en medio de la adversidad o enfermedad. Fondo: cumbres montañosas con amanecer dorado entre las nubes. Música: Orquestación suave de esperanza.",
    category: "versiculos",
    score: 98,
    glyph: "🛡️",
    hookType: "Protección & Fortaleza",
    durationMin: 1,
    isLive: true,
  },
];

const STORAGE_PINNED_KEY = "lumen_pinned_viral_topics";
const STORAGE_DAILY_TOPICS_KEY = "lumen_daily_viral_topics";

/**
 * Detecta si un tema proviene del catálogo estático hardcodeado antiguo para purgarlo.
 */
export function isHardcodedLegacy(id: string): boolean {
  return typeof id === "string" && id.startsWith("vt-") && !id.startsWith("vtl-");
}

/**
 * Obtiene los IDs de los temas anclados/favoritos desde localStorage
 */
export function getStoredPinnedIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_PINNED_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((id: string) => !isHardcodedLegacy(id)) : [];
  } catch {
    return [];
  }
}

/**
 * Guarda los IDs de los temas anclados en localStorage y en el backend
 */
export function savePinnedIds(ids: string[], topicObj?: ViralTopic, isAdding?: boolean): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_PINNED_KEY, JSON.stringify(ids));
  } catch {}

  // Sincronización en segundo plano con el backend
  if (topicObj) {
    try {
      fetch("/api/trend-radar/favorites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: isAdding ? "add" : "remove",
          topic: {
            id: topicObj.id,
            title: topicObj.title,
            category: topicObj.category,
            score: topicObj.score,
            nuances: topicObj.nuances,
            durationMin: topicObj.durationMin,
          },
        }),
      }).catch(() => {});
    } catch {}
  }
}

/**
 * Sincroniza temas recibidos del rastreador de Internet en vivo, purgando hardcodeados.
 */
export function syncLiveTopics(incomingTopics: ViralTopic[], pinnedIds: string[]): ViralTopic[] {
  const pinnedSet = new Set(pinnedIds);
  let existing: ViralTopic[] = [];

  if (typeof window !== "undefined") {
    try {
      const raw = localStorage.getItem(STORAGE_DAILY_TOPICS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          // Filtrar cualquier residuo hardcodeado
          existing = parsed.filter((t) => !isHardcodedLegacy(t.id) && t.isLive);
        }
      }
    } catch {}
  }

  // Combinar por ID y título normalizado
  const map = new Map<string, ViralTopic>();
  existing.forEach((t) => map.set(t.id, t));
  incomingTopics.forEach((t) => {
    if (!isHardcodedLegacy(t.id)) {
      map.set(t.id, { ...t, isLive: true });
    }
  });

  const merged = Array.from(map.values());
  const pinned = merged.filter((t) => pinnedSet.has(t.id));
  const unpinned = merged.filter((t) => !pinnedSet.has(t.id));
  const result = [...pinned, ...unpinned];

  if (typeof window !== "undefined") {
    try {
      localStorage.setItem(STORAGE_DAILY_TOPICS_KEY, JSON.stringify(result));
    } catch {}
  }

  return result;
}

/**
 * Genera o recupera los temas virales. Elimina por completo los temas hardcodeados.
 */
export function generateDailyTopics(pinnedIds: string[], _forceNewSeed: boolean = false): ViralTopic[] {
  let savedTopics: ViralTopic[] = [];

  if (typeof window !== "undefined") {
    try {
      const rawTopics = localStorage.getItem(STORAGE_DAILY_TOPICS_KEY);
      if (rawTopics) {
        const parsed = JSON.parse(rawTopics);
        if (Array.isArray(parsed)) {
          // Purgar de inmediato cualquier tema hardcodeado antiguo de la caché
          savedTopics = parsed.filter((t) => !isHardcodedLegacy(t.id) && t.isLive);
        }
      }
    } catch {}
  }

  if (savedTopics.length === 0) {
    savedTopics = [...VIRAL_MASTER_POOL];
  }

  const pinnedSet = new Set(pinnedIds);
  const pinned = savedTopics.filter((t) => pinnedSet.has(t.id));
  const unpinned = savedTopics.filter((t) => !pinnedSet.has(t.id));
  return [...pinned, ...unpinned];
}

// Mantener retrocompatibilidad con la firma anterior
export const generateDaily30Topics = generateDailyTopics;

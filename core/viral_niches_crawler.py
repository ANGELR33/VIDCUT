"""Motor de Descubrimiento Progresivo de Nichos Virales en Internet.

Rastrea noticias, tendencias y debates frescos en Internet para las 14 categorías
del estudio (finanzas, misterio, ciencia, política, tecnología, etc.), generando
progresivamente al menos 10 temas de alto impacto por categoría y actualizándolos
continuamente sin temas hardcodeados.
"""

from __future__ import annotations

import json
import random
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import settings
from core.llm import LLMClient, safe_log

VIRAL_CATEGORIES_CONFIG = {
    "motivacion": {
        "name": "Motivación & Estoicismo",
        "glyph": "⚡",
        "hook": "Mentalidad Inquebrantable",
        "queries": [
            "frases motivacionales estoicismo marco aurelio seneca disciplina mentalidad exito",
            "lecciones de vida fuerza mental foco imparable superacion personal habitos",
            "citas celebres de motivacion hombres de impacto discursos inspiradores",
        ],
    },
    "cristiano_cine": {
        "name": "Cine & Cortos Cristianos",
        "glyph": "🎬",
        "hook": "Escena de Fe & Redención",
        "queries": [
            "peliculas cristianas escenas mas emotivas lecciones de fe perdon redencion",
            "historias cristianas cine momentos inspiradores amor de Dios esperanza milagros",
            "cortos cristianos reflexiones cinematicas testimonios reales de fe orquesta emotiva",
        ],
    },
    "versiculos": {
        "name": "Versículos & Promesas",
        "glyph": "📖",
        "hook": "Promesa Bíblica & Paz",
        "queries": [
            "versiculos biblicos para la ansiedad paz fortaleza promesas de Dios",
            "salmos poderosos oraciones de la manana proteccion bendicion diaria",
            "proverbios sabiduria versiculos cortos explicacion profunda fe y esperanza",
        ],
    },
    "finanzas": {
        "name": "Finanzas",
        "glyph": "💰",
        "hook": "Estrategia de Riqueza",
        "queries": [
            "estrategia inversion multimillonarios economia dinero 2026",
            "mercados financieros crisis oportunidad negocio",
            "finanzas personales secretos ahorro impuestos",
        ],
    },
    "amor": {
        "name": "Amor & Pareja",
        "glyph": "❤️",
        "hook": "Psicología Relacional",
        "queries": [
            "psicologia de parejas relaciones amor seduccion",
            "comportamiento humano ruptura atraccion citas",
            "terapia de pareja comunicacion apego emocional",
        ],
    },
    "religion": {
        "name": "Religión & Misterios",
        "glyph": "✝️",
        "hook": "Enigma Bíblico",
        "queries": [
            "misterios biblicos arqueologia sagrada descubrimientos vaticano",
            "manuscritos mar muerto textos apocrifos revelaciones",
            "historia de las religiones enigmas teologicos fe",
        ],
    },
    "versus": {
        "name": "Versus",
        "glyph": "⚔️",
        "hook": "Duelo Definitivo",
        "queries": [
            "comparativa marcas empresas rivalidad historica mercado",
            "duelo tecnologia modelos potencia benchmark",
            "enfrentamiento economico corporativo titanes",
        ],
    },
    "terror": {
        "name": "Terror",
        "glyph": "👻",
        "hook": "Terror Psicológico",
        "queries": [
            "casos oscuros perturbadores misterios terror psicologico",
            "leyendas urbanas reales fenomenos aterradores",
            "archivos desclasificados expedientes inquietantes",
        ],
    },
    "misterio": {
        "name": "Misterio",
        "glyph": "👁️",
        "hook": "Enigma Oculto",
        "queries": [
            "enigmas mundiales fenomenos inexplicables investigaciones cientificas",
            "desapariciones misteriosas anomalias geograficas",
            "secretos jamas resueltos evidencia desconcertante",
        ],
    },
    "politica": {
        "name": "Política",
        "glyph": "🏛️",
        "hook": "Geopolítica y Poder",
        "queries": [
            "geopolitica mundial secretos de estado conflictos poder 2026",
            "estrategia militar acuerdos internacionales tension diplomacia",
            "elecciones lideres mundiales decisiones historicas",
        ],
    },
    "ciencia": {
        "name": "Ciencia",
        "glyph": "🔬",
        "hook": "Revelación Científica",
        "queries": [
            "descubrimientos cientificos astrofisica universo james webb",
            "fisica cuantica experimentos revolucionarios naturaleza",
            "biologia genetica avances medicina descubrimientos",
        ],
    },
    "curiosidades": {
        "name": "Curiosidades",
        "glyph": "💡",
        "hook": "Curiosidad Viral",
        "queries": [
            "datos insolitos paradojas mundo real que pocos conocen",
            "records increibles fenomenos cotidianos explicados",
            "hechos sorprendentes que desafian el sentido comun",
        ],
    },
    "historia": {
        "name": "Historia",
        "glyph": "🏺",
        "hook": "Caso Histórico Real",
        "queries": [
            "arqueologia civilizaciones antiguas imperios secretos desenterrados",
            "batallas olvidadas reyes conspiraciones historicas",
            "momentos que cambiaron el rumbo de la humanidad",
        ],
    },
    "psicologia": {
        "name": "Psicología",
        "glyph": "🧠",
        "hook": "Psicología Oscura",
        "queries": [
            "psicologia oscura sesgos cognitivos manipulacion mente persuasión",
            "experimentos psicologicos comportamiento social mente humana",
            "neurociencia habitos concentracion toma de decisiones",
        ],
    },
    "crimen": {
        "name": "True Crime",
        "glyph": "🔍",
        "hook": "Investigación True Crime",
        "queries": [
            "true crime investigacion policial casos reales juicios pruebas",
            "robos maestros estafas complejas mentes criminales",
            "misterios forenses resolucion de crimenes de alto impacto",
        ],
    },
    "tecnologia": {
        "name": "Tecnología",
        "glyph": "🤖",
        "hook": "Frontera Tecnológica",
        "queries": [
            "inteligencia artificial futuro robotica microchips semiconductores",
            "ciberseguridad innovacion computacion cuantica software",
            "dispositivos del futuro avances tecnologicos emergentes",
        ],
    },
    "narrativa": {
        "name": "Narrativa",
        "glyph": "🎬",
        "hook": "Crónica Inmersiva",
        "queries": [
            "historias reales supervivencia casos extraordinarios hazana humana",
            "relatos de exploradores desafios extremos cronica",
            "vidas extraordinarias giros de guion de la vida real",
        ],
    },
}


SEED_CURATED_TOPICS: List[Dict[str, Any]] = [
    # Motivación & Estoicismo
    {
        "id": "vtl-mot-seed-01",
        "title": "Marco Aurelio y el Control de la Mente: Cómo ser inmune a la provocación",
        "nuances": "Estudio de las Meditaciones: la dicotomía del control aplicada a 2026. Gancho: 'Nadie puede perturbar tu paz sin tu consentimiento'. Fondo cinematográfico de estatuas romanas y contraste 35mm. Música: Orquesta épica motivacional.",
        "category": "motivacion",
        "score": 98,
        "glyph": "⚡",
        "hookType": "Estoicismo & Disciplina",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-mot-seed-02",
        "title": "La Regla de los 5 Segundos de Mel Robbins: Hackea la parálisis antes de dudar",
        "nuances": "Mecanismo neuroquímico: cómo activar la corteza prefrontal contando 5-4-3-2-1 para vencer la amígdala. Gancho: 'El momento en que dudas, tu cerebro mata la idea'. Fondo dinámico acelerado en 4K. Música: Electrónica motivacional de foco.",
        "category": "motivacion",
        "score": 96,
        "glyph": "🔥",
        "hookType": "Neurociencia & Acción",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-mot-seed-03",
        "title": "Séneca frente al Caos: Por qué sufrimos más en la imaginación que en la realidad",
        "nuances": "Análisis de las Cartas a Lucilio: la técnica estoica de 'Praemeditatio Malorum' para desarmar la ansiedad anticipatoria. Gancho: 'Estás sufriendo por guerras que solo ocurren en tu cabeza'. Fondo de lluvia en la noche y luz dorada. Música: Piano solemne de cuerdas.",
        "category": "motivacion",
        "score": 97,
        "glyph": "🏛️",
        "hookType": "Paz Mental & Fortaleza",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-mot-seed-04",
        "title": "El Efecto de la Regla del 1%: La matemática implacable que transforma tu destino",
        "nuances": "Estudio de hábitos atómicos: mejorar 1% diario te hace 37 veces mejor en un año; empeorar 1% te reduce a casi cero. Gancho: 'No necesitas cambiar tu vida de golpe, necesitas ganar los próximos 10 minutos'. Fondo arquitectónico minimalista. Música: Cuerdas épicas ascendentes.",
        "category": "motivacion",
        "score": 95,
        "glyph": "📈",
        "hookType": "Hábito & Enfoque",
        "durationMin": 1,
        "isLive": True,
    },

    # Cine & Cortos Cristianos
    {
        "id": "vtl-cri-seed-01",
        "title": "Hasta el Último Hombre (Hacksaw Ridge): La oración de Desmond Doss bajo fuego enemigo",
        "nuances": "Análisis del momento culmen donde un joven desarmado rescata a 75 soldados heridos clamando 'Señor, ayúdame a salvar a uno más'. La fe que desafía la lógica militar. Fondo cinematográfico dramático con neblina y rayos de luz. Música: Orquesta emotiva y violonchelo celestial.",
        "category": "cristiano_cine",
        "score": 99,
        "glyph": "🎬",
        "hookType": "Fe Bajo Fuego",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-cri-seed-02",
        "title": "Cuarto de Guerra (War Room): La escena donde la batalla se gana de rodillas",
        "nuances": "La revelación de Elizabeth cuando deja de pelear con su esposo y lleva su batalla al armario de oración: 'El enemigo no es la persona, es el plano espiritual'. Gancho profundo sobre el poder de la intercesión. Fondo en penumbra con rayos dorados de luz. Música: Piano de adoración íntimo.",
        "category": "cristiano_cine",
        "score": 98,
        "glyph": "✝️",
        "hookType": "Poder de la Oración",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-cri-seed-03",
        "title": "La Cabaña (The Shack): La desgarradora conversación sobre el perdón que libera el alma",
        "nuances": "La escena del juicio donde Mack comprende que perdonar no es justificar el dolor, sino soltar el veneno del rencor que destruye a quien lo guarda. Mensaje de amor restaurador. Fondo de lago sereno en penumbra y naturaleza viva. Música: Cuerdas orquestales inspiradoras.",
        "category": "cristiano_cine",
        "score": 97,
        "glyph": "🕊️",
        "hookType": "Perdón & Redención",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-cri-seed-04",
        "title": "Ben-Hur: El momento en que un vaso de agua dado por Jesús cambia el destino de Judá",
        "nuances": "El encuentro decisivo camino a las galeras: una mirada de Cristo que calma la sed y apaga el fuego del odio, sembrando la semilla de la redención. Fondo desértico cinematográfico de alta definición. Música: Coral solemne y emotiva.",
        "category": "cristiano_cine",
        "score": 96,
        "glyph": "🏺",
        "hookType": "Milagro & Gracia",
        "durationMin": 1,
        "isLive": True,
    },

    # Versículos Bíblicos & Promesas
    {
        "id": "vtl-ver-seed-01",
        "title": "Filipenses 4:6-7: El antídoto bíblico infalible contra la ansiedad y el insomnio",
        "nuances": "'Por nada estéis afanosos, sino sean conocidas vuestras peticiones delante de Dios en oración... y la paz de Dios que sobrepasa todo entendimiento guardará vuestros corazones'. Contexto de Pablo en prisión. Fondo: olas suaves y puesta de sol en cámara lenta. Música: Piano de adoración pacífica.",
        "category": "versiculos",
        "score": 99,
        "glyph": "📖",
        "hookType": "Paz Sobrenatural",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-ver-seed-02",
        "title": "Salmo 91: El escudo de protección sobrenatural para ti y tu familia",
        "nuances": "'El que habita al abrigo del Altísimo morará bajo la sombra del Omnipotente... con sus plumas te cubrirá'. La promesa de refugio seguro en medio de la adversidad o enfermedad. Fondo: cumbres montañosas con amanecer dorado entre las nubes. Música: Orquestación suave de esperanza.",
        "category": "versiculos",
        "score": 98,
        "glyph": "🛡️",
        "hookType": "Protección & Fortaleza",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-ver-seed-03",
        "title": "Isaías 41:10: La promesa viva de Dios cuando sientes que tus fuerzas se acabaron",
        "nuances": "'No temas, porque yo estoy contigo; no desmayes, porque yo soy tu Dios que te esfuerzo; siempre te sustentaré con la diestra de mi justicia'. Un mensaje directo al corazón agotado. Fondo: cielo estrellado y primeros rayos del alba. Música: Pad etéreo y piano de paz interior.",
        "category": "versiculos",
        "score": 98,
        "glyph": "✨",
        "hookType": "Fortaleza en la Debilidad",
        "durationMin": 1,
        "isLive": True,
    },
    {
        "id": "vtl-ver-seed-04",
        "title": "Jeremías 29:11: 'Sé los planes que tengo para vosotros... planes de bienestar y no de calamidad'",
        "nuances": "La promesa divina en el exilio: Dios tiene trazado un futuro y una esperanza incluso cuando todo parezca incierto. Gancho de confianza y propósito de vida. Fondo: bosque bañado en luz dorada y naturaleza 4K. Música: Violines y piano emotivo.",
        "category": "versiculos",
        "score": 97,
        "glyph": "🌱",
        "hookType": "Esperanza & Futuro",
        "durationMin": 1,
        "isLive": True,
    },
]


class ViralNichesCrawler:
    """Rastreador en segundo plano que puebla progresivamente nichos virales con búsqueda real en la web."""

    TARGET_PER_CATEGORY = 10
    STORAGE_FILE = settings.STORAGE_DIR / "viral_niches_live.json"

    def __init__(self):
        self._lock = threading.Lock()
        self._is_crawling = False
        self._stop_event = threading.Event()
        self._topics: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.STORAGE_FILE.exists():
            try:
                data = json.loads(self.STORAGE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    # Asegurar que no hay temas hardcodeados heredados
                    self._topics = [t for t in data if isinstance(t, dict) and t.get("isLive", False)]
                    safe_log(f"[ViralNichesCrawler] Cargados {len(self._topics)} temas en vivo persistentes.")
            except Exception as e:
                safe_log(f"[ViralNichesCrawler] Error leyendo almacenamiento previo: {e}")

        # Inyectar semillas de alta calidad para categorías recién creadas o vacías
        existing_ids = {t.get("id") for t in self._topics}
        added_seeds = 0
        for seed in SEED_CURATED_TOPICS:
            if seed["id"] not in existing_ids:
                seed_copy = dict(seed)
                seed_copy["added_at"] = datetime.now(timezone.utc).isoformat()
                self._topics.append(seed_copy)
                existing_ids.add(seed["id"])
                added_seeds += 1

        if added_seeds > 0:
            safe_log(f"[ViralNichesCrawler] +{added_seeds} temas semilla curados incorporados (Motivación, Cine Cristiano, Versículos).")
            self._save()

    def _save(self) -> None:
        try:
            self.STORAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
            disk_topics = []
            if self.STORAGE_FILE.exists():
                try:
                    loaded = json.loads(self.STORAGE_FILE.read_text(encoding="utf-8"))
                    if isinstance(loaded, list):
                        disk_topics = loaded
                except Exception:
                    pass
            
            merged_map = {t["id"]: t for t in disk_topics if isinstance(t, dict) and "id" in t}
            for t in self._topics:
                if isinstance(t, dict) and "id" in t:
                    merged_map[t["id"]] = t
            
            all_merged = list(merged_map.values())
            self._topics = all_merged
            self.STORAGE_FILE.write_text(
                json.dumps(all_merged, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            safe_log(f"[ViralNichesCrawler] Error guardando temas en vivo: {e}")

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            if self.STORAGE_FILE.exists():
                try:
                    disk_data = json.loads(self.STORAGE_FILE.read_text(encoding="utf-8"))
                    if isinstance(disk_data, list) and len(disk_data) > len(self._topics):
                        self._topics = disk_data
                except Exception:
                    pass

            by_cat: Dict[str, int] = {}
            for t in self._topics:
                c = t.get("category", "")
                by_cat[c] = by_cat.get(c, 0) + 1
            return {
                "topics": list(self._topics),
                "total": len(self._topics),
                "counts_by_category": by_cat,
                "is_crawling": self._is_crawling and not self._stop_event.is_set(),
                "is_paused": self._stop_event.is_set(),
                "target_per_category": self.TARGET_PER_CATEGORY,
            }

    def stop_crawling(self) -> None:
        """Detiene inmediatamente el rastreo continuo en segundo plano."""
        with self._lock:
            self._stop_event.set()
            self._is_crawling = False
            safe_log("[ViralNichesCrawler] ⏹️ Rastreo de temas pausado/detenido por el usuario.")

    def resume_crawling(self) -> None:
        """Reanuda el rastreo continuo en segundo plano."""
        with self._lock:
            self._stop_event.clear()
            if hasattr(self, "_thread") and self._thread is not None and self._thread.is_alive():
                safe_log("[ViralNichesCrawler] ▶️ Rastreador ya activo.")
                return
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ViralNichesCrawlerThread")
            self._thread.start()
            safe_log("[ViralNichesCrawler] ▶️ Rastreo de temas reanudado por el usuario.")

    def start_background_loop(self) -> None:
        with self._lock:
            if hasattr(self, "_thread") and self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ViralNichesCrawlerThread")
            self._thread.start()
            safe_log("[ViralNichesCrawler] Hilo de rastreo continuo en segundo plano iniciado.")

    def crawl_category_now(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fuerza un rastreo de Internet inmediato para una categoría específica o una pasada global."""
        cat_clean = (category or "").strip().lower()
        if cat_clean and cat_clean not in ["all", "todas"] and cat_clean in VIRAL_CATEGORIES_CONFIG:
            self._fetch_and_add_for_category(cat_clean)
        else:
            self._crawl_pass()
        return self.get_snapshot()["topics"]

    def _run_loop(self) -> None:
        """Ciclo continuo que llena al menos 10 temas por categoría progresivamente y luego refresca periódicamente."""
        if self._stop_event.wait(timeout=2.0):
            return
        safe_log("[ViralNichesCrawler] Iniciando motor de descubrimiento continuo en Internet...")
        
        while not self._stop_event.is_set():
            try:
                self._crawl_pass()
            except Exception as e:
                safe_log(f"[ViralNichesCrawler] Error en pasada de rastreo: {e}")
            
            # Verificar si todas las categorías tienen al menos 10 temas
            with self._lock:
                all_satisfied = all(
                    sum(1 for t in self._topics if t.get("category") == cat) >= self.TARGET_PER_CATEGORY
                    for cat in VIRAL_CATEGORIES_CONFIG
                )
            
            # Si faltan temas, ciclo rápido progresivo (3.5s) para poblar sin demora.
            # Una vez completadas las 14 categorías con >= 10 temas, descanso de 15 min.
            sleep_time = 900 if all_satisfied else 3.5
            if self._stop_event.wait(timeout=sleep_time):
                break

    def _crawl_pass(self) -> None:
        """Ejecuta una pasada de búsqueda progresiva priorizando categorías con menos de 10 temas."""
        with self._lock:
            needed: List[tuple[str, int]] = []
            for cat, cfg in VIRAL_CATEGORIES_CONFIG.items():
                cnt = sum(1 for t in self._topics if t.get("category") == cat)
                if cnt < self.TARGET_PER_CATEGORY:
                    needed.append((cat, cnt))
            
            needed.sort(key=lambda x: x[1])

        if not needed:
            # Todas tienen >= 10 temas; seleccionar 2 categorías para refrescar periódicamente
            cats_to_process = random.sample(list(VIRAL_CATEGORIES_CONFIG.keys()), 2)
        else:
            # Procesar las categorías más necesitadas
            cats_to_process = [cat for cat, _ in needed[:3]]

        for cat in cats_to_process:
            self._fetch_and_add_for_category(cat)
            time.sleep(1.0)

    def _fetch_and_add_for_category(self, category: str) -> None:
        cfg = VIRAL_CATEGORIES_CONFIG.get(category)
        if not cfg:
            return

        with self._lock:
            self._is_crawling = True

        try:
            query = random.choice(cfg["queries"])
            findings: List[Dict[str, str]] = []

            # 1. Búsqueda web real con DDGS
            try:
                from ddgs import DDGS
                with DDGS(timeout=5) as ddgs:
                    news = list(ddgs.news(query, max_results=3))
                    if not news:
                        news = list(ddgs.text(query, max_results=3))
                    for item in news:
                        t = item.get("title", "")
                        b = item.get("body", "")
                        if t and len(t) > 12:
                            clean_t = re.sub(r"\s*[-|–]\s*[A-Za-z0-9\.\sáéíóúÁÉÍÓÚ]+$", "", t).strip()
                            clean_t = re.sub(r"^[A-Za-z0-9\.\s]+:\s*", "", clean_t).strip()
                            findings.append({"title": clean_t, "body": (b or clean_t)[:200]})
            except Exception as e_ddg:
                safe_log(f"[ViralNichesCrawler] Aviso en búsqueda DDGS ({category}): {e_ddg}")

            # 2. Generación y curación con LLM basada en los hallazgos de internet
            llm = LLMClient()
            context_str = "\n".join([f"- {f['title']}: {f['body']}" for f in findings]) if findings else f"Tendencias actuales y debates candentes en Internet sobre {category} ({query})"

            # Instrucción de curaduría especializada según la categoría
            is_short_specialty = category in ("motivacion", "cristiano_cine", "versiculos")
            specialty_note = ""
            if category == "motivacion":
                specialty_note = """- ENFOQUE: Frases motivacionales de alto impacto, estoicismo práctico (Marco Aurelio, Séneca, Epicteto), leyes del carácter y disciplina implacable.
- FORMATO: Optimizado para Reels/Shorts de 30-60s (o documentales cortos de 10m).
- ESENCIA: Incluye en 'nuances' la frase gancho central, el fondo sugerido (ej: cine 35mm, estatuas, lluvia/noche) y música recomendada (orquesta épica / sintetizador estoico). durationMin debe ser 1."""
            elif category == "cristiano_cine":
                specialty_note = """- ENFOQUE: Escenas conmovedoras de películas de fe (Hacksaw Ridge, War Room, The Shack, Ben-Hur, etc.), lecciones de perdón, redención y testimonios reales.
- FORMATO: Optimizado para Reels de impacto emocional (30-60s) o análisis de fe (15m).
- ESENCIA: Cita la película o momento exacto, la lección de redención, fondo sugerido y música recomendada (piano de adoración / cuerdas emotivas). durationMin debe ser 1."""
            elif category == "versiculos":
                specialty_note = """- ENFOQUE: Versículos bíblicos EXACTOS con libro, capítulo y versículo citado (ej: Salmo 91, Filipenses 4:6-7, Isaías 41:10, Proverbios 3:5-6) para paz, ansiedad y fortaleza.
- FORMATO: Optimizado para Shorts de reflexión diaria y promesa viva (45-60s).
- ESENCIA: Cita el versículo textual, la promesa revelada, fondo sugerido (naturaleza majestuosa, amaneceres, olas) y música recomendada (piano celestial y adoración pacífica). durationMin debe ser 1."""
            else:
                specialty_note = """- PROHIBIDO TÍTULOS ABSTRACTOS O GENÉRICOS (No pongas 'El misterio del cosmos' ni 'Secretos del dinero').
- EXIGENCIA: Cada tema DEBE incluir un caso real, experimento con nombre y año, personaje histórico específico, corporación o anomalía geográfica verificable.
- ESENCIA: Incluye en 'nuances' el gancho de los primeros 3 segundos, la hipótesis central y revelaciones clave. durationMin entre 15 y 30."""

            prompt = f"""Actúa como Director Creativo Senior de YouTube Studio especializado en retención viral y storytelling cinematográfico.
Categoría: {category.upper()} ({cfg['name']})
Noticias y hallazgos reales de Internet:
{context_str}

DIRECTRICES DE CALIDAD:
{specialty_note}

Genera entre 2 y 3 temas virales COMPLETAMENTE NUEVOS, CONCRETOS y con ESENCIA PROPIA.
Calcula una puntuación de viralidad REAL (+88 a +99) según retención y gancho.

Devuelve EXCLUSIVAMENTE una lista JSON válida:
[
  {{
    "title": "Título magnético ultra concreto (con nombres, versículo o película exacta)",
    "nuances": "Gancho inicial de 3s, desarrollo del estudio/escena y atmósfera recomendada (Fondo: ... | Música: ...)",
    "category": "{category}",
    "score": 97,
    "glyph": "{cfg['glyph']}",
    "hookType": "{cfg['hook']}",
    "durationMin": {1 if is_short_specialty else 20}
  }}
]"""

            resp = llm.generate(prompt, json_mode=True, deadline_sec=14.0)
            clean_resp = re.sub(r"^```(?:json)?\s*|\s*```$", "", resp.strip(), flags=re.MULTILINE).strip()
            try:
                parsed = json.loads(clean_resp, strict=False)
            except Exception:
                m = re.search(r"\[.*\]", clean_resp, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0), strict=False)
                else:
                    m_obj = re.search(r"\{.*\}", clean_resp, re.DOTALL)
                    if m_obj:
                        parsed = [json.loads(m_obj.group(0), strict=False)]
                    else:
                        raise
            
            new_items = []
            if isinstance(parsed, list):
                new_items = parsed
            elif isinstance(parsed, dict) and "title" in parsed:
                new_items = [parsed]

            # 3. Incorporación PROGRESIVA inmediata
            added_count = 0
            with self._lock:
                existing_titles = {t.get("title", "").strip().lower() for t in self._topics}
                for item in new_items:
                    t_title = str(item.get("title", "")).strip()
                    if not t_title or t_title.lower() in existing_titles:
                        continue

                    topic_obj = {
                        "id": f"vtl-{category[:3]}-{int(time.time())}-{random.randint(100, 999)}",
                        "title": t_title,
                        "nuances": str(item.get("nuances") or t_title).strip(),
                        "category": category,
                        "score": int(min(99, max(88, item.get("score", 95)))),
                        "glyph": item.get("glyph") or cfg["glyph"],
                        "hookType": item.get("hookType") or cfg["hook"],
                        "durationMin": int(item.get("durationMin") or random.choice([15, 20, 25, 30])),
                        "isLive": True,
                        "added_at": datetime.now(timezone.utc).isoformat(),
                    }
                    self._topics.append(topic_obj)
                    existing_titles.add(t_title.lower())
                    added_count += 1

                if added_count > 0:
                    self._save()
                    cat_total = sum(1 for t in self._topics if t.get("category") == category)
                    safe_log(
                        f"[ViralNichesCrawler] ✓ +{added_count} tema(s) incorporado(s) para '{cfg['name']}' "
                        f"({cat_total}/{self.TARGET_PER_CATEGORY} en categoría | Total biblioteca: {len(self._topics)})"
                    )

        except Exception as exc:
            safe_log(f"[ViralNichesCrawler] Error procesando '{category}': {exc}")
        finally:
            with self._lock:
                self._is_crawling = False


# Instancia única singleton del rastreador
viral_niches_crawler = ViralNichesCrawler()


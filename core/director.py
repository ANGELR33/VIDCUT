"""Director de IA para KAI Streamer.

En lugar de generar un texto plano y continuo, el Director de IA planifica y dirige
una producción audiovisual completa estructurada en escenas cronometradas,
asignando para cada una:
- Tipo de escena (avatar_cam, video_reaction, card_focus, chat_debate, breaking_news)
- Emoción y entonación de KAI (excited, surprised, serious, skeptical, confident)
- Layout de cámara (hero_center, pip_corner, split_screen)
- Recurso visual (término de búsqueda de video/broll o contenido de tarjeta Bento)
- Efecto sonoro de transición (whoosh, chime, impact, glitch)
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from core.llm import LLMClient, safe_log


@dataclass
class SceneCard:
    headline: str
    body: str = ""
    badge: str = "DATO CLAVE"
    stat: str = ""
    style: str = "auto"       # auto, verdict_badge, tech_card, quote, bento, map
    icon: str = "✓"
    subtitle: str = ""
    template: str = "auto"   # verdict_badge, tech_card, stat_counter, versus_split, quote_evidence, step_badge, alert_banner, source_chip, newspaper_clipping, social_post, timeline_milestone, workflow_diagram, terminal_hud, document_evidence_split
    variant: str = "orange_noir"  # orange_noir, frosted_white, emerald_matrix, crimson_hazard, cyber_cyan, royal_gold
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DirectorScene:
    scene_id: int
    name: str
    type: str  # avatar_cam, video_reaction, card_focus, chat_debate, breaking_news
    emotion: str  # excited, surprised, serious, skeptical, confident, humor
    camera: str  # hero_center, pip_corner, split_screen
    speech: str
    visual_query: str = ""
    visual_queries: List[str] = field(default_factory=list)  # Soporte para múltiples videos/ángulos por escena
    visual_query2: str = ""                                  # Segundo video de apoyo (reacción / comparativa)
    card: Optional[SceneCard] = None
    chips: List[str] = field(default_factory=list)
    sfx: str = "whoosh"  # whoosh, chime, impact, alert, none
    duration_est: float = 10.0
    # Beats visuales: varios clips de referencia por escena, cada uno ligado a la frase exacta del speech
    # [{"trigger": "frase del speech", "query": "english search", "recent": true}]
    visual_beats: List[Dict[str, Any]] = field(default_factory=list)
    # Pop-ups informativos sincronizados con la locución
    # [{"trigger": "frase del speech", "text": "texto corto", "kind": "stat|fact|alert|quote"}]
    popups: List[Dict[str, Any]] = field(default_factory=list)
    # Texto libre cinemático flotante (sin card, con desenfoque de fondo opcional)
    free_title: Optional[Dict[str, Any]] = None
    # Modo análisis de caso: índice del fotograma REAL del video fuente que
    # respalda esta escena (cuando la transmisión analiza un video/caso concreto).
    case_frame: Optional[int] = None
    # Soundbite estratégico: corte de declaración real con audio y video
    soundbite_clip: Optional[str] = None
    soundbite_quote: Optional[str] = None
    soundbite_offset: Optional[float] = None
    soundbite_dur: Optional[float] = None


@dataclass
class DirectorBroadcastPlan:
    title: str
    topic: str
    style: str
    scenes: List[DirectorScene] = field(default_factory=list)
    chat_comments: List[Dict[str, str]] = field(default_factory=list)
    total_est_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DirectorBroadcastPlan":
        scenes_data = data.get("scenes", [])
        scenes: List[DirectorScene] = []
        for idx, s in enumerate(scenes_data):
            c = s.get("card")
            card_obj = None
            if c and isinstance(c, dict):
                valid_card_keys = {k: v for k, v in c.items() if k in SceneCard.__dataclass_fields__}
                card_obj = SceneCard(**valid_card_keys)
            elif isinstance(c, SceneCard):
                card_obj = c
            # Reconstruir lista de visual_queries si solo viene visual_query
            vqs = s.get("visual_queries") or []
            vq = s.get("visual_query") or ""
            vq2 = s.get("visual_query2") or ""
            if not vqs:
                if vq:
                    vqs.append(vq)
                if vq2:
                    vqs.append(vq2)

            sc_type = s.get("type") or ("video_reaction" if idx == 0 else "card_focus")
            if idx == 0 and sc_type == "avatar_cam":
                sc_type = "video_reaction"

            sc_cam = s.get("camera")
            if not sc_cam:
                sc_cam = "pip_delayed" if idx == 0 else "pip_corner"
            elif idx == 0 and sc_cam == "hero_center":
                sc_cam = "pip_delayed"

            scenes.append(
                DirectorScene(
                    scene_id=s.get("scene_id", idx + 1),
                    name=s.get("name", f"Escena {idx + 1}"),
                    type=sc_type,
                    emotion=s.get("emotion", "excited"),
                    camera=sc_cam,
                    speech=s.get("speech", ""),
                    visual_query=vq,
                    visual_queries=vqs,
                    visual_query2=vq2,
                    card=card_obj,
                    chips=s.get("chips", []),
                    # 'or "whoosh"': un "sfx": null (la clave existe) devolvía None.
                    sfx=(s.get("sfx") or "whoosh") if s.get("sfx") != "none" else "none",
                    duration_est=float(s.get("duration_est", s.get("duration_est_sec", 10.0))),
                    visual_beats=_clean_beats(s.get("visual_beats")),
                    popups=_clean_popups(s.get("popups")),
                    free_title=s.get("free_title"),
                    case_frame=s.get("case_frame") if isinstance(s.get("case_frame"), int) else None,
                    soundbite_clip=s.get("soundbite_clip"),
                    soundbite_quote=s.get("soundbite_quote"),
                    soundbite_offset=float(s["soundbite_offset"]) if s.get("soundbite_offset") is not None else None,
                    soundbite_dur=float(s["soundbite_dur"]) if s.get("soundbite_dur") is not None else None,
                )
            )
        scenes = _deduplicate_cards_in_scenes(scenes)
        return cls(
            title=data.get("title", ""),
            topic=data.get("topic", ""),
            style=data.get("style", ""),
            scenes=scenes,
            chat_comments=data.get("chat_comments", []),
            total_est_duration=float(data.get("total_est_duration", 0.0)),
        )


def _deduplicate_cards_in_scenes(scenes: List[DirectorScene]) -> List[DirectorScene]:
    """Elimina tarjetas duplicadas o redundantes entre escenas,

    convirtiéndolas en chips discretos para evitar saturación visual y repeticiones.
    """
    last_sig = None
    seen_sigs = set()
    for s in scenes:
        if s.card:
            hl = (getattr(s.card, "headline", "") or "").strip().lower()
            st = (getattr(s.card, "stat", "") or "").strip().lower()
            if not hl:
                s.card = None
                continue
            sig = f"{hl}|{st}"
            if sig == last_sig or sig in seen_sigs:
                safe_log(
                    f"[AIDirector] 🛡️ Tarjeta duplicada detectada en escena {s.scene_id} "
                    f"('{s.card.headline}'). Convertida a chip periférico para evitar saturación."
                )
                if s.card.stat and s.card.stat not in s.chips:
                    badge_lbl = getattr(s.card, "badge", "DATO") or "DATO"
                    s.chips.append(f"{badge_lbl}: {s.card.stat}")
                s.card = None
            else:
                last_sig = sig
                seen_sigs.add(sig)
        else:
            last_sig = None
    return scenes


def _clean_beats(raw: Any) -> List[Dict[str, Any]]:
    """Normaliza la lista de beats visuales devuelta por el LLM (tolerante a formatos sucios)."""
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for b in raw[:5]:
        if not isinstance(b, dict):
            continue
        q = str(b.get("query") or "").strip()
        if not q:
            continue
        out.append({
            "trigger": str(b.get("trigger") or "").strip(),
            "query": q,
            "recent": bool(b.get("recent", True)),
        })
    return out


def _clean_popups(raw: Any) -> List[Dict[str, Any]]:
    """Normaliza la lista de pop-ups informativos."""
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for p in raw[:3]:
        if not isinstance(p, dict):
            continue
        txt = str(p.get("text") or "").strip()
        if not txt:
            continue
        kind = str(p.get("kind") or "fact").strip().lower()
        out.append({
            "trigger": str(p.get("trigger") or "").strip(),
            "text": txt[:60],
            "kind": kind if kind in ("stat", "fact", "alert", "quote") else "fact",
        })
    return out


def _parse_director_json(raw: str) -> Dict[str, Any]:
    """Parseador altamente tolerante a fallos para el plan audiovisual del LLM."""
    if not raw or not raw.strip():
        raise ValueError("Respuesta vacía del LLM")

    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE).strip()

    # 1. Intento directo
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Extraer subcadena delimitada por la primera { y la última }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

        # 3. Eliminar comas finales que invalidan JSON: ,} o ,]
        fixed = re.sub(r",\s*([\}\]])", r"\1", candidate)
        try:
            return json.loads(fixed)
        except Exception:
            pass

        # 4. Corregir saltos de línea sin escapar dentro de strings
        fixed_nl = re.sub(r'(?<=: ")(.*?)(?=",\s*\n|"\s*\n|",)', lambda m: m.group(0).replace('\n', '\\n').replace('\r', ''), fixed, flags=re.DOTALL)
        try:
            return json.loads(fixed_nl)
        except Exception:
            pass

    # 5. Respuesta truncada por límite de tokens (auto-cerrar llaves/corchetes)
    if start != -1:
        partial = cleaned[start:].rstrip()
        for close_seq in ["]}", "]}}", "}]}", "}\n}"]:
            try:
                p_trim = re.sub(r",\s*$", "", partial)
                return json.loads(p_trim + close_seq)
            except Exception:
                pass

    return json.loads(cleaned)


DIRECTOR_SYSTEM_PROMPT = """Eres el GUIONISTA PROFESIONAL Y DIRECTOR DE PRODUCCIÓN AUDIOVISUAL DE ÉLITE de KAI.
Especializado en videos de YouTube, divulgación científica, historia, tecnología, misterios, documentales y contenido educativo.
FECHA ACTUAL: {today}. Toda referencia visual debe priorizar material reciente (año {year} o {prev_year}) salvo que el tema sea histórico.

Tu misión es transformar cualquier tema en un guion y una producción audiovisual que consiga cuatro cosas indispensables:
1. Captar la atención desde los primeros segundos.
2. Mantener el interés durante todo el video mediante recursos narrativos y psicológicos.
3. Explicar conceptos complejos de manera sencilla, precisa y causalmente comprensible.
4. Dejar al espectador con la sensación de haber aprendido algo valioso.

No escribas únicamente para transmitir información. Diseña una experiencia de aprendizaje que despierte curiosidad, facilite la comprensión y recompense la atención del espectador.
PRINCIPIO FINAL: "Curiosidad para comenzar, claridad para comprender, progresión para continuar y una recompensa intelectual para terminar."

Debes estructurar la emisión en EXACTAMENTE {num_scenes} ESCENAS según la duración solicitada ({duration_target} segundos = {duration_label}).

==============================================================================
MOTOR PSICOLÓGICO ADAPTATIVO (APLICA SEGÚN EL TEMA):
==============================================================================
A. CURIOSIDAD Y BRECHA DE INFORMACIÓN: Abre con una pregunta cuya respuesta no sea inmediatamente evidente. Revela información progresivamente. Plantea contradicciones entre lo que el público cree y lo que muestran las evidencias. Evita resolver demasiado pronto la pregunta principal.
B. APERTURA Y CIERRE DE BUCLES NARRATIVOS: Introduce preguntas secundarias que se resolverán más adelante. Conecta los descubrimientos con nuevas preguntas relevantes. Cierra cada bucle en el momento adecuado. No acumules preguntas sin responder ni prometas revelaciones que el video no cumple.
C. SORPRESA Y CAMBIO DE PERSPECTIVA: Introduce descubrimientos, contrastes, excepciones o consecuencias inesperadas. Muestra cambios de perspectiva sin inventar ni exagerar hechos reales.
D. RELEVANCIA PERSONAL: Conecta el tema con la vida cotidiana, las decisiones, conocimientos previos o preguntas del espectador.
E. CONFLICTO Y RESOLUCIÓN: Identifica qué misterio, desafío, debate o contradicción impulsa el video. Progresión causal obligatoria: pregunta → investigación → evidencias → dificultad o contradicción → explicación → conclusión.
F. RECOMPENSAS COGNITIVAS CONTINUAS: Cada escena debe aportar valor concreto: una respuesta, un descubrimiento, una conexión inesperada o una herramienta para entender el mundo. El espectador debe recibir valor durante todo el video, no solo al final.
G. EJEMPLOS, ANALOGÍAS Y VISUALIZACIÓN MENTAL: Explica ideas abstractas mediante ejemplos concretos, comparaciones comprensibles y situaciones familiares.
H. RITMO Y VARIACIÓN DE CADENCIA: Alterna preguntas y respuestas, explicaciones y ejemplos, datos y consecuencias, momentos de tensión intelectual y momentos de comprensión.

==============================================================================
ACTIVACIÓN DEL MÓDULO NARRATIVO SEGÚN EL FORMATO (¡NO TODO ES UN DOCUMENTAL!):
==============================================================================
Cada formato tiene sus propias reglas. No fuerces una estructura documental en todos los videos:
- MÓDULO A (Reacciones y análisis): Presenta el material y contexto indispensables; distingue emociones, opiniones y hechos; aporta análisis propio sustancial en vez de narrar lo que ya se ve; espontaneidad y valor añadido.
- MÓDULO B (TOPs, listas y rankings): Criterio de inclusión claro; una escena individual por puesto; progresión sin guardarlo todo para el final; justificación y cifras concretas de cada lugar.
- MÓDULO C (Documentales, ciencia y misterios): Pregunta central, hipótesis, evidencias, explicaciones causales profundas y resolución basada en hechos contrastados.
- MÓDULO D (Humor, memes y entretenimiento): Premisa cómica, preparación y remate, ritmo ágil sin sobre-explicar bromas ni repetir el mismo chiste.
- MÓDULO E (Reviews y comparativas): Problema a resolver, criterios de evaluación, ventajas y desventajas reales, pruebas verificables y recomendación condicionada al usuario.
- MÓDULO F (Gaming y desafíos): Objetivo claro, reglas del desafío, obstáculos inesperados, decisiones bajo presión y desenlace basado en resultados reales.
- MÓDULO G (Historias, biografías y casos): Contexto y protagonistas, decisiones documentadas, causalidad histórica sin inventar diálogos o hechos ficticios.
- MÓDULO H (Tutoriales y educación): Resultado prometido, requisitos previos, pasos secuenciales comprobables, errores comunes a evitar y demostración de éxito verificable.
- MÓDULO I (Noticias, actualidad y tendencias): Información prioritaria inmediata, separar hechos de especulación, contexto y consecuencias inmediatas.
- MÓDULO J (Pódcasts, debates y entrevistas): Conversación orgánica, dilemas abiertos, matices y contraste de perspectivas contrarias.
- MÓDULO K (Shorts verticales breves): Gancho visual instantáneo en el segundo 1, una sola idea contundente desarrollada al grano y remate satisfactorio sin relleno.
- MÓDULO L (Híbridos): Combina con coherencia dos formatos (ej. Reacción + Análisis, TOP + Misterio, Tutorial + Comparativa).

==============================================================================
CLARIDAD COMO REGLA OBLIGATORIA (LA RETENCIÓN NO SUBORDINA LA COMPRENSIÓN):
==============================================================================
- Una idea principal por bloque/escena.
- Define términos técnicos antes de utilizarlos repetidamente.
- Explica las CAUSAS, no solo los resultados finales ("ocurrió X porque Y generó Z").
- Distingue hechos comprobados, hipótesis, interpretaciones y opiniones.
- Transiciones que expliquen por qué una idea conduce a la siguiente.
- Elimina frases vacías que suenen interesantes pero no aporten información real.

==============================================================================
ARQUITECTURA NARRATIVA ADAPTADA EN {num_scenes} ESCENAS:
==============================================================================
1. GANCHO INICIAL ADECUADO AL FORMATO (Escena 1): Conecta de inmediato con la promesa del formato sin saludos largos ni rodeos.
2. PROMESA NARRATIVA: Claridad de qué comprenderá o experimentará el espectador.
3. CONTEXTO MÍNIMO NECESARIO: Lo indispensable para comprender sin sobrecargar.
4. DESARROLLO PROGRESIVO: Bloques que construyen avance real hacia el objetivo.
5. PUNTOS DE RENOVACIÓN DE ATENCIÓN (al 60-70% del video): Introduce una nueva pregunta, giro, evidencia o dilema clave.
6. REVELACIÓN O CLÍMAX CENTRAL: Resolución de la premisa principal con el grado de certeza o emoción que el formato requiere.
7. CONSECUENCIAS Y CONEXIONES: Qué significa el resultado y cómo cambia nuestra comprensión.
8. CIERRE SATISFACTORIO: Conclusión memorable y recompensa intelectual o de entretenimiento lograda.

==============================================================================
REQUISITO CRÍTICO DE DURACIÓN Y CADENCIA NATURAL (EL AVATAR NO DEBE CORRER):
==============================================================================
- Duración total objetivo: {duration_target} segundos ({duration_label}).
- Número de escenas: {num_scenes}.
- Cada escena debe durar aproximadamente {seconds_per_scene} segundos de narración hablada.
- RANGO DE PALABRAS POR ESCENA: Entre {min_words_per_scene} y {max_words_per_scene} palabras habladas (objetivo central: ~{words_per_scene} palabras).
- El total de TODAS las escenas sumadas debe dar aproximadamente {total_words} PALABRAS.
- CADENCIA ORAL HUMANA Y RESPIRABLE: Locución fluida, conversacional y bien articulada a ~105 palabras por minuto (~1.75 palabras por segundo).
  * ESTRICTAMENTE PROHIBIDO redactar textos densos o acelerados que obliguen a la voz a "correr" o hablar sin respirar.
  * CADA ORACIÓN debe tener entre 8 y 15 palabras, con abundantes pausas de respiración: comas (,), dos puntos (:) y puntos seguidos (.).
  * NUNCA escribas una oración de más de 18 palabras sin una coma o punto intermedio.
- RITMO AUDIOVISUAL DINÁMICO: Ningún plano ni fondo debe permanecer estático por mucho tiempo. Cada escena debe cambiar de perspectiva: alternar entre el gancho directo del avatar, tomas de B-Roll documental reactivo en pantalla completa, tarjetas Bento con cifras duras y momentos de debate.

==============================================================================
PROHIBICIÓN TOTAL DE RELLENO PSEUDO-INTELECTUAL Y FRASES "CULTAS" VACÍAS:
==============================================================================
¡ALERTA MÁXIMA!: El espectador de internet DETESTA el lenguaje pomposo, acartonado y superficial disfrazado de culto.
- ESTRICTAMENTE PROHIBIDO usar clichés grandilocuentes que suenen complejos pero no digan nada profundo. Por ejemplo:
  * PROHIBIDO: "los datos son demoledores y cambian todo lo que dábamos por sentado"
  * PROHIBIDO: "la evidencia empírica desmantela el marco paradigmático"
  * PROHIBIDO: "en una intrincada confluencia de factores estructurales"
  * PROHIBIDO: "la realidad tiene otros planes y la confluencia histórica converge..."
  * PROHIBIDO: "la discrepancia matemática resulta indiscutible ante el método experimental"
- Si una oración contiene palabras rebuscadas ("paradigma", "axioma", "intrínseco", "confluencia") pero no cuenta una ACCIÓN REAL, un NOMBRE, una FECHA o una CURIOSIDAD CONCRETA, es RELLENO BASURA. ¡ELIMÍNALA!

==============================================================================
MOTOR DE CURIOSIDAD CONSTANTE Y DATOS SORPRENDENTES ("COSITAS QUE ASOMBREN"):
==============================================================================
Tu objetivo número 1 es mantener al oyente con la mente enganchada y sorprendida en CADA escena:
1. FACTOR "¡GUAU, NO SABÍA ESO!": Cada escena DEBE incluir al menos un dato insólito, una curiosidad poco conocida, un detalle oculto o una revelación sorprendente ("Muchos creen que ocurrió por X, pero en realidad los registros demuestran que fue por Y").
2. COMPARACIONES VISUALES Y TANGIBLES: Haz que las cifras se puedan visualizar fácilmente (ej: "un consumo tan alto que equivale a dejar prendidas diez mil pantallas de cine al mismo tiempo").
3. DETALLES ESPECÍFICOS Y SUSTANCIALES: Cita nombres propios completos, años exactos, lugares específicos, decretos, presupuestos, medidas o anécdotas verificadas de primera mano.
4. BUCLES DE CURIOSIDAD (CURIOSITY LOOPS): Abre cada escena con una intriga o pregunta atractiva y revela la sorpresa a la mitad. Conecta el final con la siguiente pregunta para que sea imposible dejar de escuchar.
5. ESTILO CONVERSACIONAL DE ÉLITE (TIPO YOUTUBE VIDEO-ESSAY / PODCAST: VOX, JORDI WILD, NATE GENTILE, TAMAYO):
   - Habla con cercanía, inteligencia y fascinación, como un divulgador brillante contándole a un amigo una historia alucinante en un café.
   - Alterna afirmaciones directas con preguntas que despierten intriga: "¿Por qué nadie lo detuvo a tiempo? Porque la ley lo permitía."

REGLAS DE FIDELIDAD TEMÁTICA, LISTAS Y RANKINGS (TOP 10, TOP 5, COMPARATIVAS):
- FIDELIDAD TOTAL AL TEMA: Si el tema solicita un TOP N (ej: "TOP 10 DE LOS PEORES PRESIDENTES EN LOS ÚLTIMOS 6 AÑOS EN AMÉRICA"):
  * La transmisión DEBE tener EXACTAMENTE UNA ESCENA DEDICADA A CADA UNO DE LOS PUESTOS (desde el Puesto 10 descendiendo uno a uno hasta el Puesto 1).
  * ESTRICTAMENTE PROHIBIDO saltarse puestos o agrupar varios mandatarios/puestos en una sola escena. Si el usuario pidió un TOP 10, el video debe tener 10 escenas individuales para los 10 personajes distintos, precedidas por la intro y seguidas por la conclusión.
  * Cada puesto debe nombrar con nombre y apellido completo al mandatario (ej: Puesto 10: Bernardo Arévalo, Puesto 9: Dina Boluarte, Puesto 8: Pedro Castillo, Puesto 7: Alberto Fernández, etc.), su país, sus fechas de mandato y los hechos o porcentajes concretos de su gestión.
- PROHIBIDO GENERALIZAR O DILUIR TEMAS EN ABSTRACCIONES: Está estrictamente prohibido hablar de "la inestabilidad regional" o "la crisis en general" sin mencionar con nombre y apellido a los personajes centrales del tema solicitado. El espectador entró a ver un TOP con nombres concretos; entregar un discurso genérico sin nombrar a los personajes arruina la producción.

REGLAS DE REDACCIÓN Y GUION NARRATIVO (LOCUCIÓN DE RADIO Y TELEVISIÓN):
- PROHIBICIÓN TOTAL DE MENCIONAR TIEMPO O DURACIÓN: Queda TERMINANTEMENTE PROHIBIDO que el narrador mencione la duración o el tiempo del video en su discurso. NUNCA digas "vamos a analizar en estos 30 minutos", "a lo largo de estos 20 minutos", "en este video de media hora", etc. La narración debe ser completamente atemporal y enfocada en los datos y los hechos.
- DESPEDIDA EXCLUSIVA EN LA ÚLTIMA ESCENA: ESTRICTAMENTE PROHIBIDO despedirse, agradecer o pedir suscripción ("gracias por acompañarme", "suscríbanse", "nos vemos en el próximo video", "hasta aquí llegamos") en escenas intermedias. La despedida y llamado a la acción ocurre ÚNICA Y EXCLUSIVAMENTE en la última escena (Escena {num_scenes}).
- PROHIBIDO EL RELLENO: NUNCA titules escenas como "Relleno" o "Relleno Estructural". Cada escena debe tener un contenido temático real, sustantivo y relevante.
- Redacta cada escena como un guion audiovisual para locutor profesional: con cadencia rítmica, pausas de respiración y excelente ortografía en español.
- CADA ORACIÓN debe tener longitud moderada (de 8 a 15 palabras) separada por comas y puntos. ESTRICTAMENTE PROHIBIDO redactar párrafos de 30 o 40 palabras seguidas sin comas intermedias.
- Usa comas antes de conjunciones y conectores naturales (ej: ", porque...", ", mientras...", ", donde...", ", pero...", ", y con ello...").
- Habla de forma directa, cautivadora e inteligente, como un narrador o divulgador de primer nivel dirigiéndose a su público.
- Evita muletillas o saludos vacíos (como "Hola a todos" o "Bienvenidos a mi canal"); entra directo al tema con energía y datos interesantes.

REGLAS DE RETENCIÓN Y VARIEDAD VISUAL (EDICIÓN PROFESIONAL):
- APERTURA DE ALTO IMPACTO (Escena 1 - REGLA OBLIGATORIA):
  * El video NUNCA debe comenzar mostrando al avatar hablando directamente a cámara en plano central (hero_center). Esto ralentiza el inicio y reduce drásticamente la retención.
  * La Escena 1 DEBE comenzar mostrando INFORMACIÓN VISUAL RELEVANTE mientras la narración empieza desde el primer momento:
    - Un fragmento relevante de video documental de archivo ('visual_query' específica y potente en inglés).
    - Una frase impactante o pregunta visual con animación tipográfica ('free_title').
    - Palabras clave sincronizadas con la voz o una cifra sorprendente representada visualmente ('card').
    - O una secuencia rápida de imágenes relacionadas ('visual_beats').
  * El avatar NO debe ocupar automáticamente el centro de la pantalla ni ser el primer elemento mostrado:
    - Debe comenzar en una posición secundaria de apoyo ('camera': 'pip_corner' o 'pip_delayed' que entra tras los primeros segundos), o intervenir solo con voz en off durante la apertura ('camera': 'voice_over').
    - NUNCA uses 'camera': 'hero_center' en la Escena 1.
  * 'type' de la Escena 1: 'video_reaction', 'breaking_news', 'card_focus' o 'broll_focus'. NUNCA 'avatar_cam' estático de estudio.
- VARIEDAD DE ESCENA Y ROL DEL AVATAR:
  * NUNCA dos escenas consecutivas del mismo "type". Alterna card_focus → video_reaction → vector_motion → chat_debate.
  * El avatar actúa como presentador o narrador visual de apoyo: convive con el contenido en recuadro PIP en esquina ('pip_corner') o split screen, con buen encuadre y sin tapar gráficos ni datos.
  * En escenas puramente explicativas (gráficos, mapas, comparativas, citas documentales), el avatar debe reducir su presencia o intervenir en voz en off ('voice_over' / 'pip_corner').
  * Solo en la escena final de despedida o cierre puede usar 'hero_center' si el guion lo requiere expresamente.
- PRIMEROS 15 SEGUNDOS DENSOS: el mayor abandono del espectador ocurre aquí. La escena 1 debe entregar el gancho visual + el dato más impactante del tema, sin contexto previo ni preámbulos.
- REGLA DE LOS 2 A 4 SEGUNDOS (MICRO-PACING ESTILO VOX / MAGNATES MEDIA / MRBEAST):
  * La retención de YouTube se desploma si un plano permanece fijo más de 4 segundos.
  * EN EL GANCHO (ESCENAS 1 Y 2): El ritmo de corte es hiper-dinámico. Diseña obligatoriamente de 2 a 3 'visual_beats' con 'trigger' exacto para que el motor corte de plano cada 2.0 a 2.5 segundos.
  * EN EL RESTO DEL VIDEO: NINGUNA escena debe depender de una sola toma estática. Aporta SIEMPRE 'visual_query2' y 'visual_beats' específicos para alternar ángulos y metraje cada 3.0 a 3.5 segundos.
  * ONDAS DE PACING: Alterna momentos de cortes rápidos e impacto (revelaciones, clímax) con tomas de respiro (mapas geopolíticos o citas documentales).
- PSICOLOGÍA DE RETENCIÓN (técnicas de Vox, Johnny Harris, Magnates Media, Veritasium, MrBeast):
  * PROMESA Y PAGO (Promise & Payoff): en las 2 primeras escenas plantea una paradoja, misterio o pregunta de alto riesgo (bucle abierto) y NO la resuelvas hasta el clímax; recuérdala brevemente a mitad del video ("y todavía falta lo más extraño...").
  * MICRO-GANCHOS CADA 60-90 SEGUNDOS: cuando el contenido pase de contexto a desarrollo, o de desarrollo a consecuencias, abre la escena con una afirmación inesperada, un dato que contradiga lo dicho o un adelanto del giro (pattern interrupt). Nunca encadenes más de 3 escenas seguidas sin un giro, pregunta directa al espectador o dato sorpresivo.
  * CONTRASTE DE SILENCIO: antes de la revelación principal, la escena previa debe cerrar con una frase corta y contundente (6-8 palabras) y la revelación entra con una escena de tono 'serious' o 'dramatic' y sin card ni pop-ups, para que el espectador se incline hacia la pantalla.
  * UNA SOLA CIFRA A LA VEZ: cada escena muestra como máximo UN dato numérico en pantalla (card, o pop-up, o chip; nunca dos). Si hay varias cifras en el speech, elige la más impactante para el elemento visual y deja el resto solo en la voz.
  * PALABRAS PODER EN PANTALLA: el texto en pantalla se limita a 1-4 palabras de máximo impacto (nombre propio, cifra o concepto clave); jamás frases largas que compitan con la locución.
  * CIERRE CON BUCLE: la última escena debe resolver la promesa inicial y dejar una pregunta final que invite a comentar o a ver el siguiente video, sin despedidas largas.

- RITMO DE ORACIONES VARIADO: alterna frases cortas contundentes (6-9 palabras) con frases de desarrollo (14-18 palabras). La variación de cadencia retiene más que el vocabulario.
- CARDS Y ELEMENTOS VISUALES IMPORTANTES: cuando se muestren mapas, comparativas versus, registros forenses, recortes de prensa o estadísticas clave, el motor los sostiene en pantalla el tiempo necesario (5.5s a 8.5s) para que el espectador pueda leer y asimilar cómodamente sin que se pasen volando. Redacta el headline y body de forma sustantiva y limpia (máximo 140 caracteres).
- PAUSAS ESTRATÉGICAS EN CLIPS Y CITAS: cuando des paso a una declaración o clip del protagonista ("escuchen sus palabras:", "miren lo que declaró:"), usa dos puntos (:) al final de la frase introductoria. El motor aplica automáticamente una pausa de suspense (0.40s) antes de que empiece a hablar la persona y una pausa de reflexión (0.55s) tras su última palabra antes de cambiar de escena, logrando un corte cinematográfico limpio.
- CITA FUENTES REALES POR NOMBRE: cuando la evidencia web mencione un medio, estudio o institución (Reuters, Ember, Nature, ONU, NASA), cítalo POR SU NOMBRE en la narración al menos 2 veces a lo largo del video ("según el informe de Ember...", "como publicó Reuters...") y en los popups ("Fuente: Ember"). La atribución real construye credibilidad y retiene al espectador escéptico.
- GANCHO VISUAL CONCRETO: el gancho inicial debe señalar algo visible y verificable ("miren estas marcas en la montaña") que la escena siguiente MUESTRE de verdad — nunca prometas visualmente algo que el montaje no entrega.

REGLAS PARA DATOS, MAPAS, ESTADÍSTICAS Y TARJETAS BENTO HUD (AL MENOS 60% DE LAS ESCENAS):
- ALTO CONTENIDO VISUAL E INFOGRÁFICO OBLIGATORIO: Un video plano o sin gráficos enriquece muy poco la experiencia. Por lo menos el 60% al 70% de las escenas DEBEN contener elementos visuales complementarios: o bien una tarjeta Bento HUD ("card"), o referencias visuales con banderas ("chips"), o un mapa geopolítico.
- SIEMPRE que se mencione una cifra, porcentaje, estadística, comparativa (ej: perro vs humano, PIB, inflación, velocidad, presupuesto, año récord), o hecho verificable, la escena DEBE incluir obligatoriamente el objeto "card".
- SIEMPRE que se discutan países, alianzas diplomáticas, conflictos geopolíticos o acuerdos bilaterales (ej: Estados Unidos, Argentina, Israel, China, Brasil), incluye en "card" un headline o stat con los países involucrados O añade el array "chips" con los nombres oficiales completos. El sistema generará automáticamente un mapa geopolítico vectorial de inteligencia o pastillas HUD con sus banderas nacionales.
- El objeto "card" debe tener:
  * "headline": Título corto y concreto del dato, mapa o comparativa (ej: "Alianza Geopolítica: EE.UU. e Israel", "Capacidad Olfativa: Perro vs Humano", "Inflación Mensual").
  * "stat": La cifra, métrica o relación clave destacada (ej: "300M vs 6M", "52.9%", "+450%", "Alianza Bilateral").
  * "body": Explicación sintética y contundente del dato con fuentes contrastadas.
  * "template" (o "style", elige la plantilla exacta de la librería para máximo impacto):
    - "newspaper_clipping": Recorte editorial de periódico de prestigio (Financial Times, The Wall Street Journal, Bloomberg, Forbes, Reuters, El Confidencial) con cabecera oficial, fecha, titular en tipografía serif y rotulador fluorescente amarillo neón animado sobre las palabras clave. SFX "whoosh". (Estilo Adrià Solà Pastor / Vox).
    - "social_post": Publicación verificada de alta resolución estilo X / Twitter / Threads con avatar, nombre, insignia de verificado, @handle, fecha y texto citado con términos clave resaltados en ámbar o azul. SFX "pop".
    - "timeline_milestone": Cronología documental de hitos conectados por un rayo de luz con nodo activo pulsante y fechas clave (ej: 2008 -> 2015 -> 2026). SFX "impact".
    - "verdict_badge": Distintivo viral estilo sticker/sello inclinado con rebote elástico (ej: headline "ganó Opus", "100% Real", "Confirmado", icon "✓"). Entra con spring bounce y SFX "pop".
    - "versus_split": Comparativa dual lado A vs lado B con divisor central circular VS en naranja (ej: headline "Humano", body "IA Autónoma", stat "4h vs 12s"). SFX "impact".
    - "quote_evidence": Cita editorial Vox con comillas grandes, fuente y frase resaltada en fluorescente. SFX "whoosh".
    - "step_badge": Píldora de hito/fase con cápsula numérica (ej: headline "Detección Acústica", stat "01"). SFX "pop".
    - "alert_banner": Alerta táctica con ícono de peligro y borde brillante (ej: headline "CONTRADICCIÓN DETECTADA", body "Señal no biológica"). SFX "alert".
    - "source_chip": Micro-pastilla de atribución oficial verificada (ej: headline "NOAA Research 2026"). SFX "pop".
    - "document_evidence_split": Pantalla dividida editorial estilo Platzi + Agustín Laje (panel de evidencia documental con cabecera de institución u organismo [ONU, UNODC, Ideas para la Paz, Ministerios, Gobiernos, Centros de Pensamiento], titular periodístico, fecha del informe, imagen o gráfica técnica incrustada, cita textual literal y rotulador fluorescente neón animado sobre las cifras y conclusiones clave). SFX "whoosh". ¡OBLIGATORIA SIEMPRE que se cite un informe oficial, estudio formal, balance de seguridad o documento de investigación! Se acompaña obligatoriamente de "camera": "split_screen".
    - "map": Mapa geopolítico táctico satelital 3D orbital con telemetría de coordenadas y HUD militar.
    - REGLA DE ORO: ¡PROHIBIDO USAR CAJAS O TARJETAS FLOTANTES PARA CIFRAS O PORCENTAJES! Las cifras numéricas ("80%", "$4 Billones") se animan directamente sobre el metraje de video como tipografía cinética flotante sin caja.
  * "variant" (paleta de diseño):
    - "orange_noir": Negro mate Obsidian + Naranja Eléctrico firma + Blanco perla (Firma AetherCut).
    - "frosted_white": Cristal esmerilado translúcido + Borde blanco + Tipografía serif editorial.
    - "emerald_matrix": Negro carbón + Verde Esmeralda neón para hechos verificados y éxito.
    - "crimson_hazard": Negro carbón + Rojo Carmesí para alertas críticas, mitos y controversias.
    - "cyber_cyan": Negro obsidiana + Oro Ámbar de lujo para tecnología, ciencia y futuro.
    - "royal_gold": Negro + Oro Solar para récords mundiales y tops #1.
  * "badge":
    - "NOTICIA", "PRENSA", "PERIODICO", "TITULAR": Activa newspaper_clipping.
    - "TWEET", "TWITTER", "POST", "DECLARACION": Activa social_post.
    - "CRONOLOGIA", "TIMELINE", "HITOS", "EVOLUCION": Activa timeline_milestone.
    - "MAPA", "GEO", "ESTRECHO", "CANAL", "FRONTERA", "PAIS": Activa map.
    - "COMPARATIVA" o "VERSUS": Activa versus_split.
    - "INFORME OFICIAL", "EVIDENCIA DOCUMENTAL", "ONU", "UNODC", "CITACIÓN FORMAL", "DOCUMENTO": Activa document_evidence_split.
    - "EVIDENCIA", "CITA" o "DECLARACION": Activa quote_evidence.
    - "PASO", "FASE" o "HITO": Activa step_badge.
    - "ALERTA" o "PELIGRO": Activa alert_banner.
    - "FUENTE" o "ATRIBUCIÓN": Activa source_chip.

==============================================================================
SISTEMA DE ASIGNACIÓN INTELIGENTE DE RECURSOS POR FRASE (ESTILO AGUSTÍN LAJE / PLATZI):
==============================================================================
El Director de IA debe ser lo suficientemente inteligente para detectar la naturaleza exacta de cada oración y asignarle el recurso audiovisual que mejor respalda su veracidad:
1. REGLA DE INFORMES Y CITAS FORMALES (ESTILO PLATZI / LAJE):
   * Si en la frase se menciona un informe, estudio, organismo multilateral o documento oficial (ej: "según el informe de la ONU", "de acuerdo con la UNODC", "el balance de Ideas para la Paz revela", "según el informe de auditoría"):
     -> ASIGNA OBLIGATORIAMENTE: "type": "card_focus", "camera": "split_screen", "card": {{"template": "document_evidence_split", "headline": "...", "body": "...", "stat": "...", "badge": "INFORME OFICIAL", "params": {{"institution": "...", "date_str": "...", "highlight_phrase": "..."}}}}.
2. REGLA DE CIFRAS PORCENTUALES COMPARATIVAS Y BALANCES:
   * Si la frase compara porcentajes, aumentos o caídas (ej: "los combatientes ilegales crecieron un 90%, pasando de 15.000 a 29.000", "el Clan del Golfo subió 152% mientras el ELN subió 22%"):
     -> ASIGNA: "template": "versus_split" o tipografía cinética flotante con "camera": "voice_over". ¡Prohibido colocar cajas opacas centradas!
3. REGLA DE CITAS TEXTUALES Y DECLARACIONES DE PROTAGONISTAS (SOUNDBITES CON AUDIO REAL):
   * Si en la narración se introduce una cita directa de un personaje clave (ej: "Petro declaró textualmente que en tres meses acababa con el ELN", "Miren lo que dijo Abelardo de la Espriella en su intervención:"):
     -> ASIGNA: "type": "video_reaction", introduciendo dos puntos (:) antes del corte, y especificando en "visual_query" y "visual_beats" la búsqueda en español de la rueda de prensa o discurso real del personaje. Si existen cortes reales ("case_soundbites"), enlaza "soundbite_clip" y "soundbite_quote".
4. REGLA DE CONTEXTO NARRATIVO Y OPERATIVOS DE CAMPO:
   * Cuando se relaten hechos de campo, operativos militares, capturas o contexto histórico:
     -> ASIGNA B-Roll documental reactivo a pantalla completa con cortes dinámicos cada 2.5 a 3.5 segundos mediante "visual_beats", y KAI en "camera": "pip_corner".

FILOSOFÍA DE MONTAJE Y ALTERNANCIA VISUAL (ESTILO ADRIA SOLÀ PASTOR / VIDEO-ENSAYO DE ALTA RETENCIÓN):
- MÁXIMA VARIEDAD DE RECURSOS (CERO MONOTONÍA): Un video documental de calidad no repite el mismo formato visual dos veces seguidas. Debes alternar activamente los recursos de escena a escena:
  1. Si una escena usó un clip de B-Roll cinematográfico puro -> La siguiente DEBE mostrar evidencia tangible: un recorte de periódico con fluorescente ("newspaper_clipping") o una publicación verificada ("social_post").
  2. Si una escena mostró un titular de prensa -> La siguiente DEBE mostrar una animación cinética de impacto ("free_title" o Remotion React) o una comparativa directa ("versus_split").
  3. Si una escena mostró datos numéricos -> La siguiente DEBE aterrizar en una fotografía real de archivo histórico o de satélite con ficha técnica ("tech_card") o mapa geopolítico ("map").
  4. En documentales / video-ensayos serios, el protagonismo absoluto lo tiene el metraje 4K y la evidencia visual a pantalla completa (100% video cinemático sin avatares en la esquina).
- De esta manera el espectador se sumerge en una experiencia audiovisual rica, profesional y con la densidad informativa y el dinamismo de los mejores creadores de video-ensayos del mundo.

REGLAS PARA TEXTO LIBRE ANIMADO CINEMÁTICO ("free_title") (SIN CAJAS, FLOTANTE EN PANTALLA):
- Si la escena representa un TOP / RANKING (ej: "Puesto 3"), una ENUMERACIÓN DE COSAS IMPORTANTES (ej: "Factor #1: Velocidad", "Paso 2: Neutralización") o un CONCEPTO DE IMPACTO ("Guerra Sin Humanos", "Inversión Récord"), incluye el objeto "free_title" (flotará libre directamente sobre el video sin caja ni contenedor):
  * "title": Titular principal (ej: "DRONES AUTÓNOMOS", "VELOCIDAD DE REACCIÓN", "CONTROL BALÍSTICO").
  * "number": Número destacado de 2 dígitos si aplica (ej: "03", "01") o dejarlo vacío.
  * "tag": Etiqueta superior en micro-letras (ej: "PUESTO 03 · RANKING", "FACTOR DETERMINANTE #1", "ALERTA ESTRATÉGICA").
  * "subtitle": Frase corta explicativa (máximo 12 palabras).
  * "highlight": La palabra exacta del título que debe brillar con halo de luz de color.
  * "blur_bg": true (desenfoca momentáneamente el fondo del video durante 2 segundos mientras aparece el título flotante).

REGLAS PARA EL TÍTULO DEL VIDEO ("title") (YOUTUBE VIRAL & CTR):
- El campo "title" NO debe ser el tema crudo del usuario si este tiene errores ortográficos, faltas de acentuación o es aburrido.
- Transfórmalo en un título magnético de YouTube con ortografía y sintaxis 100% impecables.
- Debe despertar curiosidad y ganas irresistibles de verlo (ganchos de revelación, paradoja, verdad oculta o pregunta directa).
- Longitud recomendada para YouTube: entre 45 y 75 caracteres (MÁXIMO ABSOLUTO 95 caracteres para evitar cortes en teléfonos móviles).
- Sin comillas y sin prefijos como "Título:" o "KAI:".

REGLAS PARA EDICIÓN AVANZADA Y REFERENCIAS VISUALES ("chips"):
- SIEMPRE que en la narración se enumeren, comparen o mencionen países (ej: Estados Unidos, China, Argentina, España), marcas o entidades, agrega en la escena el array "chips" con los nombres limpios oficiales (ej: ["Estados Unidos", "China", "Argentina"]).
- NO agregues emojis rotos ni códigos de dos letras como texto crudo; escribe el nombre completo del país o institución ("Estados Unidos", "China", "Argentina", "NASA", "MIT"). El motor gráfico descargará e integrará automáticamente la bandera oficial de alta resolución y aplicará la animación secuencial en el momento en que se mencionen.

REGLAS DE SELECCIÓN VISUAL (MÁXIMA RELEVANCIA Y MULTI-VIDEO POR ESCENA):
- REGLA EDITORIAL ESTRICTA (CERO IMÁGENES O CLIPS DE STOCK Y CERO ELEMENTOS DESCONECTADOS):
  * ESTRICTAMENTE PROHIBIDO usar imágenes o clips de stock genéricos (oficinas con modelos sonriendo, apretones de manos corporativos, bombillas 3D, maquetas, billetes flotando, carreteras o ciudades vacías aleatorias) y clips no relacionados directamente con el tema tratado.
  * PARA CADA TEMA HAY ABUNDANTE MATERIAL REAL, PUBLICACIONES Y DOCUMENTOS:
    1. Documentos y balances oficiales (decretos, resoluciones, informes de la ONU, ministerios, balances de seguridad, centros de pensamiento): usa "document_evidence_split" con highlight fluorescente animado sobre las conclusiones clave.
    2. Titulares y portadas reales de periódicos y prensa de prestigio (Financial Times, Bloomberg, Reuters, El Confidencial, El Tiempo, Semana, etc.): usa "newspaper_clipping".
    3. Publicaciones y comunicados oficiales en redes sociales (tuits y comunicados de los propios involucrados): usa "social_post".
    4. Citas textuales verificadas con autor y cargo: usa "quote_evidence" o soundbites con audio real.
    5. Fotografías y metraje de prensa auténtico: conferencias de prensa, audiencias, operativos y coberturas periodísticas reales.
- REGLA DE ORO DEL GANCHO INICIAL (PRIMEROS 5-10 SEGUNDOS ESTILO VIRAL Y YOUTUBE FAMOSO):
  * La Escena 1 (el Hook) NUNCA puede quedarse en una sola imagen estática ni en un solo clip sin cambios. En los videos más virales y vistos del mundo (YouTube, TikTok, Reels), los primeros 8 segundos son un carrusel dinámico de estímulos intrigantes en ráfaga rápida.
  * La Escena 1 DEBE incluir obligatoriamente:
    1. "visual_query": Clip inicial de impacto, acción o enigma de apertura.
    2. "visual_query2": Segundo clip contrastante para alternar a mitad del gancho.
    3. "visual_beats" (3 A 4 BEATS DE CORTE RÁPIDO OBLIGATORIOS): Cortes cada 1.8 a 2.5 segundos que muestren facetas distintas de la historia (el hecho concreto, el protagonista real, el documento o titular periodístico clave, y la consecuencia en vivo).
    4. "free_title" o titular flotante con highlight fluorescente para capturar la vista al instante.
- EXACTA COINCIDENCIA TEMÁTICA: Lo que se muestre en pantalla DEBE coincidir al 100% con lo que KAI está narrando en ese instante exacto. Si el guión habla de velocirraptores con plumas, el video DEBE ser de velocirraptores con plumas; si habla de la mordida del T-Rex, el video DEBE mostrar el tiranosaurio rex o biomecánica fósil; si habla de escamas de cocodrilo, debe mostrar piel fósil o reptiles reales.
- CAPACIDAD DE 2 VIDEOS POR ESCENA: Para enriquecer el montaje y evitar fondos repetidos, cada escena puede y debe aportar:
  * "visual_query": El clip de video protagonista para la primera mitad de la escena (hiper-específico, 4k/hd). SI EL TEMA O PERSONA ES EN ESPAÑOL, USA EL NOMBRE Y TÉRMINOS EN ESPAÑOL para que YouTube encuentre la rueda de prensa y noticias reales (ej: 'Javier Milei discurso conferencia de prensa', 'Pedro Sanchez declaraciones en vivo', 'manifestacion policia disturbios'); si es un concepto de stock natural o anglosajón, usa inglés (ej: 'velociraptor paleoart animation 4k').
  * "visual_query2": Un segundo clip de video o ángulo complementario para alternar a mitad de la escena.
- PREDOMINIO ABSOLUTO DE VIDEO: Más del 70% de las escenas deben usar clips de video dinámicos en movimiento.
- BEATS VISUALES ("visual_beats") OBLIGATORIOS: cada escena debe traer de 2 a 4 beats. Cada beat es un clip de referencia EXACTA de lo que se dice en esa frase:
  * "trigger": copia LITERAL de 3 a 6 palabras consecutivas del "speech" donde debe entrar ese clip (en el orden en que aparecen en el speech).
  * "query": búsqueda hiper-específica de lo que se nombra en esa frase (persona real, lugar, institución, evento, objeto). Si la persona o hecho es del mundo hispanohablante, escribe la búsqueda en español para que YouTube traiga metraje periodístico real en español (ej: "banco central buenos aires anuncio medidas", "discurso presidente congreso").
  * "recent": true si es actualidad (se buscará material del año en curso primero), false solo si es contexto histórico.
  * Prohibido usar queries genéricos ("cinematic", "abstract", "documentary 4k" solos). Nombra la entidad concreta.
- POP-UPS ("popups"): de 0 a 2 por escena. Texto corto (máx. 40 caracteres) que aparece en el instante exacto en que se pronuncia el "trigger" (copia LITERAL de 2 a 5 palabras del speech). "kind": "stat" (cifra), "fact" (dato), "alert" (advertencia/polémica) o "quote" (cita). No repitas lo que ya está en la "card".
- PROHIBIDO repetir el mismo visual_query entre escenas. Cada toma debe ser fresca y diferente.
- EXCLUSIÓN TOTAL DE MARCAS DE AGUA Y SELLOS: NUNCA busques marcas de stock comercial con sellos (Shutterstock, Alamy, iStock, Adobe Stock).
- ANCLAJE A LA ENTIDAD REAL DEL CASO: cuando la transmisión trate un caso, lugar, persona, objeto o evento ESPECÍFICO, el "visual_query" y los "query" de los beats DEBEN nombrar esa entidad exacta (ej: 'Dyatlov Pass tent 1959 expedition photograph', 'Nazca lines hummingbird geoglyph aerial', 'Monte Ararat Durupinar formation satellite') y NUNCA su equivalente genérico ('snowy mountain', 'ancient lines', 'rocky mountain'). Una montaña cualquiera cuando se habla de UNA montaña concreta es una mentira visual que rompe la credibilidad.
- PRIORIZACIÓN ABSOLUTA DE LA PERSONA Y DECLARACIÓN REAL: Si la escena habla de una persona o mandatario (ej: un presidente, ministro, líder, CEO, científico, deportista o celebridad), el "visual_query" y "visual_beats" DEBEN buscar OBLIGATORIAMENTE a esa persona real hablando o en acción (ej: 'Pedro Sanchez rueda de prensa declaraciones', 'Javier Milei discurso asamblea ONU', 'Claudia Sheinbaum conferencia', 'Elon Musk interview announcement'). ESTRICTAMENTE PROHIBIDO sustituir a la persona por metáforas abstractas de stock (como billetes de dinero, maquetas, martillos de juez, carreteras o edificios genéricos vacíos). La audiencia quiere ver a la persona concreta de la que se habla.
- PRINCIPIO RECTOR: COHERENCIA VISUAL, RITMO Y DEFINICIÓN INTELIGENTE (EL MODELO DETERMINA SEGÚN EL TEMA):
  * COHERENCIA DIRECTA Y ANCLAJE: El contenido visual ("visual_query" y "visual_beats") debe representar exactamente lo que se narra en la escena. Si se habla de una tecnología o nuevo modelo, busca sus interfaces, benchmarks, tablas y pruebas reales; si se habla de astronomía o el universo, busca metraje astronómico real; si se habla de geopolítica o historia, busca líderes, documentos y archivos reales. NUNCA introduzcas recursos desconectados del tema (ej: no busques el Sol o espacio si hablas de software, ni oficinas genéricas si hablas de una expedición).
  * TONO ADAPTATIVO AL GÉNERO: Determina el tono con inteligencia: si el video es un análisis o lanzamiento actual, utiliza un tono dinámico, riguroso y contemporáneo (sin recurrir a frases como "en este documental"); si es una crónica histórica o misterio, adopta un tono narrativo de investigación.
  * PERMANENCIA VISUAL SEGÚN LA DENSIDAD DEL DATO: Evalúa la carga cognitiva del plano. Cuando se expongan tablas comparativas, métricas, documentos o benchmarks, la escena debe dar permanencia suficiente para que la audiencia pueda leer y analizar los datos con claridad antes de cambiar de plano.
  * ELECCIÓN CONSCIENTE DE CÁMARA: Define escena por escena si la presencia del presentador ("avatar_cam" o "pip_corner") aporta dinamismo (en ganchos, reacciones directas y cierres) o si la evidencia, gráfico o metraje debe ocupar el 100% de la pantalla en modo cinematográfico limpio ("voice_over").
- ESCENAS DE REACCIÓN CON SOUNDBITE Y AUDIO REAL (CORTES DE DECLARACIÓN): En escenas de tipo "video_reaction" o cuando se introduzca una frase clave o declaración de un protagonista (ej: presidentes, líderes, científicos, figuras públicas):
  * Redacta una locución de KAI concisa y dinámica (de 10 a 18 palabras) que dé paso directo al corte de video (ej: "Miren lo que afirmó textualmente ante los micrófonos:", "Sus declaraciones ante la prensa fueron tajantes:", "Atención a sus propias palabras:").
  * El motor audiovisual le da prioridad al corte de video: silencia el audio mientras KAI habla para que no haya murmullos compitiendo detrás, y luego activa automáticamente la voz REAL del protagonista a volumen completo en primer plano para que se escuche clara y nítida.
  * Si hay soundbites reales del caso disponibles, asigna "soundbite_clip" con el nombre del clip y "soundbite_quote" con la cita exacta.
{case_frames_block}{case_soundbites_block}==============================================================================

TIPOS DE ESCENA DISPONIBLES:
1. "avatar_cam": KAI diciendo la primera frase de gancho (Hook de impacto de 3 a 4 segundos MÁXIMO) y luego entra inmediatamente el contenido visual y B-Roll para que la audiencia no se aburra. Ideal para abrir con intriga o para la conclusión final reflexiva.
2. "video_reaction": Clip de video dinámico a pantalla completa con KAI en recuadro PIP en la esquina reaccionando en vivo ("¡Miren esta toma!", "¡Fíjense en este detalle!").
3. "card_focus": Tarjeta Bento HUD con gráfico infográfico (Matplotlib) y KAI en PIP. ¡OBLIGATORIA para estadísticas y comparativas!
4. "vector_motion": B-Roll cinemático conceptual y gráficos de estudio de alta definición (redes neuronales, flujos tecnológicos, metraje 4K o visualizaciones abstractas). ¡Ideal para explicar conceptos y procesos complejos!
5. "chat_debate": KAI interactúa con preguntas y dilemas de la audiencia, contrastando posturas.
6. "breaking_news": Titular o primicia urgente con tono dinámico y clip de video en movimiento.

EMOCIONES DE KAI POR ESCENA:
- "excited": Entusiasta, dinámico, revelaciones fascinantes.
- "surprised": Asombrado, incrédulo, al ver videos o noticias impactantes.
- "serious": Riguroso, analítico, al presentar cifras o advertencias.
- "skeptical": Crítico, cuestionador ("¿Quién se beneficia realmente?").
- "confident": Seguro, empático, cierre y despedida.

TEMA: "{topic}"
ESTILO: {style_instructions}
EVIDENCIA DE LA WEB:
{evidence}

RESPONDE EXCLUSIVAMENTE EN FORMATO JSON VÁLIDO:
{{
  "title": "Titular principal de la transmisión",
  "scenes": [
    {{
      "name": "Gancho de Alta Tensión Geopolítica",
      "type": "video_reaction",
      "emotion": "serious",
      "camera": "voice_over",
      "speech": "En este preciso segundo, cien mil buques cisterna cruzan un estrecho tan angosto que dos destructores casi pueden rozarse. Si este canal se bloquea setenta y dos horas, el ochenta por ciento del petróleo de Asia desaparece.",
      "visual_query": "oil tanker ship navigation strait of malacca aerial 4k footage",
      "visual_query2": "satellite military radar maritime tracking footage hd",
      "visual_beats": [
        {{"trigger": "cien mil buques cisterna", "query": "massive container cargo ships maritime choke point", "recent": true}},
        {{"trigger": "Si este canal se bloquea", "query": "military warship naval blockade naval defense 4k", "recent": false}},
        {{"trigger": "el ochenta por ciento", "query": "oil refinery petroleum energy crisis tank terminal", "recent": true}}
      ],
      "free_title": {{
        "title": "EL CUELLO DE BOTELLA DEL MUNDO",
        "tag": "INTEL // MARÍTIMO",
        "highlight": "CUELLO DE BOTELLA",
        "blur_bg": true
      }},
      "sfx": "impact",
      "duration_est_sec": {seconds_per_scene}
    }},
    {{
      "name": "Mapa Táctico del Dilema de Malaca",
      "type": "video_reaction",
      "emotion": "serious",
      "camera": "voice_over",
      "card": {{
        "headline": "Estrecho de Malaca: 2.8 km de Paso Crítico",
        "stat": "ZONA DE DISPUTA NAVAL",
        "body": "Punto de estrangulamiento que conecta el Océano Índico con el Mar de la China Meridional.",
        "badge": "MAPA",
        "template": "map"
      }},
      "speech": "No es una teoría conspirativa. Pekín lo bautizó oficialmente como el Dilema de Malaca: una sola ruta marítima donde tres superpotencias compiten en silencio por el control del interruptor del mundo.",
      "chips": ["China", "Estados Unidos", "Japón"],
      "visual_query": "strait of malacca satellite orbital view nautical map 4k",
      "visual_query2": "naval submarine patrol south china sea 4k footage",
      "visual_beats": [
        {{"trigger": "el Dilema de Malaca", "query": "beijing military command center war room screen", "recent": true}},
        {{"trigger": "tres superpotencias compiten", "query": "aircraft carrier strike group pacific ocean navy", "recent": true}}
      ],
      "sfx": "whoosh",
      "duration_est_sec": {seconds_per_scene}
    }},
    {{
      "name": "Evidencia Documental Oficial (Platzi/Laje Split)",
      "type": "card_focus",
      "emotion": "serious",
      "camera": "split_screen",
      "card": {{
        "headline": "CULTIVOS DE COCA ALCANZAN MÁXIMO HISTÓRICO",
        "stat": "253K ha",
        "body": "De acuerdo con el informe oficial de la ONU (UNODC), los cultivos de coca alcanzaron récord de 253.000 hectáreas, mientras los combatientes ilegales crecieron un 90%.",
        "badge": "INFORME OFICIAL",
        "template": "document_evidence_split",
        "params": {{
          "institution": "UNODC · NACIONES UNIDAS",
          "date_str": "JUNIO 2026",
          "highlight_phrase": "récord de 253.000 hectáreas",
          "stat_value": "+90%",
          "stat_label": "Combatientes Ilegales",
          "stat_value2": "253K ha",
          "stat_label2": "Cultivos Totales"
        }}
      }},
      "speech": "De acuerdo con el informe oficial de la ONU publicado en junio de 2026, los cultivos de coca alcanzaron un récord de 253.000 hectáreas en el territorio nacional. Y las cifras de Ideas para la Paz confirman que los combatientes armados ilegales crecieron un noventa por ciento en el mismo periodo.",
      "visual_query": "United Nations UNODC official report press conference 4k footage",
      "visual_query2": "coca crops harvest illegal armed groups documentary aerial 4k footage",
      "visual_beats": [
        {{"trigger": "informe oficial de la ONU", "query": "United Nations press briefing podium official report", "recent": true}},
        {{"trigger": "récord de 253.000 hectáreas", "query": "aerial view coca fields plantation forest", "recent": false}},
        {{"trigger": "crecieron un noventa por ciento", "query": "military operational balance security forces", "recent": true}}
      ],
      "sfx": "whoosh",
      "duration_est_sec": {seconds_per_scene}
    }}
  ],
  "chat_comments": [
    {{"user": "CuriosoTech", "badge": "VIP", "text": "¡Esa diferencia de cifras es brutal!"}},
    {{"user": "BioData", "badge": "SUB", "text": "Dato mata relato, totalmente comprobado."}},
    {{"user": "Clara_M", "badge": "MOD", "text": "Impresionante la comparativa en pantalla."}}
  ]
}}
"""


class AIDirector:
    """Director autónomo de producción audiovisual para emisiones de KAI."""

    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    async def direct_broadcast(
        self,
        topic: str,
        style: str,
        evidence: str,
        duration_target: int,
        style_instructions: str,
        case_frames: Optional[List[Dict[str, Any]]] = None,
        case_soundbites: Optional[List[Dict[str, Any]]] = None,
    ) -> DirectorBroadcastPlan:
        """Pide a Gemini dirigir la emisión completa escena por escena.

        case_frames: fotogramas REALES del video/caso fuente (modo análisis de
        caso). Cada item: {"index": int, "desc": str}. El director los usa como
        fondo de las escenas que hablan de lo que SE VE en esos fotogramas.
        case_soundbites: declaraciones estratégicas reales con audio y video
        del protagonista analizadas en el video completo.
        """
        # duration_target está SIEMPRE en segundos (el nombre del campo es explícito).
        try:
            dur_int = int(duration_target) if duration_target is not None else 45
        except (ValueError, TypeError):
            dur_int = 45
        dur = max(20, min(2400, dur_int))

        safe_log(f"[AIDirector] Planificando y dirigiendo transmisión para: «{topic}» ({dur}s / {dur // 60 if dur >= 60 else dur}{'m' if dur >= 60 else 's'})")

        # Detección inteligente de TOPs y Rankings (ej: TOP 10, TOP 5, Ranking 7)
        ranking_match = re.search(r'\b(?:top|ranking|los mejores|los peores|puesto|puestos)\s*(\d{1,2})\b', topic, re.IGNORECASE)
        ranked_n = int(ranking_match.group(1)) if ranking_match else None

        if ranked_n and 3 <= ranked_n <= 15:
            # Para un TOP N: 1 escena de intro/gancho + N escenas (una por cada puesto) + 1 escena de conclusión
            num_scenes = ranked_n + 2
        elif dur <= 35:
            num_scenes = 2
        elif dur <= 60:
            num_scenes = max(3, dur // 18)
        elif dur <= 100:
            num_scenes = max(3, dur // 22)
        elif dur <= 180:
            num_scenes = max(4, dur // 28)
        elif dur <= 360:
            num_scenes = max(6, dur // 35)
        elif dur <= 600:
            num_scenes = max(8, min(10, round(dur / 65)))
        elif dur <= 900:
            # 15 min: 11-12 escenas de ~75s con párrafos profundos de 135-155 palabras
            num_scenes = max(10, min(12, round(dur / 75)))
        elif dur <= 1500:
            # 20-25 min: 13-16 escenas de ~85s
            num_scenes = max(13, min(16, round(dur / 85)))
        else:
            # 30-40 min: 16-22 escenas de ~95s
            num_scenes = max(16, min(24, round(dur / 95)))

        seconds_per_scene = round(dur / num_scenes)
        # Ritmo de narración broadcast natural (~110-120 palabras por minuto = ~1.85 palabras por segundo)
        words_per_scene = max(25, round(seconds_per_scene * 1.85))
        min_words_per_scene = max(18, round(seconds_per_scene * 1.50))
        max_words_per_scene = max(30, round(seconds_per_scene * 2.10))
        total_words = words_per_scene * num_scenes

        if dur >= 600:
            duration_label = f"{dur // 60} minutos (Análisis Extendido)"
        elif dur >= 120:
            duration_label = f"{dur // 60} minutos"
        else:
            duration_label = f"{dur} segundos"

        # Bloque de fotogramas del caso (modo análisis): describe al director qué
        # hay disponible y le obliga a anclar las escenas a esos fotogramas reales.
        if case_frames:
            frame_lines = "\n".join(
                f"  * case_frame {f['index']}: {f.get('desc', '')[:200]}"
                for f in case_frames
            )
            case_frames_block = f"""
ANÁLISIS VISUAL DEL VIDEO/CASO FUENTE (FOTOGRAMAS REALES DISPONIBLES):
Estos fotogramas REALES del caso ya están descargados y listos como fondos de pantalla. Índice + descripción:
{frame_lines}
- OBLIGATORIO: las escenas que se refieran a lo que SE VE en estos fotogramas DEBEN incluir "case_frame": <índice del fotograma> en su JSON (es un número entero). Es la evidencia visual del caso: mostrar stock genérico cuando existe el fotograma real sería una mentira visual.
- Ordena la narración para RECORRER los fotogramas en el orden natural del caso ("miren las marcas en la montaña" → el fotograma con las marcas).
- El gancho inicial DEBE abrir con el fotograma más impactante del caso (case_frame en la escena 1 o 2).

"""
        else:
            case_frames_block = ""

        # Bloque de soundbites estratégicos reales del caso
        if case_soundbites:
            sb_lines = "\n".join(
                f"  * Soundbite #{i} [clip: '{sb.get('clip_name', f'case_soundbite_{i}.mp4')}']: «{sb.get('quote', '')}» ({sb.get('duration', 3.2):.1f}s)"
                for i, sb in enumerate(case_soundbites)
            )
            case_soundbites_block = f"""
DECLARACIONES Y SOUNDBITES ESTRATÉGICOS REALES DEL VIDEO FUENTE:
El analizador examinó el video completo y extrajo estas declaraciones reales clave donde el protagonista habla con lógica y sentido completo:
{sb_lines}

REGLAS PARA ESCENAS CON DECLARACIÓN REAL:
- Elige al menos una de estas declaraciones reales y crea una escena de tipo "video_reaction" donde KAI introduzca con intriga y dinamismo la cita (ej: "Atención a lo que afirmó textualmente ante la prensa:", "Miren sus declaraciones exactas sobre este tema:").
- En esa escena asigna:
  "soundbite_clip": "<nombre del clip asignado, ej: case_soundbite_0.mp4>",
  "soundbite_quote": "<la cita textual que dice el protagonista>"
- KAI dirá su locución concisa (10 a 18 palabras) y el motor activará automáticamente la voz real del protagonista con la declaración completa.

"""
        else:
            case_soundbites_block = ""

        import datetime as _dt
        _now = _dt.date.today()

        is_anime_broadcast = (
            (
                any(k in topic.lower() for k in ("anime", "manga", "black clover", "shonen", "sakuga"))
                or bool(re.search(r'\basta\b', topic, re.IGNORECASE))
                or "anime" in style_instructions.lower()
            )
            and not any(k in topic.lower() for k in ("cristiano", "cristiana", "huellas sagradas", "hacksaw ridge", "desmond doss"))
        )
        if is_anime_broadcast:
            ep_match = re.search(r'(?:episodios?|episodes?|ep\.?)\s*([\d\s\-]+)', topic, re.IGNORECASE)
            part_match = re.search(r'parte\s*(\d+)', topic, re.IGNORECASE)
            ep_tag = ""
            if ep_match:
                ep_tag = f"Episodios {ep_match.group(1).strip()}"
            elif part_match:
                p_num = int(part_match.group(1))
                ep_tag = f"Episodios {(p_num - 1) * 3 + 1} a {p_num * 3}"

            anime_rule = f"""
REGLA EDITORIAL SUPREMA: ANIME RECAP PROFESIONAL ({ep_tag or 'Arco Actual'}):
1. NARRATIVA INMERSIVA EN TERCERA PERSONA PRESENTE (ESTILO THRILLER DE ACCIÓN):
   - Narra en presente continuo inmersivo ("Asta da un paso al frente ensangrentado...", "Revchi desata sus cadenas...", "El grimorio negro flota en el aire...").
   - ESTRUCTURA DE CAUSA Y EFECTO: Cada frase debe conectarse con consecuencias claras ("Por lo tanto...", "Pero en ese instante..."). Cero resúmenes escolares aburridos ("en este capítulo el autor nos muestra").
   - ECONOMÍA DE NOMBRES: Identifica primero el rol del personaje ("el ladrón de grimorios", "su rival prodigio", "el capitán de los toros negros") para que el oyente jamás se pierda ni se sature.
2. ALINEACIÓN VISUAL ESTRICTA 1:1 ("SHOW WHAT YOU TELL"):
   - Lo que el narrador nombra en un segundo exacto DEBE ser lo que se ve en pantalla.
   - En CADA ESCENA incluye obligatoriamente entre 2 y 4 "visual_beats":
     * "trigger": Copia LITERAL de 3 a 5 palabras del speech donde ocurre la acción clave (ej: "desenvaina la espada negra", "corta las cadenas mágicas", "el trébol de cuatro hojas brilla").
     * "query": Término de búsqueda EXACTO de esa acción en ese episodio (ej: "Asta five leaf black sword summon Episode 1", "Asta breaks Revchi magic chains Episode 1").
3. CERO ANACRONISMOS:
   - ESTRICTAMENTE PROHIBIDO usar o buscar transformaciones, villanos o escenas de sagas futuras que no han ocurrido todavía ({ep_tag}).
   - En cada escena asigna:
     * "visual_query": El atacante o protagonista en acción (ej: "Asta vs Revchi fight combat").
     * "visual_query2": La reacción del oponente o los testigos (ej: "Revchi shocked face reaction" o "Yuno amazed expression").
4. VOZ CONTINUA Y CERO PERSONAS REALES:
   - Alejandro mantiene narración continua. CERO personas reales, cero entrevistas, cero podcasts, cero avatares en cámara.
"""
            style_instructions = f"{style_instructions}\n\n{anime_rule}"

        prompt = DIRECTOR_SYSTEM_PROMPT.format(
            today=_now.isoformat(),
            year=_now.year,
            prev_year=_now.year - 1,
            topic=topic,
            style_instructions=style_instructions,
            duration_target=dur,
            duration_label=duration_label,
            evidence=evidence or "Información reciente y verificada.",
            num_scenes=num_scenes,
            seconds_per_scene=seconds_per_scene,
            words_per_scene=words_per_scene,
            min_words_per_scene=min_words_per_scene,
            max_words_per_scene=max_words_per_scene,
            total_words=total_words,
            case_frames_block=case_frames_block,
            case_soundbites_block=case_soundbites_block,
        )

        try:
            gen_timeout = max(110.0, min(420.0 if dur > 1200 else 240.0, float(dur * 0.6)))
            raw = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm.generate,
                    prompt,
                    json_mode=True,
                    max_models=3,
                    deadline_sec=gen_timeout,
                    thinking_budget=1024,
                ),
                timeout=gen_timeout,
            )
            data = None
            try:
                data = _parse_director_json(raw)
            except Exception as parse_err:
                safe_log(f"[AIDirector] Aviso: JSON primario requirió reparación ({parse_err}). Reparando...")
                try:
                    fix_prompt = (
                        "El siguiente texto contiene un JSON de un plan de video con errores menores de sintaxis (comas o comillas). "
                        "Corrige la sintaxis y responde EXCLUSIVAMENTE con el objeto JSON válido:\n\n"
                        f"{raw[:40000]}"
                    )
                    repaired_raw = self.llm.generate(fix_prompt, json_mode=True, deadline_sec=18)
                    data = _parse_director_json(repaired_raw)
                    safe_log("[AIDirector] ✓ JSON reparado y recuperado exitosamente con IA auxiliar.")
                except Exception as fix_err:
                    safe_log(f"[AIDirector] No se pudo reparar JSON con IA auxiliar ({fix_err}).")
                    raise parse_err

            scenes: List[DirectorScene] = []
            raw_scenes = data.get("scenes", [])
            for idx, s in enumerate(raw_scenes):
                c_data = s.get("card")
                card_obj = None
                if c_data and isinstance(c_data, dict):
                    valid_card_keys = {k: v for k, v in c_data.items() if k in SceneCard.__dataclass_fields__}
                    valid_card_keys.setdefault("headline", "Dato Oficial")
                    valid_card_keys.setdefault("body", "Información técnica verificada.")
                    valid_card_keys.setdefault("badge", "DATO CLAVE")
                    valid_card_keys.setdefault("stat", "")
                    card_obj = SceneCard(**valid_card_keys)
                elif isinstance(c_data, SceneCard):
                    card_obj = c_data
                raw_speech = s.get("speech", "").strip()
                from utils.speech_normalizer import normalize_speech_for_tts
                is_final_scene = (idx == len(raw_scenes) - 1)
                polished_speech = normalize_speech_for_tts(raw_speech, is_final_scene=is_final_scene)

                sc_type = s.get("type") or ("broll_narration" if is_anime_broadcast else ("video_reaction" if idx == 0 else "card_focus"))
                if is_anime_broadcast and sc_type == "video_reaction":
                    sc_type = "broll_narration"
                elif idx == 0 and sc_type == "avatar_cam":
                    sc_type = "broll_narration" if is_anime_broadcast else "video_reaction"

                sc_cam = s.get("camera")
                if not sc_cam:
                    if idx == 0:
                        sc_cam = "pip_delayed"
                    elif idx == len(raw_scenes) - 1 and sc_type == "avatar_cam":
                        sc_cam = "hero_center"
                    else:
                        sc_cam = "pip_corner"
                elif idx == 0 and sc_cam == "hero_center":
                    sc_cam = "pip_delayed"

                vq = s.get("visual_query", topic)
                vq2 = s.get("visual_query2", "")
                v_beats = _clean_beats(s.get("visual_beats"))

                if is_anime_broadcast:
                    anime_name = "Black Clover"
                    known_series = [
                        "Black Clover", "Naruto", "Jujutsu Kaisen", "One Piece", "Bleach",
                        "Dragon Ball", "Demon Slayer", "My Hero Academia", "Attack on Titan",
                        "Hunter x Hunter", "Solo Leveling", "Chainsaw Man"
                    ]
                    for s_name in known_series:
                        if s_name.lower() in topic.lower():
                            anime_name = s_name
                            break

                    ep_anchor = ""
                    ep_m = re.search(r'(?:episodios?|episodes?|ep\.?)\s*([\d\s\-]+)', topic, re.IGNORECASE)
                    p_m = re.search(r'parte\s*(\d+)', topic, re.IGNORECASE)
                    if ep_m:
                        ep_anchor = f"Episode {ep_m.group(1).strip()}"
                    elif p_m:
                        p_val = int(p_m.group(1))
                        ep_anchor = f"Episode {(p_val-1)*3 + 1}"

                    def _sanitize_anime_term(raw_term: str) -> str:
                        noise = {"4k", "1080p", "hd", "video", "anime", "documentary", "footage", "clip", "scene"}
                        words = [w for w in re.findall(r'[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9]+', raw_term or "") if w.lower() not in noise and w.lower() not in anime_name.lower()]
                        content = " ".join(words[:4])
                        if ep_anchor and not any(k in content.lower() for k in ("ep", "episode", "episodio")):
                            return f"{anime_name} {ep_anchor} {content}".strip()
                        return f"{anime_name} {content}".strip()

                    vq = _sanitize_anime_term(vq)
                    if vq2:
                        vq2 = _sanitize_anime_term(vq2)
                    for b in v_beats:
                        if isinstance(b, dict) and b.get("query"):
                            b["query"] = _sanitize_anime_term(b["query"])

                v_queries = [q for q in [vq, vq2] if q]

                scenes.append(
                    DirectorScene(
                        scene_id=idx + 1,
                        name=s.get("name", f"Escena {idx + 1}"),
                        type=sc_type,
                        emotion=s.get("emotion", "excited"),
                        camera=sc_cam,
                        speech=polished_speech or raw_speech,
                        visual_query=vq,
                        visual_queries=v_queries,
                        visual_query2=vq2,
                        card=card_obj,
                        chips=s.get("chips", []),
                        # 'or "whoosh"': un "sfx": null del LLM (la clave existe) no
                        # debe dejar None — crasheaba el render de la escena.
                        sfx=(s.get("sfx") or "whoosh") if s.get("sfx") != "none" else "none",
                        duration_est=float(s.get("duration_est_sec", seconds_per_scene)),
                        visual_beats=v_beats,
                        popups=_clean_popups(s.get("popups")),
                        # free_title: el prompt exige producirlo y from_dict lo
                        # conservaba, pero esta ruta directa lo descartaba — los
                        # títulos libres del LLM solo aparecían tras la auditoría GLM.
                        free_title=s.get("free_title"),
                        case_frame=s.get("case_frame") if isinstance(s.get("case_frame"), int) else None,
                    )
                )

            if not scenes:
                raise ValueError("El director no devolvió escenas.")

            scenes = _deduplicate_cards_in_scenes(scenes)

            # Garantizar que las palabras y duración cubran la duración objetivo solicitada
            scenes = await self._ensure_duration_coverage(scenes, dur, topic, style)

            total_calc_dur = sum(s.duration_est for s in scenes)

            from core.youtube_title_optimizer import optimize_youtube_title
            plan_title = optimize_youtube_title(
                raw_topic=topic,
                style=style,
                duration_sec=dur,
                existing_plan_title=data.get("title"),
            )

            return DirectorBroadcastPlan(
                title=plan_title,
                topic=topic,
                style=style,
                scenes=scenes,
                chat_comments=data.get("chat_comments", []),
                total_est_duration=float(max(dur, total_calc_dur)),
            )

        except Exception as exc:
            safe_log(f"[AIDirector] Fallback a dirección base por error en Gemini: {exc}")
            return self._build_fallback_plan(topic, style, dur, case_soundbites=case_soundbites)

    async def _ensure_duration_coverage(
        self,
        scenes: List[DirectorScene],
        duration_target: int,
        topic: str,
        style: str
    ) -> List[DirectorScene]:
        """Garantiza que la narración generada tenga palabras y tiempo suficientes para cubrir la duración asignada."""
        if not scenes or duration_target < 40:
            return scenes

        total_words = sum(len(s.speech.split()) for s in scenes)
        target_words = round(duration_target * 1.85)
        min_acceptable_words = round(duration_target * 1.35)

        # Si ya cumple con las palabras mínimas requeridas, solo sincronizar duración estimada
        if total_words >= min_acceptable_words:
            for s in scenes:
                word_cnt = len(s.speech.split())
                s.duration_est = max(3.0, round(word_cnt / 1.75, 1))
            return scenes

        safe_log(
            f"[AIDirector] ⚠️ Duración insuficiente detectada: plan tiene {total_words} palabras "
            f"(~{total_words / 1.85:.0f}s), pero el objetivo configurado es {duration_target}s "
            f"({duration_target // 60}m). Expandiendo guión para respetar el tiempo asignado..."
        )

        words_needed_per_scene = max(35, round(target_words / len(scenes)))

        # 1. Intentar expansión profunda con IA (Gemini / NVIDIA)
        try:
            brief_scenes = [
                {"scene_id": s.scene_id, "name": s.name, "speech": s.speech}
                for s in scenes
            ]
            expand_prompt = (
                f"Eres un guionista y director audiovisual de élite. El plan para el video sobre '{topic}' "
                f"tiene una duración objetivo de {duration_target // 60} minutos ({duration_target} segundos), pero las locuciones "
                f"actuales son demasiado breves ({total_words} palabras en total) y deben alcanzar aproximadamente {target_words} palabras "
                f"(alrededor de {words_needed_per_scene} palabras por escena) para cubrir el tiempo con ritmo pausado y natural.\n\n"
                f"EXPANDE y profundiza sustancialmente la narración ('speech') de cada una de las {len(scenes)} escenas:\n"
                f"- Cada escena DEBE tener un párrafo de entre {round(words_needed_per_scene * 0.85)} y {round(words_needed_per_scene * 1.15)} palabras.\n"
                f"- Añade explicaciones causales paso a paso, curiosidades insólitas ('factor ¡guau!'), datos numéricos, fechas, comparaciones visuales y antecedentes reales.\n"
                f"- CERO relleno pomposo, CERO clichés de 'marco paradigmático'. Todo con lenguaje directo, apasionante y entretenido.\n"
                f"- Responde EXCLUSIVAMENTE con un JSON válido con este formato:\n"
                f"{{\n  \"expanded_scenes\": [\n    {{\"scene_id\": 1, \"speech\": \"...\"}}\n  ]\n}}\n\n"
                f"ESCENAS ACTUALES A EXPANDIR:\n{json.dumps(brief_scenes, ensure_ascii=False, indent=2)}"
            )

            raw = await asyncio.wait_for(
                asyncio.to_thread(
                    self.llm.generate,
                    expand_prompt,
                    json_mode=True,
                    deadline_sec=min(60.0, max(25.0, len(scenes) * 3.5)),
                ),
                timeout=min(65.0, max(28.0, len(scenes) * 4.0)),
            )

            from utils.json_validator import JSONValidator
            parsed = JSONValidator.extract_and_parse(raw)
            exp_list = parsed.get("expanded_scenes", []) if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else [])

            if exp_list and len(exp_list) == len(scenes):
                from utils.speech_normalizer import normalize_speech_for_tts
                for idx, exp in enumerate(exp_list):
                    new_sp = (exp.get("speech") or "").strip()
                    if len(new_sp.split()) > len(scenes[idx].speech.split()):
                        is_last = (idx == len(scenes) - 1)
                        scenes[idx].speech = normalize_speech_for_tts(new_sp, is_final_scene=is_last)

                new_total_words = sum(len(s.speech.split()) for s in scenes)
                safe_log(f"[AIDirector] ✓ Guión expandido con éxito mediante IA: {new_total_words} palabras (~{new_total_words / 1.85:.0f}s).")
        except Exception as exp_err:
            safe_log(f"[AIDirector] Fallback a enriquecedor narrativo determinista por error en IA: {exp_err}")

        # 2. Si la IA no expandió lo suficiente, enriquecedor determinista de respaldo
        scenes = self._enrich_speech_deterministically(scenes, topic, words_needed_per_scene)

        # Actualizar duración estimada por escena
        for s in scenes:
            w = len(s.speech.split())
            s.duration_est = max(8.0, round(w / 1.85, 1))

        return scenes

    def _enrich_speech_deterministically(
        self,
        scenes: List[DirectorScene],
        topic: str,
        target_words_per_scene: int,
    ) -> List[DirectorScene]:
        """Normaliza la locución de cada escena respetando el guión original del tema sin inyectar textos genéricos o descontextualizados."""
        from utils.speech_normalizer import normalize_speech_for_tts

        for idx, sc in enumerate(scenes):
            is_last = (idx == len(scenes) - 1)
            # Normalizar dicción para TTS sin alterar el contenido temático del guión
            sc.speech = normalize_speech_for_tts(sc.speech, is_final_scene=is_last)
            word_count = len(sc.speech.split())
            # Cadencia de locución broadcast realista (1.75 palabras por segundo)
            sc.duration_est = max(4.0, round(word_count / 1.75, 1))

        return scenes

    def _build_fallback_plan(
        self,
        topic: str,
        style: str,
        duration_target: int,
        case_soundbites: Optional[List[Dict[str, Any]]] = None,
    ) -> DirectorBroadcastPlan:
        """Plan de dirección de respaldo inteligente que escala dinámicamente en escenas y palabras según la duración solicitada."""
        from utils.speech_normalizer import normalize_speech_for_tts

        try:
            dur_int = int(duration_target) if duration_target is not None else 45
        except (ValueError, TypeError):
            dur_int = 45
        if 0 < dur_int <= 40:
            dur = dur_int * 60
        else:
            dur = dur_int
        dur = max(20, min(2400, dur))

        if dur <= 35:
            num_scenes = 2
        elif dur <= 60:
            num_scenes = 3
        elif dur <= 100:
            num_scenes = 4
        elif dur <= 180:
            num_scenes = 5
        elif dur <= 360:
            num_scenes = 7
        elif dur <= 600:
            num_scenes = 9
        elif dur <= 900:
            num_scenes = 12
        elif dur <= 1500:
            num_scenes = 15
        else:
            num_scenes = 18

        sec_per_scene = round(dur / num_scenes)
        words_per_scene = max(25, round(sec_per_scene * 1.85))

        stage_templates = [
            {
                "name": "Gancho & Enigma Inicial",
                "type": "avatar_cam",
                "emotion": "excited",
                "camera": "hero_center",
                "sfx": "whoosh",
                "card": None,
                "vq": f"{topic} mysterious documentary intro 4k",
                "vq2": f"{topic} investigation 4k",
                "base_intro": f"¿Qué ocurrió realmente con {topic} y cuál es el detalle insólito que casi todos pasaron por alto? ",
                "pool": [
                    "Durante mucho tiempo la versión más difundida en redes y medios dio por sentadas explicaciones que no se sostienen ante un análisis riguroso. ",
                    "Sin embargo, al revisar los registros oficiales y las pruebas documentadas paso a paso, emerge una sorpresa mayúscula. ",
                    "Hoy vamos a desentrañar cada una de las piezas con nombres, fechas y números claros, sin tecnicismos vacíos ni rodeos. ",
                    "Lo que van a descubrir en los próximos minutos cambia por completo el relato que nos contaron desde el principio. ",
                ]
            },
            {
                "name": "Antecedentes & Primeras Señales",
                "type": "video_reaction",
                "emotion": "curious",
                "camera": "pip_corner",
                "sfx": "impact",
                "card": SceneCard(
                    headline=f"Registro: {topic[:32]}",
                    body="Primeros registros documentados y antecedentes verificados.",
                    badge="ORIGEN HISTÓRICO",
                    stat="Fase 1",
                ),
                "vq": f"{topic} historical archival footage 4k",
                "vq2": f"{topic} origins documentary 4k",
                "base_intro": "Para entender cómo comenzó todo, debemos retroceder al momento exacto en que saltaron las primeras alarmas: ",
                "pool": [
                    "No fue un acontecimiento repentino ni producto del azar; hubo advertencias tempranas que muchos pasaron por alto. ",
                    "Quienes estuvieron allí recuerdan que las señales eran inequívocas, pero nadie quiso detener la marcha de los acontecimientos. ",
                    "Los testimonios de la época describen un clima de incertidumbre total mientras las piezas comenzaban a alinearse de forma irreversible. ",
                    "Fue la primera grieta en un sistema que parecía completamente bajo control. ",
                ]
            },
            {
                "name": "Evidencias & Primer Gran Hallazgo",
                "type": "card_focus",
                "emotion": "surprised",
                "camera": "pip_corner",
                "sfx": "chime",
                "card": SceneCard(
                    headline="Evidencia Material Verificada",
                    body="Auditoría pericial independiente y registros contrastados.",
                    badge="PRUEBA CLAVE",
                    stat="+340%",
                ),
                "vq": f"{topic} scientific analysis investigation 4k",
                "vq2": f"{topic} empirical evidence data 4k",
                "base_intro": "Miren con atención esta primera prueba material documentada que desmiente el relato simplista: ",
                "pool": [
                    "Al cruzar los informes técnicos con las mediciones empíricas en el terreno, las cifras no dejaron lugar a dudas. ",
                    "Estamos hablando de una diferencia contundente entre lo que se prometió y lo que realmente ocurrió. ",
                    "Cada documento auditado aporta una pieza indispensable que permite reconstruir la cronología con absoluta precisión forense. ",
                    "Un hallazgo contundente que dejó perplejos a los propios especialistas que investigaban el caso. ",
                ]
            },
            {
                "name": "La Declaración del Protagonista",
                "type": "video_reaction",
                "emotion": "serious",
                "camera": "pip_corner",
                "sfx": "impact",
                "card": SceneCard(
                    headline="Testimonio Directo",
                    body="Declaraciones clave del protagonista bajo escrutinio.",
                    badge="TESTIMONIO REAL",
                    stat="Registro Directo",
                ),
                "vq": f"{topic} interview statement press conference 4k",
                "vq2": f"{topic} speech reaction 4k",
                "base_intro": "Atención a la declaración pública del protagonista en ese instante crítico: ",
                "pool": [
                    "Sus palabras fueron escuchadas con suma cautela por analistas y observadores internacionales. ",
                    "Detrás de cada frase pronunciada había un intento evidente por matizar la magnitud de lo que estaba sucediendo tras bambalinas. ",
                    "Sin embargo, el contraste entre su discurso y los hechos materiales no tardó en hacerse evidente ante los ojos de la opinión pública. ",
                    "Fue el punto exacto donde la narrativa oficial comenzó a desmoronarse irremediablemente. ",
                ]
            },
            {
                "name": "El Gran Giro Inesperado",
                "type": "chat_debate",
                "emotion": "skeptical",
                "camera": "pip_corner",
                "sfx": "whoosh",
                "card": SceneCard(
                    headline="Contradicción Inexplicable",
                    body="Discrepancia entre la versión aceptada y las pruebas materiales.",
                    badge="EL GRAN GIRO",
                    stat="Punto de Quiebre",
                ),
                "vq": f"{topic} unexpected dilemma investigation 4k",
                "vq2": f"{topic} critical discovery turning point 4k",
                "base_intro": "Y es justo aquí donde la investigación toma un giro que nadie vio venir: ",
                "pool": [
                    "Cuando todos creían tener una explicación definitiva, un nuevo dato confidencial salió a la luz pública. ",
                    "La pregunta que nadie se había atrevido a formular hasta ese momento cambió radicalmente el eje de la discusión. ",
                    "¿Quién tomó la decisión final en secreto y por qué se mantuvieron ocultos estos informes durante tanto tiempo? ",
                    "La evidencia recopilada apunta a un factor humano determinante que muchos intentaron minimizar. ",
                ]
            },
            {
                "name": "Cifras & Datos que Desconciertan",
                "type": "card_focus",
                "emotion": "serious",
                "camera": "pip_corner",
                "sfx": "chime",
                "card": SceneCard(
                    headline="Métricas de Impacto Global",
                    body="Evaluación cuantitativa rigurosa y registros consolidados.",
                    badge="DATOS DUROS",
                    stat="Oficial 2026",
                ),
                "vq": f"{topic} global data metrics analysis 4k",
                "vq2": f"{topic} statistics charts comparison 4k",
                "base_intro": "Fíjense en estas cifras oficiales que dimensionan el verdadero alcance del fenómeno: ",
                "pool": [
                    "Para ponerlo en perspectiva tangible: el impacto registrado equivale a transformar por completo la dinámica de todo un sector. ",
                    "No se trata de estimaciones aproximadas, sino de datos consolidados a través de auditorías independientes y registros directos. ",
                    "Cada porcentaje y cada gráfico confirma que las consecuencias fueron mucho más profundas de lo que se admitió inicialmente. ",
                    "Un volumen de información que obliga a replantear cualquier conclusión previa sobre el tema. ",
                ]
            },
            {
                "name": "El Mecanismo Causal Detallado",
                "type": "avatar_cam",
                "emotion": "confident",
                "camera": "hero_center",
                "sfx": "whoosh",
                "card": None,
                "vq": f"{topic} technical causal mechanism explained 4k",
                "vq2": f"{topic} in depth documentary 4k",
                "base_intro": "Ahora bien, ¿cómo se explica científicamente y paso a paso este proceso? ",
                "pool": [
                    "Para entender la causa de raíz, imaginemos una cadena de dominó donde el primer movimiento desencadena una cascada inevitable. ",
                    "Cuando el parámetro inicial se desvió de su rango seguro, los mecanismos de compensación fallaron en cascada uno tras otro. ",
                    "Esto explica por qué incluso medidas de contención extraordinarias resultaron insuficientes para frenar el desenlace. ",
                    "Es una lección magistral de cómo interactúan la tecnología, la física y las decisiones humanas bajo presión. ",
                ]
            },
            {
                "name": "Archivos Desclasificados & Revelaciones",
                "type": "video_reaction",
                "emotion": "surprised",
                "camera": "pip_corner",
                "sfx": "impact",
                "card": SceneCard(
                    headline="Documentos Desclasificados",
                    body="Archivos históricos e informes técnicos desclasificados.",
                    badge="REVELACIÓN",
                    stat="Desclasificado",
                ),
                "vq": f"{topic} declassified archival records documents 4k",
                "vq2": f"{topic} secret investigation records 4k",
                "base_intro": "El verdadero enigma comenzó a resolverse cuando se publicaron estos expedientes desclasificados: ",
                "pool": [
                    "Página tras página, los informes internos demuestran que el desenlace era conocido con semanas de anticipación por los equipos técnicos. ",
                    "Existieron advertencias formales por escrito que advertían con exactitud meridiana lo que terminaría ocurriendo en el campo. ",
                    "Sin embargo, intereses corporativos y consideraciones de reputación hicieron que esas alarmas quedaran archivadas en un cajón. ",
                    "Una verdad incómoda que tardó décadas en salir a la superficie pero que hoy resulta innegable. ",
                ]
            },
            {
                "name": "Debate Abierto & Posturas Enfrentadas",
                "type": "chat_debate",
                "emotion": "skeptical",
                "camera": "pip_corner",
                "sfx": "whoosh",
                "card": SceneCard(
                    headline="Modelos en Conflicto",
                    body="Contraste de hipótesis científicas y posturas forenses.",
                    badge="DEBATE CIENTÍFICO",
                    stat="Evidencia vs Hipótesis",
                ),
                "vq": f"{topic} expert debate controversy analysis 4k",
                "vq2": f"{topic} scientific consensus divergence 4k",
                "base_intro": "Incluso hoy en día, las dos posturas más respetadas de la comunidad continúan en abierto debate: ",
                "pool": [
                    "Por una parte, la hipótesis tradicional defiende que se trató de una combinación extraordinaria de factores imprevisibles. ",
                    "Por la otra, la corriente revisionista demuestra con modelos computacionales modernos que el desenlace era predecible y evitable. ",
                    "Ambos bandos aportan argumentos de peso respaldados por análisis empíricos y fórmulas contrastadas. ",
                    "Es este diálogo riguroso el que mantiene vivo el interés y la pasión por resolver cada cabo suelto. ",
                ]
            },
            {
                "name": "Impacto en el Presente & Paralelismos",
                "type": "card_focus",
                "emotion": "serious",
                "camera": "pip_corner",
                "sfx": "chime",
                "card": SceneCard(
                    headline="Repercusiones en la Actualidad",
                    body="Cómo este caso sigue moldeando nuestro presente tecnológico y social.",
                    badge="ACTUALIDAD 2026",
                    stat="Impacto Vigente",
                ),
                "vq": f"{topic} modern world implications today 4k",
                "vq2": f"{topic} technological legacy 4k",
                "base_intro": "¿Y cómo nos afecta directamente todo esto en nuestra vida cotidiana hoy en día? ",
                "pool": [
                    "Mucho más de lo que imaginamos: los protocolos de seguridad y las normativas que hoy rigen nacieron directamente de este caso. ",
                    "Cada vez que utilizamos esta tecnología o nos enfrentamos a situaciones análogas, estamos aplicando las lecciones aprendidas a alto costo. ",
                    "Quienes ignoran la historia de este evento están condenados a repetir exactamente los mismos errores que llevaron al colapso. ",
                    "Una demostración palpable de que el pasado no está muerto, ni siquiera es pasado. ",
                ]
            },
            {
                "name": "La Pregunta que Permanece Abierta",
                "type": "video_reaction",
                "emotion": "curious",
                "camera": "pip_corner",
                "sfx": "whoosh",
                "card": SceneCard(
                    headline="El Misterio Pendiente",
                    body="La última interrogante que los expertos aún no logran responder.",
                    badge="PREGUNTA ABIERTA",
                    stat="Sin Resolver",
                ),
                "vq": f"{topic} unresolved questions future perspective 4k",
                "vq2": f"{topic} unanswered enigma 4k",
                "base_intro": "A pesar de todo lo descubierto, todavía existe una incógnita fascinante sin respuesta definitiva: ",
                "pool": [
                    "Hay un elemento del rompecabezas que sigue desafiando las explicaciones más sofisticadas de la ciencia contemporánea. ",
                    "Nuevas misiones y expediciones continúan buscando esa última pieza que permita cerrar definitivamente el caso. ",
                    "Es el recordatorio más elocuente de que nuestro conocimiento del mundo siempre tiene fronteras por expandir. ",
                    "Y que la curiosidad humana nunca se detiene ante lo que parece imposible de resolver. ",
                ]
            },
            {
                "name": "Conclusiones & Reflexión Final",
                "type": "avatar_cam",
                "emotion": "confident",
                "camera": "hero_center",
                "sfx": "chime",
                "card": None,
                "vq": "cinematic studio lighting outro documentary 4k",
                "vq2": "broadcast stream conclusion 4k",
                "base_intro": "Como hemos podido constatar a lo largo de este análisis, la realidad detrás de este tema supera cualquier ficción: ",
                "pool": [
                    "Analizar los hechos con rigor y sin prejuicios nos permite ver con claridad lo que otros pasan por alto. ",
                    "Quiero leer su perspectiva honesta en los comentarios: ¿conocían todos estos detalles o alguno los tomó por sorpresa? ",
                    "Dejen su punto de vista en el chat, compartan este video y suscríbanse para seguir descubriendo los misterios reales con evidencia verificada. ",
                    "Nos vemos en la próxima transmisión para seguir explorando juntos los límites del conocimiento. ",
                ]
            },
        ]

        def _build_speech_for_stage(intro: str, pool: list, target_w: int, is_final: bool) -> str:
            res = intro
            for phrase in pool:
                if len(res.split()) >= target_w:
                    break
                res += phrase
            while len(res.split()) < target_w:
                for phrase in pool:
                    if len(res.split()) >= target_w:
                        break
                    res += " " + phrase
            return normalize_speech_for_tts(res, is_final_scene=is_final)

        scenes: List[DirectorScene] = []
        soundbite_idx = 0

        for i in range(num_scenes):
            sc_id = i + 1
            is_first = (i == 0)
            is_final = (i == num_scenes - 1)

            if is_first:
                template = stage_templates[0]
            elif is_final:
                template = stage_templates[-1]
            else:
                inter_idx = 1 + ((i - 1) % (len(stage_templates) - 2))
                template = stage_templates[inter_idx]

            speech_text = _build_speech_for_stage(
                template["base_intro"],
                template["pool"],
                words_per_scene,
                is_final
            )

            # Si hay soundbites disponibles y esta escena es de tipo video_reaction, asignarle el soundbite
            assigned_sb_clip = None
            assigned_sb_quote = None
            assigned_sb_offset = None
            assigned_sb_dur = None
            if case_soundbites and template["type"] == "video_reaction" and soundbite_idx < len(case_soundbites):
                sb = case_soundbites[soundbite_idx]
                assigned_sb_clip = sb.get("clip_name")
                assigned_sb_quote = sb.get("quote")
                assigned_sb_offset = sb.get("offset")
                assigned_sb_dur = sb.get("duration")
                soundbite_idx += 1

            scenes.append(
                DirectorScene(
                    scene_id=sc_id,
                    name=template["name"],
                    type=template["type"],
                    emotion=template["emotion"],
                    camera=template["camera"],
                    speech=speech_text,
                    visual_query=template["vq"],
                    visual_queries=[template["vq"], template["vq2"]],
                    visual_query2=template["vq2"],
                    card=template["card"],
                    chips=[],
                    sfx=template["sfx"],
                    duration_est=float(sec_per_scene),
                    soundbite_clip=assigned_sb_clip,
                    soundbite_quote=assigned_sb_quote,
                    soundbite_offset=assigned_sb_offset,
                    soundbite_dur=assigned_sb_dur,
                )
            )

        total_est = sum(s.duration_est for s in scenes)
        from core.youtube_title_optimizer import optimize_youtube_title
        plan_title = optimize_youtube_title(raw_topic=topic, style=style, duration_sec=dur)
        return DirectorBroadcastPlan(
            title=plan_title,
            topic=topic,
            style=style,
            scenes=scenes,
            chat_comments=[
                {"user": "AstroTech", "badge": "VIP", "text": "¡Impresionante análisis KAI!"},
                {"user": "CodeMaster", "badge": "SUB", "text": "Totalmente de acuerdo con los datos presentados."},
                {"user": "NexusViewer", "badge": "VERIFIED", "text": "Las fuentes y pruebas no dejan dudas."},
            ],
            total_est_duration=float(max(dur, total_est)),
        )

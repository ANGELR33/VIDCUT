import re


def refine_speech_cadence(text: str) -> str:
    """
    Pule la cadencia oral del texto respetando la prosodia que el guionista
    (humano o LLM) diseñó. Edge-TTS respeta comas y puntos suspensivos como
    pausas reales, así que este pulido NUNCA elimina pausas legítimas:

    - NO toca comas de aposición ("Todo, absolutamente todo, cambió") ni comas
      antes de 'y' en incisos ("..., y con ello...") — antes las borraba y la
      voz perdía las pausas que el director pidió escribir.
    - NO colapsa puntos suspensivos '...' (pausa dramática del estilo podcast).
    - Solo corrige defectos mecánicos evidentes: comas duplicadas, comas sin
      espacio posterior (excepto decimales), espacios antes de coma y
      espacios faltantes después de punto.
    """
    if not text or len(text.strip()) < 5:
        return text

    clean = text.strip()

    # 1. Comas duplicadas o encadenadas: ',,,' → ','
    clean = re.sub(r',(\s*,)+', ',', clean)

    # 2. Espacios antes de coma: 'palabra ,' → 'palabra,'
    clean = re.sub(r'\s+,', ',', clean)

    # 3. Comas pegadas a la palabra siguiente (con espacio): 'dato,mas' → 'dato, mas'.
    #    El lookahead de dígito preserva los decimales españoles ('1,5 millones').
    clean = re.sub(r',([^\s\d])', r', \1', clean)

    # 4. Signos de exclamación/interrogación repetidos: '!!!' → '!', '???' → '?'.
    #    Los puntos suspensivos '...' se conservan: son pausa dramática intencional.
    clean = re.sub(r'([!?])\1+', r'\1', clean)

    # 5. Punto y coma reemplazado por punto para dar pausa respiratoria real en TTS
    clean = re.sub(r';\s*', '. ', clean)

    # 6. Punto pegado a la palabra siguiente: 'frase.Siguiente' → 'frase. Siguiente'
    #    (solo si sigue letra: nunca rompe decimales '3.14' ni siglas con puntos).
    clean = re.sub(r'\.(?=[A-ZÁÉÍÓÚÑ])', '. ', clean)

    # 7. Dos puntos con espacio asegurado para pausa prosódica
    clean = re.sub(r':(?=[^\s\d])', ': ', clean)

    # 8. Micro-pausas respiratorias en marcadores discursivos orales clave
    discourse_markers_comma = [
        "sin embargo", "por lo tanto", "por eso", "en realidad",
        "de hecho", "es decir", "por ejemplo", "en consecuencia",
        "pero ojo", "ojo con esto", "y lo más curioso", "ahora bien",
        "al mismo tiempo", "en paralelo", "por otra parte"
    ]
    for marker in discourse_markers_comma:
        # Si el marcador está al inicio de frase o tras puntuación, y no le sigue coma/punto
        clean = re.sub(
            rf'(?i)(\b|^|\.\s+|\!\s+|\?\s+)({re.escape(marker)})(?!\s*[,:;.!?])',
            r'\1\2,',
            clean
        )

    discourse_markers_colon = [
        "miren esto", "fíjense en esto", "atención a esto",
        "el resultado", "la clave", "un detalle fascinante",
        "miren lo que dijo", "escuchen lo que dijo", "escuchen sus declaraciones",
        "esto fue lo que afirmó", "atención a sus palabras", "en sus propias palabras",
        "escuchen con atención", "miren sus declaraciones", "vean lo que sucedió",
        "escuchémoslo", "escuchen esto"
    ]
    for marker in discourse_markers_colon:
        clean = re.sub(
            rf'(?i)(\b|^|\.\s+|\!\s+|\?\s+)({re.escape(marker)})(?!\s*[,:;.!?])',
            r'\1\2:',
            clean
        )

    # 9. Romper oraciones corridas excesivamente largas (>16 palabras sin pausa) antes de conjunciones
    words = clean.split()
    if len(words) > 16:
        # Insertar coma antes de conjunciones coordinadas o subordinadas si la cláusula previa es larga
        # Evitar crear ',,' o ', ,'
        clean = re.sub(
            r'(\b\w+\b(?:\s+\b\w+\b){9,18})\s+(pero|porque|ya que|mientras que|lo que|lo cual)\s+',
            r'\1, \2 ',
            clean,
            flags=re.IGNORECASE
        )

    # Limpieza final de posibles comas redundantes generadas
    clean = re.sub(r'\s*,\s*,+', ', ', clean)
    clean = re.sub(r'\s{2,}', ' ', clean)

    return clean


def clean_hyphenated_acronyms(text: str) -> str:
    """
    Convierte siglas artificialmente divididas por guiones ('A-D-N' -> 'ADN', 'I-A' -> 'IA', 'N-A-S-A' -> 'NASA')
    para que la voz neuronal de Edge-TTS las lea de forma fluida y natural, sin deletreos
    robóticos ni pausas incómodas entre letras.
    """
    if not text:
        return ""
    # Siglas de 2 a 6 letras mayúsculas separadas por guiones (ej. A-D-N, N-A-S-A, O-N-U, I-A)
    return re.sub(r'\b[A-ZÁÉÍÓÚÑ](?:-[A-ZÁÉÍÓÚÑ]){1,5}\b', lambda m: m.group(0).replace("-", ""), text)


def strip_video_time_mentions(text: str) -> str:
    """
    Elimina menciones explícitas de la duración del video ('en estos 30 minutos',
    'en esta serie de treinta minutos', 'en los próximos 10 minutos', etc.)
    para que la locución sea atemporal, natural y no contradiga la duración real de la emisión.
    """
    if not text:
        return ""

    time_patterns = [
        r"(?i)\b(?:a lo largo de|en|durante)\s+(?:esta serie de|este video de|este episodio de|estos?|los?|los próximos?)\s+(?:\d+|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte|veinticinco|treinta|cuarenta|cincuenta|sesenta)\s+minutos\b,?\s*",
        r"(?i)\b(?:en esta serie de|en este video de)\s+\w+\s+minutos\b,?\s*",
        r"(?i)\b(?:en estos?|en los próximos?|a lo largo de estos?)\s+\d+\s+minutos\b,?\s*",
        r"(?i)\b(?:durante los próximos?|en los siguientes?)\s+(?:\d+|\w+)\s+minutos\b,?\s*",
        r"(?i)\b(?:en esta media hora|durante esta media hora)\b,?\s*",
        r"(?i)\b(?:en estos|en los próximos)\s+\d+\s+segundos\b,?\s*",
    ]

    clean = text
    for pat in time_patterns:
        clean = re.sub(pat, "", clean)

    # Limpiar posibles comas o espacios dobles huérfanos tras la eliminación
    clean = re.sub(r"\s*,\s*,+", ", ", clean)
    clean = re.sub(r"^\s*,\s*", "", clean)
    clean = re.sub(r"\s{2,}", " ", clean)
    return clean.strip()


def clean_premature_farewells(text: str) -> str:
    """
    Elimina despedidas o llamados a suscripción prematuros en escenas intermedias
    ('gracias por acompañarme', 'suscríbanse', 'nos vemos en el próximo video').
    """
    if not text:
        return ""

    farewell_patterns = [
        r"(?i)\b(?:gracias por acompañarme|gracias por ver|gracias por acompañarnos|gracias por su atención|gracias por estar ahí)[^.!?]*[.!?]?",
        r"(?i)\b(?:suscríbanse|suscríbete|no olviden suscribirse|no olvides suscribirte)[^.!?]*[.!?]?",
        r"(?i)\b(?:nos vemos en el próximo video|nos vemos en el próximo|nos vemos en el siguiente video|nos vemos en la próxima|hasta el próximo video|hasta la próxima)[^.!?]*[.!?]?",
        r"(?i)\b(?:hasta aquí este análisis|hasta aquí llegamos hoy|hasta aquí el video de hoy)[^.!?]*[.!?]?",
        r"(?i)\b(?:dejen su like|deja tu like|dale like al video)[^.!?]*[.!?]?",
    ]

    clean = text
    for pat in farewell_patterns:
        clean = re.sub(pat, "", clean)

    clean = re.sub(r"\s{2,}", " ", clean).strip()
    return clean


def enhance_speech_emphasis(text: str) -> str:
    """
    Convierte marcas de énfasis de guion (*palabra*, [énfasis: ...]) en
    puntuación prosódica natural (dos puntos suspensivos y exclamación limpia)
    para que las voces neuronales de Edge-TTS / Azure pronuncien con relieve,
    fuerza y peso acústico humano en los momentos clave.
    """
    if not text:
        return ""

    clean = text

    # 1. Convertir asteriscos estilo markdown (*palabra* o **frase**) en exclamación prosódica
    clean = re.sub(r'\*{1,2}([^*]+?)\*{1,2}', r'¡\1!', clean)

    # 2. Convertir etiquetas explícitas [énfasis: ...] o [fuerte: ...]
    clean = re.sub(r'\[(?:énfasis|enfasis|fuerte|impacto):\s*([^\]]+)\]', r': ¡\1!', clean, flags=re.IGNORECASE)

    # 3. Limpieza de puntuación accidental redundante
    clean = re.sub(r'¡{2,}', '¡', clean)
    clean = re.sub(r'!{2,}', '!', clean)
    clean = re.sub(r':\s*:', ':', clean)
    clean = re.sub(r'\s{2,}', ' ', clean)

    return clean.strip()


def normalize_speech_for_tts(text: str, is_final_scene: bool = True) -> str:
    """
    Normalización limpia y de alta fidelidad para Edge-TTS:
    - Conserva 100% los acentos, tildes y entonación humana natural.
    - Elimina menciones erróneas de duraciones fijas ('en estos 30 minutos').
    - Elimina despedidas prematuras en escenas intermedias si is_final_scene es False.
    - Convierte porcentajes fonéticamente ('25%' -> '25 por ciento').
    - Limpia siglas con guiones para pronunciación fluida ('A-D-N' -> 'ADN').
    - Aplica modulación de énfasis prosódico natural en palabras clave.
    - Pulir cadencia sin introducir frenadas o cortes en seco.
    """
    if not text:
        return ""

    # Limpiar saltos de línea y espacios repetidos
    text = re.sub(r"\r?\n+", " ", text)
    text = re.sub(r"[ \t]+", " ", text).strip()

    # Eliminar menciones de tiempo
    text = strip_video_time_mentions(text)

    # Si es escena intermedia, eliminar despedidas o conclusiones prematuras
    if not is_final_scene:
        text = clean_premature_farewells(text)

    # Des-guionar siglas mayúsculas artificiales
    text = clean_hyphenated_acronyms(text)

    # Normalizar porcentaje para lectura fonética correcta
    text = re.sub(r"(\d+)\s*%", r"\1 por ciento", text)

    # Incorporar marcas de relieve y énfasis prosódico
    text = enhance_speech_emphasis(text)

    # Pulir cadencia sin introducir frenadas o cortes en seco
    text = refine_speech_cadence(text)

    return text



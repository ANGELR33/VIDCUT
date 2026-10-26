import asyncio
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from PIL import Image

from core.llm import LLMClient, safe_log
from core.run_log import log_count, log_llm, log_service
from core.source_trust import assess_sources
from core.models import InfoCard, SourceRef, VideoEditingPlan
from core.web_media import WikiMediaClient
from utils.json_validator import JSONValidator

# Tipos de tarjeta que describen QUÉ ES algo (persona, ley, institución...). Se muestran si la web
# confirma la entidad; no hace falta que la web repita lo que opinó el hablante.
ENTITY_KINDS = {"persona", "organizacion", "organización", "lugar", "ley", "concepto", "hardware", "definicion"}

JUDGE_PROMPT = """Eres un verificador de datos estricto. Trabajas SOLO con la EVIDENCIA (fragmentos reales de la web).

TIPO DE TARJETA: {mode}
TEMA: {headline}
LO QUE SE DIJO EN EL VIDEO: {claim}

EVIDENCIA:
{evidence}

INSTRUCCIONES SEGÚN EL TIPO:
- Si TIPO = "entidad" o "definicion": decide si la evidencia identifica claramente al TEMA (quién es la persona, qué es la ley, institución, lugar, término o concepto).
  * "supported": la evidencia describe o define el TEMA. Escribe en "summary" una definición o descripción neutral y clara usando solo la evidencia.
  * "contradicted": la evidencia demuestra que lo dicho sobre el tema es falso.
  * "insufficient": la evidencia no habla del tema.
  NO exijas que la evidencia mencione al hablante del video ni sus opiniones.
- Si TIPO = "dato": decide si la evidencia confirma el DATO concreto (cifra, fecha, hecho), sin importar quién lo dijo.
  * "supported": la evidencia confirma lo esencial del dato. "summary" = el dato confirmado, redactado de forma neutral.
  * "contradicted": la evidencia da otra cifra, fecha o hecho.
  * "insufficient": no se puede confirmar ni desmentir.

REGLAS:
- Prohibido inventar datos fuera de la evidencia. Ante la duda: "insufficient".
- "summary": máximo 180 caracteres en español. Debe ser ENRIQUECEDOR: destaca cifras concretas, organismos de referencia (ej. NASA, OIT, tribunales, ministerios, leyes específicas) o hechos contrastados que aporten alto valor informativo. Vacío si el veredicto no es "supported".
- "stat": si el dato confirmado tiene una cifra o porcentaje protagonista (ej. "26.743", "40%", "1994", "541 días"), extráela exactamente aquí; si no, "".
- "correction": SI el veredicto es "contradicted", escribe aquí la frase de corrección con datos contundentes y la entidad/norma que lo desmiente (ej. "La pena real fijada por ley es de 541 días a 3 años, no 15 años."). Si no es contradicted, déjalo vacío.
- "corrected_value": SI el veredicto es "contradicted", escribe aquí el DATO EXACTO CORREGIDO (ej. "541 días a 3 años", "8.4%", "Ley 21.208"). Si no, "".
- "source_indexes": números de los fragmentos usados.
- "reason": una frase corta que explique el veredicto.

Responde SOLO con JSON: {{"verdict": "...", "summary": "...", "stat": "", "correction": "...", "corrected_value": "...", "source_indexes": [1], "reason": "..."}}"""


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""


def _is_bad_image_url(url: str) -> bool:
    """Detecta logos, iconos de Wikipedia, símbolos y placeholders vectoriales."""
    if not url:
        return True
    u = url.lower()
    bad_tokens = (
        "logo", "icon", "symbol", "wikipedia", "wikimedia", "disambig",
        "question", "default", "placeholder", ".svg", "flag", "bandera",
        "escudo", "coat_of_arms", "shield", "emblem", "sign", "arrow",
        "pixel", "blank", "commons-logo"
    )
    return any(token in u for token in bad_tokens)


def _valid_image(path: Path, min_side: int = 220) -> bool:
    """Descarta HTML disfrazado de imagen, archivos corruptos, miniaturas y logos planos."""
    try:
        with Image.open(path) as im:
            im.verify()
        with Image.open(path) as im:
            if min(im.size) < min_side:
                return False
            # Verificar variedad cromática: los logos planos/vectoriales tienen muy pocos colores
            small = im.convert("RGB").resize((32, 32), Image.NEAREST)
            colors = len(set(small.getdata()))
            if colors < 28:
                # Menos de 28 colores en 1024 pixeles es casi con certeza un icono o logo plano
                return False
            return True
    except Exception:
        return False


class FactChecker:
    """
    Verifica cada tarjeta contra la web real ANTES de que aparezca en el video.

    1. Busca en internet (DuckDuckGo, región es) + Wikipedia.
    2. Gemini actúa como juez usando SOLO esos fragmentos (no su memoria).
    3. Solo las tarjetas "supported" se dibujan. Lo falso ("contradicted") o no confirmado nunca sale en el video.
    4. Busca una foto real fotográfica y la valida antes de usarla (nunca logos de Wikipedia).
    """

    def __init__(self, llm: LLMClient, workdir: Path, concurrency: int = 3):
        self.llm = llm
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.wiki = WikiMediaClient()
        self._sem = asyncio.Semaphore(concurrency)
        self._web_cache: Dict[str, List[Dict[str, str]]] = {}
        self._web_cache_lock = asyncio.Lock()

    # ---------- búsqueda ----------
    @staticmethod
    def _web_search(query: str, max_results: int = 6) -> List[Dict[str, str]]:
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region="es-es", max_results=max_results))
            log_service("ddgs_search", ok=True)
            return [{"title": r.get("title", ""), "url": r.get("href", ""), "text": r.get("body", "")}
                    for r in results if r.get("href")]
        except Exception as exc:
            safe_log(f"[FactChecker] Búsqueda web falló para '{query}': {exc}")
            log_service("ddgs_search", ok=False)
            return []

    @staticmethod
    def _web_image_search(query: str, max_results: int = 8) -> List[str]:
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.images(query, max_results=max_results))
            urls = []
            for r in results:
                url = r.get("image") or ""
                w, h = int(r.get("width") or 0), int(r.get("height") or 0)
                if url.startswith("http") and not _is_bad_image_url(url) and (not w or min(w, h) >= 300):
                    urls.append(url)
            return urls
        except Exception as exc:
            safe_log(f"[FactChecker] Búsqueda de imágenes falló para '{query}': {exc}")
            return []

    async def fetch_real_image(self, query: str, dest_stem: str, wiki_url: Optional[str] = None) -> Optional[str]:
        """Foto real: primero Wikipedia (si no es logo), luego imágenes web. Siempre validada fotográficamente."""
        candidates = []
        if wiki_url and not _is_bad_image_url(wiki_url):
            candidates.append(wiki_url)
        try:
            web_candidates = await asyncio.wait_for(
                asyncio.to_thread(self._web_image_search, query), timeout=12
            )
            candidates.extend(web_candidates)
        except asyncio.TimeoutError:
            safe_log(f"[FactChecker] La búsqueda de imágenes tardó demasiado para '{query}'.")

        for i, url in enumerate(candidates[:4]):
            dest = self.workdir / f"{dest_stem}_{i}.img"
            if await self.wiki.download_image(url, dest) and _valid_image(dest):
                return str(dest)
            dest.unlink(missing_ok=True)
        return None

    async def _gather_evidence(self, card: InfoCard, progress: Optional[Callable[[str], None]] = None):
        queries = [card.search_query]
        if card.headline and card.headline.lower() not in card.search_query.lower():
            queries.append(card.headline)
        async def search(query: str) -> List[Dict[str, str]]:
            async with self._web_cache_lock:
                cached = self._web_cache.get(query)
            if cached is not None:
                return cached
            try:
                found = await asyncio.wait_for(asyncio.to_thread(self._web_search, query), timeout=12)
            except asyncio.TimeoutError:
                safe_log(f"[FactChecker] La búsqueda web tardó demasiado para '{query}'.")
                found = []
            async with self._web_cache_lock:
                self._web_cache[query] = found
            return found

        for q in queries:
            if progress:
                progress(f"Buscando información para «{card.headline}»: {q}")
        found_groups = await asyncio.gather(*(search(q) for q in queries))
        web: List[Dict[str, str]] = [item for group in found_groups for item in group]
        if progress:
            progress(f"Consultando Wikipedia para «{card.headline}».")
        wiki = await self.wiki.search(card.image_query or card.headline)

        seen, evidence = set(), []
        if wiki:
            evidence.append({"title": f"{wiki.title} - Wikipedia", "url": wiki.page_url, "text": wiki.extract})
            seen.add(wiki.page_url)
        for e in web:
            if e["url"] not in seen:
                seen.add(e["url"])
                evidence.append(e)
        return evidence[:9], wiki

    # ---------- veredicto ----------
    def _judge(self, card: InfoCard, evidence: List[Dict[str, str]], mode: str,
               progress: Optional[Callable[[str], None]] = None) -> Dict:
        numbered = "\n".join(
            f"[{i}] {e['title']} ({_domain(e['url'])}): {e['text'][:450]}"
            for i, e in enumerate(evidence, start=1)
        )
        prompt = JUDGE_PROMPT.format(mode=mode, headline=card.headline, claim=card.claim, evidence=numbered)

        # 1. Intentar con NVIDIA Kimi-k3 / Nemotron (Razonamiento profundo ultra-preciso)
        from config.settings import settings
        if settings.NVIDIA_API_KEY:
            try:
                from openai import OpenAI
                nv_client = OpenAI(
                    base_url="https://integrate.api.nvidia.com/v1",
                    api_key=settings.NVIDIA_API_KEY,
                    timeout=30.0,
                )
                active_model = getattr(settings, "NVIDIA_MODEL", "nvidia/nemotron-3.5-lightning-30b-a3b")
                model_name = "Nemotron" if "nemotron" in active_model.lower() else ("Kimi" if "kimi" in active_model.lower() else active_model)
                safe_log(f"[FactChecker] Auditando «{card.headline}» con {model_name} ({active_model})...")
                call_kwargs = {
                    "model": active_model,
                    "messages": [
                        {"role": "system", "content": "Eres un auditor y verificador de hechos estricto. Responde siempre con JSON puro sin markdown ni explicaciones previas."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1024,
                }
                if "nemotron" in active_model.lower():
                    call_kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}

                _t0 = time.monotonic()
                response = nv_client.chat.completions.create(**call_kwargs)
                _u = getattr(response, "usage", None)
                log_llm("nvidia", active_model, "verificacion_dato",
                        input_tokens=int(getattr(_u, "prompt_tokens", 0) or 0),
                        output_tokens=int(getattr(_u, "completion_tokens", 0) or 0),
                        latency_sec=time.monotonic() - _t0)
                msg = response.choices[0].message
                raw_text = (msg.content or getattr(msg, "reasoning_content", "") or "").strip()
                parsed = JSONValidator.extract_and_parse(raw_text)
                if parsed and isinstance(parsed, dict) and "verdict" in parsed:
                    safe_log(f"[FactChecker] Veredicto exitoso de {model_name}: {parsed.get('verdict')}")
                    return parsed
            except Exception as exc:
                safe_log(f"[FactChecker] Proveedor NVIDIA no disponible ({exc}). Continuando con Gemini...")

        # 2. Respaldo transparente en Gemini
        return JSONValidator.extract_and_parse(
            self.llm.generate(prompt, json_mode=True, progress=progress, max_models=1, purpose="verificacion_dato")
        )

    async def verify_card(self, card: InfoCard,
                          progress: Optional[Callable[[str], None]] = None) -> InfoCard:
        async with self._sem:
            mode = "entidad" if (card.kind or "").lower() in ENTITY_KINDS else "dato"
            evidence, wiki = await self._gather_evidence(card, progress)
            if not evidence:
                card.verdict, card.note = "insufficient", "La búsqueda web no devolvió resultados."
                return card

            try:
                if progress:
                    progress(f"Contrastando «{card.claim}» con {len(evidence)} fuentes recopiladas.")
                result = await asyncio.to_thread(self._judge, card, evidence, mode, progress)
            except Exception as exc:
                card.verdict, card.note = "insufficient", f"No se pudo verificar: {str(exc)[:90]}"
                return card

            verdict = str(result.get("verdict", "insufficient")).lower()
            card.verdict = verdict if verdict in ("supported", "contradicted", "insufficient") else "insufficient"
            card.note = str(result.get("reason", ""))[:200]

            idxs = [i for i in result.get("source_indexes", []) if isinstance(i, int) and 1 <= i <= len(evidence)]
            card.sources = [
                SourceRef(title=evidence[i - 1]["title"][:90], url=evidence[i - 1]["url"],
                          domain=_domain(evidence[i - 1]["url"]))
                for i in idxs[:3]
            ]

            if card.verdict in ("supported", "contradicted"):
                trusted, why = assess_sources(card.kind, card.verdict, [s.domain for s in card.sources])
                if not trusted:
                    safe_log(f"[FactChecker] «{card.headline}» descartada por fuentes débiles: {why}")
                    log_count("tarjeta_fuentes_debiles")
                    card.verdict = "insufficient"
                    card.note = f"Fuentes insuficientes: {why}."
                    card.sources = []

            if card.verdict == "insufficient":
                card.body = "No se encontraron fuentes confiables en la web que puedan demostrar o refutar esta afirmación."
                if not card.note.startswith("Fuentes insuficientes"):
                    card.note = "Información no verificable."
                return card

            # Si es supported
            if card.verdict == "supported":
                summary = str(result.get("summary", "")).strip()
                if not summary or not card.sources:
                    card.verdict, card.note = "insufficient", "Sin resumen o sin fuente citable."
                    return card
                card.body = summary
                stat = str(result.get("stat", "")).strip()
                if stat and card.card_style == "stat_highlight":
                    card.stat_value = stat[:14]
            
            # Si es contradicted (Correction Engine)
            elif card.verdict == "contradicted":
                correction = str(result.get("correction", "")).strip()
                corrected_val = str(result.get("corrected_value", "")).strip()
                if not correction or not card.sources:
                    card.verdict, card.note = "insufficient", "Sin corrección o sin fuente citable."
                    return card
                card.correction = correction
                card.corrected_value = corrected_val[:20]
                card.correction_source = card.sources[0].domain

            abstract_kinds = {"ley", "normativa", "articulo", "cifra", "estadistica", "concepto", "definicion"}
            should_fetch_photo = bool(card.image_query or (card.kind or "").lower() not in abstract_kinds)
            if should_fetch_photo:
                if progress:
                    progress(f"Buscando imagen de apoyo fotográfico para «{card.headline}».")
                card.image_path = await self.fetch_real_image(
                    card.image_query or card.headline, f"{card.card_id}_photo",
                    wiki.image_url if (wiki and not _is_bad_image_url(wiki.image_url)) else None,
                )
            else:
                card.image_path = None
            return card

    async def verify_plan(self, plan: VideoEditingPlan,
                          progress: Optional[Callable[[str], None]] = None) -> VideoEditingPlan:
        if not plan.info_cards:
            return plan
        safe_log(f"[FactChecker] Verificando {len(plan.info_cards)} datos contra la web...")
        labels = {"supported": "confirmado en la web", "contradicted": "FALSO, se descarta",
                  "insufficient": "sin evidencia, se descarta"}

        async def run(card: InfoCard) -> InfoCard:
            result = await self.verify_card(card, progress)
            if progress:
                progress(f"Dato '{card.headline}': {labels.get(result.verdict, result.verdict)}")
            return result

        plan.info_cards = list(await asyncio.gather(*[run(c) for c in plan.info_cards]))
        ok = sum(1 for c in plan.info_cards if c.verdict == "supported")
        corrected = sum(1 for c in plan.info_cards if c.verdict == "contradicted")
        unverified = sum(1 for c in plan.info_cards if c.verdict == "insufficient")
        safe_log(f"[FactChecker] {ok} confirmados, {corrected} correcciones, {unverified} no verificables.")
        return plan

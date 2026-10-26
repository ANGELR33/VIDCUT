import os
import re
import asyncio
import abc
import json
import shutil
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional, Dict, Any
from config.settings import settings
from core.models import BRollCue
from core.llm import safe_log


def has_word(text: str, word: str) -> bool:
    """True si `word` aparece en `text` como palabra o frase completa.

    Evita falsos positivos de subcadena: "fe" no coincide con "coffee" ni "ia"
    con "media".
    """
    if not word:
        return False
    return re.search(rf"(?<!\w){re.escape(word.lower())}(?!\w)", (text or "").lower()) is not None


def content_tokens(text: str, stop: Optional[set] = None) -> list:
    """Palabras sustantivas (>=3 letras) de una consulta, sin duplicados y en orden."""
    stop = stop or set()
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]{3,}", text or "")]
    return [t for t in dict.fromkeys(tokens) if t not in stop]


def required_token_matches(n_tokens: int) -> int:
    """Cuántas palabras de la consulta deben aparecer para aceptar un candidato.

    Con consultas de 1-2 palabras basta una; con 3 o más se exigen al menos 2.
    """
    return 1 if n_tokens <= 2 else 2


class AssetProvider(abc.ABC):
    """Interfaz base para proveedores de recursos multimedia (B-Roll)."""

    @abc.abstractmethod
    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        """Busca el activo más relevante y lo descarga de forma asíncrona en target_dir."""
        pass


class LocalOriginalAssetProvider(AssetProvider):
    """Biblioteca de material ORIGINAL del canal (assets/broll).

    Sin stock ni bancos genéricos: solo metraje/fotos propios, de archivo del
    canal o material oficial que el usuario haya depositado aquí.
    """

    MEDIA_SUFFIXES = (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".jpg", ".jpeg", ".png", ".webp")

    def __init__(self):
        self.root = settings.BASE_DIR / "assets" / "broll"

    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        if not self.root.exists():
            return None
        query = cue.search_query_en or cue.concept or ""
        tokens = content_tokens(query)
        if not tokens:
            return None
        needed = required_token_matches(len(tokens))

        best_path = None
        best_score = 0
        for path in self.root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in self.MEDIA_SUFFIXES:
                continue
            rel = str(path.relative_to(self.root)).lower()
            score = sum(1 for token in tokens if token in rel)
            if score > best_score:
                best_score = score
                best_path = path

        if not best_path or best_score < needed:
            return None

        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / f"{cue.cue_id}{best_path.suffix.lower()}"
        try:
            shutil.copy2(best_path, out_path)
        except Exception as exc:
            safe_log(f"[LocalOriginal] No se pudo copiar {best_path.name}: {exc}")
            return None

        prov = {
            "source_url": str(best_path),
            "source_name": "Biblioteca original del canal",
            "license": "Material propio / original",
            "artist": "Canal",
            "date": "",
            "visual_nature": "documental_real",
            "attribution_badge": "MATERIAL PROPIO",
            "context_note": str(best_path.relative_to(self.root)),
        }
        try:
            (target_dir / f"{cue.cue_id}_provenance.json").write_text(
                json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass
        safe_log(f"[LocalOriginal] Usando material propio: {best_path.name} (score={best_score})")
        return out_path



class OriginalSourceAssetProvider(AssetProvider):
    """Material original/oficial en fuentes permitidas: Wikimedia, Archive, NASA,
    gobiernos, universidades y salas de prensa de empresas tecnológicas.

    Sin stock genérico. La consulta la sigue escribiendo la IA (Gemini/DeepSeek)
    desde el plan; este proveedor la dirige a fuentes originales y archiva la
    procedencia/licencia.
    """

    def __init__(self):
        self.used_urls: set = set()

    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        query = cue.search_query_en or cue.concept
        if not query:
            return None

        def _search() -> list:
            try:
                from ddgs import DDGS
                from core.licensing import classify_license
            except Exception:
                return []

            clean_q = re.sub(r"\b(4k|hd|footage|futuristic|screen|real footage|documentary|abstract|animation|broll)\b", "", query, flags=re.I).strip()
            clean_q = " ".join(dict.fromkeys(clean_q.split()))

            # Búsquedas orgánicas directas basadas en el concepto visual diseñado por el Director
            queries = [
                clean_q,
                f"{clean_q} official archive",
                f"{clean_q} high resolution",
            ]
            candidates = []
            try:
                # Palabras clave sustantivas del tema para verificar correspondencia temática real
                query_tokens = set(content_tokens(clean_q, {
                    "foto", "photo", "image", "imagen", "video", "real", "official",
                    "archive", "high", "resolution", "4k", "footage", "documentary",
                    "photograph", "historical", "original", "evidence", "screen", "wallpaper"
                }))
                needed_matches = required_token_matches(len(query_tokens))
                with DDGS(timeout=6) as ddgs:
                    for q in queries:
                        try:
                            batch = list(ddgs.images(q, max_results=8))
                        except Exception:
                            continue
                        for item in batch:
                            image_url = item.get("image") or ""
                            page_url = item.get("url") or ""
                            title = (item.get("title") or "").lower()
                            if not image_url.startswith("http") or image_url in self.used_urls:
                                continue
                            
                            # Filtro dinámico de correspondencia: si el buscador devolvió un resultado
                            # sin relación con los términos de búsqueda (fallback espurio), descartarlo
                            candidate_text = f"{title} {page_url.lower()} {image_url.lower()}"
                            if query_tokens and sum(1 for t in query_tokens if t in candidate_text) < needed_matches:
                                continue

                            lic = classify_license(page_url or image_url)
                            if not lic.get("allowed"):
                                continue
                            candidates.append((image_url, page_url, lic))
                            if len(candidates) >= 10:
                                break
                        if len(candidates) >= 10:
                            break
            except Exception as exc:
                safe_log(f"[OriginalSource] Búsqueda falló: {exc}")
            return candidates

        candidates = await asyncio.to_thread(_search)
        if not candidates:
            return None

        from PIL import Image
        from core.web_media import WikiMediaClient
        client = WikiMediaClient()

        min_w = 700
        min_h = 380

        for index, (image_url, page_url, lic) in enumerate(candidates):
            out_path = target_dir / f"{cue.cue_id}_orig{index}.jpg"
            self.used_urls.add(image_url)
            if not await client.download_image(image_url, out_path):
                continue
            try:
                with Image.open(out_path) as im:
                    if im.size[0] < min_w or im.size[1] < min_h:
                        out_path.unlink(missing_ok=True)
                        continue
                    width, height = im.size
            except Exception:
                out_path.unlink(missing_ok=True)
                continue

            prov = {
                "source_url": page_url or image_url,
                "source_name": f"Fuente original/oficial ({lic.get('domain', 'archivo')})",
                "license": lic.get("class", "licensed_or_public"),
                "artist": lic.get("domain", ""),
                "date": "",
                "visual_nature": "documental_real",
                "attribution_badge": "ARCHIVO ORIGINAL",
                "context_note": query,
                "monetization_safe": bool(lic.get("monetization_safe")),
                "license_note": lic.get("note", ""),
            }
            try:
                (target_dir / f"{cue.cue_id}_provenance.json").write_text(
                    json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except OSError:
                pass
            safe_log(
                f"[OriginalSource] Usando {lic.get('domain')} ({lic.get('class')}) "
                f"para '{query}' -> {out_path.name} ({width}x{height})"
            )
            return out_path
        return None


class PixabayAssetProvider(AssetProvider):
    """Proveedor de stock utilizando la API de Pixabay (videos y fotos de alta resolución)."""

    BASE_URL_VIDEOS = "https://pixabay.com/api/videos/"
    BASE_URL_PHOTOS = "https://pixabay.com/api/"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.PIXABAY_API_KEY
        self.used_ids = set()

    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        if not self.api_key:
            return None

        query = cue.search_query_en or cue.concept
        print(f"[PixabayProvider] Buscando recurso para '{query}' ({cue.asset_type})...")

        # 1. Intentar video primero si el tipo es video
        if cue.asset_type.lower() == "video":
            download_url = await self._search_video(query)
            if download_url:
                out_path = target_dir / f"{cue.cue_id}.mp4"
                if await self._download_file(download_url, out_path):
                    return out_path

        # 2. Si no hubo video o se solicitó foto, buscar imagen
        download_url = await self._search_image(query)
        if download_url:
            out_path = target_dir / f"{cue.cue_id}.jpg"
            if await self._download_file(download_url, out_path):
                return out_path

        return None

    async def _search_video(self, query: str) -> Optional[str]:
        params = {
            "key": self.api_key,
            "q": query,
            "per_page": 6,
            "video_type": "film"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL_VIDEOS, params=params, timeout=12) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hits = data.get("hits", [])
                        chosen_hit = None
                        for h in hits:
                            h_id = str(h.get("id"))
                            if h_id not in self.used_ids:
                                chosen_hit = h
                                break
                        if not chosen_hit and hits:
                            chosen_hit = hits[0]
                        if chosen_hit:
                            self.used_ids.add(str(chosen_hit.get("id")))
                            videos = chosen_hit.get("videos", {})
                            # Priorizar máxima calidad disponible (large / full HD / medium)
                            chosen = videos.get("large", {}) or videos.get("medium", {}) or videos.get("small", {})
                            return chosen.get("url")
        except Exception as e:
            print(f"[PixabayProvider] Error al buscar video: {e}")
        return None

    async def _search_image(self, query: str) -> Optional[str]:
        params = {
            "key": self.api_key,
            "q": query,
            "per_page": 6,
            "image_type": "photo",
            "orientation": "horizontal"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.BASE_URL_PHOTOS, params=params, timeout=12) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        hits = data.get("hits", [])
                        chosen_hit = None
                        for h in hits:
                            h_id = str(h.get("id"))
                            if h_id not in self.used_ids:
                                chosen_hit = h
                                break
                        if not chosen_hit and hits:
                            chosen_hit = hits[0]
                        if chosen_hit:
                            self.used_ids.add(str(chosen_hit.get("id")))
                            return chosen_hit.get("largeImageURL") or chosen_hit.get("fullHDURL") or chosen_hit.get("webformatURL")
        except Exception as e:
            print(f"[PixabayProvider] Error al buscar imagen: {e}")
        return None

    async def _download_file(self, url: str, destination: Path) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status == 200:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        async with aiofiles.open(destination, mode="wb") as f:
                            async for chunk in resp.content.iter_chunked(256 * 1024):
                                await f.write(chunk)
                        print(f"[PixabayProvider] Guardado exitosamente: {destination.name}")
                        return True
        except Exception as e:
            print(f"[PixabayProvider] Error al descargar {url}: {e}")
        return False


class PexelsAssetProvider(AssetProvider):
    """Proveedor utilizando la API oficial de Pexels (si está disponible con clave activa)."""

    BASE_URL_VIDEOS = "https://api.pexels.com/videos/search"
    BASE_URL_PHOTOS = "https://api.pexels.com/v1/search"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.PEXELS_API_KEY
        self.used_ids = set()

    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        if not self.api_key:
            return None

        query = cue.search_query_en or cue.concept
        headers = {"Authorization": self.api_key}
        print(f"[PexelsProvider] Buscando recurso para '{query}' en Pexels...")

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 1. Intentar video
                if cue.asset_type.lower() == "video":
                    async with session.get(f"{self.BASE_URL_VIDEOS}?query={query}&per_page=6", timeout=12) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            videos = data.get("videos", [])
                            chosen_vid = None
                            for vid in videos:
                                v_id = str(vid.get("id"))
                                if v_id not in self.used_ids and vid.get("video_files"):
                                    chosen_vid = vid
                                    break
                            if not chosen_vid and videos:
                                chosen_vid = videos[0]
                            if chosen_vid:
                                files = chosen_vid.get("video_files", [])
                                if files:
                                    self.used_ids.add(str(chosen_vid.get("id")))
                                    sorted_files = sorted(
                                        files,
                                        key=lambda f: (int(f.get("width") or 0) * int(f.get("height") or 0)),
                                        reverse=True
                                    )
                                    chosen = sorted_files[0]
                                    dl_url = chosen.get("link")
                                    out_path = target_dir / f"{cue.cue_id}.mp4"
                                    if await self._download_direct(session, dl_url, out_path):
                                        return out_path

                # 2. Fallback a foto en máxima resolución original
                async with session.get(f"{self.BASE_URL_PHOTOS}?query={query}&per_page=6", timeout=12) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        photos = data.get("photos", [])
                        chosen_photo = None
                        for ph in photos:
                            ph_id = str(ph.get("id"))
                            if ph_id not in self.used_ids:
                                chosen_photo = ph
                                break
                        if not chosen_photo and photos:
                            chosen_photo = photos[0]
                        if chosen_photo:
                            self.used_ids.add(str(chosen_photo.get("id")))
                            dl_url = (
                                chosen_photo.get("src", {}).get("original")
                                or chosen_photo.get("src", {}).get("large2x")
                                or chosen_photo.get("src", {}).get("large")
                            )
                            out_path = target_dir / f"{cue.cue_id}.jpg"
                            if await self._download_direct(session, dl_url, out_path):
                                return out_path

        except Exception as e:
            print(f"[PexelsProvider] Error en Pexels: {e}")
        return None

    async def _download_direct(self, session: aiohttp.ClientSession, url: str, destination: Path) -> bool:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status == 200:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    async with aiofiles.open(destination, mode="wb") as f:
                        async for chunk in resp.content.iter_chunked(256 * 1024):
                            await f.write(chunk)
                    print(f"[PexelsProvider] Guardado en: {destination.name}")
                    return True
        except Exception as e:
            print(f"[PexelsProvider] Error de descarga: {e}")
        return False


class OpenStockAssetProvider(AssetProvider):
    """
    Proveedor de fotos e ilustraciones enciclopédicas reales verificadas de alta resolución
    mediante Wikimedia Commons y bibliotecas abiertas (100% libre de IA deforme).
    """

    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        from core.web_media import WikiMediaClient
        query = cue.search_query_en or cue.concept
        print(f"[OpenStockProvider] Buscando fotografía real enciclopédica de alta resolución para '{query}'...")
        client = WikiMediaClient()
        res = await client.search(query, langs=["es", "en"])
        if not res or not res.image_url:
            res = await client.search_commons(query)
        if res and res.image_url:
            out_path = target_dir / f"{cue.cue_id}_wiki.jpg"
            if await client.download_image(res.image_url, out_path):
                try:
                    from PIL import Image
                    with Image.open(out_path) as im:
                        # Asegurar resolución nítida mínima (al menos 1280x720 o 1000px ancho)
                        if im.size[0] >= 1000 and im.size[1] >= 600:
                            import json
                            # Guardar registro oficial de procedencia y derechos de uso
                            prov = {
                                "source_url": res.page_url or res.image_url,
                                "source_name": "Wikimedia Commons",
                                "license": getattr(res, "license", "Dominio Público / CC BY-SA"),
                                "artist": getattr(res, "artist", "Archivo Histórico"),
                                "date": getattr(res, "date", ""),
                                "visual_nature": "documental_real",
                                "attribution_badge": f"ARCHIVO HISTÓRICO · {res.date[:4]}" if (getattr(res, "date", "") and any(c.isdigit() for c in res.date)) else "ARCHIVO HISTÓRICO VERIFICADO",
                                "context_note": res.title or query,
                            }
                            prov_path = target_dir / f"{cue.cue_id}_provenance.json"
                            prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
                            print(f"[OpenStockProvider] Foto real verificada obtenida: {out_path.name} ({im.size}) | {prov['attribution_badge']}")
                            return out_path
                except Exception:
                    pass
                out_path.unlink(missing_ok=True)
        return None


class WebPhotoAssetProvider(AssetProvider):
    """Foto REAL desde la búsqueda de imágenes web (DuckDuckGo), filtrando rigurosamente stock comercial y marcas de agua."""

    STOCK_AND_WATERMARK_DOMAINS = (
        "dreamstime", "alamy", "shutterstock", "istockphoto", "istock",
        "gettyimages", "getty", "123rf", "adobestock", "depositphotos", "depositphoto",
        "bigstockphoto", "canstockphoto", "freepik", "vectorstock", "stockphoto",
        "watermark", "pond5", "envato", "storyblocks", "motionelements", "pixtastock",
        "agefotostock", "ftcdn.net", "ftcdn", "stock.adobe", "adobe.com", "canva",
        "eyeem", "shutter", "renderhub", "turbosquid", "cgtrader", "vector", "clipart",
        "shutter stock", "pexels", "pixabay", "unsplash", "rawpixel", "vecteezy", "fotolia"
    )
    WATERMARK_DOMAINS = STOCK_AND_WATERMARK_DOMAINS

    ANIME_AND_WALLPAPER_TERMS = (
        "anime", "manga", "otaku", "waifu", "shonen", "fanart", "moewalls",
        "pixiv", "danbooru", "gelbooru", "konachan", "zerochan", "deviantart",
        "black clover", "naruto", "one piece", "dragon ball", "demon slayer",
        "jujutsu kaisen", "live wallpaper", "wallpaper anime", "wallpaper",
    )

    def __init__(self):
        self.used_urls = set()

    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        import asyncio
        import json
        from PIL import Image
        from core.web_media import WikiMediaClient

        query = cue.search_query_en or cue.concept
        clean_q = " ".join(dict.fromkeys(re.sub(r'[\.\,\;]+$', '', query).replace("4k", "").replace("1080p", "").replace("video", "").split()))

        q_lower = clean_q.lower()
        is_spiritual_biblical = any(has_word(q_lower, w) for w in (
            "dios", "jesus", "cristo", "fe", "oracion", "biblia", "biblico", "cristiano", "perdon",
            "salomon", "milagro", "cruz", "iglesia", "evangelio", "apóstol", "desmond doss", "hacksaw",
            "pasion", "creador", "templo", "orando", "espiritual", "sagrado", "huellas"
        ))
        is_historical_geopolitics = any(has_word(q_lower, w) for w in (
            "historia", "imperio", "guerra", "batalla", "roma", "griego", "filosofia", "siglo",
            "revolucion", "tratado", "antiguo", "monarquia", "emperador", "geopolitica", "alianza"
        ))

        is_spanish = any(has_word(q_lower, w) for w in (
            "presidente", "discurso", "gobierno", "rueda de prensa", "noticia", "declaraciones",
            "manifestacion", "policia", "milei", "petro", "bukele", "sanchez", "sheinbaum", "mexico",
            "argentina", "colombia", "espana", "chile", "peru", "politico", "entrevista", "informe",
            "oficial", "documento", "reforma", "seguridad", "cifra", "alcalde", "ministro", "fiscal"
        ))

        is_tech_benchmark = any(has_word(q_lower, w) for w in (
            "benchmark", "benchmarks", "ia", "ai", "llm", "modelo", "model", "kimi", "deepseek",
            "openai", "chatgpt", "gpt", "claude", "gemini", "anthropic", "meta", "llama", "token",
            "tokens", "contexto", "rendimiento", "evaluacion", "evaluación", "comparativa",
            "versus", "chart", "grafico", "gráfico", "tabla", "mmlu", "gsm8k", "arena", "lmsys",
            "score", "test", "gpu", "nvidia", "hardware", "chip", "chips", "tpu", "procesador", "paper", "arxiv"
        ))

        def search() -> list:
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    res = []
                    if is_spiritual_biblical:
                        # Para Huellas Sagradas: Arte sacro clásico, pinturas al óleo y cinematografía bíblica
                        search_term = f"{clean_q} pintura al oleo clasica arte cinematico obra maestra hd -anime -cartoon -clipart"
                    elif is_historical_geopolitics:
                        # Para PixelGrama / Historia: Fotografía documental y pinturas de época auténticas
                        search_term = f"{clean_q} fotografia documental pintura historica archivo siglo hd -stock -vector -clipart"
                    elif is_tech_benchmark:
                        # Para tecnología e Inteligencia Artificial: Gráficos de benchmark, tablas comparativas y publicaciones reales
                        search_term = f"{clean_q} benchmark comparison chart graph table results -stock -clipart -illustration"
                    elif is_spanish:
                        search_term = f"{clean_q} noticia prensa periodico fotografia real -stock -vector -clipart"
                    else:
                        search_term = f"{clean_q} press news photograph documentary -stock -vector -clipart"

                    # Exclusiones duras: nunca anime/manga/wallpapers/ilustración.
                    search_term = f"{search_term} -anime -manga -illustration -wallpaper -fanart"

                    if is_tech_benchmark:
                        try:
                            res = list(ddgs.images(search_term, size="Large", max_results=16))
                        except Exception:
                            pass
                        if not res:
                            try:
                                res = list(ddgs.images(search_term, size="Medium", max_results=16))
                            except Exception:
                                pass
                        if not res:
                            alt_term = f"{clean_q} benchmark test results leaderboard research -stock"
                            try:
                                res = list(ddgs.images(alt_term, max_results=16))
                            except Exception:
                                pass
                    else:
                        try:
                            res = list(ddgs.images(search_term, size="Wallpaper", max_results=15))
                        except Exception:
                            pass
                        if not res:
                            try:
                                res = list(ddgs.images(search_term, size="Large", max_results=15))
                            except Exception:
                                pass
                        if not res:
                            # Fallback a documentos, informes o publicaciones oficiales
                            alt_term = f"{clean_q} documento publicacion prensa informe -stock" if is_spanish else f"{clean_q} official publication press report document -stock"
                            try:
                                res = list(ddgs.images(alt_term, size="Large", max_results=15))
                            except Exception:
                                pass
                        if not res:
                            res = list(ddgs.images(f"{clean_q} real photograph -stock -vector -clipart", size="Large", max_results=15))
                        if not res:
                            res = list(ddgs.images(f"{clean_q} -stock -vector -clipart", max_results=15))

                clean_items = []
                for r in res:
                    img_url = r.get("image") or ""
                    if not img_url.startswith("http"):
                        continue
                    img_lower = img_url.lower()
                    page_lower = (r.get("url") or "").lower()
                    title_lower = (r.get("title") or "").lower()
                    # Descarte total de dominios de stock comercial
                    if any(bad in img_lower or bad in page_lower or bad in title_lower for bad in self.STOCK_AND_WATERMARK_DOMAINS):
                        continue
                    if any(bad in img_lower or bad in page_lower or bad in title_lower for bad in self.ANIME_AND_WALLPAPER_TERMS):
                        continue
                    w = int(r.get("width") or 0)
                    h = int(r.get("height") or 0)
                    # Exigir alta definición mínima (HD real) y evitar banners deformes
                    if is_tech_benchmark and (w >= 750 and h >= 400 and 0.8 <= (w / max(1, h)) <= 2.6):
                        clean_items.append(r)
                    elif (w >= 1280 and h >= 720) or (w >= 1000 and 1.2 <= (w / max(1, h)) <= 2.2):
                        clean_items.append(r)
                    elif not clean_items and min(w, h) >= 700:
                        clean_items.append(r)
                return clean_items
            except Exception as exc:
                print(f"[WebPhotoProvider] Búsqueda falló: {exc}")
                return []

        client = WikiMediaClient()
        # wait_for: ddgs no tiene timeout propio — un DuckDuckGo colgado
        # (rate-limit/CAPTCHA) congelaba el render de la escena indefinidamente.
        items = await asyncio.wait_for(asyncio.to_thread(search), timeout=12.0)
        # Priorizar elementos no utilizados en escenas previas
        sorted_items = sorted(items[:12], key=lambda x: 1 if (x.get("image") or "") in self.used_urls else 0)
        for i, item in enumerate(sorted_items[:8]):
            url = item.get("image") or ""
            dest = target_dir / f"{cue.cue_id}_web{i}.jpg"
            if not await client.download_image(url, dest):
                continue
            try:
                with Image.open(dest) as im:
                    im.verify()
                with Image.open(dest) as im:
                    aspect = im.size[0] / max(1, im.size[1])
                    if is_tech_benchmark and im.size[0] >= 700 and im.size[1] >= 380 and 0.8 <= aspect <= 2.6:
                        self.used_urls.add(url)
                        prov = {
                            "source_url": item.get("url") or url,
                            "source_name": "Publicación Técnica / Benchmark",
                            "license": "Uso Editorial / Divulgación Técnica",
                            "artist": item.get("source", "Technical Report"),
                            "date": "",
                            "visual_nature": "documental_real",
                            "attribution_badge": "BENCHMARK TÉCNICO",
                            "context_note": item.get("title", query),
                        }
                        prov_path = target_dir / f"{cue.cue_id}_provenance.json"
                        prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
                        print(f"[WebPhotoProvider] Benchmark / Publicación HD descargada: {dest.name} ({im.size})")
                        return dest
                    elif im.size[0] >= 900 and im.size[1] >= 500 and 1.1 <= aspect <= 2.4:
                        self.used_urls.add(url)
                        prov = {
                            "source_url": item.get("url") or url,
                            "source_name": "Archivo Web Editorial",
                            "license": "Uso Editorial / Periodístico",
                            "artist": item.get("source", "Web Press"),
                            "date": "",
                            "visual_nature": "ilustrativo",
                            "attribution_badge": "IMAGEN ILUSTRATIVA",
                            "context_note": item.get("title", query),
                        }
                        prov_path = target_dir / f"{cue.cue_id}_provenance.json"
                        prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
                        print(f"[WebPhotoProvider] Imagen HD real descargada: {dest.name} ({im.size})")
                        return dest
            except Exception:
                pass
            dest.unlink(missing_ok=True)
        return None


class YouTubeReactionAssetProvider(AssetProvider):
    """
    Proveedor autónomo de video-clips reales de YouTube y redes sociales para B-Rolls dinámicos y video-reacciones.
    Utiliza búsqueda integrada de YouTube y yt-dlp con Node.js para descargar un fragmento corto (14s) en HD 720p sin claves de API.
    """

    _global_used_ids = set()

    @classmethod
    def reset_used_assets(cls):
        """Limpia la memoria global de IDs usados para iniciar un proyecto nuevo desde cero."""
        cls._global_used_ids.clear()

    @staticmethod
    def _validate_anime_title(e_title: str, query: str, active_anime: str) -> bool:
        t_low = (e_title or "").lower().strip()
        if not t_low:
            return False
        import unicodedata
        t_norm = "".join(c for c in unicodedata.normalize('NFD', t_low) if unicodedata.category(c) != 'Mn')

        def _has_any(words_tuple):
            return any(w in t_low or w in t_norm for w in words_tuple)

        # 1. Bloqueo TERMINANTE de personas reales, creadores, webcams, reacciones y reviews
        TALKING_HEAD_EXCLUDE = (
            "watch party", "watch along", "watch with me", "watching with me", "watching",
            "reaction", "reacts", "reacting", "react", "reaccion", "reaccionando",
            "review", "resena", "breakdown", "analysis", "analisis",
            "explained", "explanation", "explicacion", "explaining",
            "theory", "theories", "teoria", "podcast", "interview", "entrevista",
            "vlog", "cosplay", "facecam", "webcam", "talking", "commentary", "tier list",
            "ranking", "discussion", "opinion", "critica",
            "funny moments", "first time", "live stream", "livestream", "with cam",
            "with camera", "resumen con camara", "talks about", "in real life",
            "sujeto", "creator", "host", "camara", "youtuber", "streamer", "bedroom",
            "talking head", "unboxing", "vlogger"
        )
        if _has_any(TALKING_HEAD_EXCLUDE):
            return False

        # 2. Bloqueo TERMINANTE de videojuegos, Roblox, simuladores, mods y gameplays
        GAMING_EXCLUDE = (
            "roblox", "grimshot", "simulator", "showcase", "gameplay", "game", "gaming",
            "walkthrough", "playthrough", "mod", "minecraft", "fortnite", "genshin",
            "jump force", "bandai", "bandai namco", "ps4", "ps5", "xbox", "steam", "fighting simulator",
            "glitch", "update", "code", "codes", "mobile game", "mobile", "modded",
            "game trailer", "official game", "rpg", "gacha", "quartet knights", "phantom knights",
            "project clover", "clover retribution", "grimoires era", "clover battlegrounds",
            "black clover m", "rise of the wizard king", "missions", "mission", "panel mission",
            "grand mission", "banner", "summon", "reroll", "tier list", "pvp", "apk", "ios", "android game"
        )
        if _has_any(GAMING_EXCLUDE):
            return False

        # 3. Bloqueo TERMINANTE de parodias, fandubs, abridged, trailers, openings/endings y recopilaciones
        FAN_PARODY_EXCLUDE = (
            "abridged", "parody", "parodia", "fan animation", "fandub", "ytp", "meme",
            "comic dub", "remake", "ai cover", "cover", "karaoke", "trailer", "official trailer",
            "teaser", "preview", "best moments", "moments", "momentos", "compilation", "scene pack",
            "all fights", "all transformations", "evolution", "top 10", "top 5", "sin respiracion",
            "opening", "openings", "ending", "endings", "theme song", "soundtrack", "ost", "full song"
        )
        if _has_any(FAN_PARODY_EXCLUDE):
            return False

        # 4. Bloqueo de canales extranjeros explicativos (Hindi, Malayalam, Tamil, etc.)
        FOREIGN_LANGUAGES = (
            "hindi", "malayalam", "tamil", "telugu", "bengali", "urdu",
            "indonesia", "filipino", "tagalog", "arabic", "vietnam"
        )
        if _has_any(FOREIGN_LANGUAGES):
            return False

        # 5. Bloqueo de spoilers de Manga / After Anime
        MANGA_SPOILERS = (
            "manga", "chapter", "capitulo del manga", "after anime", "spoilers", "spoiler",
            "raw manga", "webtoon", "manhwa"
        )
        if _has_any(MANGA_SPOILERS):
            return False

        # 6. Bloqueo de edits, twixtor, AMVs y contenido vertical recortado
        EDIT_SLOP = (
            "twixtor", "amv", "edit", "shorts", "tiktok", "reels", "status video", "whatsapp status"
        )
        if _has_any(EDIT_SLOP):
            return False

        # 7. Bloqueo de contaminación por personajes de OTROS animes (Deku, Naruto, etc.)
        CROSS_ANIME_MAP = {
            "black clover": ["deku", "bakugo", "all might", "mha", "my hero", "naruto", "sasuke", "boruto", "luffy", "zoro", "one piece", "goku", "vegeta", "dragon ball", "ichigo", "bleach", "tanjiro", "nezuko", "demon slayer", "gojo", "sukuna", "jujutsu", "eren", "levi", "attack on titan", "saitama", "death battle"],
            "naruto": ["deku", "all might", "asta", "yuno", "black clover", "luffy", "zoro", "one piece", "goku", "vegeta", "dragon ball", "ichigo", "bleach", "tanjiro", "gojo", "sukuna", "jujutsu", "eren", "death battle"],
            "one piece": ["deku", "asta", "naruto", "sasuke", "goku", "vegeta", "ichigo", "tanjiro", "gojo", "sukuna", "death battle"],
            "jujutsu kaisen": ["deku", "asta", "naruto", "luffy", "goku", "ichigo", "tanjiro", "death battle"]
        }
        active_key = (active_anime or "black clover").lower().strip()
        banned_cross = CROSS_ANIME_MAP.get(active_key, [])
        for bad_ch in banned_cross:
            if re.search(r'\b' + re.escape(bad_ch) + r'\b', t_low) or re.search(r'\b' + re.escape(bad_ch) + r'\b', t_norm):
                return False

        # 8. Control universal dinámico de episodio, temporada y arco canónico
        range_m = re.search(r'(?:episodios?|episodes?|ep\.?)\s*(\d+)\s*(?:-|a|to)\s*(\d+)', query.lower())
        if range_m:
            min_target_ep = int(range_m.group(1))
            max_target_ep = int(range_m.group(2))
        else:
            single_m = re.search(r'(?:episodios?|episodes?|ep\.?)\s*(\d+)', query.lower())
            if single_m:
                ep_val = int(single_m.group(1))
                min_target_ep = max(1, ep_val - 1)
                max_target_ep = ep_val
            else:
                min_target_ep = 1
                max_target_ep = 9999

        # A) Bloqueo estricto de cualquier episodio futuro que supere el techo del arco actual (+1 de gracia)
        found_eps = [int(n) for n in re.findall(r'(?:ep|episode|episodio)\s*(\d+)', t_low)]
        if found_eps:
            if max_target_ep < 9999 and any(f_ep > (max_target_ep + 1) for f_ep in found_eps):
                return False
            # Si estamos en sagas avanzadas (ej: ep > 12), descartar episodios tempranos desconectados (ej: ep 1 o 2)
            if min_target_ep > 12 and any(f_ep < (min_target_ep - 6) for f_ep in found_eps):
                return False

        # B) Bloqueo de temporadas futuras
        curr_season = 1
        s_m = re.search(r'(?:season|temporada|s)\s*(\d+)', query.lower())
        if s_m:
            curr_season = int(s_m.group(1))
        found_seasons = [int(n) for n in re.findall(r'(?:season|temporada|s)\s*(\d+)', t_low)]
        if found_seasons and any(fs > curr_season for fs in found_seasons):
            return False

        # C) Bloqueo universal de películas, OVAs y saltos temporales futuros no solicitados
        if ("movie" in t_low or "pelicula" in t_low or "film" in t_low) and ("movie" not in query.lower() and "pelicula" not in query.lower()):
            return False
        if "timeskip" in t_low and "timeskip" not in query.lower():
            return False

        # 9. Coincidencia de la franquicia del anime o entidades narrativas de la consulta
        anime_words = [w for w in re.findall(r'[a-zA-Z]+', active_key.lower()) if len(w) >= 3]
        query_kw = [w for w in re.findall(r'[a-zA-Z]+', query.lower()) if len(w) >= 4 and w not in (
            "episode", "episodio", "clip", "scene", "crunchyroll", "action", "moment", "sakuga", "4k", "1080p", "hd"
        )]
        matches_anime = any(w in t_low for w in anime_words)
        matches_query_kw = any(w in t_low for w in query_kw)

        if not matches_anime and not matches_query_kw:
            return False

        return True

    @classmethod
    def _fetch_sakugabooru_sync(cls, series_tag: str, target_path: Path) -> Optional[Path]:
        """Descarga un clip de animación 100% pura y libre de watermarks desde Sakugabooru como fallback."""
        import urllib.request
        import json
        try:
            url = f"https://www.sakugabooru.com/post.json?tags={series_tag}&limit=15"
            req = urllib.request.Request(url, headers={"User-Agent": "AetherCutAI/2.0"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for post in data:
                f_url = post.get("file_url")
                p_id = str(post.get("id"))
                if f_url and f_url.endswith(".mp4") and p_id not in cls._global_used_ids:
                    cls._global_used_ids.add(p_id)
                    dl_req = urllib.request.Request(f_url, headers={"User-Agent": "AetherCutAI/2.0"})
                    with urllib.request.urlopen(dl_req, timeout=15) as dl_resp:
                        target_path.write_bytes(dl_resp.read())
                    if target_path.exists() and target_path.stat().st_size > 50000:
                        return target_path
        except Exception as e:
            print(f"[SakugabooruFallback] {e}", flush=True)
        return None

    def __init__(self):
        self.used_ids = YouTubeReactionAssetProvider._global_used_ids

    async def search_and_download(self, cue: BRollCue, target_dir: Path) -> Optional[Path]:
        import asyncio
        import yt_dlp

        # Solo buscar clip de video si el asset requerido es explícitamente video
        if (cue.asset_type or "").lower() != "video":
            return None

        query = cue.search_query_en or cue.concept
        # YouTube no entiende las exclusiones tipo "-anime"; se quitan para no ensuciar la búsqueda.
        query = re.split(r"\s-(?:anime|manga|illustration|cartoon|wallpaper|fanart|stock|vector|clipart)", query)[0].strip()
        print(f"[YouTubeReactionProvider] Buscando clip de video para '{query}'...", flush=True)

        def _fetch_slice() -> Optional[Path]:
            target_path = target_dir / f"{cue.cue_id}_yt.mp4"
            target_path.unlink(missing_ok=True)

            try:
                # Determinar si la búsqueda es de discurso/persona para descargar una sección sustancial del video
                is_speech_or_person = any(k in query.lower() for k in (
                    "speech", "interview", "press", "declaracion", "discurso", "rueda de prensa",
                    "statement", "conferencia", "debate", "president", "presidente", "ceo", "senador",
                    "ministro", "milei", "trump", "musk", "biden", "petro", "bukele", "sanchez", "altman", "sheinbaum"
                ))

                if is_speech_or_person:
                    start_slice = 20 + ((abs(hash(query)) + len(self.used_ids) * 7) % 25)
                    end_slice = start_slice + 32
                else:
                    start_slice = 10 + ((abs(hash(query)) + len(self.used_ids) * 7) % 20)
                    end_slice = start_slice + 28

                yt_fmt = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best[ext=mp4]/best'

                ydl_opts = {
                    'format': yt_fmt,
                    'outtmpl': str(target_path.with_suffix('')) + '.%(ext)s',
                    'download_ranges': yt_dlp.utils.download_range_func(None, [(start_slice, end_slice)]),
                    'force_keyframes_at_cuts': False,
                    'match_filter': yt_dlp.utils.match_filter_func('!is_live & duration > 8 & duration < 3600'),
                    'quiet': True,
                    'no_warnings': True,
                    'socket_timeout': 18,
                    'extractor_args': {'youtube': {'player_client': ['android', 'ios']}},
                    'postprocessor_args': {'ffmpeg': ['-threads', '2']},
                }
                # Si el usuario colocó un cookies.txt en storage o base, cargarlo automáticamente
                for c_cand in [settings.STORAGE_DIR / "cookies.txt", settings.BASE_DIR / "cookies.txt", settings.BASE_DIR / "assets" / "cookies.txt"]:
                    if c_cand.is_file() and c_cand.stat().st_size > 10:
                        ydl_opts['cookiefile'] = str(c_cand.resolve())
                        print(f"[YouTubeReactionProvider] 🍪 Usando archivo de cookies: {c_cand.name}", flush=True)
                        break

                # Limpiar query y evitar palabras repetidas redundantes
                clean_q = " ".join(dict.fromkeys(query.replace("4k", "").replace("1080p", "").replace("video", "").split()))
                import datetime as _dt
                cur_yr = _dt.date.today().year
                has_year = any(str(y) in query for y in range(1900, 2035))
                is_breaking = any(k in query.lower() for k in ("news", "breaking", "actualidad", "noticia", "report", "urgente"))

                # Detección de anime permanentemente desactivada
                is_anime_query = False
                anime_series = ""
                target_ep = 1
                content_kw = ""
                is_spanish_query = any(w in clean_q.lower() for w in (
                    "presidente", "discurso", "gobierno", "rueda de prensa", "noticia", "declaraciones",
                    "manifestacion", "policia", "milei", "petro", "bukele", "sanchez", "sheinbaum", "mexico",
                    "argentina", "colombia", "espana", "chile", "peru", "politico", "entrevista"
                ))

                if is_speech_or_person:
                    # Anclaje directo a la persona o declaración real en español si aplica
                    if is_spanish_query:
                        search_term = f"{clean_q} discurso rueda de prensa declaraciones" if not any(w in clean_q.lower() for w in ("discurso", "declaraciones", "prensa")) else clean_q
                    else:
                        search_term = f"{clean_q} speech interview press" if not any(w in clean_q.lower() for w in ("speech", "interview", "press", "discurso")) else clean_q
                elif is_breaking:
                    if is_spanish_query:
                        search_term = f"{clean_q} {cur_yr} noticias reportaje en vivo" if not has_year else f"{clean_q} noticias reportaje"
                    else:
                        search_term = f"{clean_q} {cur_yr} news report coverage" if not has_year else f"{clean_q} news report"
                else:
                    if any(w in clean_q.lower() for w in ("documentary", "documental", "footage", "report", "satellite", "aerial", "4k", "news")):
                        search_term = clean_q
                    else:
                        search_term = f"{clean_q} documental reportaje" if is_spanish_query else f"{clean_q} documentary 4k footage"

                # Palabras de descarte para evitar paquetes de stock y b-roll genérico
                GENERIC_STOCK_VIDEO_KEYWORDS = (
                    "stock footage", "royalty free", "copyright free", "no copyright video",
                    "b-roll pack", "free footage", "green screen", "videvo", "storyblocks",
                    "shutterstock", "envato", "pond5", "motion graphics template", "stock video"
                )

                # Evaluar candidatos de YouTube para elegir el de mayor coincidencia real que NUNCA haya sido usado
                best_url = None
                try:
                    search_eval_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': True,
                        'socket_timeout': 10,
                    }
                    with yt_dlp.YoutubeDL(search_eval_opts) as ydl_eval:
                        info = ydl_eval.extract_info(f"ytsearch12:{search_term}", download=False)
                        entries = (info.get("entries") or []) if info else []
                        if entries:
                            q_words = set(re.findall(r"\w{3,}", search_term.lower()))
                            scored_entries = []
                            for ent in entries:
                                e_title = (ent.get("title") or "")
                                e_id = ent.get("id") or ""
                                if not e_id or e_id in self.used_ids:
                                    continue
                                if any(bad in e_title.lower() for bad in GENERIC_STOCK_VIDEO_KEYWORDS):
                                    continue

                                if is_anime_query:
                                    # Validador estricto anti-youtubers, anti-reacciones, anti-idiomas ajenos y anti-otras series
                                    if not self._validate_anime_title(e_title, query, anime_series):
                                        continue
                                    score = sum(3 for w in q_words if w in e_title.lower())
                                    if any(k in e_title.lower() for k in ("clip", "scene", "fight", "combate", "sakuga", "1080p", "hd", "moment", "momentos", "battle", "sub", "dub")):
                                        score += 8
                                    if f"episode {target_ep}" in e_title.lower() or f"ep {target_ep}" in e_title.lower():
                                        score += 15
                                    if "crunchyroll" in e_title.lower() or "official" in e_title.lower():
                                        score += 12
                                else:
                                    score = sum(3 for w in q_words if w in e_title.lower())
                                    if is_speech_or_person and any(k in e_title.lower() for k in ("discurso", "speech", "declaracion", "conferencia", "press", "entrevista", "interview")):
                                        score += 3
                                    if any(k in e_title.lower() for k in ("noticias", "reportaje", "documental", "prensa", "informe", "news", "documentary", "investigation", "coverage")):
                                        score += 2

                                scored_entries.append((score, e_id, e_title))

                            scored_entries.sort(key=lambda x: x[0], reverse=True)
                            chosen_candidate = None
                            for cand_score, cand_id, cand_title in scored_entries:
                                if cand_id and cand_id not in self.used_ids and cand_score > 0:
                                    chosen_candidate = (cand_score, cand_id, cand_title)
                                    break

                            # Si no hay candidatos limpios en la búsqueda principal de anime, recurrir a Crunchyroll oficial
                            if not chosen_candidate:
                                if is_anime_query:
                                    alt_term = f"{anime_series} episode {target_ep} {content_kw} clip".strip()
                                else:
                                    alt_term = f"{search_term} cobertura en vivo archivo"
                                try:
                                    info_alt = ydl_eval.extract_info(f"ytsearch8:{alt_term}", download=False)
                                    for ent in (info_alt.get("entries") or []):
                                        cand_id = ent.get("id") or ""
                                        cand_t = ent.get("title") or ""
                                        if not cand_id or cand_id in self.used_ids:
                                            continue
                                        if is_anime_query:
                                            if not self._validate_anime_title(cand_t, query, anime_series):
                                                continue
                                            chosen_candidate = (10, cand_id, cand_t)
                                            break
                                        else:
                                            chosen_candidate = (1, cand_id, cand_t)
                                            break
                                except Exception:
                                    pass

                            if chosen_candidate and chosen_candidate[1]:
                                best_vid = chosen_candidate[1]
                                self.used_ids.add(best_vid)
                                best_url = f"https://www.youtube.com/watch?v={best_vid}"
                                safe_log(f"[YouTubeReactionProvider] Video más relevante no repetido seleccionado: {chosen_candidate[2]} ({best_vid})")
                except Exception as _e_eval:
                    safe_log(f"[YouTubeReactionProvider] Evaluación de candidatos omitida ({_e_eval}).")

                # Fallback de tercer nivel: si YouTube no tiene ningún clip limpio verificado para este anime, usar Sakugabooru (animación 100% pura)
                if not best_url and is_anime_query:
                    safe_log(f"[YouTubeReactionProvider] 🎬 Sin candidatos limpios en YouTube para '{query}'. Probando Sakugabooru...")
                    tag_map = {
                        "black clover": "black_clover",
                        "naruto": "naruto",
                        "jujutsu kaisen": "jujutsu_kaisen",
                        "one piece": "one_piece",
                        "bleach": "bleach",
                        "demon slayer": "kimetsu_no_yaiba",
                        "dragon ball": "dragon_ball",
                        "attack on titan": "shingeki_no_kyojin"
                    }
                    s_tag = tag_map.get(anime_series.lower(), "black_clover")
                    sakuga_clip = self._fetch_sakugabooru_sync(s_tag, target_path)
                    if sakuga_clip and sakuga_clip.exists():
                        safe_log(f"[YouTubeReactionProvider] ✨ Clip Sakugabooru 100% animación pura obtenido: {sakuga_clip.name}")
                        return sakuga_clip
                    safe_log(f"[YouTubeReactionProvider] ⚠️ Ningún video de YouTube pasó los filtros estrictos de anime para '{query}'. Descartando.")
                    return None

                skip_count = len(self.used_ids) + 1
                download_target = best_url or f"ytsearch{skip_count}:{search_term}"
                if not best_url:
                    ydl_opts['playlist_items'] = str(skip_count)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    try:
                        ydl.download([download_target])
                    except Exception:
                        try:
                            # Fallback 1: búsqueda directa sobre el query limpio con índice no repetido
                            ydl_opts['playlist_items'] = str(skip_count)
                            ydl.download([f"ytsearch{skip_count + 1}:{clean_q} documental reportaje"])
                        except Exception:
                            try:
                                # Fallback 2: descarga desde t=0 si el rango falló
                                ydl_opts['download_ranges'] = yt_dlp.utils.download_range_func(None, [(0, 20)])
                                ydl_opts['playlist_items'] = str(skip_count)
                                ydl.download([f"ytsearch{skip_count + 2}:{clean_q}"])
                            except Exception:
                                pass

                matches = list(target_dir.glob(f"{cue.cue_id}_yt.*"))
                if matches and matches[0].exists() and matches[0].stat().st_size > 50000:
                    chosen = matches[0]
                    if chosen.suffix.lower() != ".mp4":
                        final_mp4 = target_path.with_suffix(".mp4")
                        chosen.replace(final_mp4)
                        chosen = final_mp4

                    # Validar que el video contenga frames decodificables reales
                    try:
                        import subprocess
                        chk = subprocess.run(
                            ["ffmpeg", "-i", str(chosen), "-t", "0.5", "-f", "null", "-"],
                            capture_output=True, text=True, timeout=5
                        )
                        if "Output file is empty" in chk.stderr:
                            print(f"[YouTubeReactionProvider] Clip descargado no contiene frames decodificables, descartando: {chosen.name}", flush=True)
                            chosen.unlink(missing_ok=True)
                            return None
                    except Exception:
                        pass

                    import json
                    prov = {
                        "source_url": f"https://www.youtube.com/results?search_query={clean_q.replace(' ', '+')}",
                        "source_name": "Archivo Audiovisual / YouTube",
                        "license": "Uso Informativo / Editorial",
                        "artist": "Metraje de Archivo",
                        "date": str(cur_yr),
                        "visual_nature": "documental_real",
                        "attribution_badge": "METRAJE DOCUMENTAL",
                        "context_note": clean_q,
                    }
                    prov_path = target_dir / f"{cue.cue_id}_provenance.json"
                    prov_path.write_text(json.dumps(prov, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(f"[YouTubeReactionProvider] Clip H.264 limpio obtenido: {chosen.name} ({chosen.stat().st_size // 1024} KB) | {prov['attribution_badge']}", flush=True)
                    return chosen
            except Exception as e:
                print(f"[YouTubeReactionProvider] Falló descarga de clip para '{query}': {e}", flush=True)
            return None

        return await asyncio.to_thread(_fetch_slice)


class AssetProviderFactory:
    """Fábrica que prioriza fotos reales web de prensa/noticias sin marcas de agua y clips de video reales antes de stock."""

    @staticmethod
    def get_providers(allow_stock: bool = False):
        providers = []
        # 0. Material ORIGINAL del canal (assets/broll): máxima prioridad.
        providers.append(LocalOriginalAssetProvider())
        # 1. Fuentes originales/oficiales (prensa, archivo, gobiernos, empresas).
        providers.append(OriginalSourceAssetProvider())
        # 2. Archivo enciclopédico con licencia/atribución (Wikimedia Commons).
        providers.append(OpenStockAssetProvider())
        # 2. Stock genérico: desactivado por política editorial (cero stock).
        #    Solo se activa si allow_stock=True de forma explícita.
        if allow_stock:
            if settings.PEXELS_API_KEY:
                providers.append(PexelsAssetProvider())
            if settings.PIXABAY_API_KEY:
                providers.append(PixabayAssetProvider())
        # 3. Fotografía editorial/periodística real (requiere revisión de derechos).
        providers.append(WebPhotoAssetProvider())
        # 4. Metraje real de YouTube (último recurso; revisar derechos).
        providers.append(YouTubeReactionAssetProvider())
        return providers

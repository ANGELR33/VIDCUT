import re
import ssl
from pathlib import Path
from typing import Optional, Dict, Any, List

import aiohttp
import aiofiles
import certifi

# Verificación TLS activa, con el paquete de certificados de certifi (el del sistema puede estar desactualizado).
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

def _session(headers: Dict[str, str], total: int) -> aiohttp.ClientSession:
    return aiohttp.ClientSession(
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=total),
        connector=aiohttp.TCPConnector(ssl=_SSL_CTX),
    )

# Wikimedia exige un User-Agent identificable; sin él responde 403.
USER_AGENT = "AetherCutAI/1.0 (video editor; educational use) python-aiohttp"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


class WikiResult:
    """Resultado de una búsqueda enciclopédica real (título, extracto, imagen, URL fuente, licencia y fecha)."""

    def __init__(
        self,
        title: str,
        extract: str,
        image_url: Optional[str],
        page_url: str,
        lang: str,
        license: str = "Dominio Público / CC BY-SA",
        artist: str = "Archivo oficial",
        date: str = "",
        visual_nature: str = "documental_real",
    ):
        self.title = title
        self.extract = extract
        self.image_url = image_url
        self.page_url = page_url
        self.lang = lang
        self.license = license
        self.artist = artist
        self.date = date
        self.visual_nature = visual_nature

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "extract": self.extract,
            "image_url": self.image_url,
            "page_url": self.page_url,
            "lang": self.lang,
            "license": self.license,
            "artist": self.artist,
            "date": self.date,
            "visual_nature": self.visual_nature,
        }


class WikiMediaClient:
    """
    Cliente de Wikipedia/Wikimedia (gratuito, sin API key).

    A diferencia de un generador de imágenes con IA, devuelve FOTOS REALES y texto de una
    enciclopedia con enlace verificable, apto para usar como referencia en pantalla.
    """

    API = "https://{lang}.wikipedia.org/w/api.php"
    COMMONS_API = "https://commons.wikimedia.org/w/api.php"

    async def search(self, query: str, langs: Optional[List[str]] = None) -> Optional[WikiResult]:
        for lang in (langs or ["es", "en"]):
            result = await self._search_one(query, lang)
            if result:
                return result
        # Si no hubo resultado en artículos enciclopédicos, buscar directamente en el archivo multimedia de Commons
        return await self.search_commons(query)

    async def search_commons(self, query: str) -> Optional[WikiResult]:
        """Busca directamente en el archivo fotográfico y documental de Wikimedia Commons."""
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",
            "gsrlimit": 5,
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "iiurlwidth": 1280,
        }
        try:
            async with _session(HEADERS, 12) as session:
                async with session.get(self.COMMONS_API, params=params) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json(content_type=None)
        except Exception as exc:
            print(f"[WikiMedia] Error buscando en Commons '{query}': {exc}")
            return None

        pages = (data.get("query") or {}).get("pages") or {}
        if not pages:
            return None

        for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            imageinfo = (page.get("imageinfo") or [{}])[0]
            thumb_url = imageinfo.get("thumburl") or imageinfo.get("url")
            mime = (imageinfo.get("mime") or "").lower()
            w = int(imageinfo.get("width") or 0)

            if not thumb_url or "audio" in mime or "ogg" in mime or (w > 0 and w < 400):
                continue

            title = page.get("title", "").replace("File:", "").replace(".jpg", "").replace(".png", "")
            extmeta = imageinfo.get("extmetadata") or {}
            clean_license = extmeta.get("LicenseShortName", {}).get("value", "CC BY-SA / Dominio Público")
            clean_artist = extmeta.get("Artist", {}).get("value", "Archivo Histórico / Wikimedia")
            # Limpiar etiquetas HTML que a veces Wikimedia pone en el campo Artist
            clean_artist = re.sub(r"<[^>]+>", "", clean_artist).strip() or "Wikimedia Commons"
            clean_date = extmeta.get("DateTimeOriginal", {}).get("value", extmeta.get("DateTime", {}).get("value", ""))
            clean_desc = extmeta.get("ImageDescription", {}).get("value", "Fotografía documental de archivo de Wikimedia Commons.")
            clean_desc = re.sub(r"<[^>]+>", "", clean_desc).strip()

            return WikiResult(
                title=title or query,
                extract=clean_desc or "Fotografía documental de archivo de Wikimedia Commons.",
                image_url=thumb_url,
                page_url=imageinfo.get("descriptionurl", "https://commons.wikimedia.org"),
                lang="commons",
                license=clean_license,
                artist=clean_artist,
                date=clean_date,
                visual_nature="documental_real",
            )
        return None


    async def _search_one(self, query: str, lang: str) -> Optional[WikiResult]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": 1,
            "prop": "pageimages|extracts|info",
            "piprop": "thumbnail",
            "pithumbsize": 1280,
            "exintro": 1,
            "explaintext": 1,
            "exsentences": 3,
            "inprop": "url",
            "redirects": 1,
        }
        try:
            async with _session(HEADERS, 12) as session:
                async with session.get(self.API.format(lang=lang), params=params) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json(content_type=None)
        except Exception as exc:
            print(f"[WikiMedia] Error buscando '{query}' ({lang}): {exc}")
            return None

        pages = (data.get("query") or {}).get("pages") or {}
        if not pages:
            return None
        page = sorted(pages.values(), key=lambda p: p.get("index", 99))[0]
        page_title = (page.get("title") or "").lower()
        extract = re.sub(r"\s+", " ", (page.get("extract") or "")).strip()
        if not extract:
            return None

        # Descartar artículos de Wikipedia desconectados semánticamente del término buscado
        substantive_tokens = {
            w.lower() for w in re.findall(r"[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]{3,}", query)
            if w.lower() not in {"building", "exterior", "foto", "photo", "image", "real", "4k", "the", "and", "del", "los", "las", "para", "con", "por", "sobre"}
        }
        if substantive_tokens and not any(t in page_title or t in extract.lower() for t in substantive_tokens):
            return None

        return WikiResult(
            title=page.get("title", query),
            extract=extract,
            image_url=(page.get("thumbnail") or {}).get("source"),
            page_url=page.get("fullurl", ""),
            lang=lang,
        )

    async def download_image(self, url: str, destination: Path) -> bool:
        try:
            async with _session({"User-Agent": USER_AGENT}, 12) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return False
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    async with aiofiles.open(destination, "wb") as fh:
                        await fh.write(await resp.read())
            return True
        except Exception as exc:
            print(f"[WikiMedia] Error descargando imagen: {exc}")
            return False

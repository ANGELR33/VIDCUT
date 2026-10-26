"""Descargador e importador asistido para la Biblioteca de Audio de YouTube.

Permite:
1. MODO AUTOMÁTICO: Analiza el tema del video, determina el tono ideal (tensión, cinemático, etc.)
   y descarga automáticamente la mejor pista instrumental libre de derechos de YouTube Audio Library.
2. MODO MANUAL: Descarga cualquier URL específica de YouTube Audio Library o efectos SFX.

Uso:
    # Modo Automático adaptado al tema:
    python scripts/download_youtube_library_samples.py --auto --topic "Cumbre de Presidentes y Rueda de Prensa"
    python scripts/download_youtube_library_samples.py --auto --topic "Avances en Inteligencia Artificial Cuántica"

    # Modo Manual con URL específica:
    python scripts/download_youtube_library_samples.py --url "<YOUTUBE_URL>" --type bgm --category cinematic
"""

import argparse
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.youtube_audio import download_best_audio_for_topic, infer_audio_mood, YOUTUBE_BGM_DIR, LIB_DIR


def download_audio_track(url: str, audio_type: str, category: str, custom_name: str = "") -> bool:
    target_dir = LIB_DIR / audio_type / category
    target_dir.mkdir(parents=True, exist_ok=True)

    out_template = str(target_dir / (f"{custom_name}.%(ext)s" if custom_name else "%(title)s.%(ext)s"))

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "-o", out_template,
        url,
    ]

    print(f"\n[YouTubeAudioLoader] Descargando track a: {target_dir}")
    try:
        res = subprocess.run(cmd, check=True, text=True, capture_output=True)
        print(f"[YouTubeAudioLoader] ¡Descarga exitosa en {target_dir}!")
        return True
    except subprocess.CalledProcessError as exc:
        print(f"[YouTubeAudioLoader] Error descargando audio:\n{exc.stderr}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Descargar audio adaptativo libre de derechos para KAI Streamer")
    parser.add_argument("--auto", action="store_true", help="Descargar automáticamente la música que mejor se adapte al video")
    parser.add_argument("--topic", type=str, default="", help="Tema del video para inferir el mood y descargar automáticamente")
    parser.add_argument("--style", type=str, default="divulgacion", help="Estilo editorial del video")
    parser.add_argument("--force", action="store_true", help="Forzar nueva descarga incluso si ya existe una pista en esa categoría")
    parser.add_argument("--url", type=str, default="", help="URL del video/audio en YouTube (Audio Library) para descarga manual")
    parser.add_argument("--type", choices=["bgm", "sfx"], default="bgm", help="Tipo: bgm (música) o sfx (efecto)")
    parser.add_argument("--category", type=str, default="", help="Categoría/Mood forzado (cinematic, tension, upbeat, ambient, lofi, etc.)")
    parser.add_argument("--name", type=str, default="", help="Nombre personalizado para el archivo guardado (sin extensión)")

    args = parser.parse_args()

    if args.auto or (args.topic and not args.url):
        topic = args.topic.strip() or "Actualidad y Noticias"
        mood = args.category.strip() or infer_audio_mood(topic, args.style)
        print("=================================================================")
        print("    DESCARGA AUTOMÁTICA ADAPTATIVA - YOUTUBE AUDIO LIBRARY       ")
        print("=================================================================")
        print(f"Tema analizado: «{topic}»")
        print(f"Mood detectado: {mood.upper()}")
        print(f"Buscando en YouTube Audio Library y descargando pista adaptada...")

        result_path = download_best_audio_for_topic(
            topic=topic,
            style=args.style,
            preferred_mood=mood,
            force_download=args.force
        )

        if result_path and result_path.exists():
            print(f"\n[ÉXITO] Pista adaptada lista para el video:")
            print(f"-> Archivo: {result_path}")
            print(f"-> Tamaño: {result_path.stat().st_size / (1024*1024):.2f} MB")
            sys.exit(0)
        else:
            print(f"\n[AVISO] No se pudo descargar la pista automática. Se usará el audio de respaldo local.")
            sys.exit(1)

    if not args.url:
        parser.error("Debes indicar --auto con un --topic, o proporcionar una --url para descarga manual.")

    category = args.category or ("tension" if args.type == "bgm" else "transitions")
    success = download_audio_track(args.url, args.type, category, args.name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

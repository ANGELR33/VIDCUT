"""Audita y gestiona los videos de la cola del autopilot en YouTube.

Requiere un token OAuth con el scope https://www.googleapis.com/auth/youtube
(el flujo de autorización ya lo solicita). Sin ese scope, YouTube responde 403.

Uso:
  python scripts/audit_youtube_queue.py --list
  python scripts/audit_youtube_queue.py --private
  python scripts/audit_youtube_queue.py --delete

No imprime tokens.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests

from config.settings import settings
import core.youtube_oauth as yt

QUEUE_FILE = settings.STORAGE_DIR / "autopilot_queue.json"
API = "https://www.googleapis.com/youtube/v3/videos"


def load_jobs():
    if not QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def status_for(video_id: str, channel_id: str):
    token = yt._valid_access_token(channel_id)
    response = requests.get(
        API,
        params={"part": "status,snippet", "id": video_id, "access_token": token},
        timeout=(5, 20),
    )
    if response.status_code == 403:
        return {"error": "403 insufficient scopes: reconecta YouTube con el scope youtube"}
    if response.status_code >= 400:
        return {"error": f"HTTP {response.status_code}: {response.text[:160]}"}
    items = (response.json() or {}).get("items") or []
    if not items:
        return {"error": "video no encontrado"}
    item = items[0]
    return {
        "title": (item.get("snippet") or {}).get("title", ""),
        "privacy": (item.get("status") or {}).get("privacyStatus", ""),
        "publish_at": (item.get("status") or {}).get("publishAt", ""),
        "upload_status": (item.get("status") or {}).get("uploadStatus", ""),
    }


def update_privacy(video_id: str, channel_id: str, privacy: str):
    token = yt._valid_access_token(channel_id)
    response = requests.put(
        API,
        params={"part": "status", "access_token": token},
        json={"id": video_id, "status": {"privacyStatus": privacy}},
        timeout=(5, 20),
    )
    return response.status_code, response.text[:200]


def delete_video(video_id: str, channel_id: str):
    token = yt._valid_access_token(channel_id)
    response = requests.delete(
        API,
        params={"id": video_id, "access_token": token},
        timeout=(5, 20),
    )
    return response.status_code, response.text[:200]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--delete", action="store_true")
    args = parser.parse_args()

    jobs = [j for j in load_jobs() if j.get("video_id") and j.get("channel_id")]
    if not jobs:
        print("No hay videos con video_id en la cola.")
        return

    for job in jobs:
        video_id = job["video_id"]
        channel_id = job["channel_id"]
        info = status_for(video_id, channel_id)
        print(f"{video_id} | {job.get('channel_title')} | {job.get('status')} | {info}")
        if info.get("error"):
            continue
        if args.private and info.get("privacy") != "private":
            code, body = update_privacy(video_id, channel_id, "private")
            print(f"  -> private: {code} {body}")
        if args.delete:
            code, body = delete_video(video_id, channel_id)
            print(f"  -> delete: {code} {body}")


if __name__ == "__main__":
    main()

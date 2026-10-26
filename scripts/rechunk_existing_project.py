import json
import re
from pathlib import Path

def parse_srt_time(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(parts[0])

def fmt_srt(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def chunk_words(text_str: str):
    raw_w = text_str.split()
    if not raw_w:
        return []
    chunks = []
    cur = []
    for i, w in enumerate(raw_w):
        cur.append(w)
        remaining = len(raw_w) - (i + 1)
        has_punct = bool(re.search(r"[.,!?;:]", w))
        if len(cur) >= 4 or (len(cur) >= 3 and remaining != 1) or (has_punct and len(cur) >= 2 and remaining >= 2):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        if len(cur) <= 2 and chunks:
            prev_words = chunks[-1].split()
            if len(prev_words) <= 3:
                chunks[-1] = chunks[-1] + " " + " ".join(cur)
            else:
                chunks.append(" ".join(cur))
        else:
            chunks.append(" ".join(cur))
    return chunks

def rechunk_project(pid: str):
    proj_dir = Path("storage/projects") / pid
    if not proj_dir.exists():
        print(f"Project {pid} not found")
        return

    work_dir = proj_dir / "work"
    scene_dirs = sorted(
        work_dir.glob("scene_*"),
        key=lambda p: int(p.name.replace("scene_", "")) if p.name.replace("scene_", "").isdigit() else 999
    )

    all_master_blocks = []
    master_idx = 1
    cum_offset = 0.0

    for sc_dir in scene_dirs:
        srt_file = sc_dir / "scene_subtitles.srt"
        scene_mp4 = sc_dir / f"{sc_dir.name}.mp4"
        sc_dur = 0.0
        if scene_mp4.exists():
            try:
                from utils.file_manager import FileManager
                sc_dur = FileManager.get_media_metadata(scene_mp4).get("duration", 0.0)
            except Exception:
                pass

        if srt_file.exists():
            content = srt_file.read_text(encoding="utf-8").strip()
            if content:
                blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
                rechunked_scene_blocks = []
                sc_idx = 1
                for b in blocks:
                    lines = [l.strip() for l in b.splitlines() if l.strip()]
                    if len(lines) >= 3 and "-->" in lines[1]:
                        tp = lines[1].split("-->")
                        st = parse_srt_time(tp[0])
                        en = parse_srt_time(tp[1])
                        txt = " ".join(lines[2:])
                        sub_chunks = chunk_words(txt)
                        total_chars = sum(len(c) for c in sub_chunks) or 1
                        span = max(0.3, en - st)
                        c_start = st
                        for ch_i, ch in enumerate(sub_chunks):
                            wt = len(ch) / total_chars
                            dur = span * wt
                            c_end = en if ch_i == len(sub_chunks) - 1 else round(c_start + dur, 3)
                            
                            clean_c = ch.strip().replace(":", "")
                            rechunked_scene_blocks.append(f"{sc_idx}\n{fmt_srt(c_start)} --> {fmt_srt(c_end)}\n{clean_c}\n")
                            sc_idx += 1

                            all_master_blocks.append(
                                f"{master_idx}\n{fmt_srt(c_start + cum_offset)} --> {fmt_srt(c_end + cum_offset)}\n{clean_c}"
                            )
                            master_idx += 1
                            c_start = c_end

                if rechunked_scene_blocks:
                    srt_file.write_text("\n".join(rechunked_scene_blocks), encoding="utf-8")

        cum_offset += sc_dur

    if all_master_blocks:
        full_srt = work_dir / "full_subtitles.srt"
        full_srt.write_text("\n\n".join(all_master_blocks), encoding="utf-8")
        print(f"[OK] Rechunked {len(all_master_blocks)} subtitle blocks across {len(scene_dirs)} scenes for project {pid}")

if __name__ == "__main__":
    import sys
    pid = sys.argv[1] if len(sys.argv) > 1 else "1b204942"
    rechunk_project(pid)

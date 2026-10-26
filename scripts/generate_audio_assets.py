"""Genera los assets de audio del KAI Streamer (BGM y SFX) con FFmpeg puro.

Son sintetizados (capas de senos con tremolo/lowpass y ruido filtrado):
BGM suena a volumen 0.06 bajo la voz, así que un pad ambiental limpio basta.
Ejecutar una sola vez: python scripts/generate_audio_assets.py
"""
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "assets" / "audio"


def run(args):
    cmd = ["ffmpeg", "-y", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(f"ERROR: {' '.join(cmd[:6])}...\n{r.stderr[-500:]}")
        sys.exit(1)


def mix_sines(freqs_vols, dur, out, tremolo_f, tremolo_d, lowpass, final_vol, extra_filter=""):
    """Pad ambiental: capas de senos + tremolo lento + lowpass."""
    inputs = []
    for i, (f, v) in enumerate(freqs_vols):
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={dur}"]
    fc_parts = ";".join(f"[{i}]volume={v}[s{i}]" for i, (f, v) in enumerate(freqs_vols))
    labels = "".join(f"[s{i}]" for i in range(len(freqs_vols)))
    n = len(freqs_vols)
    graph = (
        f"{fc_parts};{labels}amix=inputs={n}:normalize=0,"
        f"tremolo=f={tremolo_f}:d={tremolo_d},lowpass=f={lowpass}"
        + (f",{extra_filter}" if extra_filter else "")
        + f",volume={final_vol}[out]"
    )
    run([*inputs, "-filter_complex", graph, "-map", "[out]", "-ar", "48000", "-ac", "2", str(out)])
    print(f"OK {out.name}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # ── BGM (loops de 32 s, sin fades para que la costura del loop sea limpia) ──
    mix_sines([(110.0, 0.5), (164.81, 0.34), (220.0, 0.2), (261.63, 0.11)], 32, OUT / "bgm_streamer.wav",
              tremolo_f=0.15, tremolo_d=0.35, lowpass=700, final_vol=0.8)
    mix_sines([(82.41, 0.5), (98.0, 0.36), (123.47, 0.22), (164.81, 0.12)], 32, OUT / "bgm_tension.wav",
              tremolo_f=0.1, tremolo_d=0.4, lowpass=500, final_vol=0.8)
    mix_sines([(220.0, 0.4), (277.18, 0.3), (329.63, 0.22), (440.0, 0.12)], 32, OUT / "bgm_upbeat.wav",
              tremolo_f=2.0, tremolo_d=0.55, lowpass=1300, final_vol=0.75)
    mix_sines([(110.0, 0.55), (164.81, 0.3)], 32, OUT / "bgm_ambient.wav",
              tremolo_f=0.1, tremolo_d=0.45, lowpass=400, final_vol=0.7)

    # ── SFX ──
    # Whoosh: ruido rosa con barrido de paso-bajo y fades suaves (1.2 s)
    run(["-f", "lavfi", "-i", "anoisesrc=colour=pink:duration=1.2:amplitude=0.9",
         "-af", "highpass=f=110,lowpass=f=900,afade=t=in:d=0.45,afade=t=out:st=0.7:d=0.5,volume=1.1",
         "-ar", "48000", "-ac", "2", str(OUT / "whoosh.wav")])
    print("OK whoosh.wav")

    # Chime: ding de dos tonos (880 + 1318 Hz) con caída larga (1.6 s)
    run(["-f", "lavfi", "-i", "sine=frequency=880:duration=1.6",
         "-f", "lavfi", "-i", "sine=frequency=1318.5:duration=1.2",
         "-filter_complex", "[0]volume=0.55[a];[1]volume=0.4,afade=t=out:st=0.1:d=1.1[b];[a][b]amix=inputs=2:normalize=0,afade=t=out:st=0.15:d=1.45,volume=1.2[out]",
         "-map", "[out]", "-ar", "48000", "-ac", "2", str(OUT / "chime.wav")])
    print("OK chime.wav")

    # Impact: golpe grave (55 Hz) con estallido corto de ruido (0.9 s)
    run(["-f", "lavfi", "-i", "sine=frequency=55:duration=0.9",
         "-f", "lavfi", "-i", "anoisesrc=colour=white:duration=0.12:amplitude=0.5",
         "-filter_complex", "[0]afade=t=out:st=0.03:d=0.85,volume=1.2[a];[1]lowpass=f=2500,afade=t=out:st=0.02:d=0.1,volume=0.5[b];[a][b]amix=inputs=2:normalize=0[out]",
         "-map", "[out]", "-ar", "48000", "-ac", "2", str(OUT / "impact.wav")])
    print("OK impact.wav")

    # Alert: tono moderno y elegante de alerta / advertencia (tríada armónica cálida A4-C#5-E5 + sub-bass suave)
    run([
        "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5",
        "-f", "lavfi", "-i", "sine=frequency=554.37:duration=0.45",
        "-f", "lavfi", "-i", "sine=frequency=659.25:duration=0.4",
        "-f", "lavfi", "-i", "sine=frequency=110:duration=0.25",
        "-filter_complex",
        "[0]afade=t=in:d=0.015,afade=t=out:st=0.08:d=0.4,volume=0.5[t1];"
        "[1]adelay=delays=90:all=1,afade=t=in:d=0.015,afade=t=out:st=0.15:d=0.35,volume=0.4[t2];"
        "[2]adelay=delays=180:all=1,afade=t=in:d=0.015,afade=t=out:st=0.22:d=0.3,volume=0.35[t3];"
        "[3]afade=t=out:st=0.02:d=0.2,volume=0.4[sub];"
        "[t1][t2][t3][sub]amix=inputs=4:normalize=0,lowpass=f=2400,volume=0.9[out]",
        "-map", "[out]", "-ar", "48000", "-ac", "2", str(OUT / "alert.wav")
    ])
    print("OK alert.wav (modern harmonic chime)")

    # Pop: clic elástico y satisfactorio para stickers y badges virales (0.18 s)
    run(["-f", "lavfi", "-i", "sine=frequency=620:duration=0.18",
         "-af", "afade=t=out:st=0.03:d=0.15,volume=1.35",
         "-ar", "48000", "-ac", "2", str(OUT / "pop.wav")])
    print("OK pop.wav")

    print("\nAssets generados en", OUT)


if __name__ == "__main__":
    main()

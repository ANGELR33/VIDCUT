import json
import time
import urllib.request
import urllib.error
import sys

BASE_URL = "http://127.0.0.1:8000"

payload = {
    "topic": "El fin de la hegemonia AI: Por que Kimi K3.1 Pro ha cambiado las reglas",
    "style": "divulgacion",
    "duration_sec": 480,
    "aspect_ratio": "16:9",
    "card_theme": "dark",
    "voice": "es-MX-JorgeNeural",
    "extra_notes": "Analisis tecnico del modelo Kimi K3.1 Pro, arquitectura MoE de 2.8 billones de parametros, costo por millon de tokens y comparativas de rendimiento en benchmarks reales."
}

req_data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    f"{BASE_URL}/api/streamer/create",
    data=req_data,
    headers={"Content-Type": "application/json"}
)

print("[Kimi Test] Iniciando generacion de transmision Kimi K3.1 Pro...")
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        res_json = json.loads(resp.read().decode("utf-8"))
        task_id = res_json.get("task_id")
        print(f"[Kimi Test] Tarea creada exitosamente. Task ID: {task_id}")
except Exception as e:
    print(f"[Kimi Test] Error al crear tarea: {e}")
    sys.exit(1)

last_step = ""
last_msg = ""
last_pct = -1

while True:
    try:
        prog_req = urllib.request.Request(f"{BASE_URL}/api/progress/{task_id}")
        with urllib.request.urlopen(prog_req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            step = data.get("step", "")
            pct = data.get("progress", 0.0)
            msg = data.get("message", "")
            completed = data.get("completed", False)
            error = data.get("error")

            if step != last_step or abs(pct - last_pct) >= 1.0 or msg != last_msg:
                print(f"[{time.strftime('%H:%M:%S')}] [{step.upper()}] {pct:.1f}% -> {msg}", flush=True)
                last_step = step
                last_pct = pct
                last_msg = msg

            if completed:
                if error:
                    print(f"\n[Kimi Test] Tarea finalizada con ERROR: {error}", flush=True)
                else:
                    print(f"\n[Kimi Test] Transmision COMPLETADA CON EXITO!", flush=True)
                    print(f"Resultado: {json.dumps(data.get('result', {}), indent=2)}", flush=True)
                break

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] Polling warning: {e}", flush=True)

    time.sleep(3)

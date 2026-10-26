"""Pruebas del registro estructurado de ejecuciones. No usan red ni modelos reales."""

import asyncio
import contextvars
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core import run_log
from core.run_log import RunLog, estimate_llm_cost, log_count, log_llm, logged_run, redact

PRICING = {
    "llm_per_million_tokens": {
        "gemini-flash": {"input": 0.10, "output": 0.40},
        "gemini-flash-lite": {"input": 0.05, "output": 0.20},
        "nvidia/free": {"input": 0, "output": 0},
        "sin-tarifa": {"input": None, "output": None},
    },
    "services_per_unit": {"speechify": 0.015},
}


class RedactTest(unittest.TestCase):
    def test_hides_known_key_formats(self):
        samples = [
            "clave nvapi-FAKE0123456789abcdefghijklmnopqrst fin",
            "sk-FAKE0123456789abcdefghijklmnop",
            "AIzaFAKE0123456789abcdefghijklmnopqrs",
            "GOCSPX-FAKE0123456789ab",
            "Authorization: Bearer abcdefghijklmnop1234",
            "api_key=supersecreto123",
        ]
        for text in samples:
            cleaned = redact(text)
            self.assertIn("***", cleaned, text)
            for fragment in ("FAKE0123456789", "supersecreto", "abcdefghijklmnop1234"):
                self.assertNotIn(fragment, cleaned)

    def test_recurses_into_structures(self):
        out = redact({"a": ["nvapi-abcdefghijkl"], "b": {"c": "ok"}})
        self.assertEqual(out["b"]["c"], "ok")
        self.assertNotIn("abcdefghijkl", json.dumps(out))


class CostTest(unittest.TestCase):
    def test_longest_prefix_wins_and_math(self):
        flash_lite = estimate_llm_cost(PRICING, "gemini-flash-lite-latest", 1_000_000, 500_000)
        self.assertAlmostEqual(flash_lite, 0.05 + 0.10)
        flash = estimate_llm_cost(PRICING, "gemini-flash-latest", 1_000_000, 0)
        self.assertAlmostEqual(flash, 0.10)

    def test_unknown_or_null_rate_is_none(self):
        self.assertIsNone(estimate_llm_cost(PRICING, "otro-modelo", 10, 10))
        self.assertIsNone(estimate_llm_cost(PRICING, "sin-tarifa", 10, 10))

    def test_free_model_costs_zero(self):
        self.assertEqual(estimate_llm_cost(PRICING, "nvidia/free-model", 5000, 5000), 0.0)


class RunLogTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="runlog-test-"))

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_report_files_stages_and_costs(self):
        run = RunLog.start(self.temp, "video_editado", "VideoPipeline", run_id="abc", pricing=PRICING)
        run.on_state("gemini", "Analizando")
        run.on_state("gemini", "Esperando")
        run.on_state("render", "Renderizando")
        log_llm("gemini", "gemini-flash-lite-latest", "plan_edicion", 1_000_000, 500_000, 2.0)
        log_llm("gemini", "gemini-flash-lite-latest", "plan_edicion", ok=False, error="HTTP 503", latency_sec=1.0)
        log_llm("nvidia", "modelo-desconocido", "respaldo", 100, 50, 0.5, fallback=True)
        run.record_service("speechify", units=2000, unit_name="caracteres")
        log_count("broll_accepted", 3)
        run.warn("broll", "Candidato descartado")
        report = run.finalize("completed", outputs={"master": "x.mp4"})

        self.assertEqual([s["name"] for s in report["stages"]], ["gemini", "render"])
        gem = next(r for r in report["llm"] if r["provider"] == "gemini")
        self.assertEqual((gem["calls"], gem["failures"]), (2, 1))
        self.assertAlmostEqual(report["cost"]["estimated_total"], 0.15 + 30.0)
        self.assertTrue(report["cost"]["partial"])
        self.assertIn("nvidia:modelo-desconocido", report["cost"]["without_rate"])
        self.assertEqual(report["counters"]["broll_accepted"], 3)
        self.assertEqual(report["issue_counts"], {"warnings": 2, "errors": 0})

        self.assertTrue((self.temp / "run_report.json").exists())
        md = (self.temp / "run_report.md").read_text(encoding="utf-8")
        self.assertIn("Reporte de ejecución `abc`", md)
        self.assertIn("sin tarifa", md)
        lines = (self.temp / "run_events.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(lines), 6)
        for line in lines:
            json.loads(line)

    def test_events_never_contain_secrets(self):
        run = RunLog.start(self.temp, "x", "y", pricing=PRICING)
        run.event("t", "fallo con nvapi-FAKE0123456789abcdef en la llamada", key="sk-FAKE0123456789abcdefghijklmnop")
        run.finalize()
        raw = (self.temp / "run_events.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("FAKE0123456789", raw)
        self.assertNotIn("FAKE0123456789abcdefghijklmnop", raw)

    def test_helpers_are_noops_without_active_run(self):
        self.assertIsNone(run_log.current())
        log_llm("gemini", "m")  # no debe lanzar
        log_count("x")

    def test_context_reaches_executor_threads_with_copy_context(self):
        run = RunLog.start(self.temp, "x", "y", pricing=PRICING)

        async def main():
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, contextvars.copy_context().run,
                                       lambda: log_llm("gemini", "gemini-flash", "hilo", 10, 10, 0.1))
        asyncio.run(main())
        report = run.finalize()
        self.assertEqual(report["llm"][0]["calls"], 1)

    def test_decorator_sync_and_failure(self):
        @logged_run("podcast", "SpanishPodcastClipper")
        def ok(workdir):
            log_count("clips", 2)
            return "listo"

        self.assertEqual(ok(workdir=self.temp / "ok"), "listo")
        data = json.loads((self.temp / "ok" / "run_report.json").read_text(encoding="utf-8"))
        self.assertEqual((data["status"], data["content_type"], data["counters"]["clips"]), ("completed", "podcast", 2))

        @logged_run("anime", "AnimeAutopilot")
        async def boom(workdir):
            raise RuntimeError("nvapi-abcdefghijklmnop falló")

        with self.assertRaises(RuntimeError):
            asyncio.run(boom(workdir=self.temp / "bad"))
        bad = json.loads((self.temp / "bad" / "run_report.json").read_text(encoding="utf-8"))
        self.assertEqual(bad["status"], "failed")
        self.assertEqual(bad["issue_counts"]["errors"], 1)
        self.assertNotIn("abcdefghijklmnop", json.dumps(bad))
        self.assertIsNone(run_log.current())


if __name__ == "__main__":
    unittest.main()

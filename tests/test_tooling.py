"""Pruebas de las herramientas operativas: escáner de secretos y diagnóstico previo."""

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # los dataclass buscan su módulo en sys.modules
    spec.loader.exec_module(module)
    return module


class SecretScannerTest(unittest.TestCase):
    def setUp(self):
        self.scanner = load_script("check_secrets")
        self.temp = Path(tempfile.mkdtemp(prefix="secrets-test-"))

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_detects_real_looking_keys_and_masks_them(self):
        key = "nvapi-" + "A1b2C3d4E5f6G7h8I9j0K1l2"  # concatenado para no autodetectarse
        (self.temp / "a.py").write_text(f'KEY = "{key}"\n', encoding="utf-8")
        findings = self.scanner.scan(self.temp)
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0].path, findings[0].line), ("a.py", 1))
        self.assertNotIn("A1b2C3d4", findings[0].preview)

    def test_ignores_placeholders_and_empty_examples(self):
        (self.temp / ".env.example").write_text("NVIDIA_API_KEY=\nGEMINI_API_KEY=\n", encoding="utf-8")
        (self.temp / "t.py").write_text('x = "nvapi-FAKE0123456789abcdefghijklmnop"\n', encoding="utf-8")
        self.assertEqual(self.scanner.scan(self.temp), [])

    def test_detects_hardcoded_default_in_getattr_fallback(self):
        key = "sk-" + "a1b2c3d4e5f6a7b8c9d0e1f2a3b4"
        (self.temp / "d.py").write_text(f'k = getattr(s, "K", "") or "{key}"\n', encoding="utf-8")
        self.assertEqual(len(self.scanner.scan(self.temp)), 1)

    def test_current_repository_is_clean(self):
        self.assertEqual(self.scanner.scan(ROOT), [])

    def test_scanner_patterns_are_also_redacted_by_run_log(self):
        from core.run_log import redact
        samples = ["nvapi-" + "A1b2C3d4E5f6G7h8I9j0K1l2", "sk-" + "a1b2c3d4e5f6a7b8c9d0e1f2a3b4",
                   "AIza" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6", "GOCSPX-" + "a1B2c3D4e5F6"]
        for sample in samples:
            self.assertEqual(redact(sample), "***", sample[:8])


class DoctorTest(unittest.TestCase):
    def test_reports_expected_checks_without_leaking_keys(self):
        import os
        doctor = load_script("doctor")
        os.environ["NVIDIA_API_KEY"] = "nvapi-" + "FAKE0123456789abcdefghijkl"
        try:
            checks = doctor.run_checks()
        finally:
            os.environ.pop("NVIDIA_API_KEY", None)
        names = {name for name, _, _ in checks}
        for expected in ("Python >= 3.10", "ffmpeg", "ffprobe", "GEMINI_API_KEY", "almacenamiento escribible", "tarifas de costos"):
            self.assertIn(expected, names)
        self.assertTrue(all(status in ("ok", "warn", "fail") for _, status, _ in checks))
        self.assertNotIn("FAKE0123456789", " ".join(detail for _, _, detail in checks))


if __name__ == "__main__":
    unittest.main()

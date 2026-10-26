import asyncio
import unittest
from pathlib import Path

from core.avatar_narrator import AvatarNarrator
from core.avatar_renderer import AvatarRenderer
from core.models import InfoCard


class TestAvatarCopilot(unittest.TestCase):
    def test_avatar_dialogue_crafting(self):
        narrator = AvatarNarrator()
        
        # 1. Contradicción
        card_contra = InfoCard(
            card_id="c1", start_sec=2.0, end_sec=6.0,
            headline="Dato erróneo", claim="El Sol gira alrededor de la Tierra",
            search_query="orbita heliocentrica", verdict="contradicted",
            correction="La Tierra y los planetas orbitan alrededor del Sol."
        )
        text_contra = narrator.craft_dialogue(card_contra)
        self.assertTrue(
            any(marker in text_contra for marker in ("Un momento", "Atención", "Miren", "Ojo", "Bueno"))
        )
        self.assertIn("Sol", text_contra)

        # 2. Cifra confirmada
        card_stat = InfoCard(
            card_id="c2", start_sec=10.0, end_sec=15.0,
            headline="Ventas récord", claim="Se vendieron 5 millones de unidades",
            search_query="ventas unidades", verdict="supported",
            stat_value="5.2 millones"
        )
        text_stat = narrator.craft_dialogue(card_stat)
        self.assertIn("5.2 millones", text_stat)

    def test_voice_synthesis_and_clip_render(self):
        narrator = AvatarNarrator()
        workdir = Path("storage/test_avatar_unit")
        workdir.mkdir(parents=True, exist_ok=True)
        
        audio_file = workdir / "test_voice.mp3"
        video_file = workdir / "test_avatar.webm"
        
        try:
            # Síntesis con Microsoft Edge-TTS
            async def run_synth():
                return await narrator.synthesize("Dato clave verificado con éxito.", audio_file)
            
            p, dur = asyncio.run(run_synth())
            self.assertTrue(audio_file.exists())
            self.assertGreater(dur, 0.5)

            # Render de video transparente WebM
            renderer = AvatarRenderer(badge_size=200)
            rendered = renderer.render_reaction_clip(dur, video_file, fps=15)
            self.assertIsNotNone(rendered)
            self.assertTrue(video_file.exists())
            self.assertGreater(video_file.stat().st_size, 1000)
        finally:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

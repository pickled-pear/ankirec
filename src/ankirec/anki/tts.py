import random
import subprocess
from pathlib import Path
import aiohttp
import asyncio
import time
from rich import print

from click import get_app_dir

from ..base.constants import APP_NAME


class TtsController:
    def __init__(self, voices: list[str]):
        if not voices:
            raise ValueError("At least one voice is required")
        self.voices = voices
        


    def create_tts(self, text: str, filename: str) -> Path:
        import edge_tts
        """Creates TTS for the text using a random voice and returns the opus path."""
        # print(edge_tts.__version__)
        out_dir = Path(get_app_dir(APP_NAME)) / "temp_storage"
        out_dir.mkdir(parents=True, exist_ok=True)
        mp3_path = out_dir / f"{filename}.mp3"

        attempts = 4
        for attempt in range(1, attempts + 1):
            voice = random.choice(self.voices)
            try:
                asyncio.run(edge_tts.Communicate(text, voice).save(str(mp3_path)))
                break
            except aiohttp.WSServerHandshakeError as e:
                if e.status != 403 or attempt == attempts:
                    if e.status == 403:
                        print("[red]Edge TTS kept rejecting the request (403). "
                            "Try upgrading edge-tts or checking the system clock.")
                    raise
                wait = 2 ** attempt + random.uniform(0, 1)  # ~2 s, 4 s, 8 s
                print(f"[yellow]Edge TTS returned 403, retrying in {wait:.1f} s "
                    f"(attempt {attempt}/{attempts})")
                time.sleep(wait)

        opus_path = self._convert_to_opus(mp3_path)
        mp3_path.unlink(missing_ok=True)
        return opus_path

    @staticmethod
    def _convert_to_opus(filepath: Path) -> Path:
        """Uses ffmpeg to convert the file to an opus"""
        opus_path = filepath.with_suffix(".opus")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(filepath),
                "-c:a", "libopus", "-b:a", "24k", "-application", "voip",
                str(opus_path),
            ],
            check=True,
        )
        return opus_path



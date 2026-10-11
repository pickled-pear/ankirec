import random
import subprocess
from pathlib import Path

from click import get_app_dir

from ..base.constants import APP_NAME


class TtsController:
    def __init__(self, voices: list[str]):
        if not voices:
            raise ValueError("At least one voice is required")
        self.voices = voices

    def create_tts(self, text: str, filename: str) -> Path:
        """Creates tts for the text using a random voice.

        Saves to same place recording files go to and returns the opus path.
        """
        import edge_tts
        voice = random.choice(self.voices)
        out_dir = Path(get_app_dir(APP_NAME)) / "temp_storage"
        out_dir.mkdir(parents=True, exist_ok=True)

        mp3_path = out_dir / f"{filename}.mp3"
        edge_tts.Communicate(text, voice).save_sync(str(mp3_path))

        opus_path = self._convert_to_opus(mp3_path)
        mp3_path.unlink()
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
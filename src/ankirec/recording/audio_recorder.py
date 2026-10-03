"""
Contains classes used to record audio on Linux and Windows.
Uses soundcard+numpy on Windows (reliable WASAPI), ffmpeg on Linux (lightweight).
"""

from abc import ABC, abstractmethod
import threading
import subprocess
from pathlib import Path
from typing import Protocol

from ..base.mixin import VerboseMixin

class AudioConfigProtocol(Protocol):
    recording_volume_lufs: float
    sample_rate: int
    bitrate: int
    timestamp: str
    output_dir: Path


class AbstractAudioRecorder(ABC, VerboseMixin):
    """Abstract base for platform-specific audio recorders."""

    def __init__(self, config: AudioConfigProtocol):
        super().__init__()
        self.config = config
        self._thread: threading.Thread = None
        self._lock = threading.Lock()

    @abstractmethod
    def start(self) -> None:
        """Start recording audio in background thread."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop recording and wait for thread to finish."""
        pass

    @abstractmethod
    def get_output_audio(self) -> Path:
        """Get the path to the recorded audio file."""
        pass

    def _wait_for_thread(self, timeout: float = 3.0) -> None:
        """Helper to wait for recording thread to finish"""
        with self._lock:
            thread = self._thread
            self._thread = None

        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
            if thread.is_alive():
                self.warning(f"Recording thread did not terminate within {timeout} s")

    def compress_audio(self, audio_file: Path) -> Path:
        """Compress audio to Opus format using ffmpeg."""
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        compressed_file = audio_file.with_suffix(".opus")

        try:
            subprocess.run(
                [
                    "ffmpeg", "-i", str(audio_file),
                    "-vn",
                    "-map_metadata", "-1",
                    "-acodec", "libopus",
                    "-b:a", f"{self.config.bitrate}k",
                    "-vbr", "on",
                    "-compression_level", "10",
                    "-ar", str(self.config.sample_rate),
                    "-sample_fmt", "s16",
                    "-frame_duration", "60",
                    "-af", f"loudnorm=I={self.config.recording_volume_lufs}:TP=-1.5:LRA=11",
                    "-y",
                    str(compressed_file),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=60,
            )
            audio_file.unlink()

        except FileNotFoundError:
            raise FileNotFoundError(
                "ffmpeg not found. Install with:\n"
                "  Windows: choco install ffmpeg\n"
                "  Linux: sudo apt install ffmpeg"
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg compression failed: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg compression timed out after 60 s")

        return compressed_file
# """
# Contains classes used to record audio on Linux and Windows.
# Uses soundcard+numpy on Windows (reliable WASAPI), ffmpeg on Linux (lightweight).
# """

# from abc import ABC, abstractmethod
# import threading
# import subprocess
# from pathlib import Path
# from typing import Protocol

# from ..base.mixin import VerboseMixin

# class AudioConfigProtocol(Protocol):
#     recording_volume_lufs: float
#     sample_rate: int
#     bitrate: int
#     timestamp: str
#     output_dir: Path


# class AbstractAudioRecorder(ABC, VerboseMixin):
#     """Abstract base for platform-specific audio recorders."""
    
#     def __init__(self, config: AudioConfigProtocol):
#         super().__init__()
#         self.config = config

#     @abstractmethod
#     def start(self, stop_event: threading.Event = None):
#         """Start recording audio. Respects stop_event for graceful shutdown."""
#         pass

#     @abstractmethod
#     def stop(self):
#         """Stop recording."""
#         pass

#     @abstractmethod
#     def get_output_audio(self) -> Path:
#         """Get the path to the recorded audio file."""
#         pass

#     def compress_audio(self, audio_file: Path) -> Path:
#         """Compress audio to Opus format using ffmpeg."""
#         if not audio_file.exists():
#             raise FileNotFoundError(f"Audio file not found: {audio_file}")

#         compressed_file = audio_file.with_suffix(".opus")

#         try:
#             subprocess.run(
#                 [
#                     "ffmpeg", "-i", str(audio_file),
#                     "-vn",
#                     "-map_metadata", "-1",
#                     "-acodec", "libopus",
#                     "-b:a", f"{self.config.bitrate}k",
#                     "-vbr", "on",
#                     "-compression_level", "10",
#                     "-ar", str(self.config.sample_rate),
#                     "-sample_fmt", "s16",
#                     "-frame_duration", "60",
#                     "-af", f"loudnorm=I={self.config.recording_volume_lufs}:TP=-1.5:LRA=11",
#                     "-y",
#                     str(compressed_file),
#                 ],
#                 stdout=subprocess.DEVNULL,
#                 stderr=subprocess.DEVNULL,
#                 check=True,
#                 timeout=60,
#             )
#             audio_file.unlink()

#         except FileNotFoundError:
#             raise FileNotFoundError(
#                 "ffmpeg not found. Install with:\n"
#                 "  Windows: choco install ffmpeg\n"
#                 "  Linux: sudo apt install ffmpeg"
#             )
#         except subprocess.CalledProcessError as e:
#             raise RuntimeError(f"ffmpeg compression failed: {e}")
#         except subprocess.TimeoutExpired:
#             raise RuntimeError("ffmpeg compression timed out after 60 seconds")

#         return compressed_file


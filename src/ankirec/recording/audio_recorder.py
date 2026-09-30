from abc import ABC, abstractmethod
import threading
import time
import subprocess
from pathlib import Path
from typing import Protocol, Optional

from ..base.mixin import VerboseMixin
from ..base.constants import PLATFORM
# PLATFORM = "linux"


class AudioConfigProtocol(Protocol):
    recording_volume_lufs: float
    sample_rate: int
    bitrate: int
    timestamp: str
    output_dir: Path

class AbstractAudioRecorder(ABC, VerboseMixin):
    """Abstract class to contain the core ideas of recording audio. Will differ between OS"""
    def __init__(self, config: AudioConfigProtocol):
        super().__init__()
        self.config = config

    @abstractmethod
    def start(self, stop_event: threading.Event=None):
        """Start recording audio. Respects stop_event for graceful shutdown."""
        pass

    @abstractmethod
    def stop(self):
        """Stop recording"""
        pass

    @abstractmethod
    def get_output_audio(self) -> Path:
        """Gets the output file"""
        pass

    def compress_audio(self, audio_file: Path) -> Path:
        """Uses ffmpeg to compress the audio"""
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        # Output file with .opus extension
        compressed_file = audio_file.with_suffix(".opus")

        try:
            # Use ffmpeg to compress to Opus with loudness normalisation
            bitrate = f"{self.config.bitrate}k"
            lufs = self.config.recording_volume_lufs

            subprocess.run(
                [
                    "ffmpeg", "-i", str(audio_file),
                    "-c:a", "libopus",
                    "-b:a", bitrate,
                    "-ar", str(self.config.sample_rate),   
                    "-compression_level", "10",  
                    "-sample_fmt", "s16",      
                    "-frame_duration", "60",   
                    "-map_metadata", "-1",       
                    "-filter:a", f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
                    "-y",
                    str(compressed_file),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=60,
            )

            # Remove original WAV file
            audio_file.unlink()


        except FileNotFoundError:
            raise FileNotFoundError(
                "ffmpeg not found. Install with: sudo apt install ffmpeg"
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg compression failed: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg compression timed out")

        return compressed_file


class WindowsAudioRecorder(AbstractAudioRecorder):
    """Records audio on windows"""
    def __init__(self, config):
        super().__init__(config)

    def start(self, stop_event = None):
        return super().start(stop_event)

    def stop(self):
        return super().stop()

    def get_output_audio(self) -> Path:
        return super().get_output_audio()


class LinuxAudioRecorder(AbstractAudioRecorder):
    """Records system audio on Linux using parecord (lightweight)."""

    def __init__(self, config: AudioConfigProtocol):
        """Initialise Linux audio recorder with configuration."""
        super().__init__(config)
        self.process: Optional[subprocess.Popen] = None
        self.audio_file: Optional[Path] = None
        self._lock = threading.Lock()
        self._output_dir = Path(config.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def start(self, stop_event: threading.Event = None):
        """
        Start recording audio using parecord. Respects stop_event for graceful shutdown.

        Args:
            stop_event: Threading event to signal when to stop recording.
        """
        self.echo("Audio Recorder: Start")

        with self._lock:
            if self.process is not None:
                raise RuntimeError("Recording already in progress")

            # Generate audio file path with timestamp
            self.audio_file = self._output_dir / f"{self.config.timestamp}.wav"

        try:
            # Get monitor source dynamically
            device = self._get_monitor_source()
            self.echo(f"Recording system audio from: {device}")

            # Build parecord command - let it use device's native format
            # --latency: minimize buffer latency (in microseconds)
            cmd = [
                "parecord",
                "--latency=10000",  # 10ms latency buffer instead of default ~500ms
                "-d", device,
                str(self.audio_file),
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        except FileNotFoundError:
            self.audio_file = None
            raise RuntimeError(
                "parecord not found. Install PulseAudio: sudo apt install pulseaudio-utils"
            )

        # Keep recording until stop_event is set
        while stop_event is None or not stop_event.is_set():
            time.sleep(0.1)

            if self.process and self.process.poll() is not None:
                _, stderr = self.process.communicate()
                self.echo(f"Audio Recorder: Process terminated. stderr: {stderr.decode()}")
                # Clean up immediately so next recording attempt doesn't fail
                with self._lock:
                    self.process = None
                break


    def stop(self) -> None:
        """
        Stop recording gracefully.

        Raises:
            RuntimeError: If recording hasn't started.
        """
        self.echo("Audio Recorder: Stop")

        with self._lock:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError("No recording in progress")

        # Terminate gracefully
        try:
            self.process.terminate()  # SIGTERM
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            # Force kill if SIGTERM didn't work
            self.process.kill()  # SIGKILL
            self.process.wait()

        # Wait for file to be written to disk
        time.sleep(0.5)

    def get_output_audio(self) -> Path:
        """
        Get and return the path to the recorded audio file.

        The audio file is compressed to Opus format before being returned.
        Must be called after stop() has completed.

        Returns:
            Path to the compressed audio file.

        Raises:
            RuntimeError: If no recording has been captured.
        """
        with self._lock:
            if self.audio_file is None:
                raise RuntimeError("No recording available")

            audio_file = self.audio_file
            self.process = None
            self.audio_file = None

        # Compress before returning
        audio_file = self.compress_audio(audio_file=audio_file)

        return audio_file

    @staticmethod
    def _get_monitor_source() -> str:
        """
        Dynamically detect available monitor source (system audio device).
        Scores each monitor against the default sink name for best match.

        Returns:
            Name of a monitor source for system audio recording.

        Raises:
            RuntimeError: If no monitor sources found.
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True, text=True, timeout=3,
            )
            monitors = [
                line.split()[1]
                for line in result.stdout.splitlines()
                if len(line.split()) >= 2 and line.split()[1].endswith(".monitor")
            ]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            monitors = []

        if not monitors:
            raise RuntimeError(
                "No monitor sources found. Is PipeWire/PulseAudio running? "
                "Try: pactl list short sources"
            )

        # Try to score against default sink for better match
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True, text=True, timeout=3,
            )
            default_sink = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            default_sink = ""

        if default_sink:
            keywords = default_sink.lower().replace("-", " ").replace("_", " ").split()

            def score(m: str) -> int:
                m_norm = m.lower().replace("-", " ").replace("_", " ")
                return sum(1 for kw in keywords if kw in m_norm)

            best = max(monitors, key=score)
            if score(best) > 0:
                return best

        # Fallback: prefer USB/headset monitors, then first available
        usb = next(
            (m for m in monitors if any(kw in m.lower() for kw in ("usb", "wireless", "headset", "headphone"))),
            None,
        )
        return usb or monitors[0]


class AudioRecorderFactory:
    @staticmethod
    def create(config: AudioConfigProtocol) -> AbstractAudioRecorder:
        if PLATFORM == "windows":
            return WindowsAudioRecorder(config)
        elif PLATFORM == "linux":
            return LinuxAudioRecorder(config)
        else:
            raise NotImplementedError(f"Platform {PLATFORM} not supported")
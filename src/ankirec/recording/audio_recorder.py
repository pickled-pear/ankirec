"""
Contains classes used to record audio on linux and windows
"""

from abc import ABC, abstractmethod
import threading
import time
import subprocess
from pathlib import Path
from typing import Protocol, Optional

from ..base.mixin import VerboseMixin
from ..base.constants import PLATFORM
# PLATFORM = "linux" or "windows"


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
    def start(self, stop_event: threading.Event = None):
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
        """Uses ffmpeg to compress the audio to Opus format"""
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
                    "-vn",
                    "-map_metadata", "-1",
                    "-acodec", "libopus",
                    "-b:a", bitrate,
                    "-vbr", "on",
                    "-compression_level", "10",
                    "-ar", str(self.config.sample_rate),
                    "-sample_fmt", "s16",
                    "-frame_duration", "60",
                    # "-filter:a", f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
                    "-af", f"loudnorm=I={lufs}:TP=-1.5:LRA=11",
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
            error_msg = (
                "ffmpeg not found. Install with:\n"
                "  Windows: choco install ffmpeg (or download from ffmpeg.org)\n"
                "  Linux: sudo apt install ffmpeg"
            )
            raise FileNotFoundError(error_msg)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"ffmpeg compression failed: {e}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg compression timed out after 60 seconds")

        return compressed_file


class WindowsAudioRecorder(AbstractAudioRecorder):
    """Records system and microphone audio on Windows using ffmpeg and loopback devices."""

    def __init__(self, config: AudioConfigProtocol):
        """Initialise Windows audio recorder with configuration."""
        super().__init__(config)
        self.process: Optional[subprocess.Popen] = None
        self.audio_file: Optional[Path] = None
        self._lock = threading.Lock()
        self._output_dir = Path(config.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._recording_thread: Optional[threading.Thread] = None

    def start(self, stop_event: threading.Event = None):
        """
        Start recording system audio on Windows using ffmpeg and Stereo Mix device.

        Records exclusively from Windows Stereo Mix (system audio loopback).
        Requires Stereo Mix to be enabled in Windows Sound Settings.

        Args:
            stop_event: Threading event to signal when to stop recording.
        """
        self.debug("Audio Recorder: Start (Windows)")

        with self._lock:
            if self.process is not None:
                raise RuntimeError("Recording already in progress")

            # Generate audio file path with timestamp
            self.audio_file = self._output_dir / f"{self.config.timestamp}.wav"

        try:
            # Try to detect Stereo Mix device, fallback to default microphone
            device = self._get_audio_device()
            self.debug(f"Recording audio from: {device}")

            # Build ffmpeg command for Windows
            # Uses dshow (DirectShow) for audio device input
            cmd = [
                "ffmpeg",
                "-f", "dshow",
                "-i", f"audio=\"{device}\"",
                "-c:a", "pcm_s24le",
                "-ar", str(self.config.sample_rate),
                "-acodec", "pcm_s24le",
                "-y",
                str(self.audio_file),
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
            )

            # Start monitoring thread
            self._recording_thread = threading.Thread(
                target=self._monitor_recording,
                args=(stop_event,),
                daemon=True,
            )
            self._recording_thread.start()

        except FileNotFoundError:
            self.audio_file = None
            raise RuntimeError(
                "ffmpeg not found on Windows. "
                "Install from: https://ffmpeg.org/download.html#build-windows "
                "or use: choco install ffmpeg"
            )
        except Exception as e:
            self.audio_file = None
            raise RuntimeError(f"Failed to start audio recording: {e}")

    def _monitor_recording(self, stop_event: Optional[threading.Event]) -> None:
        """Monitor the recording process and handle graceful shutdown."""
        try:
            while stop_event is None or not stop_event.is_set():
                time.sleep(0.1)

                if self.process and self.process.poll() is not None:
                    _, stderr = self.process.communicate()
                    stderr_msg = stderr.decode() if stderr else "No error details"
                    self.debug(f"Audio Recorder: Process terminated. stderr: {stderr_msg}")
                    with self._lock:
                        self.process = None
                    break
        except Exception as e:
            self.error(f"Audio Recorder: Monitoring error: {e}")

    def stop(self) -> None:
        """
        Stop recording gracefully.

        Raises:
            RuntimeError: If recording hasn't started.
        """
        self.debug("Audio Recorder: Stop (Windows)")

        with self._lock:
            if self.process is None or self.process.poll() is not None:
                raise RuntimeError("No recording in progress")

        # Send 'q' to ffmpeg for graceful shutdown
        try:
            self.process.stdin.write(b"q")
            self.process.stdin.flush()
            self.process.wait(timeout=3)
        except (subprocess.TimeoutExpired, BrokenPipeError):
            # Force kill if graceful shutdown didn't work
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

        # Wait for file to be written to disk
        time.sleep(0.5)

        # Wait for monitoring thread to finish
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=2)

    def get_output_audio(self) -> Path:
        """
        Get and return the path to the recorded audio file.

        The audio file is compressed to Opus format before being returned.
        Must be called after stop() has completed.

        Returns:
            Path to the compressed audio file (Opus format).

        Raises:
            RuntimeError: If no recording has been captured.
        """
        with self._lock:
            if self.audio_file is None:
                raise RuntimeError("No recording available")

            audio_file = self.audio_file
            self.process = None
            self.audio_file = None
            self._recording_thread = None

        # Verify file exists and has content
        if not audio_file.exists():
            raise RuntimeError(f"Audio file was not created: {audio_file}")

        if audio_file.stat().st_size == 0:
            audio_file.unlink()
            raise RuntimeError("Audio file is empty. Check audio device configuration.")

        # Compress before returning
        audio_file = self.compress_audio(audio_file=audio_file)

        return audio_file

    @staticmethod
    def _get_audio_device() -> str:
        """
        Detect Stereo Mix (system audio) device on Windows.

        Returns:
            Name of Stereo Mix audio device for system audio recording.

        Raises:
            RuntimeError: If Stereo Mix device not found or disabled.
        """
        try:
            # Use ffmpeg to list audio devices
            result = subprocess.run(
                ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            output = result.stderr  # ffmpeg outputs device info to stderr
            devices = []

            # Parse device list for audio devices
            for line in output.split("\n"):
                if "audio" in line.lower() and '"' in line:
                    # Extract device name from ffmpeg output
                    parts = line.split('"')
                    if len(parts) >= 2:
                        device_name = parts[1]
                        devices.append(device_name)

            if not devices:
                raise RuntimeError("No audio devices found")

            # Look for Stereo Mix (system audio) device
            stereo_mix = next(
                (d for d in devices if "stereo mix" in d.lower()),
                None,
            )

            if stereo_mix:
                return stereo_mix

            # Stereo Mix not found - provide helpful error
            raise RuntimeError(
                "Stereo Mix device not found or disabled. "
                "To enable Stereo Mix on Windows:\n"
                "1. Right-click the speaker icon in system tray\n"
                "2. Click 'Open Sound settings'\n"
                "3. Go to 'Recording devices'\n"
                "4. Right-click 'Stereo Mix' and select 'Enable'\n"
                f"Available audio devices: {', '.join(devices)}"
            )

        except (FileNotFoundError, subprocess.TimeoutExpired, IndexError) as e:
            raise RuntimeError(
                f"Failed to detect audio devices: {e}. "
                "Ensure ffmpeg is installed and in PATH."
            )


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
        self.debug("Audio Recorder: Start (Linux)")

        with self._lock:
            if self.process is not None:
                raise RuntimeError("Recording already in progress")

            # Generate audio file path with timestamp
            self.audio_file = self._output_dir / f"{self.config.timestamp}.wav"

        try:
            # Get monitor source dynamically
            device = self._get_monitor_source()
            self.debug(f"Recording system audio from: {device}")

            # Build parecord command - let it use device's native format
            # --latency: minimise buffer latency (in microseconds)
            cmd = [
                "parecord",
                "--latency=10000",  # 10 ms latency buffer instead of default ~500 ms
                "-d", device,
                "--format=s24le", 
                f"--rate={self.config.sample_rate}",
                "--channels=2",
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
                self.debug(f"Audio Recorder: Process terminated. stderr: {stderr.decode()}")
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
        self.debug("Audio Recorder: Stop (Linux)")

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

    def _get_monitor_source(self) -> str:
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
            self.warning("No monitors")
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
            self.warning("Something went wrong. No sink found for audio")
            default_sink = ""

        if default_sink:
            keywords = default_sink.lower().replace("-", " ").replace("_", " ").split()

            def score(m: str) -> int:
                m_norm = m.lower().replace("-", " ").replace("_", " ")
                return sum(1 for kw in keywords if kw in m_norm)

            best = max(monitors, key=score)
            for monitor in monitors:
                self.debug(f"Found monitor {monitor}")
            if score(best) > 0:
                self.debug(f"Best monitor: {best}")
                return best

        # Fallback: prefer USB/headset monitors, then first available
        usb = next(
            (m for m in monitors if any(kw in m.lower() for kw in ("usb", "wireless", "headset", "headphone"))),
            None,
        )
        if usb:
            self.debug(f"USB headset: {usb}")

        return usb or monitors[0]


class AudioRecorderFactory:
    """Factory for creating platform-specific audio recorder instances."""

    @staticmethod
    def create(config: AudioConfigProtocol) -> AbstractAudioRecorder:
        """
        Create appropriate audio recorder for the current platform.

        Args:
            config: Audio configuration object implementing AudioConfigProtocol.

        Returns:
            Platform-specific AbstractAudioRecorder instance.

        Raises:
            NotImplementedError: If platform is not supported.
        """
        if PLATFORM == "windows":
            return WindowsAudioRecorder(config)
        elif PLATFORM == "linux":
            return LinuxAudioRecorder(config)
        else:
            raise NotImplementedError(f"Platform {PLATFORM} not supported")
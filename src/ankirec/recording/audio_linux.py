import threading
import subprocess
import time

from typing import Optional
from pathlib import Path

from .audio_recorder import AbstractAudioRecorder, AudioConfigProtocol

class LinuxAudioRecorder(AbstractAudioRecorder):
    """Records system audio on Linux using ffmpeg + PulseAudio."""

    def __init__(self, config: AudioConfigProtocol):
        super().__init__(config)
        self.process: Optional[subprocess.Popen] = None
        self.audio_file: Optional[Path] = None
        self._output_dir = Path(config.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self.is_recording = False

    def start(self) -> None:
        """Start recording audio in background thread using ffmpeg + PulseAudio."""
        self.debug("Audio Recorder: Start (Linux)")

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Recording thread already running")

            self.audio_file = self._output_dir / f"{self.config.timestamp}.wav"
            self.is_recording = True
            self._thread = threading.Thread(
                target=self._record_loop,
                daemon=False,
            )
            self._thread.start()

    def _record_loop(self) -> None:
        """Background recording loop"""
        try:
            device = self._get_monitor_source()
            self.debug(f"Recording from: {device}")

            cmd = [
                "ffmpeg", "-y",
                "-f", "pulse",
                "-fragment_size", "4096",
                "-i", device,
                "-ar", str(self.config.sample_rate),
                "-ac", "2",
                str(self.audio_file),
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.PIPE,
            )

            # Wait for process to finish or stop signal
            while self.is_recording and self.process.poll() is None:
                time.sleep(0.1)

        except FileNotFoundError:
            self.audio_file = None
            raise RuntimeError("ffmpeg not found. Install: sudo apt install ffmpeg")
        except Exception as e:
            self.error(f"Recording loop error: {e}")
        finally:
            self.is_recording = False
            self.debug("Recording loop ended")

    def stop(self) -> None:
        """Stop recording gracefully."""
        self.debug("Audio Recorder: Stop (Linux)")

        self.is_recording = False

        # Signal ffmpeg to stop
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
                self.process.wait(timeout=3)
            except (subprocess.TimeoutExpired, BrokenPipeError):
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()

            time.sleep(0.5)

        # Wait for recording thread to finish
        self._wait_for_thread(timeout=3)

    def get_output_audio(self) -> Path:
        """Get and return the compressed audio file."""
        with self._lock:
            if self.audio_file is None:
                raise RuntimeError("No recording available")

            audio_file = self.audio_file
            self.process = None
            self.audio_file = None

        if not audio_file.exists():
            raise RuntimeError("Audio file was not created")

        if audio_file.stat().st_size == 0:
            audio_file.unlink()
            raise RuntimeError("Audio file is empty")

        return self.compress_audio(audio_file)

    @staticmethod
    def _get_monitor_source() -> str:
        """Detect monitor source using pactl."""
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True,
                text=True,
                timeout=3,
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
                "No monitor sources found. Is PulseAudio/PipeWire running?\n"
                "Try: pactl list short sources"
            )

        # Score against default sink
        try:
            result = subprocess.run(
                ["pactl", "get-default-sink"],
                capture_output=True,
                text=True,
                timeout=3,
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

        # Fallback: USB/headset, then first available
        usb = next(
            (m for m in monitors if any(
                kw in m.lower() for kw in ("usb", "wireless", "headset", "headphone")
            )),
            None,
        )
        return usb or monitors[0]

# import threading
# import subprocess
# import time

# from typing import Optional
# from pathlib import Path

# from .audio_recorder import AbstractAudioRecorder, AudioConfigProtocol

# class LinuxAudioRecorder(AbstractAudioRecorder):
#     """Records system audio on Linux using ffmpeg + PulseAudio."""

#     def __init__(self, config: AudioConfigProtocol):
#         super().__init__(config)
#         self.process: Optional[subprocess.Popen] = None
#         self.audio_file: Optional[Path] = None
#         self._lock = threading.Lock()
#         self._output_dir = Path(config.output_dir)
#         self._output_dir.mkdir(parents=True, exist_ok=True)
#         self.is_recording = False

#     def start(self, stop_event: threading.Event = None):
#         """Start recording using ffmpeg + PulseAudio."""
#         self.debug("Audio Recorder: Start (Linux)")

#         with self._lock:
#             if self.process is not None:
#                 raise RuntimeError("Recording already in progress")

#             self.audio_file = self._output_dir / f"{self.config.timestamp}.wav"

#         try:
#             device = self._get_monitor_source()
#             self.debug(f"Recording from: {device}")

#             cmd = [
#                 "ffmpeg", "-y",
#                 "-f", "pulse",
#                 "-fragment_size", "4096",
#                 "-i", device,
#                 "-ar", str(self.config.sample_rate),
#                 "-ac", "2",
#                 str(self.audio_file),
#             ]

#             self.process = subprocess.Popen(
#                 cmd,
#                 stdout=subprocess.DEVNULL,
#                 stderr=subprocess.DEVNULL,
#                 stdin=subprocess.PIPE,
#             )
#             self.is_recording = True

#             # Wait for stop event in background
#             threading.Thread(
#                 target=self._wait_for_stop,
#                 args=(stop_event,),
#                 daemon=True,
#             ).start()

#         except FileNotFoundError:
#             self.audio_file = None
#             raise RuntimeError("ffmpeg not found. Install: sudo apt install ffmpeg")

#     def _wait_for_stop(self, stop_event: Optional[threading.Event]):
#         """Monitor for stop event or process termination."""
#         try:
#             while self.is_recording:
#                 if stop_event and stop_event.is_set():
#                     self.debug("Stop event received")
#                     break

#                 # Check if process died
#                 if self.process and self.process.poll() is not None:
#                     self.debug("Process terminated unexpectedly")
#                     break

#                 time.sleep(0.1)
#         except Exception as e:
#             self.error(f"Wait loop error: {e}")

#     def stop(self) -> None:
#         """Stop recording gracefully."""
#         self.debug("Audio Recorder: Stop (Linux)")

#         with self._lock:
#             if self.process is None or self.process.poll() is not None:
#                 raise RuntimeError("No recording in progress")

#         self.is_recording = False

#         # Signal ffmpeg to stop
#         try:
#             self.process.stdin.write(b"q")
#             self.process.stdin.flush()
#             self.process.wait(timeout=3)
#         except (subprocess.TimeoutExpired, BrokenPipeError):
#             self.process.terminate()
#             try:
#                 self.process.wait(timeout=2)
#             except subprocess.TimeoutExpired:
#                 self.process.kill()
#                 self.process.wait()

#         time.sleep(0.5)

#     def get_output_audio(self) -> Path:
#         """Get and return the compressed audio file."""
#         with self._lock:
#             if self.audio_file is None:
#                 raise RuntimeError("No recording available")

#             audio_file = self.audio_file
#             self.process = None
#             self.audio_file = None

#         if not audio_file.exists():
#             raise RuntimeError("Audio file was not created")

#         if audio_file.stat().st_size == 0:
#             audio_file.unlink()
#             raise RuntimeError("Audio file is empty")

#         return self.compress_audio(audio_file)

#     @staticmethod
#     def _get_monitor_source() -> str:
#         """Detect monitor source using pactl."""
#         try:
#             result = subprocess.run(
#                 ["pactl", "list", "short", "sources"],
#                 capture_output=True,
#                 text=True,
#                 timeout=3,
#             )
#             monitors = [
#                 line.split()[1]
#                 for line in result.stdout.splitlines()
#                 if len(line.split()) >= 2 and line.split()[1].endswith(".monitor")
#             ]
#         except (FileNotFoundError, subprocess.TimeoutExpired):
#             monitors = []

#         if not monitors:
#             raise RuntimeError(
#                 "No monitor sources found. Is PulseAudio/PipeWire running?\n"
#                 "Try: pactl list short sources"
#             )

#         # Score against default sink
#         try:
#             result = subprocess.run(
#                 ["pactl", "get-default-sink"],
#                 capture_output=True,
#                 text=True,
#                 timeout=3,
#             )
#             default_sink = result.stdout.strip()
#         except (FileNotFoundError, subprocess.TimeoutExpired):
#             default_sink = ""

#         if default_sink:
#             keywords = default_sink.lower().replace("-", " ").replace("_", " ").split()

#             def score(m: str) -> int:
#                 m_norm = m.lower().replace("-", " ").replace("_", " ")
#                 return sum(1 for kw in keywords if kw in m_norm)

#             best = max(monitors, key=score)
#             if score(best) > 0:
#                 return best

#         # Fallback: USB/headset, then first available
#         usb = next(
#             (m for m in monitors if any(
#                 kw in m.lower() for kw in ("usb", "wireless", "headset", "headphone")
#             )),
#             None,
#         )
#         return usb or monitors[0]
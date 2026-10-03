"""
Windows audio recorder using WASAPI loopback via soundcard.

Dependencies: soundcard, soundfile, pywin32
"""

import threading
import gc
from pathlib import Path
from typing import Optional

import pythoncom
import soundcard as sc
import soundfile as sf
import numpy as np

from .audio_recorder import AbstractAudioRecorder, AudioConfigProtocol


class WindowsAudioRecorder(AbstractAudioRecorder):
    """Records system audio on Windows using WASAPI loopback."""

    def __init__(self, config: AudioConfigProtocol):
        super().__init__(config)
        self.audio_file: Optional[Path] = None
        self._lock = threading.Lock()
        self._ready_event = threading.Event()
        self._stop_event: Optional[threading.Event] = None
        self._output_dir = Path(config.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        self.audio_data = []
        self.is_recording = False
        self.record_thread: Optional[threading.Thread] = None
        self.mic = None

    def start(self, stop_event: threading.Event = None):
        """Start recording system audio using WASAPI loopback."""
        self.debug("Audio Recorder: Start (Windows)")

        with self._lock:
            if self.is_recording:
                raise RuntimeError("Recording already in progress")

        try:
            # CRITICAL: Initialise COM ONLY for device selection
            # This must be brief — COM is uninitialised immediately after
            pythoncom.CoInitialize()
            try:
                # Select device while COM is initialised
                self.mic = self._select_loopback_device()
                self.debug(f"Using device: {self.mic.name}")
            finally:
                # CRITICAL: Uninitialise COM immediately after device selection
                # This prevents conflicts with tkinter's event loop later
                pythoncom.CoUninitialize()

        except Exception as e:
            raise RuntimeError(f"Failed to initialise audio device: {e}")

        with self._lock:
            self.audio_file = self._output_dir / f"{self.config.timestamp}.wav"
            self.audio_data = []
            self._stop_event = stop_event
            self._ready_event.clear()
            self.record_thread = None
            self.is_recording = True

        try:
            # Start recording thread (non-daemon for clean shutdown)
            self.record_thread = threading.Thread(
                target=self._record_loop,
                daemon=False,
            )
            self.record_thread.start()

            # Wait for recording thread to signal it's ready
            if not self._ready_event.wait(timeout=5.0):
                self.warning("Recording thread took >5 s to initialise")

            self.debug("Recording thread ready")

        except Exception as e:
            with self._lock:
                self.is_recording = False
                self.audio_data = []
                self.mic = None

            raise RuntimeError(f"Failed to start recording thread: {e}")

    def _record_loop(self):
        """Recording thread loop. Initialises COM on this thread only."""
        recorder = None
        com_initialised = False

        try:
            # Initialise COM on this thread
            pythoncom.CoInitialize()
            com_initialised = True
            self.debug("COM initialised on recording thread")

            # Create recorder using context manager
            recorder = self.mic.recorder(
                samplerate=self.config.sample_rate,
                blocksize=4096,
            )

            # Enter context to acquire recorder resources
            recorder.__enter__()

            # Signal that recorder is ready
            self._ready_event.set()
            self.debug("Recorder initialised and ready")

            # Main recording loop
            while self.is_recording:
                # Check external stop event
                if self._stop_event and self._stop_event.is_set():
                    self.debug("Stop event received in record loop")
                    break

                try:
                    data = recorder.record(numframes=4096)
                except Exception as e:
                    self.error(f"Error recording block: {e}")
                    break

                if data is None or len(data) == 0:
                    self.debug("No data from recorder, stopping")
                    break

                # Store chunk safely
                with self._lock:
                    if self.is_recording:
                        self.audio_data.append(data.copy())

        except Exception as e:
            self.error(f"Recording thread error: {e}")

        finally:
            # CRITICAL: Ensure resources are released in correct order

            # 1. Exit recorder context manager
            if recorder is not None:
                try:
                    recorder.__exit__(None, None, None)
                    self.debug("Recorder context exited cleanly")
                except Exception as e:
                    self.debug(f"Error exiting recorder context: {e}")

            # 2. Release recorder reference
            recorder = None

            # 3. Uninitialise COM on this thread
            if com_initialised:
                try:
                    pythoncom.CoUninitialize()
                    self.debug("COM uninitialised on recording thread")
                except Exception as e:
                    self.debug(f"Error uninitialising COM: {e}")

            # 4. Mark recording as stopped
            with self._lock:
                self.is_recording = False

            # 5. Force garbage collection
            gc.collect()

            self.debug(f"Recording thread cleanup complete. Chunks: {len(self.audio_data)}")

    def stop(self) -> None:
        """Stop recording gracefully."""
        self.debug("Audio Recorder: Stop (Windows)")

        with self._lock:
            if not self.is_recording:
                self.debug("Recording already stopped")
            else:
                self.is_recording = False

        # Wait for thread to finish with timeout
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=3)
            if self.record_thread.is_alive():
                self.warning("Recording thread did not terminate within 3 s")

        self.record_thread = None

        # Release device reference
        with self._lock:
            self.mic = None

        # Force garbage collection to ensure COM cleanup
        gc.collect()

        self.debug("Recording stopped and cleaned up")

    def get_output_audio(self) -> Path:
        """Get and return the compressed audio file."""

        # Copy audio data safely
        with self._lock:
            if self.audio_file is None:
                raise RuntimeError("No audio file was created")

            audio_file = self.audio_file
            audio_chunks = self.audio_data.copy()
            self.audio_data = []

        if len(audio_chunks) == 0:
            self.warning("No audio data was recorded - recording may have been interrupted")
            raise RuntimeError("No audio data recorded")

        # Concatenate and write audio
        try:
            self.debug(f"Concatenating {len(audio_chunks)} audio chunks")
            audio_data = np.vstack(audio_chunks)

            # Normalise to prevent clipping
            max_val = np.max(np.abs(audio_data))
            self.debug(f"Audio peak level: {max_val:.3f}")

            if max_val > 1.0:
                self.warning(f"Audio clipped (peak: {max_val:.3f}). Normalising...")
                audio_data = audio_data / max_val

            # Add ~3 dB headroom for compression
            audio_data = audio_data * 0.7

            # Clip to valid range
            audio_data = np.clip(audio_data, -1.0, 1.0)

            self.debug(f"Writing audio: shape={audio_data.shape}, peak={np.max(np.abs(audio_data)):.3f}")
            sf.write(
                audio_file,
                audio_data,
                self.config.sample_rate,
                subtype="FLOAT",
            )
            self.debug(f"Audio file written to {audio_file}")

            # Clear chunks from memory
            audio_chunks = []

        except Exception as e:
            raise RuntimeError(f"Failed to write audio file: {e}")
        finally:
            gc.collect()

        # Compress to Opus
        return self.compress_audio(audio_file)

    @staticmethod
    def _select_loopback_device():
        """Find WASAPI loopback device. MUST be called with COM initialised."""
        speaker = sc.default_speaker()
        if not speaker:
            raise RuntimeError("No default speaker found")

        loopbacks = sc.all_microphones(include_loopback=True)
        if not loopbacks:
            raise RuntimeError("No loopback devices found")

        # Try to match loopback to default speaker
        name_match = next(
            (m for m in loopbacks if speaker.name.lower() in m.name.lower()),
            None,
        )
        if name_match:
            return name_match

        # Fallback: first loopback device with "loopback" in name
        lb_match = next(
            (m for m in loopbacks if "loopback" in m.name.lower()),
            None,
        )
        return lb_match or loopbacks[0]

    def __enter__(self):
        """Context manager support for automatic cleanup."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure cleanup on context manager exit."""
        self.stop()
        return False
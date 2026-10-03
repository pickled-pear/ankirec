"""
Windows audio recorder using WASAPI loopback via soundcard.

Dependencies: soundcard, soundfile, pywin32
"""

import threading
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
        self._ready_event = threading.Event()  # Signals when recorder is ready
        self._output_dir = Path(config.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        
        self.audio_data = []  # List of chunks
        self.is_recording = False
        self._recording_started = False  # Track if recording thread has actually started
        self.record_thread: Optional[threading.Thread] = None
        self.mic = None
        self._stop_event = None

    def start(self, stop_event: threading.Event = None):
        """Start recording system audio using WASAPI loopback."""
        self.debug("Audio Recorder: Start (Windows)")

        with self._lock:
            if self.is_recording:
                raise RuntimeError("Recording already in progress")

            self.audio_file = self._output_dir / f"{self.config.timestamp}.wav"
            self.audio_data = []
            self._recording_started = False  # Reset flag for new recording
            self._stop_event = stop_event
            self._ready_event.clear()
            self.record_thread = None

        # Do COM initialization on this thread BEFORE starting recording thread
        # This avoids race conditions and is much faster on first run
        try:
            pythoncom.CoInitialize()
        except:
            # Already initialized, that's fine
            pass

        try:
            self.mic = self._select_loopback_device()
            self.debug(f"Using device: {self.mic.name}")

            # Start recording thread (NOT daemon, so we can join cleanly)
            self.record_thread = threading.Thread(
                target=self._record_loop,
                daemon=False,
            )
            self.record_thread.start()

            # Wait for recording thread to signal it's ready
            # Timeout after 5 seconds as a safety net
            if not self._ready_event.wait(timeout=5.0):
                self.warning("Recording thread took >5s to initialize")
            
            with self._lock:
                self.is_recording = True
            
            self.debug("Recording thread ready")

        except Exception as e:
            with self._lock:
                self.is_recording = False
                self.audio_data = []
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            raise RuntimeError(f"Failed to start recording: {e}")

    def _record_loop(self):
        """Recording thread loop."""
        recorder = None
        try:
            # Initialize COM on this thread with apartment mode for better interop
            pythoncom.CoInitialize()
            
            # Create recorder in a scoped context to ensure cleanup
            recorder = self.mic.recorder(
                samplerate=self.config.sample_rate,
                blocksize=4096,
            )
            recorder.__enter__()
            
            # Signal that recorder is ready and first block is about to be read
            with self._lock:
                self._recording_started = True
            self._ready_event.set()
            self.debug("Recorder initialized and ready")
            
            while self.is_recording:
                # Check stop event
                if self._stop_event and self._stop_event.is_set():
                    self.debug("Stop event received in record loop")
                    break

                # Read audio block
                try:
                    data = recorder.record(numframes=4096)
                except Exception as e:
                    self.error(f"Error recording block: {e}")
                    break
                    
                if data is None or len(data) == 0:
                    self.debug("No data from recorder, stopping")
                    break

                # Store chunk
                with self._lock:
                    if self.is_recording:
                        self.audio_data.append(data.copy())  # Copy to avoid reference issues

        except Exception as e:
            self.error(f"Recording thread error: {e}")
        finally:
            # CRITICAL: Explicitly close recorder to release COM objects
            try:
                if recorder is not None:
                    recorder.__exit__(None, None, None)
            except Exception as e:
                self.debug(f"Error closing recorder: {e}")
            
            # Release recorder reference
            recorder = None
            
            with self._lock:
                self.is_recording = False
            
            # Uninitialize COM thread
            try:
                pythoncom.CoUninitialize()
            except:
                pass
            
            # Force garbage collection to clean up any remaining COM references
            import gc
            gc.collect()
            
            self.debug(f"Recording thread ended. Chunks collected: {len(self.audio_data)}")

    def stop(self) -> None:
        """Stop recording gracefully."""
        self.debug("Audio Recorder: Stop (Windows)")

        with self._lock:
            self.mic = None
            if not self.is_recording:
                # Thread may have exited on its own (e.g., due to error or short recording)
                # This is not an error condition
                self.debug("Recording already stopped")
                return

            self.is_recording = False

        # Wait for thread to finish, but use a shorter timeout to prevent UI blocking
        if self.record_thread and self.record_thread.is_alive():
            self.record_thread.join(timeout=2)  # Reduced from 5s to allow faster UI recovery
            if self.record_thread.is_alive():
                self.warning("Recording thread did not terminate within 2 seconds")
        
        self.record_thread = None
        
        # CRITICAL: Release COM objects immediately to unblock Windows message queue
        with self._lock:
            self.mic = None
        
        # Force garbage collection to ensure COM cleanup
        import gc
        gc.collect()
        
        self.debug("Recording stopped, thread joined, COM objects released")

    def get_output_audio(self) -> Path:
        """Get and return the compressed audio file."""
        with self._lock:
            if self.audio_file is None:
                raise RuntimeError("No audio file was created")
            
            audio_file = self.audio_file
            audio_chunks = self.audio_data.copy()
            self.audio_data = []
        
        if len(audio_chunks) == 0:
            # Recording may have been too short or thread exited early
            self.warning("No audio data was recorded - recording may have been interrupted or too short")
            raise RuntimeError("No audio data recorded")

        # Concatenate chunks and write WAV file
        try:
            if len(audio_chunks) == 0:
                raise RuntimeError("No audio data to write")
            
            self.debug(f"Concatenating {len(audio_chunks)} audio chunks")
            audio_data = np.vstack(audio_chunks)
            
            # CRITICAL: Normalize to prevent clipping
            # soundcard returns f32 in range [-1.0, 1.0], but hot signals can exceed this
            max_val = np.max(np.abs(audio_data))
            self.debug(f"Audio peak level: {max_val:.3f}")
            
            if max_val > 1.0:
                self.warning(f"Audio clipped (peak: {max_val:.3f}). Normalizing to prevent distortion...")
                audio_data = audio_data / max_val  # Scale down to fit in [-1.0, 1.0]
            
            # Add 3 dB headroom to prevent compression artifacts
            # This matches loudness perceptually but gives the compressor headroom
            audio_data = audio_data * 0.7  # 0.7 ≈ -3.1 dB
            
            # Ensure values are strictly within valid range for WAV output
            audio_data = np.clip(audio_data, -1.0, 1.0)
            
            self.debug(f"Writing audio: shape={audio_data.shape}, dtype={audio_data.dtype}, peak={np.max(np.abs(audio_data)):.3f}")
            sf.write(
                audio_file,
                audio_data,
                self.config.sample_rate,
                subtype="FLOAT",
            )
            self.debug(f"Audio file written to {audio_file}")
        except Exception as e:
            raise RuntimeError(f"Failed to write audio file: {e}")

        # Compress to Opus
        return self.compress_audio(audio_file)

    @staticmethod
    def _select_loopback_device():
        """Find WASAPI loopback device."""
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

        # Fallback: first loopback device
        lb_match = next(
            (m for m in loopbacks if "loopback" in m.name.lower()),
            None,
        )
        return lb_match or loopbacks[0]
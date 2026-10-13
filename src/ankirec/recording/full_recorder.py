from ..base.mixin import VerboseMixin
# from ..base.constants import PLATFORM, SCRIPT_DIR
from ..base.config import Config, RecordingConfig
from .audio_recorder_factory import AudioRecorderFactory
from .screen_recorder import ScreenshotTaker
from ..base.constants import APP_NAME
from ..audio.audioplayer import AudioPlayerController

from pathlib import Path
from datetime import datetime
from click import get_app_dir
import threading
import time


class FullRecorder(VerboseMixin):
    """Handles both recording image and audio.

    Thread safety: start_recording, stop_recording and abort may be called from
    any thread (e.g. a hotkey listener). They are fully serialised by a single
    lock, so one transition always finishes before the next begins. This class
    is the single owner of the `recording` state; callers should read it, never set it.
    """

    recording: bool
    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        # Lock so two threads can't both create the singleton
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(FullRecorder, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialise once
        if hasattr(self, '_initialised'):
            return
        self._initialised = True
        self.audio_controller = AudioPlayerController(volume=Config().load_section("general").get("sfx_volume", 0.5))

        super().__init__()
        self.config = self._load_config()
        self.audio_recorder = AudioRecorderFactory.create(config=self.config)
        self.screen_recorder = ScreenshotTaker(config=self.config)
        self.recording_cycle = 0
        self.recording = False

        # Held for the whole of start/stop/abort, so an abort from the listener
        # thread can never interleave with a half-finished start or stop.
        self._transition_lock = threading.Lock()
        # Files already in the media folder when the current recording began.
        # Anything not in this set on abort belongs to the aborted recording.
        self._preexisting_files: set[Path] = set()

    def _load_config(self) -> RecordingConfig:
        """Loads the values in the config file to the config dataclass"""
        config = Config()
        rec_config = config.load_section("recording")
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        media_output_dir = Path(get_app_dir(APP_NAME)) / "temp_storage"
        media_output_dir.mkdir(parents=True, exist_ok=True)
        return RecordingConfig(
            fps=rec_config.get("fps", 10),
            max_duration=rec_config.get("max_duration", 30),
            recording_volume_lufs=rec_config.get("recording_volume_lufs", -22),
            ffmpeg_compression_factor=rec_config.get("image_compression_factor", 6),
            output_image_height_px=rec_config.get("output_image_height_px", 960),
            sample_rate=rec_config.get("sample_rate", 48000),
            bitrate=rec_config.get("bitrate_kbps", 48),
            output_dir=media_output_dir,
            timestamp=timestamp,
            screenshot_time=rec_config.get("screenshot_time", 0.8),
            wipe_media_folder=rec_config.get("wipe_media_folder", True)
        )

    def start_recording(self) -> None:
        """Start recording both audio and screenshots."""
        with self._transition_lock:
            if self.recording:
                self.warning("start_recording called while already recording; ignoring")
                return

            self.info("Beginning recording...")
            self.recording_cycle += 1

            now = datetime.now()
            self.start_time = time.time()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            self.config.timestamp = timestamp

            # Remember what was already on disk so an abort only removes this recording's files
            self._preexisting_files = self._snapshot_media_files()

            # Start audio recorder (spawns thread internally)
            try:
                self.audio_recorder.start()
            except Exception as e:
                self.error(f"Failed to start audio recorder: {e}")
                raise

            # Start screenshot recorder (spawns thread internally)
            try:
                self.screen_recorder.start()
            except Exception as e:
                self.error(f"Failed to start screen recorder: {e}")
                # Clean up audio recorder on failure
                try:
                    self.audio_recorder.stop()
                except Exception as cleanup_error:
                    self.error(f"Error cleaning up audio recorder: {cleanup_error}")
                raise

            # Only mark as recording once both recorders are actually running
            self.recording = True
            self.debug("Recording started (audio and screenshots recording)")

    def stop_recording(self) -> tuple[Path | None, Path | None]:
        """Stop recording and clean up threads."""
        with self._transition_lock:
            if not self.recording:
                # Either never started, or an abort got there first
                self.warning("stop_recording called with no recording in progress")
                return None, None
            self.recording = False

            self.info("Stopping recording...")
            end_time = time.time()

            # Stop screen recorder (waits for thread internally)
            screenshot = None
            try:
                self.screen_recorder.stop()
                screenshot = self.screen_recorder.get_output_screenshot()
                self.debug(f"Screenshot file ready: {screenshot}")
            except Exception as e:
                self.error(f"Error stopping screen recorder: {e}")

            # Stop audio recorder (waits for thread internally)
            audio_file = None
            try:
                self.audio_recorder.stop()
                audio_file = self.audio_recorder.get_output_audio()
                self.debug(f"Audio file ready: {audio_file}")
            except Exception as e:
                self.error(f"Error stopping audio recorder: {e}")

            self.wipe_media_folder(audio_file, screenshot)

            self.info("### Recording Done ###\n")
            self.recording_cycle += 1
            return screenshot, audio_file

    def abort(self, silent: bool = False) -> bool:
        """
        Aborts the current recording, stops both recorders and discards
        everything this recording wrote to disk.

        Safe to call from any thread at any time. If a start or stop is in
        progress, this waits for it to finish first: an abort during start
        then cleanly aborts the new recording, and an abort after a stop is a
        no-op. Blocks until the recorders have shut down, so call it from a
        worker thread rather than directly inside a key callback.

        Returns False so callers can use it as a "recording did not complete" result.
        """
        with self._transition_lock:
            if not self.recording:
                self.debug("Abort requested but no recording in progress; ignoring")
                return False
            self.recording = False

            self.warning("ABORTING RECORDING")

            if not silent:
                try:
                    self.audio_controller.play_sfx("abort.mp3")
                except Exception as e:
                    self.debug(f"Could not play abort sound: {e}")

            # Stop both recorders independently so one failing doesn't leave the other running
            for name, recorder in (("screen", self.screen_recorder), ("audio", self.audio_recorder)):
                try:
                    recorder.stop()
                except Exception as e:
                    self.error(f"Error aborting {name} recorder: {e}")

            # Always discard the aborted recording's files, regardless of the
            # wipe_media_folder setting (that setting governs leftovers from
            # *completed* recordings, not partial ones).
            self._discard_current_recording_files()

            # Also honour the normal wipe behaviour for anything else in the folder
            self.wipe_media_folder()

            self.info("### Recording Aborted ###\n")
            return False

    def _snapshot_media_files(self) -> set[Path]:
        """Returns the resolved paths of all files currently in the media folder."""
        media_path = Path(self.config.output_dir)
        if not media_path.exists():
            return set()
        return {p.resolve() for p in media_path.rglob("*") if p.is_file()}

    def _discard_current_recording_files(self) -> None:
        """Deletes every file created in the media folder since the current recording started."""
        new_files = self._snapshot_media_files() - self._preexisting_files
        for file_path in new_files:
            try:
                file_path.unlink(missing_ok=True)
                self.debug(f"Discarded aborted recording file: {file_path}")
            except Exception as e:
                self.error(f"Error deleting {file_path}: {e}")
        self._preexisting_files = set()

    def wipe_media_folder(self, *exclude: Path):
        """Wipes the media folder of all files, excluding given files (only if enabled)."""
        if self.config.wipe_media_folder:
            self.info("Cleaning up temporary media files...")

            media_path = Path(self.config.output_dir)

            if not media_path.exists():
                return

            # Convert exclude paths to a set for O(1) lookup
            exclude_set = {path.resolve() for path in exclude if path is not None}

            # Iterate through all files in the media folder
            for file_path in media_path.rglob("*"):
                # Skip directories, only delete files
                if file_path.is_file():
                    # Check if file is in the exclude set
                    if file_path.resolve() not in exclude_set:
                        try:
                            file_path.unlink()
                        except Exception as e:
                            self.error(f"Error deleting {file_path}: {e}")
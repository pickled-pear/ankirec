from ..base.mixin import VerboseMixin
# from ..base.constants import PLATFORM, SCRIPT_DIR
from ..base.config import Config, RecordingConfig
from .audio_recorder_factory import AudioRecorderFactory
from .screen_recorder import ScreenshotTaker
from ..base.constants import APP_NAME

from pathlib import Path
from datetime import datetime
from click import get_app_dir
import time


class FullRecorder(VerboseMixin):
    """Handles both recording image and audio"""

    recording: bool
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FullRecorder, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialise once
        if hasattr(self, '_initialised'):
            return
        self._initialised = True

        super().__init__()
        self.config = self._load_config()
        self.audio_recorder = AudioRecorderFactory.create(config=self.config)
        self.screen_recorder = ScreenshotTaker(config=self.config)
        self.recording_cycle = 0
        self.recording = False

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
        self.info("Beginning recording...")
        self.recording_cycle += 1
        self.recording = True

        now = datetime.now()
        self.start_time = time.time()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        self.config.timestamp = timestamp

        # Start audio recorder (spawns thread internally)
        try:
            self.audio_recorder.start()
        except Exception as e:
            self.error(f"Failed to start audio recorder: {e}")
            self.recording = False
            raise

        # Start screenshot recorder (spawns thread internally)
        try:
            self.screen_recorder.start()
        except Exception as e:
            self.error(f"Failed to start screen recorder: {e}")
            self.recording = False
            # Clean up audio recorder on failure
            try:
                self.audio_recorder.stop()
            except Exception as cleanup_error:
                self.error(f"Error cleaning up audio recorder: {cleanup_error}")
            raise

        self.debug("Recording started (audio and screenshots recording)")

    def stop_recording(self) -> tuple[Path, Path]:
        """Stop recording and clean up threads."""
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

        self.recording = False
        self.info("### Recording Done ###\n")
        self.recording_cycle += 1
        return screenshot, audio_file

    def abort(self, silent: bool = False) -> bool:
        """Aborts recording and cleans up threads."""
        self.warning("ABORTING RECORDING")
        self.recording = False

        # Stop screen recorder
        try:
            self.screen_recorder.stop()
        except Exception as e:
            self.debug(f"Error aborting screen recorder: {e}")

        # Stop audio recorder
        try:
            self.audio_recorder.stop()
        except Exception as e:
            self.debug(f"Error aborting audio recorder: {e}")

        self.wipe_media_folder()
        return False

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

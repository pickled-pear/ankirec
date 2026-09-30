from ..base.mixin import *
from ..base.constants import PLATFORM, SCRIPT_DIR
# from ..base.universal import timeout_wrapper
from ..base.universal import warn
from ..base.config import Config, RecordingConfig
from .audio_recorder import AudioRecorderFactory
from .screen_recorder import ScreenshotTaker

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import threading
import time


    


# class FullRecorder(VerboseMixin):
#     """Handles both recording image and audio"""
 
#     def __init__(self):
#         super().__init__()
#         self.audio_recorder = LinuxAudioRecorder()
#         self.screen_recorder = ScreenshotTaker()
#         self.audio_thread = None
#         self.screenshot_thread = None
 
#     def start_recording(self):
#         """Start recording with a 2-second timeout"""
#         try:
#             self.actually_start_recording()
#             self.echo("Recording started successfully")
#         except TimeoutError as e:
#             self.echo(f"Warning: {e}")
#             # Optionally clean up threads
#             self.stop_recording()
 
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
        self.audio_thread = None
        self.screenshot_thread = None
        self.recording_cycle = 0
        self.recording = False
        self.stop_event = threading.Event()

    def _load_config(self) -> RecordingConfig:
        """Loads the values in the config file to the config dataclass"""
        config = Config()
        config.reset_to_defaults()
        rec_config = config.load_specific_config("recording")
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        return RecordingConfig(
            fps=rec_config.get("fps"),
            max_duration=rec_config.get("max_duration"),
            recording_volume_lufs=rec_config.get("recording_volume_lufs"),
            ffmpeg_compression_factor=rec_config.get("image_compression_factor"),
            output_image_height_px=rec_config.get("output_image_height_px"),
            sample_rate=rec_config.get("sample_rate"),
            bitrate=rec_config.get("bitrate_kbps"),
            output_dir=Path(__file__).parent.parent / "temp_storage",
            timestamp=timestamp,
            screenshot_time=rec_config.get("screenshot_time", 0.8),
            wipe_media_folder=rec_config.get("wipe_media_folder", True)
        )

    def start_recording(self) -> None:
        self.echo("Beginning recording...")
        self.recording_cycle += 1
        self.recording = True
        self.stop_event.clear()

        now = datetime.now()
        self.start_time = time.time()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        self.config.timestamp = timestamp
        
        # Start audio thread first
        self.audio_thread = threading.Thread(
            target=self.audio_recorder.start,
            args=(self.stop_event,),  
            daemon=True
        )
        self.audio_thread.start()
        
        # Wait 0.5s before starting screenshot thread
        # This gives parecord time to acquire device before graphics libraries load
        time.sleep(0.5)
        
        self.screenshot_thread = threading.Thread(
            target=self.screen_recorder.start,
            args=(self.stop_event,),  # ALSO pass stop_event here!
            daemon=True
        )
        self.screenshot_thread.start()

    def stop_recording(self) -> tuple[Path, Path]:
        """Stop recording and clean up threads"""
        self.echo("Stopped!")
        end_time = time.time()
        self.stop_event.set()
        
        # Give threads time to stop gracefully
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=2)
        if self.screenshot_thread and self.screenshot_thread.is_alive():
            self.screenshot_thread.join(timeout=2)
        
    
        audio_file = None
        try:
            self.audio_recorder.stop()
            audio_file = self.audio_recorder.get_output_audio()
        except Exception as e:
            self.echo(f"Error stopping audio recorder: {e}")

        screenshot = None
        try:
            self.screen_recorder.stop()
            screenshot = self.screen_recorder.get_output_screenshot()
        except Exception as e:
            self.echo(f"Error stopping screen recorder: {e}")


        self.wipe_media_folder(audio_file, screenshot)


        self.recording = False
        self.echo("### Recording Done ###\n")
        return screenshot, audio_file


    def abort(self, silent: bool = False) -> bool:
        """Aborts recording and cleans up threads. Returns the recording state"""
        self.recording = False
        self.stop_event.set() 
        
        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join(timeout=1)
        if self.screenshot_thread and self.screenshot_thread.is_alive():
            self.screenshot_thread.join(timeout=1)
        
        print("ABORT")
        self.wipe_media_folder()
        return False

        
    def wipe_media_folder(self, *exclude: Path):
        """Wipes the media folder of all files, excluding given files. But only if set."""
        if self.config.wipe_media_folder:
            self.echo("Deleting media...")
            
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
                            self.echo(f"Error deleting {file_path}: {e}")
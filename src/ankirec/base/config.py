from .json_manager import JsonManager
from .helpers import singleton
from .constants import DEFAULT_SETTINGS
from typing import Optional
from pathlib import Path
from dataclasses import dataclass

@singleton
class Config(JsonManager):
    """Handles the application settings."""
 
    CONFIG_SECTIONS = {"general", "anki", "recording"}
 
    def __init__(self, filename: str = "config", defaults: Optional[dict] = None):
        # Set before super().__init__(), which reads self.filename
        self._filename = filename
        self._defaults = DEFAULT_SETTINGS if defaults is None else defaults
        super().__init__()
 
    @property
    def filename(self) -> str:
        return self._filename
 
    @property
    def defaults(self) -> dict:
        return self._defaults
 
    def load_section(self, section: str) -> dict:
        """Load the config of a specific section."""
        if section not in self.CONFIG_SECTIONS:
            raise KeyError(f"Unrecognised section: {section}")
        return self.load().get(section)
 
    # Old names, so existing callers keep working. Delete once they're migrated.
    # load_config = JsonManager.load
    # load_specific_config = load_section
    # get_config = JsonManager.get
    # save_config = JsonManager.save
    # update_config = JsonManager.save
    # get_single_config = JsonManager.get_value
    # set_single_config = JsonManager.set_value
    # config_exists = JsonManager.exists
    # delete_config_file = JsonManager.delete_file
 
    @property
    def config_path(self) -> Path:
        return self.file_path


@dataclass
class RecordingConfig:
    fps: int
    max_duration: int
    recording_volume_lufs: float
    ffmpeg_compression_factor: int
    output_image_height_px: int
    sample_rate: int
    bitrate: int
    output_dir: Path
    timestamp: str
    screenshot_time: float
    wipe_media_folder: bool

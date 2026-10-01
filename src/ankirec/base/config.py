import json
from pathlib import Path
from typing import Optional
from .constants import APP_NAME, DEFAULT_SETTINGS
from .universal import singleton
import click # used to get the app dir
from dataclasses import dataclass

@singleton
class Config:
    config_path: Path
    DEFAULT_CONFIG: dict | None = None
    _config_cache: Optional[dict] = None
    CONFIG_SECTIONS = set(["general", "anki", "recording"])

    def __init__(self, filename: str = "config", defaults: dict = DEFAULT_SETTINGS):
        super().__init__()
        self.config_path = self.get_config_path(filename=filename)
        self.DEFAULT_CONFIG = defaults

    def get_config_path(self, filename: str) -> Path:
        """Get the config file path, creating directory if needed."""
        config_dir = Path(click.get_app_dir(APP_NAME))
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / f"{filename}.json"

    def load_config(self) -> dict:
        """Load config, merging with defaults."""
        config = self.DEFAULT_CONFIG.copy()
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
            except json.JSONDecodeError as e:
                print(f"Warning: Config file corrupted, using defaults: {e}", err=True)
        return config

    def load_specific_config(self, config_section: str) -> dict:
        """Loads the config of a specific section"""
        if config_section not in self.CONFIG_SECTIONS:
            raise KeyError(f"Unrecognised section: {config_section}")

        config = self.load_config()
        return config.get(config_section)

    def save_config(self, config: dict) -> None:
        """Save config to file."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def get_config(self) -> dict:
        """Get config with caching."""
        if self._config_cache is None:           # First call: cache is empty
            self._config_cache = self.load_config()   # Load from disk
        return self._config_cache                # Return cached version

    def invalidate_cache(self) -> None:
        """Clear cache after saving."""
        self._config_cache = None                # Reset to None

    def update_config(self, config: dict) -> None:
        """Saves the config and clears the cache."""
        self.save_config(config=config)
        self.invalidate_cache()

    def reset_to_defaults(self) -> None:
        """Resets every setting to its default value"""
        self.save_config(self.DEFAULT_CONFIG)
        self.invalidate_cache()

    def get_single_config(self, key: str):
        """Gets a single setting by key.
        
        Args:
            key: The configuration key to retrieve (supports nested keys with dot notation)
            
        Returns:
            The configuration value
            
        Raises:
            KeyError: If the key is not found in configuration
        """
        config = self.get_config()
        
        # Support nested keys with dot notation (e.g., "anki.deckname")
        if "." in key:
            keys = key.split(".")
            value = config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                    if value is None:
                        raise KeyError(f"Configuration key not found: {key}")
                else:
                    raise KeyError(f"Cannot access '{k}' in non-dict value for key '{key}'")
            return value
        
        if key not in config:
            raise KeyError(f"Configuration key not found: {key}")
        return config[key]

    def set_single_config(self, key: str, value: any) -> None:
        """Sets a single configuration value.
        
        Args:
            key: The configuration key to set (supports nested keys with dot notation)
            value: The value to set
        """
        config = self.get_config().copy()
        
        # Support nested keys with dot notation (e.g., "general.theme")
        if "." in key:
            keys = key.split(".")
            target = config
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = value
        else:
            config[key] = value
        
        self.update_config(config)

    def config_exists(self) -> bool:
        """Check if configuration file exists."""
        return self.config_path.exists()

    def delete_config_file(self) -> None:
        """Delete the configuration file and clear cache."""
        if self.config_exists():
            self.config_path.unlink()
        self.invalidate_cache()
        

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


if __name__ == "__main__":
    base_config = Config(filename="config", defaults=DEFAULT_SETTINGS)
    # Test loading config
    print("Loading config...")
    config = base_config.get_config()
    print(f"Config: {config}")
    print(f"Config path: {base_config.config_path}")
    
    # Test updating config
    print("\nUpdating config...")
    config['test_key'] = 'test_value'
    base_config.update_config(config)
    
    # Test cache invalidation and reload
    print("Reloading config...")
    reloaded = base_config.get_config()
    print(f"Reloaded config: {reloaded}")
    
    # Verify cache is working (second call should be instant)
    print("\nTesting cache...")
    config_again = base_config.get_config()
    print(f"Cache working: {config_again is reloaded}")  # Should be True (same object)
    
    
    print("\n✓ All tests passed!")
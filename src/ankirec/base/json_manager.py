import copy
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional
 
import click
from click import get_app_dir
 
# Project imports - adjust to match your package layout:
from .constants import APP_NAME
 
 
class JsonManager(ABC):
    """Base class for anything persisted as a single JSON file in the app directory.
 
    Subclasses must provide `filename`; they may override `defaults`.
    """
 
    def __init__(self):
        super().__init__()
        self.file_path: Path = self.build_path(self.filename)
        self._cache: Optional[dict] = None
 
    # ---- What subclasses supply -------------------------------------------
 
    @property
    @abstractmethod
    def filename(self) -> str:
        """File name without the .json extension."""
 
    @property
    def defaults(self) -> dict:
        """Values used when the file is missing, corrupted, or lacks a key."""
        return {}
 
    # ---- Paths ------------------------------------------------------------
 
    @staticmethod
    def build_path(filename: str) -> Path:
        """Get the json file path, creating the app directory if needed."""
        app_dir = Path(get_app_dir(APP_NAME))
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / f"{filename}.json"
 
    def exists(self) -> bool:
        """Check if the json file exists."""
        return self.file_path.exists()
 
    def delete_file(self) -> None:
        """Delete the json file and clear the cache."""
        self.file_path.unlink(missing_ok=True)
        self.invalidate_cache()
 
    # ---- Reading ----------------------------------------------------------
 
    def load(self) -> dict:
        """Load from disk, merged over the defaults."""
        data = copy.deepcopy(self.defaults)
        if self.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self._deep_merge(data, json.load(f))
            except json.JSONDecodeError as e:
                click.echo(
                    f"Warning: {self.file_path.name} corrupted, using defaults: {e}",
                    err=True,
                )
        return data
 
    def get(self) -> dict:
        """Get the data, loading from disk only on the first call."""
        if self._cache is None:
            self._cache = self.load()
        return self._cache
 
    def get_value(self, key: str) -> Any:
        """Get a single value. Supports dot notation, e.g. "anki.deckname".
 
        Raises:
            KeyError: If the key is not found.
        """
        value = self.get()
        for k in key.split("."):
            if not isinstance(value, dict):
                raise KeyError(f"Cannot access '{k}' in non-dict value for key '{key}'")
            if k not in value:
                raise KeyError(f"Key not found: {key}")
            value = value[k]
        return value
 
    # ---- Writing ----------------------------------------------------------
 
    def save(self, data: dict) -> None:
        """Write to file and clear the cache."""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.invalidate_cache()
 
    def set_value(self, key: str, value: Any) -> None:
        """Set a single value. Supports dot notation, e.g. "general.theme"."""
        data = copy.deepcopy(self.get())
        *parents, last = key.split(".")
        target = data
        for k in parents:
            target = target.setdefault(k, {})
        target[last] = value
        self.save(data)
 
    def reset_to_defaults(self) -> None:
        """Reset everything to its default value."""
        self.save(copy.deepcopy(self.defaults))
 
    def invalidate_cache(self) -> None:
        """Force the next get() to re-read from disk."""
        self._cache = None
 
    # ---- Helpers ----------------------------------------------------------
 
    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Recursively merge `override` into `base`, in place."""
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                JsonManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

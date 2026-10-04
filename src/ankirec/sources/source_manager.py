"""Handles the sources feature, intended to help you organise anki cards created"""
from pathlib import Path
from dataclasses import dataclass

from ..base.json_manager import JsonManager

# APP_NAME = "ankirec"

@dataclass
class SourceData:
    name: str

class Sources(JsonManager):
    """Handles the sources feature, intended to help you organise anki cards created"""
    filename = "sources"
    defaults = {"selected": ""}
    def __init__(self):
        super().__init__()
 
    @staticmethod
    def get_selected_source_name() -> str:
        """Returns the name of the selected source"""
        return Sources().load().get("selected", "")

 
    @property
    def source_file(self) -> Path:
        return self.file_path
 
    @staticmethod
    def get_source_file() -> Path:
        return JsonManager.build_path(Sources.filename)


if __name__ == "__main__":
    # Sources.get_source_file()
    # sources = Sources()
    # sources.save_config({})
    print(Sources.get_selected_source_name())
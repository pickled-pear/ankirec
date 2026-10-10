import json
import requests
import socket
import re
from pathlib import Path
from dataclasses import dataclass
from datetime import date
from base64 import b64encode
from enum import Enum
from click import get_app_dir

from ..base.exceptions import AnkiConnectError
from ..base.config import Config
from ..base.mixin import VerboseMixin
from ..base.constants import SCRIPT_DIR, APP_NAME
from ..base.json_manager import JsonManager
from ..sources.source_manager import Sources

class FieldType(Enum):
    IMAGE = ("image", "screenshot")
    SENTENCE_AUDIO = ("sentenceaudio",)
    WORD = ("word", "term")
    WORD_AUDIO = ("wordaudio",)
    DATE = ("date",)
    SOURCE = ("source",)
    STANDARD = ()

    @classmethod
    def from_name(cls, name: str) -> "FieldType":
        def normalise(name: str) -> str:
            return re.sub(r"[\s_-]", "", name).lower()

        key = normalise(name)
        for member in cls:
            if key in member.value:
                return member
        return cls.STANDARD

@dataclass
class NoteField:
    name: str
    optional: bool
    special_feature: FieldType

@dataclass
class AnkiConfig:
    instant_send: bool
    auto_clear_folder: bool
    deckname: str
    cardmodel: str
    cardmodel_fields: list[NoteField]
    anki_profile: str
    ankiconnect_port: int
    ankiconnect_api_ver: int




class NotesJson(JsonManager):
    _filename = "notes"
    defaults = {}
    def __init__(self, filename: str = "notes"):
        super().__init__()
        self._filename = filename

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def notes_path(self) -> Path:
        return self.file_path


class SharedValues(VerboseMixin):
    # notes_json_file = SCRIPT_DIR / "anki" / "notes.json"
    notes_json_filename = "notes"
    notes_json_file = Path(get_app_dir(APP_NAME)) / f"{notes_json_filename}.json"
    notes_json_file.parent.mkdir(parents=True, exist_ok=True)
    notes_json_manager = NotesJson()
    def __init__(self):
        super().__init__()



class AnkiconnectActions(SharedValues):
    """Contains various actions associated with using the ankiconnect api"""
    API_VERSION: int
    port: int

    def __init__(self, port, api_ver):
        super().__init__()
        self.set_port(port=port)
        self.API_VERSION = api_ver
        # self.notes_json_file = Path("notes.json")
        # self._moved_media_filename = None

    def _invoke(self, action, **params):
        """Sends an action request to AnkiConnect and returns the result.
        
        Args:
            action: The AnkiConnect action name (e.g., 'deckNames', 'addNote')
            **params: Additional parameters for the action
            
        Returns:
            The result from AnkiConnect
            
        Raises:
            AnkiConnectError: If the API returns an error or connection fails
        """
        payload = {
            "action": action,
            "version": self.API_VERSION,
            "params": params
        }
        
        try:
            response = requests.post(self.ANKI_CONNECT_URL, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.ConnectionError as e:
            raise AnkiConnectError(f"Failed to connect to AnkiConnect: {e}")
        except requests.exceptions.Timeout:
            raise AnkiConnectError("AnkiConnect request timed out")
        except requests.exceptions.HTTPError as e:
            raise AnkiConnectError(f"HTTP error: {e.response.status_code}")
        except json.JSONDecodeError as e:
            raise AnkiConnectError(f"Invalid JSON response: {e}")
        
        if result.get("error"):
            raise AnkiConnectError(f"AnkiConnect error: {result['error']}")
        
        return result

    def send_notes_to_anki(self) -> None:
        """Adds the contents of notes.json to anki itself"""
        if is_port_open(self.port):
            # with open(self.notes_json_file, "r") as f:
            #     notes_json = json.load(f)
            notes_json = self.notes_json_manager.load()
            notes_array = notes_json.get("notes", [])

            if not notes_json:
                self.warning("No notes found")
                return

            for note in notes_array:
                note.setdefault("options", {
                    "allowDuplicate": True,
                    "duplicateScope": "deck"
                })
            # uses api to send the notes
            result = self._invoke("addNotes", notes=notes_array)
            if not result.get("error"):
                self.wipe_json()
                
            return result

        else:
            self.warning("Anki is not running!")

    def set_port(self, port: int):
        self.port = port
        self.ANKI_CONNECT_URL = f"http://localhost:{self.port}"

    def wipe_json(self):
        # with open(self.notes_json_file, "w") as file:
        #     json.dump([], file)
        self.notes_json_manager.save({})

        self.info("Note json cleared")


    def move_file_to_ank_media(self, filename: str, filepath: Path):
        """Moves the given file to anki"""
        try:
            with open(filepath, 'rb') as f:
                media_data = b64encode(f.read()).decode('utf-8')
        except FileNotFoundError:
            raise AnkiConnectError(f"File not found: {filepath}")
        except IOError as e:
            raise AnkiConnectError(f"Failed to read file {filepath}: {e}")
        
        result = self._invoke("storeMediaFile", filename=filename, data=media_data)
        self.debug(f"Stored media file: {filename}")
        # self._moved_media_filename = str(filepath)
        return result
        

def is_port_open(port: int, host: str = 'localhost', timeout: float = 1.0) -> bool:
    """
    Check if a port is open and listening on the local machine.
    
    Args:
        port: The port number to check (0-65535)
        host: The host to check (default: 'localhost')
        timeout: Socket timeout in seconds (default: 1.0)
    
    Returns:
        True if the port is open, False otherwise
    
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()



class AnkiManager(SharedValues):
    def __init__(self, screenshot: Path, audio: Path):
        super().__init__()
        self.screenshot = screenshot
        self.audio = audio
        self.config = self.load_config()
        self.actions = AnkiconnectActions(self.config.ankiconnect_port, self.config.ankiconnect_api_ver)

    def load_config(self) -> AnkiConfig:
        """Loads the config json into the AnkiConfig object"""
        config = Config()
        anki_config = config.load_section("anki")
        if not anki_config.get("deckname") or not anki_config.get("cardmodel"):
            raise ValueError("Deckname and Cardmodel must be provided")
        
        # cardmodel_fields=anki_config.get("cardmodel_fields", [])
        # if not "Image" in cardmodel_fields:
        #     raise ValueError("Your cardmodel must include a field called Image")
        # if not "SentenceAudio" in cardmodel_fields:
        #     raise ValueError("Your cardmodel must include a field called SentenceAudio")

        cardmodel_fields = self._load_fields(anki_config.get("cardmodel_fields", []))
        
        return AnkiConfig(
            instant_send=anki_config.get("instant_send", False),
            auto_clear_folder=anki_config.get("auto_clear_folder", True),
            deckname=anki_config.get("deckname", ""),
            cardmodel= anki_config.get("cardmodel", ""),
            cardmodel_fields=cardmodel_fields,
            anki_profile=anki_config.get("anki_profile", "User1"),
            ankiconnect_port=anki_config.get("ankiconnect_port", 8765),
            ankiconnect_api_ver=anki_config.get("ankiconnect_api_ver", 6)
        )



    def _load_fields(self, fields: list[str]) -> list[NoteField]:
        """Takes the list of fields and categorises them based on function"""
        note_fields = []
        for entry in fields:
            name, *flags = (part.strip() for part in entry.split(":"))

            optional = False
            field_type = None
            for flag in flags:
                if flag.lower() == "optional":
                    optional = True
                    continue
                flag_type = FieldType.from_name(flag)
                if flag_type is FieldType.STANDARD:
                    raise ValueError(f"Unknown flag '{flag}' on field '{name}'")
                if field_type is not None:
                    raise ValueError(f"Field '{name}' has more than one type flag")
                field_type = flag_type

            if field_type is None:
                field_type = FieldType.from_name(name)  # fall back to the name

            note_fields.append(NoteField(name, optional=optional, special_feature=field_type))

        return note_fields



    def move_media_to_anki(self):
        """Moves both the screenshot and audio file to anki (if they exist)"""
        if self.screenshot:
            result = self.actions.move_file_to_ank_media(self.screenshot.name, self.screenshot)

            if not result.get("error"):
                self.debug("Screenshot moved")

        if self.audio:
            result = self.actions.move_file_to_ank_media(self.audio.name, self.audio)
            if not result.get("error"):
                self.debug("Audio moved")

    

    def add_notes_to_json(
        self,
        fields: dict | None = None,
        **kwargs,
    ):
        """Adds the given data as a note to notes.json. Sends them to anki if setting enabled"""

        self.config = self.load_config() # reloads the config in case there were any changes
        source = Sources.get_selected_source_name()

        # Media fields, only included if the media actually exists
        note_fields = {}
        if self.screenshot.name:
            note_fields["Image"] = f'<img src="{self.screenshot.name}">'
        if self.audio.name:
            note_fields["SentenceAudio"] = f"[sound:{self.audio.name}]"

        # Caller-supplied fields: dict first, then keyword args on top
        note_fields.update(fields or {})
        note_fields.update(kwargs)

        note_fields["Date"] = date.today().isoformat()
        note_fields["Source"] = source

        tags = ["ankirec", source]
        tags = [tag for tag in tags if tag] # removes empty tags

        note_json = {
            "deckName": self.config.deckname,
            "modelName": self.config.cardmodel,
            "fields": note_fields,
            "tags": tags
        }

        # Read existing notes, tolerating a missing or corrupt file
        try:
            # with open(self.notes_json_file, "r", encoding="utf-8") as file:
            #     existing_notes = json.load(file)
            existing_notes = self.notes_json_manager.load()
        except (FileNotFoundError, json.JSONDecodeError):
            self.error("No existing notes found. Using empty array")
            existing_notes = {}

        notes_array = existing_notes.get("notes", [])

        notes_array.append(note_json)
        existing_notes["notes"] = notes_array
        self.debug(f"{len(existing_notes)} notes")

        # adds to the json
        # with open(self.notes_json_file, "w", encoding="utf-8") as file:
        #     json.dump(existing_notes, file, indent=4, ensure_ascii=False)
        self.notes_json_manager.save(existing_notes)

        if self.config.instant_send:
            self.info("Sending notes...")
            result = self.actions.send_notes_to_anki() or {}
            error = result.get("error")
            if error:
                self.error(f"Error: {error}")
            else:
                self.info("Sent notes!")

        return note_json


if __name__ == "__main__":
    print(is_port_open(8765))
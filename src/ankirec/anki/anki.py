import json
import requests
import socket
import re
import shutil
from pathlib import Path
from dataclasses import dataclass
from datetime import date, datetime
from base64 import b64encode
from enum import Enum
from click import get_app_dir

from ..base.exceptions import AnkiConnectError
from ..base.config import Config
from ..base.mixin import VerboseMixin
from ..base.constants import APP_NAME
from ..base.json_manager import JsonManager
from ..sources.source_manager import Sources
from .tts import TtsController

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
    field_type: FieldType

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
    tts_voices: list[str]




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

        self.anki_open = False
        self.anki_media_dir: Path | None = None

    def update_anki_open(self) -> None:
        self.anki_open = is_port_open(self.port)


    def _invoke(self, action, **params) -> dict:
        """Sends an action request to AnkiConnect and returns the result.
        
        Args:
            action: The AnkiConnect action name (e.g., 'deckNames', 'addNote')
            **params: Additional parameters for the action
            
        Returns:
            The result from AnkiConnect
            
        Raises:
            AnkiConnectError: If the API returns an error or connection fails
        """
        if is_port_open(self.port):
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
        else:
            self.warning("Anki port not detected. Nothing done")
            return {
                "result": None,
                "error": "Anki was closed"
            }

    def send_notes_to_anki(self):
        """Adds the contents of notes.json and the folder media to anki itself"""
        if self.anki_open:

            # get and send the notes
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

            # now loop through the media dir and do the same
            media_folder = Path(get_app_dir(APP_NAME)) / "media"
            media_folder.mkdir(parents=True, exist_ok=True)

            for file in media_folder.iterdir():
                if file.is_file():
                    self.move_file_to_anki_media(file.name, file)
                    file.unlink()



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


    def get_media_dir(self) -> Path | None:
        """Retrieves the local media dir"""
        result = self._invoke(action="getMediaDirPath")
        return Path(result.get("result")) if result else None


    def move_file_to_anki_media(self, filename: str, filepath: Path):
        """Moves the given file to Anki, or buffers it locally if Anki isn't running."""
        try:
            with open(filepath, 'rb') as f:
                raw_data = f.read()
        except FileNotFoundError:
            raise AnkiConnectError(f"File not found: {filepath}")
        except IOError as e:
            raise AnkiConnectError(f"Failed to read file {filepath}: {e}")

        safe_name = Path(filename).name

        # use ankiconnect to move if anki open, otherwise move to the folder media in the app dir
        if self.anki_open:
            if not self.anki_media_dir:
                self.anki_media_dir = self.get_media_dir()

            # media_data = b64encode(raw_data).decode('utf-8')
            # result = self._invoke("storeMediaFile", filename=filename, data=media_data)
            destination = self.anki_media_dir / safe_name
            shutil.copy(filepath, destination)
            result = {
                "result": "moved to anki",
                "error": None
            }
            self.debug(f"Stored media file: {filename} in anki")
        else:
            media_folder = Path(get_app_dir(APP_NAME)) / "media"
            media_folder.mkdir(parents=True, exist_ok=True)

            # write the media to the folder
            destination = media_folder / Path(filename).name
            try:
                destination.write_bytes(raw_data)
            except OSError as e:
                raise AnkiConnectError(f"Failed to buffer media file {filename}: {e}")

            result = {
                "result": "buffered media",
                "error": None
            }
            self.debug(f"Stored media file: {filename} in the buffer folder ({destination})")

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
        self.card_fields = self.config.cardmodel_fields # for ease of use
        self.actions = AnkiconnectActions(self.config.ankiconnect_port, self.config.ankiconnect_api_ver)

    def load_config(self) -> AnkiConfig:
        """Loads the config json into the AnkiConfig object"""
        config = Config()
        anki_config = config.load_section("anki")
        if not anki_config.get("deckname") or not anki_config.get("cardmodel"):
            raise ValueError("Deckname and Cardmodel must be provided")

        cardmodel_fields = self._load_fields(anki_config.get("cardmodel_fields", []))
        
        return AnkiConfig(
            instant_send=anki_config.get("instant_send", False),
            auto_clear_folder=anki_config.get("auto_clear_folder", True),
            deckname=anki_config.get("deckname", ""),
            cardmodel= anki_config.get("cardmodel", ""),
            cardmodel_fields=cardmodel_fields,
            anki_profile=anki_config.get("anki_profile", "User1"),
            ankiconnect_port=anki_config.get("ankiconnect_port", 8765),
            ankiconnect_api_ver=anki_config.get("ankiconnect_api_ver", 6),
            tts_voices=anki_config.get("tts_voices", [])
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

            note_fields.append(NoteField(name, optional=optional, field_type=field_type))

        return note_fields


    def get_manual_fields(self, manual: bool=True) -> list[NoteField]:
        """Returns a list of all fields requiring manual input by default. Gets all non-manual is specified"""
        manual_field_types = {FieldType.STANDARD, FieldType.WORD}
        if manual:
            return [field for field in self.card_fields if field.field_type in manual_field_types]
        else:
            return [field for field in self.card_fields if field.field_type not in manual_field_types]

    def check_field_type_exists(self, field_type: FieldType) -> bool:
        """Checks the specified field type exists in the given field list"""
        special_fields = self.get_manual_fields(manual=False)
        special_field_types = [value.field_type for value in special_fields]
        return field_type in special_field_types


    def move_media_to_anki(self, word_tts: Path = None, media_dir: Path | None = None):
        """Moves both the screenshot and audio file to anki (if they exist)"""
        # anki_open = is_port_open(self.actions.port)
        self.actions.update_anki_open()
        if media_dir:
            self.actions.anki_media_dir = media_dir
            
        if self.screenshot:
            result = self.actions.move_file_to_anki_media(self.screenshot.name, self.screenshot)

            if not result.get("error"):
                self.debug("Screenshot moved")

        if self.audio:
            result = self.actions.move_file_to_anki_media(self.audio.name, self.audio)
            if not result.get("error"):
                self.debug("Audio moved")

        if word_tts:
            result = self.actions.move_file_to_anki_media(word_tts.name, word_tts)
            if not result.get("error"):
                self.debug("Word TTS move")

    @classmethod
    def _find_field_name(cls, fields: list[NoteField],  field_type: FieldType) -> str:
        """Returns the name of the field of the desired field type, or an empty string if it is not found"""
        for field in fields:
            if field.field_type == field_type:
                return field.name
        return ""

    def create_tts(self, text: str) -> tuple[Path, Path]:
        voices = self.config.tts_voices
        if voices:
            # steal the filename from self.audio, since that should exist
            # if not use the date today
            if self.audio:
                partial_filename = self.audio.stem
            else:
                partial_filename = datetime.now().strftime("%Y%m%d_%H%M%S")

            filename = f"{partial_filename}_tts"
            tts = TtsController(voices=voices)
            self.debug(f"Creating TTS on text {text}")
            mp3, tts_file = tts.create_tts(text=text, filename=filename)
            self.debug("Saved tts")
            return mp3, tts_file


    def add_notes_to_json(
        self,
        fields: dict | None = None,
        **kwargs,
    ):
        """Adds the given data as a note to notes.json. Sends them to anki if setting enabled"""

        def _set_field(note_fields: dict, field_type: FieldType, value: str) -> None:
            """Sets the given speical field type to the given value. Does nothing if field not found"""
            field_name = self._find_field_name(self.card_fields, field_type)
            if field_name:
                note_fields[field_name] = value

        self.actions.update_anki_open()
        self.config = self.load_config() # reloads the config in case there were any changes
        source = Sources.get_selected_source_name()
        note_fields = {}

        # attempt to set special fields with special values if they exist
        if self.audio.name:
            _set_field(note_fields, FieldType.SENTENCE_AUDIO, f"[sound:{self.audio.name}]")

        if self.screenshot.name:
            _set_field(note_fields, FieldType.IMAGE, f'<img src="{self.screenshot.name}">')

        _set_field(note_fields, FieldType.DATE, date.today().isoformat())
        _set_field(note_fields, FieldType.SOURCE, source)

        # need some way to get the word field's name and tts for it

        # Caller-supplied fields: dict first, then keyword args on top
        note_fields.update(fields or {})
        note_fields.update(kwargs)


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
            existing_notes = self.notes_json_manager.load()
        except (FileNotFoundError, json.JSONDecodeError):
            self.error("No existing notes found. Using empty array")
            existing_notes = {}

        notes_array = existing_notes.get("notes", [])

        notes_array.append(note_json)
        existing_notes["notes"] = notes_array
        self.debug(f"{len(existing_notes)} notes")

        # adds to the json
        self.notes_json_manager.save(existing_notes)

        if self.config.instant_send and self.actions.anki_open:
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
import json
import requests
import socket
from pathlib import Path
from dataclasses import dataclass
from base64 import b64encode

from ..base.exceptions import AnkiConnectError
from ..base.config import Config
from ..base.mixin import VerboseMixin

@dataclass
class AnkiConfig:
    instant_send: bool
    auto_clear_folder: bool
    deckname: str
    cardmodel: str
    anki_profile: str
    ankiconnect_port: int
    ankiconnect_api_ver: int


class SharedValues(VerboseMixin):
    notes_json_file = Path("src")  / "ankirec" / "anki" / "notes.json"
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
            with open(self.notes_json_file, "r") as f:
                notes_json = json.load(f)

            if not notes_json:
                self.warning("No notes found")
                return

            for note in notes_json:
                note.setdefault("options", {
                    "allowDuplicate": True,
                    "duplicateScope": "deck"
                })
            # uses api to send the notes
            result = self._invoke("addNotes", notes=notes_json)
            if not result.get("error"):
                self.wipe_json()
                
            return result

        else:
            self.warning("Anki is not running!")

    def set_port(self, port: int):
        self.port = port
        self.ANKI_CONNECT_URL = f"http://localhost:{self.port}"

    def wipe_json(self):
        with open(self.notes_json_file, "w") as file:
            json.dump([], file)

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
        

    ### OBSOLETE ###
    # def write_to_anki(self):
    #     """Reads the contents of the cardUpdates json and sends everything in it to anki"""


    #     with open(self.notes_json_file, "r") as f:
    #         notes_json = json.load(f)

    #     if not notes_json:
    #         print("[orange]No cards to add")
    #         return

    #     for note in notes_json:
    #         note.setdefault("options", {
    #             "allowDuplicate": True,
    #             "duplicateScope": "deck"
    #         })

    #     try:
    #         result = self.send_to_anki(notes=notes_json)
    #     except Exception as e:
    #         print(f"[red]Failed to connect to Anki: {e}")
    #         return


    #     self.wipe_json()
    #     print("[#18f900]Sent to anki")
            

def is_port_open(port: int, host: str = 'localhost', timeout: float = 1.0) -> bool:
    """
    Check if a port is open and listening on the local machine.
    
    Args:
        port: The port number to check (0-65535)
        host: The host to check (default: 'localhost')
        timeout: Socket timeout in seconds (default: 1.0)
    
    Returns:
        True if the port is open, False otherwise
    
    Example:
        >>> is_port_open(8080)
        True
        >>> is_port_open(9999)
        False
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
        config = Config()
        anki_config = config.load_specific_config("anki")
        return AnkiConfig(
            instant_send=anki_config.get("instant_send"),
            auto_clear_folder=anki_config.get("auto_clear_folder"),
            deckname=anki_config.get("deckname"),
            cardmodel= anki_config.get("cardmodel"),
            anki_profile=anki_config.get("anki_profile"),
            ankiconnect_port=anki_config.get("ankiconnect_port"),
            ankiconnect_api_ver=anki_config.get("ankiconnect_api_ver")
        )


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

    

    def add_notes_to_json(self, fields: dict = {}):
        """Adds the given data as a note to notes.json. Sends them to anki if setting enabled"""

        screenshot_str = f"""<img src="{self.screenshot.name}">""" if self.screenshot.name else ""
        audio = self.audio.name if self.audio.name else ""

        # TEMP
        tagarr = []
        note_json = {
                "deckName":"Core::Mining::Central",
                "modelName":"MiningCard",
                "fields":{
                    "Word":"tempword",
                    "Image":screenshot_str,
                    "SentenceAudio":f"[sound:{audio}]",
                },
                "tags":tagarr
        }

        # read existing notes
        with open(self.notes_json_file, "r") as file:
            existing_notes = json.load(file)

        existing_notes.append(note_json)
        self.debug(f"{len(existing_notes)} notes")

        # adds to the json
        with open(self.notes_json_file, "w") as file:
            json.dump(existing_notes, file, indent=4, ensure_ascii=False)

        self.debug(f"instant_send: {True}")
        if self.config.instant_send:
            self.info("Sending notes...")
            result = self.actions.send_notes_to_anki()
            if not result.get("error"):
                self.info("Sent notes!")
            else:
                self.error(f"Error: {result.get("error")}")
                


if __name__ == "__main__":
    print(is_port_open(8765))
from enum import Enum
import platform
from pathlib import Path

class UserPlatform(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MAC = "mac"
    UNRECOGNISED = "unrecognised"

def _get_platform() -> UserPlatform:
    platformstring = platform.system()
    platformstring = platformstring.strip().lower()
    LOOKUP = {
        "windows": UserPlatform.WINDOWS,
        "linux": UserPlatform.LINUX,
        "darwin": UserPlatform.MAC,
    }
    found_platform = LOOKUP.get(platformstring, UserPlatform.UNRECOGNISED)
    return found_platform

PLATFORM = _get_platform()
APP_NAME = "ankirec"
SCRIPT_DIR = Path(__file__).parent.parent

DEFAULT_SETTINGS = {
    # CHECK FOR UNUSED SETTINGS ME
    "general": {
        "developer": False,
        "logging_level": 1,  # 1 - 5
        "sfx_volume": 0.5,
        # blah blah blah git gists
        "sources_sync": False
    },
    "anki": {
        "instant_send": True,
        "auto_clear_folder": True,
        "deckname": "",
        "cardmodel": "",
        # "cardmodel_fields": ["Image", "Date", "Source", "SentenceAudio", "WordAudio"],
        "cardmodel_fields": ["Picture:image", "Clip:sentenceaudio", "Expression:word", "ExpressionAudio:wordaudio", "Meaning", "Notes:optional"],
        "anki_profile":"User1",
        "ankiconnect_port":8765,
        "ankiconnect_api_ver": 6,
        "tts_voices": [],
    },
    "recording": {
        "record_screen": True,
        "fps": 15,
        "max_duration": 30,
        "recording_volume_lufs": -23,
        "blocksize":4096,   #higher on slow computers
        "image_compression_factor": 5,
        "output_image_height_px": 540,
        "sample_rate": 48000,
        "bitrate_kbps": 48,
        "screenshot_time": 0.8, # how long in to take the screenshot from
        "wipe_media_folder": True
    }
}


if __name__ == "__main__":
    print(PLATFORM)
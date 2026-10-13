from ..base.mixin import VerboseMixin
from ..recording.full_recorder import FullRecorder
from ..anki.anki import AnkiManager, FieldType
from ..base.context import verbose_mode
from ..fields_input_api.input_api import InputDialog, DialogCancelled, Field
from ..sources.source_manager import Sources
from ..audio.audioplayer import AudioPlayerController
from ..base.config import Config

import time
import threading
from pathlib import Path

class FlashcardManager(VerboseMixin):
    """Manages all aspects of assembling anki flashcard.

    Recording state lives only in FullRecorder (a singleton shared with the
    abort listener), so this class never tracks or toggles it itself.
    """

    def __init__(self):
        super().__init__()
        self.audio_controller = AudioPlayerController(volume=Config().load_section("general").get("sfx_volume", 0.5))
        self.combined_recorder = FullRecorder()
        self.persistent_verbose = self.verbose
        self.dialog = InputDialog()
        self.retaken_screenshot = None


    def _start_abort_timer(self, recording_cycle: int, timeout_seconds: int) -> None:
        """
        Sleep on a new thread and abort if the same recording is still running after timeout.
        """
        def _abort_if_unchanged():
            time.sleep(timeout_seconds)
            # recording_cycle changes on every start/stop, so this only aborts the
            # recording that started this timer. abort() is a no-op if it already ended.
            if recording_cycle == self.combined_recorder.recording_cycle:
                self.combined_recorder.abort()

        thread = threading.Thread(target=_abort_if_unchanged, daemon=True)
        thread.start()

    def retake_image(self) -> Path:
        """Retakes the image and returns the new one"""
        self.info("Retaking in 1s")
        time.sleep(1)
        new_screenshot = self.combined_recorder.screen_recorder.take_screenshot()
        self.retaken_screenshot = new_screenshot
        return new_screenshot


    def on_press(self):
        """The core listener callback. Decides whether the system is recording, and responds accordingly"""
        if not self.combined_recorder.recording:
            # if not recording, start recording
            self.combined_recorder.start_recording()
            current_cycle = self.combined_recorder.recording_cycle
            self._start_abort_timer(recording_cycle=current_cycle, timeout_seconds=30)
            return

        screenshot, audio = self.combined_recorder.stop_recording()
        if screenshot is None or audio is None:
            # An abort (key or timeout) got there first, or a recorder failed
            self.info("No recording to save (aborted or failed).")
            return

        self.audio_controller.play_sfx("stop_recording.mp3")

        # Give the system time to recover from COM object cleanup
        # This prevents UI lag when the dialog opens

        # but try removing on windows later
        time.sleep(0.2)

        verbose_mode.set(self.persistent_verbose)

        ankimanager = AnkiManager(screenshot=screenshot, audio=audio)
        manual_fields = ankimanager.get_manual_fields()
        display_fields = [Field(label=field.name, optional=field.optional) for field in manual_fields]


        fields = {}
        try:
            fields = self.dialog.ask(
                fields=display_fields,
                title="Add Note",
                image_path=screenshot,
                audio_path=audio,
                retake_callback=self.retake_image

            )
            if not fields:
                self.info("Cancelled!")
                return

        except DialogCancelled:
            self.info("Window closed, aborting...")
            return

        if self.retaken_screenshot:
            ankimanager.screenshot = self.retaken_screenshot
            self.retaken_screenshot = None

        # renames the media before moving
        selected_source = Sources.get_selected_source_name()
        normalised_source = Sources.normalise_source_name(selected_source)
        ankimanager.screenshot = ankimanager.screenshot.rename(ankimanager.screenshot.with_stem(f"{normalised_source}_{ankimanager.screenshot.stem}"))
        ankimanager.audio = ankimanager.audio.rename(ankimanager.audio.with_stem(f"{normalised_source}_{ankimanager.audio.stem}"))

        # re-dict fields
        fields = dict(fields)

        # if there is a word field, create tts for it.
        # the tts voice is randomly chosen from the list
        word_field = word_tts_field = tts_file = None
        for field in manual_fields:
            if field.field_type == FieldType.WORD:
                word_field = field
                word_tts_field = AnkiManager._find_field_name(ankimanager.card_fields, FieldType.WORD_AUDIO)
                break

        if word_tts_field:
            text = fields.get(word_field.name, "")
            tts_file = ankimanager.create_tts(text=text)
            if tts_file:
                fields[word_tts_field] = f"[sound:{tts_file.name}]"

        self.info("Moving media...")
        ankimanager.move_media_to_anki(word_tts=tts_file)

        self.info("Adding note...")
        ankimanager.add_notes_to_json(fields=fields)


        self.combined_recorder.wipe_media_folder()
        self.info("Done! Ready to add next note.")
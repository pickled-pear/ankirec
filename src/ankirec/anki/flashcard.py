from ..base.mixin import VerboseMixin
from ..recording.full_recorder import FullRecorder
from ..anki.anki import AnkiManager
from ..base.context import verbose_mode
from .fields_input_api.input_api import ask_input, Field, DialogCancelled, InputDialog

import time
import threading
from pathlib import Path

# @dataclass
# class FlashcardData:


class FlashcardManager(VerboseMixin):
    """Manages all aspects of assembling anki flashcard"""
    recording: bool = False

    def __init__(self):
        super().__init__()
        self.combined_recorder = FullRecorder()
        self.persistent_verbose = self.verbose
        self.dialog = InputDialog()
        self.retaken_screenshot = None

    def _start_abort_timer(self, recording_cycle: int, timeout_seconds: int) -> None:
        """
        Sleep on a new thread and abort if still running after timeout.
        """
        def _abort_if_unchanged():
            time.sleep(timeout_seconds)
            if recording_cycle == self.combined_recorder.recording_cycle and self.recording:
                self.recording = self.combined_recorder.abort()
        
        thread = threading.Thread(target=_abort_if_unchanged, daemon=True)
        thread.start()

    def retake_image(self) -> Path:
        """Retakes the image and returns the new one"""
        print("Retaking in 1s")
        time.sleep(1)
        new_screenshot = self.combined_recorder.screen_recorder.take_screenshot()
        self.retaken_screenshot = new_screenshot
        return new_screenshot

    def on_press(self):
        """The core listener callback. Decides whether the system is recording, and responds accordingly"""
        if not self.recording:
            # if not recording, start recording
            self.combined_recorder.start_recording()
            current_cycle = self.combined_recorder.recording_cycle
            self._start_abort_timer(recording_cycle=current_cycle, timeout_seconds=30)

        else:
            screenshot, audio = self.combined_recorder.stop_recording()
            verbose_mode.set(self.persistent_verbose)

            ankimanager = AnkiManager(screenshot=screenshot, audio=audio)

            try:
                fields = self.dialog.ask(
                    fields=[
                        Field("Word"),
                        Field("Reading"),
                        Field("Definition"),
                        Field("Sentence", optional=True),
                        Field("Notes", optional=True)
                    ],
                    title="Add Note",
                    image_path=screenshot,
                    audio_path=audio,
                    retake_callback=self.retake_image
                    
                )
                if not fields:
                    self.info("Cancelled!")
                    self.recording = not self.recording
                    return

            except DialogCancelled:
                self.info("Window closed, aborting...")
                self.recording = not self.recording
                return

            if self.retaken_screenshot:
                ankimanager.screenshot = self.retaken_screenshot
                self.retaken_screenshot = None

            self.info("Moving media...")
            ankimanager.move_media_to_anki()

            self.info("Adding note...")
            ankimanager.add_notes_to_json()


            self.combined_recorder.wipe_media_folder()
            self.info("Done! Ready to add next note.")

            

        self.recording = not self.recording
    

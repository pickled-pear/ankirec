from dataclasses import dataclass

from ..base.mixin import VerboseMixin
from ..recording.full_recorder import FullRecorder
from ..anki.anki import AnkiManager
from ..base.context import verbose_mode

import time
import threading

# @dataclass
# class FlashcardData:


class FlashcardManager(VerboseMixin):
    """Manages all aspects of assembling anki flashcard"""
    recording: bool = False

    def __init__(self):
        super().__init__()
        self.combined_recorder = FullRecorder()
        self.persistent_verbose = self.verbose

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

            self.info("Moving media...")
            ankimanager.move_media_to_anki()

            self.info("Adding note...")
            ankimanager.add_notes_to_json()

            self.info("Done! Ready to add next note.")

            

        self.recording = not self.recording
    

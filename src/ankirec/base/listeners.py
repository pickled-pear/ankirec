from abc import ABC, abstractmethod
from pynput import keyboard
import threading

from ..anki.flashcard import FlashcardManager
from ..recording.full_recorder import FullRecorder
from ..base.mixin import VerboseMixin

class KeyListener(ABC, VerboseMixin):
    """Base class for restartable keyboard listeners."""
    target_keys: set[keyboard.Key, keyboard.KeyCode]

    def __init__(self) -> None:
        super().__init__()
        self._listener: keyboard.Listener | None = None
        self._stop_requested = False
        
    @abstractmethod
    def on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> bool | None:
        """Called on key press. Return False to stop listening."""

    def on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> bool | None:
        """Called on key release. Does nothing by default."""
        return None

    @property
    def is_listening(self) -> bool:
        return self._listener is not None and self._listener.running

    def start_listening(self) -> None:
        """Start listening (creates a new thread each time)."""
        if not self.is_listening:
            self._stop_requested = False
            self._listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release,
            )
            self._listener.start()

    def stop_listening(self) -> None:
        """Stop listening."""
        self._stop_requested = True
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def join(self) -> None:
        """Block until the listener stops."""
        if self._listener is not None:
            self._listener.join()


class ListenerManager(VerboseMixin):
    """Manages multiple keyboard listeners running concurrently."""
    
    def __init__(self) -> None:
        super().__init__()
        self.listeners: list[KeyListener] = []
        self._stop_event = threading.Event()
    
    def add_listener(self, listener: KeyListener) -> KeyListener:
        """Add a listener and start it."""
        listener.start_listening()
        self.listeners.append(listener)
        return listener
    
    def stop_all(self) -> None:
        """Stop all listeners gracefully."""
        for listener in self.listeners:
            listener.stop_listening()
        self._stop_event.set()  # Signals keep_alive() to exit
    
    def stop_specific_listener(self, listener: KeyListener) -> None:
        """Stops a specific listener."""
        listener.stop_listening()
        if listener in self.listeners:
            self.listeners.remove(listener)
    
    def keep_alive(self) -> None:
        """Keep the main thread alive until interrupted."""
        try:
            # Use a timeout so the main thread periodically wakes up
            # This helps catch KeyboardInterrupt on Windows more reliably
            while not self._stop_event.is_set():
                self._stop_event.wait(timeout=0.1)
        except KeyboardInterrupt:
            self.info("\nShutting down...")
            self.stop_all()



class RecordListener(KeyListener):
    """Class that listens to trigger recording"""
    target_keys = set([keyboard.Key.alt_r, keyboard.Key.alt_gr])
    flashcard: FlashcardManager

    def __init__(self,):
        super().__init__()
        self.flashcard = FlashcardManager()
        self.info("Listening! Press altgr to start")

    def map_to_key(self, keyvk: int) -> keyboard.Key | None:
        """right alt is non-consistent across platforms so map it if does not work"""
        try:
            if keyvk == 65027: # right alt on linux
                return keyboard.Key.alt_r
            elif keyvk == 165: # windows
                return keyboard.Key.alt_r
            else:
                return None
        except AttributeError:
            # if this calls it wasnt alt anyway, return null
            return None

    def on_press(self, key):
        # Check if shutdown was requested
        if self._stop_requested:
            return False
        
        if not isinstance(key, keyboard.Key):
            key = self.map_to_key(key.vk)

        if key in self.target_keys:
            # Wrap flashcard.on_press() in a try-except to handle interrupts
            try:
                self.flashcard.on_press()
            except KeyboardInterrupt:
                self.info("Recording interrupted")
                return False
        
        return None

class AbortRecordListener(KeyListener):
    """Class that listens to abort recording"""
    target_keys = set([keyboard.KeyCode.from_char("q")])
    recorder: FullRecorder

    def __init__(self):
        super().__init__()
        self.recorder = FullRecorder()

    def on_press(self, key):
        # Check if shutdown was requested
        if self._stop_requested:
            return False
        
        if key in self.target_keys:
            try:
                self.recorder.abort()
                self.debug(self.recorder.recording_cycle)
            except KeyboardInterrupt:
                self.info("Abort interrupted")
                return False
        
        return None


class Parrot(KeyListener):
    """Prints the key that was pressed"""
    def on_press(self, key):
        if self._stop_requested:
            return False
        
        print(f"""{key} was pressed\n{key.vk}""")
        if not isinstance(key, keyboard.Key):
            # print("NOT A KEY")
            pass
        
        return None

if __name__ == "__main__":
    manager = ListenerManager()
    
    manager.add_listener(RecordListener())
    manager.add_listener(AbortRecordListener())
    # manager.add_listener(Parrot())

    # Keep main thread alive (Ctrl+C to exit)
    manager.keep_alive()
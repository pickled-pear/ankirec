from abc import ABC, abstractmethod
from pynput import keyboard
import threading

from ..anki.flashcard import FlashcardManager
from ..recording.full_recorder import FullRecorder

class KeyListener(ABC):
    """Base class for restartable keyboard listeners."""
    target_keys: set[keyboard.Key, keyboard.KeyCode]

    def __init__(self) -> None:
        self._listener: keyboard.Listener | None = None

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
            self._listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release,
            )
            self._listener.start()

    def stop_listening(self) -> None:
        """Stop listening."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def join(self) -> None:
        """Block until the listener stops."""
        if self._listener is not None:
            self._listener.join()


class ListenerManager:
    """Manages multiple keyboard listeners running concurrently."""
    
    def __init__(self) -> None:
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
            # Blocks here until _stop_event.set() is called
            # Returns immediately when set, no polling
            self._stop_event.wait()
        except KeyboardInterrupt:
            print("\nShutting down...")
            self.stop_all()



class RecordListener(KeyListener):
    """Class that listens to trigger recording"""
    target_keys = set([keyboard.Key.alt_r, keyboard.Key.alt_gr])
    flashcard: FlashcardManager

    def __init__(self,):
        # super().__init__(verbose=verbose, on=True)
        super().__init__()
        self.flashcard = FlashcardManager()

    def map_to_key(self, keyvk: int) -> keyboard.Key | None:
        """right alt is non-consistent across platforms so map it if does not work"""
        try:
            if keyvk == 65027: # right alt on linux
                return keyboard.Key.alt_r
            elif keyvk == 165: # windows
                return keyboard.Key.alt_r
            else:
                return None # returns null 
        except AttributeError:
            # if this calls it wasnt alt anyway, return null
            return None

    def on_press(self, key):
        if not isinstance(key, keyboard.Key):
            key = self.map_to_key(key.vk)

        if key in self.target_keys:
            self.flashcard.on_press()

class AbortRecordListener(KeyListener):
    """Class that listens to abort recording"""
    target_keys = set([keyboard.KeyCode.from_char("q")])
    recorder: FullRecorder

    def __init__(self):
        super().__init__()
        self.recorder = FullRecorder()

    def on_press(self, key):
        if key in self.target_keys:
            self.recorder.abort()
            print(self.recorder.recording_cycle)


class Parrot(KeyListener):
    """Prints the key that was pressed"""
    def on_press(self, key):
        print(f"""{key} was pressed\n{key.vk}""")
        if not isinstance(key, keyboard.Key):
            # print("NOT A KEY")
            pass

if __name__ == "__main__":
    manager = ListenerManager()
    
    manager.add_listener(RecordListener())
    manager.add_listener(AbortRecordListener())
    # manager.add_listener(Parrot())

    # Keep main thread alive (Ctrl+C to exit)
    manager.keep_alive()
import threading
import time
from pathlib import Path
import miniaudio
import array


class Player:
    def __init__(self, volume: float = 1.0):
        self._device = miniaudio.PlaybackDevice()
        self._finished = threading.Event()
        self._stopped_early = False
        self.volume = volume  # 0.0 to 1.0; can be changed during playback

    def _apply_volume(self, chunk):
        v = max(0.0, min(1.0, self.volume)) ** 2
        if v == 1.0:
            return chunk
        return array.array("h", (int(s * v) for s in chunk))

    def play(self, path: Path):
        stream = miniaudio.stream_with_callbacks(
            miniaudio.stream_file(str(path)),
            frame_process_method=self._apply_volume,
            end_callback=self._finished.set,
        )
        next(stream)
        self._device.start(stream)
        threading.Thread(target=self._close_when_done, daemon=True).start()

    def stop(self):
        """Stop now; the device is closed by the watcher thread."""
        self._stopped_early = True
        self._finished.set()

    def wait(self):
        """Block until playback has finished or been stopped."""
        self._finished.wait()

    def _close_when_done(self):
        self._finished.wait()
        if not self._stopped_early:
            time.sleep(0.2)  # let the final buffer drain
        self._device.close()


class AudioPlayerController:
    def __init__(self, volume: float = 0.8):
        self.sfx_dir = Path(__file__).parent / "sfx"
        self.volume = volume  # default for every sound

    def play_audio(self, path: Path, volume: float | None = None) -> Player:
        """Plays audio at the given path and closes after. File extension must be given."""
        player = Player(self.volume if volume is None else volume)
        true_path = Path(__file__).parent / path
        player.play(true_path)
        return player

    def play_sfx(self, name: str, volume: float | None = None) -> Player:
        return self.play_audio(self.sfx_dir / name, volume)



if __name__ == "__main__":
    player = Player()
    controller = AudioPlayerController(volume=0.4)
    # player.play("/home/evan/tools/ankirec/src/ankirec/audio/sfx/ClashRoyale/Cards/Mini PEKKA/mini_pekka_atk_12.ogg")
    # input("Enter to stop...")
    # player.stop()
    # player.close()
    # controller.play_audio(controller.sfx_dir / "ClashRoyale" / "Cards" / "Spear Goblins" / "spear_gob_dep_01v2.ogg")
    controller.play_sfx("ClashRoyale/Cards/Spear Goblins/spear_gob_dep_01v2.ogg")
    # print("done")
    time.sleep(2)
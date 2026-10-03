from ..base.constants import PLATFORM
from .audio_recorder import AudioConfigProtocol, AbstractAudioRecorder

class AudioRecorderFactory:
    """Factory for creating platform-specific recorders."""

    @staticmethod
    def create(config: AudioConfigProtocol) -> AbstractAudioRecorder:
        """Create recorder for current platform. Only imports module relevant to platform."""
        if PLATFORM == "windows":
            from .audio_windows import WindowsAudioRecorder
            return WindowsAudioRecorder(config)
        elif PLATFORM == "linux":
            from .audio_linux import LinuxAudioRecorder
            return LinuxAudioRecorder(config)
        else:
            raise NotImplementedError(f"Platform {PLATFORM} not supported")
import logging
from rich.logging import RichHandler
from functools import wraps
from .context import verbose_mode
# from .config import Config
from typing import Protocol

class ConfigProtocol(Protocol):
    def get_config(self) -> dict: ...
    def get_single_config(self, key: str): ...

class VerboseMixin:
    verbose: bool

    def __init__(self):
        self.verbose = verbose_mode.get()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if not self.logger.handlers:
            handler = RichHandler(rich_tracebacks=True)
            # Configure styling per level
            handler.setFormatter(logging.Formatter('%(message)s', datefmt='[%X]'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

    def echo(self, *args):
        """Default echo"""
        if self.verbose:
            message = ' '.join(str(arg) for arg in args)
            print(message)

    def debug(self, *args):
        """Log at debug level"""
        if self.verbose:
            message = ' '.join(str(arg) for arg in args)
            self.logger.debug(message)

    def info(self, *args):
        """Log at info level"""
        if self.verbose:
            message = ' '.join(str(arg) for arg in args)
            self.logger.info(message)

    def warning(self, *args):
        """Log at warning level"""
        message = '[yellow]'.join(str(arg) for arg in args)
        self.logger.warning(message)

    def error(self, *args):
        """Log at error level"""
        message = ' '.join(str(arg) for arg in args)
        self.logger.error(message)

    def critical(self, *args):
        """Log at critical level"""
        message = ' '.join(str(arg) for arg in args)
        self.logger.critical(message)


class ToggleableMixin:
    # To use this class, every feature that can be toggled off should check settings to see its status,
    # and pass that here somehow. Either with context or a param
    enabled: bool
    def __init__(self, on: bool, **kwargs):
        super().__init__(**kwargs)
        self.enabled = on

    def requires_enabled(self, func):
        """Decorator that checks if the feature is enabled before executing."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not self.enabled:
                logger = logging.getLogger(self.__class__.__name__)
                logger.warning(f"{func.__name__} is disabled")
                return
            return func(*args, **kwargs)
        return wrapper
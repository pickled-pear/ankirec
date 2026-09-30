from contextvars import ContextVar
from typing import Protocol, ClassVar
from pathlib import Path

verbose_mode: ContextVar[bool] = ContextVar('verbose_mode', default=False)

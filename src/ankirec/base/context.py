from contextvars import ContextVar

verbose_mode: ContextVar[bool] = ContextVar('verbose_mode', default=False)

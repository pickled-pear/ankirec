from rich import print
from functools import wraps
from .context import verbose_mode

class VerboseMixin:
    verbose: bool

    def __init__(self):
        self.verbose = verbose_mode.get()

    def echo(self, *args):
        if self.verbose:
            print(*args)


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
                print(f"{func.__name__} is disabled")
                return
            return func(*args, **kwargs)
        return wrapper

# class VerboseMixin:
#     verbose: bool

#     def __init__(self, verbose, **kwargs):
#         super().__init__(**kwargs)
#         self.verbose = verbose

#     def echo(self, *args):
#         if self.verbose:
#             print(*args)


# class ToggleableMixin:
#     enabled: bool
#     def __init__(self, on: bool, **kwargs):
#         super().__init__(**kwargs)
#         self.enabled = on

#     def requires_enabled(self, func):
#         """Decorator that checks if the feature is enabled before executing."""
#         @wraps(func)
#         def wrapper(*args, **kwargs):
#             if not self.enabled:
#                 print(f"{func.__name__} is disabled")
#                 return
#             return func(*args, **kwargs)
#         return wrapper
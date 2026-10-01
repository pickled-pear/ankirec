from rich import print
import functools
import time
import threading
import sys

from .mixin import VerboseMixin
from .constants import PLATFORM

if PLATFORM == "windows":
    import msvcrt
elif PLATFORM == "linux":
    import termios


# def warn(*args):
#     """Prints the arguments with formatting. Not surpressed by verbose"""
#     print(f"[yellow]{' '.join(str(arg) for arg in args)}")

# def success_message(*args):
#     """Prints the arguments with formatting. Not surpressed by verbose"""
#     print(f"[green]{' '.join(str(arg) for arg in args)}")



class Timer(VerboseMixin):
    """Decorator class that measures and prints function execution time."""
    
    def __init__(self, func):
        super().__init__()
        self.func = func
        functools.update_wrapper(self, func)
    
    def __call__(self, *args, **kwargs):
        start_time = time.perf_counter()
        result = self.func(*args, **kwargs)
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        
        self.echo(f"{self.func.__name__} took {elapsed_time:.4f} seconds")
        return result


def timeout_wrapper(timeout_seconds):
    """
    Function decorator that enforces a maximum execution time using a timer,
    not a separate thread. Works correctly with instance methods called from
    event listeners or other threads.
    
    This sucks dont use it
    Args:
        timeout_seconds: Maximum time allowed for function execution
    
    Raises:
        TimeoutError: If function execution exceeds the timeout
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            stop_event = threading.Event()
            result = [None]
            exception = [None]
            completed = threading.Event()
            
            # Run the function synchronously in the current thread
            start_time = time.perf_counter()
            
            def timeout_handler():
                """Called when timeout expires"""
                stop_event.set()
            
            # Set up a timer that will signal after timeout_seconds
            timer = threading.Timer(timeout_seconds, timeout_handler)
            timer.daemon = True
            timer.start()
            
            try:
                result[0] = func(*args, stop_event=stop_event, **kwargs)
                completed.set()
            except Exception as e:
                exception[0] = e
                completed.set()
            finally:
                elapsed_time = time.perf_counter() - start_time
                timer.cancel()  # Cancel the timer if we finished early
                
                # If stop_event was set, we timed out
                if stop_event.is_set():
                    raise TimeoutError(
                        f"Function '{func.__name__}' exceeded "
                        f"{timeout_seconds} second timeout (took {elapsed_time:.4f}s)"
                    )
                
                # If there was an exception, raise it
                if exception[0]:
                    raise exception[0]
                
                print(f"[Timeout] {func.__name__} took {elapsed_time:.4f} seconds")
                return result[0]

        return wrapper
    return decorator


def flush_input(max_flush=5000):
    """Used to flush the terminal to prevent strange input issues. Might not be needed on out of windwos"""
    if PLATFORM == "windows":
        flushcount = 0
        while msvcrt.kbhit() and flushcount < max_flush:
            msvcrt.getch()
            flushcount += 1
    # else:
        # if termios:
            # termios.tcflush(sys.stdin, termios.TCIFLUSH)


def singleton(cls):
    """Decorator to make a class a singleton."""
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance
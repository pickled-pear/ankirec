import json
import click
from rich import print
from rich.console import Console
from rich.table import Table

# elif PLATFORM == UserPlatform.LINUX:
#     import termios


# def warn(*args):
#     """Prints the arguments with formatting. Not surpressed by verbose"""
#     print(f"[yellow]{' '.join(str(arg) for arg in args)}")

# def success_message(*args):
#     """Prints the arguments with formatting. Not surpressed by verbose"""
#     print(f"[green]{' '.join(str(arg) for arg in args)}")



# class Timer(VerboseMixin):
#     """Decorator class that measures and prints function execution time."""
    
#     def __init__(self, func):
#         super().__init__()
#         self.func = func
#         functools.update_wrapper(self, func)
    
#     def __call__(self, *args, **kwargs):
#         start_time = time.perf_counter()
#         result = self.func(*args, **kwargs)
#         end_time = time.perf_counter()
#         elapsed_time = end_time - start_time
        
#         self.echo(f"{self.func.__name__} took {elapsed_time:.4f} seconds")
#         return result


# def timeout_wrapper(timeout_seconds):
#     """
#     DO NOT USE
    
#     Function decorator that enforces a maximum execution time using a timer,
#     not a separate thread. Works correctly with instance methods called from
#     event listeners or other threads.
    
#     This sucks dont use it
#     Args:
#         timeout_seconds: Maximum time allowed for function execution
    
#     Raises:
#         TimeoutError: If function execution exceeds the timeout
#     """
#     def decorator(func):
#         @functools.wraps(func)
#         def wrapper(*args, **kwargs):
#             stop_event = threading.Event()
#             result = [None]
#             exception = [None]
#             completed = threading.Event()
            
#             # Run the function synchronously in the current thread
#             start_time = time.perf_counter()
            
#             def timeout_handler():
#                 """Called when timeout expires"""
#                 stop_event.set()
            
#             # Set up a timer that will signal after timeout_seconds
#             timer = threading.Timer(timeout_seconds, timeout_handler)
#             timer.daemon = True
#             timer.start()
            
#             try:
#                 result[0] = func(*args, stop_event=stop_event, **kwargs)
#                 completed.set()
#             except Exception as e:
#                 exception[0] = e
#                 completed.set()
#             finally:
#                 elapsed_time = time.perf_counter() - start_time
#                 timer.cancel()  # Cancel the timer if we finished early
                
#                 # If stop_event was set, we timed out
#                 if stop_event.is_set():
#                     raise TimeoutError(
#                         f"Function '{func.__name__}' exceeded "
#                         f"{timeout_seconds} second timeout (took {elapsed_time:.4f}s)"
#                     )
                
#                 # If there was an exception, raise it
#                 if exception[0]:
#                     raise exception[0]
                
#                 print(f"[Timeout] {func.__name__} took {elapsed_time:.4f} seconds")
#                 return result[0]

#         return wrapper
#     return decorator


# def flush_input(max_flush=5000):
#     """Used to flush the terminal to prevent strange input issues. Might not be needed on out of windwos"""
#     if PLATFORM == UserPlatform.WINDOWS:
#         flushcount = 0
#         while msvcrt.kbhit() and flushcount < max_flush:
#             msvcrt.getch()
#             flushcount += 1
#     # else:
#         # if termios:
#             # termios.tcflush(sys.stdin, termios.TCIFLUSH)


def singleton(cls):
    """Decorator to make a class a singleton."""
    instances = {}
    
    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


def success_message(*args):
    string = " ".join(f"[green]{a}[/green]" for a in args).strip()
    print(string)


def display_table(title: str, cols: list, *rows, show_lines: bool = True):
    # If called with a single argument that is itself a list of rows,
    # unwrap it so both calling styles work.
    if len(rows) == 1 and rows[0] and isinstance(rows[0], (list, tuple)) \
            and isinstance(rows[0][0], (list, tuple)):
        rows = rows[0]

    table = Table(title=title, show_lines=show_lines)
    for col in cols:
        table.add_column(str(col))

    for row in rows:
        table.add_row(*(str(c) for c in row))

    Console().print(table)


def run_action(action, *args, **kwargs):
    """Runs an action, turning its errors into a clean CLI message."""
    try:
        return action(*args, **kwargs)
    except ValueError as e:
        raise click.ClickException(str(e)) from None


def coerce(item):
    """Convert a CLI string to bool/int/float where it clearly is one."""
    if not isinstance(item, str):
        return item
    text = item.strip()

    # Explicitly quoted -> always a string, eg '"123"'
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1]

    if text.lower() in ("true", "false"):
        return text.lower() == "true"

    try:
        return int(text)
    except ValueError:
        pass

    if any(ch.isdigit() for ch in text):   # stops "nan"/"inf" becoming floats
        try:
            return float(text)
        except ValueError:
            pass

    return item


def parse_value(values):
    """Turn the CLI args into a scalar or a list.

    foo                    -> "foo"
    true                   -> True
    5                      -> 5
    foo bar baz            -> ["foo", "bar", "baz"]
    '["foo", "bar"]'       -> ["foo", "bar"]
    [foo, bar]             -> ["foo", "bar"]   (quotes eaten by the shell)
    """
    joined = " ".join(values).strip()

    if joined.startswith("[") and joined.endswith("]"):
        try:
            parsed = json.loads(joined)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [
            coerce(item)
            for item in joined[1:-1].split(",")
            if item.strip()
        ]

    if len(values) > 1:
        return [coerce(v) for v in values]
    return coerce(values[0])
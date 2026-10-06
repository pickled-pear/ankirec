import click
from pathlib import Path
from rich import print
from rich.table import Table
from rich.console import Console
import sys

from .listeners import ListenerManager, RecordListener, AbortRecordListener
from .constants import APP_NAME
from .config import Config
from .context import verbose_mode
from ..anki.anki import AnkiconnectActions
from ..sources.source_manager import Sources


def verify_location_safety():
    def _bad_dirs() -> set[Path]:
        """Sets dirs to avoid based on os"""
        if sys.platform == "win32":
            raw = {
                Path("C:/Windows"),
                Path("C:/Program Files"),
                Path("C:/Program Files (x86)"),
            }
        else:  # linux, and largely fine for macOS too
            raw = {
                Path("/bin"), Path("/sbin"), Path("/boot"), Path("/dev"),
                Path("/etc"), Path("/lib"), Path("/lib32"), Path("/lib64"),
                Path("/libx32"), Path("/opt"), Path("/proc"), Path("/root"),
                Path("/run"), Path("/sys"), Path("/usr"), Path("/var"),
            }
        return {p.resolve() for p in raw}

    BAD_DIRS = _bad_dirs()

    r"""Checks the script is not run in an unsafe folder, eg C:\Windows"""
    cwd = Path.cwd().resolve()
    if cwd == cwd.parent or any(cwd.is_relative_to(bad) for bad in BAD_DIRS):
        raise click.UsageError(f"Bad working directory: {cwd}")

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

@click.group
@click.version_option()
def cli():
    """The main function that starts the tool"""
    verify_location_safety()


@cli.command(name="record")
@click.option("--verbose", is_flag=True, default=False, help="Verbose flag")
def record(verbose):
    """Starts listening to record screen"""
    listener_manager = ListenerManager()
    verbose_mode.set(verbose)

    listener_manager.add_listener(RecordListener())
    listener_manager.add_listener(AbortRecordListener())

    listener_manager.keep_alive()


@cli.command(name="send-notes")
@click.option("--verbose", is_flag=True, default=False, help="Verbose flag")
def sendnotes(verbose):
    """Sends the contents of notes.json to anki"""
    verbose_mode.set(verbose)
    ankiconfig = Config().load_section("anki")
    ankiactions = AnkiconnectActions(port=ankiconfig.get("ankiconnect_port", 8765), api_ver=ankiconfig.get("ankiconnect_api_ver", 6))
    ankiactions.send_notes_to_anki()
    success_message("Sent notes")




@cli.group
def source():
    """Manage the source options"""

@source.command(name="list")
@click.option("--folder", help="Folder to list. None by default")
def list_sources(folder):
    """Lists all sources"""
    raise NotImplementedError

@source.command(name="add")
@click.argument("source")
@click.argument("folder")
def add_source(source, folder):
    """Adds a source at the given location"""
    raise NotImplementedError

@source.command(name="move")
@click.argument("source")
@click.argument("old_folder")
@click.argument("new_folder")
def move_source():
    """Moves a source"""
    raise NotImplementedError

@source.command(name="delete")
@click.argument("chosen_object")
def delete_object(chosen_object):
    """Deletes the given object. Deleting a folder deletes all children"""
    raise NotImplementedError

@source.command(name="set")
@click.argument("source")
def set_source(source: str):
    """Sets the active source (WIP)"""
    source_manager = Sources()
    source_manager.set_value("selected", source)
    success_message("Successfully set source")

# continue source commands...


@cli.group
def config():
    """View and edit the config"""
    

@config.command(name="list")
# @click.option("--type")
@click.option("--key", help="Specifc key to show config for (none by default)")
def list_config(key):
    """Lists all settings with their current values"""
    cols = ["Name", "Value"]
    config = Config()
    if key:
        value = config.get_value_recursively(target_key=key, data=config.load())
        row = [key, value]
        display_table("List Config", cols, row)
    else:
        config_data = config.get()
        for name, section in config_data.items():
            rows = [[key, value] for key, value in section.items()]
            display_table(name, cols, rows)


@config.command(name="open")
def open_config():
    """Opens the config json in a the default text editor"""
    config = Config()
    config.open_json_file()

@config.command(name="set")
@click.argument("setting")
@click.argument("value")
def set_value(setting, value):
    """Update a given setting. Use . notation to specifiy section, eg anki.deckname"""
    config = Config()
    if "." in setting:
        config.set_value(setting, value)
    else:
        # need to recursively search for the key
        result_json = config.set_value_recursively(setting, value, config.load())
        config.save(result_json)


@config.command(name="reset")
def reset_to_default():
    """Reset all settings to default values"""
    # note to self: make the user confirm somehow
    Config().reset_to_defaults()
    print("Reset")
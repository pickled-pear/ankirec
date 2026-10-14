import click
from pathlib import Path
from rich import print
from rich.table import Table
from rich.console import Console
import sys
import copy
import json

from .listeners import ListenerManager, RecordListener, AbortRecordListener
from .constants import APP_NAME
from .config import Config
from .context import verbose_mode
from ..anki.anki import AnkiconnectActions
from ..sources.source_manager import Sources, Source
from ..sources.source_tree import source_tree_rich


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


def _run(action, *args, **kwargs):
    """Runs an action, turning its errors into a clean CLI message."""
    try:
        return action(*args, **kwargs)
    except ValueError as e:
        raise click.ClickException(str(e)) from None


def _coerce(item):
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


def _parse_value(values):
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
            _coerce(item)
            for item in joined[1:-1].split(",")
            if item.strip()
        ]

    if len(values) > 1:
        return [_coerce(v) for v in values]
    return _coerce(values[0])

# --- general commands --------------------------------------------------------

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


# --- notes group --------------------------------------------------------------

@cli.group
def notes():
    """Manages saved notes"""


@notes.command(name="send")
@click.option("--verbose", is_flag=True, default=False, help="Verbose flag")
def sendnotes(verbose):
    """Sends the contents of notes.json to anki"""
    verbose_mode.set(verbose)
    ankiconfig = Config().load_section("anki")
    ankiactions = AnkiconnectActions(port=ankiconfig.get("ankiconnect_port", 8765), api_ver=ankiconfig.get("ankiconnect_api_ver", 6))
    ankiactions.send_notes_to_anki()
    success_message("Sent notes")


# @notes.command(name="open")
# def open_notes_json():
#     """Opens the notes json file for inspection"""
#     verbose_mode.set(False)
#     json_file = anki.SharedValues().notes_json_file




 
# --- source group ------------------------------------------------------------

 
@cli.group
def source():
    """Manage the source options"""
 
 
@source.command(name="list")
@click.option("--folder", default="root", help="Folder to show. Root by default")
def list_sources(folder: str):
    """Shows the source tree, with the active source marked"""
    sources = Sources()
    top = _run(sources.get_folder, folder)
    if not top.children:
        click.echo(f"{folder} is empty")
        return
    Console().print(source_tree_rich(top, sources.selected_id))
 
 
@source.command(name="current")
def current_source():
    """Shows the active source"""
    selected = Sources().selected
    click.echo(selected.path if selected else "No active source")
 
 
@source.command(name="open")
def open_sources():
    """Opens the source json in the default text editor"""
    Sources().open_json_file()
 
 
@source.command(name="add")
@click.argument("name")
@click.argument("folder")
@click.argument("item_type", type=click.Choice(["source", "folder"], case_sensitive=False))
def add_source(name: str, folder: str, item_type: str):
    """Adds a source or folder called NAME inside FOLDER"""
    _run(Sources().add_item, name, folder, item_type)
    success_message("Added!")
 
 
@source.command(name="move")
@click.argument("path")
@click.argument("new_folder")
def move_source(path: str, new_folder: str):
    """Moves the item at PATH into NEW_FOLDER"""
    item = _run(Sources().move_item, path, new_folder)
    success_message(f"Moved to {item.path}")
 
 
@source.command(name="rename")
@click.argument("path")
@click.argument("new_name")
def rename_source(path: str, new_name: str):
    """Renames the item at PATH to NEW_NAME"""
    item = _run(Sources().rename_item, path, new_name)
    success_message(f"Renamed to {item.path}")
 
 
@source.command(name="delete")
@click.argument("path")
def delete_object(path: str):
    """Deletes the item at PATH. Deleting a folder deletes all children"""
    item = _run(Sources().delete_item, path)
    success_message(f"Deleted {item.name}")
 
 
@source.command(name="set")
@click.argument("path", required=False)
def set_source(path: str | None):
    """Sets the active source to PATH, or shows the tree to pick from if no PATH is given"""
    sources = Sources()
    if path is None:
        options: list[Source] = []
        tree = source_tree_rich(sources.get_folder(), sources.selected_id, numbered=options)
        if not options:
            raise click.ClickException("No sources yet. Add one with: source add NAME FOLDER source")
        Console().print(tree)
        choice = click.prompt("Source number", type=click.IntRange(1, len(options)))
        path = options[choice - 1].full_path
    item = _run(sources.select, path)
    success_message(f"Active source set to {item.path}")
 
 
@source.command(name="unset")
def unset_source():
    """Clears the active source"""
    Sources().deselect()
    success_message("No active source")
 
 
@source.command(name="reset")
@click.option("--confirm", is_flag=True, default=False, help="Add to confirm reset. Will do nothing without this.")
def reset_source_json(confirm):
    """Resets the source json by deleting everything except for root"""
    if confirm:
        Sources().reset_to_defaults()
        click.echo("Reset")
    else:
        click.echo("Not confirmed so no reset. Use --confirm to confirm")



# @source.command
# maybe make a group for login?

@source.group
def sync():
    """Handles syncing the sources with firebase if desired"""

@sync.command(name="toggle")
def toggle_sync():
    """Toggles whether to sync the sources json with firebase or not"""
    cfg = Config()
    sync_value = cfg.get_value("general.sources_sync")
    sync_value = not sync_value
    click.echo(f"Sync set to {sync_value}")
    cfg.set_value("general.sources_sync", sync_value)


@sync.command(name="login")
@click.argument("email")
def firebase_login(email):
    """Logs in to firebase"""

@sync.command(name="signup")
@click.argument("email")
def firebase_signup(email):
    """Signs up to firebase"""

@sync.command(name="logout")
@click.argument("email")
def firebase_logout(email):
    """Logs out of firebase locally"""


# --- config group -------------------------------------------------------------------------

@cli.group
def config():
    """View and edit the config"""

@config.command(name="list")
@click.option("--key", help="Specific key to show config for (none by default)")
def list_config(key):
    """Lists all settings with their current values"""
    cols = ["Name", "Value"]
    cfg = Config()
    if key:
        if "." in key:
            value = _run(cfg.get_value, key)
        else:
            value = cfg.get_value_recursively(target_key=key, data=cfg.get())
            if value is None:
                raise click.ClickException(f"Unknown setting: {key}")
        display_table("List Config", cols, [[key, value]])
    else:
        for name, section in cfg.get().items():
            rows = [[k, v] for k, v in section.items()]
            display_table(name, cols, rows)


@config.command(name="open")
def open_config():
    """Opens the config json in the default text editor"""
    Config().open_json_file()


@config.command(name="set")
@click.argument("setting")
@click.argument("values", nargs=-1, required=True)
def set_value(setting, values):
    """Update a given setting. Use . notation to specify section, eg anki.deckname

    Give several values, or a [bracketed, list], to store a list.
    """
    value = _parse_value(values)

    cfg = Config()
    if "." in setting:
        _run(cfg.get_value, setting)          # fails cleanly if the setting doesn't exist
        cfg.set_value(setting, value)
    else:
        data = copy.deepcopy(cfg.get())
        if not cfg.set_value_recursively(setting, value, data):
            raise click.ClickException(f"Unknown setting: {setting}")
        cfg.save(data)
    success_message(f"Set {setting}")


@config.command(name="reset")
@click.option("--confirm", is_flag=True, default=False, help="Add to confirm reset. Will do nothing without this.")
def reset_to_default(confirm):
    """Reset all settings to default values."""
    if confirm:
        Config().reset_to_defaults()
        click.echo("Reset")
    else:
        click.echo("Not confirmed so no reset. Use --confirm to confirm")


@config.command(name="update")
def update_config_keys():
    """Merges existing config file with any new default keys"""
    current_config = Config()
    config_json = current_config.load()
    current_config.save(config_json)
    success_message("Updated config to have new keys")
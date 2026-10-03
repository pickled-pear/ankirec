import click
from pathlib import Path
import sys

from .listeners import ListenerManager, RecordListener, AbortRecordListener
from .constants import APP_NAME
from .config import Config
from .context import verbose_mode


def verify_location_safety():
    def _bad_dirs() -> set[Path]:
        """Sets dirs to avoid based on os"""
        print("babagaboosh!")
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

@click.group
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

# continue source commands...


@cli.group
def config():
    """View and edit the config"""
    

@config.command(name="list")
# @click.option("--type")
@click.option("--key", help="Specifc key to show history for (none by default)")
def list_config(key):
    """Lists all settings with their current values"""
    raise NotImplementedError

@config.command(name="open")
def open_config():
    """Opens the history json in a the default text editor"""
    raise NotImplementedError

@config.command(name="set")
@click.argument("setting")
@click.argument("value")
def set_value(setting, value):
    """Update a given setting"""
    raise NotImplementedError

@config.command(name="reset")
def reset_to_default():
    """Reset all settings to default values"""
    # note to self: make the user confirm somehow
    Config().reset_to_defaults()
    print("Reset")
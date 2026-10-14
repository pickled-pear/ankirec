import click
from pathlib import Path
import sys

from .commands.record import record
from .commands.notes import notes
from .commands.source import source
from .commands.config import config


def verify_location_safety():
    r"""Checks the script is not run in an unsafe folder, eg C:\Windows"""
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

    cwd = Path.cwd().resolve()
    if cwd == cwd.parent or any(cwd.is_relative_to(bad) for bad in BAD_DIRS):
        raise click.UsageError(f"Bad working directory: {cwd}")


@click.group
@click.version_option()
def cli():
    """The main function that starts the tool"""
    verify_location_safety()


cli.add_command(record)
cli.add_command(notes)
cli.add_command(source)
cli.add_command(config)
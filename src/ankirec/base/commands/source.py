import click
from rich.console import Console

from ..helpers import success_message, run_action
from ...sources.source_manager import Sources, Source
from ...sources.source_tree import source_tree_rich
from .sync import sync


@click.group
def source():
    """Manage the source options"""


source.add_command(sync)


@source.command(name="list")
@click.option("--folder", default="root", help="Folder to show. Root by default")
def list_sources(folder: str):
    """Shows the source tree, with the active source marked"""
    sources = Sources()
    top = run_action(sources.get_folder, folder)
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
    run_action(Sources().add_item, name, folder, item_type)
    success_message("Added!")


@source.command(name="move")
@click.argument("path")
@click.argument("new_folder")
def move_source(path: str, new_folder: str):
    """Moves the item at PATH into NEW_FOLDER"""
    item = run_action(Sources().move_item, path, new_folder)
    success_message(f"Moved to {item.path}")


@source.command(name="rename")
@click.argument("path")
@click.argument("new_name")
def rename_source(path: str, new_name: str):
    """Renames the item at PATH to NEW_NAME"""
    item = run_action(Sources().rename_item, path, new_name)
    success_message(f"Renamed to {item.path}")


@source.command(name="delete")
@click.argument("path")
def delete_object(path: str):
    """Deletes the item at PATH. Deleting a folder deletes all children"""
    item = run_action(Sources().delete_item, path)
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
    item = run_action(sources.select, path)
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
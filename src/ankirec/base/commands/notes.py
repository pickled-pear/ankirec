import click

from ..config import Config
from ..context import verbose_mode
from ..helpers import success_message
from ...anki.anki import AnkiconnectActions


@click.group
def notes():
    """Manages saved notes"""


@notes.command(name="send")
@click.option("--verbose", is_flag=True, default=False, help="Verbose flag")
def sendnotes(verbose):
    """Sends the contents of notes.json to anki"""
    verbose_mode.set(verbose)
    ankiconfig = Config().load_section("anki")
    ankiactions = AnkiconnectActions(
        port=ankiconfig.get("ankiconnect_port", 8765),
        api_ver=ankiconfig.get("ankiconnect_api_ver", 6),
    )
    ankiactions.update_anki_open()
    ankiactions.send_notes_to_anki()
    success_message("Sent notes")


# @notes.command(name="open")
# def open_notes_json():
#     """Opens the notes json file for inspection"""
#     verbose_mode.set(False)
#     json_file = anki.SharedValues().notes_json_file
import click

from ..config import Config


@click.group
def sync():
    """Handles syncing the sources with firebase if desired"""


@sync.command(name="toggle")
def toggle_sync():
    """Toggles whether to sync the sources json with firebase or not"""
    cfg = Config()
    sync_value = not cfg.get_value("general.sources_sync")
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
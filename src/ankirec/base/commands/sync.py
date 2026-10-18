import click
import json

from ..config import Config
from ..firebase_sync import FirebaseStore, SyncError
from ...sources.source_manager import Sources

def _friendly(err: SyncError) -> click.ClickException:
    FRIENDLY_ERRORS = {
        "INVALID_LOGIN_CREDENTIALS": "Wrong email or password",
        "INVALID_PASSWORD": "Wrong email or password",
        "EMAIL_NOT_FOUND": "Wrong email or password",
        "EMAIL_EXISTS": "An account with that email already exists. Try 'login'",
        "INVALID_EMAIL": "That doesn't look like a valid email address",
        "WEAK_PASSWORD": "Password must be at least 6 characters",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Too many attempts. Please wait a while and try again",
        "USER_DISABLED": "This account has been disabled",
        "ADMIN_ONLY_OPERATION": "New sign-ups are currently disabled",
    }

    text = str(err)
    for code, msg in FRIENDLY_ERRORS.items():
        if code in text:
            return click.ClickException(msg)
    return click.ClickException(text)

def get_store() -> FirebaseStore:
    store = FirebaseStore()
    if not store.signed_in:
        raise SystemExit("Not signed in. Sign in first")
    return store

@click.group
def sync():
    """Handles syncing the sources with firebase if desired"""


@sync.command(name="toggle")
def toggle_sync():
    """Toggles whether to sync the sources json with firebase or not. Doesn't actually affect anything"""
    cfg = Config()
    sync_value = not cfg.get_value("general.sources_sync")
    click.echo(f"Sync set to {sync_value}")
    cfg.set_value("general.sources_sync", sync_value)

@sync.command(name="login")
@click.argument("email")
def firebase_login(email):
    """Logs in to firebase"""
    store = FirebaseStore()
    password = click.prompt("Password", hide_input=True)
    try:
        store.sign_in(email, password)
        if not store.email_verified():
            click.echo("Your email is not verified")
        else:
            click.echo("Signed in!")
    except SyncError as e:
        raise _friendly(e)

@sync.command(name="signup")
@click.argument("email")
def firebase_signup(email):
    """Signs up to firebase"""
    store = FirebaseStore()
    password = click.prompt("Password", hide_input=True)
    try:
        if password:
            store.sign_up(email, password)
            click.echo("Check your inbox to verify, then log in")

        else:
            click.echo("You didn't enter a password!")
    except SyncError as e:
        raise _friendly(e)

@sync.command(name="logout")
def firebase_logout():
    """Logs out of firebase locally"""
    FirebaseStore().sign_out()
    click.echo("Logged out on this device")

@sync.command(name="push")
@click.option("--confirm", is_flag=True, default=False, help="Add to confirm. Will do nothing without this.")
def firebase_push(confirm):
    """Pushes the sources.json file to the db
    
    IMPORTANT: will overwrite the database. Be sure you want to do this!"""
    if confirm:
        store = get_store()
        sources_json_file = Sources().file_path
        with open(sources_json_file) as file:
            sources_data = json.load(file)

        store.save(sources_data)
        click.echo("Saved to db!")
    else:
        click.echo("Not confirmed so no changes. Use --confirm to confirm")


@sync.command(name="pull")
@click.option("--confirm", is_flag=True, default=False, help="Add to confirm. Will do nothing without this.")
def firebase_pull(confirm):
    """Pulls the sources.json file from db and overwrites the local one"""
    if confirm:
        store = get_store()
        existing_data = store.load()
        assert isinstance(existing_data, dict)
        sources_json_file = Sources().file_path
        with open(sources_json_file, "w", encoding="utf-8") as file:
            json.dump(existing_data, file, indent=2, ensure_ascii=False)

        click.echo("Saved locally!")

    else:
        click.echo("Not confirmed so no changes. Use --confirm to confirm")

@sync.command(name="status")
def status_check():
    """Check if you are signed in"""
    store = FirebaseStore()
    if store.signed_in:
        click.echo(f"Signed in as {store.email}")
    else:
        click.echo(f"Not signed in. Use ankirec source sync login to sign in.")
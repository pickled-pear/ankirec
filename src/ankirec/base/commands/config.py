import copy

import click

from ..config import Config
from ..helpers import success_message, display_table, run_action, parse_value


@click.group
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
            value = run_action(cfg.get_value, key)
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
    value = parse_value(values)

    cfg = Config()
    if "." in setting:
        run_action(cfg.get_value, setting)    # fails cleanly if the setting doesn't exist
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
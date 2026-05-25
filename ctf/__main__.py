#!/usr/bin/env python3
import json
import logging
import os
import time
import urllib.request
from pathlib import Path

import rich
import typer
from rich.console import Console
from rich.prompt import Prompt
from typing_extensions import Annotated

from ctf import ENV, STATE
from ctf.commands.askgod import app as askgod_app
from ctf.commands.check import app as check_app
from ctf.commands.deploy import app as deploy_app
from ctf.commands.destroy import app as destroy_app
from ctf.commands.flags import app as flags_app
from ctf.commands.generate import app as generate_app
from ctf.commands.init import app as init_app
from ctf.commands.list import app as list_app
from ctf.commands.new import app as new_app
from ctf.commands.post import app as post_app
from ctf.commands.redeploy import app as redeploy_app
from ctf.commands.services import app as services_app
from ctf.commands.stats import app as stats_app
from ctf.commands.validate import app as validate_app
from ctf.commands.version import app as version_app
from ctf.common.logger import LOG
from ctf.common.utils import get_version, show_version

app = typer.Typer(
    help="CLI tool to manage CTF challenges as code. Run from the root CTF repo directory or set the CTF_ROOT_DIR environment variable to run the tool.",
    no_args_is_help=True,
)
app.add_typer(check_app)
app.add_typer(deploy_app)
app.add_typer(destroy_app)
app.add_typer(flags_app)
app.add_typer(generate_app)
app.add_typer(init_app)
app.add_typer(list_app)
app.add_typer(new_app)
app.add_typer(
    post_app,
    name="post",
    help="Commands to manage discourse post files.",
    rich_help_panel="Subcommands",
)
app.add_typer(redeploy_app)
app.add_typer(services_app)
app.add_typer(stats_app)
app.add_typer(validate_app)
app.add_typer(version_app)

app.add_typer(
    askgod_app,
    name="askgod",
    help="Commands for interacting with a live askgod server (github.com/nsec/askgod).",
    rich_help_panel="Subcommands",
)


def check_tool_version() -> None:
    # Check at most once per day
    stamp: Path = (
        Path(
            os.environ.get(
                "XDG_CACHE_HOME",
                Path(os.environ.get("HOME", "~")).expanduser() / ".cache",
            )
        )
        / "ctf-script"
        / "last_update_check"
    )
    if stamp.exists() and time.time() - stamp.stat().st_mtime < 24 * 60 * 60:
        return
    with Console().status("Checking for updates..."):
        current_version = get_version()
        try:
            r_context = urllib.request.urlopen(
                url="https://api.github.com/repos/nsec/ctf-script/releases/latest"
            )
        except Exception as e:
            LOG.debug(e)
            LOG.warning("Could not verify the latest release.")
            return
        with r_context as r:
            try:
                latest_version: str = json.loads(s=r.read().decode())["tag_name"]
            except Exception as e:
                LOG.debug(e)
                LOG.error("Could not verify the latest release.")
                return

            stamp.parent.mkdir(parents=True, exist_ok=True)
            stamp.touch()
            compare = 0
            for current_part, latest_part in zip(
                [int(part) for part in current_version.split(".")],
                [int(part) for part in latest_version.split(".")],
            ):
                if current_part < latest_part:
                    compare = -1
                    break
                elif current_part > latest_part:
                    compare = 1
                    break

    match compare:
        case 0 | 1:
            LOG.debug("Script is up to date.")
        case -1:
            LOG.warning(
                f"Script is outdated (current: {current_version}, upstream: {latest_version}). Please update to the latest release before continuing."
            )
            if (
                Prompt.ask(
                    "Do you want to continue?",
                    choices=["y", "N"],
                    case_sensitive=False,
                    show_default=False,
                    default="N",
                ).lower()
                == "n"
            ):
                raise typer.Exit()


@app.callback()
def global_options(
    location: Annotated[
        str,
        typer.Option(
            "--location",
            help="CTF root directory location.",
            rich_help_panel="Global options",
        ),
    ] = "",
    no_update_check: Annotated[
        bool,
        typer.Option(
            "--no-update-check",
            help="Do not check for update.",
            is_flag=True,
            rich_help_panel="Global options",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable DEBUG logging.",
            rich_help_panel="Global options",
        ),
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            show_default=False,
            is_eager=True,
            callback=show_version,
            help="Show version",
            rich_help_panel="Global options",
        ),
    ] = None,
):
    if verbose:
        LOG.setLevel(logging.DEBUG)
        LOG.handlers[0].setLevel(logging.DEBUG)
        STATE["verbose"] = True

    if location:
        ENV["CTF_ROOT_DIR"] = location

    if not no_update_check:
        check_tool_version()


def main():
    # Set console width to 150 if it's smaller to avoid "…" in output
    console = rich.get_console()
    console.width = 150 if console.width < 150 else console.width
    app()

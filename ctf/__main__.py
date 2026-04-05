#!/usr/bin/env python3
import json
import logging
import os
import sys
import urllib.request

import rich
import typer
from rich.console import Console
from rich.prompt import Prompt
from typer import Typer
from typing_extensions import Annotated

from ctf import ENV, STATE
from ctf.check import app as check_app
from ctf.deploy import app as deploy_app
from ctf.destroy import app as destroy_app
from ctf.flags import app as flags_app
from ctf.generate import app as generate_app
from ctf.init import app as init_app
from ctf.list import app as list_app
from ctf.logger import LOG
from ctf.new import app as new_app
from ctf.redeploy import app as redeploy_app
from ctf.services import app as services_app
from ctf.stats import app as stats_app
from ctf.utils import find_ctf_root_directory, get_version, show_version
from ctf.validate import app as validate_app
from ctf.version import app as version_app

app = Typer(
    help="CLI tool to manage CTF challenges as code. Run from the root CTF repo directory or set the CTF_ROOT_DIR environment variable to run the tool.",
    no_args_is_help=True,
)
app.add_typer(validate_app)
app.add_typer(init_app)
app.add_typer(new_app)
app.add_typer(destroy_app)
app.add_typer(flags_app)
app.add_typer(services_app)
app.add_typer(generate_app)
app.add_typer(deploy_app)
app.add_typer(redeploy_app)
app.add_typer(check_app)
app.add_typer(stats_app)
app.add_typer(list_app)
app.add_typer(version_app)


def check_tool_version() -> None:
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
        str, typer.Option("--location", help="CTF root directory location.")
    ] = "",
    no_update_check: Annotated[
        bool,
        typer.Option(
            "--no-update-check", help="Do not check for update.", is_flag=True
        ),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable DEBUG logging.")
    ] = False,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            show_default=False,
            is_eager=True,
            callback=show_version,
            help="Show version",
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


if __name__ == "__main__":
    import sys

    if "version" not in sys.argv and "init" not in sys.argv:
        if not os.path.isdir(
            s=(p := os.path.join(find_ctf_root_directory(), "challenges"))
        ):
            LOG.error(
                msg=f"Directory `{p}` not found. Make sure this script is ran from the root directory OR set the CTF_ROOT_DIR environment variable to the root directory."
            )
            exit(code=1)
    main()

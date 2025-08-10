#!/usr/bin/env python3
import logging
import os

import typer
from typer import Typer
from typing_extensions import Annotated

from ctf import ENV, LOG
from ctf.check import app as check_app
from ctf.deploy import app as deploy_app
from ctf.destroy import app as destroy_app
from ctf.flags import app as flags_app
from ctf.generate import app as generate_app
from ctf.init import app as init_app
from ctf.list import app as list_app
from ctf.new import app as new_app
from ctf.redeploy import app as redeploy_app
from ctf.services import app as services_app
from ctf.stats import app as stats_app
from ctf.utils import find_ctf_root_directory
from ctf.validate import app as validate_app
from ctf.version import app as version_app

app = Typer(
    help="CLI tool to manage CTF challenges as code. Run from the root CTF repo directory or set the CTF_ROOT_DIR environment variable to run the tool."
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


@app.callback()
def global_options(
    location: Annotated[
        str, typer.Option("--location", help="CTF root directory location.")
    ] = "",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable DEBUG logging.")
    ] = False,
):
    if verbose:
        LOG.setLevel(logging.DEBUG)
        LOG.handlers[0].setLevel(logging.DEBUG)

    if location:
        ENV["CTF_ROOT_DIR"] = location


def main():
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

#!/usr/bin/env python3
import os

from typer import Typer

from ctf import LOG
from ctf.utils import (
    CTF_ROOT_DIRECTORY,
)

try:
    import pybadges

    _has_pybadges = True
except ImportError:
    _has_pybadges = False

try:
    import matplotlib.pyplot as plt

    _has_matplotlib = True
except ImportError:
    _has_matplotlib = False

from validate import app as validate_app
from init import app as init_app
from new import app as new_app
from destroy import app as destroy_app
from flags import app as flags_app
from services import app as services_app
from generate import app as generate_app
from deploy import app as deploy_app
from redeploy import app as redeploy_app
from check import app as check_app
from stats import app as stats_app
from list import app as list_app
from version import app as version_app

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


def main():
    app()


if __name__ == "__main__":
    if not os.path.isdir(s=(p := os.path.join(CTF_ROOT_DIRECTORY, "challenges"))):
        import sys

        if "init" not in sys.argv:
            LOG.error(
                msg=f"Directory `{p}` not found. Make sure this script is ran from the root directory OR set the CTF_ROOT_DIR environment variable to the root directory."
            )
            exit(code=1)
    main()

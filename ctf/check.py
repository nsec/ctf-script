import os
import subprocess

import typer
from typing_extensions import Annotated

from ctf import CTF_ROOT_DIRECTORY, ENV
from ctf.generate import generate
from ctf.logger import LOG
from ctf.utils import check_git_lfs, terraform_binary

app = typer.Typer()


@app.command(help="Preview the changes")
def check(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Only check the given tracks (use the directory name)",
        ),
    ] = [],
    production: Annotated[
        bool,
        typer.Option(
            "--production",
            help="Do a production deployment. Only use this if you know what you're doing.",
        ),
    ] = False,
    remote: Annotated[
        str, typer.Option("--remote", help="Incus remote to deploy to")
    ] = "local",
) -> None:
    ENV["INCUS_REMOTE"] = remote
    # Run generate first.
    generate(tracks=tracks, production=production, remote=remote)

    # Then run terraform plan.
    subprocess.run(
        args=[terraform_binary(), "plan"],
        cwd=os.path.join(CTF_ROOT_DIRECTORY, ".deploy"),
        check=True,
    )

    # Check if Git LFS is installed on the system as it will be required for deployment.
    if not check_git_lfs():
        LOG.warning(
            msg="Git LFS is missing from  your system. Install it before deploying."
        )

import subprocess

import typer
from typing_extensions import Annotated

from ctf import ENV
from ctf.commands.generate import generate
from ctf.common.logger import LOG
from ctf.common.utils import check_git_lfs, find_ctf_root_directory, terraform_binary

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
            envvar="CTF_PRODUCTION",
            help="Do a production deployment. Only use this if you know what you're doing.",
        ),
    ] = False,
    remote: Annotated[
        str,
        typer.Option(
            "--remote",
            envvar="CTF_REMOTE",
            help="Incus remote to deploy to",
        ),
    ] = "local",
) -> None:
    ENV["INCUS_REMOTE"] = remote
    # Run generate first.
    generate(tracks=tracks, production=production, remote=remote)

    # Then run terraform plan.
    subprocess.run(
        args=[terraform_binary(), "plan"],
        cwd=find_ctf_root_directory() / ".deploy",
        check=True,
    )

    # Check if Git LFS is installed on the system as it will be required for deployment.
    if not check_git_lfs():
        LOG.warning(
            msg="Git LFS is missing from  your system. Install it before deploying."
        )

import typer
from typing_extensions import Annotated

from ctf import ENV
from ctf.deploy import deploy
from ctf.destroy import destroy

app = typer.Typer()


@app.command(help="Destroy and then deploy the given tracks")
def redeploy(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Only redeploy the given tracks (use the directory name)",
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
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="If there are artefacts remaining, delete them without asking.",
        ),
    ] = False,
    skip_build: Annotated[
        bool,
        typer.Option(
            "--skip-build",
            help="Skip build container. (Use this only if you already have the necessary locally for the deploy.yaml to work!)",
        ),
    ] = False,
) -> None:
    ENV["INCUS_REMOTE"] = remote
    destroy(tracks=tracks, production=production, remote=remote, force=force)
    deploy(
        tracks=tracks,
        production=production,
        remote=remote,
        redeploy=True,
        force=force,
        skip_build=skip_build,
    )

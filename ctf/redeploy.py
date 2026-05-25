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
    vm_remote: Annotated[
        str | None,
        typer.Option(
            "--vm-remote",
            envvar="CTF_VM_REMOTE",
            help="Incus remote for VM to be deployed to",
        ),
    ] = None,
    vm_project: Annotated[
        str | None,
        typer.Option(
            "--vm-project",
            envvar="CTF_VM_PROJECT",
            help="Incus project for VM to be deployed to",
        ),
    ] = None,
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
    skip_pre_common: Annotated[
        bool,
        typer.Option(
            "--skip-pre-common",
            help="Skip pre-common deployment Ansible script. Useful for Windows VM that crashes all the time. (Use this only if you already ran the pre-common once)",
        ),
    ] = False,
    skip_post_common: Annotated[
        bool,
        typer.Option(
            "--skip-post-common",
            help="Skip post-common deployment Ansible script. Useful for Windows VM. DO NOT USE IN PRODUCTION.",
        ),
    ] = False,
    exclude_tracks: Annotated[
        list[str],
        typer.Option(
            "--exclude",
            "-x",
            help="Exclude the list of provided tracks from redeployment.",
        ),
    ] = [],
) -> None:
    ENV["INCUS_REMOTE"] = remote
    destroy(
        tracks=tracks,
        production=production,
        remote=remote,
        force=force,
        exclude_tracks=exclude_tracks,
    )
    deploy(
        tracks=tracks,
        production=production,
        remote=remote,
        vm_remote=vm_remote,
        vm_project=vm_project,
        keep_already_deployed=True,
        force=force,
        skip_build=skip_build,
        skip_pre_common=skip_pre_common,
        skip_post_common=skip_post_common,
        exclude_tracks=exclude_tracks,
    )

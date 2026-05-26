import os
import subprocess

import typer
from typing_extensions import Annotated

from ctf import ENV
from ctf.common.logger import LOG
from ctf.common.models import Track
from ctf.common.utils import (
    add_tracks_to_terraform_modules,
    create_terraform_modules_file,
    does_track_require_build_container,
    find_ctf_root_directory,
    get_all_available_tracks,
    get_terraform_tracks_from_modules,
    terraform_binary,
    track_has_virtual_machine,
    validate_track_can_be_deployed,
)

app = typer.Typer()


@app.command(
    help="Generate the deployment files using `terraform init` and `terraform validate`"
)
def generate(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Only generate the given tracks (use the directory name)",
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
    keep_already_deployed: Annotated[
        bool, typer.Option("--keep", help="Keep already deployed tracks.")
    ] = False,
    exclude_tracks: Annotated[
        list[str],
        typer.Option(
            "--exclude",
            "-x",
            help="Exclude the list of provided tracks from generation.",
        ),
    ] = [],
) -> set[Track]:
    ENV["INCUS_REMOTE"] = remote
    # Get the list of tracks.
    distinct_tracks: set[Track] = set(
        track
        for track in get_all_available_tracks()
        if validate_track_can_be_deployed(track=track)
        and (not tracks or track.name in tracks)
        and track not in exclude_tracks
    )

    if distinct_tracks:
        LOG.debug(f"Found {len(distinct_tracks)} tracks")
        # Generate the Terraform modules file.
        if not keep_already_deployed:
            create_terraform_modules_file(remote=remote, production=production)

        tmp_tracks: set[Track] = set()
        for track in distinct_tracks:
            tmp_tracks.add(
                Track(
                    name=track.name,
                    remote=remote,
                    production=production,
                    require_build_container=does_track_require_build_container(track),
                    has_virtual_machine=track_has_virtual_machine(track),
                    vm_project=vm_project,
                    vm_remote=vm_remote,
                )
            )
        distinct_tracks = tmp_tracks

        add_tracks_to_terraform_modules(
            tracks=distinct_tracks - get_terraform_tracks_from_modules()
            if keep_already_deployed
            else distinct_tracks
        )

        for track in distinct_tracks:
            relpath = os.path.relpath(
                find_ctf_root_directory() / ".deploy" / "common",
                (
                    terraform_directory := (
                        find_ctf_root_directory()
                        / "challenges"
                        / track.name
                        / "terraform"
                    )
                ),
            )

            # If the file exists and is a symlink, refresh it by deleting it first.
            if (
                p := (terraform_directory / "variables.tf")
            ).exists() and p.is_symlink():
                p.unlink()

                LOG.debug(f"Refreshing symlink {p}.")

            if not p.exists():
                os.symlink(
                    src=os.path.join(relpath, "variables.tf"),
                    dst=p,
                )

                LOG.debug(f"Created symlink {p}.")

            # If the file exists and is a symlink, refresh it by deleting it first.
            if (p := (terraform_directory / "versions.tf")).exists() and p.is_symlink():
                p.unlink()

                LOG.debug(f"Refreshing symlink {p}.")

            if not p.exists():
                os.symlink(
                    src=os.path.join(relpath, "versions.tf"),
                    dst=p,
                )

                LOG.debug(f"Created symlink {p}.")

        subprocess.run(
            args=[terraform_binary(), "init", "-upgrade"],
            cwd=find_ctf_root_directory() / ".deploy",
            stdout=subprocess.DEVNULL,
            check=True,
        )
        subprocess.run(
            args=[terraform_binary(), "validate"],
            cwd=find_ctf_root_directory() / ".deploy",
            check=True,
        )
    else:
        LOG.critical("No track was found")
        exit(1)

    return distinct_tracks

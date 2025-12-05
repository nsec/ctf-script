import os
import subprocess

import typer
from typing_extensions import Annotated

from ctf import ENV
from ctf.logger import LOG
from ctf.models import Track
from ctf.utils import (
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
            help="Do a production deployment. Only use this if you know what you're doing.",
        ),
    ] = False,
    remote: Annotated[
        str, typer.Option("--remote", help="Incus remote to deploy to")
    ] = "local",
    redeploy: Annotated[
        bool, typer.Option("--redeploy", help="Do not use. Use `ctf redeploy` instead.")
    ] = False,
) -> set[Track]:
    ENV["INCUS_REMOTE"] = remote
    # Get the list of tracks.
    distinct_tracks: set[Track] = set(
        track
        for track in get_all_available_tracks()
        if validate_track_can_be_deployed(track=track)
        and (not tracks or track.name in tracks)
    )

    if distinct_tracks:
        LOG.debug(msg=f"Found {len(distinct_tracks)} tracks")
        # Generate the Terraform modules file.
        if not redeploy:
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
                )
            )
        distinct_tracks = tmp_tracks

        add_tracks_to_terraform_modules(
            tracks=distinct_tracks - get_terraform_tracks_from_modules()
            if redeploy
            else distinct_tracks
        )

        for track in distinct_tracks:
            relpath = os.path.relpath(
                os.path.join(find_ctf_root_directory(), ".deploy", "common"),
                (
                    terraform_directory := os.path.join(
                        find_ctf_root_directory(), "challenges", track.name, "terraform"
                    )
                ),
            )

            # If the file exists and is a symlink, refresh it by deleting it first.
            if os.path.exists(
                path=(p := os.path.join(terraform_directory, "variables.tf"))
            ) and os.path.islink(path=p):
                os.unlink(path=p)

                LOG.debug(msg=f"Refreshing symlink {p}.")

            if not os.path.exists(path=p):
                os.symlink(
                    src=os.path.join(relpath, "variables.tf"),
                    dst=p,
                )

                LOG.debug(msg=f"Created symlink {p}.")

            # If the file exists and is a symlink, refresh it by deleting it first.
            if os.path.exists(
                path=(p := os.path.join(terraform_directory, "versions.tf"))
            ) and os.path.islink(path=p):
                os.unlink(path=p)

                LOG.debug(msg=f"Refreshing symlink {p}.")

            if not os.path.exists(path=p):
                os.symlink(
                    src=os.path.join(relpath, "versions.tf"),
                    dst=p,
                )

                LOG.debug(msg=f"Created symlink {p}.")

        subprocess.run(
            args=[terraform_binary(), "init", "-upgrade"],
            cwd=os.path.join(find_ctf_root_directory(), ".deploy"),
            stdout=subprocess.DEVNULL,
            check=True,
        )
        subprocess.run(
            args=[terraform_binary(), "validate"],
            cwd=os.path.join(find_ctf_root_directory(), ".deploy"),
            check=True,
        )
    else:
        LOG.critical("No track was found")
        exit(code=1)

    return distinct_tracks

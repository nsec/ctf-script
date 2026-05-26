import json
import subprocess

import typer
from pydantic import ValidationError
from rich.prompt import Confirm
from typing_extensions import Annotated

from ctf import ENV
from ctf.common.logger import LOG
from ctf.common.models import Track
from ctf.common.utils import (
    find_ctf_root_directory,
    get_terraform_tracks_from_modules,
    remove_tracks_from_terraform_modules,
    terraform_binary,
)

app = typer.Typer()


@app.command(
    help="Destroy everything deployed by Terraform. This is a destructive operation."
)
def destroy(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Only destroy the given tracks (use the directory name)",
        ),
    ] = [],
    production: Annotated[
        bool,
        typer.Option(
            "--production",
            envvar="CTF_PRODUCTION",
            help="Do a production destruction. Only use this if you know what you're doing.",
        ),
    ] = False,
    remote: Annotated[
        str,
        typer.Option(
            "--remote",
            envvar="CTF_REMOTE",
            help="Incus remote from where to destroy",
        ),
    ] = "local",
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="If there are artefacts remaining, delete them without asking.",
        ),
    ] = False,
    exclude_tracks: Annotated[
        list[str],
        typer.Option(
            "--exclude",
            "-x",
            help="Exclude the list of provided tracks from destruction.",
        ),
    ] = [],
) -> None:
    ENV["INCUS_REMOTE"] = remote

    if not (find_ctf_root_directory() / ".deploy" / "modules.tf").exists():
        LOG.critical("Nothing to destroy.")
        exit(1)

    terraform_tracks: set[Track] = get_terraform_tracks_from_modules()

    total_deployed_tracks = len(terraform_tracks)

    terraform_tracks -= {Track(name=x) for x in exclude_tracks}

    current_project = Track(
        name=subprocess.run(
            args=["incus", "project", "get-current"],
            check=True,
            capture_output=True,
            env=ENV,
        )
        .stdout.decode()
        .strip()
    )

    tmp_tracks: set[Track] = {Track(name=x) for x in tracks}
    if tmp_tracks and tmp_tracks != terraform_tracks:
        terraform_tracks &= tmp_tracks

    if not terraform_tracks:
        LOG.warning("No track to destroy.")
        return

    if current_project in terraform_tracks:
        projects: set[Track] = {
            Track(name=project["name"])
            for project in json.loads(
                s=subprocess.run(
                    args=["incus", "project", "list", "--format=json"],
                    check=False,
                    capture_output=True,
                    env=ENV,
                ).stdout.decode()
            )
        }

        project_list = list((projects - terraform_tracks))
        if len(project_list) == 0:
            LOG.critical(
                "No project to switch to. This should never happen as the default should always exists."
            )
            exit(1)

        cmd = [
            "incus",
            "project",
            "switch",
            "default" if "default" in project_list else project_list[0].name,
        ]

        LOG.info(f"Running `{' '.join(cmd)}`")
        subprocess.run(args=cmd, check=True, env=ENV)

    subprocess.run(
        args=[
            terraform_binary(),
            "destroy",
            "-auto-approve",
            *(
                []  # If every track needs to be destroyed, destroy everything including the network zone as well.
                if total_deployed_tracks == len(terraform_tracks)
                else [
                    f"-target=module.track-{track.name}" for track in terraform_tracks
                ]
            ),
        ],
        cwd=find_ctf_root_directory() / ".deploy",
        check=False,
    )

    projects = {
        Track(name=project["name"])
        for project in json.loads(
            s=subprocess.run(
                args=["incus", "project", "list", "--format=json"],
                check=False,
                capture_output=True,
                env=ENV,
            ).stdout.decode()
        )
    }

    networks = set()
    for network in json.loads(
        s=subprocess.run(
            args=["incus", "network", "list", "--format=json"],
            check=False,
            capture_output=True,
            env=ENV,
        ).stdout.decode()
    ):
        try:
            networks.add(Track(name=network["name"]))
        except ValidationError:
            pass

    network_acls = {
        Track(name=network_acl["name"])
        for network_acl in json.loads(
            s=subprocess.run(
                args=["incus", "network", "acl", "list", "--format=json"],
                check=False,
                capture_output=True,
                env=ENV,
            ).stdout.decode()
        )
    }

    network_zones = {
        Track(name=network_zone["name"])
        for network_zone in json.loads(
            s=subprocess.run(
                args=["incus", "network", "zone", "list", "--format=json"],
                check=False,
                capture_output=True,
                env=ENV,
            ).stdout.decode()
        )
    }

    for module in terraform_tracks:
        if module in projects:
            LOG.warning(f"The project {module.name} was not destroyed properly.")
            if force or Confirm.ask("Do you want to destroy it?", default=True):
                subprocess.run(
                    args=["incus", "project", "delete", module.name, "--force"],
                    check=False,
                    capture_output=True,
                    input=b"yes\n",
                    env=ENV,
                )

        if (tmp_module_name := module.name[:15]) in networks:
            LOG.warning(f"The network {tmp_module_name} was not destroyed properly.")
            if force or Confirm.ask("Do you want to destroy it?", default=True):
                subprocess.run(
                    args=["incus", "network", "delete", tmp_module_name],
                    check=False,
                    capture_output=True,
                    env=ENV,
                )

        if (tmp_module := module) in network_acls or (
            tmp_module := Track(name=f"{module.name}-default")
        ) in network_acls:
            LOG.warning(
                f"The network ACL {tmp_module.name} was not destroyed properly."
            )
            if force or Confirm.ask("Do you want to destroy it?", default=True):
                subprocess.run(
                    args=["incus", "network", "acl", "delete", tmp_module.name],
                    check=False,
                    capture_output=True,
                    env=ENV,
                )

    if Track(name="ctf") in network_zones:
        LOG.warning('The network zone "ctf" was not destroyed properly.')
        if force or Confirm.ask("Do you want to destroy it?", default=True):
            subprocess.run(
                args=["incus", "network", "zone", "delete", "ctf"],
                check=False,
                capture_output=True,
                env=ENV,
            )

    if Track(name="simulated-production-acl") in network_acls:
        LOG.warning(
            'The network ACL "simulated-production-acl" was not destroyed properly.'
        )
        if force or Confirm.ask("Do you want to destroy it?", default=True):
            subprocess.run(
                args=["incus", "network", "acl", "delete", "simulated-production-acl"],
                check=False,
                capture_output=True,
                env=ENV,
            )

    remove_tracks_from_terraform_modules(
        tracks=terraform_tracks,
        remote=remote,
        production=production,
    )
    if total_deployed_tracks == len(terraform_tracks):
        LOG.info("Successfully destroyed every track")
    else:
        LOG.info(
            f"Successfully destroyed: {', '.join([track.name for track in terraform_tracks])}"
        )

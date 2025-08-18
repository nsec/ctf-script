import json
import os
import subprocess

import typer
from typing_extensions import Annotated

from ctf import ENV
from ctf.logger import LOG
from ctf.models import Track
from ctf.utils import (
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
) -> None:
    ENV["INCUS_REMOTE"] = remote
    LOG.info(msg="tofu destroy...")

    if not os.path.exists(
        path=os.path.join(find_ctf_root_directory(), ".deploy", "modules.tf")
    ):
        LOG.critical(msg="Nothing to destroy.")
        exit(code=1)

    terraform_tracks = get_terraform_tracks_from_modules()

    total_deployed_tracks = len(terraform_tracks)

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

    tmp_tracks: set[Track] = set(Track(name=x) for x in tracks)
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
                msg="No project to switch to. This should never happen as the default should always exists."
            )
            exit(code=1)

        cmd = [
            "incus",
            "project",
            "switch",
            "default" if "default" in project_list else project_list[0].name,
        ]

        LOG.info(msg=f"Running `{' '.join(cmd)}`")
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
        cwd=os.path.join(find_ctf_root_directory(), ".deploy"),
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

    networks = {
        Track(name=network["name"])
        for network in json.loads(
            s=subprocess.run(
                args=["incus", "network", "list", "--format=json"],
                check=False,
                capture_output=True,
                env=ENV,
            ).stdout.decode()
        )
    }

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

    for module in terraform_tracks:
        if module in projects:
            LOG.warning(msg=f"The project {module.name} was not destroyed properly.")
            if (
                force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    args=["incus", "project", "delete", module.name, "--force"],
                    check=False,
                    capture_output=True,
                    input=b"yes\n",
                    env=ENV,
                )

        if (tmp_module_name := module.name[0:15]) in networks:
            LOG.warning(
                msg=f"The network {tmp_module_name} was not destroyed properly."
            )
            if (
                force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    args=["incus", "network", "delete", tmp_module_name],
                    check=False,
                    capture_output=True,
                    env=ENV,
                )

        if (tmp_module := module) in network_acls or (
            tmp_module := f"{module.name}-default"
        ) in network_acls:
            LOG.warning(
                msg=f"The network ACL {tmp_module.name} was not destroyed properly."
            )
            if (
                force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    args=["incus", "network", "acl", "delete", tmp_module.name],
                    check=False,
                    capture_output=True,
                    env=ENV,
                )

    remove_tracks_from_terraform_modules(
        tracks=terraform_tracks,
        remote=remote,
        production=production,
    )
    LOG.info(msg="Successfully destroyed every track")

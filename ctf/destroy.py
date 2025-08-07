import json
import os
import subprocess

import typer
from typing_extensions import Annotated

from ctf import CTF_ROOT_DIRECTORY, ENV
from ctf.logger import LOG
from ctf.utils import (
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
        path=os.path.join(CTF_ROOT_DIRECTORY, ".deploy", "modules.tf")
    ):
        LOG.critical(msg="Nothing to destroy.")
        exit(code=1)

    terraform_tracks = get_terraform_tracks_from_modules()

    r = (
        subprocess.run(
            args=["incus", "project", "get-current"],
            check=True,
            capture_output=True,
            env=ENV,
        )
        .stdout.decode()
        .strip()
    )

    tmp_tracks = set(tracks)
    if tmp_tracks and tmp_tracks != terraform_tracks:
        terraform_tracks &= tmp_tracks
        if not terraform_tracks:
            LOG.warning("No track to destroy.")
            return

    if r in terraform_tracks:
        projects = {
            project["name"]
            for project in json.loads(
                s=subprocess.run(
                    args=["incus", "project", "list", "--format=json"],
                    check=False,
                    capture_output=True,
                    env=ENV,
                ).stdout.decode()
            )
        }

        projects = list((projects - terraform_tracks))
        if len(projects) == 0:
            LOG.critical(
                msg="No project to switch to. This should never happen as the default should always exists."
            )
            exit(code=1)

        cmd = [
            "incus",
            "project",
            "switch",
            "default" if "default" in projects else projects[0],
        ]

        LOG.info(msg=f"Running `{' '.join(cmd)}`")
        subprocess.run(args=cmd, check=True, env=ENV)

    subprocess.run(
        args=[
            terraform_binary(),
            "destroy",
            "-auto-approve",
            *[f"-target=module.track-{track}" for track in terraform_tracks],
        ],
        cwd=os.path.join(CTF_ROOT_DIRECTORY, ".deploy"),
        check=False,
    )

    projects = [
        project["name"]
        for project in json.loads(
            s=subprocess.run(
                args=["incus", "project", "list", "--format=json"],
                check=False,
                capture_output=True,
                env=ENV,
            ).stdout.decode()
        )
    ]

    networks = [
        network["name"]
        for network in json.loads(
            s=subprocess.run(
                args=["incus", "network", "list", "--format=json"],
                check=False,
                capture_output=True,
                env=ENV,
            ).stdout.decode()
        )
    ]

    network_acls = [
        network_acl["name"]
        for network_acl in json.loads(
            s=subprocess.run(
                args=["incus", "network", "acl", "list", "--format=json"],
                check=False,
                capture_output=True,
                env=ENV,
            ).stdout.decode()
        )
    ]

    for module in terraform_tracks:
        if module in projects:
            LOG.warning(msg=f"The project {module} was not destroyed properly.")
            if (
                force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    args=["incus", "project", "delete", module, "--force"],
                    check=False,
                    capture_output=True,
                    input=b"yes\n",
                    env=ENV,
                )

        if (tmp_module := module[0:15]) in networks:
            LOG.warning(msg=f"The network {tmp_module} was not destroyed properly.")
            if (
                force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    args=["incus", "network", "delete", tmp_module],
                    check=False,
                    capture_output=True,
                    env=ENV,
                )

        if (tmp_module := module) in network_acls or (
            tmp_module := f"{module}-default"
        ) in network_acls:
            LOG.warning(msg=f"The network ACL {tmp_module} was not destroyed properly.")
            if (
                force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    args=["incus", "network", "acl", "delete", tmp_module],
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

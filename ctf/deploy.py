import json
import os
import shutil
import subprocess
import textwrap

import typer
from typing_extensions import Annotated

from ctf import CTF_ROOT_DIRECTORY, ENV
from ctf.destroy import destroy
from ctf.generate import generate
from ctf.logger import LOG
from ctf.utils import (
    add_tracks_to_terraform_modules,
    check_git_lfs,
    get_all_available_tracks,
    get_terraform_tracks_from_modules,
    parse_track_yaml,
    terraform_binary,
    validate_track_can_be_deployed,
)

app = typer.Typer()


@app.command(help="Deploy and provision the tracks")
def deploy(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Only deploy the given tracks (use the directory name)",
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
    force: Annotated[
        bool,
        typer.Option("--force", help="Force the deployment even if there are errors."),
    ] = False,
):
    ENV["INCUS_REMOTE"] = remote
    if redeploy:
        distinct_tracks = set(
            track
            for track in get_all_available_tracks()
            if validate_track_can_be_deployed(track=track) and track in tracks
        )

        add_tracks_to_terraform_modules(
            tracks=distinct_tracks - get_terraform_tracks_from_modules(),
            remote=remote,
            production=production,
        )
    else:
        # Run generate first.
        distinct_tracks = generate(tracks=tracks, production=production, remote=remote)

    # Check if Git LFS is installed on the system as it is required for deployment.
    if not check_git_lfs():
        LOG.critical(
            msg="Git LFS is missing from  your system. Install it before deploying."
        )
        exit(code=1)

    # Pull LFS files
    LOG.debug("Pulling Git LFS files for specific tracks.")
    subprocess.run(
        args=[
            "git",
            "lfs",
            "pull",
            f"--include={','.join([os.path.join('challenges', track, 'ansible', '*') for track in distinct_tracks])}",
        ],
        check=True,
    )

    try:
        subprocess.run(
            args=[terraform_binary(), "apply", "-auto-approve"],
            cwd=os.path.join(CTF_ROOT_DIRECTORY, ".deploy"),
            check=True,
        )
    except subprocess.CalledProcessError:
        LOG.warning(
            f"The project could not deploy due to instable state. It is often due to CTRL+C while deploying as {os.path.basename(terraform_binary())} was not able to save the state of each object created."
        )

        if (input("Do you want to clean and start over? [Y/n] ").lower() or "y") != "y":
            exit(code=1)

        force = True
        destroy(tracks=tracks, production=production, remote=remote, force=force)

        subprocess.run(
            args=[terraform_binary(), "apply", "-auto-approve"],
            cwd=os.path.join(CTF_ROOT_DIRECTORY, ".deploy"),
            check=True,
        )
    except KeyboardInterrupt:
        LOG.warning(
            "CTRL+C was detected during Terraform deployment. Destroying everything..."
        )
        force = True
        destroy(tracks=tracks, production=production, remote=remote, force=force)
        exit(code=0)

    for track in distinct_tracks:
        if not os.path.exists(
            path=(
                path := os.path.join(CTF_ROOT_DIRECTORY, "challenges", track, "ansible")
            )
        ):
            continue

        run_ansible_playbook(
            remote=remote, production=production, track=track, path=path
        )

        if not production:
            incus_list = json.loads(
                s=subprocess.run(
                    args=["incus", "list", f"--project={track}", "--format", "json"],
                    check=True,
                    capture_output=True,
                    env=ENV,
                ).stdout.decode()
            )
            ipv6_to_container_name = {}
            for machine in incus_list:
                addresses = machine["state"]["network"]["eth0"]["addresses"]
                ipv6_address = list(
                    filter(lambda address: address["family"] == "inet6", addresses)
                )[0]["address"]
                ipv6_to_container_name[ipv6_address] = machine["name"]

            LOG.debug(msg=f"Mapping: {ipv6_to_container_name}")

            if remote == "local":
                LOG.debug(msg=f"Parsing track.yaml for track {track}")
                track_yaml = parse_track_yaml(track_name=track)

                for service in track_yaml["services"]:
                    if service.get("dev_port_mapping"):
                        LOG.debug(
                            f"Adding incus proxy for service {track}-{service['name']}-port-{service['port']}"
                        )
                        machine_name = ipv6_to_container_name[
                            service["address"]
                            .replace(":0", ":")
                            .replace(":0", ":")
                            .replace(":0", ":")
                            .replace(":0", ":")
                        ]
                        subprocess.run(
                            args=[
                                "incus",
                                "config",
                                "device",
                                "add",
                                machine_name,
                                f"proxy-{track}-{service['dev_port_mapping']}-to-{service['port']}",
                                "proxy",
                                f"listen=tcp:0.0.0.0:{service['dev_port_mapping']}",
                                f"connect=tcp:127.0.0.1:{service['port']}",
                                "--project",
                                track,
                            ],
                            cwd=path,
                            check=True,
                        )

            LOG.info(msg=f"Running `incus --project={track} list`")
            subprocess.run(
                args=["incus", f"--project={track}", "list"], check=True, env=ENV
            )

    if not production and distinct_tracks:
        tracks_list = list(distinct_tracks)
        track_index = input(
            textwrap.dedent(
                f"""\
                Do you want to `incus project switch` to any of the tracks mentioned in argument?
                {chr(10).join([f"{list(tracks_list).index(t) + 1}) {t}" for t in tracks_list])}

                Which? """
            )
        )

        if (
            track_index.isnumeric()
            and (track_index := int(track_index))
            and 0 < track_index <= len(tracks_list)
        ):
            LOG.info(
                msg=f"Running `incus project switch {tracks_list[track_index - 1]}`"
            )
            subprocess.run(
                args=["incus", "project", "switch", tracks_list[track_index - 1]],
                check=True,
                env=ENV,
            )
        elif track_index:
            LOG.warning(
                msg=f"Could not switch project, unrecognized input: {track_index}."
            )


def run_ansible_playbook(remote: str, production: bool, track: str, path: str) -> None:
    extra_args = []
    if remote:
        extra_args += ["-e", f"ansible_incus_remote={remote}"]

    if production:
        extra_args += ["-e", "nsec_production=true"]

    LOG.info(msg=f"Running common yaml with ansible for track {track}...")
    ansible_args = [
        "ansible-playbook",
        "../../../.deploy/common.yaml",
        "-i",
        "inventory",
    ] + extra_args
    subprocess.run(
        args=ansible_args,
        cwd=path,
        check=True,
    )

    LOG.info(msg=f"Running deploy.yaml with ansible for track {track}...")
    ansible_args = [
        "ansible-playbook",
        "deploy.yaml",
        "-i",
        "inventory",
    ] + extra_args
    subprocess.run(
        args=ansible_args,
        cwd=path,
        check=True,
    )

    artifacts_path = os.path.join(path, "artifacts")
    if os.path.exists(path=artifacts_path):
        shutil.rmtree(artifacts_path)

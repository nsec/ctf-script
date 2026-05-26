import json
import os
import shutil
import subprocess
import textwrap
import time
from pathlib import Path

import typer
from rich.prompt import IntPrompt
from typing_extensions import Annotated

from ctf import ENV, STATE
from ctf.commands.destroy import destroy
from ctf.commands.generate import generate
from ctf.common.logger import LOG
from ctf.common.models import Track, TrackYaml
from ctf.common.utils import (
    add_tracks_to_terraform_modules,
    check_git_lfs,
    find_ctf_root_directory,
    parse_track_yaml,
    remove_tracks_from_terraform_modules,
    terraform_binary,
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
    force: Annotated[
        bool,
        typer.Option("--force", help="Force the deployment even if there are errors."),
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
            help="Exclude the list of provided tracks from deployment.",
        ),
    ] = [],
):
    ENV["INCUS_REMOTE"] = remote
    # Run generate first.
    distinct_tracks = generate(
        tracks=tracks,
        exclude_tracks=exclude_tracks,
        production=production,
        remote=remote,
        vm_remote=vm_remote,
        vm_project=vm_project,
        keep_already_deployed=keep_already_deployed,
    )

    # Check if Git LFS is installed on the system as it is required for deployment.
    if not check_git_lfs():
        LOG.critical(
            "Git LFS is missing from  your system. Install it before deploying."
        )
        exit(1)

    # Pull LFS files
    LOG.debug("Pulling Git LFS files for specific tracks.")
    subprocess.run(
        args=[
            "git",
            "lfs",
            "pull",
            f"--include={','.join([os.path.join('challenges', track.name, 'ansible', '*') for track in distinct_tracks])}",
        ],
        check=True,
    )

    if regenerated_tracks := terraform_apply(
        tracks=tracks,
        exclude_tracks=exclude_tracks,
        production=production,
        remote=remote,
        vm_remote=vm_remote,
        vm_project=vm_project,
    ):
        distinct_tracks = regenerated_tracks

    # Starting a timer for tracks with a virtual machine in them.
    start_timer: float = time.time()

    for track in sorted(
        distinct_tracks,
        key=lambda t: (
            t.has_virtual_machine,
            t.name,
        ),  # Running ansible on containers first then virtual machines
    ):
        if not skip_build and track.require_build_container:
            run_ansible_playbook(
                remote=remote,
                production=production,
                track=track.name,
                path=find_ctf_root_directory() / "challenges" / track.name / "ansible",
                playbook="build.yaml",
                vm_remote=vm_remote,
                vm_project=vm_project,
                execute_common=False,
            )

            if production:
                track.require_build_container = False
                remove_tracks_from_terraform_modules(
                    {track}, remote=remote, production=production
                )
                add_tracks_to_terraform_modules({track})

                if regenerated_tracks := terraform_apply(
                    tracks=tracks,
                    exclude_tracks=exclude_tracks,
                    production=production,
                    remote=remote,
                    vm_remote=vm_remote,
                    vm_project=vm_project,
                ):
                    distinct_tracks = regenerated_tracks

        if not (
            path := find_ctf_root_directory() / "challenges" / track.name / "ansible"
        ).exists():
            continue

        if track.has_virtual_machine:
            incus_list = json.loads(
                subprocess.run(
                    args=["incus", "list", f"--project={track}", "--format", "json"],
                    check=True,
                    capture_output=True,
                    env=ENV,
                ).stdout.decode()
            )

            # Waiting for virtual machine to be up and running
            # Starting with a minute
            if start_timer > time.time() - (seconds := 30):
                for machine in incus_list:
                    if machine["type"] != "virtual-machine":
                        continue

                    cmd: str = "whoami"  # Should works on most OS
                    while start_timer > time.time() - seconds:
                        # Avoid spamming too much, sleeping for a second between each request.
                        time.sleep(1)

                        s = subprocess.run(
                            args=[
                                "incus",
                                "exec",
                                f"--project={track}",
                                "-T",
                                machine["name"],
                                "--",
                                cmd,
                            ],
                            capture_output=True,
                            env=ENV,
                        )

                        match s.returncode:
                            case 127:
                                # If "whoami" is not found by the OS, change the command to sleep as it is most likely Linux.
                                LOG.debug(
                                    f'Command not found, changing it to "{(cmd := "sleep 0")}".'
                                )
                                start_timer = time.time()
                            case 0:
                                LOG.info("Agent is up and running!")
                                break
                            case _:
                                LOG.info(
                                    f"Waiting for the virtual machine to be ready. Remaining {(seconds - (time.time() - start_timer)):.1f} seconds..."
                                )

        run_ansible_playbook(
            remote=remote,
            production=production,
            track=track.name,
            path=path,
            vm_remote=vm_remote,
            vm_project=vm_project,
            skip_pre_common=skip_pre_common,
            skip_post_common=skip_post_common,
        )

        track.already_deployed = True
        remove_tracks_from_terraform_modules(
            {track}, remote=remote, production=production
        )
        add_tracks_to_terraform_modules({track})

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
                if machine["type"] == "virtual-machine":
                    continue
                addresses = machine["state"]["network"]["eth0"]["addresses"]
                ipv6_address = list(
                    filter(lambda address: address["family"] == "inet6", addresses)
                )[0]["address"]
                ipv6_to_container_name[ipv6_address] = machine["name"]

            LOG.debug(f"Mapping: {ipv6_to_container_name}")

            if remote == "local":
                LOG.debug(f"Parsing track.yaml for track {track}")
                track_yaml: TrackYaml = TrackYaml.model_validate(
                    parse_track_yaml(track_name=track.name)
                )

                services: dict[str, dict[str, str | int | None]] = {}

                if track_yaml.instances:
                    for k, v in track_yaml.instances.root.items():
                        for service in v.services:
                            if not service.dev_port_mapping:
                                continue
                            services[service.name] = {
                                **service.model_dump(),
                                "address": v.ipv6,
                            }

                for service_name, service in services.items():
                    if (
                        service.get("dev_port_mapping")
                        and (
                            str(service["address"])
                            .replace(":0", ":")
                            .replace(":0", ":")
                            .replace(":0", ":")
                            .replace(":0", ":")
                        )
                        in ipv6_to_container_name
                    ):
                        LOG.debug(
                            f"Adding incus proxy for service {track}-{service_name}-port-{service['port']}"
                        )
                        machine_name = ipv6_to_container_name[
                            str(service["address"])
                            .replace(":0", ":")
                            .replace(":0", ":")
                            .replace(":0", ":")
                            .replace(":0", ":")
                        ]
                        subprocess.run(
                            args=[
                                "incus",
                                f"--project={track.name}",
                                "config",
                                "device",
                                "add",
                                machine_name,
                                f"proxy-{track.name}-{service['dev_port_mapping']}-to-{service['port']}",
                                "proxy",
                                f"listen=tcp:0.0.0.0:{service['dev_port_mapping']}",
                                f"connect=tcp:127.0.0.1:{service['port']}",
                            ],
                            cwd=path,
                            check=True,
                        )

            LOG.info(f"Running `incus --project={track} list`")
            subprocess.run(
                args=["incus", f"--project={track}", "list"], check=True, env=ENV
            )

    if distinct_tracks:
        LOG.info("Applying post-deploy Terraform resources...")
        try:
            terraform_apply(
                tracks=tracks,
                exclude_tracks=exclude_tracks,
                production=production,
                remote=remote,
                vm_remote=vm_remote,
                vm_project=vm_project,
            )
        except subprocess.CalledProcessError:
            LOG.critical(
                "Could not apply post-deploy Terraform resources. Fix the Terraform configuration and rerun `ctf deploy`."
            )
            exit(1)

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
            LOG.info(f"Running `incus project switch {tracks_list[track_index - 1]}`")
            subprocess.run(
                args=["incus", "project", "switch", tracks_list[track_index - 1].name],
                check=True,
                env=ENV,
            )
        elif track_index:
            LOG.warning(f"Could not switch project, unrecognized input: {track_index}.")


def terraform_apply(
    tracks: list[str],
    exclude_tracks: list[str],
    production: bool,
    remote: str,
    vm_remote: str | None = None,
    vm_project: str | None = None,
) -> set[Track]:
    args = [terraform_binary(), "apply", "-auto-approve"]

    try:
        subprocess.run(
            args=args,
            cwd=find_ctf_root_directory() / ".deploy",
            check=True,
        )
    except subprocess.CalledProcessError:
        LOG.warning(
            f"The project could not deploy due to instable state. It is often due to CTRL+C while deploying as {os.path.basename(terraform_binary())} was not able to save the state of each object created."
        )

        match IntPrompt.ask(
            "Do you want to start over (1), clean up (2) or quit (3)?",
            choices=["1", "2", "3"],
            default=1,
        ):
            case 1:
                destroy(
                    tracks=tracks,
                    exclude_tracks=exclude_tracks,
                    production=production,
                    remote=remote,
                    force=True,
                )

                distinct_tracks = generate(
                    tracks=tracks,
                    exclude_tracks=exclude_tracks,
                    production=production,
                    remote=remote,
                    vm_remote=vm_remote,
                    vm_project=vm_project,
                )

                subprocess.run(
                    args=args,
                    cwd=find_ctf_root_directory() / ".deploy",
                    check=True,
                )

                return distinct_tracks
            case 2:
                destroy(
                    tracks=tracks,
                    exclude_tracks=exclude_tracks,
                    production=production,
                    remote=remote,
                    force=True,
                )
                exit(0)
            case 3:
                exit(1)

    except KeyboardInterrupt:
        LOG.warning(
            "CTRL+C was detected during Terraform deployment. Destroying everything..."
        )
        destroy(
            tracks=tracks,
            exclude_tracks=exclude_tracks,
            production=production,
            remote=remote,
            force=True,
        )
        exit(0)

    return set()


def run_ansible_playbook(
    remote: str,
    production: bool,
    track: str,
    path: Path,
    playbook: str = "deploy.yaml",
    vm_remote: str | None = None,
    vm_project: str | None = None,
    execute_common: bool = True,
    skip_pre_common: bool = False,
    skip_post_common: bool = False,
) -> None:
    extra_args = []
    if STATE["verbose"]:
        extra_args.append("-vvv")

    extra_args += [
        "-e",
        f"ansible_incus_container_remote={remote}",
        "-e",
        f"ansible_incus_vm_remote={vm_remote if vm_remote else remote}",
        "-e",
        f"ansible_incus_vm_project={vm_project if vm_project else track}",
    ]

    if production:
        extra_args += ["-e", "nsec_production=true"]

    if not skip_pre_common and execute_common:
        LOG.info(f"Running pre-common.yaml with ansible for track {track}...")
        ansible_args = [
            "ansible-playbook",
            os.path.join("..", "..", "..", ".deploy", "ansible", "common.yaml"),
            "-i",
            "inventory",
        ] + extra_args
        subprocess.run(
            args=ansible_args,
            cwd=path,
            check=True,
        )

    LOG.info(f"Running {playbook} with ansible for track {track}...")
    ansible_args = [
        "ansible-playbook",
        playbook,
        "-i",
        "inventory",
    ] + extra_args
    subprocess.run(args=ansible_args, cwd=path, check=True)

    if not skip_post_common and execute_common:
        LOG.info(f"Running post-common.yaml with ansible for track {track}...")
        ansible_args = (
            [
                "ansible-playbook",
                os.path.join("..", "..", "..", ".deploy", "ansible", "common.yaml"),
                "-i",
                "inventory",
            ]
            + extra_args
            + ["-e", "nsec_post_deployment=true"]
        )
        subprocess.run(
            args=ansible_args,
            cwd=path,
            check=True,
        )

    if (artifacts_path := path / "artifacts").exists():
        shutil.rmtree(artifacts_path)

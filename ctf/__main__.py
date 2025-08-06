#!/usr/bin/env python3
import csv
import io
import json
import logging
import os
import re
import secrets
import shutil
import statistics
import subprocess
import textwrap
from datetime import datetime
from enum import Enum, unique

import jinja2
import typer
import yaml
from tabulate import tabulate
from typer import Typer
from typing_extensions import Annotated

from ctf import CTF_ROOT_DIRECTORY, ENV, LOG
from ctf.utils import (
    add_tracks_to_terraform_modules,
    available_incus_remotes,
    check_git_lfs,
    create_terraform_modules_file,
    get_all_available_tracks,
    get_ctf_script_schemas_directory,
    get_ctf_script_templates_directory,
    get_terraform_tracks_from_modules,
    parse_post_yamls,
    parse_track_yaml,
    remove_tracks_from_terraform_modules,
    validate_track_can_be_deployed,
)
from ctf.validate_json_schemas import validate_with_json_schemas
from ctf.validators import (
    ValidationError,
    validators_list,
)

try:
    import pybadges

    _has_pybadges = True
except ImportError:
    _has_pybadges = False

try:
    import matplotlib.pyplot as plt

    _has_matplotlib = True
except ImportError:
    _has_matplotlib = False

TEMPLATES_ROOT_DIRECTORY = get_ctf_script_templates_directory()
SCHEMAS_ROOT_DIRECTORY = get_ctf_script_schemas_directory()
AVAILABLE_INCUS_REMOTES = available_incus_remotes()

app = Typer(help="CLI tool to manage CTF challenges as code. Run from the root CTF repo directory or set the CTF_ROOT_DIR environment variable to run the tool.")


@unique
class Template(Enum):
    APACHE_PHP = "apache-php"
    PYTHON_SERVICE = "python-service"
    FILES_ONLY = "files-only"
    TRACK_YAML_ONLY = "track-yaml-only"
    RUST_WEBSERVICE = "rust-webservice"

    def __str__(self) -> str:
        return self.value


@unique
class OutputFormat(Enum):
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"

    def __str__(self) -> str:
        return self.value


def terraform_binary() -> str:
    path = shutil.which(cmd="tofu")
    if not path:
        path = shutil.which(cmd="terraform")

    if not path:
        raise Exception("Couldn't find Terraform or OpenTofu")

    return path


@app.command(help="Initialize a directory with the default CTF structure. If the directory does not exist, it will be created.")
def init(path: Annotated[str, typer.Argument(help="Directory in which to initialize a CTF")] = CTF_ROOT_DIRECTORY,
         force: Annotated[bool, typer.Option("--force", help="Overwrite the directory if it's already initialized")] = False) -> None:
    created_directory = False
    created_assets: list[str] = []
    try:
        if not os.path.isdir(path):
            os.mkdir(path)
            LOG.info(f'Creating directory "{path}"')
            created_directory = True
        elif (
            os.path.isdir(os.path.join(path, "challenges"))
            or os.path.isdir(os.path.join(path, ".deploy"))
        ) and not force:
            LOG.error(
                f'Directory "{path}" is already initialized. Use --force to overwrite.'
            )
            LOG.error(force)
            exit(code=1)


        for asset in os.listdir(p := os.path.join(TEMPLATES_ROOT_DIRECTORY, "init")):
            dst_asset = os.path.join(path, asset)
            if os.path.isdir(src_asset := os.path.join(p, asset)):
                shutil.copytree(src_asset, dst_asset, dirs_exist_ok=True)
                LOG.info(f'Created "{dst_asset}" folder')
            else:
                shutil.copy(src_asset, dst_asset)
                LOG.info(f'Created "{dst_asset}" file')

            created_assets.append(dst_asset)

    except Exception:
        import traceback

        if created_directory:
            shutil.rmtree(path)
            LOG.info(f'Removed created "{path}" folder')
        else:
            for asset in created_assets:
                if os.path.isdir(asset):
                    shutil.rmtree(asset)
                    LOG.info(f'Removed created "{asset}" folder')
                else:
                    os.unlink(asset)
                    LOG.info(f'Removed created "{asset}" file')

        LOG.critical(traceback.format_exc())


@app.command(help="Create a new CTF track with a given name")
def new(name: Annotated[str, typer.Option(help="Track name. No space, use underscores if needed.", prompt="Track name. No space, use underscores if needed.")],
        template: Annotated[Template, typer.Option("--template", "-t", help="Template to use for the track.")] = Template.APACHE_PHP,
        force: Annotated[bool, typer.Option("--force", help="If directory already exists, delete it and create it again.")] = False) -> None:
    LOG.info(msg=f"Creating a new track: {name}")
    if not re.match(pattern=r"^[a-z][a-z0-9\-]{0,61}[a-z0-9]$", string=name):
        LOG.critical(
            msg="""The track name Valid instance names must fulfill the following requirements:
* The name must be between 1 and 63 characters long;
* The name must contain only letters, numbers and dashes from the ASCII table;
* The name must not start with a digit or a dash;
* The name must not end with a dash."""
        )
        exit(code=1)

    if os.path.exists(
        path=(
            new_challenge_directory := os.path.join(
                CTF_ROOT_DIRECTORY, "challenges", name
            )
        )
    ):
        if force:
            LOG.debug(msg=f"Deleting {new_challenge_directory}")
            shutil.rmtree(new_challenge_directory)
        else:
            LOG.critical(
                "Track already exists with that name. Use `--force` to overwrite the track."
            )
            exit(code=1)

    os.mkdir(new_challenge_directory)

    LOG.debug(msg=f"Directory {new_challenge_directory} created.")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            searchpath=TEMPLATES_ROOT_DIRECTORY, encoding="utf-8"
        )
    )

    ipv6_subnet = f"9000:d37e:c40b:{secrets.choice('0123456789abcdef')}{secrets.choice('0123456789abcdef')}{secrets.choice('0123456789abcdef')}{secrets.choice('0123456789abcdef')}"

    rb = [
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
        secrets.choice("0123456789abcdef"),
    ]
    hardware_address = f"00:16:3e:{rb[0]}{rb[1]}:{rb[2]}{rb[3]}:{rb[4]}{rb[5]}"
    ipv6_address = f"216:3eff:fe{rb[0]}{rb[1]}:{rb[2]}{rb[3]}{rb[4]}{rb[5]}"
    full_ipv6_address = f"{ipv6_subnet}:{ipv6_address}"

    track_template = env.get_template(name="track.yaml.j2")
    render = track_template.render(
        data={
            "name": name,
            "full_ipv6_address": full_ipv6_address,
            "ipv6_subnet": ipv6_subnet,
            "template": template.value,
        }
    )
    with open(
        file=(p := os.path.join(new_challenge_directory, "track.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    posts_directory = os.path.join(new_challenge_directory, "posts")

    os.mkdir(path=posts_directory)

    LOG.debug(msg=f"Directory {posts_directory} created.")

    track_template = env.get_template(name="topic.yaml.j2")
    render = track_template.render(data={"name": name})
    with open(
        file=(p := os.path.join(posts_directory, f"{name}.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    track_template = env.get_template(name="post.yaml.j2")
    render = track_template.render(data={"name": name})
    with open(
        file=(p := os.path.join(posts_directory, f"{name}_flag1.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    if template == Template.TRACK_YAML_ONLY:
        return

    files_directory = os.path.join(new_challenge_directory, "files")

    os.mkdir(path=files_directory)

    LOG.debug(msg=f"Directory {files_directory} created.")

    if template == Template.FILES_ONLY:
        return

    terraform_directory = os.path.join(new_challenge_directory, "terraform")

    os.mkdir(path=terraform_directory)

    LOG.debug(msg=f"Directory {terraform_directory} created.")

    track_template = env.get_template(name="main.tf.j2")

    render = track_template.render(
        data={
            "name": name,
            "hardware_address": hardware_address,
            "ipv6": ipv6_address,
            "ipv6_subnet": ipv6_subnet,
            "full_ipv6_address": full_ipv6_address,
        }
    )
    with open(
        file=(p := os.path.join(terraform_directory, "main.tf")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    relpath = os.path.relpath(
        os.path.join(CTF_ROOT_DIRECTORY, ".deploy", "common"), terraform_directory
    )

    os.symlink(
        src=os.path.join(relpath, "variables.tf"),
        dst=(p := os.path.join(terraform_directory, "variables.tf")),
    )

    LOG.debug(msg=f"Wrote {p}.")

    os.symlink(
        src=os.path.join(relpath, "versions.tf"),
        dst=(p := os.path.join(terraform_directory, "versions.tf")),
    )

    LOG.debug(msg=f"Wrote {p}.")

    ansible_directory = os.path.join(new_challenge_directory, "ansible")

    os.mkdir(path=ansible_directory)

    LOG.debug(msg=f"Directory {ansible_directory} created.")

    track_template = env.get_template(name=f"deploy-{template}.yaml.j2")
    render = track_template.render(data={"name": name})
    with open(
        file=(p := os.path.join(ansible_directory, "deploy.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    track_template = env.get_template(name="inventory.j2")
    render = track_template.render(data={"name": name})
    with open(
        file=(p := os.path.join(ansible_directory, "inventory")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    ansible_challenge_directory = os.path.join(ansible_directory, "challenge")

    os.mkdir(path=ansible_challenge_directory)

    LOG.debug(msg=f"Directory {ansible_challenge_directory} created.")

    if template == Template.APACHE_PHP:
        track_template = env.get_template(name="index.php.j2")
        render = track_template.render(data={"name": name})
        with open(
            file=(p := os.path.join(ansible_challenge_directory, "index.php")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)

        LOG.debug(msg=f"Wrote {p}.")

    if template == Template.PYTHON_SERVICE:
        track_template = env.get_template(name="app.py.j2")
        render = track_template.render(data={"name": name})
        with open(
            file=(p := os.path.join(ansible_challenge_directory, "app.py")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)

        LOG.debug(msg=f"Wrote {p}.")

        with open(
            file=(p := os.path.join(ansible_challenge_directory, "flag-1.txt")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(f"{{{{ track_flags.{name}_flag_1 }}}} (1/2)\n")

        LOG.debug(msg=f"Wrote {p}.")

    if template == Template.RUST_WEBSERVICE:
        # Copy the entire challenge template
        shutil.copytree(
            os.path.join(TEMPLATES_ROOT_DIRECTORY, "rust-webservice"),
            ansible_challenge_directory,
            dirs_exist_ok=True,
        )
        LOG.debug(msg=f"Wrote files to {ansible_challenge_directory}")

        manifest_template = env.get_template(name="Cargo.toml.j2")
        render = manifest_template.render(data={"name": name})
        with open(
            file=(p := os.path.join(ansible_challenge_directory, "Cargo.toml")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)

        LOG.debug(msg=f"Wrote {p}.")


@app.command(help="Destroy everything deployed by Terraform. This is a destructive operation.")
def destroy(
        tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Only destroy the given tracks (use the directory name)")] = [],
        production: Annotated[bool, typer.Option("--production", help="Do a production deployment. Only use this if you know what you're doing.")] = False,
        remote: Annotated[str, typer.Option("--remote", help="Incus remote to deploy to")] = "local",
        force: Annotated[bool, typer.Option("--force", help="If there are artefacts remaining, delete them without asking.")] = False
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

    tracks = set(tracks)
    if tracks and tracks != terraform_tracks:
        terraform_tracks &= tracks
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


@app.command(help="Get flags from tracks")
def flags(tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Only flags from the given tracks (use the directory name)")] = [],
          format: Annotated[OutputFormat, typer.Option("--format", help="Output format", prompt="Output format")] = OutputFormat.JSON) -> None:
    distinct_tracks = set()
    print(tracks)
    for entry in os.listdir(
        path=(challenges_directory := os.path.join(CTF_ROOT_DIRECTORY, "challenges"))
    ):
        if os.path.isdir(
            s=(track_directory := os.path.join(challenges_directory, entry))
        ) and os.path.exists(path=os.path.join(track_directory, "track.yaml")):
            if not tracks:
                distinct_tracks.add(entry)
            elif entry in tracks:
                distinct_tracks.add(entry)

    flags = []
    for track in distinct_tracks:
        LOG.debug(msg=f"Parsing track.yaml for track {track}")
        track_yaml = parse_track_yaml(track_name=track)

        if len(track_yaml["flags"]) == 0:
            LOG.debug(msg=f"No flag in track {track}. Skipping...")
            continue

        flags.extend(track_yaml["flags"])

    if not flags:
        LOG.warning(msg="No flag found...")
        return

    if format == OutputFormat.JSON:
        print(json.dumps(obj=flags, indent=2))
    elif format == OutputFormat.CSV:
        output = io.StringIO()
        writer = csv.DictWriter(f=output, fieldnames=flags[0].keys())
        writer.writeheader()
        writer.writerows(rowdicts=flags)
        print(output.getvalue())
    elif format == OutputFormat.YAML:
        print(yaml.safe_dump(data=flags))


@app.command(help="Get services from tracks")
def services(tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Only services from the given tracks (use the directory name)")] = []) -> None:
    distinct_tracks = set()
    for entry in os.listdir(
        path=(challenges_directory := os.path.join(CTF_ROOT_DIRECTORY, "challenges"))
    ):
        if os.path.isdir(
            s=(track_directory := os.path.join(challenges_directory, entry))
        ) and os.path.exists(path=os.path.join(track_directory, "track.yaml")):
            if not tracks:
                distinct_tracks.add(entry)
            elif entry in tracks:
                distinct_tracks.add(entry)

    for track in distinct_tracks:
        LOG.debug(msg=f"Parsing track.yaml for track {track}")
        track_yaml = parse_track_yaml(track_name=track)

        if len(track_yaml["services"]) == 0:
            LOG.debug(msg=f"No service in track {track}. Skipping...")
            continue

        for service in track_yaml["services"]:
            contact = ",".join(track_yaml["contacts"]["support"])
            name = service["name"]
            instance = service["instance"]
            address = service["address"]
            check = service["check"]
            port = service["port"]

            print(f"{track}/{instance}/{name} {contact} {address} {check} {port}")


@app.command(help="Generate the deployment files using `terraform init` and `terraform validate`")
def generate(tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Only generate the given tracks (use the directory name)")] = [],
             production: Annotated[bool, typer.Option("--production", help="Do a production deployment. Only use this if you know what you're doing.")] = False,
             remote: Annotated[str, typer.Option("--remote", help="Incus remote to deploy to")] = "local") -> set[str]:
    ENV["INCUS_REMOTE"] = remote
    # Get the list of tracks.
    distinct_tracks = set(
        track
        for track in get_all_available_tracks()
        if validate_track_can_be_deployed(track=track)
        and (not tracks or track in tracks)
    )

    LOG.debug(msg=f"Found {len(distinct_tracks)} tracks")

    if distinct_tracks:
        # Generate the Terraform modules file.
        create_terraform_modules_file(remote=remote, production=production)
        add_tracks_to_terraform_modules(
            tracks=distinct_tracks,
            remote=remote,
            production=production,
        )

        for track in distinct_tracks:
            relpath = os.path.relpath(
                os.path.join(CTF_ROOT_DIRECTORY, ".deploy", "common"),
                (
                    terraform_directory := os.path.join(
                        CTF_ROOT_DIRECTORY, "challenges", track, "terraform"
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
            cwd=os.path.join(CTF_ROOT_DIRECTORY, ".deploy"),
            stdout=subprocess.DEVNULL,
            check=True,
        )
        subprocess.run(
            args=[terraform_binary(), "validate"],
            cwd=os.path.join(CTF_ROOT_DIRECTORY, ".deploy"),
            check=True,
        )

    return distinct_tracks


@app.command(help="Deploy and provision the tracks")
def deploy(
        tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Only deploy the given tracks (use the directory name)")] = [],
        production: Annotated[bool, typer.Option("--production", help="Do a production deployment. Only use this if you know what you're doing.")] = False,
        remote: Annotated[str, typer.Option("--remote", help="Incus remote to deploy to")] = "local",
        redeploy: Annotated[bool, typer.Option("--redeploy", help="Do not use. Use `ctf redeploy` instead.")] = False,
        force: Annotated[bool, typer.Option("--force", help="Force the deployment even if there are errors.")] = False
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

        run_ansible_playbook(remote=remote, production=production, track=track, path=path)

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

    if not production and tracks:
        tracks = list(tracks)
        track_index = input(
            f"""Do you want to `incus project switch` to any of the tracks mentioned in argument?
{chr(10).join([f"{list(tracks).index(t) + 1}) {t}" for t in tracks])}

Which? """
        )

        if (
            track_index.isnumeric()
            and (track_index := int(track_index))
            and 0 < track_index <= len(tracks)
        ):
            LOG.info(
                msg=f"Running `incus project switch {tracks[track_index - 1]}`"
            )
            subprocess.run(
                args=["incus", "project", "switch", tracks[track_index - 1]],
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


@app.command(help="Destroy and then deploy the given tracks")
def redeploy(tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Only redeploy the given tracks (use the directory name)")] = [],
             production: Annotated[bool, typer.Option("--production", help="Do a production deployment. Only use this if you know what you're doing.")] = False,
             remote: Annotated[str, typer.Option("--remote", help="Incus remote to deploy to")] = "local",
             force: Annotated[bool, typer.Option("--force", help="If there are artefacts remaining, delete them without asking.")] = False
             ) -> None:
    ENV["INCUS_REMOTE"] = remote
    destroy(terraform_tracks=tracks, production=production, remote=remote, force=force)
    deploy(distinct_tracks=tracks, production=production, remote=remote, force=force)


@app.command(help="Preview the changes")
def check(tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Only check the given tracks (use the directory name)")] = [],
          production: Annotated[bool, typer.Option("--production", help="Do a production deployment. Only use this if you know what you're doing.")] = False,
          remote: Annotated[str, typer.Option("--remote", help="Incus remote to deploy to")] = "local",
    ) -> None:
    ENV["INCUS_REMOTE"] = remote
    # Run generate first.
    generate(tracks=tracks, production=production, remote=remote)

    # Then run terraform plan.
    subprocess.run(
        args=[terraform_binary(), "plan"],
        cwd=os.path.join(CTF_ROOT_DIRECTORY, ".deploy"),
        check=True,
    )

    # Check if Git LFS is installed on the system as it will be required for deployment.
    if not check_git_lfs():
        LOG.warning(
            msg="Git LFS is missing from  your system. Install it before deploying."
        )


@app.command(help="Generate statistics (such as number of tracks, number of flags, total flag value, etc.) from all the `track.yaml files. Outputs as JSON.")
def stats(
    tracks: Annotated[list[str], typer.Option("--tracks", "-t", help="Name of the tracks to count in statistics (if not specified, all tracks are counted).")] = [],
    generate_badges: Annotated[bool, typer.Option("--generate-badges", help="Generate SVG files of some statistics in the .badges directory.")] = False,
    charts: Annotated[bool, typer.Option("--charts", help="Generate PNG charts of some statistics in the .charts directory.")] = False,
    historical: Annotated[bool, typer.Option("--historical", help="Use in conjunction with --charts to generate historical data. ONLY USE THIS IF YOU KNOW WHAT YOU ARE DOING. THIS IS BAD CODE THAT WILL FUCK YOUR REPO IN UNEXPECTED WAYS.")] = False,
    ) -> None:
    LOG.debug(msg="Generating statistics...")
    stats = {}
    distinct_tracks = []
    for entry in os.listdir(
        (challenges_directory := os.path.join(CTF_ROOT_DIRECTORY, "challenges"))
    ):
        if os.path.isdir(
            (track_directory := os.path.join(challenges_directory, entry))
        ) and os.path.isfile(os.path.join(track_directory, "track.yaml")):
            if not args.tracks:
                distinct_tracks.append(entry)
            elif entry in args.tracks:
                distinct_tracks.append(entry)

    stats["number_of_tracks"] = len(distinct_tracks)
    stats["number_of_tracks_integrated_with_scenario"] = 0
    stats["number_of_flags"] = 0
    stats["highest_value_flag"] = 0
    stats["most_flags_in_a_track"] = 0
    stats["total_flags_value"] = 0
    stats["number_of_services"] = 0
    stats["number_of_files"] = 0
    stats["median_flag_value"] = 0
    stats["mean_flag_value"] = 0
    stats["number_of_services_per_port"] = {}
    stats["flag_count_per_value"] = {}
    stats["number_of_challenge_designers"] = 0
    stats["number_of_flags_per_track"] = {}
    stats["number_of_points_per_track"] = {}
    stats["not_integrated_with_scenario"] = []
    challenge_designers = set()
    flags = []
    for track in distinct_tracks:
        track_yaml = parse_track_yaml(track_name=track)
        number_of_flags = len(track_yaml["flags"])
        stats["number_of_flags_per_track"][track] = number_of_flags
        if track_yaml["integrated_with_scenario"]:
            stats["number_of_tracks_integrated_with_scenario"] += 1
        else:
            stats["not_integrated_with_scenario"].append(track)
        if number_of_flags > stats["most_flags_in_a_track"]:
            stats["most_flags_in_a_track"] = number_of_flags
        stats["number_of_flags"] += number_of_flags
        stats["number_of_services"] += len(track_yaml["services"])
        stats["number_of_points_per_track"][track] = 0
        for flag in track_yaml["flags"]:
            flags.append(flag["value"])
            stats["number_of_points_per_track"][track] += flag["value"]
            stats["total_flags_value"] += flag["value"]
            if flag["value"] > stats["highest_value_flag"]:
                stats["highest_value_flag"] = flag["value"]
            if flag["value"] not in stats["flag_count_per_value"]:
                stats["flag_count_per_value"][flag["value"]] = 0
            stats["flag_count_per_value"][flag["value"]] += 1
        for service in track_yaml["services"]:
            if service["port"] not in stats["number_of_services_per_port"]:
                stats["number_of_services_per_port"][service["port"]] = 0
            stats["number_of_services_per_port"][service["port"]] += 1
        for challenge_designer in track_yaml["contacts"]["dev"]:
            challenge_designers.add(challenge_designer.lower())

        if os.path.exists(
            path=(files_directory := os.path.join(challenges_directory, track, "files"))
        ):
            for file in os.listdir(path=files_directory):
                stats["number_of_files"] += 1
    stats["median_flag_value"] = statistics.median(flags)
    stats["mean_flag_value"] = round(statistics.mean(flags), 2)
    stats["number_of_challenge_designers"] = len(challenge_designers)

    # Sort dict keys
    stats["flag_count_per_value"] = {
        key: stats["flag_count_per_value"][key]
        for key in sorted(stats["flag_count_per_value"].keys())
    }
    stats["number_of_services_per_port"] = {
        key: stats["number_of_services_per_port"][key]
        for key in sorted(stats["number_of_services_per_port"].keys())
    }

    stats["challenge_designers"] = sorted(list(challenge_designers))
    stats["number_of_flags_per_track"] = dict(
        sorted(stats["number_of_flags_per_track"].items(), key=lambda item: item[1])
    )
    stats["number_of_points_per_track"] = dict(
        sorted(stats["number_of_points_per_track"].items(), key=lambda item: item[1])
    )

    print(json.dumps(stats, indent=2, ensure_ascii=False))
    if args.generate_badges:
        if not _has_pybadges:
            LOG.critical(msg="Module pybadges was not found.")
            exit(code=1)
        LOG.info(msg="Generating badges...")
        os.makedirs(name=".badges", exist_ok=True)
        write_badge(
            "flag",
            pybadges.badge(left_text="Flags", right_text=str(stats["number_of_flags"])),  # type: ignore
        )
        write_badge(
            "points",
            pybadges.badge(  # type: ignore
                left_text="Points", right_text=str(stats["total_flags_value"])
            ),
        )
        write_badge(
            "tracks",
            pybadges.badge(  # type: ignore
                left_text="Tracks", right_text=str(stats["number_of_tracks"])
            ),
        )
        write_badge(
            "services",
            pybadges.badge(  # type: ignore
                left_text="Services", right_text=str(stats["number_of_services"])
            ),
        )
        write_badge(
            "designers",
            pybadges.badge(  # type: ignore
                left_text="Challenge Designers",
                right_text=str(stats["number_of_challenge_designers"]),
            ),
        )
        write_badge(
            "files",
            pybadges.badge(  # type: ignore
                left_text="Files",
                right_text=str(stats["number_of_files"]),
            ),
        )
        write_badge(
            "scenario",
            pybadges.badge(  # type: ignore
                left_text="Integrated with scenario",
                right_text=str(stats["number_of_tracks_integrated_with_scenario"])
                + "/"
                + str(stats["number_of_tracks"]),
            ),
        )

    if args.charts:
        if not _has_matplotlib:
            LOG.critical(msg="Module matplotlib was not found.")
            exit(code=1)
        LOG.info(msg="Generating charts...")
        mpl_logger = logging.getLogger("matplotlib")
        mpl_logger.setLevel(logging.INFO)
        os.makedirs(name=".charts", exist_ok=True)
        # Flag count per value barchart
        plt.bar(
            stats["flag_count_per_value"].keys(), stats["flag_count_per_value"].values()
        )
        plt.xticks(
            ticks=range(0, max(stats["flag_count_per_value"].keys()) + 1), rotation=45
        )
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.xlabel("Flag Value")
        plt.ylabel("Number of Flags")
        plt.title("Number of Flags per Value")
        plt.savefig(os.path.join(".charts", "flags_per_value.png"))
        plt.clf()

        # Number of flag per track barchart
        plt.bar(
            list(stats["number_of_flags_per_track"].keys()),
            stats["number_of_flags_per_track"].values(),
        )
        plt.xticks(ticks=list(stats["number_of_flags_per_track"].keys()), rotation=90)
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.subplots_adjust(bottom=0.5)
        plt.xlabel("Track")
        plt.ylabel("Number of flags")
        plt.title("Number of flags per track")
        plt.savefig(os.path.join(".charts", "flags_per_track.png"))
        plt.clf()

        # Number of points per track barchart
        plt.bar(
            list(stats["number_of_points_per_track"].keys()),
            stats["number_of_points_per_track"].values(),
        )
        plt.xticks(ticks=list(stats["number_of_points_per_track"].keys()), rotation=90)
        plt.grid(True, linestyle="--", alpha=0.3)
        plt.subplots_adjust(bottom=0.5)
        plt.xlabel("Track")
        plt.ylabel("Number of points")
        plt.title("Number of points per track")
        plt.savefig(os.path.join(".charts", "points_per_track.png"))
        plt.clf()

        if args.historical:
            # Number of points and flags over time
            historical_data = {}
            commit_list = (
                subprocess.check_output(
                    ["git", "log", "--pretty=format:%H %ad", "--date=iso"]
                )
                .decode()
                .splitlines()[::-1]
            )
            commit_list_with_date = []
            for commit in commit_list:
                hash, date = commit.split(" ", 1)
                parsed_datetime = datetime.strptime(date, "%Y-%m-%d %H:%M:%S %z")
                commit_list_with_date.append((parsed_datetime, hash))
            commit_list_with_date = sorted(commit_list_with_date, key=lambda x: x[0])
            subprocess.run(["git", "stash"], check=True)
            for i, commit in list(enumerate(commit_list_with_date))[0:]:
                parsed_datetime, hash = commit
                # Check if the commit message has "Merge pull request" in it
                commit_message = subprocess.run(
                    ["git", "show", "-s", "--pretty=%B", hash],
                    check=True,
                    capture_output=True,
                )
                if "Merge pull request" in commit_message.stdout.decode():
                    LOG.debug(
                        f"{i + 1}/{len(commit_list_with_date)} Checking out commit: {commit}"
                    )
                    parsed_date = parsed_datetime.date()
                    subprocess.run(
                        ["git", "checkout", hash], check=True, capture_output=True
                    )

                    # Execute your command here (replace with what you need)
                    result = (
                        subprocess.run(
                            ["python", "scripts/ctf.py", "stats"],
                            check=False,
                            capture_output=True,
                            text=True,
                        ),
                    )
                    if result[0].returncode == 0:
                        stats = json.loads(result[0].stdout)
                        total_points = stats["total_flags_value"]
                        total_flags = stats["number_of_flags"]
                        print(total_flags)
                        historical_data[parsed_date] = {
                            "total_points": total_points,
                            "total_flags": total_flags,
                        }
            subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)
            subprocess.run(["git", "stash", "pop"], check=True)

            plt.plot(
                historical_data.keys(),
                [data["total_points"] for data in historical_data.values()],
                label="Total Points",
            )
            # plt.plot(historical_data.keys(), [data["total_flags"] for data in historical_data.values()], label="Total Flags")
            # plt.xticks(ticks=list(stats["number_of_points_per_track"].keys()), rotation=90)
            plt.grid(True, linestyle="--", alpha=0.3)
            plt.subplots_adjust(bottom=0.1)
            plt.xlabel("Time")
            plt.ylabel("Total points")
            plt.title("Total points over time")
            plt.xticks(rotation=90)
            plt.subplots_adjust(bottom=0.2)
            plt.subplot().set_ylim(
                0, max([data["total_points"] for data in historical_data.values()]) + 10
            )
            plt.savefig(os.path.join(".charts", "points_over_time.png"))
            plt.clf()

    LOG.debug(msg="Done...")

class ListOutputFormat(Enum):
    PRETTY = "pretty"


@app.command("list", help="List tracks and their author(s).")
def list_tracks(format: Annotated[ListOutputFormat, typer.Option("--format", "-f", help="Output format")] = ListOutputFormat.PRETTY) -> None:
    tracks = []
    for track in os.listdir(path=os.path.join(CTF_ROOT_DIRECTORY, "challenges")):
        if os.path.isdir(
            s=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track)
        ) and os.path.exists(
            path=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track, "track.yaml")
        ):
            tracks.append(track)

    parsed_tracks = []
    for track in tracks:
        parsed_track = parse_track_yaml(track)

        # find the discourse topic name
        posts = parse_post_yamls(track)
        topic = None
        for post in posts:
            if post.get("type") == "topic":
                topic = post["title"]
        parsed_tracks.append(
            [
                parsed_track["name"],
                topic,
                ", ".join(parsed_track["contacts"]["dev"]),
                ", ".join(parsed_track["contacts"]["support"]),
                ", ".join(parsed_track["contacts"]["qa"]),
            ]
        )

    if format.value == "pretty":
        LOG.info(
            "\n"
            + tabulate(
                parsed_tracks,
                headers=[
                    "Internal track name",
                    "Discourse Topic Name",
                    "Dev",
                    "Support",
                    "QA",
                ],
                tablefmt="fancy_grid",
            )
        )
    else:
        raise ValueError(f"Invalid format: {format.value}")


@app.command(help="Run many static validations to ensure coherence and quality in the tracks and repo as a whole.")
def validate() -> None:
    LOG.info(msg="Starting ctf validate...")

    LOG.info(msg=f"Found {len(validators_list)} Validators")

    validators = [validator_class() for validator_class in validators_list]

    tracks = []
    for track in os.listdir(path=os.path.join(CTF_ROOT_DIRECTORY, "challenges")):
        if os.path.isdir(
            s=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track)
        ) and os.path.exists(
            path=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track, "track.yaml")
        ):
            tracks.append(track)

    LOG.info(msg=f"Found {len(tracks)} tracks")

    errors: list[ValidationError] = []

    LOG.info(msg="Validating track.yaml files against JSON Schema...")
    validate_with_json_schemas(
        schema=os.path.join(SCHEMAS_ROOT_DIRECTORY, "track.yaml.json"),
        files_pattern=os.path.join(CTF_ROOT_DIRECTORY, "challenges", "*", "track.yaml"),
    )
    LOG.info(msg="Validating discourse post YAML files against JSON Schema...")
    validate_with_json_schemas(
        schema=os.path.join(SCHEMAS_ROOT_DIRECTORY, "post.json"),
        files_pattern=os.path.join(
            CTF_ROOT_DIRECTORY, "challenges", "*", "posts", "*.yaml"
        ),
    )

    LOG.info(msg="Validating terraform files format...")
    r = subprocess.run(
        args=["tofu", "fmt", "-no-color", "-check", "-recursive", CTF_ROOT_DIRECTORY],
        capture_output=True,
    )
    if r.returncode != 0:
        errors.append(
            ValidationError(
                error_name="Tofu format",
                error_description="Bad Terraform formatting. Please run `tofu fmt -recursive ./`",
                details={
                    "Files": "\n".join(
                        [
                            *([out] if (out := r.stdout.decode().strip()) else []),
                            *re.findall(
                                pattern=r"(Failed to read file .+)$",
                                string=r.stderr.decode().strip(),
                                flags=re.MULTILINE,
                            ),
                        ]
                    )
                },
            )
        )

    for validator in validators:
        LOG.info(msg=f"Running {type(validator).__name__}")
        for track in tracks:
            errors += validator.validate(track_name=track)

    # Get the errors from finalize()
    for validator in validators:
        errors += validator.finalize()

    if not errors:
        LOG.info(msg="No error found!")
    else:
        LOG.error(msg=f"{len(errors)} errors found.")

        errors_list = list(
            map(
                lambda error: [
                    error.track_name,
                    error.error_name,
                    "\n".join(textwrap.wrap(error.error_description, 50)),
                    "\n".join(
                        [
                            str(key) + ": " + str(value)
                            for key, value in error.details.items()
                        ]
                    ),
                ],
                errors,
            )
        )

        LOG.error(
            "\n"
            + tabulate(
                errors_list,
                headers=["Track", "Error", "Description", "Details"],
                tablefmt="fancy_grid",
            )
        )
        exit(code=1)


def write_badge(name: str, svg: str) -> None:
    with open(
        file=os.path.join(".badges", f"badge-{name}.svg"), mode="w", encoding="utf-8"
    ) as f:
        f.write(svg)


@app.command(help="Print the tool's version.")
def version():
    # Create an empty command as the version is printed before anything else in the __init__.py file.
    pass


def main():
    app()

if __name__ == "__main__":
    if not os.path.isdir(s=(p := os.path.join(CTF_ROOT_DIRECTORY, "challenges"))):
        import sys
        if not "init" in sys.argv:
            LOG.error(
                msg=f"Directory `{p}` not found. Make sure this script is ran from the root directory OR set the CTF_ROOT_DIR environment variable to the root directory."
            )
            exit(code=1)
    main()

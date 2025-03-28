#!/usr/bin/env python3
import argparse
import csv
import io
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import textwrap
from enum import Enum, unique

import argcomplete
import coloredlogs
import jinja2
import yaml

import ctf.validate_json_schemas
import ctf.validators
from ctf.utils import find_root_directory, parse_track_yaml

try:
    import pybadges

    _has_pybadges = True
except ImportError:
    _has_pybadges = False

LOG = logging.getLogger()
LOG.setLevel(logging.DEBUG)
coloredlogs.install(level="DEBUG", logger=LOG)

ROOT_DIRECTORY = find_root_directory()


@unique
class Template(Enum):
    APACHE_PHP = "apache-php"
    PYTHON_SERVICE = "python-service"
    FILES_ONLY = "files-only"
    TRACK_YAML_ONLY = "track-yaml-only"

    def __str__(self):
        return self.value


@unique
class OutputFormat(Enum):
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"

    def __str__(self):
        return self.value


def requires_pybadges(f):
    def wrapper(*args, **kwargs):
        if not _has_pybadges:
            LOG.fatal("Module pybadges was not found.")
            exit(1)

        f(*args, **kwargs)

    return wrapper


def terraform_binary():
    path = shutil.which("tofu")
    if not path:
        path = shutil.which("terraform")

    if not path:
        raise Exception("Couldn't find Terraform or OpenTofu")

    return path


def new(args):
    LOG.info(f"Creating a new track: {args.name}")
    if not re.match(r"^[a-z][a-z0-9\-]{0,61}[a-z0-9]$", args.name):
        LOG.fatal(
            """The track name Valid instance names must fulfill the following requirements:
* The name must be between 1 and 63 characters long;
* The name must contain only letters, numbers and dashes from the ASCII table;
* The name must not start with a digit or a dash;
* The name must not end with a dash."""
        )
        exit(1)

    directory = f"{ROOT_DIRECTORY}/challenges/{args.name}"

    if os.path.exists(directory):
        if args.force:
            LOG.debug(f"Deleting {directory}")
            shutil.rmtree(directory)
        else:
            LOG.fatal(
                "Track already exists with that name. Use `--force` to overwrite the track."
            )
            exit(1)

    os.mkdir(directory)

    LOG.debug(f"Directory {directory} created.")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            f"{ROOT_DIRECTORY}/scripts/templates", encoding="utf-8"
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

    track_template = env.get_template("track.yaml.j2")
    render = track_template.render(
        data={
            "name": args.name,
            "full_ipv6_address": full_ipv6_address,
            "ipv6_subnet": ipv6_subnet,
            "template": args.template.value,
        }
    )
    with open(f"{directory}/track.yaml", "w", encoding="utf-8") as f:
        f.write(render)

    LOG.debug("Wrote track.yaml.")

    posts_directory = f"{directory}/posts"

    os.mkdir(posts_directory)

    track_template = env.get_template("topic.yaml.j2")
    render = track_template.render(data={"name": args.name})
    with open(f"{posts_directory}/{args.name}.yaml", "w", encoding="utf-8") as f:
        f.write(render)

    LOG.debug(f"Wrote {args.name}.yaml")

    track_template = env.get_template("post.yaml.j2")
    render = track_template.render(data={"name": args.name})
    with open(f"{posts_directory}/flag1.yaml", "w", encoding="utf-8") as f:
        f.write(render)

    LOG.debug("Wrote flag1.yaml")

    if args.template == Template.TRACK_YAML_ONLY:
        return

    files_directory = f"{directory}/files"

    os.mkdir(files_directory)

    LOG.debug(f"Wrote {files_directory}")

    if args.template == Template.FILES_ONLY:
        return

    terraform_directory = f"{directory}/terraform"

    os.mkdir(terraform_directory)

    track_template = env.get_template("main.tf.j2")

    render = track_template.render(
        data={
            "name": args.name,
            "hardware_address": hardware_address,
            "ipv6": ipv6_address,
            "ipv6_subnet": ipv6_subnet,
            "full_ipv6_address": full_ipv6_address,
        }
    )
    with open(f"{terraform_directory}/main.tf", "w", encoding="utf-8") as f:
        f.write(render)

    LOG.debug("Wrote main.tf")

    os.symlink(
        f"{ROOT_DIRECTORY}/.deploy/common/variables.tf",
        f"{terraform_directory}/variables.tf",
    )
    LOG.debug("Wrote variables.tf")

    os.symlink(
        f"{ROOT_DIRECTORY}/.deploy/common/versions.tf",
        f"{terraform_directory}/versions.tf",
    )
    LOG.debug("Wrote versions.tf")

    ansible_directory = f"{directory}/ansible"

    os.mkdir(ansible_directory)

    track_template = env.get_template(f"deploy-{args.template}.yaml.j2")
    render = track_template.render(data={"name": args.name})
    with open(f"{ansible_directory}/deploy.yaml", "w", encoding="utf-8") as f:
        f.write(render)

    LOG.debug("Wrote deploy.yaml")

    track_template = env.get_template("inventory.j2")
    render = track_template.render(data={"name": args.name})
    with open(f"{ansible_directory}/inventory", "w", encoding="utf-8") as f:
        f.write(render)

    LOG.debug("Wrote ansible inventory file")

    challenge_directory = f"{ansible_directory}/challenge"

    os.mkdir(challenge_directory)

    if args.template == Template.APACHE_PHP:
        track_template = env.get_template("index.php.j2")
        render = track_template.render(data={"name": args.name})
        with open(f"{challenge_directory}/index.php", "w", encoding="utf-8") as f:
            f.write(render)

        LOG.debug("Wrote index.php")

    if args.template == Template.PYTHON_SERVICE:
        track_template = env.get_template("app.py.j2")
        render = track_template.render(data={"name": args.name})
        with open(f"{challenge_directory}/app.py", "w", encoding="utf-8") as f:
            f.write(render)

        LOG.debug("Wrote app.py")

        with open(f"{challenge_directory}/flag-1.txt", "w", encoding="utf-8") as f:
            f.write("FLAG-CHANGEME (1/2)\n")

        LOG.debug("Wrote flag-1.txt")


def destroy(args):
    LOG.info("tofu destroy...")

    if not os.path.exists(f"{ROOT_DIRECTORY}/.deploy/modules.tf"):
        LOG.fatal("Nothing to destroy.")
        exit(1)

    with open(f"{ROOT_DIRECTORY}/.deploy/modules.tf", "r") as f:
        modules_tf = f.read()

    tracks = set(
        re.findall(
            r"^module \"track-([a-z][a-z0-9\-]{0,61}[a-z0-9])\"",
            modules_tf,
            re.MULTILINE,
        )
    )

    r = (
        subprocess.run(
            ["incus", "project", "get-current"],
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )

    if r in tracks:
        projects = {
            project["name"]
            for project in json.loads(
                subprocess.run(
                    ["incus", "project", "list", "--format=json"],
                    check=False,
                    capture_output=True,
                ).stdout.decode()
            )
        }

        projects = list((projects - tracks))
        if len(projects) == 0:
            LOG.fatal(
                "No project to switch to. This should never happen as the default should always exists."
            )
            exit(1)

        LOG.info(
            f"Running `incus project switch {'default' if 'default' in projects else projects[0]}`"
        )
        subprocess.run(
            [
                "incus",
                "project",
                "switch",
                "default" if "default" in projects else projects[0],
            ],
            check=True,
        )

    subprocess.run(
        [terraform_binary(), "destroy", "-auto-approve"],
        cwd=f"{ROOT_DIRECTORY}/.deploy/",
        check=False,
    )

    projects = [
        project["name"]
        for project in json.loads(
            subprocess.run(
                ["incus", "project", "list", "--format=json"],
                check=False,
                capture_output=True,
            ).stdout.decode()
        )
    ]

    networks = [
        network["name"]
        for network in json.loads(
            subprocess.run(
                ["incus", "network", "list", "--format=json"],
                check=False,
                capture_output=True,
            ).stdout.decode()
        )
    ]

    network_acls = [
        network_acl["name"]
        for network_acl in json.loads(
            subprocess.run(
                ["incus", "network", "acl", "list", "--format=json"],
                check=False,
                capture_output=True,
            ).stdout.decode()
        )
    ]

    for module in re.findall(
        r"^module \"track-([a-z][a-z0-9\-]{0,61}[a-z0-9])\"", modules_tf, re.MULTILINE
    ):
        if module == "common":
            continue

        if module in projects:
            LOG.warning(f"The project {module} was not destroyed properly.")
            if (
                args.force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    ["incus", "project", "delete", module, "--force"],
                    check=False,
                    capture_output=True,
                    input=b"yes\n",
                )

        if (tmp_module := module[0:15]) in networks:
            LOG.warning(f"The network {tmp_module} was not destroyed properly.")
            if (
                args.force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    ["incus", "network", "delete", tmp_module],
                    check=False,
                    capture_output=True,
                )

        if (tmp_module := module) in network_acls or (
            tmp_module := f"{module}-default"
        ) in network_acls:
            LOG.warning(f"The network ACL {tmp_module} was not destroyed properly.")
            if (
                args.force
                or (input("Do you want to destroy it? [Y/n] ").lower() or "y") == "y"
            ):
                subprocess.run(
                    ["incus", "network", "acl", "delete", tmp_module],
                    check=False,
                    capture_output=True,
                )

    LOG.info("Successfully destroyed every track")


def flags(args):
    tracks = set()
    for entry in os.listdir(f"{ROOT_DIRECTORY}/challenges/"):
        if os.path.isdir(f"{ROOT_DIRECTORY}/challenges/{entry}") and os.path.exists(
            os.path.join(ROOT_DIRECTORY, "challenges", entry, "track.yaml")
        ):
            if not args.tracks:
                tracks.add(entry)
            elif entry in args.tracks:
                tracks.add(entry)

    flags = []
    for track in tracks:
        LOG.debug(f"Parsing track.yaml for track {track}")
        track_yaml = parse_track_yaml(track)

        if len(track_yaml["flags"]) == 0:
            LOG.debug(f"No flag in track {track}. Skipping...")
            continue

        flags.extend(track_yaml["flags"])

    if not flags:
        LOG.warning("No flag found...")
        return

    if args.format == OutputFormat.JSON:
        print(json.dumps(flags, indent=2))
    elif args.format == OutputFormat.CSV:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=flags[0].keys())
        writer.writeheader()
        writer.writerows(flags)
        print(output.getvalue())
    elif args.format == OutputFormat.YAML:
        print(yaml.safe_dump(flags))


def generate(args):
    # Get the list of tracks.
    tracks = set()

    for entry in os.listdir(f"{ROOT_DIRECTORY}/challenges/"):
        if args.tracks and entry not in args.tracks:
            continue

        if not os.path.isdir(os.path.join(ROOT_DIRECTORY, "challenges", entry)):
            continue

        if not os.path.exists(
            os.path.join(ROOT_DIRECTORY, "challenges", entry, "terraform", "main.tf")
        ):
            continue

        tracks.add(entry)

    LOG.debug(f"Found {len(tracks)} tracks")

    if tracks:
        # Generate the Terraform modules file.
        with open(f"{ROOT_DIRECTORY}/.deploy/modules.tf", "w+") as fd:
            template = jinja2.Environment().from_string(
                textwrap.dedent(
                    """\
                    module "common" {
                      source = "./common"
                    }
                    {% for track in tracks %}
                    module "track-{{ track }}" {
                      source = "../challenges/{{ track }}/terraform"
                    {% if production %}
                      deploy = "production"
                    {% endif %}

                      depends_on = [module.common]
                    }
                    {% endfor %}
                    """
                )
            )
            fd.write(template.render(tracks=tracks, production=args.production))

        subprocess.run(
            [terraform_binary(), "init", "-upgrade"],
            cwd=f"{ROOT_DIRECTORY}/.deploy/",
            stdout=subprocess.DEVNULL,
            check=True,
        )
        subprocess.run(
            [terraform_binary(), "validate"],
            cwd=f"{ROOT_DIRECTORY}/.deploy/",
            check=True,
        )

    return tracks


def deploy(args):
    # Run generate first.
    tracks = generate(args)

    try:
        subprocess.run(
            [terraform_binary(), "apply", "-auto-approve"],
            cwd=f"{ROOT_DIRECTORY}/.deploy/",
            check=True,
        )
    except subprocess.CalledProcessError:
        LOG.warning(
            f"The project could not deploy due to instable state. It is often due to CTRL+C while deploying as {os.path.basename(terraform_binary())} was not able to save the state of each object created."
        )

        if (input("Do you want to clean and start over? [Y/n] ").lower() or "y") != "y":
            exit(1)

        args.force = True
        destroy(args)

        subprocess.run(
            [terraform_binary(), "apply", "-auto-approve"],
            cwd=f"{ROOT_DIRECTORY}/.deploy/",
            check=True,
        )

    for track in tracks:
        LOG.debug(f"Parsing track.yaml for track {track}")
        track_yaml = parse_track_yaml(track)

        LOG.info(f"Running deploy.yaml with ansible for track {track}...")
        path = os.path.join(ROOT_DIRECTORY, "challenges", track, "ansible")
        if not os.path.exists(path):
            continue

        subprocess.run(
            ["ansible-playbook", "deploy.yaml", "-i", "inventory"],
            cwd=path,
            check=True,
        )

        artifacts_path = os.path.join(path, "artifacts")
        if os.path.exists(artifacts_path):
            shutil.rmtree(artifacts_path)

        if not args.production:
            incus_list = json.loads(
                subprocess.run(
                    ["incus", "list", f"--project={track}", "--format", "json"],
                    check=True,
                    capture_output=True,
                ).stdout.decode()
            )
            ipv6_to_container_name = {}
            for machine in incus_list:
                addresses = machine["state"]["network"]["eth0"]["addresses"]
                ipv6_address = list(
                    filter(lambda address: address["family"] == "inet6", addresses)
                )[0]["address"]
                ipv6_to_container_name[ipv6_address] = machine["name"]

            LOG.debug(f"Mapping: {ipv6_to_container_name}")

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
                        [
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

            LOG.info(f"Running `incus --project={track} list`")
            subprocess.run(["incus", f"--project={track}", "list"], check=True)

    if not args.production and args.tracks:
        track_index = input(
            f"""Do you want to `incus project switch` to any of the tracks mentioned in argument?
{chr(10).join([f"{args.tracks.index(t) + 1}) {t}" for t in args.tracks])}

Which? """
        )

        if (
            track_index.isnumeric()
            and (track_index := int(track_index))
            and 0 < track_index <= len(args.tracks)
        ):
            LOG.info(f"Running `incus project switch {args.tracks[track_index - 1]}`")
            subprocess.run(
                ["incus", "project", "switch", args.tracks[track_index - 1]], check=True
            )
        elif track_index:
            LOG.warning(f"Could not switch project, unrecognized input: {track_index}.")


def check(args):
    # Run generate first.
    generate(args)

    # Then run terraform plan.
    subprocess.run(
        [terraform_binary(), "plan"], cwd=f"{ROOT_DIRECTORY}/.deploy/", check=True
    )


@requires_pybadges
def stats(args):
    LOG.debug("Generating statistics...")
    stats = {}
    tracks = []
    for entry in os.listdir(f"{ROOT_DIRECTORY}/challenges/"):
        if os.path.isdir(f"{ROOT_DIRECTORY}/challenges/{entry}"):
            if not args.tracks:
                tracks.append(entry)
            elif entry in args.tracks:
                tracks.append(entry)

    stats["number_of_tracks"] = len(tracks)
    stats["number_of_tracks_integrated_with_scenario"] = 0
    stats["number_of_flags"] = 0
    stats["highest_value_flag"] = 0
    stats["most_flags_in_a_track"] = 0
    stats["total_flags_value"] = 0
    stats["number_of_services"] = 0
    stats["number_of_services_per_port"] = {}
    stats["flag_count_per_value"] = {}
    challenge_designers = set()
    for track in tracks:
        track_yaml = parse_track_yaml(track)
        number_of_flags = len(track_yaml["flags"])
        if track_yaml["integrated_with_scenario"]:
            stats["number_of_tracks_integrated_with_scenario"] += 1
        if number_of_flags > stats["most_flags_in_a_track"]:
            stats["most_flags_in_a_track"] = number_of_flags
        stats["number_of_flags"] += number_of_flags
        stats["number_of_services"] += len(track_yaml["services"])
        for flag in track_yaml["flags"]:
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
            challenge_designers.add(challenge_designer)

        stats["number_of_files"] = 0
        if os.path.exists(f"{ROOT_DIRECTORY}/challenges/{track}/files"):
            for file in os.listdir(f"{ROOT_DIRECTORY}/challenges/{track}/files"):
                stats["number_of_files"] += 1
    stats["number_of_challenge_designers"] = len(challenge_designers)

    print(json.dumps(stats, indent=2))
    if args.generate_badges:
        LOG.info("Generating badges...")
        os.makedirs(".badges", exist_ok=True)
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

    LOG.debug("Done...")


def validate(args: argparse.Namespace):
    LOG.info("Starting ctf validate...")

    LOG.info(f"Found {len(ctf.validators.validators_list)} Validators")

    validators = [
        validator_class() for validator_class in ctf.validators.validators_list
    ]

    tracks = []
    for track in os.listdir(f"{ROOT_DIRECTORY}/challenges/"):
        if os.path.isdir(f"{ROOT_DIRECTORY}/challenges/{track}") and os.path.exists(
            f"{ROOT_DIRECTORY}/challenges/{track}/track.yaml"
        ):
            tracks.append(track)

    LOG.info(f"Found {len(tracks)} tracks")

    errors: list[ctf.validators.ValidationError] = []

    LOG.info("Validating track.yaml files against JSON Schema...")
    ctf.validate_json_schemas.validate_with_json_schemas(
        schema=f"{ROOT_DIRECTORY}/schemas/track.yaml.json",
        files_pattern=f"{ROOT_DIRECTORY}/challenges/*/track.yaml",
    )
    LOG.info("Validating discourse post YAML files against JSON Schema...")
    ctf.validate_json_schemas.validate_with_json_schemas(
        schema=f"{ROOT_DIRECTORY}/schemas/post.json",
        files_pattern=f"{ROOT_DIRECTORY}/challenges/*/posts/*.yaml",
    )

    LOG.info("Validating terraform files format...")
    r = subprocess.run(
        ["tofu", "fmt", "-no-color", "-check", "-recursive", ROOT_DIRECTORY],
        capture_output=True,
    )
    if r.returncode != 0:
        errors.append(
            ctf.validators.ValidationError(
                error_name="Tofu format",
                error_description="Error when checking terraform files formatting. Please run `tofu fmt -recursive ./`",
                details={
                    "files": "\n".join(
                        [
                            *([out] if (out := r.stdout.decode().strip()) else []),
                            *re.findall(
                                r"(Failed to read file .+)$",
                                r.stderr.decode().strip(),
                                re.MULTILINE,
                            ),
                        ]
                    )
                },
            )
        )

    for validator in validators:
        LOG.info(f"Running {type(validator).__name__}")
        for track in tracks:
            errors += validator.validate(track)

    # Get the errors from finalize()
    for validator in validators:
        errors += validator.finalize()

    if not errors:
        LOG.info("No error found!")
    else:
        LOG.error(f"{len(errors)} errors found.")
        LOG.error(
            "{:<30} {:<20} {:<40} {:<80}".format(
                "============Error============",
                "=======Track=======",
                "=================Details================",
                "==================================Description==================================",
            )
        )
        for error in errors:
            LOG.error(
                "{:<30} {:<20} {:<40} {:<80}".format(
                    error.error_name,
                    error.track_name,
                    str(error.details),
                    error.error_description,
                )
            )
        exit(1)


def write_badge(name: str, svg: str):
    with open(f".badges/badge-{name}.svg", "w", encoding="utf-8") as f:
        f.write(svg)


def main():
    # Command line parsing.
    parser = argparse.ArgumentParser(
        prog="ctf",
        description="CTF preparation tool. Run from the root CTF repo directory or set the CTF_ROOT_DIR environment variable to run the tool.",
    )

    subparsers = parser.add_subparsers(required=True)

    parser_flags = subparsers.add_parser(
        "flags",
        help="Get flags from tracks",
    )
    parser_flags.set_defaults(func=flags)
    parser_flags.add_argument(
        "--tracks",
        "-t",
        nargs="+",
        help="Only flags from the given tracks (use the folder name)",
    )
    parser_flags.add_argument(
        "--format",
        help="Output format.",
        choices=list(OutputFormat),
        default=OutputFormat.JSON,
        type=OutputFormat,
    )

    parser_generate = subparsers.add_parser(
        "generate",
        help="Generate the deployment files using `terraform init` and `terraform validate`",
    )
    parser_generate.set_defaults(func=generate)
    parser_generate.add_argument(
        "--tracks",
        "-t",
        nargs="+",
        help="Only generate the given tracks (use the folder name)",
    )
    parser_generate.add_argument(
        "--production",
        action="store_true",
        default=False,
        help="Do a production deployment. Only use this if you know what you're doing.",
    )

    parser_deploy = subparsers.add_parser("deploy", help="Deploy all the changes")
    parser_deploy.set_defaults(func=deploy)
    parser_deploy.add_argument(
        "--tracks",
        "-t",
        nargs="+",
        help="Only deploy the given tracks (use the folder name)",
    )
    parser_deploy.add_argument(
        "--production",
        action="store_true",
        default=False,
        help="Do a production deployment. Only use this if you know what you're doing.",
    )

    parser_check = subparsers.add_parser("check", help="Preview the changes")
    parser_check.set_defaults(func=check)
    parser_check.add_argument(
        "--tracks",
        "-t",
        nargs="+",
        help="Only check the given tracks (use the folder name)",
    )
    parser_check.add_argument(
        "--production",
        action="store_true",
        default=False,
        help="Do a production deployment. Only use this if you know what you're doing.",
    )

    parser_new = subparsers.add_parser("new", help="Create a new track.")
    parser_new.set_defaults(func=new)
    parser_new.add_argument(
        "--name", help="Track name. No space, use underscores if needed.", required=True
    )
    parser_new.add_argument(
        "--template",
        help="Template name.",
        choices=list(Template),
        default=Template.APACHE_PHP,
        type=Template,
    )
    parser_new.add_argument(
        "--force",
        help="If directory already exists, delete it and create it again.",
        action="store_true",
        default=False,
    )

    parser_destroy = subparsers.add_parser(
        "destroy",
        help="Destroy everything deployed by Terraform. This is a destructive operation.",
    )
    parser_destroy.set_defaults(func=destroy)
    parser_destroy.add_argument(
        "--force",
        help="If there are artefacts remaining, delete them without asking.",
        action="store_true",
        default=False,
    )

    parser_stats = subparsers.add_parser(
        "stats",
        help="Generate statistics (such as number of tracks, number of flags, total flag value, etc.) from all the `track.yaml files. Outputs as JSON.",
    )
    parser_stats.set_defaults(func=stats)
    parser_stats.add_argument(
        "--tracks",
        "-t",
        nargs="+",
        help="Name of the tracks to count in statistics (if not specified, all tracks are counted).",
    )
    parser_stats.add_argument(
        "--generate-badges",
        action="store_true",
        default=False,
        help="Generate SVG files of some statistics in the .badges directory.",
    )

    parser_validate = subparsers.add_parser(
        "validate",
        help="Run many static validations to ensure coherence and quality in the tracks and repo as a whole.",
    )
    parser_validate.set_defaults(func=validate)
    parser_validate.add_argument(
        "--list",
        "-l",
        action="store_true",
        default=False,
        help="List validators.",
    )

    argcomplete.autocomplete(parser)

    args = parser.parse_args()

    if not os.path.isdir(f"{ROOT_DIRECTORY}/challenges/"):
        LOG.error(
            f"Directory `{ROOT_DIRECTORY}/challenges/` not found. Make sure this script is ran from the root directory OR set the CTF_ROOT_DIR environment variable to the root directory."
        )
        exit(1)

    args.func(args)


if __name__ == "__main__":
    main()

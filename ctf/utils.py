import os
import re
import shutil
import subprocess
import textwrap
from typing import Any, Generator

import jinja2
import yaml

from ctf import ENV
from ctf.logger import LOG
from ctf.models import Track

__CTF_ROOT_DIRECTORY = ""


def available_incus_remotes() -> list[str]:
    try:
        r = subprocess.run(
            args=["incus", "remote", "list", "-fcsv", "-cn"],
            capture_output=True,
        )
    except FileNotFoundError:
        return []

    return r.stdout.decode().strip().replace(" (current)", "").splitlines()


def check_git_lfs() -> bool:
    return not bool(subprocess.run(args=["git", "lfs"], capture_output=True).returncode)


def get_all_available_tracks() -> set[Track]:
    tracks = set()

    for entry in os.listdir(
        path=(
            challenges_directory := os.path.join(
                find_ctf_root_directory(), "challenges"
            )
        )
    ):
        if not os.path.isdir(s=os.path.join(challenges_directory, entry)):
            continue

        tracks.add(Track(name=entry))

    return tracks


def does_track_require_build_container(track: Track) -> bool:
    return os.path.isfile(
        build_yaml_file_path := os.path.join(
            find_ctf_root_directory(),
            "challenges",
            track.name,
            "ansible",
            "build.yaml",
        )
    ) and bool(load_yaml_file(build_yaml_file_path))


def validate_track_can_be_deployed(track: Track) -> bool:
    return (
        os.path.exists(
            path=os.path.join(
                find_ctf_root_directory(),
                "challenges",
                track.name,
                "terraform",
                "main.tf",
            )
        )
        and os.path.exists(
            path=os.path.join(
                find_ctf_root_directory(),
                "challenges",
                track.name,
                "ansible",
                "deploy.yaml",
            )
        )
        and os.path.exists(
            path=os.path.join(
                find_ctf_root_directory(),
                "challenges",
                track.name,
                "ansible",
                "inventory",
            )
        )
    )


def add_tracks_to_terraform_modules(tracks: set[Track]):
    with open(
        file=os.path.join(find_ctf_root_directory(), ".deploy", "modules.tf"), mode="a"
    ) as fd:
        template = jinja2.Environment().from_string(
            source=textwrap.dedent(
                text="""\
                    {% for track in tracks %}
                    module "track-{{ track.name }}" {
                      source = "../challenges/{{ track.name }}/terraform"
                      build_container = {{ 'true' if track.require_build_container else 'false' }}
                      {% if track.production %}deploy = "production"{% endif %}
                      {% if track.remote %}incus_remote = "{{ track.remote }}"{% endif %}
                      {% for ov in output_variables %}
                      {{ ov }} = module.common.{{ ov }}
                      {% endfor %}
                    }
                    {% endfor %}
                    """
            )
        )
        fd.write(
            template.render(
                tracks=tracks - get_terraform_tracks_from_modules(),
                output_variables=get_common_modules_output_variables(),
            )
        )


def create_terraform_modules_file(remote: str, production: bool = False):
    with open(
        file=os.path.join(find_ctf_root_directory(), ".deploy", "modules.tf"), mode="w+"
    ) as fd:
        template = jinja2.Environment().from_string(
            source=textwrap.dedent(
                text="""\
                    module "common" {
                      source = "./common"
                      {% if production %}deploy = "production"{% endif %}
                      {% if remote %}incus_remote = "{{ remote }}"{% endif %}
                    }
                    
                    """
            )
        )
        fd.write(template.render(production=production, remote=remote))


def get_common_modules_output_variables() -> set[str]:
    output_variables: set[str] = set()
    output_variable_regex: re.Pattern = re.compile(
        r'^output\s*"([a-zA-Z_\-]+)"\s*{', re.MULTILINE
    )
    variable_regex: re.Pattern = re.compile(
        r'^variable\s*"([a-zA-Z_\-]+)"\s*{', re.MULTILINE
    )

    variables: set[str] = set()

    for file in os.listdir(
        path := os.path.join(find_ctf_root_directory(), ".deploy", "common")
    ):
        if file == "versions.tf":
            continue

        with open(os.path.join(path, file), "r") as f:
            match file:
                case "variables.tf":
                    for i in variable_regex.findall(f.read()):
                        variables.add(i)
                case _:
                    for i in output_variable_regex.findall(f.read()):
                        output_variables.add(i)

    for variable in output_variables - variables:
        LOG.error(
            msg
            := f'Variable "{variable}" could not be found in "variables.tf". This could cause an issue when creating/destroying an environment.'
        )

        if (
            input(f'Do you want to add "{variable}" to "variables.tf"? [y/N] ').lower()
            or "n"
        ) == "n":
            raise Exception(msg)

        try:
            print("Do CTRL+C to cancel...")
            while not (default := input("What is the default value? ")):
                print("Do CTRL+C to cancel...")

            var_type = input("What is the type? [string] ") or "string"

            with open(os.path.join(path, "variables.tf"), "a") as f:
                f.write("\n")
                template = jinja2.Environment().from_string(
                    source=textwrap.dedent(
                        text="""\
                        variable "{{variable}}" {
                            default = "{{default}}"
                            type = {{type}}
                        }
                        """
                    )
                )
                f.write(
                    template.render(variable=variable, default=default, type=var_type)
                )
            variables.add(variable)
        except KeyboardInterrupt:
            LOG.warning(
                f'Cancelling the addition of the "{variable}" to "variables.tf".'
            )

            raise Exception(msg)

    if len(output_variables - variables) != 0:
        LOG.critical(
            msg
            := f'Some output variables were not found in "variables.tf": {", ".join(output_variables - variables)}'
        )
        raise Exception(msg)

    return output_variables & variables


def get_terraform_tracks_from_modules() -> set[Track]:
    with open(
        file=os.path.join(find_ctf_root_directory(), ".deploy", "modules.tf"), mode="r"
    ) as f:
        modules_tf = f.read()

    module_line_regex = re.compile(
        r"^module \"track-([a-z][a-z0-9\-]{0,61}[a-z0-9])\"\s*\{$"
    )
    production_line_regex = re.compile(r"^deploy\s*=\s*\"production\"$")
    remote_line_regex = re.compile(r"^incus_remote\s*=\s*\"([^\"]+)\"$")
    build_container_line_regex = re.compile(r"^build_container\s*=\s*true$")

    tracks: set[Track] = set()
    name: str = ""
    remote: str = "local"
    production: bool = False
    require_build_container: bool = False

    for line in modules_tf.splitlines():
        if not (line := line.strip()):
            continue

        if "}" == line and name:
            tracks.add(
                Track(
                    name=name,
                    remote=remote,
                    production=production,
                    require_build_container=require_build_container,
                )
            )
            name = ""
            remote = "local"
            production = False
            require_build_container = False
            continue

        if m := module_line_regex.match(line):
            name = m.group(1)

        if production_line_regex.match(line):
            production = True

        if m := remote_line_regex.match(line):
            remote = m.group(1)

        if build_container_line_regex.match(line):
            require_build_container = True

    return tracks


def remove_tracks_from_terraform_modules(
    tracks: set[Track], remote: str, production: bool = False
):
    current_tracks = get_terraform_tracks_from_modules()

    create_terraform_modules_file(remote=remote, production=production)
    add_tracks_to_terraform_modules(tracks=(current_tracks - tracks))


def get_all_file_paths_recursively(path: str) -> Generator[str, None, None]:
    if os.path.isfile(path=path):
        yield remove_ctf_script_root_directory_from_path(path=path)
    else:
        for file in os.listdir(path=path):
            for f in get_all_file_paths_recursively(path=os.path.join(path, file)):
                yield f


def get_ctf_script_root_directory() -> str:
    return os.path.dirname(p=__file__)


def get_ctf_script_templates_directory() -> str:
    return os.path.join(get_ctf_script_root_directory(), "templates")


def get_ctf_script_schemas_directory() -> str:
    return os.path.join(get_ctf_script_root_directory(), "schemas")


def remove_ctf_script_root_directory_from_path(path: str) -> str:
    return os.path.relpath(path=path, start=find_ctf_root_directory())


def load_yaml_file(file: str) -> dict[str, Any]:
    return yaml.safe_load(stream=open(file, mode="r", encoding="utf-8"))


def parse_track_yaml(track_name: str) -> dict[str, Any]:
    r = load_yaml_file(
        p := os.path.join(
            find_ctf_root_directory(), "challenges", track_name, "track.yaml"
        )
    )
    r["file_location"] = remove_ctf_script_root_directory_from_path(path=p)

    return r


def parse_post_yamls(track_name: str) -> list[dict]:
    posts = []
    for post in os.listdir(
        path=(
            posts_dir := os.path.join(
                find_ctf_root_directory(), "challenges", track_name, "posts"
            )
        )
    ):
        if post.endswith(".yml") or post.endswith(".yaml"):
            r = load_yaml_file(os.path.join(posts_dir, post))
            r["file_location"] = remove_ctf_script_root_directory_from_path(
                path=posts_dir
            )
            posts.append(r)

    return posts


def find_ctf_root_directory() -> str:
    global __CTF_ROOT_DIRECTORY
    if __CTF_ROOT_DIRECTORY:
        return __CTF_ROOT_DIRECTORY

    path: str = (
        str(ENV.get("CTF_ROOT_DIR"))
        if "CTF_ROOT_DIR" in ENV
        else os.path.join(os.getcwd(), ".")
    )
    if not is_ctf_dir(path=path):
        while path != (path := os.path.dirname(p=path)):
            ctf_dir = is_ctf_dir(path)

            if ctf_dir:
                break

    if path == "/":
        LOG.critical(
            msg='Could not automatically find the root directory nor the "CTF_ROOT_DIR" environment variable. To initialize a new root directory, use `ctf init [path]`'
        )
        exit(1)

    LOG.debug(msg=f"Found root directory: {path}")
    return (__CTF_ROOT_DIRECTORY := path)


def is_ctf_dir(path):
    ctf_dir = True
    dir = os.listdir(path=path)
    if ".deploy" not in dir:
        ctf_dir = False
    if "challenges" not in dir:
        ctf_dir = False
    return ctf_dir


def terraform_binary() -> str:
    path = shutil.which(cmd="tofu")
    if not path:
        path = shutil.which(cmd="terraform")

    if not path:
        raise Exception("Couldn't find Terraform or OpenTofu")

    return path

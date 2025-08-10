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


def get_all_available_tracks() -> set[str]:
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

        tracks.add(entry)

    return tracks


def validate_track_can_be_deployed(track: str) -> bool:
    return (
        os.path.exists(
            path=os.path.join(
                find_ctf_root_directory(), "challenges", track, "terraform", "main.tf"
            )
        )
        and os.path.exists(
            path=os.path.join(
                find_ctf_root_directory(), "challenges", track, "ansible", "deploy.yaml"
            )
        )
        and os.path.exists(
            path=os.path.join(
                find_ctf_root_directory(), "challenges", track, "ansible", "inventory"
            )
        )
    )


def add_tracks_to_terraform_modules(
    tracks: set[str], remote: str, production: bool = False
):
    with open(
        file=os.path.join(find_ctf_root_directory(), ".deploy", "modules.tf"), mode="a"
    ) as fd:
        template = jinja2.Environment().from_string(
            source=textwrap.dedent(
                text="""\
                    {% for track in tracks %}
                    module "track-{{ track }}" {
                      source = "../challenges/{{ track }}/terraform"
                    {% if production %}
                      deploy = "production"
                    {% endif %}
                    {% if remote %}
                      incus_remote = "{{ remote }}"
                    {% endif %}

                      depends_on = [module.common]
                    }
                    {% endfor %}
                    """
            )
        )
        fd.write(
            template.render(
                tracks=tracks - get_terraform_tracks_from_modules(),
                production=production,
                remote=remote,
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
                    {% if production %}
                      deploy = "production"
                    {% endif %}
                    {% if remote %}
                      incus_remote = "{{ remote }}"
                    {% endif %}
                    }
                    """
            )
        )
        fd.write(template.render(production=production, remote=remote))


def get_terraform_tracks_from_modules() -> set[str]:
    with open(
        file=os.path.join(find_ctf_root_directory(), ".deploy", "modules.tf"), mode="r"
    ) as f:
        modules_tf = f.read()

    return set(
        re.findall(
            pattern=r"^module \"track-([a-z][a-z0-9\-]{0,61}[a-z0-9])\"",
            string=modules_tf,
            flags=re.MULTILINE,
        )
    )


def remove_tracks_from_terraform_modules(
    tracks: set[str], remote: str, production: bool = False
):
    current_tracks = get_terraform_tracks_from_modules()

    create_terraform_modules_file(remote=remote, production=production)
    add_tracks_to_terraform_modules(
        tracks=(current_tracks - tracks), remote=remote, production=production
    )


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


def parse_track_yaml(track_name: str) -> dict[str, Any]:
    r = yaml.safe_load(
        stream=open(
            file=(
                p := os.path.join(
                    find_ctf_root_directory(), "challenges", track_name, "track.yaml"
                )
            ),
            mode="r",
            encoding="utf-8",
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
            with open(
                file=os.path.join(posts_dir, post), mode="r", encoding="utf-8"
            ) as f:
                r = post_data = yaml.safe_load(stream=f)
                r["file_location"] = remove_ctf_script_root_directory_from_path(
                    path=posts_dir
                )
                posts.append(post_data)

    return posts


def find_ctf_root_directory() -> str:
    global __CTF_ROOT_DIRECTORY
    if __CTF_ROOT_DIRECTORY:
        return __CTF_ROOT_DIRECTORY

    path = (
        ENV.get("CTF_ROOT_DIR")
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
        raise
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

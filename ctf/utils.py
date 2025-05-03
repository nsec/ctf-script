import logging
import os
import re
import subprocess
import textwrap
from typing import Any, Generator

import coloredlogs
import jinja2
import yaml

LOG = logging.getLogger()
LOG.addHandler(hdlr=logging.StreamHandler())
LOG.setLevel(level=logging.DEBUG)
coloredlogs.install(level="DEBUG", logger=LOG)


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


def find_ctf_root_directory() -> str:
    path = os.path.join(os.getcwd(), ".")

    while path != (path := os.path.dirname(p=path)):
        dir = os.listdir(path=path)

        if ".git" not in dir:
            continue
        if ".deploy" not in dir:
            continue
        if "challenges" not in dir:
            continue
        break

    if path == "/":
        if "CTF_ROOT_DIR" not in os.environ:
            LOG.critical(
                msg='Could not automatically find the root directory nor the "CTF_ROOT_DIR" environment variable.'
            )
            exit(1)
        return os.environ.get("CTF_ROOT_DIR", default=".")

    LOG.debug(msg=f"Found root directory: {path}")
    return path


CTF_ROOT_DIRECTORY = find_ctf_root_directory()


def get_all_available_tracks() -> set[str]:
    tracks = set()

    for entry in os.listdir(
        path=(challenges_directory := os.path.join(CTF_ROOT_DIRECTORY, "challenges"))
    ):
        if not os.path.isdir(s=os.path.join(challenges_directory, entry)):
            continue

        tracks.add(entry)

    return tracks


def validate_track_can_be_deployed(track: str) -> bool:
    return (
        os.path.exists(
            path=os.path.join(
                CTF_ROOT_DIRECTORY, "challenges", track, "terraform", "main.tf"
            )
        )
        and os.path.exists(
            path=os.path.join(
                CTF_ROOT_DIRECTORY, "challenges", track, "ansible", "deploy.yaml"
            )
        )
        and os.path.exists(
            path=os.path.join(
                CTF_ROOT_DIRECTORY, "challenges", track, "ansible", "inventory"
            )
        )
    )


def add_tracks_to_terraform_modules(
    tracks: set[str], remote: str, production: bool = False
):
    with open(
        file=os.path.join(CTF_ROOT_DIRECTORY, ".deploy", "modules.tf"), mode="a"
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
        file=os.path.join(CTF_ROOT_DIRECTORY, ".deploy", "modules.tf"), mode="w+"
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
        file=os.path.join(CTF_ROOT_DIRECTORY, ".deploy", "modules.tf"), mode="r"
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


def get_all_file_paths_recursively(path: str) -> Generator[None, None, str]:
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
    return os.path.relpath(path=path, start=CTF_ROOT_DIRECTORY)


def parse_track_yaml(track_name: str) -> dict[str, Any]:
    r = yaml.safe_load(
        stream=open(
            file=(
                p := os.path.join(
                    CTF_ROOT_DIRECTORY, "challenges", track_name, "track.yaml"
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
                CTF_ROOT_DIRECTORY, "challenges", track_name, "posts"
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

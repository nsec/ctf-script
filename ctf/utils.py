import os
from typing import Any
import yaml
import logging
import coloredlogs

LOG = logging.getLogger()
LOG.addHandler(hdlr=logging.StreamHandler())
LOG.setLevel(level=logging.DEBUG)
coloredlogs.install(level="DEBUG", logger=LOG)


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


ROOT_DIRECTORY = find_ctf_root_directory()


def get_ctf_script_root_directory() -> str:
    return os.path.dirname(p=os.path.dirname(p=__file__))


def get_ctf_script_templates_directory() -> str:
    return os.path.join(get_ctf_script_root_directory(), "templates")


def get_ctf_script_schemas_directory() -> str:
    return os.path.join(get_ctf_script_root_directory(), "schemas")


def parse_track_yaml(track_name: str) -> dict[str, Any]:
    r = yaml.safe_load(
        stream=open(
            file=(
                p := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "track.yaml"
                )
            ),
            mode="r",
            encoding="utf-8",
        )
    )

    r["file_location"] = p

    return r


def parse_post_yamls(track_name: str) -> list[dict]:
    posts = []
    for post in os.listdir(
        path=(
            posts_dir := os.path.join(ROOT_DIRECTORY, "challenges", track_name, "posts")
        )
    ):
        if post.endswith(".yml") or post.endswith(".yaml"):
            with open(
                file=os.path.join(posts_dir, post), mode="r", encoding="utf-8"
            ) as f:
                r = post_data = yaml.safe_load(stream=f)
                r["file_location"] = posts_dir
                posts.append(post_data)

    return posts

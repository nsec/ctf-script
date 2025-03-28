import os
from typing import Any
import yaml
import logging
import coloredlogs

LOG = logging.getLogger()
LOG.addHandler(logging.StreamHandler())
LOG.setLevel(logging.DEBUG)
coloredlogs.install(level="DEBUG", logger=LOG)


def find_root_directory() -> str:
    path = os.path.join(os.getcwd(), ".")

    while path != (path := os.path.dirname(path)):
        dir = os.listdir(path=path)

        if ".git" not in dir:
            continue
        if "challenges" not in dir:
            continue
        if "schemas" not in dir:
            continue
        if "scripts" not in dir:
            continue
        break

    if path == "/":
        if "CTF_ROOT_DIR" not in os.environ:
            LOG.fatal(
                'Could not automatically find the root directory nor the "CTF_ROOT_DIR" environment variable.'
            )
            exit(1)
        return os.environ.get("CTF_ROOT_DIR", ".")

    LOG.debug(f"Found root directory: {path}")
    return path


ROOT_DIRECTORY = find_root_directory()


def parse_track_yaml(track_name: str) -> dict[str, Any]:
    return yaml.safe_load(
        open(
            f"{ROOT_DIRECTORY}/challenges/{track_name}/track.yaml",
            "r",
            encoding="utf-8",
        )
    )


def parse_post_yamls(track_name: str) -> list[dict]:
    posts_dir = f"{ROOT_DIRECTORY}/challenges/{track_name}/posts"
    posts = []
    for post in os.listdir(posts_dir):
        if post.endswith(".yml") or post.endswith(".yaml"):
            with open(f"{posts_dir}/{post}", "r", encoding="utf-8") as f:
                post_data = yaml.safe_load(f)
                posts.append(post_data)
    return posts

#!/usr/bin/env python3
import importlib.metadata
import logging
import os

import coloredlogs

ENV = {}
for k, v in os.environ.items():
    ENV[k] = v

VERSION = importlib.metadata.version("ctf-script")

LOG = logging.getLogger()
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


CTF_ROOT_DIRECTORY = find_ctf_root_directory()

#!/usr/bin/env python3
import importlib.metadata
import json
import logging
import os
import sys
import urllib.request

import coloredlogs

VERSION = importlib.metadata.version("ctf-script")

if len(sys.argv) > 1 and sys.argv[1] == "version":
    print(VERSION)
    exit(code=0)

ENV = {}
for k, v in os.environ.items():
    ENV[k] = v

LOG = logging.getLogger()
LOG.setLevel(level=logging.DEBUG)
coloredlogs.install(level="DEBUG", logger=LOG)


def check_tool_version():
    with urllib.request.urlopen(
        url="https://api.github.com/repos/nsec/ctf-script/releases/latest"
    ) as r:
        if r.getcode() != 200:
            LOG.debug(r.read().decode())
            LOG.error("Could not verify the latest release.")
        else:
            try:
                latest_version = json.loads(s=r.read().decode())["tag_name"]
            except Exception as e:
                LOG.debug(e)
                LOG.error("Could not verify the latest release.")

        compare = 0
        for current_part, latest_part in zip(
            [int(part) for part in VERSION.split(".")],
            [int(part) for part in latest_version.split(".")],
        ):
            if current_part < latest_part:
                compare = -1
                break
            elif current_part > latest_part:
                compare = 1
                break

        match compare:
            case 0 | 1:
                LOG.debug("Script is up to date.")
            case -1:
                LOG.critical(
                    "Script is outdated. Please update to the latest release before continuing."
                )
                exit(code=1)


check_tool_version()


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

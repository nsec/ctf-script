#!/usr/bin/env python3
import importlib.metadata
import json
import os
import sys
import urllib.request

from ctf.logger import LOG
from ctf.utils import (
    find_ctf_root_directory,
    get_ctf_script_schemas_directory,
    get_ctf_script_templates_directory,
)

VERSION = importlib.metadata.version("ctf-script")

if len(sys.argv) > 1 and sys.argv[1] == "version":
    print(VERSION)
    exit(code=0)


ENV = {}
for k, v in os.environ.items():
    ENV[k] = v

match sys.argv[1] if len(sys.argv) > 1 else "":
    case "init":
        CTF_ROOT_DIRECTORY = os.path.join(os.getcwd(), ".")
    case "version":
        CTF_ROOT_DIRECTORY = ""
    case _:
        CTF_ROOT_DIRECTORY = find_ctf_root_directory()

TEMPLATES_ROOT_DIRECTORY = get_ctf_script_templates_directory()
SCHEMAS_ROOT_DIRECTORY = get_ctf_script_schemas_directory()


def check_tool_version() -> None:
    with urllib.request.urlopen(
        url="https://api.github.com/repos/nsec/ctf-script/releases/latest"
    ) as r:
        if r.getcode() != 200:
            LOG.debug(r.read().decode())
            LOG.error("Could not verify the latest release.")
            return
        else:
            try:
                latest_version = json.loads(s=r.read().decode())["tag_name"]
            except Exception as e:
                LOG.debug(e)
                LOG.error("Could not verify the latest release.")
                return

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
                LOG.warning(
                    f"Script is outdated (current: {VERSION}, upstream: {latest_version}). Please update to the latest release before continuing."
                )
                if (input("Do you want to continue? [y/N] ").lower() or "n") == "n":
                    exit(code=0)


check_tool_version()

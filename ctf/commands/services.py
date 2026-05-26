import os
import socket

import requests
import rich
import typer
from typing_extensions import Annotated

from ctf.common.logger import LOG
from ctf.common.utils import find_ctf_root_directory, parse_track_yaml

app = typer.Typer()


@app.command(help="Get services from tracks")
def services(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Only services from the given tracks (use the directory name)",
        ),
    ] = [],
    check: Annotated[
        bool, typer.Option("--check", "-c", help="Check every service")
    ] = False,
) -> None:
    distinct_tracks: set[str] = set()
    for entry in os.listdir(
        challenges_directory := (find_ctf_root_directory() / "challenges")
    ):
        if (track_directory := (challenges_directory / entry)).is_dir() and (
            track_directory / "track.yaml"
        ).exists():
            if not tracks:
                distinct_tracks.add(entry)
            elif entry in tracks:
                distinct_tracks.add(entry)

    all_services = []

    for track in distinct_tracks:
        LOG.debug(f"Parsing track.yaml for track {track}")
        track_yaml = parse_track_yaml(track_name=track)

        services = track_yaml.get("services", [])
        for instance_name, instance in track_yaml.get("instances", {}).items():
            services += [
                {"instance": instance_name, "address": instance.get("ipv6"), **service}
                for service in instance.get("services", [])
            ]

        if len(services) == 0:
            LOG.debug(f"No service in track {track}. Skipping...")
            continue

        for service in services:
            contact = ",".join(track_yaml["contacts"]["support"])
            name = service["name"]
            instance = service["instance"]
            address = service["address"]
            check_type = service["check"]
            port = service["port"]

            rich.print(
                f"{instance}/{name} {contact.replace(' ', '_')} {address} {check_type} {port}",
            )

        all_services += services

    if check:
        LOG.info("Checking services...")
        for service in all_services:
            name = service["name"]
            instance = service["instance"]
            address = service["address"]
            check_type = service["check"]
            port = service["port"]

            LOG.info(f"Checking {check_type} {instance}/{name} at {address}:{port}...")

            if check_type == "tcp":
                success = check_tcp_port(host=address, port=port)
                if not success:
                    LOG.error(
                        f"TCP Service {instance}/{name} is NOT responding on {address}:{port}"
                    )
            elif check_type == "http":
                try:
                    response = requests.get(
                        f"http://[{address}]:{port}", timeout=5, verify=False
                    )
                    success = response.status_code == 200
                    print(
                        f"HTTP Service {instance}/{name} returned status code: {response.status_code}"
                    )

                except Exception as e:
                    LOG.error(
                        f"Error occurred while checking HTTP service {instance}/{name}: {e}"
                    )
                    success = False
                if not success:
                    LOG.error(
                        f"HTTP Service {instance}/{name} is NOT responding on {address}:{port}"
                    )
            else:
                LOG.warning(
                    f"Unknown check type {check_type} for service {instance}/{name}. Skipping check."
                )


def check_tcp_port(host, port, timeout=2):
    """
    Checks if a TCP port is open at a specific host.
    Returns True if open, False otherwise.
    """
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        # connect_ex returns 0 on success, and an error code on failure
        result = s.connect_ex((host, port))
        success = result == 0
    return success

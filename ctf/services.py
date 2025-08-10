import os

import rich
import typer
from typing_extensions import Annotated

from ctf.logger import LOG
from ctf.utils import find_ctf_root_directory, parse_track_yaml

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
) -> None:
    distinct_tracks: set[str] = set()
    for entry in os.listdir(
        path=(
            challenges_directory := os.path.join(
                find_ctf_root_directory(), "challenges"
            )
        )
    ):
        if os.path.isdir(
            s=(track_directory := os.path.join(challenges_directory, entry))
        ) and os.path.exists(path=os.path.join(track_directory, "track.yaml")):
            if not tracks:
                distinct_tracks.add(entry)
            elif entry in tracks:
                distinct_tracks.add(entry)

    for track in distinct_tracks:
        LOG.debug(msg=f"Parsing track.yaml for track {track}")
        track_yaml = parse_track_yaml(track_name=track)

        if len(track_yaml["services"]) == 0:
            LOG.debug(msg=f"No service in track {track}. Skipping...")
            continue

        for service in track_yaml["services"]:
            contact = ",".join(track_yaml["contacts"]["support"])
            name = service["name"]
            instance = service["instance"]
            address = service["address"]
            check = service["check"]
            port = service["port"]

            rich.print(f"{track}/{instance}/{name} {contact} {address} {check} {port}")

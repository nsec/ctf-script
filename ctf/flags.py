import csv
import io
import json
import os

import rich
import typer
import yaml
from typing_extensions import Annotated

from ctf.logger import LOG
from ctf.models import OutputFormat, Track
from ctf.utils import find_ctf_root_directory, parse_track_yaml

app = typer.Typer()


@app.command(help="Get flags from tracks")
def flags(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Only flags from the given tracks (use the directory name)",
        ),
    ] = [],
    format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Output format", prompt="Output format"),
    ] = OutputFormat.JSON,
) -> None:
    distinct_tracks: set[Track] = set()

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
                distinct_tracks.add(Track(name=entry))
            elif entry in tracks:
                distinct_tracks.add(Track(name=entry))

    flags = []
    for track in distinct_tracks:
        LOG.debug(msg=f"Parsing track.yaml for track {track.name}")
        track_yaml = parse_track_yaml(track_name=track.name)

        if len(track_yaml["flags"]) == 0:
            LOG.debug(msg=f"No flag in track {track.name}. Skipping...")
            continue

        flags.extend(track_yaml["flags"])

    if not flags:
        LOG.warning(msg="No flag found...")
        return

    if format == OutputFormat.JSON:
        rich.print(json.dumps(obj=flags, indent=2))
    elif format == OutputFormat.CSV:
        output = io.StringIO()
        writer = csv.DictWriter(f=output, fieldnames=flags[0].keys())
        writer.writeheader()
        writer.writerows(rowdicts=flags)
        rich.print(output.getvalue())
    elif format == OutputFormat.YAML:
        rich.print(yaml.safe_dump(data=flags))

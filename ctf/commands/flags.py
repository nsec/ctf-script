import csv
import io
import json
import os
from enum import StrEnum

import rich
import typer
import yaml
from typing_extensions import Annotated

from ctf.common.logger import LOG
from ctf.common.models import Track
from ctf.common.utils import find_ctf_root_directory, parse_track_yaml

app = typer.Typer()


class OutputFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"


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
        challenges_directory := (find_ctf_root_directory() / "challenges")
    ):
        if (track_directory := challenges_directory / entry).is_dir() and (
            track_directory / "track.yaml"
        ).exists():
            if not tracks:
                distinct_tracks.add(Track(name=entry))
            elif entry in tracks:
                distinct_tracks.add(Track(name=entry))

    flags = []
    for track in distinct_tracks:
        LOG.debug(f"Parsing track.yaml for track {track.name}")
        track_yaml = parse_track_yaml(track_name=track.name)

        if len(track_yaml["flags"]) == 0:
            LOG.debug(f"No flag in track {track.name}. Skipping...")
            continue

        track_flags = track_yaml["flags"]
        for track_flag in track_flags:
            track_flag["return_string"] = (
                f"{track_flag['return_string']} [{track_flag.get('cfss')}]"
            )
        flags.extend(track_flags)

    if not flags:
        LOG.warning("No flag found...")
        return

    if format == OutputFormat.JSON:
        rich.print(rich.markup.escape(json.dumps(obj=flags, indent=2)))
    elif format == OutputFormat.CSV:
        output = io.StringIO()
        writer = csv.DictWriter(f=output, fieldnames=flags[0].keys())
        writer.writeheader()
        writer.writerows(rowdicts=flags)
        rich.print(rich.markup.escape(output.getvalue()))
    elif format == OutputFormat.YAML:
        rich.print(rich.markup.escape(yaml.safe_dump(data=flags)))

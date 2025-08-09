import os
from enum import StrEnum

import rich
import typer
from rich.table import Table
from typing_extensions import Annotated

from ctf import CTF_ROOT_DIRECTORY
from ctf.utils import parse_post_yamls, parse_track_yaml

app = typer.Typer()


class ListOutputFormat(StrEnum):
    PRETTY = "pretty"


@app.command("list", help="List tracks and their author(s).")
def list_tracks(
    format: Annotated[
        ListOutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = ListOutputFormat.PRETTY,
) -> None:
    tracks: set[str] = set()
    for track in os.listdir(path=os.path.join(CTF_ROOT_DIRECTORY, "challenges")):
        if os.path.isdir(
            s=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track)
        ) and os.path.exists(
            path=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track, "track.yaml")
        ):
            tracks.add(track)

    parsed_tracks = []
    for track in tracks:
        parsed_track = parse_track_yaml(track)

        # find the discourse topic name
        posts = parse_post_yamls(track)
        topic = None
        for post in posts:
            if post.get("type") == "topic":
                topic = post["title"]
        parsed_tracks.append(
            [
                parsed_track["name"],
                topic,
                ", ".join(parsed_track["contacts"]["dev"]),
                ", ".join(parsed_track["contacts"]["support"]),
                ", ".join(parsed_track["contacts"]["qa"]),
            ]
        )

    if format.value == "pretty":
        table = Table(title="Tracks")
        table.add_column("Internal track name", style="cyan")
        table.add_column("Discourse topic name", style="magenta")
        table.add_column("Dev")
        table.add_column("Support")
        table.add_column("QA")

        for parsed_track in sorted(parsed_tracks, key=lambda x: x[0].lower()):
            table.add_row(*parsed_track)

        rich.print(table)
    else:
        raise ValueError(f"Invalid format: {format.value}")

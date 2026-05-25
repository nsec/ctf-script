from enum import StrEnum

import rich
import typer
from rich.table import Table
from typing_extensions import Annotated

from ctf.common.models import Track
from ctf.common.utils import find_ctf_root_directory, parse_post_yamls, parse_track_yaml

app = typer.Typer()


class ListOutputFormat(StrEnum):
    PRETTY = "pretty"


@app.command("list", help="List tracks and their author(s).")
def list_tracks(
    format: Annotated[
        ListOutputFormat, typer.Option("--format", "-f", help="Output format")
    ] = ListOutputFormat.PRETTY,
) -> None:
    tracks: set[Track] = set()
    for track in (find_ctf_root_directory() / "challenges").iterdir():
        if (find_ctf_root_directory() / "challenges" / track).is_dir() and (
            find_ctf_root_directory() / "challenges" / track / "track.yaml"
        ).exists():
            tracks.add(Track(name=track.name))

    parsed_tracks = []
    for track in tracks:
        parsed_track = parse_track_yaml(track.name)

        # find the discourse topic name
        posts = parse_post_yamls(track.name)
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

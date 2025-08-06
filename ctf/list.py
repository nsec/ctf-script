import os
from enum import StrEnum

import typer
from tabulate import tabulate
from typing_extensions import Annotated

from ctf import LOG
from ctf.utils import CTF_ROOT_DIRECTORY, parse_track_yaml, parse_post_yamls

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
        LOG.info(
            "\n"
            + tabulate(
                parsed_tracks,
                headers=[
                    "Internal track name",
                    "Discourse Topic Name",
                    "Dev",
                    "Support",
                    "QA",
                ],
                tablefmt="fancy_grid",
            )
        )
    else:
        raise ValueError(f"Invalid format: {format.value}")

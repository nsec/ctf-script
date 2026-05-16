import os
import re
import textwrap
from enum import StrEnum

import typer
from typing_extensions import Annotated

from ctf.logger import LOG
from ctf.utils import find_ctf_root_directory, parse_track_yaml

app = typer.Typer(no_args_is_help=True)


class ApiUser(StrEnum):
    NSEC = "nsec"
    SYSTEM = "system"


class TriggerType(StrEnum):
    FLAG = "flag"


def _format_yaml_block(text: str) -> str:
    lines = text.splitlines() or [""]
    return "\n".join(f"  {line}" for line in lines)


def _default_post_filename(track: str, tag: str) -> str:
    normalized_track = track.replace("-", "_")
    suffix = tag
    if tag.startswith(normalized_track + "_"):
        suffix = tag[len(normalized_track) + 1 :]
    suffix = re.sub(r"[^a-zA-Z0-9_-]+", "-", suffix).strip("-_")
    if not suffix:
        suffix = "post"
    return f"{track}-{suffix.replace('_', '-')}.yaml"


def _get_available_discourse_tags(track: str) -> list[str]:
    track_yaml = parse_track_yaml(track_name=track)
    tags: set[str] = set()
    for flag in track_yaml.get("flags", []):
        discourse_tag = ((flag or {}).get("tags") or {}).get("discourse")
        if isinstance(discourse_tag, str) and discourse_tag.strip():
            tags.add(discourse_tag.strip())
    return sorted(tags)


def _add_counter_to_filename(posts_directory: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".yaml"

    candidate = f"{base}{ext}"
    if not os.path.exists(os.path.join(posts_directory, candidate)):
        return candidate

    counter = 2
    while os.path.exists(os.path.join(posts_directory, f"{base}-{counter}{ext}")):
        counter += 1
    return f"{base}-{counter}{ext}"


def _resolve_post_file_path(
    posts_directory: str,
    track: str,
    name: str | None,
    tag: str | None,
    force: bool,
) -> str:
    filename = (
        f"{track}-{name}.yaml"
        if name
        else (
            _default_post_filename(track=track, tag=tag)
            if tag
            else f"{track}-post.yaml"
        )
    )

    if not force:
        filename = _add_counter_to_filename(posts_directory, filename)

    return os.path.join(posts_directory, filename)


def _render_post_yaml(
    track: str,
    user: ApiUser,
    body: str,
    trigger: TriggerType | None = None,
    tag: str | None = None,
) -> str:
    trigger_block = ""
    if trigger == TriggerType.FLAG:
        trigger_block = textwrap.dedent(
            f"""\
            trigger:
              type: flag
              tag: {tag}
            """
        )

    return (
        textwrap.dedent(
            f"""\
            type: post
            topic: {track}
            {trigger_block}api:
              user: {user.value}
            body: |-
            {_format_yaml_block(body)}
            """
        ).rstrip()
        + "\n"
    )


@app.command("new", help="Create a new discourse post YAML file for a track.")
def new_post(
    track: Annotated[
        str,
        typer.Option(
            "--track",
            "-t",
            help="Track name (challenge directory name).",
        ),
    ],
    tag: Annotated[
        str | None,
        typer.Option(
            "--tag",
            help="Discourse trigger tag, usually from track.yaml flag tags.discourse. Required when --trigger flag is set.",
        ),
    ] = None,
    trigger: Annotated[
        TriggerType | None,
        typer.Option(
            "--trigger",
            help="Trigger type for this post. If omitted, no trigger block is added.",
        ),
    ] = None,
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Post file name. Defaults to a name derived from the track and tag.",
        ),
    ] = None,
    user: Annotated[
        ApiUser,
        typer.Option("--user", help="Discourse user posting this message."),
    ] = ApiUser.NSEC,
    body: Annotated[
        str,
        typer.Option("--body", help="Post body. Markdown is supported."),
    ] = "CHANGE_ME",
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the post file if it already exists."),
    ] = False,
) -> None:
    challenges_track_directory = os.path.join(
        find_ctf_root_directory(), "challenges", track
    )
    if not os.path.isdir(challenges_track_directory):
        LOG.critical(
            f"Track directory not found: {challenges_track_directory}. Verify --track."
        )
        raise typer.Exit(code=1)

    posts_directory = os.path.join(challenges_track_directory, "posts")
    os.makedirs(posts_directory, exist_ok=True)

    # TODO: add support for other triggers
    if trigger == TriggerType.FLAG and not tag:
        LOG.critical("--tag is required when --trigger flag is provided.")
        raise typer.Exit(code=1)

    if trigger != TriggerType.FLAG and tag:
        LOG.critical("--tag can only be used with --trigger flag.")
        raise typer.Exit(code=1)

    if trigger == TriggerType.FLAG and tag:
        valid_tags = _get_available_discourse_tags(track=track)
        if tag not in valid_tags:
            if valid_tags:
                LOG.critical(
                    f'Invalid --tag "{tag}" for track "{track}". Valid tags: {", ".join(valid_tags)}'
                )
            else:
                LOG.critical(
                    f'Invalid --tag "{tag}" for track "{track}". No discourse tags were found in track.yaml flags[].tags.discourse.'
                )
            raise typer.Exit(code=1)

    post_file_path = _resolve_post_file_path(
        posts_directory=posts_directory,
        track=track,
        name=name,
        tag=tag,
        force=force,
    )

    post_yaml = _render_post_yaml(
        track=track,
        user=user,
        body=body,
        trigger=trigger,
        tag=tag,
    )

    with open(post_file_path, "w", encoding="utf-8") as f:
        f.write(post_yaml)

    LOG.info(f"Created post file: {post_file_path}")

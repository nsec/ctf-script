import datetime
import json
import os
from enum import StrEnum
from pathlib import Path

import typer
from pydantic import BaseModel, field_validator
from rich.prompt import Confirm, IntPrompt, Prompt
from typing_extensions import Annotated

from ctf.common.logger import LOG
from ctf.common.models import Track
from ctf.common.utils import (
    get_all_available_tracks,
    get_ctf_script_schemas_directory,
    parse_track_yaml,
)

app = typer.Typer()


class TriggerType(StrEnum):
    FLAG = "flag"
    NONE = "none"
    SCORE = "score"
    TIMER = "timer"


class ApiPost(BaseModel):
    user: str
    body: str

    @field_validator("user", mode="after")
    @classmethod
    def is_even(cls, value: str) -> str:
        if value not in _get_api_users_from_schema():
            raise ValueError(
                f"{value} is not a valid user from {_get_api_users_from_schema()}"
            )
        return value


__API_USERS: list[str] = []


def _get_api_users_from_schema(lowercase: bool = False) -> list[str]:
    global __API_USERS
    if not __API_USERS:
        __API_USERS = json.load(
            (get_ctf_script_schemas_directory() / "post.json").open(
                mode="r", encoding="utf-8"
            )
        )["properties"]["api"]["properties"]["user"]["enum"]

    if lowercase:
        return [user.lower() if lowercase else user for user in __API_USERS]

    return __API_USERS


def _validate_user(value: str | None) -> str | None:
    if value and value not in _get_api_users_from_schema(lowercase=True):
        raise typer.BadParameter(
            f"{value} is not a valid user from {_get_api_users_from_schema()}"
        )

    return value


def _autocomplete_user(value: str) -> list[str]:
    completion: list[str] = []
    for name in _get_api_users_from_schema():
        if name.lower().startswith(value.lower()):
            completion.append(name)
    return completion


def _format_yaml_block(text: str, indent: int = 2) -> str:
    lines = text.splitlines() or [""]
    return "\n".join(f"{' ' * indent}{line}" for line in lines)


def _get_available_discourse_tags(track: Track) -> list[str]:
    track_yaml = parse_track_yaml(track_name=track.name)
    tags: set[str] = set()
    for flag in track_yaml.get("flags", []):
        discourse_tag = ((flag or {}).get("tags") or {}).get("discourse")
        if isinstance(discourse_tag, str) and discourse_tag.strip():
            tags.add(discourse_tag.strip())
    return sorted(tags)


def _add_counter_to_filename(posts_directory: Path, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    if not ext:
        ext = ".yaml"

    candidate = f"{base}{ext}"
    if not (posts_directory / candidate).exists():
        return candidate

    counter = 2
    while (posts_directory / f"{base}-{counter}{ext}").exists():
        counter += 1
    return f"{base}-{counter}{ext}"


def _resolve_post_file_path(
    posts_directory: Path,
    track: Track,
    name: str | None,
    force: bool,
) -> Path:
    filename = f"{track}-{name}.yaml" if name else (f"{track}-post.yaml")

    if not force:
        filename = _add_counter_to_filename(posts_directory, filename)

    return posts_directory / filename


def _render_post_yaml(
    track: Track,
    api_posts: list[ApiPost],
    trigger: TriggerType,
    tags: list[str] = [],
    score_value: int | None = None,
    threshold: int | None = None,
    timer_after: datetime.datetime | None = None,
) -> str:
    lines: list[str] = [
        f"type: post{'s' if len(api_posts) > 1 else ''}",
        f"topic: {track}",
        "",
    ]

    match trigger:
        case TriggerType.FLAG:
            lines.extend(
                [
                    "trigger:",
                    f"  type: {trigger}",
                ]
            )
            if len(tags) > 1:
                lines.append("  tags:")
                for tag in tags:
                    lines.append(f"    - {tag}")
            else:
                lines.append(f"{tags[0]}")

            if threshold:
                lines.append(f"  threshold: {threshold}")
        case TriggerType.SCORE:
            if not score_value:
                LOG.critical(
                    "--value parameter is required when using the score trigger."
                )
                raise typer.Exit(1)

            lines.extend(
                [
                    "trigger:",
                    f"  type: {trigger}",
                    f"  value: {score_value}",
                ]
            )
        case TriggerType.TIMER:
            if not timer_after:
                LOG.critical(
                    "--after parameter is required when using the timer trigger."
                )
                raise typer.Exit(1)

            lines.extend(
                [
                    "trigger:",
                    f"  type: {trigger}",
                    f"  after: {timer_after.strftime('%Y/%m/%d %H:%M')}",
                ]
            )
        case TriggerType.NONE:
            ...

    if len(api_posts) > 1:
        lines.append("posts:")
        for api_post in api_posts:
            lines.extend(
                [
                    "  - api:",
                    f"      user: {api_post.user}",
                    "    body: |-",
                    _format_yaml_block(api_post.body, indent=6),
                ]
            )

    else:
        lines.extend(
            [
                "api:",
                f"  user: {api_posts[0].user}",
                "body: |-",
                _format_yaml_block(api_posts[0].body),
            ]
        )

    return "\n".join(lines) + "\n"


@app.command(
    "new",
    help="Create a new discourse post YAML file for a track.",
    no_args_is_help=True,
)
def new(
    track: Annotated[
        str,
        typer.Option(
            "-t",
            "--track",
            help="Track name (challenge directory name).",
        ),
    ],
    trigger: Annotated[
        TriggerType,
        typer.Option(
            "--trigger",
            help="Trigger type for this post. If omitted, no trigger block is added.",
        ),
    ] = TriggerType.NONE,
    name: Annotated[
        str | None,
        typer.Option(
            "-n",
            "--name",
            help="Post file name. Defaults to a name derived from the track and tag.",
        ),
    ] = None,
    user: Annotated[
        str | None,
        typer.Option(
            "--user",
            help="Discourse user posting this message. If multiple users, use --multiple-users instead.",
            callback=_validate_user,
            autocompletion=_autocomplete_user,
            case_sensitive=False,
        ),
    ] = None,
    body: Annotated[
        str,
        typer.Option(
            "--body",
            help="Post body. Markdown is supported. Do not use when using --multiple-users.",
        ),
    ] = "CHANGE_ME",
    tags: Annotated[
        list[str],
        typer.Option(
            "-T",
            "--tags",
            help="Discourse trigger tag, usually from track.yaml flag tags.discourse. Required when --trigger=flag is set.",
        ),
    ] = [],
    threshold: Annotated[
        int | None,
        typer.Option(
            "--threshold",
            help="Amount of flags (tags) required to trigger. Required when --trigger=flag is set. Must be lower than the amount of tags provided.",
        ),
    ] = None,
    score_value: Annotated[
        int | None,
        typer.Option(
            "--value",
            help="Score value. When the team has reached that score, the post will trigger. Required when --trigger=score is set.",
        ),
    ] = None,
    timer_after: Annotated[
        datetime.datetime | None,
        typer.Option(
            "--after",
            help="After a specific date. Required when --trigger=timer is set.",
            formats=["%Y/%m/%d %H:%M"],
        ),
    ] = None,
    multiple_users: Annotated[
        bool,
        typer.Option(
            "-M",
            "--multiple-users",
            help="Multiple users for the post file. This results in multiple posts in one post file.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite the post file if it already exists."),
    ] = False,
) -> None:
    api_posts: list[ApiPost] = []
    if (track_obj := Track(name=track)) not in get_all_available_tracks():
        LOG.critical(f"Track directory not found: {track_obj.name}. Verify --track.")
        raise typer.Exit(1)

    posts_directory: Path = track_obj.location / "posts"
    os.makedirs(posts_directory, exist_ok=True)

    if multiple_users:
        while True:
            u = Prompt.ask(
                "user",
                choices=_get_api_users_from_schema(),
                show_choices=True,
                case_sensitive=False,
            )
            b = Prompt.ask("body")

            api_posts.append(ApiPost(user=u, body=b))

            if not Confirm.ask("Adding more?"):
                break
    else:
        if not user:
            user = Prompt.ask(
                "user",
                choices=_get_api_users_from_schema(),
                show_choices=True,
                case_sensitive=False,
            )

        if (
            user not in _get_api_users_from_schema()
            and user in _get_api_users_from_schema(lowercase=True)
        ):
            user = [u for u in _get_api_users_from_schema() if user == u.lower()][0]

        api_posts.append(ApiPost(user=user, body=body))

    match trigger:
        case TriggerType.FLAG:
            if not tags:
                LOG.critical("--tags is required when --trigger=flag is provided.")
                raise typer.Exit(1)

            if not (valid_tags := _get_available_discourse_tags(track=track_obj)):
                LOG.critical(
                    f"No discourse tags were found in track.yaml flags[].tags.discourse for {track_obj.name}"
                )
                raise typer.Exit(1)

            for tag in tags:
                if tag not in valid_tags:
                    LOG.critical(
                        f'Invalid --tag "{tag}" for track "{track_obj.name}". Valid tags: {", ".join(valid_tags)}'
                    )
                raise typer.Exit(1)

            if threshold and (threshold <= 0 or threshold > len(tags)):
                LOG.critical(
                    "Threshold must be higher than 0 and lower than the amount of tags provided."
                )
                raise typer.Exit(1)
        case TriggerType.SCORE:
            if not score_value:
                while (
                    score_value := IntPrompt.ask(
                        "Please enter the score at which this post will trigger for teams [bold magenta]\\[x>0][/bold magenta]"
                    )
                ) <= 0:
                    LOG.warning("The score must be positive and above 0.")
        case TriggerType.TIMER:
            while True:
                if timer_after:
                    if timer_after >= datetime.datetime.now():
                        break

                    LOG.warning("The date must be in the future.")
                try:
                    timer_after = datetime.datetime.strptime(
                        Prompt.ask(
                            "Enter a datetime in the futur [bold magenta]\\[YYYY/MM/DD HH:MM][/bold magenta]"
                        ),
                        "%Y/%m/%d %H:%M",
                    )

                    if timer_after < datetime.datetime.now():
                        LOG.warning("The date must be in the future.")
                        continue

                    break
                except ValueError:
                    LOG.warning("The provided string was not a valid date.")

        case TriggerType.NONE:
            if not Confirm.ask(
                "Without a trigger, the post will [bold red]automatically be submitted to all teams[/bold red]. This is usually used for [bold cyan]hints[/bold cyan]. Is this what you want?",
                default=False,
            ):
                raise typer.Exit(0)

    post_file_path: Path = _resolve_post_file_path(
        posts_directory=posts_directory,
        track=track_obj,
        name=name,
        force=force,
    )

    post_yaml: str = _render_post_yaml(
        track=track_obj,
        api_posts=api_posts,
        trigger=trigger,
        tags=tags,
        threshold=threshold,
        score_value=score_value,
        timer_after=timer_after,
    )

    with post_file_path.open(mode="w", encoding="utf-8") as f:
        f.write(post_yaml)

    LOG.info(f"Created post file: {post_file_path}")

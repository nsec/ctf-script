import re
import subprocess
import textwrap

import rich.table
import typer
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)

from ctf.common.logger import LOG
from ctf.common.utils import find_ctf_root_directory, get_ctf_script_schemas_directory
from ctf.common.validators import ValidationError, validators_list
from ctf.validate_json_schemas import validate_with_json_schemas

app = typer.Typer()


@app.command(
    help="Run many static validations to ensure coherence and quality in the tracks and repo as a whole."
)
def validate() -> None:
    LOG.info("Starting ctf validate...")

    LOG.info(f"Found {len(validators_list)} Validators")

    validators = [validator_class() for validator_class in validators_list]

    tracks = []
    for track in (find_ctf_root_directory() / "challenges").iterdir():
        if (find_ctf_root_directory() / "challenges" / track).is_dir() and (
            find_ctf_root_directory() / "challenges" / track / "track.yaml"
        ).exists():
            tracks.append(track.name)

    LOG.info(f"Found {len(tracks)} tracks")

    errors: list[ValidationError] = []

    LOG.debug("Validating track.yaml files against JSON Schema...")
    validate_with_json_schemas(
        schema=get_ctf_script_schemas_directory() / "track.yaml.json",
        files_pattern=str(
            find_ctf_root_directory() / "challenges" / "*" / "track.yaml"
        ),
    )
    LOG.debug("Validating discourse post YAML files against JSON Schema...")
    validate_with_json_schemas(
        schema=get_ctf_script_schemas_directory() / "post.json",
        files_pattern=str(
            find_ctf_root_directory() / "challenges" / "*" / "posts" / "*.yaml"
        ),
    )

    LOG.info("Validating terraform files format...")
    r = subprocess.run(
        args=[
            "tofu",
            "fmt",
            "-no-color",
            "-check",
            "-recursive",
            find_ctf_root_directory(),
        ],
        capture_output=True,
    )
    if r.returncode != 0:
        errors.append(
            ValidationError(
                error_name="Tofu format",
                error_description="Bad Terraform formatting. Please run `tofu fmt -recursive ./`",
                details={
                    "Files": "\n".join(
                        [
                            *([out] if (out := r.stdout.decode().strip()) else []),
                            *re.findall(
                                pattern=r"(Failed to read file .+)$",
                                string=r.stderr.decode().strip(),
                                flags=re.MULTILINE,
                            ),
                        ]
                    )
                },
            )
        )

    with Progress(
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        TextColumn("{task.description}"),
    ) as progress:
        task = progress.add_task(
            "Running Validators...", total=(len(validators) * len(tracks))
        )

        for validator in validators:
            LOG.debug(f"Running {type(validator).__name__}")
            for track in tracks:
                errors += validator.validate(track_name=track)
                progress.update(task, advance=1)
        task = progress.add_task("Finalizing Validators...", total=len(validators))
        # Get the errors from finalize()
        for validator in validators:
            errors += validator.finalize()
            progress.update(task, advance=1)

    if not errors:
        LOG.info("No error found!")
    else:
        LOG.error(msg=f"{len(errors)} errors found.")

        errors_list = list(
            map(
                lambda error: [
                    error.track_name,
                    error.error_name,
                    "\n".join(textwrap.wrap(error.error_description, 50)),
                    "\n".join(
                        [
                            str(key) + ": " + str(value)
                            for key, value in error.details.items()
                        ]
                    ),
                ],
                errors,
            )
        )

        table = rich.table.Table(
            title=f"❌ Found {len(errors_list)} validation error(s)", expand=True
        )
        table.add_column("Track", style="cyan", no_wrap=True)
        table.add_column("Error", style="red")
        table.add_column("Description")
        table.add_column("Details", style="magenta")
        for error in errors_list:
            table.add_row(*error)

        rich.print(table)

        exit(1)

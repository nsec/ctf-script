import os
import re
import subprocess
import textwrap

import typer
from tabulate import tabulate

from ctf import CTF_ROOT_DIRECTORY, SCHEMAS_ROOT_DIRECTORY
from ctf.logger import LOG
from ctf.validate_json_schemas import validate_with_json_schemas
from ctf.validators import ValidationError, validators_list

app = typer.Typer()


@app.command(
    help="Run many static validations to ensure coherence and quality in the tracks and repo as a whole."
)
def validate() -> None:
    LOG.info(msg="Starting ctf validate...")

    LOG.info(msg=f"Found {len(validators_list)} Validators")

    validators = [validator_class() for validator_class in validators_list]

    tracks = []
    for track in os.listdir(path=os.path.join(CTF_ROOT_DIRECTORY, "challenges")):
        if os.path.isdir(
            s=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track)
        ) and os.path.exists(
            path=os.path.join(CTF_ROOT_DIRECTORY, "challenges", track, "track.yaml")
        ):
            tracks.append(track)

    LOG.info(msg=f"Found {len(tracks)} tracks")

    errors: list[ValidationError] = []

    LOG.info(msg="Validating track.yaml files against JSON Schema...")
    validate_with_json_schemas(
        schema=os.path.join(SCHEMAS_ROOT_DIRECTORY, "track.yaml.json"),
        files_pattern=os.path.join(CTF_ROOT_DIRECTORY, "challenges", "*", "track.yaml"),
    )
    LOG.info(msg="Validating discourse post YAML files against JSON Schema...")
    validate_with_json_schemas(
        schema=os.path.join(SCHEMAS_ROOT_DIRECTORY, "post.json"),
        files_pattern=os.path.join(
            CTF_ROOT_DIRECTORY, "challenges", "*", "posts", "*.yaml"
        ),
    )

    LOG.info(msg="Validating terraform files format...")
    r = subprocess.run(
        args=["tofu", "fmt", "-no-color", "-check", "-recursive", CTF_ROOT_DIRECTORY],
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

    for validator in validators:
        LOG.info(msg=f"Running {type(validator).__name__}")
        for track in tracks:
            errors += validator.validate(track_name=track)

    # Get the errors from finalize()
    for validator in validators:
        errors += validator.finalize()

    if not errors:
        LOG.info(msg="No error found!")
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

        LOG.error(
            "\n"
            + tabulate(
                errors_list,
                headers=["Track", "Error", "Description", "Details"],
                tablefmt="fancy_grid",
            )
        )
        exit(code=1)

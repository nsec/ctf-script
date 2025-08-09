import argparse
import glob
import json

import jsonschema
import rich
import yaml
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from ctf import LOG


def validate_with_json_schemas(schema: str, files_pattern: str) -> None:
    LOG.debug(msg="Starting JSON Schema validator")
    LOG.debug(msg=f"Schema: {schema}")

    schema = json.load(open(file=schema, mode="r", encoding="utf-8"))

    if not isinstance(schema, dict):
        LOG.error(msg=f"Loaded schema was not a dictionary: {schema}")
        exit(code=1)

    errors = []
    with Progress(
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        TextColumn("{task.description}"),
    ) as progress:
        files = list(glob.glob(pathname=files_pattern))
        task = progress.add_task(f"Validating JSON ({files_pattern})", total=len(files))
        for file in files:
            LOG.debug(msg=f"Validating {file}")
            yaml_document = yaml.safe_load(
                stream=open(file=file, mode="r", encoding="utf-8")
            )
            try:
                jsonschema.validate(instance=yaml_document, schema=schema)
            except jsonschema.ValidationError as e:
                errors.append((file, e))
            progress.update(task, advance=1)

    if errors:
        LOG.error(msg=f"{len(errors)} error(s) in JSON Schema validation found")
        table = Table(title="Errors")
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Error", style="magenta", no_wrap=False)
        for filename, error in errors:
            table.add_row(filename, error.message)
        rich.print(table)
        exit(code=1)
    else:
        LOG.debug(msg="No error found!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--schema",
        help="Path to a JSON Schema file to use for validation",
        required=True,
    )
    parser.add_argument(
        "--files-pattern",
        help="glob pattern to match the files to validate.",
        required=True,
    )
    args = parser.parse_args()
    validate_with_json_schemas(schema=args.schema, files_pattern=args.files_pattern)

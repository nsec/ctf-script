import argparse
import glob
import json
import logging

import coloredlogs
import jsonschema
import yaml

LOG = logging.getLogger()

if __name__ == "__main__":
    LOG.addHandler(hdlr=logging.StreamHandler())
    LOG.setLevel(level=logging.DEBUG)
    coloredlogs.install(level="DEBUG", logger=LOG)


def validate_with_json_schemas(schema: str, files_pattern: str) -> None:
    LOG.info(msg="Starting JSON Schema validator")
    LOG.info(msg=f"Schema: {schema}")

    schema = json.load(open(file=schema, mode="r", encoding="utf-8"))

    if not isinstance(schema, dict):
        LOG.error(msg=f"Loaded schema was not a dictionary: {schema}")
        exit(code=1)

    errors = []
    for file in glob.glob(pathname=files_pattern):
        LOG.info(msg=f"Validating {file}")
        yaml_document = yaml.safe_load(
            stream=open(file=file, mode="r", encoding="utf-8")
        )
        try:
            jsonschema.validate(instance=yaml_document, schema=schema)
        except jsonschema.ValidationError as e:
            errors.append((file, e))

    if errors:
        LOG.error(
            msg=f"================= {len(errors)} in JSON Schema validation ================="
        )
        for filename, error in errors:
            LOG.error(msg=f"File: {filename}")
            LOG.error(msg=f"Error: {error.message}")
        exit(code=1)
    else:
        LOG.info(msg="No error found!")


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

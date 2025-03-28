import argparse
import logging
import glob
import json
import yaml
import jsonschema
import coloredlogs

LOG = logging.getLogger()
if __name__ == "__main__":
    LOG.addHandler(logging.StreamHandler())
    LOG.setLevel(logging.DEBUG)
    coloredlogs.install(level="DEBUG", logger=LOG)


def validate_with_json_schemas(schema: str, files_pattern: str):
    LOG.info("Starting JSON Schema validator")
    LOG.info(f"Schema: {schema}")

    schema = json.load(open(schema, "r", encoding="utf-8"))

    errors = []
    for file in glob.glob(files_pattern):
        LOG.info(f"Validating {file}")
        yaml_document = yaml.safe_load(open(file, "r", encoding="utf-8"))
        try:
            jsonschema.validate(yaml_document, schema)
        except jsonschema.ValidationError as e:
            errors.append((file, e))

    if errors:
        LOG.error(
            f"================= {len(errors)} in JSON Schema validation ================="
        )
        for filename, error in errors:
            LOG.error(f"File: {filename}")
            LOG.error(f"Error: {error.message}")
        exit(1)
    else:
        LOG.info("No error found!")


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

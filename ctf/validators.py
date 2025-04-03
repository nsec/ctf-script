import abc
import glob
import os
import re
from dataclasses import dataclass

from ctf.utils import find_ctf_root_directory, parse_post_yamls, parse_track_yaml

ROOT_DIRECTORY = find_ctf_root_directory()


@dataclass
class ValidationError:
    error_name: str
    error_description: str
    track_name: str = ""
    file_location: str = ""
    details: dict | None = None


class Validator(abc.ABC):
    @abc.abstractmethod
    def validate(self, track_name: str) -> list[ValidationError]:
        pass

    def finalize(self) -> list[ValidationError]:
        return []


class FilesValidator(Validator):
    """Validate that each file name is unique."""

    def __init__(self):
        self.files_mapping = {}

    def validate(self, track_name: str) -> list[ValidationError]:
        if os.path.exists(
            path=(
                path := os.path.join(ROOT_DIRECTORY, "challenges", track_name, "files")
            )
        ):
            for file in os.listdir(path=path):
                if file not in self.files_mapping:
                    self.files_mapping[file.lower().strip()] = []
                self.files_mapping[file.lower().strip()].append(
                    {"name": track_name, "file_location": os.path.join(path, file)}
                )

        return []

    def finalize(self) -> list[ValidationError]:
        errors = []
        for file, tracks in self.files_mapping.items():
            if len(tracks) > 1:
                errors.append(
                    ValidationError(
                        error_name="File collision",
                        error_description="Two files from two different track share the same name, creating a collision. One of them must be changed.",
                        track_name=" + ".join([track["name"] for track in tracks]),
                        file_location=" ".join(
                            [track["file_location"] for track in tracks]
                        ),
                        details={"file_name": file},
                    )
                )
        return errors


class FlagsValidator(Validator):
    """Validate that each flag is unique."""

    def __init__(self):
        self.flags_mapping = {}

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)
        for flag in track_yaml["flags"]:
            flag_string = flag["flag"].lower().strip()
            if flag_string not in self.flags_mapping:
                self.flags_mapping[flag_string] = []
            self.flags_mapping[flag_string].append(
                {"name": track_name, "file_location": track_yaml["file_location"]}
            )

        return []

    def finalize(self) -> list[ValidationError]:
        errors = []
        for flag, tracks in self.flags_mapping.items():
            if len(tracks) > 1:
                errors.append(
                    ValidationError(
                        error_name="Flag collision",
                        error_description="Two flags from two different tracks share the same name, creating a collision. One of them must be changed.",
                        track_name=" + ".join([track["name"] for track in tracks]),
                        file_location=" ".join(
                            [track["file_location"] for track in tracks]
                        ),
                        details={"flag": flag},
                    )
                )
        return errors


class DiscoursePostsAskGodTagValidator(Validator):
    """Validate that the triggers used in discourse posts are correctly defined in the discourse tag of each flag in track.yaml. Also validate that each discourse tag is unique."""

    def __init__(self):
        self.discourse_tags_mapping = {}
        self.file_location = ""

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)
        self.file_location = track_yaml["file_location"]
        discourse_triggers = []
        for flag in track_yaml["flags"]:
            discourse_trigger = flag.get("tags", {}).get("discourse")
            if discourse_trigger:
                discourse_triggers.append(discourse_trigger)
                if discourse_trigger not in self.discourse_tags_mapping:
                    self.discourse_tags_mapping[discourse_trigger] = []
                self.discourse_tags_mapping[discourse_trigger].append(track_name)

        errors = []
        discourse_posts = parse_post_yamls(track_name=track_name)
        for discourse_post in discourse_posts:
            if discourse_post.get("trigger", {}).get("type", "") == "flag":
                if discourse_post["trigger"]["tag"] not in discourse_triggers:
                    errors.append(
                        ValidationError(
                            error_name="Invalid trigger in discourse post",
                            error_description="A discourse post has a flag trigger that references a discourse tag not defined.",
                            track_name=track_name,
                            file_location=discourse_post["file_location"],
                            details={
                                "invalid_tag": discourse_post["trigger"]["tag"],
                                "discourse_tags_in_track.yaml": discourse_triggers,
                            },
                        )
                    )

        return errors

    def finalize(self) -> list[ValidationError]:
        errors = []
        for discourse_tag, tracks in self.discourse_tags_mapping.items():
            if len(tracks) > 1:
                errors.append(
                    ValidationError(
                        error_name="Discourse tag collision",
                        error_description="Two discourse tags from two different tracks share the same name, creating a collision. One of them must be changed.",
                        track_name=" + ".join(tracks),
                        file_location=self.file_location,
                        details={"discourse_tag": discourse_tag},
                    )
                )
        return errors


class PlaceholderValuesValidator(Validator):
    """Validate that the CHANGE_ME values were in fact, changed"""

    def __init__(self):
        pass

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)

        placeholder_regex = re.compile(r"(CHANGE[_-]?ME)", flags=re.IGNORECASE)

        commented_placeholder_regex = re.compile(
            r"#[^#]*(CHANGE[_-]?ME)", flags=re.IGNORECASE
        )

        integrated_with_scenario = track_yaml["integrated_with_scenario"]

        # Checking placeholders in track.yaml
        errors = []
        if s := placeholder_regex.search(track_yaml["description"]):  # Description
            errors.append(
                ValidationError(
                    error_name="Placeholder value found",
                    error_description=f"'{s.group(0)}' is found in the description, indicating that this value was not changed.",
                    track_name=track_name,
                    file_location=track_yaml["file_location"],
                    details={"description": track_yaml["description"]},
                )
            )

        for contact_type in ["dev", "qa", "support"]:
            for contact in track_yaml["contacts"][contact_type]:  # Contacts
                if s := placeholder_regex.search(contact):
                    errors.append(
                        ValidationError(
                            error_name="Placeholder value found",
                            error_description=f"'{s.group(0)}' is found in the contacts.{contact_type}, indicating that this value was not changed.",
                            track_name=track_name,
                            file_location=track_yaml["file_location"],
                            details={"value": contact},
                        )
                    )

        for flag in track_yaml["flags"]:  # Flags
            if s := placeholder_regex.search(flag["flag"]):
                errors.append(
                    ValidationError(
                        error_name="Placeholder value found",
                        error_description=f"'{s.group(0)}' is found in the flags.flag, indicating that this value was not changed.",
                        track_name=track_name,
                        file_location=track_yaml["file_location"],
                        details={"value": flag},
                    )
                )
            if "description" in flag and (
                s := placeholder_regex.search(flag["description"])  # Flag description
            ):
                errors.append(
                    ValidationError(
                        error_name="Placeholder value found",
                        error_description=f"'{s.group(0)}' is found in the flags.description, indicating that this value was not changed.",
                        track_name=track_name,
                        file_location=track_yaml["file_location"],
                        details={"value": flag},
                    )
                )
            if s := placeholder_regex.search(
                flag["return_string"]  # Flag return string
            ):
                errors.append(
                    ValidationError(
                        error_name="Placeholder value found",
                        error_description=f"'{s.group(0)}' is found in the flags.return_string, indicating that this value was not changed.",
                        track_name=track_name,
                        file_location=track_yaml["file_location"],
                        details={"value": flag},
                    )
                )

        # Checking placeholders in terraform/main.tf
        if os.path.exists(
            path=(
                path := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "terraform", "main.tf"
                )
            )
        ):
            with open(file=path, mode="r") as f:
                for line in f.read().split("\n"):
                    if (
                        s := placeholder_regex.search(line)
                    ) and not commented_placeholder_regex.search(line):
                        errors.append(
                            ValidationError(
                                error_name="Placeholder value found",
                                error_description=f"'{s.group(0)}' is found in terraform, indicating that this value was not changed.",
                                track_name=track_name,
                                file_location=path,
                                details={"value_to_search": s.group(0)},
                            )
                        )

        # Checking placeholders in ansible/inventory
        if os.path.exists(
            path=(
                path := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "ansible", "inventory"
                )
            )
        ):
            with open(file=path, mode="r") as f:
                for line in f.read().split("\n"):
                    if (
                        s := placeholder_regex.search(line)
                    ) and not commented_placeholder_regex.search(line):
                        errors.append(
                            ValidationError(
                                error_name="Placeholder value found",
                                error_description=f"'{s.group(0)}' is found in inventory, indicating that this value was not changed.",
                                track_name=track_name,
                                file_location=path,
                                details={"value_to_search": s.group(0)},
                            )
                        )

        # Checking placeholders in ansible/*.yaml
        if os.path.exists(
            path=(
                path := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "ansible"
                )
            )
        ):
            for file in glob.glob(pathname=os.path.join(path, "*.yaml")):
                with open(file=file, mode="r") as f:
                    for line in f.read().split("\n"):
                        if (
                            s := placeholder_regex.search(line)
                        ) and not commented_placeholder_regex.search(line):
                            errors.append(
                                ValidationError(
                                    error_name="Placeholder value found",
                                    error_description=f"'{s.group(0)}' is found in ansible YAMLs, indicating that this value was not changed.",
                                    track_name=track_name,
                                    file_location=file,
                                    details={"value_to_search": s.group(0)},
                                )
                            )

        # Checking placeholders in posts/*.yaml
        if integrated_with_scenario and os.path.exists(
            path=(
                path := os.path.join(ROOT_DIRECTORY, "challenges", track_name, "posts")
            )
        ):
            for file in glob.glob(pathname=os.path.join(path, "*.yaml")):
                with open(file=file, mode="r") as f:
                    for line in f.read().split("\n"):
                        if (
                            s := placeholder_regex.search(line)
                        ) and not commented_placeholder_regex.search(line):
                            errors.append(
                                ValidationError(
                                    error_name="Placeholder value found",
                                    error_description=f"'{s.group(0)}' is found in posts YAMLs, indicating that this value was not changed.",
                                    track_name=track_name,
                                    file_location=file,
                                    details={"value_to_search": s.group(0)},
                                )
                            )

        return errors


validators_list = [
    FilesValidator,
    FlagsValidator,
    DiscoursePostsAskGodTagValidator,
    PlaceholderValuesValidator,
]

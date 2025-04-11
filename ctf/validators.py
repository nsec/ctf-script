import abc
import os
import re
import glob
from dataclasses import dataclass

from ctf.utils import (
    find_ctf_root_directory,
    parse_post_yamls,
    parse_track_yaml,
    remove_ctf_script_root_directory_from_path,
)

ROOT_DIRECTORY = find_ctf_root_directory()


@dataclass
class ValidationError:
    error_name: str
    error_description: str
    details: dict[str, str]
    track_name: str = ""


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
                self.files_mapping[file.lower().strip()].append(track_name)

        return []

    def finalize(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        for file, tracks in self.files_mapping.items():
            if len(tracks) > 1:
                errors.append(
                    ValidationError(
                        error_name="File collision",
                        error_description="Two files from two different track share the same name, creating a collision. One of them must be changed.",
                        track_name=" + ".join(tracks),
                        details={"File name": file},
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
            self.flags_mapping[flag_string].append(track_name)

        return []

    def finalize(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        for flag, tracks in self.flags_mapping.items():
            if len(tracks) > 1:
                errors.append(
                    ValidationError(
                        error_name="Flag collision",
                        error_description="Two flags from two different tracks share the same name, creating a collision. One of them must be changed.",
                        track_name=" + ".join(tracks),
                        details={"Flag": flag},
                    )
                )
        return errors


class DiscoursePostsAskGodTagValidator(Validator):
    """Validate that the triggers used in discourse posts are correctly defined in the discourse tag of each flag in track.yaml. Also validate that each discourse tag is unique."""

    def __init__(self):
        self.discourse_tags_mapping = {}

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)
        discourse_triggers = []
        for flag in track_yaml["flags"]:
            discourse_trigger = flag.get("tags", {}).get("discourse")
            if discourse_trigger:
                discourse_triggers.append(discourse_trigger)
                if discourse_trigger not in self.discourse_tags_mapping:
                    self.discourse_tags_mapping[discourse_trigger] = []
                self.discourse_tags_mapping[discourse_trigger].append(track_yaml)

        errors: list[ValidationError] = []
        discourse_posts = parse_post_yamls(track_name=track_name)
        for discourse_post in discourse_posts:
            if discourse_post.get("trigger", {}).get("type", "") == "flag":
                if discourse_post["trigger"]["tag"] not in discourse_triggers:
                    errors.append(
                        ValidationError(
                            error_name="Invalid trigger in discourse post",
                            error_description="A discourse post has a flag trigger that references a discourse tag not defined in track.yaml.",
                            track_name=track_name,
                            details={
                                "Invalid tag": discourse_post["trigger"]["tag"],
                                "Discourse tags in track.yaml": str(discourse_triggers),
                            },
                        )
                    )

        return errors

    def finalize(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        for discourse_tag, tracks in self.discourse_tags_mapping.items():
            if len(tracks) > 1:
                errors.append(
                    ValidationError(
                        error_name="Discourse tag collision",
                        error_description="Two discourse tags from two different tracks share the same name, creating a collision. One of them must be changed.",
                        track_name=" + ".join(tracks),
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
        placeholder_regex = re.compile(r"(CHANGE[_\-]?ME)", flags=re.IGNORECASE)
        commented_placeholder_regex = re.compile(
            r"#[^#]*(CHANGE[_-]?ME)", flags=re.IGNORECASE
        )
        integrated_with_scenario = track_yaml["integrated_with_scenario"]
        errors: list[ValidationError] = []
        files = []

        # Checking placeholders in terraform/main.tf
        if os.path.exists(
            path=(
                path := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "terraform", "main.tf"
                )
            )
        ):
            files += [path]

        # Checking placeholders in track.yml
        if os.path.exists(
            path=(
                path := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "track.yaml"
                )
            )
        ):
            files += [path]

        # Checking placeholders in ansible/inventory
        if os.path.exists(
            path=(
                path := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "ansible", "inventory"
                )
            )
        ):
            files += [path]
        # Checking placeholders in posts/*.yaml
        if integrated_with_scenario and os.path.exists(
            path=(
                path := os.path.join(ROOT_DIRECTORY, "challenges", track_name, "posts")
            )
        ):
            files += list(glob.glob(pathname=os.path.join(path, "*.yaml")))
        # Checking placeholders in ansible/*.yaml
        if os.path.exists(
            path=(
                path := os.path.join(
                    ROOT_DIRECTORY, "challenges", track_name, "ansible"
                )
            )
        ):
            files += list(glob.glob(pathname=os.path.join(path, "*.yaml")))

        for file in files:
            with open(file=file, mode="r") as f:
                for line in f.read().split("\n"):
                    if (
                        s := placeholder_regex.findall(line)
                    ) and not commented_placeholder_regex.findall(line):
                        errors.append(
                            ValidationError(
                                track_name=track_name,
                                error_name="Placeholder value found",
                                error_description="A placeholder value was found in a challenge file. This indicates that a value was not changed.",
                                details={
                                    "File location": remove_ctf_script_root_directory_from_path(
                                        path=file
                                    ),
                                    "Value found": "\n".join(s),
                                },
                            )
                        )

        return errors


validators_list = [
    FilesValidator,
    FlagsValidator,
    DiscoursePostsAskGodTagValidator,
    PlaceholderValuesValidator,
]

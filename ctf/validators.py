import abc
import glob
import os
import re

from ctf.models import ValidationError
from ctf.utils import (
    find_ctf_root_directory,
    get_all_file_paths_recursively,
    parse_post_yamls,
    parse_track_yaml,
    remove_ctf_script_root_directory_from_path,
)


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
                path := os.path.join(
                    find_ctf_root_directory(), "challenges", track_name, "files"
                )
            )
        ):
            for file in get_all_file_paths_recursively(path=path):
                # Lower the file name to avoid human error
                file = os.path.relpath(path=file, start=path).lower()

                if file not in self.files_mapping:
                    self.files_mapping[file] = []
                self.files_mapping[file].append(track_name)

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


class FireworksAskGodTagValidator(Validator):
    """Validate that ui_sound and ui_gif tags of each flag in track.yaml also as a file associated."""

    def __init__(self):
        self.sound_tags_mapping = {}
        self.gif_tags_mapping = {}

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)

        for flag in track_yaml["flags"]:
            sound_trigger = flag.get("tags", {}).get("ui_sound")
            gif_trigger = flag.get("tags", {}).get("ui_gif")

            if sound_trigger:
                if sound_trigger not in self.sound_tags_mapping:
                    self.sound_tags_mapping[sound_trigger] = []

                self.sound_tags_mapping[sound_trigger].append(track_name)

            if gif_trigger:
                if gif_trigger not in self.gif_tags_mapping:
                    self.gif_tags_mapping[gif_trigger] = []

                self.gif_tags_mapping[gif_trigger].append(track_name)

        return []

    def finalize(self) -> list[ValidationError]:
        errors: list[ValidationError] = []

        sound_path = os.path.join(
            find_ctf_root_directory(), "challenges", "*", "files", "askgod", "sounds"
        )
        for sound_tag, track_names in self.sound_tags_mapping.items():
            if len(glob.glob(pathname=os.path.join(sound_path, sound_tag))) == 0:
                errors.append(
                    ValidationError(
                        error_name="Fireworks sound file not found",
                        error_description=f'The "ui_sound" tag should have an associated file in "{remove_ctf_script_root_directory_from_path(path=sound_path)}/" which could not be found.',
                        track_name=" + ".join(
                            [track_name for track_name in track_names]
                        ),
                        details={'"ui_sound" tag': sound_tag},
                    )
                )

        gif_path = os.path.join(
            find_ctf_root_directory(), "challenges", "*", "files", "askgod", "gifs"
        )
        for gif_tag, track_names in self.gif_tags_mapping.items():
            if len(glob.glob(pathname=os.path.join(gif_path, gif_tag))) == 0:
                errors.append(
                    ValidationError(
                        error_name="Fireworks gif file not found",
                        error_description=f'The "ui_gif" tag should have an associated file in "{remove_ctf_script_root_directory_from_path(path=gif_path)}/" which could not be found.',
                        track_name=" + ".join(
                            [track_name for track_name in track_names]
                        ),
                        details={'"ui_gif" tag': gif_tag},
                    )
                )
        return errors


class DiscoursePostsAskGodTagValidator(Validator):
    """
    Validate that the triggers used in discourse posts are correctly defined in the discourse tag of each flag in track.yaml. It checks for triggers in ALL tracks to allow a flow like: "When a flag from track A is triggered, show a post in track B".
    Also validate that each discourse tag is unique.
    Also validates that the topic matches an existing file name in the posts directory.
    """

    def __init__(self):
        self.discourse_tags_mapping = {}
        self.discourse_triggers = []
        self.discourse_posts = []

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)
        for flag in track_yaml["flags"]:
            discourse_trigger = flag.get("tags", {}).get("discourse")
            if discourse_trigger:
                self.discourse_triggers.append(discourse_trigger)
                if discourse_trigger not in self.discourse_tags_mapping:
                    self.discourse_tags_mapping[discourse_trigger] = []
                self.discourse_tags_mapping[discourse_trigger].append(track_yaml)

        errors: list[ValidationError] = []
        discourse_posts = parse_post_yamls(track_name=track_name)
        for discourse_post in discourse_posts:
            if discourse_post.get("trigger", {}).get("type", "") == "flag":
                self.discourse_posts.append((track_name, discourse_post))
                if not os.path.exists(
                    os.path.join(
                        find_ctf_root_directory(),
                        "challenges",
                        track_name,
                        "posts",
                        discourse_post["topic"] + ".yaml",
                    )
                ):
                    errors.append(
                        ValidationError(
                            error_name="Discourse post topic not found",
                            error_description="The topic of the discourse post does not match any file in the posts directory.",
                            track_name=track_name,
                            details={
                                "Topic": discourse_post["topic"],
                                "Posts directory": os.path.join(
                                    find_ctf_root_directory(),
                                    "challenges",
                                    track_name,
                                    "posts",
                                ),
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
                        track_name=" + ".join(map(lambda track: track["name"], tracks)),
                        details={'"discourse" tag': discourse_tag},
                    )
                )

        for track_name, discourse_post in self.discourse_posts:
            if discourse_post["trigger"]["tag"] not in self.discourse_triggers:
                errors.append(
                    ValidationError(
                        error_name="Invalid trigger in discourse post",
                        error_description="A discourse post has a flag trigger that references a discourse tag not defined in track.yaml.",
                        track_name=track_name,
                        details={
                            "Invalid tag": discourse_post["trigger"]["tag"],
                        },
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
                    find_ctf_root_directory(),
                    "challenges",
                    track_name,
                    "terraform",
                    "main.tf",
                )
            )
        ):
            files += [path]

        # Checking placeholders in track.yml
        if os.path.exists(
            path=(
                path := os.path.join(
                    find_ctf_root_directory(), "challenges", track_name, "track.yaml"
                )
            )
        ):
            files += [path]

        # Checking placeholders in ansible/inventory
        if os.path.exists(
            path=(
                path := os.path.join(
                    find_ctf_root_directory(),
                    "challenges",
                    track_name,
                    "ansible",
                    "inventory",
                )
            )
        ):
            files += [path]
        # Checking placeholders in posts/*.yaml
        if integrated_with_scenario and os.path.exists(
            path=(
                path := os.path.join(
                    find_ctf_root_directory(), "challenges", track_name, "posts"
                )
            )
        ):
            files += list(glob.glob(pathname=os.path.join(path, "*.yaml")))
        # Checking placeholders in ansible/*.yaml
        if os.path.exists(
            path=(
                path := os.path.join(
                    find_ctf_root_directory(), "challenges", track_name, "ansible"
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


class DiscourseFileNamesValidator(Validator):
    """Validate that the discourse posts have unique file names."""

    def __init__(self):
        self.discourse_posts_mapping = {}

    def validate(self, track_name: str) -> list[ValidationError]:
        files = []

        # Checking placeholders in posts/*.yaml
        if os.path.exists(
            path=(
                path := os.path.join(
                    find_ctf_root_directory(), "challenges", track_name, "posts"
                )
            )
        ):
            files += list(glob.glob(pathname=os.path.join(path, "*.yaml")))

        for file in files:
            file_name = os.path.basename(file)
            if file_name not in self.discourse_posts_mapping:
                self.discourse_posts_mapping[file_name] = []
            self.discourse_posts_mapping[file_name].append(track_name)

        return []

    def finalize(self) -> list[ValidationError]:
        errors: list[ValidationError] = []
        for file_name, tracks in self.discourse_posts_mapping.items():
            if len(tracks) > 1:
                errors.append(
                    ValidationError(
                        error_name="Discourse post file name collision",
                        error_description="Two discourse posts from two different tracks share the same name, creating a collision. One of them must be changed.",
                        track_name="\n".join(tracks),
                        details={"File name": file_name},
                    )
                )
        return errors


class ServicesValidator(Validator):
    """Validate that each service in a given track has a unique name within its instance and that it only contains letters, numbers and dashes."""

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)
        errors: list[ValidationError] = []
        services = set()
        for service in track_yaml["services"]:
            service_name = service.get("name")
            instance_name = service.get("instance")
            service = f"{instance_name}/{service_name}"

            if service in services:
                errors.append(
                    ValidationError(
                        error_name="Service name collision",
                        error_description="Two services from the same track and instance share the same name, creating a collision. One of them must be changed.",
                        track_name=track_name,
                        details={"Service name": service_name},
                    )
                )
            else:
                services.add(service)

            # Validate that the service name only contains lowercase letters, numbers and dashes
            if not re.match(r"^[a-zA-Z0-9\-]+$", service_name):
                errors.append(
                    ValidationError(
                        error_name="Invalid service name",
                        error_description="The service name must only contain letters, numbers and dashes.",
                        track_name=track_name,
                        details={"Service name": service_name},
                    )
                )

        return errors


class OrphanServicesValidator(Validator):
    """Validate that if there is a service in the track.yaml, there is a terraform directory."""

    def validate(self, track_name: str) -> list[ValidationError]:
        track_yaml = parse_track_yaml(track_name=track_name)
        errors: list[ValidationError] = []
        if track_yaml.get("services"):
            if not os.path.exists(
                path=os.path.join(
                    find_ctf_root_directory(),
                    "challenges",
                    track_name,
                    "terraform",
                )
            ):
                errors.append(
                    ValidationError(
                        error_name="Orphan service",
                        error_description="A service is defined in track.yaml, but a terraform directory was not found. This indicates that the service might not be needed.",
                        track_name=track_name,
                        details={
                            "Service Name": "\n".join(
                                [
                                    service.get("name")
                                    for service in track_yaml["services"]
                                ]
                            ),
                        },
                    )
                )

        return errors


validators_list = [
    FilesValidator,
    FlagsValidator,
    FireworksAskGodTagValidator,
    DiscoursePostsAskGodTagValidator,
    PlaceholderValuesValidator,
    DiscourseFileNamesValidator,
    ServicesValidator,
    OrphanServicesValidator,
]

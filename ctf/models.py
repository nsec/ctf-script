from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    StringConstraints,
)

IncusStr = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9\-]{0,61}[a-z0-9]$")]


class ListOutputFormat(StrEnum):
    PRETTY = "pretty"


class OutputFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
    YAML = "yaml"


class Template(StrEnum):
    APACHE_PHP = "apache-php"
    PYTHON_SERVICE = "python-service"
    FILES_ONLY = "files-only"
    TRACK_YAML_ONLY = "track-yaml-only"
    RUST_WEBSERVICE = "rust-webservice"


class Track(BaseModel, frozen=True):
    name: IncusStr
    remote: str = "local"
    production: bool = False
    require_build_container: bool = False

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name="{self.name}", remote="{self.remote}", production={self.production}, require_build_container={self.require_build_container})'


class ValidationError(BaseModel, frozen=True):
    error_name: str
    error_description: str
    details: dict[str, str]
    track_name: str = ""

    def __str__(self) -> str:
        return self.error_name

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(error_name="{self.error_name}", error_description="{self.error_description}", track_name="{self.track_name}", details= {self.details})'

from __future__ import annotations

from typing import Annotated, Any

from pydantic import (
    BaseModel,
    StringConstraints,
)

IncusStr = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9\-]{0,61}[a-z0-9]$")]


class Track(BaseModel):
    # Every object is unique on it's name
    name: IncusStr
    remote: str = "local"
    production: bool = False
    require_build_container: bool = False

    def __eq__(self, other: Any) -> bool:
        match other:
            case str():
                return self.name == other
            case Track():
                return self.name == other.name
            case _:
                return False

    # Use the "name" for hashable so it's possible to do Track(name="t1") in {Track(name="t1", remote="other")}
    def __hash__(self) -> int:
        return self.name.__hash__()

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(name="{self.name}", remote="{self.remote}", production={self.production}, require_build_container={self.require_build_container})'

    def __str__(self) -> str:
        return self.name


class ValidationError(BaseModel, frozen=True):
    error_name: str
    error_description: str
    details: dict[str, str]
    track_name: str = ""

    def __str__(self) -> str:
        return self.error_name

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(error_name="{self.error_name}", error_description="{self.error_description}", track_name="{self.track_name}", details= {self.details})'

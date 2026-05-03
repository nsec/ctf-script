from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
)

IncusStr = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9\-]{0,61}[a-z0-9]$")]
PortNumber = Annotated[int, Field(ge=1, le=65535)]
CheckType = Literal["http", "https", "ssh", "tcp"]


class Track(BaseModel):
    # Every object is unique on it's name
    name: IncusStr
    remote: str = "local"
    production: bool = False
    require_build_container: bool = False
    has_virtual_machine: bool = False
    already_deployed: bool = False

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
        return f'{self.__class__.__name__}(name="{self.name}", remote="{self.remote}", production={self.production}, require_build_container={self.require_build_container}, has_virtual_machine={self.has_virtual_machine})'

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


class TrackContacts(BaseModel):
    dev: list[str]
    qa: list[str]
    support: list[str]


class InstanceConfig(BaseModel):
    model_config = ConfigDict(extra="allow")


class InstanceDeviceProperties(BaseModel):
    model_config = ConfigDict(extra="allow")


class InstanceDevice(BaseModel):
    name: str
    type: str
    properties: InstanceDeviceProperties


class InstanceWaitFor(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str | None = None


class InstanceService(BaseModel):
    name: str
    port: PortNumber
    check: CheckType
    dev_port_mapping: PortNumber | None = None


class TrackInstance(BaseModel):
    is_build_container: bool = False
    image: str
    profiles: list[str]
    type: Literal["container", "virtual-machine"]
    description: str
    hwaddr: str | None = None
    record: str | None = None
    ipv6: str | None = None
    config: InstanceConfig
    devices: list[InstanceDevice]
    wait_for: InstanceWaitFor | None = None
    services: list[InstanceService]


class TrackInstances(RootModel[dict[str, TrackInstance]]): ...


class FlagTags(BaseModel):
    model_config = ConfigDict(extra="allow")
    discourse: str | None = None
    ui_sound: str | None = None
    ui_gif: str | None = None


class TrackFlag(BaseModel):
    flag: str
    value: int
    description: str | None = None
    return_string: str
    cfss: str | None = None
    tags: FlagTags | None = None


class DeprecatedTrackService(BaseModel):
    name: str
    instance: str
    address: str
    port: PortNumber
    check: CheckType
    dev_port_mapping: PortNumber | None = None


class TrackYaml(BaseModel):
    name: str
    description: str
    integrated_with_scenario: bool
    contacts: TrackContacts
    instances: TrackInstances | None = None
    flags: list[TrackFlag]
    services: list[DeprecatedTrackService] | None = None

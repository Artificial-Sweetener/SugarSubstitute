#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Define the durable, versioned crash incident exchanged between processes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Self


CRASH_INCIDENT_SCHEMA_VERSION = 1


class CrashKind(Enum):
    """Classify the mechanism that ended or destabilized a process."""

    PYTHON_UNHANDLED = "python_unhandled"
    THREAD_UNHANDLED = "thread_unhandled"
    UNRAISABLE = "unraisable"
    QT_FATAL = "qt_fatal"
    NATIVE = "native"
    ABORT = "abort"
    ABNORMAL_EXIT = "abnormal_exit"
    STARTUP = "startup"


class CrashBoundary(Enum):
    """Identify the owned execution boundary that observed a failure."""

    PROCESS_MAIN = "process_main"
    PYTHON_THREAD = "python_thread"
    QT_EVENT = "qt_event"
    QT_MESSAGE = "qt_message"
    EXECUTION_JOB = "execution_job"
    NATIVE_HANDLER = "native_handler"
    SUPERVISOR = "supervisor"
    LAUNCHER_BOOTSTRAP = "launcher_bootstrap"


class CrashAttribution(Enum):
    """State whether evidence proves a crash or only an unclean termination."""

    CONFIRMED = "confirmed"
    UNCLEAN_TERMINATION = "unclean_termination"


@dataclass(frozen=True, slots=True)
class CrashIncident:
    """Describe one durable crash report without presentation dependencies."""

    incident_id: str
    run_id: str
    occurred_at_utc: str
    kind: CrashKind
    boundary: CrashBoundary
    attribution: CrashAttribution
    summary: str
    process_id: int
    exception_type: str | None = None
    exception_message: str | None = None
    traceback: tuple[str, ...] = ()
    all_thread_traceback: tuple[str, ...] = ()
    exit_code: int | None = None
    thread_name: str | None = None
    application_version: str | None = None
    platform: str | None = None
    python_version: str | None = None
    launch_arguments: tuple[str, ...] = ()
    breadcrumbs: tuple[str, ...] = ()
    attachments: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject identifiers and attachments that cannot be stored safely."""

        _require_identifier(self.incident_id, name="incident_id")
        _require_identifier(self.run_id, name="run_id")
        if self.process_id < 0:
            raise ValueError("Crash incident process_id cannot be negative.")
        for attachment in self.attachments:
            if not attachment or attachment in {".", ".."}:
                raise ValueError("Crash attachment names must be non-empty filenames.")
            if "/" in attachment or "\\" in attachment:
                raise ValueError(
                    "Crash attachments must stay inside the incident directory."
                )

    def to_json(self) -> dict[str, object]:
        """Return the complete stable JSON representation of this incident."""

        return {
            "schema_version": CRASH_INCIDENT_SCHEMA_VERSION,
            "incident_id": self.incident_id,
            "run_id": self.run_id,
            "occurred_at_utc": self.occurred_at_utc,
            "kind": self.kind.value,
            "boundary": self.boundary.value,
            "attribution": self.attribution.value,
            "summary": self.summary,
            "process_id": self.process_id,
            "exception_type": self.exception_type,
            "exception_message": self.exception_message,
            "traceback": list(self.traceback),
            "all_thread_traceback": list(self.all_thread_traceback),
            "exit_code": self.exit_code,
            "thread_name": self.thread_name,
            "application_version": self.application_version,
            "platform": self.platform,
            "python_version": self.python_version,
            "launch_arguments": list(self.launch_arguments),
            "breadcrumbs": list(self.breadcrumbs),
            "attachments": list(self.attachments),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_json(cls, payload: object) -> Self:
        """Parse one incident and reject corrupt or incompatible payloads."""

        if not isinstance(payload, Mapping):
            raise ValueError("Crash incident must be a JSON object.")
        if payload.get("schema_version") != CRASH_INCIDENT_SCHEMA_VERSION:
            raise ValueError("Crash incident schema version is unsupported.")
        try:
            return cls(
                incident_id=_required_string(payload, "incident_id"),
                run_id=_required_string(payload, "run_id"),
                occurred_at_utc=_required_string(payload, "occurred_at_utc"),
                kind=CrashKind(_required_string(payload, "kind")),
                boundary=CrashBoundary(_required_string(payload, "boundary")),
                attribution=CrashAttribution(_required_string(payload, "attribution")),
                summary=_required_string(payload, "summary"),
                process_id=_required_int(payload, "process_id"),
                exception_type=_optional_string(payload, "exception_type"),
                exception_message=_optional_string(payload, "exception_message"),
                traceback=_string_tuple(payload, "traceback"),
                all_thread_traceback=_string_tuple(payload, "all_thread_traceback"),
                exit_code=_optional_int(payload, "exit_code"),
                thread_name=_optional_string(payload, "thread_name"),
                application_version=_optional_string(payload, "application_version"),
                platform=_optional_string(payload, "platform"),
                python_version=_optional_string(payload, "python_version"),
                launch_arguments=_string_tuple(payload, "launch_arguments"),
                breadcrumbs=_string_tuple(payload, "breadcrumbs"),
                attachments=_string_tuple(payload, "attachments"),
                metadata=_string_mapping(payload, "metadata"),
            )
        except (TypeError, ValueError) as error:
            raise ValueError("Crash incident payload is invalid.") from error


def _require_identifier(value: str, *, name: str) -> None:
    """Require one opaque identifier that is safe as a directory name."""

    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"Crash incident {name} is not a safe identifier.")


def _required_string(payload: Mapping[object, object], key: str) -> str:
    """Return one required non-empty string field."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Crash incident field {key!r} must be a non-empty string.")
    return value


def _optional_string(payload: Mapping[object, object], key: str) -> str | None:
    """Return one optional string field."""

    value = payload.get(key)
    if value is None or isinstance(value, str):
        return value
    raise ValueError(f"Crash incident field {key!r} must be a string or null.")


def _required_int(payload: Mapping[object, object], key: str) -> int:
    """Return one required integer field without accepting booleans."""

    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Crash incident field {key!r} must be an integer.")
    return value


def _optional_int(payload: Mapping[object, object], key: str) -> int | None:
    """Return one optional integer field without accepting booleans."""

    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Crash incident field {key!r} must be an integer or null.")
    return value


def _string_tuple(payload: Mapping[object, object], key: str) -> tuple[str, ...]:
    """Return one required list of strings."""

    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"Crash incident field {key!r} must be a string list.")
    return tuple(value)


def _string_mapping(payload: Mapping[object, object], key: str) -> Mapping[str, str]:
    """Return one required string-to-string mapping."""

    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"Crash incident field {key!r} must be an object.")
    if any(
        not isinstance(item_key, str) or not isinstance(item, str)
        for item_key, item in value.items()
    ):
        raise ValueError(f"Crash incident field {key!r} must contain only strings.")
    return dict(value)


__all__ = [
    "CRASH_INCIDENT_SCHEMA_VERSION",
    "CrashAttribution",
    "CrashBoundary",
    "CrashIncident",
    "CrashKind",
]

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

"""Define persisted metadata for one Substitute-owned managed ComfyUI process."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

ContainmentMode = Literal[
    "windows_job_object",
    "posix_guardian",
    "legacy_uncontained",
]
_CURRENT_CONTAINMENT_VERSION = 2


@dataclass(frozen=True)
class ManagedProcessMetadata:
    """Capture the authoritative persisted state for one owned managed process."""

    pid: int
    host: str
    port: int
    workspace_path: Path
    parent_pid: int | None = None
    process_started_at: str | None = None
    selected_install_target: str | None = None
    selected_backend_policy: str | None = None
    last_validated_at: str | None = None
    last_launched_at: str | None = None
    containment_mode: ContainmentMode = "legacy_uncontained"
    owner_pid: int | None = None
    process_group_id: int | None = None
    job_name: str | None = None
    guardian_pipe_token: str | None = None
    containment_version: int = _CURRENT_CONTAINMENT_VERSION

    def matches_endpoint(self, *, host: str, port: int, workspace: Path) -> bool:
        """Return whether this metadata still describes the supplied managed target."""

        return (
            self.host == host
            and self.port == port
            and self.workspace_path.resolve() == workspace.resolve()
        )

    def to_payload(self) -> dict[str, Any]:
        """Serialize this metadata for filesystem persistence."""

        return {
            "pid": self.pid,
            "host": self.host,
            "port": self.port,
            "workspace_path": str(self.workspace_path),
            "parent_pid": self.parent_pid,
            "process_started_at": self.process_started_at,
            "selected_install_target": self.selected_install_target,
            "selected_backend_policy": self.selected_backend_policy,
            "last_validated_at": self.last_validated_at,
            "last_launched_at": self.last_launched_at,
            "containment_mode": self.containment_mode,
            "owner_pid": self.owner_pid,
            "process_group_id": self.process_group_id,
            "job_name": self.job_name,
            "guardian_pipe_token": self.guardian_pipe_token,
            "containment_version": self.containment_version,
        }

    def with_validation_timestamp(self, timestamp: str) -> "ManagedProcessMetadata":
        """Return one metadata record with an updated validation timestamp."""

        return replace(self, last_validated_at=timestamp)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ManagedProcessMetadata":
        """Deserialize persisted metadata into the typed runtime model."""

        return cls(
            pid=int(payload["pid"]),
            host=str(payload["host"]),
            port=int(payload["port"]),
            workspace_path=Path(str(payload["workspace_path"])),
            parent_pid=(
                int(payload["parent_pid"])
                if payload.get("parent_pid") is not None
                else None
            ),
            process_started_at=_optional_string(payload.get("process_started_at")),
            selected_install_target=_optional_string(
                payload.get("selected_install_target")
            ),
            selected_backend_policy=_optional_string(
                payload.get("selected_backend_policy")
            ),
            last_validated_at=_optional_string(payload.get("last_validated_at")),
            last_launched_at=_optional_string(payload.get("last_launched_at")),
            containment_mode=_optional_containment_mode(
                payload.get("containment_mode")
            ),
            owner_pid=(
                int(payload["owner_pid"])
                if payload.get("owner_pid") is not None
                else None
            ),
            process_group_id=(
                int(payload["process_group_id"])
                if payload.get("process_group_id") is not None
                else None
            ),
            job_name=_optional_string(payload.get("job_name")),
            guardian_pipe_token=_optional_string(payload.get("guardian_pipe_token")),
            containment_version=int(
                payload.get("containment_version", _CURRENT_CONTAINMENT_VERSION)
            ),
        )


def _optional_string(value: object) -> str | None:
    """Normalize optional persisted string values."""

    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_containment_mode(value: object) -> ContainmentMode:
    """Normalize persisted containment mode values with legacy compatibility."""

    normalized = _optional_string(value)
    if normalized == "windows_job_object":
        return "windows_job_object"
    if normalized == "linux_guardian":
        return "posix_guardian"
    if normalized == "posix_guardian":
        return "posix_guardian"
    if normalized == "legacy_uncontained":
        return "legacy_uncontained"
    return "legacy_uncontained"


__all__ = ["ContainmentMode", "ManagedProcessMetadata"]

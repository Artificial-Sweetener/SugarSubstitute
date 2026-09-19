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

"""Own persisted staged-update intent and its exact outgoing process identity."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
from typing import TYPE_CHECKING, Self

from sugarsubstitute_shared.launcher_update.persistence import (
    read_json_object,
    write_json_atomic,
)

if TYPE_CHECKING:
    from sugarsubstitute_shared.process_identity import ProcessIdentity
from sugarsubstitute_shared.windows_long_paths import operational_path

LAUNCHER_UPDATE_REQUEST_SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class LauncherUpdateRequest:
    """Retain staged update intent independently of helper lifetime.

    Schema one requests remain readable and can be rescheduled. A persisted PID
    alone cannot identify an outgoing process, so it never authorizes a wait.
    """

    install_root: Path
    version: str
    target_key: str
    staged_bundle_dir: Path
    relaunch: bool
    wait_pid: int | None = None
    wait_process_created_at: float | None = None
    schema_version: int = LAUNCHER_UPDATE_REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        """Reject malformed identity pairs before persistence or execution."""
        if type(self.schema_version) is not int or self.schema_version not in {
            1,
            LAUNCHER_UPDATE_REQUEST_SCHEMA_VERSION,
        }:
            raise ValueError("Unsupported launcher update request schema.")
        if self.wait_pid is not None and (
            type(self.wait_pid) is not int or self.wait_pid <= 0
        ):
            raise ValueError("Launcher update wait_pid must be a positive integer.")
        created = self.wait_process_created_at
        if created is not None and (
            type(created) not in {int, float}
            or not math.isfinite(created)
            or created <= 0
        ):
            raise ValueError(
                "Launcher update process creation time must be positive and finite."
            )
        if self.wait_pid is None and created is not None:
            raise ValueError("Launcher update process identity is incomplete.")
        if self.schema_version == 2 and self.wait_pid is not None and created is None:
            raise ValueError("Launcher update process identity is incomplete.")

    @property
    def wait_identity(self) -> ProcessIdentity | None:
        """Return the exact outgoing process or require legacy intent to be renewed."""
        if self.wait_pid is None:
            return None
        if self.wait_process_created_at is None:
            raise ValueError(
                "Legacy launcher update handoff must be rescheduled with an exact process identity."
            )
        from sugarsubstitute_shared.process_identity import ProcessIdentity

        return ProcessIdentity(
            pid=self.wait_pid, created_at=self.wait_process_created_at
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        """Read current or legacy staged intent without guessing process identity."""
        payload = read_json_object(path)
        schema = payload.get("schema_version")
        if type(schema) is not int or schema not in {
            1,
            LAUNCHER_UPDATE_REQUEST_SCHEMA_VERSION,
        }:
            raise ValueError("Unsupported launcher update request schema.")
        relaunch = payload.get("relaunch")
        if not isinstance(relaunch, bool):
            raise ValueError("Launcher update relaunch must be a boolean.")
        fields: dict[str, str] = {}
        for key in ("install_root", "version", "target_key", "staged_bundle_dir"):
            value = payload.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError(f"Required string field is missing: {key}")
            fields[key] = value
        pid = payload.get("wait_pid")
        if pid is not None and (type(pid) is not int or pid <= 0):
            raise ValueError("Launcher update wait_pid must be a positive integer.")
        created = payload.get("wait_process_created_at")
        if created is not None and (
            not isinstance(created, (int, float)) or isinstance(created, bool)
        ):
            raise ValueError("Launcher update process creation time must be numeric.")
        return cls(
            install_root=operational_path(fields["install_root"]),
            version=fields["version"],
            target_key=fields["target_key"],
            staged_bundle_dir=operational_path(fields["staged_bundle_dir"]),
            relaunch=relaunch,
            wait_pid=pid,
            wait_process_created_at=created,
            schema_version=schema,
        )

    def save(self, path: Path) -> None:
        """Persist this staged intent and identity atomically."""
        write_json_atomic(
            path,
            {
                "schema_version": self.schema_version,
                "install_root": str(self.install_root),
                "version": self.version,
                "target_key": self.target_key,
                "staged_bundle_dir": str(self.staged_bundle_dir),
                "relaunch": self.relaunch,
                "wait_pid": self.wait_pid,
                "wait_process_created_at": self.wait_process_created_at,
            },
        )

    def with_process_behavior(
        self, *, relaunch: bool, wait_identity: ProcessIdentity | None
    ) -> Self:
        """Bind a fresh exact handoff and upgrade legacy intent without losing staging."""
        return replace(
            self,
            relaunch=relaunch,
            wait_pid=wait_identity.pid if wait_identity is not None else None,
            wait_process_created_at=wait_identity.created_at
            if wait_identity is not None
            else None,
            schema_version=LAUNCHER_UPDATE_REQUEST_SCHEMA_VERSION,
        )

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

"""Define the process-bound readiness receipt shared by launcher and app."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import secrets
from collections.abc import Mapping
from typing import Final


READINESS_PATH_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_PATH"
READINESS_TOKEN_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_TOKEN"
READINESS_SCHEMA_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_SCHEMA"
READINESS_DELEGATION_PATH_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_DELEGATION_PATH"
READINESS_DELEGATION_TOKEN_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_DELEGATION_TOKEN"
READINESS_DELEGATION_SCHEMA_ENV: Final = "SUGAR_SUBSTITUTE_READINESS_DELEGATION_SCHEMA"
READINESS_SCHEMA_VERSION: Final = 5
READINESS_LEGACY_DELEGATION_SCHEMA_VERSION: Final = 3
_LEGACY_READINESS_SCHEMA_VERSION: Final = 1
_SURFACE_READINESS_SCHEMA_VERSION: Final = 2
_PARENT_READINESS_SCHEMA_VERSION: Final = 3
_MILESTONE_READINESS_SCHEMA_VERSION: Final = 4
REQUIRED_READINESS_MILESTONES: Final = (
    "process_started",
    "surface_painted",
    "event_loop_turn_completed",
)


class ApplicationReadinessSurface(str, Enum):
    """Identify which visible application surface became ready."""

    LEGACY_VISIBLE_SHELL = "legacy_visible_shell"
    LAUNCHER_WINDOW = "launcher_window"
    ONBOARDING = "onboarding"
    MAIN_SHELL = "main_shell"


@dataclass(frozen=True, slots=True)
class ApplicationReadinessReceipt:
    """Identify the process and private launch token that became ready."""

    pid: int
    token: str
    surface: ApplicationReadinessSurface
    parent_pid: int | None
    milestones: tuple[str, ...] = REQUIRED_READINESS_MILESTONES
    attester_pids: tuple[int, ...] = ()

    def to_json(
        self, *, schema_version: int = READINESS_SCHEMA_VERSION
    ) -> dict[str, object]:
        """Return a receipt compatible with the requested supervisor schema."""

        if schema_version not in range(
            _LEGACY_READINESS_SCHEMA_VERSION, READINESS_SCHEMA_VERSION + 1
        ):
            raise ValueError("Application readiness schema is unsupported.")
        payload: dict[str, object] = {
            "parent_pid": self.parent_pid,
            "pid": self.pid,
            "schema_version": schema_version,
            "surface": self.surface.value,
            "token": self.token,
        }
        if schema_version < _PARENT_READINESS_SCHEMA_VERSION:
            payload.pop("parent_pid")
        if schema_version == _LEGACY_READINESS_SCHEMA_VERSION:
            payload.pop("surface")
        if schema_version >= _MILESTONE_READINESS_SCHEMA_VERSION:
            payload["milestones"] = list(self.milestones)
        if schema_version >= READINESS_SCHEMA_VERSION:
            payload["attester_pids"] = list(self.attester_pids)
        return payload

    @classmethod
    def from_json(cls, payload: object) -> ApplicationReadinessReceipt:
        """Parse one validated receipt or reject malformed external data."""

        if not isinstance(payload, dict):
            raise ValueError("Application readiness receipt must be an object.")
        pid = payload.get("pid")
        token = payload.get("token")
        schema_version = payload.get("schema_version")
        raw_surface = payload.get("surface")
        if (
            schema_version
            not in {
                _LEGACY_READINESS_SCHEMA_VERSION,
                _SURFACE_READINESS_SCHEMA_VERSION,
                _PARENT_READINESS_SCHEMA_VERSION,
                _MILESTONE_READINESS_SCHEMA_VERSION,
                READINESS_SCHEMA_VERSION,
            }
            or not isinstance(pid, int)
            or pid <= 0
            or not isinstance(token, str)
            or not token
        ):
            raise ValueError("Application readiness receipt is invalid.")
        if schema_version == _LEGACY_READINESS_SCHEMA_VERSION and raw_surface is None:
            return cls(
                pid=pid,
                token=token,
                surface=ApplicationReadinessSurface.LEGACY_VISIBLE_SHELL,
                parent_pid=None,
                milestones=(),
            )
        if not isinstance(raw_surface, str):
            raise ValueError("Application readiness receipt is invalid.")
        parent_pid = payload.get("parent_pid")
        if schema_version >= _PARENT_READINESS_SCHEMA_VERSION and (
            not isinstance(parent_pid, int) or parent_pid <= 0
        ):
            raise ValueError("Application readiness receipt is invalid.")
        if schema_version < _PARENT_READINESS_SCHEMA_VERSION:
            parent_pid = None
        raw_milestones = payload.get("milestones")
        milestones: tuple[str, ...]
        if schema_version >= _MILESTONE_READINESS_SCHEMA_VERSION:
            if raw_milestones != list(REQUIRED_READINESS_MILESTONES):
                raise ValueError("Application readiness milestones are incomplete.")
            milestones = REQUIRED_READINESS_MILESTONES
        else:
            milestones = ()
        raw_attester_pids = payload.get("attester_pids")
        if schema_version == READINESS_SCHEMA_VERSION:
            if not isinstance(raw_attester_pids, list) or any(
                not isinstance(process_id, int)
                or isinstance(process_id, bool)
                or process_id <= 0
                for process_id in raw_attester_pids
            ):
                raise ValueError("Application readiness attestation chain is invalid.")
            attester_pids = tuple(raw_attester_pids)
        else:
            attester_pids = ()
        try:
            surface = ApplicationReadinessSurface(raw_surface)
        except ValueError as error:
            raise ValueError("Application readiness receipt is invalid.") from error
        return cls(
            pid=pid,
            token=token,
            surface=surface,
            parent_pid=parent_pid,
            milestones=milestones,
            attester_pids=attester_pids,
        )


def publish_application_readiness_receipt(
    *,
    receipt_path: Path,
    receipt: ApplicationReadinessReceipt,
    schema_version: int = READINESS_SCHEMA_VERSION,
) -> None:
    """Atomically publish one authenticated version-compatible receipt."""

    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = receipt_path.with_name(
        f".{receipt_path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(receipt.to_json(schema_version=schema_version), sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, receipt_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def without_application_readiness_environment(
    environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment detached from every process-bound readiness contract."""

    detached = dict(os.environ if environment is None else environment)
    for name in (
        READINESS_PATH_ENV,
        READINESS_TOKEN_ENV,
        READINESS_SCHEMA_ENV,
        READINESS_DELEGATION_PATH_ENV,
        READINESS_DELEGATION_TOKEN_ENV,
        READINESS_DELEGATION_SCHEMA_ENV,
    ):
        detached.pop(name, None)
    return detached


__all__ = [
    "ApplicationReadinessReceipt",
    "ApplicationReadinessSurface",
    "READINESS_PATH_ENV",
    "READINESS_SCHEMA_ENV",
    "READINESS_DELEGATION_PATH_ENV",
    "READINESS_DELEGATION_SCHEMA_ENV",
    "READINESS_DELEGATION_TOKEN_ENV",
    "READINESS_SCHEMA_VERSION",
    "READINESS_LEGACY_DELEGATION_SCHEMA_VERSION",
    "REQUIRED_READINESS_MILESTONES",
    "READINESS_TOKEN_ENV",
    "publish_application_readiness_receipt",
    "without_application_readiness_environment",
]

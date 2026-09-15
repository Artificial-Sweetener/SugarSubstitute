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

"""Persist validated, version-bound repair preparation for detached execution."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Self

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from sugarsubstitute_shared.launcher_update.persistence import (
    read_json_object,
    write_json_atomic,
)
from sugarsubstitute_shared.launcher_version import safe_launcher_version
from sugarsubstitute_shared.windows_long_paths import operational_path

_SCHEMA_VERSION = 1


class PreparedRepairRequestError(RuntimeError):
    """Report invalid or unsafe detached repair request state."""


@dataclass(frozen=True, slots=True)
class PreparedRepairRequest:
    """Describe verified staged artifacts awaiting one repair transaction."""

    install_root: Path
    scope: RepairScope
    version: str
    channel: str
    target_key: str
    staged_app_dir: Path
    staged_launcher_dir: Path
    staged_app_sha256: str
    staged_launcher_sha256: str
    wait_pid: int | None = None
    wait_process_created_at: float | None = None
    relaunch: bool = False
    helper_bundle_dir: Path | None = None

    def with_helper_bundle(self, directory: Path) -> Self:
        """Bind the verified independent runtime prepared before UI handoff."""
        candidate = replace(self, helper_bundle_dir=directory)
        candidate._validate()
        return candidate

    def with_process_behavior(
        self,
        *,
        wait_pid: int | None,
        wait_process_created_at: float | None = None,
        relaunch: bool,
    ) -> Self:
        """Return a request bound to the process handoff chosen by its caller."""

        if wait_pid is not None and wait_pid <= 0:
            raise ValueError("Repair wait_pid must be positive.")
        if (wait_pid is None) != (wait_process_created_at is None):
            raise ValueError("Repair process identity must be complete.")
        return replace(
            self,
            wait_pid=wait_pid,
            wait_process_created_at=wait_process_created_at,
            relaunch=relaunch,
        )

    def save(self, path: Path) -> None:
        """Persist the request atomically after validating every owned path."""

        self._validate()
        write_json_atomic(
            path,
            {
                "schema_version": _SCHEMA_VERSION,
                "install_root": str(self.install_root),
                "scope": self.scope.value,
                "version": self.version,
                "channel": self.channel,
                "target_key": self.target_key,
                "staged_app_dir": str(self.staged_app_dir),
                "staged_launcher_dir": str(self.staged_launcher_dir),
                "staged_app_sha256": self.staged_app_sha256,
                "staged_launcher_sha256": self.staged_launcher_sha256,
                "wait_pid": self.wait_pid,
                "wait_process_created_at": self.wait_process_created_at,
                "relaunch": self.relaunch,
                "helper_bundle_dir": str(self.helper_bundle_dir)
                if self.helper_bundle_dir is not None
                else None,
            },
        )

    @classmethod
    def load(cls, path: Path) -> Self:
        """Load and validate a detached repair request before any mutation."""

        payload = read_json_object(path)
        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise PreparedRepairRequestError("Unsupported repair request schema.")
        wait_pid = payload.get("wait_pid")
        wait_process_created_at = payload.get("wait_process_created_at")
        relaunch = payload.get("relaunch")
        helper_bundle = payload.get("helper_bundle_dir")
        if helper_bundle is not None and not isinstance(helper_bundle, str):
            raise PreparedRepairRequestError(
                "Repair helper bundle path must be a string."
            )
        if wait_pid is not None and (not isinstance(wait_pid, int) or wait_pid <= 0):
            raise PreparedRepairRequestError("Repair wait_pid must be positive.")
        if wait_process_created_at is not None and not isinstance(
            wait_process_created_at, (int, float)
        ):
            raise PreparedRepairRequestError(
                "Repair process creation time must be numeric."
            )
        if (wait_pid is None) != (wait_process_created_at is None):
            raise PreparedRepairRequestError("Repair process identity is incomplete.")
        if not isinstance(relaunch, bool):
            raise PreparedRepairRequestError("Repair relaunch must be boolean.")
        try:
            request = cls(
                install_root=operational_path(
                    _required_string(payload, "install_root")
                ),
                scope=RepairScope(_required_string(payload, "scope")),
                version=_required_string(payload, "version"),
                channel=_required_string(payload, "channel"),
                target_key=_required_string(payload, "target_key"),
                staged_app_dir=operational_path(
                    _required_string(payload, "staged_app_dir")
                ),
                staged_launcher_dir=operational_path(
                    _required_string(payload, "staged_launcher_dir")
                ),
                staged_app_sha256=_required_sha256(payload, "staged_app_sha256"),
                staged_launcher_sha256=_required_sha256(
                    payload, "staged_launcher_sha256"
                ),
                wait_pid=wait_pid,
                wait_process_created_at=(
                    float(wait_process_created_at)
                    if wait_process_created_at is not None
                    else None
                ),
                relaunch=relaunch,
                helper_bundle_dir=operational_path(helper_bundle)
                if helper_bundle is not None
                else None,
            )
        except ValueError as error:
            raise PreparedRepairRequestError(
                "Repair request fields are invalid."
            ) from error
        try:
            request._validate()
        except ValueError as error:
            raise PreparedRepairRequestError(
                "Repair request version is invalid."
            ) from error
        return request

    def _validate(self) -> None:
        """Reject version and staging paths outside the repair-owned tree."""

        normalized_version = safe_launcher_version(self.version)
        root = operational_path(self.install_root).resolve()
        staging_root = root / ".repair" / "staging" / normalized_version
        if self.helper_bundle_dir is not None:
            helper_root = root / ".repair" / "helper" / normalized_version
            helper = operational_path(self.helper_bundle_dir).resolve()
            if helper == helper_root or not helper.is_relative_to(helper_root):
                raise PreparedRepairRequestError(
                    "Repair helper bundle escapes its version root."
                )
        for staged_path in (self.staged_app_dir, self.staged_launcher_dir):
            resolved = operational_path(staged_path).resolve()
            if resolved == staging_root or not resolved.is_relative_to(staging_root):
                raise PreparedRepairRequestError(
                    f"Repair staging path escapes its version root: {resolved}"
                )
        if not self.target_key.strip():
            raise PreparedRepairRequestError("Repair target key must not be blank.")
        if not self.channel.strip():
            raise PreparedRepairRequestError("Repair channel must not be blank.")
        for digest in (self.staged_app_sha256, self.staged_launcher_sha256):
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest.lower()
            ):
                raise PreparedRepairRequestError("Repair artifact digest is invalid.")


def _required_string(payload: dict[str, object], key: str) -> str:
    """Read one required non-empty request string."""

    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise PreparedRepairRequestError(f"Repair request field is missing: {key}")
    return value


def _required_sha256(payload: dict[str, object], key: str) -> str:
    """Read one required normalized SHA256 digest."""

    value = _required_string(payload, key).lower()
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise PreparedRepairRequestError(f"Repair request digest is invalid: {key}")
    return value


__all__ = ["PreparedRepairRequest", "PreparedRepairRequestError"]

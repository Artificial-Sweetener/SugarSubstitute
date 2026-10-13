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

"""Own the typed handoff for an independently copied baseline recovery helper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sugarsubstitute_shared.launcher_update.persistence import (
    read_json_object,
    write_json_atomic,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity

_RECOVERY_REQUEST_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BaselineRecoveryRequest:
    """Retain invocation intent and exact mapped-image incarnations to release."""

    install_root: Path
    arguments: tuple[str, ...]
    wait_identities: tuple[ProcessIdentity, ...]
    relaunch: bool

    @classmethod
    def load(cls, path: Path) -> BaselineRecoveryRequest:
        """Require a generated request inside its installation's recovery namespace."""
        payload = read_json_object(path)
        root_value = payload.get("install_root")
        arguments = payload.get("arguments")
        identities = payload.get("wait_identities")
        relaunch = payload.get("relaunch")
        if (
            payload.get("schema_version") != _RECOVERY_REQUEST_SCHEMA_VERSION
            or not isinstance(root_value, str)
            or not root_value
            or not isinstance(arguments, list)
            or not all(isinstance(argument, str) for argument in arguments)
            or not isinstance(identities, list)
            or type(relaunch) is not bool
        ):
            raise ValueError("Invalid baseline recovery request.")
        root = Path(root_value).expanduser().resolve()
        if not path.resolve().is_relative_to(
            root / "launcher" / "updates" / "recovery"
        ):
            raise ValueError(
                "Baseline recovery request escapes its installation owner."
            )
        waits: list[ProcessIdentity] = []
        for identity in identities:
            if not isinstance(identity, dict):
                raise ValueError("Invalid baseline recovery process identity.")
            pid = identity.get("pid")
            created_at = identity.get("created_at")
            if (
                type(pid) is not int
                or pid <= 0
                or not isinstance(created_at, (int, float))
                or isinstance(created_at, bool)
            ):
                raise ValueError("Invalid baseline recovery process incarnation.")
            waits.append(ProcessIdentity(pid=pid, created_at=float(created_at)))
        return cls(root, tuple(arguments), tuple(waits), relaunch)

    def save(self, path: Path) -> None:
        """Publish the complete handoff before an independent image is started."""
        if not path.resolve().is_relative_to(
            self.install_root.resolve() / "launcher" / "updates" / "recovery"
        ):
            raise ValueError(
                "Baseline recovery request escapes its installation owner."
            )
        write_json_atomic(
            path,
            {
                "schema_version": _RECOVERY_REQUEST_SCHEMA_VERSION,
                "install_root": str(self.install_root.resolve()),
                "arguments": list(self.arguments),
                "wait_identities": [
                    {"pid": identity.pid, "created_at": identity.created_at}
                    for identity in self.wait_identities
                ],
                "relaunch": self.relaunch,
            },
        )

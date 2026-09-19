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

"""Bind transient preparation worker input to the selected installation and source."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from launcher.sugarsubstitute_launcher.application.repair.models import RepairScope
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.platforms import (
    UnsupportedLauncherPlatformError,
    launcher_target_for_key,
)
from launcher.sugarsubstitute_launcher.repair_preparation_source import (
    RepairPreparationSource,
)
from sugarsubstitute_shared.windows_long_paths import operational_path

_MAXIMUM_INVOCATION_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class RepairPreparationInvocation:
    """Carry inert operation inputs whose file lifetime belongs to the parent supervisor."""

    layout: InstallLayout
    source: RepairPreparationSource
    scope: RepairScope

    def save(self, path: Path) -> None:
        """Write a private control document before its child can be admitted."""
        payload = {
            "install_root": str(self.layout.root),
            "target": self.layout.target.key,
            "scope": self.scope.value,
            "source": self.source.to_json(),
        }
        encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode(
            "ascii"
        )
        if len(encoded) > _MAXIMUM_INVOCATION_BYTES:
            raise ValueError("Repair preparation input exceeds its size limit.")
        with operational_path(path).open("xb") as destination:
            destination.write(encoded)

    @classmethod
    def load(cls, path: Path) -> RepairPreparationInvocation:
        """Bound parsing and reject incomplete input before any release acquisition."""
        with operational_path(path).open("rb") as source:
            encoded = source.read(_MAXIMUM_INVOCATION_BYTES + 1)
        if len(encoded) > _MAXIMUM_INVOCATION_BYTES:
            raise ValueError("Repair preparation input exceeds its size limit.")
        try:
            payload = json.loads(encoded)
        except (ValueError, RecursionError) as error:
            raise ValueError("Repair preparation input is malformed.") from error
        if not isinstance(payload, dict) or set(payload) != {
            "install_root",
            "target",
            "scope",
            "source",
        }:
            raise ValueError("Repair preparation input fields are malformed.")
        root_value, target_value, scope_value = (
            payload["install_root"],
            payload["target"],
            payload["scope"],
        )
        if (
            not isinstance(root_value, str)
            or not root_value
            or "\x00" in root_value
            or not Path(root_value).is_absolute()
            or not isinstance(target_value, str)
            or not isinstance(scope_value, str)
        ):
            raise ValueError("Repair preparation installation boundary is malformed.")
        try:
            target = launcher_target_for_key(target_value)
        except UnsupportedLauncherPlatformError as error:
            raise ValueError("Repair preparation target is unsupported.") from error
        return cls(
            InstallLayout.from_root(Path(root_value), target=target),
            RepairPreparationSource.from_json(payload["source"]),
            RepairScope(scope_value),
        )

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

"""Define installation-owned launcher generation identities and locations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sugarsubstitute_shared.launcher_update.targets import LauncherBundleTarget


@dataclass(frozen=True, slots=True)
class LauncherBundlePaths:
    """Recognize produced generation namespaces independently of retired records."""

    install_root: Path

    @property
    def generations(self) -> Path:
        """Return the authoritative installation namespace for retained generations."""
        return self.install_root.resolve() / "launcher" / "bundles"

    @property
    def selection(self) -> Path:
        """Return the single atomic current/previous selection record."""
        return self.generations / "active.json"

    def generation(self, identity: str) -> Path:
        """Require canonical generated identity before constructing a retained path."""
        if UUID(identity).hex != identity:
            raise ValueError("Invalid launcher generation identifier.")
        return self.generations / identity

    def payload_for_executable(
        self, executable: Path, target: LauncherBundleTarget
    ) -> Path | None:
        """Recognize a generation's exact packaged role without requiring live files.

        A running owner remains recoverable after its records or payload retire.
        Callers must separately verify OS process identity and invocation intent.
        This method confers no permission to launch unverified payloads.
        """
        image = executable.resolve()
        try:
            relative = image.relative_to(self.generations)
            if len(relative.parts) < 3 or relative.parts[1] != "payload":
                return None
            payload = self.generation(relative.parts[0]) / "payload"
        except ValueError:
            return None
        role = Path(*relative.parts[2:])
        if role not in target.required_file_relative_paths:
            return None
        return payload

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

"""Define launcher-managed runtime results and infrastructure ports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


class RuntimeProvisioningError(RuntimeError):
    """Report that the launcher-managed runtime cannot be prepared."""


class RuntimeCommandRunner(Protocol):
    """Run one runtime provisioning subprocess command."""

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
    ) -> None:
        """Run one command or raise on failure."""


class UvExecutableProvider(Protocol):
    """Provide a verified uv executable for one installation layout."""

    def ensure(self, *, layout: InstallLayout) -> Path:
        """Return the managed uv executable path."""


@dataclass(frozen=True, slots=True)
class RuntimeProvisioningResult:
    """Describe a provisioned launcher-managed runtime."""

    python_executable: Path
    requirements_path: Path

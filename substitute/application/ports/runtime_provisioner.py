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

"""Define runtime provisioning behavior required by onboarding services."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from substitute.domain.onboarding import RuntimeConfiguration


@runtime_checkable
class RuntimeProvisioner(Protocol):
    """Provision and describe the visible Substitute runtime."""

    def provision(self, configuration: RuntimeConfiguration) -> RuntimeConfiguration:
        """Provision the runtime and return updated configuration state."""

    def build_launch_command(
        self,
        configuration: RuntimeConfiguration,
        entrypoint_path: Path,
    ) -> list[str]:
        """Return the command used to launch Substitute under the provisioned runtime."""


__all__ = ["RuntimeProvisioner"]

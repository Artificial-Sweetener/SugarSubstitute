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

"""Define the managed Comfy repair adapter boundary."""

from __future__ import annotations
from pathlib import Path
from typing import Protocol
from launcher.sugarsubstitute_launcher.application.repair.models import (
    ManagedComfyOwnership,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout


class ManagedComfyRepairer(Protocol):
    """Restore and validate app-owned content inside proven managed Comfy."""

    def repair_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Restore the exact app-owned custom-node versions."""

    def validate_owned_nodes(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Raise unless both app-owned nodepacks are ready."""

    def stage_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
        destination: Path,
    ) -> None:
        """Build a fresh managed workspace outside the active Comfy tree."""

    def validate_full_managed_comfy(
        self,
        *,
        layout: InstallLayout,
        ownership: ManagedComfyOwnership,
    ) -> None:
        """Raise unless the promoted managed workspace is complete."""

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

"""Define Comfy target configuration persistence contract."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from substitute.domain.onboarding import ComfyTargetConfiguration


@runtime_checkable
class ComfyTargetConfigurationRepository(Protocol):
    """Persist and load the selected Comfy target configuration."""

    def exists(self) -> bool:
        """Return whether persisted target configuration exists."""

    def build_default(self) -> ComfyTargetConfiguration:
        """Build the default target configuration for this repository."""

    def load(self) -> ComfyTargetConfiguration:
        """Load the active Comfy target configuration."""

    def save(self, configuration: ComfyTargetConfiguration) -> None:
        """Persist the active Comfy target configuration."""


__all__ = ["ComfyTargetConfigurationRepository"]

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

"""Define persistence contract for the managed Comfy runtime state model."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
)


@runtime_checkable
class ManagedRuntimeConfigurationRepository(Protocol):
    """Persist and load the managed Comfy runtime configuration."""

    def exists(self) -> bool:
        """Return whether persisted managed runtime state exists."""

    def build_default(self) -> ManagedRuntimeConfiguration:
        """Build the default managed runtime configuration."""

    def load(self) -> ManagedRuntimeConfiguration:
        """Load the active managed runtime configuration."""

    def save(self, configuration: ManagedRuntimeConfiguration) -> None:
        """Persist the active managed runtime configuration."""


__all__ = ["ManagedRuntimeConfigurationRepository"]

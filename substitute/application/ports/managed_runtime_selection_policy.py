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

"""Define application-facing selection for managed Comfy runtime policy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from substitute.domain.onboarding.managed_runtime_models import (
    ManagedRuntimeConfiguration,
)


class ManagedRuntimeSelectionUnavailableError(RuntimeError):
    """Report that this machine has no supported managed Comfy strategy."""


@runtime_checkable
class ManagedRuntimeSelectionPolicy(Protocol):
    """Select one normalized managed runtime configuration for this machine."""

    def select_configuration(
        self,
        *,
        force_cpu_mode: bool = False,
        prefer_edge_torch: bool = False,
        prefer_edge_comfy_channel: bool = False,
    ) -> ManagedRuntimeConfiguration:
        """Return the chosen managed runtime configuration for the supplied flags."""


__all__ = [
    "ManagedRuntimeSelectionPolicy",
    "ManagedRuntimeSelectionUnavailableError",
]

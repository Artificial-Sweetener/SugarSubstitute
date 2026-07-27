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

"""Model persisted user control bindings without presentation dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

CONTROL_BINDING_PREFERENCES_SCHEMA_VERSION = "1"


@dataclass(frozen=True, slots=True)
class ControlBindingPreferences:
    """Store explicit user bindings keyed by stable application command id."""

    schema_version: str
    bindings: Mapping[str, str | None]

    def __post_init__(self) -> None:
        """Freeze the persisted mapping at the domain boundary."""

        object.__setattr__(self, "bindings", MappingProxyType(dict(self.bindings)))

    def with_binding(
        self,
        command_id: str,
        binding: str | None,
    ) -> ControlBindingPreferences:
        """Return preferences with one command binding replaced."""

        bindings = dict(self.bindings)
        bindings[command_id] = binding
        return ControlBindingPreferences(
            schema_version=CONTROL_BINDING_PREFERENCES_SCHEMA_VERSION,
            bindings=bindings,
        )


def default_control_binding_preferences() -> ControlBindingPreferences:
    """Return empty explicit bindings for the first Controls release."""

    return ControlBindingPreferences(
        schema_version=CONTROL_BINDING_PREFERENCES_SCHEMA_VERSION,
        bindings={},
    )


__all__ = [
    "CONTROL_BINDING_PREFERENCES_SCHEMA_VERSION",
    "ControlBindingPreferences",
    "default_control_binding_preferences",
]

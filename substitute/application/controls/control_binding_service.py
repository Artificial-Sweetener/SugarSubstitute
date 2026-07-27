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

"""Own normalized persistence and conflict checks for control bindings."""

from __future__ import annotations

from substitute.application.ports.control_binding_preference_repository import (
    ControlBindingPreferenceRepository,
)
from substitute.domain.controls import ControlBindingPreferences


class ControlBindingService:
    """Persist user bindings while keeping command identities independent of devices."""

    def __init__(self, repository: ControlBindingPreferenceRepository) -> None:
        """Store the repository that owns persisted preferences."""

        self._repository = repository

    def binding_for(self, command_id: str) -> str | None:
        """Return the explicit binding for one command, if configured."""

        return self.load_preferences().bindings.get(command_id)

    def load_preferences(self) -> ControlBindingPreferences:
        """Load a normalized persisted binding snapshot."""

        return self._normalize(self._repository.load())

    def set_binding(
        self, command_id: str, binding: str | None
    ) -> ControlBindingPreferences:
        """Save one command binding and transfer duplicate bindings to that command."""

        normalized_binding = binding.strip() if isinstance(binding, str) else None
        if normalized_binding == "":
            normalized_binding = None
        preferences = self.load_preferences()
        updated = preferences
        if normalized_binding is not None:
            for other_command_id, other_binding in preferences.bindings.items():
                if (
                    other_command_id != command_id
                    and other_binding == normalized_binding
                ):
                    updated = updated.with_binding(other_command_id, None)
        updated = updated.with_binding(command_id, normalized_binding)
        self._repository.save(updated)
        return updated

    def _normalize(
        self, preferences: ControlBindingPreferences
    ) -> ControlBindingPreferences:
        """Discard malformed bindings while retaining future command ids safely."""

        bindings = {
            str(command_id): binding.strip()
            if isinstance(binding, str) and binding.strip()
            else None
            for command_id, binding in preferences.bindings.items()
            if isinstance(command_id, str)
        }
        return ControlBindingPreferences(schema_version="1", bindings=bindings)


__all__ = ["ControlBindingService"]

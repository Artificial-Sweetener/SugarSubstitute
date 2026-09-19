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

"""Resolve mounted editor callbacks to the current workflow projection."""

from __future__ import annotations

from collections.abc import Mapping


class CurrentEditorFieldStateResolver:
    """Prevent mounted widgets from mutating superseded projection objects."""

    def __init__(self, host: object | None) -> None:
        """Store the host that owns the replaceable workflow projection."""

        self._host = host

    def resolve(self, captured_state: object, cube_alias: str | None) -> object:
        """Return the current state for an alias or the captured stable state."""

        if cube_alias is None:
            return captured_state
        cube_states = self._cube_states()
        if not cube_states:
            return captured_state
        return cube_states.get(cube_alias, captured_state)

    def resolve_for_field_identity(
        self,
        captured_state: object,
        field_identity: str,
    ) -> object:
        """Resolve a prompt preference callback without retaining stale state."""

        if "." not in field_identity:
            return captured_state
        return self.resolve(captured_state, self._alias_for_state(captured_state))

    def _alias_for_state(self, cube_state: object) -> str | None:
        """Return the current or formerly associated stable Cube alias."""

        alias = getattr(cube_state, "alias", None)
        if isinstance(alias, str):
            return alias
        cube_states = self._cube_states()
        if not cube_states:
            return None
        return next(
            (key for key, candidate in cube_states.items() if candidate is cube_state),
            None,
        )

    def _cube_states(self) -> Mapping[str, object] | None:
        """Return the host projection without constraining its concrete value type."""

        candidate = getattr(self._host, "_cube_states", None)
        return candidate if isinstance(candidate, Mapping) else None


__all__ = ["CurrentEditorFieldStateResolver"]

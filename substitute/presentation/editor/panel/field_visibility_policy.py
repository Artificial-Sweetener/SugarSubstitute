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

"""Compose editor field visibility without depending on Qt widgets."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FieldVisibilityPolicy:
    """Resolve behavior, search, and advanced-disclosure field visibility."""

    hidden_keys: frozenset[object]
    search_active: bool
    search_match_keys: frozenset[object] | None
    advanced_field_keys: frozenset[object]
    shown_advanced_input_nodes: frozenset[tuple[str, str]]

    def hides(self, field_key: object) -> bool:
        """Return whether the composed policy hides one field identity."""

        if self._is_behavior_hidden(field_key):
            return True
        if not self._matches_search(field_key):
            return True
        if field_key not in self.advanced_field_keys:
            return False
        if self.search_active:
            return False
        if not isinstance(field_key, tuple) or len(field_key) < 3:
            return True
        return (field_key[0], field_key[1]) not in self.shown_advanced_input_nodes

    def _is_behavior_hidden(self, field_key: object) -> bool:
        """Match both fully scoped and legacy leaf-only hidden identities."""

        return bool(
            field_key in self.hidden_keys
            or (isinstance(field_key, tuple) and field_key[-1] in self.hidden_keys)
            or (isinstance(field_key, str) and field_key in self.hidden_keys)
        )

    def _matches_search(self, field_key: object) -> bool:
        """Keep only explicit matches while field search is active."""

        if not self.search_active:
            return True
        if self.search_match_keys is None:
            return False
        if field_key in self.search_match_keys:
            return True
        return bool(
            isinstance(field_key, tuple) and field_key[-1] in self.search_match_keys
        )


__all__ = ["FieldVisibilityPolicy"]

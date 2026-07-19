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

"""Define persistence operations for user autocomplete tag lists."""

from __future__ import annotations

from typing import Protocol

from .models import PromptAutocompleteList, PromptAutocompleteListKind


class PromptAutocompleteListRepository(Protocol):
    """Persist named line-based autocomplete lists and their enablement."""

    def list_lists(self) -> tuple[PromptAutocompleteList, ...]:
        """Return every managed autocomplete list."""

    def create_list(
        self,
        *,
        name: str,
        kind: PromptAutocompleteListKind,
        text: str,
    ) -> PromptAutocompleteList:
        """Create one enabled list."""

    def read_text(self, list_id: str) -> str:
        """Read one list's source text."""

    def write_text(self, list_id: str, text: str) -> PromptAutocompleteList:
        """Replace one list's source text."""

    def rename_list(self, list_id: str, name: str) -> PromptAutocompleteList:
        """Rename one list while preserving its kind and enablement."""

    def delete_list(self, list_id: str) -> None:
        """Delete one list and its enablement record."""

    def set_enabled(self, list_id: str, enabled: bool) -> PromptAutocompleteList:
        """Set whether one list participates in autocomplete."""


__all__ = ["PromptAutocompleteListRepository"]

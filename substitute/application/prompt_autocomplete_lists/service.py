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

"""Own user autocomplete list lifecycle and prepared catalog state."""

from __future__ import annotations

from collections.abc import Callable

from .models import (
    PromptAutocompleteList,
    PromptAutocompleteListKind,
    PromptAutocompleteListSnapshot,
)
from .repository import PromptAutocompleteListRepository


class PromptAutocompleteListService:
    """Coordinate list mutations and publish one normalized snapshot."""

    def __init__(
        self,
        repository: PromptAutocompleteListRepository,
        *,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        """Store persistence and cache-invalidation dependencies."""

        self._repository = repository
        self._on_changed = on_changed
        self._revision = 0

    def list_lists(self) -> tuple[PromptAutocompleteList, ...]:
        """Return all managed lists in repository order."""

        return self._repository.list_lists()

    def set_change_callback(self, callback: Callable[[], None] | None) -> None:
        """Bind the single catalog refresh callback after composition."""

        self._on_changed = callback

    def read_text(self, list_id: str) -> str:
        """Return one list's line-based source text."""

        return self._repository.read_text(list_id)

    def create_list(
        self,
        *,
        name: str,
        kind: PromptAutocompleteListKind,
        text: str = "",
    ) -> PromptAutocompleteList:
        """Create an enabled list and refresh autocomplete consumers."""

        created = self._repository.create_list(name=name, kind=kind, text=text)
        self._changed()
        return created

    def write_text(self, list_id: str, text: str) -> PromptAutocompleteList:
        """Persist list text and refresh autocomplete consumers."""

        updated = self._repository.write_text(list_id, text)
        self._changed()
        return updated

    def rename_list(self, list_id: str, name: str) -> PromptAutocompleteList:
        """Rename a list and refresh autocomplete consumers."""

        updated = self._repository.rename_list(list_id, name)
        self._changed()
        return updated

    def delete_list(self, list_id: str) -> None:
        """Delete a list and refresh autocomplete consumers."""

        self._repository.delete_list(list_id)
        self._changed()

    def set_enabled(self, list_id: str, enabled: bool) -> PromptAutocompleteList:
        """Toggle list participation and refresh autocomplete consumers."""

        updated = self._repository.set_enabled(list_id, enabled)
        self._changed()
        return updated

    def snapshot(self) -> PromptAutocompleteListSnapshot:
        """Build normalized enabled-list content at an explicit refresh boundary."""

        custom: dict[str, str] = {}
        censored: set[str] = set()
        for autocomplete_list in self.list_lists():
            if not autocomplete_list.enabled:
                continue
            for tag in _list_tags(autocomplete_list.text):
                normalized = normalize_prompt_tag(tag)
                if not normalized:
                    continue
                if autocomplete_list.kind is PromptAutocompleteListKind.CENSORED:
                    censored.add(normalized)
                else:
                    custom.setdefault(normalized, display_prompt_tag(tag))
        return PromptAutocompleteListSnapshot(
            custom_tags=tuple(
                display
                for normalized, display in custom.items()
                if normalized not in censored
            ),
            censored_tags=frozenset(censored),
            revision=self._revision,
        )

    def _changed(self) -> None:
        """Advance snapshot identity and notify the configured gateway."""

        self._revision += 1
        if self._on_changed is not None:
            self._on_changed()


def normalize_prompt_tag(text: str) -> str:
    """Normalize tag identity with spaces and underscores equivalent."""

    return " ".join(text.replace("_", " ").casefold().split())


def display_prompt_tag(text: str) -> str:
    """Return a trimmed, space-separated display tag."""

    return " ".join(text.replace("_", " ").split())


def _list_tags(text: str) -> tuple[str, ...]:
    """Return non-empty source lines as independent tags."""

    return tuple(line.strip() for line in text.splitlines() if line.strip())


__all__ = [
    "display_prompt_tag",
    "normalize_prompt_tag",
    "PromptAutocompleteListService",
]

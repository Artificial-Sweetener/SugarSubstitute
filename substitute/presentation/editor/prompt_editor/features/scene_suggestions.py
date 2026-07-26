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

"""Derive bounded scene-title autocomplete suggestions from prepared titles."""

from __future__ import annotations

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptSceneAutocompleteQuery,
)

from .scene_models import PromptSceneAutocompleteState


def scene_autocomplete_suggestions(
    *,
    state: PromptSceneAutocompleteState,
    query: PromptSceneAutocompleteQuery,
    limit: int,
) -> tuple[PromptAutocompleteSuggestion, ...]:
    """Return deduplicated scene suggestions without reading source or state."""

    if limit <= 0 or not state.ready:
        return ()
    normalized_prefix = query.prefix.strip().casefold()
    matches: list[PromptAutocompleteSuggestion] = []
    seen_titles: set[str] = set()
    for title in state.titles:
        normalized_title = title.strip().casefold()
        if not normalized_title or normalized_title in seen_titles:
            continue
        seen_titles.add(normalized_title)
        if normalized_prefix and not normalized_title.startswith(normalized_prefix):
            continue
        if normalized_prefix and normalized_title == normalized_prefix:
            continue
        matches.append(
            PromptAutocompleteSuggestion(
                tag=title,
                popularity=None,
                source_label="Scene",
                source_kind="scene",
            )
        )
        if len(matches) >= limit:
            break
    return tuple(matches)


__all__ = ["scene_autocomplete_suggestions"]

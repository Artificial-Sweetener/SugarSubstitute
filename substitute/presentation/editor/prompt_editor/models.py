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

"""Define typed presentation-local state for prompt editor interactions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from substitute.application.ports import PromptAutocompleteSuggestion
from substitute.application.prompt_editor.autocomplete.queries import (
    PromptSceneAutocompleteQuery,
    PromptWildcardAutocompleteQuery,
)
from substitute.application.prompt_editor.lora.autocomplete import (
    PromptLoraAutocompleteCandidate,
    PromptLoraAutocompleteQuery,
)


class PromptEditorInteractionMode(Enum):
    """Describe the prompt editor's current presentation interaction mode."""

    TEXT_EDITING = auto()
    SEGMENT_REORDER = auto()


@dataclass(slots=True)
class AutocompleteSession:
    """Store the active autocomplete selection and replacement bounds."""

    mode: str = "none"
    suggestions: tuple[PromptAutocompleteSuggestion, ...] = ()
    selected_index: int = -1
    word_start: int | None = None
    word_end: int | None = None
    active_tag_end: int | None = None
    prefix: str = ""
    lora_candidates: tuple[PromptLoraAutocompleteCandidate, ...] = ()
    lora_query: PromptLoraAutocompleteQuery | None = None
    scene_query: PromptSceneAutocompleteQuery | None = None
    wildcard_query: PromptWildcardAutocompleteQuery | None = None

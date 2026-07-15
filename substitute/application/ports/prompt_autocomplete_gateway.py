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

"""Define prompt autocomplete lookup contracts used by presentation widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


@dataclass(frozen=True)
class PromptAutocompleteSuggestion:
    """Represent one prompt autocomplete row returned to presentation."""

    tag: str
    popularity: int | None = None
    source_label: str | None = None
    source_kind: Literal["tag", "lora_trigger", "scene", "wildcard"] = "tag"


@runtime_checkable
class PromptAutocompleteGateway(Protocol):
    """Return ranked prompt autocomplete suggestions for one typed prefix."""

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return suggestions for one typed prefix."""


__all__ = ["PromptAutocompleteGateway", "PromptAutocompleteSuggestion"]

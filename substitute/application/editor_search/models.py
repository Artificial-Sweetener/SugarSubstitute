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

"""Define typed editor-search models owned by the application layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EditorSearchMode(StrEnum):
    """Enumerate the supported editor-search modes."""

    TEXT = "text"
    NODE = "node"
    FIELD = "field"


@dataclass(frozen=True)
class EditorSearchQuery:
    """Describe one parsed editor-search query and its normalized components."""

    mode: EditorSearchMode
    raw_text: str
    normalized_text: str
    node_filter_text: str
    text_filter_text: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class TextSearchMatch:
    """Record one source-backed text match inside an editor field."""

    cube_alias: str
    node_name: str
    field_key: str
    start: int
    length: int


@dataclass(frozen=True)
class EditorSearchResult:
    """Describe the complete search result used by shell and editor presentation."""

    query: EditorSearchQuery
    matching_nodes: set[tuple[str, str]]
    matching_fields: set[tuple[str, str, str]]
    text_matches: tuple[TextSearchMatch, ...]
    navigation_matches: tuple[TextSearchMatch, ...]

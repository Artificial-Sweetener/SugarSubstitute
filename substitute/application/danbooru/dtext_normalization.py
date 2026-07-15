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

"""Normalize prompt selections into Danbooru wiki and tag lookup titles."""

from __future__ import annotations

import re

_WHITESPACE_PATTERN = re.compile(r"\s+")
_URL_PATTERN = re.compile(r"^(?:https?://|www\.)", re.IGNORECASE)


def normalize_selection_text(selection_text: str) -> str:
    """Return one cleaned selection string suitable for Danbooru title lookup."""

    stripped = selection_text.strip().strip(",")
    if not stripped:
        return ""
    unescaped = stripped.replace(r"\(", "(").replace(r"\)", ")")
    return _WHITESPACE_PATTERN.sub(" ", unescaped).strip()


def candidate_titles_for_selection(selection_text: str) -> tuple[str, ...]:
    """Return candidate Danbooru wiki titles ordered by lookup preference."""

    normalized = normalize_selection_text(selection_text)
    if not normalized:
        return ()
    candidates: list[str] = []
    underscore_title = normalized.replace(" ", "_")
    for candidate in (underscore_title, normalized):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    return tuple(candidates)


def prompt_display_text_from_tag(tag: str) -> str:
    """Return the prompt-editor display form for one Danbooru tag token."""

    return tag.replace("_", " ")


def prompt_display_text_from_alias(alias: str) -> str:
    """Return the native display form for one Danbooru alias or external link."""

    return (
        alias
        if _URL_PATTERN.match(alias.strip())
        else prompt_display_text_from_tag(alias)
    )


__all__ = [
    "candidate_titles_for_selection",
    "normalize_selection_text",
    "prompt_display_text_from_alias",
    "prompt_display_text_from_tag",
]

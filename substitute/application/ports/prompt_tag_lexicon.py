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

"""Define exact prompt tag membership contracts for prompt-aware services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


def normalize_prompt_tag_lookup_text(text: str) -> str:
    """Normalize exact-tag lookup text without adapter dependencies."""

    return " ".join(text.replace("_", " ").casefold().split())


@dataclass(frozen=True, slots=True)
class PromptTagLexiconSnapshot:
    """Answer exact membership from a prepared immutable tag set."""

    normalized_tags: frozenset[str] = frozenset()

    def contains_prompt_tag(self, text: str) -> bool:
        """Return whether text exactly matches a prepared prompt tag."""

        normalized = normalize_prompt_tag_lookup_text(text)
        return bool(normalized) and normalized in self.normalized_tags


@runtime_checkable
class PromptTagLexicon(Protocol):
    """Answer exact prompt tag membership questions for prompt filters."""

    def contains_prompt_tag(self, text: str) -> bool:
        """Return whether text exactly matches a known prompt tag."""


@runtime_checkable
class PromptTagLexiconSnapshotProvider(Protocol):
    """Provide prepared exact-tag state without loading on interactive paths."""

    def prepared_prompt_tag_snapshot(self) -> PromptTagLexiconSnapshot:
        """Return the current immutable snapshot without performing I/O."""


__all__ = [
    "PromptTagLexicon",
    "PromptTagLexiconSnapshot",
    "PromptTagLexiconSnapshotProvider",
    "normalize_prompt_tag_lookup_text",
]

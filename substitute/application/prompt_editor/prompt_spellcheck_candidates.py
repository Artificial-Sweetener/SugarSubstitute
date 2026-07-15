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

"""Extract prompt words that are safe to send to a spellcheck backend."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
import re

from substitute.application.ports import PromptTagLexicon
from substitute.domain.prompt import PROMPT_SCENE_MARKER

from .prompt_document_projector import PromptDocumentProjector
from .prompt_document_views import PromptDocumentView
from .prompt_spellcheck_models import PromptSpellcheckCandidate

_WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z']*")
_URL_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_WINDOWS_DRIVE_PATH_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")
_HASH_PATTERN = re.compile(r"^(?:#|0x)?[0-9a-fA-F]{8,}$")
_EXTENSION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9]{1,8}$")
_MODEL_CASE_PATTERN = re.compile(r"[a-z][A-Z]|[A-Z]{2,}[a-z]")
_ALWAYS_SKIP_CHARACTERS = frozenset("_/\\<>")


@dataclass(frozen=True, slots=True)
class _SourceRange:
    """Represent a half-open prompt source range."""

    start: int
    end: int

    def contains_range(self, start: int, end: int) -> bool:
        """Return whether this range fully contains another half-open range."""

        return self.start <= start and end <= self.end


class PromptSpellcheckCandidateService:
    """Extract prose-like prompt ranges while suppressing known prompt syntax."""

    def __init__(
        self,
        *,
        document_projector: PromptDocumentProjector | None = None,
        tag_lexicon: PromptTagLexicon | None = None,
    ) -> None:
        """Store prompt parsing and exact-tag collaborators."""

        self._document_projector = document_projector or PromptDocumentProjector()
        self._tag_lexicon = tag_lexicon

    def candidates_for_text(self, text: str) -> tuple[PromptSpellcheckCandidate, ...]:
        """Return raw source word ranges that should be spellchecked."""

        if not text.strip():
            return ()
        document_view = self._document_projector.build_document_view(text)
        blocked_ranges = tuple(_syntax_ranges(document_view))
        tag_decisions: dict[str, bool] = {}
        candidates: list[PromptSpellcheckCandidate] = []
        for match in _WORD_PATTERN.finditer(text):
            start, end = match.span()
            word = match.group()
            if self._range_is_blocked(start, end, blocked_ranges):
                continue
            if self._word_should_be_skipped(
                text=text,
                word=word,
                start=start,
                end=end,
                document_view=document_view,
                tag_decisions=tag_decisions,
            ):
                continue
            candidates.append(
                PromptSpellcheckCandidate(
                    source_start=start,
                    source_end=end,
                    text=word,
                )
            )
        return tuple(candidates)

    def _range_is_blocked(
        self,
        start: int,
        end: int,
        blocked_ranges: tuple[_SourceRange, ...],
    ) -> bool:
        """Return whether a source range belongs to prompt syntax."""

        return any(
            blocked_range.contains_range(start, end) for blocked_range in blocked_ranges
        )

    def _word_should_be_skipped(
        self,
        *,
        text: str,
        word: str,
        start: int,
        end: int,
        document_view: PromptDocumentView,
        tag_decisions: dict[str, bool],
    ) -> bool:
        """Return whether a prose-looking word is actually prompt metadata."""

        token = _source_token_at(text, start, end)
        segment_text = _segment_text_at(document_view, start)
        if _token_should_be_skipped(token):
            return True
        if _is_exact_prompt_tag(word, self._tag_lexicon, tag_decisions):
            return True
        if segment_text is not None and _segment_should_be_skipped(
            segment_text,
            tag_lexicon=self._tag_lexicon,
            tag_decisions=tag_decisions,
        ):
            return True
        return False


def _syntax_ranges(document_view: PromptDocumentView) -> Iterable[_SourceRange]:
    """Yield ranges that must never be sent to backend spellcheck."""

    for syntax_span in document_view.syntax_spans:
        yield _SourceRange(syntax_span.start, syntax_span.end)
    for lora_span in document_view.lora_spans:
        yield _SourceRange(lora_span.outer_start, lora_span.outer_end)
    for wildcard_span in document_view.wildcard_spans:
        yield _SourceRange(wildcard_span.outer_start, wildcard_span.outer_end)


def _source_token_at(text: str, start: int, end: int) -> str:
    """Return the surrounding non-whitespace/non-comma token for one word range."""

    token_start = start
    while (
        token_start > 0
        and not text[token_start - 1].isspace()
        and text[token_start - 1] != ","
    ):
        token_start -= 1
    token_end = end
    while (
        token_end < len(text)
        and not text[token_end].isspace()
        and text[token_end] != ","
    ):
        token_end += 1
    return text[token_start:token_end]


def _segment_text_at(
    document_view: PromptDocumentView,
    source_position: int,
) -> str | None:
    """Return the comma-separated segment text containing one source position."""

    for segment in document_view.segments:
        if segment.selection_start <= source_position <= segment.selection_end:
            return document_view.source_text[
                segment.selection_start : segment.selection_end
            ].strip()
    return None


def _token_should_be_skipped(token: str) -> bool:
    """Return whether one source token is prompt syntax or machine-like text."""

    stripped = token.strip()
    if not stripped:
        return True
    if any(character in stripped for character in _ALWAYS_SKIP_CHARACTERS):
        return True
    if ":" in stripped:
        return True
    if stripped.startswith("#") or stripped.startswith(PROMPT_SCENE_MARKER):
        return True
    if _URL_PATTERN.match(stripped):
        return True
    if _WINDOWS_DRIVE_PATH_PATTERN.match(stripped):
        return True
    if _HASH_PATTERN.match(stripped):
        return True
    if _EXTENSION_TOKEN_PATTERN.match(stripped):
        return True
    if _MODEL_CASE_PATTERN.search(stripped):
        return True
    if any(character.isdigit() for character in stripped):
        return True
    return False


def _segment_should_be_skipped(
    segment_text: str,
    *,
    tag_lexicon: PromptTagLexicon | None,
    tag_decisions: dict[str, bool],
) -> bool:
    """Return whether a whole prompt segment is a known tag-like phrase."""

    stripped = segment_text.strip()
    if not stripped:
        return True
    if _token_should_be_skipped(stripped):
        return True
    return _is_exact_prompt_tag(stripped, tag_lexicon, tag_decisions)


def _is_exact_prompt_tag(
    text: str,
    tag_lexicon: PromptTagLexicon | None,
    tag_decisions: dict[str, bool],
) -> bool:
    """Return cached exact autocomplete-tag membership for one prompt text."""

    if tag_lexicon is None:
        return False
    normalized_text = " ".join(text.replace("_", " ").casefold().split())
    if not normalized_text:
        return False
    if normalized_text not in tag_decisions:
        tag_decisions[normalized_text] = tag_lexicon.contains_prompt_tag(text)
    return tag_decisions[normalized_text]


__all__ = ["PromptSpellcheckCandidateService"]

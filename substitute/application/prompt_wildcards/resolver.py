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

"""Resolve prompt wildcard placeholders using native Substitute services."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from typing import Protocol

from substitute.domain.prompt import (
    PromptWildcardCsvSource,
    PromptWildcardReplacementDetail,
    PromptWildcardResolution,
    PromptWildcardSyntaxProfile,
    PromptWildcardTextSource,
    WildcardForm,
    parse_prompt_document,
)


class PromptWildcardSourceProvider(Protocol):
    """Load wildcard candidates for the resolver."""

    def load_text_source(self, identifier: str) -> PromptWildcardTextSource | None:
        """Return simple wildcard text candidates for one identifier."""

    def load_csv_source(self, identifier: str) -> PromptWildcardCsvSource | None:
        """Return CSV wildcard row candidates for one identifier."""


@dataclass(frozen=True, slots=True)
class _ResolvedPlaceholder:
    """Capture one resolved placeholder text replacement."""

    outer_text: str
    value: str
    wildcard_form: str
    identifier: str
    source_id: str
    selected_index: int
    line_number: int
    item_count: int
    tag: str | None
    csv_column: str | None
    seed: int | None

    def replacement_detail(self) -> PromptWildcardReplacementDetail:
        """Return public trace provenance for this resolved placeholder."""

        return PromptWildcardReplacementDetail(
            outer_text=self.outer_text,
            value=self.value,
            wildcard_form=self.wildcard_form,
            identifier=self.identifier,
            source_id=self.source_id,
            selected_index=self.selected_index,
            line_number=self.line_number,
            item_count=self.item_count,
            tag=self.tag,
            csv_column=self.csv_column,
            seed=self.seed,
        )


@dataclass(slots=True)
class PromptWildcardResolutionContext:
    """Carry deterministic wildcard choices across prompt resolver calls."""

    seed: int | None = None
    base_index_by_source: dict[tuple[int | None, tuple[str, str]], int] = field(
        default_factory=dict
    )
    tag_offset_by_key: dict[tuple[tuple[int | None, tuple[str, str]], str], int] = (
        field(default_factory=dict)
    )
    text_sources: dict[str, PromptWildcardTextSource | None] = field(
        default_factory=dict
    )
    csv_sources: dict[str, PromptWildcardCsvSource | None] = field(default_factory=dict)
    _rng_by_seed: dict[int | None, random.Random] = field(default_factory=dict)

    def effective_seed(self, seed: int | None) -> int | None:
        """Return the call seed, falling back to the context pass seed."""

        return seed if seed is not None else self.seed

    def rng_for_seed(self, seed: int | None) -> random.Random:
        """Return the pass-stable random stream for one effective seed."""

        if seed not in self._rng_by_seed:
            self._rng_by_seed[seed] = (
                random.Random(seed) if seed is not None else random.Random()
            )
        return self._rng_by_seed[seed]


class PromptWildcardResolver:
    """Resolve prompt wildcard placeholders with Comfy csvwildcards-compatible rules."""

    _MAX_ITERATIONS = 25

    def __init__(
        self,
        source_provider: PromptWildcardSourceProvider,
        *,
        syntax_profile: PromptWildcardSyntaxProfile | None = None,
    ) -> None:
        """Store source loading and syntax collaborators."""

        self._source_provider = source_provider
        self._syntax_profile = syntax_profile or PromptWildcardSyntaxProfile.default()

    def resolve(
        self,
        prompt_text: str,
        *,
        seed: int | None = None,
        context: PromptWildcardResolutionContext | None = None,
    ) -> PromptWildcardResolution:
        """Return prompt text with all resolvable wildcards substituted."""

        effective_seed = context.effective_seed(seed) if context is not None else seed
        rng = (
            context.rng_for_seed(effective_seed)
            if context is not None
            else random.Random(effective_seed)
        )
        current_text = prompt_text
        replacements: list[tuple[str, str]] = []
        replacement_details: list[PromptWildcardReplacementDetail] = []
        base_index_by_source: dict[tuple[int | None, tuple[str, str]], int] = (
            context.base_index_by_source if context is not None else {}
        )
        tag_offset_by_key: dict[tuple[tuple[int | None, tuple[str, str]], str], int] = (
            context.tag_offset_by_key if context is not None else {}
        )
        text_sources: dict[str, PromptWildcardTextSource | None] = (
            context.text_sources if context is not None else {}
        )
        csv_sources: dict[str, PromptWildcardCsvSource | None] = (
            context.csv_sources if context is not None else {}
        )

        for _iteration in range(self._MAX_ITERATIONS):
            resolved_placeholders = self._resolve_iteration(
                current_text=current_text,
                seed=effective_seed,
                rng=rng,
                base_index_by_source=base_index_by_source,
                tag_offset_by_key=tag_offset_by_key,
                text_sources=text_sources,
                csv_sources=csv_sources,
            )
            if not resolved_placeholders:
                break

            next_text = current_text
            for placeholder in resolved_placeholders:
                next_text = next_text.replace(placeholder.outer_text, placeholder.value)
                replacements.append((placeholder.outer_text, placeholder.value))
                replacement_details.append(placeholder.replacement_detail())
            if next_text == current_text:
                break
            current_text = next_text

        return PromptWildcardResolution(
            source_text=prompt_text,
            resolved_text=current_text,
            replacements=tuple(replacements),
            replacement_details=tuple(replacement_details),
        )

    def _resolve_iteration(
        self,
        *,
        current_text: str,
        seed: int | None,
        rng: random.Random,
        base_index_by_source: dict[tuple[int | None, tuple[str, str]], int],
        tag_offset_by_key: dict[tuple[tuple[int | None, tuple[str, str]], str], int],
        text_sources: dict[str, PromptWildcardTextSource | None],
        csv_sources: dict[str, PromptWildcardCsvSource | None],
    ) -> tuple[_ResolvedPlaceholder, ...]:
        """Resolve placeholders visible in one substitution pass."""

        document = parse_prompt_document(
            current_text,
            wildcard_syntax_profile=self._syntax_profile,
        )
        resolved: list[_ResolvedPlaceholder] = []
        seen_outer_text: set[str] = set()
        for span in document.wildcard_spans:
            outer_text = current_text[span.outer_range.start : span.outer_range.end]
            if outer_text in seen_outer_text:
                continue
            seen_outer_text.add(outer_text)
            source_key = (span.wildcard_form.value, span.identifier)
            selection_key = (seed, source_key)
            if span.wildcard_form is WildcardForm.SIMPLE:
                text_source = self._text_source(span.identifier, text_sources)
                if text_source is None or not text_source.lines:
                    continue
                index = self._selected_index(
                    selection_key=selection_key,
                    source_id=text_source.source_id,
                    item_count=len(text_source.lines),
                    tag=span.tag,
                    seed=seed,
                    rng=rng,
                    base_index_by_source=base_index_by_source,
                    tag_offset_by_key=tag_offset_by_key,
                )
                resolved.append(
                    _ResolvedPlaceholder(
                        outer_text=outer_text,
                        value=text_source.lines[index],
                        wildcard_form=span.wildcard_form.value,
                        identifier=span.identifier,
                        source_id=text_source.source_id,
                        selected_index=index,
                        line_number=index + 1,
                        item_count=len(text_source.lines),
                        tag=span.tag,
                        csv_column=None,
                        seed=seed,
                    )
                )
                continue

            csv_source = self._csv_source(span.identifier, csv_sources)
            if csv_source is None or not csv_source.rows or span.csv_column is None:
                continue
            normalized_column = span.csv_column.strip().lower()
            index = self._selected_index(
                selection_key=selection_key,
                source_id=csv_source.source_id,
                item_count=len(csv_source.rows),
                tag=span.tag,
                seed=seed,
                rng=rng,
                base_index_by_source=base_index_by_source,
                tag_offset_by_key=tag_offset_by_key,
            )
            row = csv_source.rows[index]
            if normalized_column not in row:
                continue
            resolved.append(
                _ResolvedPlaceholder(
                    outer_text=outer_text,
                    value=row[normalized_column],
                    wildcard_form=span.wildcard_form.value,
                    identifier=span.identifier,
                    source_id=csv_source.source_id,
                    selected_index=index,
                    line_number=index + 2,
                    item_count=len(csv_source.rows),
                    tag=span.tag,
                    csv_column=span.csv_column,
                    seed=seed,
                )
            )
        return tuple(resolved)

    def _text_source(
        self,
        identifier: str,
        cache: dict[str, PromptWildcardTextSource | None],
    ) -> PromptWildcardTextSource | None:
        """Return cached simple wildcard source data."""

        if identifier not in cache:
            cache[identifier] = self._source_provider.load_text_source(identifier)
        return cache[identifier]

    def _csv_source(
        self,
        identifier: str,
        cache: dict[str, PromptWildcardCsvSource | None],
    ) -> PromptWildcardCsvSource | None:
        """Return cached CSV wildcard source data."""

        if identifier not in cache:
            cache[identifier] = self._source_provider.load_csv_source(identifier)
        return cache[identifier]

    @staticmethod
    def _selected_index(
        *,
        selection_key: tuple[int | None, tuple[str, str]],
        source_id: str,
        item_count: int,
        tag: str | None,
        seed: int | None,
        rng: random.Random,
        base_index_by_source: dict[tuple[int | None, tuple[str, str]], int],
        tag_offset_by_key: dict[tuple[tuple[int | None, tuple[str, str]], str], int],
    ) -> int:
        """Return the base or tag-offset index for one source."""

        if selection_key not in base_index_by_source:
            base_index_by_source[selection_key] = rng.randrange(item_count)
        index = base_index_by_source[selection_key]
        if tag is None:
            return index

        tag_key = (selection_key, tag)
        if tag_key not in tag_offset_by_key:
            if seed is not None:
                digest = hashlib.sha256(f"{seed}:{source_id}:{tag}".encode("utf-8"))
                tag_offset_by_key[tag_key] = int(digest.hexdigest(), 16) % item_count
            else:
                tag_offset_by_key[tag_key] = rng.randrange(item_count)
        return (index + tag_offset_by_key[tag_key]) % item_count


__all__ = [
    "PromptWildcardResolutionContext",
    "PromptWildcardResolver",
    "PromptWildcardSourceProvider",
]

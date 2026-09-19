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

"""Resolve shared ordinal region names and their exact prompt source edits."""

from __future__ import annotations

from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.application.prompt_editor.document.views import (
    PromptRegionSeparatorView,
)
from substitute.application.prompt_editor.editing.region_naming import (
    PromptRegionNamingService,
)
from substitute.application.workflows.regional_prompt_name_models import (
    RegionalPromptSourceReplacement,
)


class PromptRegionNameIdentityService:
    """Own name identity resolution within canonical prompt source strings."""

    def __init__(
        self,
        *,
        prompt_documents: PromptDocumentProjector | None = None,
        naming: PromptRegionNamingService | None = None,
    ) -> None:
        """Store the canonical prompt parser and SEP syntax owner."""

        self._prompt_documents = prompt_documents or PromptDocumentProjector()
        self._naming = naming or PromptRegionNamingService()

    def changed_names(
        self,
        previous_source_text: str,
        current_source_text: str,
    ) -> dict[int, str]:
        """Return ordinal name changes one source edit explicitly made."""

        previous = self._separators(previous_source_text)
        current = self._separators(current_source_text)
        changed: dict[int, str] = {}
        for index, separator in enumerate(current):
            current_name = _authored_name(separator)
            if index < len(previous):
                if _authored_name(previous[index]) != current_name:
                    changed[index] = current_name
            elif current_name:
                changed[index] = current_name
        return changed

    def first_authored_names(self, source_texts: tuple[str, ...]) -> dict[int, str]:
        """Choose the first non-empty name for each shared ordinal identity."""

        names: dict[int, str] = {}
        for source_text in source_texts:
            for index, separator in enumerate(self._separators(source_text)):
                authored_name = _authored_name(separator)
                if authored_name and index not in names:
                    names[index] = authored_name
        return names

    def apply_names(
        self,
        source_text: str,
        canonical_names: dict[int, str],
    ) -> tuple[str, tuple[RegionalPromptSourceReplacement, ...]]:
        """Apply available ordinal names without creating or removing separators."""

        separators = self._separators(source_text)
        prepared = tuple(
            RegionalPromptSourceReplacement(
                source_start=replacement.source_start,
                source_end=replacement.source_end,
                replacement_text=replacement.replacement_text,
            )
            for index, authored_name in canonical_names.items()
            if index < len(separators)
            and _authored_name(separators[index]) != authored_name
            for replacement in (
                self._naming.replacement_for(separators[index], authored_name),
            )
        )
        updated = source_text
        for replacement in sorted(
            prepared,
            key=lambda item: item.source_start,
            reverse=True,
        ):
            updated = (
                updated[: replacement.source_start]
                + replacement.replacement_text
                + updated[replacement.source_end :]
            )
        return updated, tuple(sorted(prepared, key=lambda item: item.source_start))

    def _separators(
        self,
        source_text: str,
    ) -> tuple[PromptRegionSeparatorView, ...]:
        """Return canonical structural separators for one prompt source."""

        return tuple(
            self._prompt_documents.build_document_view(
                source_text
            ).region_structure.separators
        )


def _authored_name(separator: PromptRegionSeparatorView) -> str:
    """Return the canonical authored identity represented by one separator."""

    return "" if separator.name is None else separator.name.strip()


__all__ = ["PromptRegionNameIdentityService"]

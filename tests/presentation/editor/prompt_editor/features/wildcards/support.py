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

"""Provide deterministic wildcard catalog doubles for presentation tests."""

from __future__ import annotations

from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.domain.prompt.features.models import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureProfileController,
    PromptWildcardDiagnosticsPresentation,
)


class WildcardGatewayDouble:
    """Record wildcard catalog calls for feature-controller assertions."""

    cache_revision = 7

    def __init__(self) -> None:
        """Initialize deterministic wildcard search and resolution rows."""

        self.search_calls: list[tuple[str, int]] = []
        self.fail_search = False

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return missing resolutions for all requested references."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=False,
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Record wildcard autocomplete searches and return one row."""

        self.search_calls.append((prefix, limit))
        if self.fail_search:
            raise RuntimeError("wildcard catalog unavailable")
        return (
            PromptAutocompleteSuggestion(
                tag=f"{prefix}animal",
                source_label="TXT wildcard",
                source_kind="wildcard",
            ),
        )


def wildcard_diagnostics_presentation(
    features: tuple[PromptEditorFeature, ...],
    *,
    gateway: WildcardGatewayDouble | None = None,
) -> PromptWildcardDiagnosticsPresentation:
    """Build a wildcard diagnostics owner with deterministic feature gates."""

    return PromptWildcardDiagnosticsPresentation(
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(features)
        ),
        wildcard_catalog_gateway=gateway or WildcardGatewayDouble(),
    )

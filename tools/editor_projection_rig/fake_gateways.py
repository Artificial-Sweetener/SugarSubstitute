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

"""Provide fixture-backed gateway stubs for hermetic editor projection replay."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

from substitute.domain.common import JsonObject
from substitute.application.ports.node_definition_gateway import (
    NodeDefinitionHydrationResult,
)
from substitute.application.ports.prompt_autocomplete_gateway import (
    PromptAutocompleteSuggestion,
)
from substitute.application.ports.prompt_wildcard_catalog_gateway import (
    PromptWildcardReference,
    PromptWildcardResolution,
)


class FixtureNodeDefinitionGateway:
    """Serve captured node definitions by Comfy class name."""

    def __init__(self, definitions: Mapping[str, Any]) -> None:
        """Store captured node definitions."""

        self._definitions = definitions

    def get_node_definition(self, node_class: str) -> JsonObject:
        """Return a captured node definition or an empty mapping."""

        value = self._definitions.get(node_class, {})
        if not isinstance(value, Mapping):
            return {}
        return cast(JsonObject, {node_class: dict(value)})

    def get_required_node_definition(self, node_class: str) -> JsonObject:
        """Return a required captured node definition."""

        return self.get_node_definition(node_class)

    def ensure_node_definitions(
        self,
        node_classes: Iterable[str],
    ) -> NodeDefinitionHydrationResult:
        """Report fixture-backed node definitions as foreground hydrated."""

        requested = tuple(str(node_class) for node_class in node_classes)
        available = tuple(
            node_class for node_class in requested if node_class in self._definitions
        )
        unavailable = tuple(
            node_class
            for node_class in requested
            if node_class not in self._definitions
        )
        return NodeDefinitionHydrationResult(
            requested=requested,
            available=available,
            unavailable=unavailable,
        )


class EmptyPromptAutocompleteGateway:
    """Provide deterministic empty prompt completions for hidden rig projection."""

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no suggestions while preserving the production gateway contract."""

        del prefix, limit
        return ()


class EmptyPromptWildcardCatalogGateway:
    """Provide deterministic empty wildcard metadata for hidden rig projection."""

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Return absent resolutions aligned with the supplied references."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                exists=False,
                csv_column=reference.csv_column,
            )
            for reference in references
        )

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return no wildcard suggestions."""

        del prefix, limit
        return ()

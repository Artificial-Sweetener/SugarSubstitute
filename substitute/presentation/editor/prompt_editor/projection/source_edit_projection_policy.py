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

"""Own source-edit projection deferral decisions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from substitute.presentation.editor.prompt_editor.core.projection.tokens import (
    PromptProjectionToken,
)

from .source_edit_syntax import SYNTAX_SENSITIVE_CHARACTERS

_WRAP_REFLOW_DEFERRABLE_REASONS = frozenset(
    (
        "plain_single_character",
        "plain_single_character_requires_layout",
        "plain_single_character_delete",
        "plain_single_character_delete_requires_layout",
        "syntax_sensitive_autocomplete_prefix",
    )
)


@dataclass(frozen=True, slots=True)
class PromptSourceEditProjectionDecision:
    """Describe whether one source edit may defer projection rebuild."""

    can_defer_projection: bool
    deferral_reason: str
    projection_topology_requires_rebuild: bool = False
    typed_character_requires_projection: bool = False
    syntax_sensitive_prefix_deferrable: bool = False
    insertion_inside_projected_token: bool = False
    deletion_intersects_projected_token: bool = False
    insertion_inside_text_content: bool = False

    @property
    def wrap_reflow_deferrable(self) -> bool:
        """Return whether this decision permits deferred wrap recovery."""

        return self.deferral_reason in _WRAP_REFLOW_DEFERRABLE_REASONS

    @property
    def requires_immediate_semantic_refresh(self) -> bool:
        """Return whether delayed semantics would expose stale token behavior."""

        return bool(
            (
                self.insertion_inside_projected_token
                and (
                    not self.insertion_inside_text_content
                    or self.typed_character_requires_projection
                )
            )
            or self.deletion_intersects_projected_token
            or self.deferral_reason == "region_structure_topology_changed"
        )

    @property
    def requires_semantic_refresh_before_boundary(self) -> bool:
        """Return whether a later boundary key must resolve this edit first."""

        return bool(
            self.requires_immediate_semantic_refresh
            or (
                self.insertion_inside_projected_token
                and not self.insertion_inside_text_content
            )
            or self.projection_topology_requires_rebuild
            or self.typed_character_requires_projection
            or self.syntax_sensitive_prefix_deferrable
        )


class PromptSourceEditProjectionPolicy:
    """Decide when source edits must rebuild projection immediately."""

    def decide(
        self,
        *,
        can_defer_projection: bool,
        deferral_reason: str,
        replacement_text: str,
        autocomplete_preview_active: bool,
        insertion_overlay_can_defer: bool,
        projection_topology_requires_rebuild: bool = False,
        typed_character_requires_projection: bool = False,
        syntax_sensitive_prefix_deferrable: bool = False,
        insertion_inside_projected_token: bool = False,
        deletion_intersects_projected_token: bool = False,
        insertion_inside_text_content: bool = False,
    ) -> PromptSourceEditProjectionDecision:
        """Return the projection deferral decision for one committed source edit."""

        if not can_defer_projection:
            return PromptSourceEditProjectionDecision(
                can_defer_projection=False,
                deferral_reason=deferral_reason,
                projection_topology_requires_rebuild=projection_topology_requires_rebuild,
                typed_character_requires_projection=typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable=syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token=insertion_inside_projected_token,
                deletion_intersects_projected_token=deletion_intersects_projected_token,
                insertion_inside_text_content=insertion_inside_text_content,
            )
        if autocomplete_preview_active:
            return PromptSourceEditProjectionDecision(
                can_defer_projection=False,
                deferral_reason="autocomplete_preview_active",
                projection_topology_requires_rebuild=projection_topology_requires_rebuild,
                typed_character_requires_projection=typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable=syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token=insertion_inside_projected_token,
                deletion_intersects_projected_token=deletion_intersects_projected_token,
                insertion_inside_text_content=insertion_inside_text_content,
            )
        if replacement_text == "":
            return PromptSourceEditProjectionDecision(
                can_defer_projection=False,
                deferral_reason="deletion_requires_immediate_projection",
                projection_topology_requires_rebuild=projection_topology_requires_rebuild,
                typed_character_requires_projection=typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable=syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token=insertion_inside_projected_token,
                deletion_intersects_projected_token=deletion_intersects_projected_token,
                insertion_inside_text_content=insertion_inside_text_content,
            )
        if any(character.isspace() for character in replacement_text):
            return PromptSourceEditProjectionDecision(
                can_defer_projection=False,
                deferral_reason="whitespace_requires_immediate_projection",
                projection_topology_requires_rebuild=projection_topology_requires_rebuild,
                typed_character_requires_projection=typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable=syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token=insertion_inside_projected_token,
                deletion_intersects_projected_token=deletion_intersects_projected_token,
                insertion_inside_text_content=insertion_inside_text_content,
            )
        if replacement_text and not insertion_overlay_can_defer:
            return PromptSourceEditProjectionDecision(
                can_defer_projection=False,
                deferral_reason=f"{deferral_reason}_requires_layout",
                projection_topology_requires_rebuild=projection_topology_requires_rebuild,
                typed_character_requires_projection=typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable=syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token=insertion_inside_projected_token,
                deletion_intersects_projected_token=deletion_intersects_projected_token,
                insertion_inside_text_content=insertion_inside_text_content,
            )
        return PromptSourceEditProjectionDecision(
            can_defer_projection=True,
            deferral_reason=deferral_reason,
            projection_topology_requires_rebuild=projection_topology_requires_rebuild,
            typed_character_requires_projection=typed_character_requires_projection,
            syntax_sensitive_prefix_deferrable=syntax_sensitive_prefix_deferrable,
            insertion_inside_projected_token=insertion_inside_projected_token,
            deletion_intersects_projected_token=deletion_intersects_projected_token,
            insertion_inside_text_content=insertion_inside_text_content,
        )

    @staticmethod
    def wrap_reflow_is_deferrable(deferral_reason: str) -> bool:
        """Return whether one established reason permits deferred wrap recovery."""

        return deferral_reason in _WRAP_REFLOW_DEFERRABLE_REASONS

    def typed_character_requires_projection(
        self,
        character: str,
        *,
        comma_requires_projection: bool,
    ) -> bool:
        """Return whether one typed character changes immediate projection semantics."""

        if character == ",":
            return comma_requires_projection
        return character in SYNTAX_SENSITIVE_CHARACTERS

    def source_range_intersects_tokens(
        self,
        *,
        start: int,
        end: int,
        tokens: Sequence[PromptProjectionToken],
    ) -> bool:
        """Return whether one source range touches projected token syntax."""

        return end > start and any(
            start < token.source_end and token.source_start < end for token in tokens
        )

    def source_insertion_is_inside_token(
        self,
        *,
        source_position: int,
        tokens: Sequence[PromptProjectionToken],
    ) -> bool:
        """Return whether one insertion sits inside projected token syntax."""

        return any(
            token.source_start < source_position < token.source_end for token in tokens
        )

    def source_insertion_is_inside_text_content(
        self,
        *,
        source_position: int,
        tokens: Sequence[PromptProjectionToken],
    ) -> bool:
        """Return whether insertion sits inside one token's editable text span."""

        return any(
            token.supports_text_content_navigation
            and token.content_start is not None
            and token.content_end is not None
            and token.content_start <= source_position <= token.content_end
            for token in tokens
        )


__all__ = [
    "PromptSourceEditProjectionDecision",
    "PromptSourceEditProjectionPolicy",
]

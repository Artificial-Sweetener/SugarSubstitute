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

    @property
    def wrap_reflow_deferrable(self) -> bool:
        """Return whether this decision permits deferred wrap recovery."""

        return self.deferral_reason in _WRAP_REFLOW_DEFERRABLE_REASONS


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
    ) -> PromptSourceEditProjectionDecision:
        """Return the projection deferral decision for one committed source edit."""

        if not can_defer_projection:
            return PromptSourceEditProjectionDecision(
                False,
                deferral_reason,
                projection_topology_requires_rebuild,
                typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token,
                deletion_intersects_projected_token,
            )
        if autocomplete_preview_active:
            return PromptSourceEditProjectionDecision(
                False,
                "autocomplete_preview_active",
                projection_topology_requires_rebuild,
                typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token,
                deletion_intersects_projected_token,
            )
        if replacement_text == "":
            return PromptSourceEditProjectionDecision(
                False,
                "deletion_requires_immediate_projection",
                projection_topology_requires_rebuild,
                typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token,
                deletion_intersects_projected_token,
            )
        if any(character.isspace() for character in replacement_text):
            return PromptSourceEditProjectionDecision(
                False,
                "whitespace_requires_immediate_projection",
                projection_topology_requires_rebuild,
                typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token,
                deletion_intersects_projected_token,
            )
        if replacement_text and not insertion_overlay_can_defer:
            return PromptSourceEditProjectionDecision(
                False,
                f"{deferral_reason}_requires_layout",
                projection_topology_requires_rebuild,
                typed_character_requires_projection,
                syntax_sensitive_prefix_deferrable,
                insertion_inside_projected_token,
                deletion_intersects_projected_token,
            )
        return PromptSourceEditProjectionDecision(
            True,
            deferral_reason,
            projection_topology_requires_rebuild,
            typed_character_requires_projection,
            syntax_sensitive_prefix_deferrable,
            insertion_inside_projected_token,
            deletion_intersects_projected_token,
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

        return any(
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


__all__ = [
    "PromptSourceEditProjectionDecision",
    "PromptSourceEditProjectionPolicy",
]

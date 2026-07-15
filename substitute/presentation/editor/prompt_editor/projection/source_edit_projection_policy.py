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

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PromptSourceEditProjectionDecision:
    """Describe whether one source edit may defer projection rebuild."""

    can_defer_projection: bool
    deferral_reason: str


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
    ) -> PromptSourceEditProjectionDecision:
        """Return the projection deferral decision for one committed source edit."""

        if not can_defer_projection:
            return PromptSourceEditProjectionDecision(False, deferral_reason)
        if autocomplete_preview_active:
            return PromptSourceEditProjectionDecision(
                False,
                "autocomplete_preview_active",
            )
        if replacement_text == "":
            return PromptSourceEditProjectionDecision(
                False,
                "deletion_requires_immediate_projection",
            )
        if any(character.isspace() for character in replacement_text):
            return PromptSourceEditProjectionDecision(
                False,
                "whitespace_requires_immediate_projection",
            )
        if replacement_text and not insertion_overlay_can_defer:
            return PromptSourceEditProjectionDecision(
                False,
                f"{deferral_reason}_requires_layout",
            )
        return PromptSourceEditProjectionDecision(True, deferral_reason)


__all__ = [
    "PromptSourceEditProjectionDecision",
    "PromptSourceEditProjectionPolicy",
]

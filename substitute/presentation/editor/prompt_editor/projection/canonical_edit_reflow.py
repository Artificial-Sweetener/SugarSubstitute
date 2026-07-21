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

"""Build canonical projection documents eligible for bounded source-edit reflow."""

from __future__ import annotations

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)

from .applicator import PromptProjectionApplicator
from .freshness_controller import PromptProjectionFreshnessBlockers
from .model import PromptProjectionDisplayMode, PromptProjectionDocument
from .session import PromptProjectionSession


class PromptProjectionCanonicalEditReflow:
    """Own safe canonical-document preparation for one local source edit."""

    def __init__(self, applicator: PromptProjectionApplicator) -> None:
        """Store the canonical projection owner used for bounded reflow."""

        self._applicator = applicator

    def try_build_document(
        self,
        *,
        previous_document: PromptProjectionDocument,
        previous_source_text: str,
        document_view: PromptDocumentView,
        render_plan: PromptSyntaxRenderPlan,
        start: int,
        end: int,
        replacement_text: str,
        blockers: PromptProjectionFreshnessBlockers,
        session: PromptProjectionSession,
        decoration_accent_ranges: tuple[tuple[int, int], ...],
        scene_error_keys: frozenset[str],
    ) -> PromptProjectionDocument | None:
        """Build canonical state when a local edit can reuse surrounding layout."""

        next_source_text = document_view.source_text
        if (
            blockers.display_mode is not PromptProjectionDisplayMode.PROJECTED
            or blockers.reorder_preview_active
            or blockers.autocomplete_preview_active
            or blockers.exact_weight_edit_active
            or blockers.expanded_source_range_active
            or previous_document.source_text != previous_source_text
            or not 0 <= start <= end <= len(previous_source_text)
            or previous_source_text[:start]
            + replacement_text
            + previous_source_text[end:]
            != next_source_text
            or self._applicator.source_edit_requires_canonical_rebuild(
                previous_source_text,
                next_source_text,
                start=start,
                end=end,
            )
        ):
            return None
        return self._applicator.build_projection(
            document_view,
            render_plan,
            display_mode=blockers.display_mode,
            session=session,
            active_span_range=None,
            decoration_accent_ranges=decoration_accent_ranges,
            scene_error_keys=scene_error_keys,
        )


__all__ = ["PromptProjectionCanonicalEditReflow"]

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

"""Tests for prompt reorder preview projection cache behavior."""

from __future__ import annotations

from typing import Any, cast

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxService,
)
from substitute.presentation.editor.prompt_editor.projection.reorder_preview_projection import (
    PromptReorderPreviewProjectionProvider,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_reorder_interaction_test_helpers import syntax_service


class CountingSyntaxService:
    """Count render-plan builds while delegating to the real syntax service."""

    def __init__(self) -> None:
        """Initialize the delegate syntax service and call counter."""

        self._delegate = syntax_service()
        self.build_render_plan_calls = 0

    def build_render_plan(self, document_view: Any, syntax_profile: Any) -> Any:
        """Record and delegate one render-plan request."""

        self.build_render_plan_calls += 1
        return self._delegate.build_render_plan(document_view, syntax_profile)


def test_reorder_projection_snapshot_cache_reuses_render_plan_for_same_layout() -> None:
    """Repeated reorder projection builds reuse cached syntax render plans."""

    document_service = PromptDocumentService()
    counting_syntax_service = CountingSyntaxService()
    provider = PromptReorderPreviewProjectionProvider(
        document_service=document_service,
        syntax_service=cast(PromptSyntaxService, counting_syntax_service),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
    document_view = document_service.build_document_view("alpha, beta")
    initial_render_plan_calls = counting_syntax_service.build_render_plan_calls
    layout_view = document_service.build_reorder_layout_view(document_view)

    first_result = provider.build_projection_snapshot(
        document_view=document_view,
        layout_view=layout_view,
        cache_namespace="preview",
        source_revision=1,
        viewport_width=480,
        scroll_position=0,
        layout_key=(("layout", 1),),
        active_drop_target_identity=("line", 0, 0),
        gesture_id=None,
        event_id=None,
        reason="test",
    )
    second_result = provider.build_projection_snapshot(
        document_view=document_view,
        layout_view=layout_view,
        cache_namespace="preview",
        source_revision=1,
        viewport_width=480,
        scroll_position=0,
        layout_key=(("layout", 1),),
        active_drop_target_identity=("line", 0, 0),
        gesture_id=None,
        event_id=None,
        reason="test",
    )

    assert first_result is not None
    assert second_result is not None
    assert first_result.projection_snapshot is second_result.projection_snapshot
    assert counting_syntax_service.build_render_plan_calls == (
        initial_render_plan_calls + 1
    )


def test_reorder_projection_snapshot_cache_separates_target_identity() -> None:
    """Projection preview snapshot cache separates display target identities."""

    document_service = PromptDocumentService()
    counting_syntax_service = CountingSyntaxService()
    provider = PromptReorderPreviewProjectionProvider(
        document_service=document_service,
        syntax_service=cast(PromptSyntaxService, counting_syntax_service),
        syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
    )
    document_view = document_service.build_document_view("alpha, beta")
    layout_view = document_service.build_reorder_layout_view(document_view)

    first_result = provider.build_projection_snapshot(
        document_view=document_view,
        layout_view=layout_view,
        cache_namespace="preview",
        source_revision=1,
        viewport_width=480,
        scroll_position=0,
        layout_key=(("layout", 1),),
        active_drop_target_identity=("line", 0, 0),
        gesture_id=None,
        event_id=None,
        reason="test",
    )
    second_result = provider.build_projection_snapshot(
        document_view=document_view,
        layout_view=layout_view,
        cache_namespace="preview",
        source_revision=1,
        viewport_width=480,
        scroll_position=0,
        layout_key=(("layout", 1),),
        active_drop_target_identity=("line", 0, 1),
        gesture_id=None,
        event_id=None,
        reason="test",
    )

    assert first_result is not None
    assert second_result is not None
    assert first_result.projection_snapshot is not second_result.projection_snapshot
    assert counting_syntax_service.build_render_plan_calls == 2

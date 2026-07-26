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

"""Verify stale-safe fallback policy through the deferred-feedback owner."""

from __future__ import annotations

import os
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.core.projection.caret import (
    PromptProjectionCaretState,
)
from substitute.presentation.editor.prompt_editor.projection.deferred_feedback_strategy import (
    PromptDeferredFeedbackContext,
    PromptDeferredFeedbackStrategy,
)
from substitute.presentation.editor.prompt_editor.projection.edit_pipeline_contracts import (
    PromptProjectionSourceChangeApplyRequest,
)
from substitute.presentation.editor.prompt_editor.projection.edit_strategy import (
    PromptSourceEditKind,
)
from substitute.presentation.editor.prompt_editor.projection.source_edit_projection_policy import (
    PromptSourceEditProjectionDecision,
)
from tests.prompt_projection_surface_test_helpers import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)
from tests.prompt_projection_test_helpers import show_prompt_editor, surface_for

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _strategy(surface: object) -> PromptDeferredFeedbackStrategy:
    """Compose the focused owner from production surface collaborators."""

    host = cast(Any, surface)
    return PromptDeferredFeedbackStrategy(
        cast(PromptDeferredFeedbackContext, surface),
        editor_state=host._editor_state,
        freshness=host._projection_freshness_controller,
        layout=host._layout,
        overlays=host._transient_edit_overlays,
        source_line_chrome=host._source_line_chrome,
    )


def _request(
    surface: object,
    *,
    next_text: str,
    start: int,
    replacement_text: str,
    deferral_reason: str,
    insertion_inside_token: bool = False,
) -> PromptProjectionSourceChangeApplyRequest:
    """Return one typed fallback request with already-resolved edit facts."""

    host = cast(Any, surface)
    previous_text = host._editor_state.projection.document.source_text
    semantic = host._editor_state.edit_semantic
    caret_state = PromptProjectionCaretState(
        source_position=start + len(replacement_text)
    )
    return PromptProjectionSourceChangeApplyRequest(
        text=next_text,
        previous_source_text=previous_text,
        previous_source_identity=host._editor_state.source_identity,
        source_edit_start=start,
        source_edit_end=start,
        source_edit_replacement_text=replacement_text,
        previous_projection_freshness=host._projection_freshness_controller.freshness,
        previous_document_view=semantic.document,
        previous_render_plan=semantic.render_plan,
        next_document_view=semantic.document,
        next_render_plan=semantic.render_plan,
        previous_deletion_overlay=None,
        next_cursor_state=caret_state,
        next_anchor_state=caret_state,
        can_preserve_diagnostic_fragment_cache=True,
        projection_deferral_reason=deferral_reason,
        region_structure_requires_rebuild=False,
        edit_kind=PromptSourceEditKind.PLAIN_REPLACEMENT,
        deferred_plain_edit_extendable=False,
        wrap_reflow_deferrable=True,
        projection_decision=PromptSourceEditProjectionDecision(
            can_defer_projection=False,
            deferral_reason=deferral_reason,
            insertion_inside_projected_token=insertion_inside_token,
        ),
    )


def test_deferred_feedback_allows_plain_trailing_layout_miss(
    widgets: list[QWidget],
) -> None:
    """Allow one end insertion that fits committed transient geometry."""

    box = show_prompt_editor(widgets, text="(cat:1.05), alpha beta", width=360)
    surface = surface_for(box)
    text = box.toPlainText()
    request = _request(
        surface,
        next_text=f"{text}x",
        start=len(text),
        replacement_text="x",
        deferral_reason="plain_single_character_requires_layout",
    )

    assert _strategy(surface).can_defer_fallback(request)


def test_deferred_feedback_rejects_token_interior_or_control_edit(
    widgets: list[QWidget],
) -> None:
    """Reject fallback when token ownership or control syntax needs real geometry."""

    box = show_prompt_editor(widgets, text="(cat:1.05), alpha beta", width=360)
    surface = surface_for(box)
    text = box.toPlainText()
    token_position = text.index("cat") + 1
    token_request = _request(
        surface,
        next_text=f"{text[:token_position]}x{text[token_position:]}",
        start=token_position,
        replacement_text="x",
        deferral_reason="plain_single_character_requires_layout",
        insertion_inside_token=True,
    )
    middle_position = text.index(" beta")
    newline_request = _request(
        surface,
        next_text=f"{text[:middle_position]}\n{text[middle_position:]}",
        start=middle_position,
        replacement_text="\n",
        deferral_reason="control_character",
    )

    strategy = _strategy(surface)
    assert not strategy.can_defer_fallback(token_request)
    assert not strategy.can_defer_fallback(newline_request)

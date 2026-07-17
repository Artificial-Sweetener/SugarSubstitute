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

"""Tests for prompt projection emphasis surface behavior."""

from __future__ import annotations

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptDocumentView,
    PromptSyntaxRenderPlan,
    PromptSyntaxService,
)
from tests.prompt_autocomplete_test_helpers import prompt_syntax_profile
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
    process_events,
    projection_paint_state_for,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    first_emphasis_token,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    surface_router,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _prompt_state_for_projection_text(
    text: str,
) -> tuple[PromptDocumentView, PromptSyntaxRenderPlan]:
    """Build one semantic prompt state for emphasis surface tests."""

    document_view = PromptDocumentService().build_document_view(text)
    render_plan = PromptSyntaxService(
        StaticPromptWildcardCatalogGateway({})
    ).build_render_plan(
        document_view,
        prompt_syntax_profile("emphasis", "wildcard", "lora"),
    )
    return document_view, render_plan


def test_projection_surface_double_click_on_emphasis_selects_content_without_expansion(
    widgets: list[QWidget],
) -> None:
    """Double-clicking emphasis content should select the inner text and keep projection active."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    token = first_emphasis_token(box)
    assert token.content_start is not None
    assert token.content_end is not None
    token_rect = surface_for(box)._layout.token_rect(token, scroll_offset=0.0)  # noqa: SLF001
    weight_rect = surface_for(box).token_weight_text_rect(token)
    assert token_rect is not None
    assert weight_rect is not None
    word_point = token_rect.center().toPoint()
    word_point.setX(int((token_rect.left() + weight_rect.left()) / 2.0))

    QTest.mouseDClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=word_point,
    )
    process_events(app)

    cursor = box.textCursor()
    assert surface_for(box).projection_document().tokens != ()
    assert cursor.selectionStart() == token.content_start
    assert cursor.selectionEnd() == token.content_end


def test_projection_surface_segment_double_click_preserves_prompt_focus(
    widgets: list[QWidget],
) -> None:
    """Keep the prompt surface focused after double-clicking a plain segment."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="alpha, blue green, gamma",
        width=240,
    )
    segment_text = "blue green"
    segment_start = box.toPlainText().index(segment_text)
    click_point = box.cursorRect().center()
    cursor = box.textCursor()
    cursor.setPosition(segment_start + 1)
    box.setTextCursor(cursor)
    process_events(app)
    click_point = box.cursorRect().center()

    surface = surface_for(box)
    assert app.focusWidget() is surface
    assert box.hasFocus() is True
    assert surface.hasFocus() is True

    QTest.mouseDClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=click_point,
    )
    process_events(app)

    selected_cursor = box.textCursor()
    assert selected_cursor.selectionStart() == segment_start
    assert selected_cursor.selectionEnd() == segment_start + len(segment_text)
    assert app.focusWidget() is surface
    assert box.hasFocus() is True
    assert surface.hasFocus() is True


def test_projection_surface_replaces_double_clicked_emphasis_content_without_expansion(
    widgets: list[QWidget],
) -> None:
    """Replacing double-clicked emphasis content should keep the token collapsed."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    token = first_emphasis_token(box)
    assert token.content_start is not None
    assert token.content_end is not None
    token_rect = surface_for(box)._layout.token_rect(token, scroll_offset=0.0)  # noqa: SLF001
    weight_rect = surface_for(box).token_weight_text_rect(token)
    assert token_rect is not None
    assert weight_rect is not None
    word_point = token_rect.center().toPoint()
    word_point.setX(int((token_rect.left() + weight_rect.left()) / 2.0))

    QTest.mouseDClick(
        box.viewport(),
        Qt.MouseButton.LeftButton,
        pos=word_point,
    )
    process_events(app)
    QTest.keyClicks(box, "dog")
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    next_token = first_emphasis_token(box)
    assert box.toPlainText() == "(dog:1.05), suffix"
    assert next_token.display_text == "dog"
    assert next_token.value_text == "1.05"


def test_projection_surface_pulses_emphasis_feedback_without_rebuild(
    widgets: list[QWidget],
) -> None:
    """Emphasis feedback should repaint decoration state without rebuilding layout."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    surface = surface_for(box)
    token = first_emphasis_token(box)
    rebuild_calls: list[str] = []
    cast(Any, surface)._rebuild_projection = lambda: rebuild_calls.append("rebuild")

    surface.pulse_emphasis_feedback(
        outer_start=token.source_start,
        outer_end=token.source_end,
    )

    assert rebuild_calls == []
    assert projection_paint_state_for(box).is_token_decoration_accented(token.token_id)


def test_projection_surface_rebuilds_for_changed_emphasis_prompt_state(
    widgets: list[QWidget],
) -> None:
    """Changed emphasis source should rebuild even when its width stays stable."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    surface = surface_for(box)
    document_view, render_plan = _prompt_state_for_projection_text("(cat:1.10), suffix")
    rebuild_calls: list[str] = []
    original_rebuild_projection = surface._rebuild_projection  # noqa: SLF001

    def record_rebuild() -> None:
        """Record and perform the authoritative projection rebuild."""

        rebuild_calls.append("rebuild")
        original_rebuild_projection()

    cast(Any, surface)._rebuild_projection = record_rebuild

    surface_router(surface).replace_document_text_with_prompt_state(
        "(cat:1.10), suffix",
        document_view=document_view,
        render_plan=render_plan,
    )

    token = first_emphasis_token(box)
    assert rebuild_calls == ["rebuild"]
    assert surface.toPlainText() == "(cat:1.10), suffix"
    assert token.value_text == "1.10"


def test_projection_surface_rebuilds_when_emphasis_prompt_state_changes_geometry(
    widgets: list[QWidget],
) -> None:
    """Geometry-changing emphasis replacements should keep the full rebuild fallback."""

    box = show_prompt_editor(
        widgets,
        text="(cat:9.95), suffix",
        width=240,
    )
    surface = surface_for(box)
    document_view, render_plan = _prompt_state_for_projection_text(
        "(cat:10.00), suffix"
    )
    rebuild_calls: list[str] = []
    cast(Any, surface)._rebuild_projection = lambda: rebuild_calls.append("rebuild")

    surface_router(surface).replace_document_text_with_prompt_state(
        "(cat:10.00), suffix",
        document_view=document_view,
        render_plan=render_plan,
    )

    assert rebuild_calls == ["rebuild"]


def test_projection_surface_can_project_and_clear_transient_neutral_emphasis(
    widgets: list[QWidget],
) -> None:
    """The surface should project a temporary neutral shell without changing source text."""

    box = show_prompt_editor(
        widgets,
        text="cat, dog",
        width=220,
    )
    surface = surface_for(box)

    surface.show_transient_neutral_emphasis(content_start=0, content_end=3)

    token = first_emphasis_token(box)
    assert box.toPlainText() == "cat, dog"
    assert token.synthetic is True
    assert token.value_text == "1.00"

    surface.clear_transient_neutral_emphasis()

    assert surface.projection_document().tokens == ()


def test_projection_surface_exposes_exact_weight_text_rect_separately_from_arrow_anchor(
    widgets: list[QWidget],
) -> None:
    """The surface should expose the painted number bounds separately from the stable arrow slot."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    surface = surface_for(box)
    token = first_emphasis_token(box)

    weight_rect = surface.token_weight_text_rect(token)
    anchor_rect = surface.token_anchor_rect(token)

    assert weight_rect is not None
    assert anchor_rect is not None
    assert weight_rect.left() == pytest.approx(anchor_rect.left())
    assert weight_rect.top() == pytest.approx(anchor_rect.top())
    assert weight_rect.height() == pytest.approx(anchor_rect.height())
    assert weight_rect.width() <= anchor_rect.width()


def test_projection_surface_projects_exact_weight_edit_state_into_the_live_token(
    widgets: list[QWidget],
) -> None:
    """The surface should rebuild the active emphasis token with projection-owned edit metadata."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    surface = surface_for(box)
    token = first_emphasis_token(box)
    baseline_weight_rect = surface.token_weight_text_rect(token)
    assert baseline_weight_rect is not None

    surface.start_exact_weight_edit(token)
    surface.update_exact_weight_edit(
        buffer_text="1.20",
        caret_index=2,
        select_all=False,
    )

    exact_edit_token = surface.exact_weight_edit_token()
    assert exact_edit_token is not None
    assert exact_edit_token.editing_value_text == "1.20"
    assert exact_edit_token.editing_slot_width == pytest.approx(
        baseline_weight_rect.width()
    )
    assert exact_edit_token.editing_caret_index == 2
    assert exact_edit_token.editing_select_all is False


def test_projection_surface_exact_weight_rect_tracks_edit_buffer_width_without_moving_arrow_anchor(
    widgets: list[QWidget],
) -> None:
    """The painted number slot should widen for longer edit buffers without moving left alignment."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    surface = surface_for(box)
    token = first_emphasis_token(box)
    baseline_weight_rect = surface.token_weight_text_rect(token)
    baseline_anchor_rect = surface.token_anchor_rect(token)
    assert baseline_weight_rect is not None
    assert baseline_anchor_rect is not None

    surface.start_exact_weight_edit(token)
    surface.update_exact_weight_edit(
        buffer_text="1.234",
        caret_index=5,
        select_all=False,
    )

    exact_edit_token = surface.exact_weight_edit_token()
    assert exact_edit_token is not None
    updated_weight_rect = surface.token_weight_text_rect(exact_edit_token)
    updated_anchor_rect = surface.token_anchor_rect(exact_edit_token)

    assert updated_weight_rect is not None
    assert updated_anchor_rect is not None
    assert updated_weight_rect.width() > baseline_weight_rect.width()
    assert updated_weight_rect.left() == pytest.approx(baseline_weight_rect.left())
    assert updated_anchor_rect.left() == pytest.approx(baseline_anchor_rect.left())
    assert updated_anchor_rect.top() == pytest.approx(baseline_anchor_rect.top())
    assert updated_anchor_rect.height() == pytest.approx(baseline_anchor_rect.height())
    assert updated_anchor_rect.width() >= baseline_anchor_rect.width()


def test_projection_surface_exact_weight_rect_does_not_shrink_below_entry_width(
    widgets: list[QWidget],
) -> None:
    """Exact edit should keep the number slot at least as wide as it was on entry."""

    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=180,
    )
    surface = surface_for(box)
    token = first_emphasis_token(box)
    baseline_weight_rect = surface.token_weight_text_rect(token)
    baseline_anchor_rect = surface.token_anchor_rect(token)
    assert baseline_weight_rect is not None
    assert baseline_anchor_rect is not None

    surface.start_exact_weight_edit(token)
    surface.update_exact_weight_edit(
        buffer_text="",
        caret_index=0,
        select_all=False,
    )

    exact_edit_token = surface.exact_weight_edit_token()
    assert exact_edit_token is not None
    updated_weight_rect = surface.token_weight_text_rect(exact_edit_token)
    updated_anchor_rect = surface.token_anchor_rect(exact_edit_token)

    assert updated_weight_rect is not None
    assert updated_anchor_rect is not None
    assert updated_weight_rect.width() == pytest.approx(baseline_weight_rect.width())
    assert updated_weight_rect.left() == pytest.approx(baseline_weight_rect.left())
    assert updated_anchor_rect.width() >= baseline_anchor_rect.width()
    assert updated_anchor_rect.left() == pytest.approx(baseline_anchor_rect.left())

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

"""Tests for prompt projection surface lifecycle and host integration behavior."""

from __future__ import annotations

import os
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import (
    PromptDocumentView,
    PromptSyntaxRenderPlan,
)
from substitute.presentation.editor.prompt_editor.projection import (
    prompt_state_applier as prompt_state_applier_module,
)
from substitute.presentation.editor.prompt_editor.projection import (
    surface as prompt_surface_module,
)
from substitute.presentation.editor.prompt_editor.projection.paint_state import (
    PromptProjectionPaintStateBuilder,
)
from substitute.presentation.editor.prompt_editor.projection.update_scheduler import (
    PendingProjectionUpdate,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)
from tests.prompt_projection_surface_test_helpers import (
    first_emphasis_token,
    new_projection_surface,
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_projection_surface_active_span_reuses_existing_caret_map(
    widgets: list[QWidget],
) -> None:
    """Paint-only active-token retagging should not rebuild caret indexes."""

    ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=220,
    )
    surface = surface_for(box)
    document = surface.projection_document()
    token = first_emphasis_token(box)

    paint_state = PromptProjectionPaintStateBuilder().build(
        document,
        session=surface._session,  # noqa: SLF001
        active_span_range=(token.source_start, token.source_end),
        decoration_accent_ranges=(),
        scene_error_keys=frozenset(),
    )
    surface._layout.set_projection_paint_state(paint_state)  # noqa: SLF001
    active_token = surface._layout.effective_token_for_paint(  # noqa: SLF001
        token.token_id
    )

    assert surface._layout.projection_document is document  # noqa: SLF001
    assert surface._layout.projection_document.caret_map is document.caret_map  # noqa: SLF001
    assert active_token is not None
    assert active_token.active is True
    active_runs = tuple(
        surface._layout.effective_run_for_paint(run.run_id)  # noqa: SLF001
        for run in document.runs
        if run.token_id == token.token_id
    )
    assert any(run is not None and run.active for run in active_runs)


def test_projection_surface_caret_sync_ignores_deleted_qt_wrappers(
    monkeypatch: pytest.MonkeyPatch,
    widgets: list[QWidget],
) -> None:
    """Queued caret blink work should no-op after the surface C++ object is gone."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    surface_view = cast(Any, surface)
    surface_view._caret_visual_controller.blink_enabled = True
    surface_view._caret_visual_controller.blink_visible = True
    monkeypatch.setattr(
        surface_view._caret_visual_controller,
        "_is_alive",
        lambda _obj: False,
    )

    surface_view._sync_caret_blink_state(reset_cycle=True)
    surface_view._toggle_caret_blink_visibility()

    assert surface_view._caret_can_paint() is False
    assert surface_view._caret_visual_controller.blink_enabled is True
    assert surface_view._caret_visual_controller.blink_visible is True


def test_projection_surface_prompt_state_ignores_deleted_qt_wrappers(
    monkeypatch: pytest.MonkeyPatch,
    widgets: list[QWidget],
) -> None:
    """Queued semantic refreshes should no-op after the surface C++ object is gone."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    document_view = PromptDocumentView(
        source_text="alpha",
        segments=(),
        emphasis_spans=(),
        wildcard_spans=(),
        lora_spans=(),
        syntax_spans=(),
        has_trailing_comma=False,
    )
    render_plan = PromptSyntaxRenderPlan(syntax_spans=(), renderer_views=())
    surface_view = cast(Any, surface)
    monkeypatch.setattr(prompt_surface_module, "qt_object_is_alive", lambda _obj: False)
    monkeypatch.setattr(
        prompt_state_applier_module, "qt_object_is_alive", lambda _obj: False
    )

    surface.set_prompt_state(document_view, render_plan)
    surface_view._prompt_state_applier.apply_prompt_state_projection(
        document_view, render_plan
    )
    surface_view._prompt_state_applier.apply_scheduled_projection_update(
        PendingProjectionUpdate.create(
            document_view=document_view,
            render_plan=render_plan,
            reason="test",
            source_revision=0,
        )
    )
    surface_view._rebuild_projection()

    assert surface_view._document_view.source_text == ""


def test_projection_surface_inherits_qfluent_font_and_document_margin_from_host(
    widgets: list[QWidget],
) -> None:
    """The projection surface should render with the live QFluent shell font metrics."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=220,
    )
    surface = surface_for(box)

    assert surface.font().families() == box.font().families()
    assert surface.font().pixelSize() == box.font().pixelSize()
    assert surface.document().documentMargin() == 4.0


def test_projection_surface_ignores_unknown_control_text_shortcuts(
    widgets: list[QWidget],
) -> None:
    """Ctrl-modified text keys should not insert Qt control characters."""

    box = show_prompt_editor(
        widgets,
        text="alpha",
        width=220,
    )
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_F,
        Qt.KeyboardModifier.ControlModifier,
        "\x06",
    )

    box.keyPressEvent(event)
    process_events(ensure_qapp())

    assert box.toPlainText() == "alpha"
    assert event.isAccepted() is False

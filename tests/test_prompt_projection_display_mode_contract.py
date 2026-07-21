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

"""Contract tests for source-faithful raw/projected prompt display mode toggling."""

from __future__ import annotations

import os
from collections.abc import Iterator
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.projection.model import (
    OBJECT_REPLACEMENT_CHARACTER,
    PromptProjectionDisplayMode,
    PromptProjectionTokenKind,
)
from tests.prompt_projection_test_helpers import (
    emphasis_controls_for,
    ensure_qapp,
    process_events,
    show_prompt_editor,
    surface_for,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "projection display mode tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created during one display-mode contract test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def _select_range(box: PromptEditor, start: int, end: int) -> None:
    """Apply one raw source selection to the live prompt editor."""

    cursor = box.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)


def _reveal_first_emphasis_controls(box: PromptEditor) -> None:
    """Move the pointer over the first projected emphasis weight control."""

    app = ensure_qapp()
    token = next(
        token
        for token in surface_for(box).projection_document().tokens
        if token.kind is PromptProjectionTokenKind.EMPHASIS
    )
    anchor_rect = surface_for(box).token_anchor_rect(token)
    assert anchor_rect is not None
    QTest.mouseMove(
        box.viewport(),
        QPoint(max(1, box.viewport().width() - 3), max(1, box.viewport().height() - 3)),
    )
    process_events(app, cycles=3)
    QTest.mouseMove(box.viewport(), anchor_rect.center().toPoint())
    process_events(app, cycles=6)
    controls = emphasis_controls_for(box)
    controls._set_pointer_from_viewport(anchor_rect.center())  # noqa: SLF001
    controls.refresh_geometry()
    process_events(app, cycles=6)


def test_prompt_editor_display_mode_toggle_preserves_source_text_and_selection(
    widgets: list[QWidget],
) -> None:
    """Toggling projected and raw mode should preserve source text and source selection."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    _select_range(box, 1, 4)
    process_events(app)

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(app)
    assert box.displayMode() is PromptProjectionDisplayMode.RAW
    assert box.toPlainText() == "(cat:1.05), suffix"
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 4

    box.setDisplayMode(PromptProjectionDisplayMode.PROJECTED)
    process_events(app)
    assert box.displayMode() is PromptProjectionDisplayMode.PROJECTED
    assert box.toPlainText() == "(cat:1.05), suffix"
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 4


def test_prompt_editor_reuses_exact_mode_layouts_until_prompt_state_changes(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated raw/rich toggles should rebuild once per canonical state."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    surface = surface_for(box)
    rebuild_projection = Mock(wraps=surface._projection_applicator.rebuild_projection)
    monkeypatch.setattr(
        surface._projection_applicator,
        "rebuild_projection",
        rebuild_projection,
    )

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    box.setDisplayMode(PromptProjectionDisplayMode.PROJECTED)
    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(app)

    assert rebuild_projection.call_count == 1
    assert surface.projection_document().projection_text == "(cat:1.05), suffix"

    QTest.keyClicks(box, "x")
    box.setDisplayMode(PromptProjectionDisplayMode.PROJECTED)
    process_events(app)

    assert rebuild_projection.call_count == 2
    assert box.toPlainText() == "(cat:1.05), suffixx"


def test_prompt_editor_raw_toggle_does_not_leave_cleared_transient_projection(
    widgets: list[QWidget],
) -> None:
    """Mode switching should restore canonical geometry after caret-driven collapse."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05), suffix",
        width=240,
    )
    surface = surface_for(box)

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(app)

    assert surface._active_projection_requires_layout() is False
    assert surface.active_projection_document() is surface.projection_document()
    assert surface._layout.projection_document is surface.projection_document()


def test_prompt_editor_rich_rendering_defaults_to_projected_mode(
    widgets: list[QWidget],
) -> None:
    """Prompt editors should default to rich rendering over exact source text."""

    box = show_prompt_editor(
        widgets,
        text=r"painting \(medium\)",
        width=220,
    )
    surface = surface_for(box)

    assert box.richPromptRenderingEnabled() is True
    assert box.displayMode() is PromptProjectionDisplayMode.PROJECTED
    assert box.toPlainText() == r"painting \(medium\)"
    assert surface.projection_document().projection_text == "painting (medium)"


def test_prompt_editor_rich_rendering_toggle_switches_to_raw_source_mode(
    widgets: list[QWidget],
) -> None:
    """Disabling rich rendering should expose raw source text and emit state."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"painting \(medium\)",
        width=220,
    )
    surface = surface_for(box)
    emitted: list[bool] = []
    box.richPromptRenderingEnabledChanged.connect(emitted.append)

    box.setRichPromptRenderingEnabled(False)
    process_events(app)

    assert emitted == [False]
    assert box.richPromptRenderingEnabled() is False
    assert box.displayMode() is PromptProjectionDisplayMode.RAW
    assert surface.projection_document().projection_text == r"painting \(medium\)"


def test_prompt_editor_rich_rendering_toggle_preserves_raw_source_edits(
    widgets: list[QWidget],
) -> None:
    """Re-enabling rich rendering should not normalize raw-edited source text."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="", width=260)
    box.setRichPromptRenderingEnabled(False)
    process_events(app)

    QTest.keyClicks(box, "portrait (closeup)")
    process_events(app)
    box.setRichPromptRenderingEnabled(True)
    process_events(app)

    assert box.richPromptRenderingEnabled() is True
    assert box.displayMode() is PromptProjectionDisplayMode.PROJECTED
    assert box.toPlainText() == "portrait (closeup)"


def test_prompt_editor_raw_source_mode_preserves_typed_parentheses(
    widgets: list[QWidget],
) -> None:
    """Raw source editing should bypass typed parenthesis escaping."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="", width=260)
    box.setRichPromptRenderingEnabled(False)
    process_events(app)

    QTest.keyClicks(box, "painting (medium)")
    process_events(app)

    assert box.toPlainText() == "painting (medium)"


def test_prompt_editor_projected_mode_keeps_typed_parenthesis_normalization(
    widgets: list[QWidget],
) -> None:
    """Default rich editing should keep the existing canonical source policy."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="", width=260)

    QTest.keyClicks(box, "painting (medium)")
    process_events(app)

    assert box.richPromptRenderingEnabled() is True
    assert box.toPlainText() == "painting (medium:1.10)"
    assert surface_for(box).projection_document().projection_text == (
        f"painting {OBJECT_REPLACEMENT_CHARACTER}medium{OBJECT_REPLACEMENT_CHARACTER}"
    )


def test_prompt_editor_raw_source_mode_preserves_pasted_parentheses(
    widgets: list[QWidget],
) -> None:
    """Raw source editing should bypass pasted parenthesis escaping."""

    app = ensure_qapp()
    box = show_prompt_editor(widgets, text="", width=260)
    box.setRichPromptRenderingEnabled(False)
    QApplication.clipboard().setText("portrait (closeup)")
    process_events(app)

    box.paste()
    process_events(app)
    box.setRichPromptRenderingEnabled(True)
    process_events(app)

    assert box.toPlainText() == "portrait (closeup)"


def test_prompt_editor_raw_mode_hides_projected_emphasis_controls(
    widgets: list[QWidget],
) -> None:
    """Projected-only emphasis controls should hide when the editor is in raw mode."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text="(cat:1.05)",
        width=200,
    )
    controls = emphasis_controls_for(box)

    _select_range(box, 2, 2)
    process_events(app)
    _reveal_first_emphasis_controls(box)
    assert controls.visible_token is not None

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(app)

    assert controls.visible_token is None
    assert controls.isVisible() is False


def test_prompt_editor_projected_mode_hides_literal_parenthesis_escapes_but_raw_mode_shows_them(
    widgets: list[QWidget],
) -> None:
    """Projected mode should show clean text while raw mode shows the exact escaped source."""

    app = ensure_qapp()
    box = show_prompt_editor(
        widgets,
        text=r"painting \(medium\)",
        width=220,
    )
    surface = surface_for(box)

    assert box.toPlainText() == r"painting \(medium\)"
    assert surface.projection_document().projection_text == "painting (medium)"

    box.setDisplayMode(PromptProjectionDisplayMode.RAW)
    process_events(app)

    assert box.toPlainText() == r"painting \(medium\)"
    assert surface.projection_document().projection_text == r"painting \(medium\)"

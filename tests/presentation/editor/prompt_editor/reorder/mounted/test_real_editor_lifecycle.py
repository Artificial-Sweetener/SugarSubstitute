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

"""Test real-editor reorder lifecycle behavior."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QVBoxLayout, QWidget

from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.core.projection.document import (
    PromptProjectionDocument,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompletePanel,
)
from tests.presentation.editor.prompt_editor.autocomplete.real_widget_support import (
    ensure_qapp,
    process_events,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_fixtures import (
    sample_suggestions,
)
from tests.presentation.editor.prompt_editor.autocomplete.surface_support import (
    StaticPromptAutocompleteGateway,
    create_prompt_editor,
    editor_autocomplete_preview_text,
)
from tests.support.prompt_editor.projection_engine_support import surface_for


def _reorder_preview_document(editor: PromptEditor) -> PromptProjectionDocument | None:
    """Return the projection preview active during a mounted reorder session."""

    return cast(
        PromptProjectionDocument | None,
        getattr(surface_for(editor), "_reorder_preview_projection").preview_document,
    )


def test_prompt_editor_real_widget_enters_reorder_mode_once_and_closes_without_mutation_on_noop_alt_release(
    widgets: list[QWidget],
) -> None:
    """Holding Alt should create one reorder overlay and close cleanly without a move."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(
        prompt_autocomplete_gateway=StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(editor)
    editor.setPlainText("alpha,beta,")
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)

    first_overlay = getattr(editor, "_segment_overlay")
    assert first_overlay is not None
    assert _reorder_preview_document(editor) is None
    assert first_overlay.isVisible() is True
    assert first_overlay.parentWidget() is editor.viewport()
    assert first_overlay.findChild(QWidget, "segmentReorderScrollArea") is None
    assert first_overlay.findChild(QWidget, "segmentReorderFrame") is None

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)
    assert getattr(editor, "_segment_overlay") is first_overlay

    QTest.keyRelease(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert editor.toPlainText() == "alpha,beta,"
    assert _reorder_preview_document(editor) is None
    assert getattr(editor, "_segment_overlay") is None


def test_prompt_editor_real_widget_entering_reorder_mode_dismisses_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Entering reorder mode should clear autocomplete before creating its overlay."""

    app = ensure_qapp()
    gateway = StaticPromptAutocompleteGateway({"1g": sample_suggestions()})
    host = QWidget()
    host.resize(520, 240)
    layout = QVBoxLayout(host)
    editor = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(editor)
    host.show()
    host.activateWindow()
    editor.setFocus()
    widgets.extend([host, editor])
    process_events(app)

    QTest.keyClicks(editor, "alpha, beta, 1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(editor, "_autocomplete_panel"))
    assert panel.is_panel_visible() is True
    assert editor_autocomplete_preview_text(editor) == "irl"

    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert panel.is_panel_visible() is False
    assert editor_autocomplete_preview_text(editor) == ""
    reorder_overlay = getattr(editor, "_segment_overlay")
    assert reorder_overlay is not None
    assert reorder_overlay.parentWidget() is editor.viewport()

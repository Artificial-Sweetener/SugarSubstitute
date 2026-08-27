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

"""Regression tests for prompt projection Unicode and input-method behavior."""

from __future__ import annotations

from typing import Any, cast


import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QInputMethodEvent, QTextCharFormat
from PySide6.QtWidgets import QApplication, QWidget

from substitute.presentation.editor.prompt_editor.projection.input_method_layer_preparer import (
    PromptInputMethodRenderLayerPreparer,
)
from tests.support.prompt_editor.projection_surface_support import (
    projection_surface_widgets as _projection_surface_widgets,  # noqa: F401
    render_surface_viewport,
)
from tests.support.prompt_editor.projection_surface_factory import (
    new_projection_surface,
    surface_edit_execution,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp

from .support import _set_source


def test_prompt_preedit_is_transient_and_exposes_complete_qt_queries(
    widgets: list[QWidget],
) -> None:
    """Keep Japanese preedit out of source while answering the platform IME."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    _set_source(surface, "prefix 👩‍💻 suffix")
    surface.set_cursor_positions(cursor_position=7, anchor_position=7)
    text_format = QTextCharFormat()
    text_format.setFontUnderline(True)
    attributes = [
        QInputMethodEvent.Attribute(
            QInputMethodEvent.AttributeType.TextFormat,
            0,
            3,
            text_format,
        ),
        QInputMethodEvent.Attribute(
            QInputMethodEvent.AttributeType.Cursor,
            3,
            1,
            None,
        ),
    ]

    QApplication.sendEvent(surface, QInputMethodEvent("にほん", attributes))

    assert surface.toPlainText() == "prefix 👩‍💻 suffix"
    assert surface.inputMethodQuery(Qt.InputMethodQuery.ImEnabled) is True
    assert (
        surface.inputMethodQuery(Qt.InputMethodQuery.ImSurroundingText)
        == "prefix 👩‍💻 suffix"
    )
    assert surface.inputMethodQuery(Qt.InputMethodQuery.ImCursorPosition) == 7
    assert surface.inputMethodQuery(Qt.InputMethodQuery.ImCurrentSelection) == ""
    assert cast(
        QRectF,
        surface.inputMethodQuery(Qt.InputMethodQuery.ImCursorRectangle),
    ).isValid()


def test_prompt_preedit_paint_consumes_the_published_shaped_layer(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paint must not shape preedit text or query its caret geometry."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    surface.resize(400, 120)
    surface.show()
    QApplication.processEvents()
    _set_source(surface, "prefix suffix")
    surface.set_cursor_positions(cursor_position=7, anchor_position=7)
    QApplication.sendEvent(surface, QInputMethodEvent("にほん", []))
    controller = cast(Any, surface)._input_method_controller
    assert controller.render_layer.layout is not None

    def reject_preparation(*args: object, **kwargs: object) -> None:
        """Reject input-method shaping reached from the paint stack."""

        del args, kwargs
        raise AssertionError("input-method preparation ran during paint")

    monkeypatch.setattr(
        PromptInputMethodRenderLayerPreparer,
        "prepare",
        reject_preparation,
    )

    image = render_surface_viewport(surface)

    assert not image.isNull()


def test_prompt_ime_commit_replaces_selection_once_and_round_trips_undo(
    widgets: list[QWidget],
) -> None:
    """Commit Chinese/Japanese text as one undo-safe source mutation."""

    ensure_qapp()
    surface = new_projection_surface()
    widgets.append(surface)
    _set_source(surface, "replace me")
    surface.set_cursor_positions(cursor_position=10, anchor_position=0)
    QApplication.sendEvent(surface, QInputMethodEvent("nihon", []))
    commit = QInputMethodEvent()
    commit.setCommitString("中文 日本語 한국어 👩‍💻")

    QApplication.sendEvent(surface, commit)

    assert surface.toPlainText() == "中文 日本語 한국어 👩‍💻"
    assert surface_edit_execution(surface).undo() is not None
    assert surface.toPlainText() == "replace me"

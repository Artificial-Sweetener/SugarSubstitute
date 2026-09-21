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

"""Test projection focus-host lifecycle ownership."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.prompt_editor.projection.focus_owner import (
    PromptProjectionFocusOwner,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp


def test_focus_owner_routes_host_lifecycle_to_chrome_and_caret() -> None:
    """Focus-host transitions should refresh chrome and choose reset semantics."""

    ensure_qapp()
    surface = QWidget()
    focus_host = QWidget()
    chrome_refreshes: list[None] = []
    blink_resets: list[bool] = []
    owner = PromptProjectionFocusOwner(
        surface=surface,
        prepare_source_line_chrome=lambda: chrome_refreshes.append(None),
        schedule_caret_blink=blink_resets.append,
        parent=surface,
    )

    owner.attach(focus_host)
    assert owner.focus_host is focus_host
    assert blink_resets == [False]

    assert owner.eventFilter(focus_host, QEvent(QEvent.Type.FocusIn)) is False
    assert owner.eventFilter(focus_host, QEvent(QEvent.Type.FocusOut)) is False
    assert owner.eventFilter(focus_host, QEvent(QEvent.Type.Hide)) is False
    assert owner.eventFilter(focus_host, QEvent(QEvent.Type.Show)) is False

    assert len(chrome_refreshes) == 4
    assert blink_resets == [False, True, False, False, False]


def test_focus_owner_ignores_unmounted_widget_events() -> None:
    """Only the attached focus host should drive projection focus presentation."""

    ensure_qapp()
    surface = QWidget()
    focus_host = QWidget()
    blink_resets: list[bool] = []
    owner = PromptProjectionFocusOwner(
        surface=surface,
        prepare_source_line_chrome=lambda: None,
        schedule_caret_blink=blink_resets.append,
        parent=surface,
    )

    owner.attach(focus_host)
    assert owner.eventFilter(QWidget(), QEvent(QEvent.Type.FocusIn)) is False

    assert blink_resets == [False]

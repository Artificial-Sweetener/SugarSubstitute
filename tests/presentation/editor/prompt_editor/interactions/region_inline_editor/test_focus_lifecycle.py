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

"""Verify durable focus ownership for authored region-name inline editing."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QWidget
import pytest

from substitute.presentation.editor.prompt_editor.interactions.region_inline_editor import (
    PromptRegionInlineEditor,
)
from substitute.presentation.editor.prompt_editor.projection.region_chrome_state import (
    PromptRegionChromeEditTarget,
)
from tests.support.prompt_editor.projection_engine_support import ensure_qapp
from tests.support.qt.lifecycle import destroy_qt_object


def test_active_window_focus_churn_preserves_region_name_draft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not commit a region draft while active-window focus is unresolved."""

    ensure_qapp()
    module = __import__(
        "substitute.presentation.editor.prompt_editor.interactions.region_inline_editor",
        fromlist=("QApplication",),
    )
    monkeypatch.setattr(
        module,
        "QApplication",
        SimpleNamespace(focusWidget=lambda: None),
    )
    monkeypatch.setattr(
        module,
        "QTimer",
        SimpleNamespace(singleShot=lambda _delay, callback: callback()),
    )
    viewport = QWidget()
    committed_names: list[str] = []

    def commit_region_name(name: str) -> bool:
        """Record one accepted authored region name."""

        committed_names.append(name)
        return True

    owner = PromptRegionInlineEditor(
        viewport=viewport,
        target_provider=lambda _index: _edit_target(),
        scroll_offset=lambda: 0.0,
        active_region_sink=lambda _index: None,
        draft_sink=lambda _index, _text: None,
    )
    try:
        assert owner.begin(
            region_index=0,
            current_name="Foreground",
            commit=commit_region_name,
        )
        editor = cast(Any, owner.editor)
        editor.focusAcquired.emit()

        editor.focusCommitRequested.emit(Qt.FocusReason.ActiveWindowFocusReason)

        assert owner.active is True
        assert committed_names == []

        editor.focusCommitRequested.emit(Qt.FocusReason.MouseFocusReason)

        assert owner.active is False
        assert committed_names == ["Foreground"]
    finally:
        destroy_qt_object(viewport)


def _edit_target() -> PromptRegionChromeEditTarget:
    """Return one complete inline-editor geometry target."""

    return PromptRegionChromeEditTarget(
        region_index=0,
        center=QPointF(100.0, 20.0),
        row_height=24.0,
        width=120.0,
        maximum_width=200.0,
        rule_length=30.0,
        separator_line_count=1,
        color=QColor("white"),
        font=QFont(),
    )

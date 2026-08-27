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

"""Verify searchable combo text painting geometry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import QStyle, QStyleOptionFrame

from substitute.presentation.widgets.combo_box import _COMBO_DROPDOWN_TEXT_MARGIN
from tests.presentation.widgets.combo_box.support import MountedCombo


def test_inline_completion_elides_to_available_width(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Ghost completion should elide instead of escaping its paint rectangle."""

    combo = combo_mount().combo
    combo._inline_completion_suffix = "DPM++ 2M Karras"
    narrow_width = combo.fontMetrics().horizontalAdvance("DPM++")
    expected = combo.fontMetrics().elidedText(
        combo._inline_completion_suffix,
        Qt.TextElideMode.ElideRight,
        narrow_width,
    )

    assert combo._elided_inline_completion_text(narrow_width) == expected
    assert expected != combo._inline_completion_suffix
    assert combo._elided_inline_completion_text(combo.sizeHint().width()) == (
        combo._inline_completion_suffix
    )
    assert combo._elided_inline_completion_text(0) == ""


def test_combo_preserves_qfluent_dropdown_text_margin(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Search text should retain QFluent's arrow-side inset."""

    combo = combo_mount().combo

    assert combo.textMargins().left() == 0
    assert combo.textMargins().right() == _COMBO_DROPDOWN_TEXT_MARGIN


def test_styled_text_rect_excludes_dropdown_button(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Custom text geometry should derive from style chrome and stop before the arrow."""

    combo = combo_mount().combo
    drop_button = cast(Any, combo).dropButton
    style_contents_rect = _line_edit_contents_rect(combo)
    styled_rect = combo._styled_text_rect()

    assert drop_button.isVisible()
    assert styled_rect.left() == style_contents_rect.left()
    assert styled_rect.right() <= style_contents_rect.right()
    assert styled_rect.right() < drop_button.geometry().left()


def test_closed_and_completion_rects_share_styled_origin(
    combo_mount: Callable[..., MountedCombo],
) -> None:
    """Committed and ghost text should project from one styled text rectangle."""

    combo = combo_mount().combo
    base_rect = combo._styled_text_rect()
    closed_rect = combo._closed_display_text_rect()
    typed_width = combo.fontMetrics().horizontalAdvance("ar")
    ghost_rect = combo._inline_completion_text_rect("ar")

    assert closed_rect == base_rect
    assert ghost_rect.left() == base_rect.left() + typed_width
    assert ghost_rect.right() == base_rect.right()
    assert ghost_rect.top() == base_rect.top()
    assert ghost_rect.height() == base_rect.height()


def _line_edit_contents_rect(combo: object) -> QRect:
    """Return Qt's styled line-edit contents rectangle for one combo."""

    runtime = cast(Any, combo)
    option = QStyleOptionFrame()
    option.initFrom(runtime)
    option_state = cast(Any, option)
    option_state.rect = runtime.rect()
    option_state.lineWidth = runtime.style().pixelMetric(
        QStyle.PixelMetric.PM_DefaultFrameWidth,
        option,
        runtime,
    )
    option_state.midLineWidth = 0
    return cast(
        QRect,
        runtime.style().subElementRect(
            QStyle.SubElement.SE_LineEditContents,
            option,
            runtime,
        ),
    )

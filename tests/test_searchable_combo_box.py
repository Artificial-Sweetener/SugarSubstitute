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

"""Behavior tests for select-only searchable ordinary combo boxes."""

from __future__ import annotations

import os
from typing import Any, cast

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QStyle,
    QStyleOptionFrame,
    QWidget,
)

import substitute.presentation.widgets.searchable_combo_popup as combo_popup_module
from substitute.presentation.widgets.combo_box import (
    _COMBO_DROPDOWN_TEXT_MARGIN,
    ComboBox,
)
from substitute.presentation.widgets.searchable_combo_helpers import (
    AttachedPopupPlacement,
)


def _ensure_qapp() -> QApplication:
    """Return the QApplication used by searchable combo widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _combo_with_items(host: QWidget) -> ComboBox:
    """Create a visible combo with deterministic option labels."""

    combo = ComboBox(host)
    combo.addItems(["Flat", "Euler", "Euclid", "Heun", "DPM++ 2M Karras", "Beta Euler"])
    combo.resize(220, 34)
    combo.show()
    return combo


def _wait_for_popup_reveal(popup: Any, app: QApplication) -> None:
    """Wait for popup reveal animation completion under busy xdist workers."""

    animation = popup._reveal_animation
    if animation is None:
        app.processEvents()
        return
    for _ in range(100):
        app.processEvents()
        if animation.state() is QAbstractAnimation.State.Stopped:
            return
        QTest.qWait(10)
    app.processEvents()


def _line_edit_contents_rect(combo: ComboBox) -> QRect:
    """Return Qt's styled line-edit contents rect for a combo."""

    option = QStyleOptionFrame()
    option.initFrom(combo)
    option_state = cast(Any, option)
    option_state.rect = combo.rect()
    option_state.lineWidth = combo.style().pixelMetric(
        QStyle.PixelMetric.PM_DefaultFrameWidth,
        option,
        combo,
    )
    option_state.midLineWidth = 0
    return combo.style().subElementRect(
        QStyle.SubElement.SE_LineEditContents,
        option,
        combo,
    )


def test_search_typing_filters_without_committing_text() -> None:
    """Typed query text should narrow the popup without changing selection."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    changed: list[str] = []
    combo.currentTextChanged.connect(changed.append)

    combo.setFocus()
    QTest.keyClicks(combo, "heu")
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    assert popup.visible_texts() == ["Heun"]
    assert combo.text() == "heu"
    assert combo.currentText() == "Flat"
    assert changed == []
    host.deleteLater()


def test_down_and_enter_commit_highlighted_filtered_item() -> None:
    """Enter should commit the highlighted allowed item."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    changed: list[str] = []
    combo.currentTextChanged.connect(changed.append)

    combo.setFocus()
    QTest.keyClicks(combo, "eu")
    app.processEvents()
    QTest.keyClick(combo, Qt.Key.Key_Down)
    QTest.keyClick(combo, Qt.Key.Key_Return)
    app.processEvents()

    assert combo.currentText() == "Euclid"
    assert combo.text() == ""
    assert changed == ["Euclid"]
    host.deleteLater()


def test_tab_commits_highlighted_filtered_item() -> None:
    """Tab should commit the highlighted popup item when one is available."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "kar")
    app.processEvents()
    QTest.keyClick(combo, Qt.Key.Key_Tab)
    app.processEvents()

    assert combo.currentText() == "DPM++ 2M Karras"
    assert combo.text() == ""
    host.deleteLater()


def test_inline_completion_tracks_keyboard_highlight_changes() -> None:
    """Ghost completion should follow Up/Down popup focus."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "eu")
    app.processEvents()

    assert combo._inline_completion_suffix == "ler"
    QTest.keyClick(combo, Qt.Key.Key_Down)
    app.processEvents()
    assert combo._inline_completion_suffix == "clid"
    QTest.keyClick(combo, Qt.Key.Key_Up)
    app.processEvents()
    assert combo._inline_completion_suffix == "ler"
    host.deleteLater()


def test_inline_completion_tracks_hovered_popup_item() -> None:
    """Ghost completion should follow the row currently hovered by the mouse."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "eu")
    app.processEvents()
    popup = combo._popup
    assert popup is not None
    assert popup.visible_texts() == ["Euler", "Euclid", "Heun", "Beta Euler"]

    item = popup.view.item(1)
    assert item is not None
    popup._on_item_entered(item)
    app.processEvents()

    assert combo._inline_completion_suffix == "clid"
    host.deleteLater()


def test_empty_search_box_ghost_completion_tracks_keyboard_highlight() -> None:
    """A blank active search should ghost the whole highlighted item."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    combo.selectAll()
    QTest.keyClick(combo, Qt.Key.Key_Backspace)
    app.processEvents()

    assert combo.text() == ""
    assert combo._inline_completion_suffix == "Flat"
    QTest.keyClick(combo, Qt.Key.Key_Down)
    app.processEvents()
    assert combo._inline_completion_suffix == "Euler"
    QTest.keyClick(combo, Qt.Key.Key_Down)
    app.processEvents()
    assert combo._inline_completion_suffix == "Euclid"
    host.deleteLater()


def test_empty_search_box_ghost_completion_tracks_hovered_item() -> None:
    """A blank active search should ghost the hovered allowed item."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    combo.selectAll()
    QTest.keyClick(combo, Qt.Key.Key_Backspace)
    app.processEvents()
    popup = combo._popup
    assert popup is not None
    assert popup.visible_texts() == [
        "Flat",
        "Euler",
        "Euclid",
        "Heun",
        "DPM++ 2M Karras",
        "Beta Euler",
    ]

    item = popup.view.item(2)
    assert item is not None
    popup._on_item_entered(item)
    app.processEvents()

    assert combo.text() == ""
    assert combo._inline_completion_suffix == "Euclid"
    host.deleteLater()


def test_inline_completion_paint_text_elides_to_available_width() -> None:
    """Ghost completion text should elide instead of overflowing its paint rect."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    combo._inline_completion_suffix = "DPM++ 2M Karras"
    app.processEvents()

    narrow_width = combo.fontMetrics().horizontalAdvance("DPM++")
    expected_elided = combo.fontMetrics().elidedText(
        combo._inline_completion_suffix,
        Qt.TextElideMode.ElideRight,
        narrow_width,
    )
    wide_width = combo.fontMetrics().horizontalAdvance(combo._inline_completion_suffix)

    assert combo._elided_inline_completion_text(narrow_width) == expected_elided
    assert expected_elided != combo._inline_completion_suffix
    assert combo._elided_inline_completion_text(wide_width) == (
        combo._inline_completion_suffix
    )
    assert combo._elided_inline_completion_text(0) == ""
    host.deleteLater()


def test_combo_box_preserves_qfluent_dropdown_text_margin() -> None:
    """ComboBox should keep qfluent's arrow-side line-edit text margin."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    app.processEvents()

    assert combo.textMargins().left() == 0
    assert combo.textMargins().right() == _COMBO_DROPDOWN_TEXT_MARGIN
    host.deleteLater()


def test_styled_text_rect_uses_qfluent_contents_and_excludes_dropdown_button() -> None:
    """Custom paint geometry should derive from qfluent line-edit style geometry."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    app.processEvents()

    drop_button = cast(Any, combo).dropButton
    style_contents_rect = _line_edit_contents_rect(combo)
    styled_rect = combo._styled_text_rect()

    assert drop_button.isVisible()
    assert styled_rect.left() == style_contents_rect.left()
    assert styled_rect.right() <= style_contents_rect.right()
    assert styled_rect.right() < drop_button.geometry().left()
    host.deleteLater()


def test_closed_and_inline_completion_rects_share_styled_text_origin() -> None:
    """Closed and ghost text should derive from the same styled text rect."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    app.processEvents()

    base_rect = combo._styled_text_rect()
    closed_rect = combo._closed_display_text_rect()
    typed_width = combo.fontMetrics().horizontalAdvance("ar")
    ghost_rect = combo._inline_completion_text_rect("ar")

    assert closed_rect == base_rect
    assert ghost_rect.left() == base_rect.left() + typed_width
    assert ghost_rect.right() == base_rect.right()
    assert ghost_rect.top() == base_rect.top()
    assert ghost_rect.height() == base_rect.height()
    host.deleteLater()


def test_escape_restores_previous_committed_value() -> None:
    """Escape should cancel search without emitting a value change."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    changed: list[str] = []
    combo.currentTextChanged.connect(changed.append)

    combo.setFocus()
    QTest.keyClicks(combo, "unknown")
    app.processEvents()
    QTest.keyClick(combo, Qt.Key.Key_Escape)
    app.processEvents()

    assert combo.currentText() == "Flat"
    assert combo.text() == ""
    assert changed == []
    host.deleteLater()


def test_unknown_return_text_is_not_added_or_committed() -> None:
    """Return on unmatched text should restore the previous committed item."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "missing")
    app.processEvents()
    QTest.keyClick(combo, Qt.Key.Key_Return)
    app.processEvents()

    assert combo.currentText() == "Flat"
    assert combo.count() == 6
    assert combo.findText("missing") == -1
    host.deleteLater()


def test_clicking_combo_body_opens_full_dropdown() -> None:
    """A normal body click should open the full unfiltered dropdown."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    assert popup.isVisible() is True
    assert popup.visible_texts() == [
        "Flat",
        "Euler",
        "Euclid",
        "Heun",
        "DPM++ 2M Karras",
        "Beta Euler",
    ]
    host.deleteLater()


def test_clicking_outside_combo_and_popup_closes_dropdown() -> None:
    """An outside mouse press should dismiss the transient dropdown."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    outside = QLabel("Outside", host)
    outside.setGeometry(300, 20, 120, 34)
    outside.show()

    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    app.processEvents()
    popup = combo._popup
    assert popup is not None
    assert popup.isVisible() is True

    QTest.mouseClick(outside, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert popup.isVisible() is False
    host.deleteLater()


def test_clicking_outside_search_popup_restores_committed_text() -> None:
    """Outside dismissal should abandon transient search text without committing it."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    outside = QLabel("Outside", host)
    outside.setGeometry(300, 20, 120, 34)
    outside.show()
    changed: list[str] = []
    combo.currentTextChanged.connect(changed.append)

    combo.setFocus()
    QTest.keyClicks(combo, "eu")
    app.processEvents()
    popup = combo._popup
    assert popup is not None
    assert popup.isVisible() is True

    QTest.mouseClick(outside, Qt.MouseButton.LeftButton)
    app.processEvents()

    assert popup.isVisible() is False
    assert combo.text() == ""
    assert combo.currentText() == "Flat"
    assert changed == []
    host.deleteLater()


def test_typing_continues_through_active_popup_keyboard_grab() -> None:
    """Real popup key routing should keep building the search query."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "a")
    app.processEvents()
    popup = combo._popup
    assert popup is not None
    assert popup.isVisible() is True

    QTest.keyClicks(popup, "r")
    app.processEvents()

    assert combo.text() == "ar"
    assert combo.currentText() == "Flat"
    assert popup.visible_texts() == ["DPM++ 2M Karras"]
    host.deleteLater()


def test_typing_refines_existing_popup_without_reexecuting_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Search refreshes should reuse the visible popup window."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "a")
    app.processEvents()
    popup = combo._popup
    assert popup is not None
    assert popup.isVisible() is True

    def fail_exec(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("search refresh re-executed the popup")

    monkeypatch.setattr(popup, "exec", fail_exec)

    QTest.keyClicks(popup, "r")
    app.processEvents()

    assert combo.text() == "ar"
    assert popup.isVisible() is True
    assert popup.visible_texts() == ["DPM++ 2M Karras"]
    host.deleteLater()


def test_search_refresh_keeps_visible_list_left_anchored_to_combo() -> None:
    """In-place popup refresh should keep the list edge on the combo edge."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.move(40, 40)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "a")
    app.processEvents()
    popup = combo._popup
    assert popup is not None
    initial_left = popup.list_global_left()

    QTest.keyClicks(combo, "r")
    app.processEvents()

    assert initial_left == combo.mapToGlobal(combo.rect().topLeft()).x()
    assert popup.list_global_left() == initial_left
    host.deleteLater()


def test_combo_popup_clamps_to_ten_visible_rows() -> None:
    """Large ordinary combo popups should show ten rows and then scroll."""

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("offscreen popup reveal can abort under Windows xdist workers")

    app = _ensure_qapp()
    host = QWidget()
    host.resize(520, 640)
    host.move(40, 40)
    host.show()
    combo = ComboBox(host)
    combo.addItems([f"Choice {index:02d}" for index in range(30)])
    combo.resize(220, 34)
    combo.show()

    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    _wait_for_popup_reveal(popup, app)
    expected_view_height = popup._view_height_for_visible_rows(10)
    expected_popup_height = expected_view_height + (
        popup.layout().contentsMargins().top()
        + popup.layout().contentsMargins().bottom()
    )

    assert popup.isVisible() is True
    assert popup.list_global_top() == combo.mapToGlobal(QPoint(0, combo.height())).y()
    assert popup.view.height() == expected_view_height
    assert popup.height() == expected_popup_height
    assert popup.visible_texts()[0] == "Choice 00"
    assert popup.visible_texts()[-1] == "Choice 29"
    host.deleteLater()


def test_combo_popup_opens_above_and_stays_attached_near_screen_bottom() -> None:
    """Low ordinary combo popups should open above without detaching."""

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("offscreen popup placement can abort under Windows xdist workers")

    app = _ensure_qapp()
    screen = app.primaryScreen()
    assert screen is not None
    available = screen.availableGeometry()
    host = QWidget()
    host.resize(480, 180)
    host.move(available.left() + 40, max(available.top(), available.bottom() - 190))
    host.show()
    combo = ComboBox(host)
    combo.addItems([f"Choice {index:02d}" for index in range(12)])
    combo.resize(220, 34)
    combo.move(40, host.height() - 38)
    combo.show()

    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    _wait_for_popup_reveal(popup, app)
    combo_top = combo.mapToGlobal(QPoint(0, 0)).y()

    assert popup.isVisible() is True
    assert popup.list_global_bottom() == combo_top
    assert popup.geometry().top() >= available.top()
    host.deleteLater()


def test_combo_popup_uses_qfluent_reveal_animation() -> None:
    """Opening ordinary combo popups should mirror qfluent's reveal timing."""

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("offscreen popup reveal can abort under Windows xdist workers")

    app = _ensure_qapp()
    host = QWidget()
    host.resize(520, 640)
    host.move(40, 40)
    host.show()
    combo = ComboBox(host)
    combo.addItems([f"Choice {index:02d}" for index in range(12)])
    combo.resize(220, 34)
    combo.show()

    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    animation = popup._reveal_animation
    assert animation is not None
    start_position = animation.startValue()
    end_position = animation.endValue()
    assert isinstance(start_position, QPoint)
    assert isinstance(end_position, QPoint)

    reveal_offset = QPoint(0, int((popup.height() + 5) / 2))
    assert animation.duration() == 250
    assert animation.easingCurve().type() == QEasingCurve.Type.OutQuad
    assert animation.state() == QAbstractAnimation.State.Running
    assert start_position == end_position - reveal_offset

    _wait_for_popup_reveal(popup, app)

    assert popup.pos() == end_position
    host.deleteLater()


def test_combo_popup_shrinks_and_stays_attached_when_vertical_space_is_tight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starved ordinary combo popups should shrink instead of detaching."""

    if os.environ.get("PYTEST_XDIST_WORKER"):
        pytest.skip("offscreen popup reveal can abort under Windows xdist workers")

    def forced_starved_placement(**kwargs: object) -> AttachedPopupPlacement:
        field_global_rect = cast(QRect, kwargs["field_global_rect"])
        row_height = cast(int, kwargs["row_height"])
        vertical_chrome_height = cast(int, kwargs["vertical_chrome_height"])
        return AttachedPopupPlacement(
            geometry=QRect(
                field_global_rect.left(),
                field_global_rect.top() + field_global_rect.height(),
                260,
                3 * row_height + vertical_chrome_height,
            ),
            opens_down=True,
            visible_row_count=3,
            requires_scroll=True,
        )

    monkeypatch.setattr(
        combo_popup_module,
        "attached_combo_popup_placement",
        forced_starved_placement,
    )

    app = _ensure_qapp()
    host = QWidget()
    host.resize(460, 120)
    host.move(40, 40)
    host.show()
    combo = ComboBox(host)
    combo.addItems([f"Choice {index:02d}" for index in range(30)])
    combo.resize(220, 34)
    combo.move(40, 62)
    combo.show()

    QTest.mouseClick(combo, Qt.MouseButton.LeftButton)
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    _wait_for_popup_reveal(popup, app)
    combo_bottom = combo.mapToGlobal(QPoint(0, combo.height())).y()

    assert popup.isVisible() is True
    assert popup.list_global_top() == combo_bottom
    assert popup.view.height() == popup._view_height_for_visible_rows(3)
    assert popup.height() == popup._view_height_for_visible_rows(3) + (
        popup.layout().contentsMargins().top()
        + popup.layout().contentsMargins().bottom()
    )
    host.deleteLater()


def test_search_popup_does_not_use_keyboard_grabbing_popup_flags() -> None:
    """The search popup should not steal normal typing focus from the combo."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)

    combo.setFocus()
    QTest.keyClicks(combo, "a")
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    assert popup.isVisible() is True
    assert (popup.windowFlags() & Qt.WindowType.WindowType_Mask) != Qt.WindowType.Popup
    QTest.keyClicks(combo, "r")
    app.processEvents()

    assert combo.text() == "ar"
    host.deleteLater()


def test_typing_replaces_selected_committed_text_instead_of_restoring_it() -> None:
    """Typing after selecting the committed text should start a search query."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(480, 240)
    host.show()
    combo = _combo_with_items(host)
    combo.selectAll()

    QTest.keyClicks(combo, "a")
    app.processEvents()

    popup = combo._popup
    assert popup is not None
    assert combo.text() == "a"
    assert combo.currentText() == "Flat"
    assert popup.visible_texts() == [
        "Flat",
        "DPM++ 2M Karras",
        "Beta Euler",
    ]
    host.deleteLater()


def test_default_combo_size_policy_caps_prompt_link_width_to_hint() -> None:
    """Title-row combos should not expand across the whole row by default."""

    app = _ensure_qapp()
    host = QWidget()
    host.resize(520, 80)
    layout = QHBoxLayout(host)
    label = QLabel("Text to Image", host)
    combo = ComboBox(host)
    combo.addItems(["Independent", "Text to Image"])
    layout.addWidget(label, 1)
    layout.addWidget(combo)
    host.show()
    app.processEvents()

    assert combo.width() <= combo.sizeHint().width() + 8
    host.deleteLater()

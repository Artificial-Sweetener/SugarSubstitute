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

"""Widget contract tests for shared Settings card primitives."""

from __future__ import annotations

import os
from typing import Any, cast

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QPushButton, QSizePolicy, QWidget
from qfluentwidgets import LineEdit  # type: ignore[import-untyped]

from substitute.presentation.settings.settings_card import (
    SETTINGS_CARD_ACTION_ICON_LEFT_MARGIN,
    SETTINGS_CARD_ACTION_ICON_MAX_SIZE,
    SETTINGS_CARD_DESCRIPTION_FONT_SIZE,
    SETTINGS_CARD_ICON_MAX_SIZE,
    SETTINGS_CARD_ICON_RIGHT_MARGIN,
    SETTINGS_CARD_MIN_HEIGHT,
    SETTINGS_CARD_MIN_WIDTH,
    SETTINGS_CARD_PADDING,
    SETTINGS_CARD_RADIUS,
    SETTINGS_CARD_TEXT_CONTROL_GAP,
    SETTINGS_CARD_TRAILING_MIN_WIDTH,
    SETTINGS_CARD_VERTICAL_CONTENT_SPACING,
    SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD,
    SETTINGS_CARD_WRAP_THRESHOLD,
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_card_group import (
    SETTINGS_CARD_GROUP_SPACING,
    SettingsCardGroup,
)
from substitute.presentation.settings.settings_control_group import SettingsControlGroup
from substitute.presentation.settings.settings_style import (
    SETTINGS_EXPANDER_HEADER_PADDING,
    SETTINGS_EXPANDER_ITEM_MIN_HEIGHT,
    SETTINGS_EXPANDER_ITEM_PADDING,
)

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_settings_card_metric_constants_match_toolkit_targets() -> None:
    """Settings cards should expose the exact Toolkit-derived metric contract."""

    assert SETTINGS_CARD_MIN_WIDTH == 148
    assert SETTINGS_CARD_MIN_HEIGHT == 68
    assert SETTINGS_CARD_RADIUS == 6
    assert SETTINGS_CARD_PADDING.left() == 16
    assert SETTINGS_CARD_PADDING.top() == 16
    assert SETTINGS_CARD_PADDING.right() == 16
    assert SETTINGS_CARD_PADDING.bottom() == 16
    assert SETTINGS_CARD_DESCRIPTION_FONT_SIZE == 12
    assert SETTINGS_CARD_ICON_MAX_SIZE == 20
    assert SETTINGS_CARD_ICON_RIGHT_MARGIN == 20
    assert SETTINGS_CARD_TEXT_CONTROL_GAP == 24
    assert SETTINGS_CARD_TRAILING_MIN_WIDTH == 120
    assert SETTINGS_CARD_ACTION_ICON_MAX_SIZE == 13
    assert SETTINGS_CARD_ACTION_ICON_LEFT_MARGIN == 14
    assert SETTINGS_CARD_VERTICAL_CONTENT_SPACING == 8
    assert SETTINGS_CARD_WRAP_THRESHOLD == 476
    assert SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD == 286
    assert SETTINGS_CARD_GROUP_SPACING == 4


def test_settings_card_constructs_primary_card_shape() -> None:
    """SettingsCard should expose title, description, icon, and trailing slots."""

    _app()
    visual = QWidget()
    trailing = QWidget()
    card = SettingsCard(
        title="Title",
        description="Description",
        visual_widget=visual,
        trailing_widget=trailing,
        show_chevron=True,
    )

    assert card.minimumHeight() == SETTINGS_CARD_MIN_HEIGHT
    assert card.minimumWidth() == SETTINGS_CARD_MIN_WIDTH
    assert card.title_label.text() == "Title"
    assert card.description_label.text() == "Description"
    assert card.visual_slot.width() == SETTINGS_CARD_ICON_MAX_SIZE
    assert card.trailing_widget is trailing
    assert card.action_icon is not None
    card.close()


def test_settings_card_centers_visual_slot_vertically() -> None:
    """SettingsCard icons should be vertically centered with row text."""

    app = _app()
    card = SettingsCard(
        title="Title",
        description="Description",
        visual_widget=QWidget(),
    )
    card.resize(520, SETTINGS_CARD_MIN_HEIGHT)
    card.show()
    app.processEvents()

    visual_center_y = card.visual_slot.geometry().center().y()
    text_center_y = card.text_column.geometry().center().y()

    assert card.visual_slot.y() > SETTINGS_CARD_PADDING.top()
    assert abs(visual_center_y - text_center_y) <= 2
    card.close()


def test_settings_card_wraps_trailing_content_at_toolkit_thresholds() -> None:
    """SettingsCard should select wide, wrapped, and no-icon modes by width."""

    app = _app()
    card = SettingsCard(
        title="Title",
        description="Description",
        visual_widget=QWidget(),
        trailing_widget=QWidget(),
    )
    card.resize(SETTINGS_CARD_WRAP_THRESHOLD + 40, 90)
    card.show()
    app.processEvents()

    assert card.layout_mode() == "wide"
    assert card.visual_slot.isVisible()

    card.resize(SETTINGS_CARD_WRAP_THRESHOLD - 1, 110)
    app.processEvents()

    assert card.layout_mode() == "wrapped"
    assert card.visual_slot.isVisible()

    card.resize(SETTINGS_CARD_WRAP_NO_ICON_THRESHOLD - 1, 120)
    app.processEvents()

    assert card.layout_mode() == "wrapped_no_icon"
    assert card.visual_slot.isHidden()
    card.close()


def test_settings_card_supports_custom_wrap_thresholds() -> None:
    """SettingsCard should allow row-specific WinUI wrap thresholds."""

    app = _app()
    card = SettingsCard(
        title="Adaptive",
        description="Custom threshold",
        trailing_widget=QWidget(),
        wrap_threshold=800,
        wrap_no_icon_threshold=600,
    )
    card.resize(760, 110)
    card.show()
    app.processEvents()

    assert card.layout_mode() == "wrapped"
    assert card.visual_slot.isVisible()

    card.resize(560, 120)
    app.processEvents()

    assert card.layout_mode() == "wrapped_no_icon"
    assert card.visual_slot.isHidden()
    card.close()


def test_settings_card_stretches_wrapped_trailing_content() -> None:
    """Wrapped trailing content should stay within the card width."""

    app = _app()
    trailing = QWidget()
    trailing.setMinimumWidth(120)
    trailing.setMaximumWidth(600)
    trailing.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    card = SettingsCard(
        title="Output pattern",
        description="Shrinkable field",
        visual_widget=QWidget(),
        trailing_widget=trailing,
    )
    card.resize(320, 120)
    card.show()
    app.processEvents()

    assert card.layout_mode() == "wrapped"
    assert trailing.width() <= card.width()
    assert trailing.width() >= SETTINGS_CARD_TRAILING_MIN_WIDTH
    card.close()


def test_settings_card_vertical_content_alignment_wraps_at_wide_width() -> None:
    """Vertical alignment should place content below header text at any width."""

    app = _app()
    trailing = QWidget()
    card = SettingsCard(
        title="Vertical",
        description="Always below",
        visual_widget=QWidget(),
        trailing_widget=trailing,
        content_alignment="vertical",
    )
    card.resize(760, 120)
    card.show()
    app.processEvents()

    assert card.layout_mode() == "wide"
    assert card.visual_slot.isVisible()
    assert trailing.parentWidget() is card._wrapped_content
    card.close()


def test_settings_control_group_follows_card_layout_mode() -> None:
    """Compound row controls should stack when their card wraps."""

    app = _app()
    group = SettingsControlGroup(QPushButton("One"), QPushButton("Two"))
    card = SettingsCard(
        title="Actions",
        description="Multiple controls",
        trailing_widget=group,
    )
    card.resize(320, 130)
    card.show()
    app.processEvents()

    assert card.layout_mode() == "wrapped"
    assert group.layout_mode() == "vertical"

    card.resize(620, 90)
    app.processEvents()

    assert card.layout_mode() == "wide"
    assert group.layout_mode() == "horizontal"
    card.close()


def test_settings_control_group_preserves_input_height() -> None:
    """Fluent inputs should not be clipped by grouped Settings row content."""

    app = _app()
    field = LineEdit()
    field.setMinimumHeight(33)
    group = SettingsControlGroup(field, QPushButton("Browse"))
    card = SettingsCard(
        title="Path",
        description="Choose a folder.",
        trailing_widget=group,
    )
    card.resize(760, card.sizeHint().height())
    card.show()
    app.processEvents()

    assert group.height() >= field.minimumHeight()
    assert field.geometry().bottom() <= group.contentsRect().bottom()
    card.close()


def test_settings_card_supports_expander_header_and_item_appearances() -> None:
    """SettingsCard should expose reference roles used by SettingsExpander."""

    _app()
    header = SettingsCard(title="Header", appearance="expander_header")
    item = SettingsCard(
        title="Item",
        description="Description",
        reserve_visual_space=False,
        appearance="expander_item",
    )
    header_layout = header.layout()
    item_layout = item.layout()
    assert header_layout is not None
    assert item_layout is not None

    header_margins = header_layout.contentsMargins()
    item_margins = item_layout.contentsMargins()

    assert header.appearance() == "expander_header"
    assert header_margins.left() == SETTINGS_EXPANDER_HEADER_PADDING.left()
    assert header_margins.right() == SETTINGS_EXPANDER_HEADER_PADDING.right()
    assert item.appearance() == "expander_item"
    assert item.minimumHeight() == SETTINGS_EXPANDER_ITEM_MIN_HEIGHT
    assert item_margins.left() == SETTINGS_EXPANDER_ITEM_PADDING.left()
    assert item_margins.top() == SETTINGS_EXPANDER_ITEM_PADDING.top()
    assert item_margins.right() == SETTINGS_EXPANDER_ITEM_PADDING.right()
    assert item_margins.bottom() == SETTINGS_EXPANDER_ITEM_PADDING.bottom()
    header.close()
    item.close()


def test_interactive_settings_card_activation_ignores_trailing_controls() -> None:
    """Interactive card body clicks should activate without stealing controls."""

    _app()
    trailing = QPushButton("Control")
    card = InteractiveSettingsCard(
        title="Title",
        description="Description",
        trailing_widget=trailing,
    )
    activated: list[bool] = []
    card.activated.connect(lambda: activated.append(True))

    card.mousePressEvent(_mouse_event(QMouseEvent.Type.MouseButtonPress, card))
    card.mouseReleaseEvent(_mouse_event(QMouseEvent.Type.MouseButtonRelease, card))

    assert activated == [True]
    activated.clear()
    cast(Any, card)._interaction.set_interactive_targets(())
    trailing.click()

    assert activated == []
    card.close()


def test_settings_card_group_owns_title_and_cards() -> None:
    """SettingsCardGroup should own a compact title and vertically spaced cards."""

    _app()
    first = SettingsCard(title="First")
    second = SettingsCard(title="Second")
    group = SettingsCardGroup("Group", cards=(first, second))

    assert group.title_label.text() == "Group"
    assert group.cards() == (first, second)
    assert group._card_layout.spacing() == SETTINGS_CARD_GROUP_SPACING
    group.close()


def test_settings_cards_reject_detail_widgets() -> None:
    """Settings card primitives should not accept obsolete detail widgets."""

    _app()
    settings_card = cast(Any, SettingsCard)
    interactive_card = cast(Any, InteractiveSettingsCard)
    detail_kwargs: dict[str, object] = {"details": (QWidget(),)}

    with pytest.raises(TypeError):
        settings_card(
            title="Title",
            description="Description",
            **detail_kwargs,
        )
    with pytest.raises(TypeError):
        interactive_card(
            title="Title",
            description="Description",
            **detail_kwargs,
        )


def _mouse_event(event_type: QMouseEvent.Type, widget: QWidget) -> QMouseEvent:
    """Return one left-button mouse event centered inside a widget."""

    local = widget.rect().center()
    return QMouseEvent(
        event_type,
        local,
        widget.mapToGlobal(QPoint(local)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _app() -> QApplication:
    """Return the active QApplication instance."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)

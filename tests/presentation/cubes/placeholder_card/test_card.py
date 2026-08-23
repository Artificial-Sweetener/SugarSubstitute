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

"""Widget tests for the shared cube placeholder card."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_COMPACT_WIDTH,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)
from tests.support.qt.lifecycle import destroy_qt_object


@pytest.fixture
def placeholder_card_factory(
    qt_application_owner: QApplication,
) -> Iterator[Callable[..., CubePlaceholderCard]]:
    """Create placeholder cards and synchronously release each native widget."""

    _ = qt_application_owner
    cards: list[CubePlaceholderCard] = []

    def create(
        *,
        plus_visible: bool = False,
        interactive: bool = False,
    ) -> CubePlaceholderCard:
        """Create one unmounted placeholder card with deterministic ownership."""

        card = CubePlaceholderCard(
            plus_visible=plus_visible,
            interactive=interactive,
        )
        cards.append(card)
        return card

    try:
        yield create
    finally:
        for card in cards:
            destroy_qt_object(card)


def test_placeholder_card_defaults_to_expanded_cube_card_size(
    placeholder_card_factory: Callable[..., CubePlaceholderCard],
) -> None:
    """Placeholder cards should start at the real expanded cube-card size."""

    card = placeholder_card_factory()

    assert card.width() == CUBE_ITEM_EXPANDED_WIDTH
    assert card.height() == CUBE_ITEM_HEIGHT
    assert card.objectName() == "cubePlaceholderCard"
    assert card.isPlusVisible() is False
    assert card.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_placeholder_card_compact_mode_uses_compact_cube_width(
    placeholder_card_factory: Callable[..., CubePlaceholderCard],
) -> None:
    """Compact mode should match real compact cube-card width."""

    card = placeholder_card_factory()

    card.setCompact(True)

    assert card.isCompact() is True
    assert card.compact_progress() == 1.0
    assert card.width() == CUBE_ITEM_COMPACT_WIDTH
    assert card.height() == CUBE_ITEM_HEIGHT


def test_placeholder_card_compact_progress_clamps_and_interpolates_width(
    placeholder_card_factory: Callable[..., CubePlaceholderCard],
) -> None:
    """Transition progress should produce stable in-between card widths."""

    card = placeholder_card_factory()

    card.setCompactProgress(-1.0)
    assert card.compact_progress() == 0.0
    assert card.width() == CUBE_ITEM_EXPANDED_WIDTH

    card.setCompactProgress(0.5)
    assert card.compact_progress() == 0.5
    assert CUBE_ITEM_COMPACT_WIDTH < card.width() < CUBE_ITEM_EXPANDED_WIDTH

    card.setCompactProgress(2.0)
    assert card.compact_progress() == 1.0
    assert card.width() == CUBE_ITEM_COMPACT_WIDTH


def test_placeholder_card_interactive_mode_emits_activation(
    placeholder_card_factory: Callable[..., CubePlaceholderCard],
) -> None:
    """Interactive placeholders should emit activation on left-click release."""

    card = placeholder_card_factory(interactive=True)
    calls: list[bool] = []
    card.activated.connect(lambda: calls.append(True))
    QTest.mouseClick(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )

    assert calls == [True]
    assert card.cursor().shape() == Qt.CursorShape.PointingHandCursor


def test_placeholder_card_non_interactive_mode_does_not_emit_activation(
    placeholder_card_factory: Callable[..., CubePlaceholderCard],
) -> None:
    """Non-interactive placeholders should stay passive during mouse clicks."""

    card = placeholder_card_factory(interactive=False)
    calls: list[bool] = []
    card.activated.connect(lambda: calls.append(True))
    QTest.mouseClick(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )

    assert calls == []


def test_placeholder_card_plus_visibility_can_be_toggled(
    placeholder_card_factory: Callable[..., CubePlaceholderCard],
) -> None:
    """The centered plus affordance should be host-controlled."""

    card = placeholder_card_factory(plus_visible=True)

    assert card.isPlusVisible() is True

    card.setPlusVisible(False)

    assert card.isPlusVisible() is False

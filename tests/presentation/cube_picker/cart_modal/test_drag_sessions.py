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

"""Widget tests for the cube stack cart modal."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.application.cubes import (
    CubeStackDraft,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.presentation.cube_picker.cube_stack_cart_modal import (
    CubeStackCartModal,
)


from tests.presentation.cube_picker.cart_modal.support import (
    _IconFactory,
    _app,
    _clear_override_cursor,
    _draft_entries,
    _six_catalog_classifications,
    _six_catalog_records,
)


def test_modal_idle_cursor_policy_uses_arrow_for_library_cards() -> None:
    """Idle library cards should keep the normal pointer cursor."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    cards = list(modal._cards.values())

    assert cards
    assert all(
        card.testAttribute(Qt.WidgetAttribute.WA_SetCursor) is False for card in cards
    )
    assert all(card.cursor().shape() == Qt.CursorShape.ArrowCursor for card in cards)
    assert all(
        modal._idle_cursor_override_mode_for_widget(card) is None for card in cards
    )
    assert all(
        label.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        for card in cards
        for label in card.findChildren(QLabel)
    )


def test_modal_idle_cursor_policy_uses_arrow_for_staged_cards_and_close() -> None:
    """Idle staged cards and close buttons should keep the normal pointer cursor."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=_draft_entries(1)),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    card = modal._staging_stack.findChildren(QWidget, "cubeStagingCard")[0]
    close_button = getattr(card, "closeButton")

    assert modal._idle_cursor_override_mode_for_widget(card) is None
    assert modal._idle_cursor_override_mode_for_widget(close_button) is None
    assert card.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert close_button.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_library_drag_sets_modal_owned_closed_hand_cursor() -> None:
    """Active library drags should show modal-owned drag cursor feedback."""

    _app()
    _clear_override_cursor()
    try:
        modal = CubeStackCartModal(
            records=_six_catalog_records(),
            classifications=_six_catalog_classifications(),
            initial_draft=CubeStackDraft(entries=()),
            icon_factory=_IconFactory(),
            parent=QWidget(),
        )

        modal._begin_library_drag("inpaint", QPoint(-400, -400))
        cursor = QApplication.overrideCursor()

        assert modal._drag_controller.state is not None
        assert modal._drag_cursor_override_active is True
        assert cursor is not None
        assert cursor.shape() == Qt.CursorShape.ClosedHandCursor
    finally:
        _clear_override_cursor()


def test_library_drag_restores_modal_owned_cursor_on_finish() -> None:
    """Completing a library drag should restore the modal-owned cursor override."""

    _app()
    _clear_override_cursor()
    try:
        modal = CubeStackCartModal(
            records=_six_catalog_records(),
            classifications=_six_catalog_classifications(),
            initial_draft=CubeStackDraft(entries=()),
            icon_factory=_IconFactory(),
            parent=QWidget(),
        )
        modal._begin_library_drag("inpaint", QPoint(-400, -400))

        modal._finish_drag(QPoint(-400, -400))

        assert modal._drag_controller.state is None
        assert modal._drag_cursor_override_active is False
        assert QApplication.overrideCursor() is None
    finally:
        _clear_override_cursor()


def test_staged_drag_restores_modal_owned_cursor_on_reject() -> None:
    """Rejecting the modal during a staged drag should restore cursor feedback."""

    _app()
    _clear_override_cursor()
    try:
        modal = CubeStackCartModal(
            records=[
                CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
            ],
            initial_draft=CubeStackDraft(entries=_draft_entries(1)),
            icon_factory=_IconFactory(),
            parent=QWidget(),
        )
        staged_id = modal._staging_stack.entries()[0].draft_id
        modal._begin_staged_drag(staged_id, QPoint(-400, -400))

        modal.reject()

        assert modal._drag_controller.state is None
        assert modal._drag_cursor_override_active is False
        assert QApplication.overrideCursor() is None
    finally:
        _clear_override_cursor()


def test_staged_drag_release_is_captured_after_source_card_rebuild() -> None:
    """The modal should finish drags even after the source staged card is rebuilt."""

    app = _app()
    modal = CubeStackCartModal(
        records=[
            CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
        ],
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    modal._stage_cube_from_library("cube-a")
    staged_id = modal._staging_stack.entries()[0].draft_id

    modal._begin_staged_drag(staged_id, QPoint(-400, -400))
    release = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(-400, -400),
        QPointF(-400, -400),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    handled = modal.eventFilter(app, release)

    assert handled is True
    assert modal._drag_controller.state is None
    assert modal._drag_event_filter_installed is False
    assert modal._staging_stack.entries() == ()

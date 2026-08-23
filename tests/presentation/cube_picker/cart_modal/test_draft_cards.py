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

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QWidget

from substitute.application.cubes import (
    CubeStackDraft,
    CubeStackDraftEntry,
)
from substitute.application.ports import CubeCatalogRecord
from substitute.presentation.cube_picker.cube_stack_cart_modal import (
    CubeStackCartModal,
)
from substitute.presentation.cube_picker.cube_picker_card import (
    CUBE_PICKER_CARD_HEIGHT,
    CUBE_PICKER_CARD_WIDTH,
)
from substitute.presentation.cube_picker import CubeStagingDrawer


from tests.presentation.cube_picker.cart_modal.support import (
    _IconFactory,
    _app,
    _pack_catalog_classifications,
    _pack_catalog_records,
    _six_catalog_classifications,
    _six_catalog_records,
)


def test_cart_modal_library_cards_use_stack_card_visual_without_close_button() -> None:
    """Library cards should share stack-card dimensions without draft close controls."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    card = next(iter(modal._cards.values()))

    assert card.width() == CUBE_PICKER_CARD_WIDTH
    assert card.height() == CUBE_PICKER_CARD_HEIGHT
    assert not hasattr(card, "closeButton")
    assert card.findChildren(QLabel) == []


def test_cart_modal_library_cards_use_hover_and_press_visual_state() -> None:
    """Library cards should feed hover and press state into the shared visual."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    card = next(iter(modal._cards.values()))

    card.set_selected(False)
    idle_state = card._visual_state()
    card.set_selected(True)
    selected_state = card._visual_state()

    assert idle_state.selected is True
    assert selected_state.selected is True
    assert idle_state.hovered is False
    assert selected_state.hovered is False
    assert idle_state.pressed is False
    assert selected_state.pressed is False

    card._hovered = True
    hovered_state = card._visual_state()
    card._pressed = True
    pressed_state = card._visual_state()

    assert hovered_state.hovered is True
    assert hovered_state.pressed is False
    assert pressed_state.hovered is True
    assert pressed_state.pressed is True


def test_cart_modal_starts_from_initial_workflow_draft_and_reset_restores_it() -> None:
    """The cart stack should represent the real workflow draft on open."""

    _app()
    parent = QWidget()
    parent.resize(1000, 700)
    initial_entry = CubeStackDraftEntry(
        draft_id="existing:Text",
        source="existing",
        cube_id="cube-existing",
        display_name="Text",
        secondary_text="v1.0.0 - base-cubes",
        icon=None,
        existing_alias="Text",
    )
    modal = CubeStackCartModal(
        records=[
            CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
        ],
        initial_draft=CubeStackDraft(entries=(initial_entry,)),
        icon_factory=_IconFactory(),
        parent=parent,
    )

    assert modal._staging_stack.entries() == (initial_entry,)
    assert modal._apply_button.isEnabled() is False

    modal._stage_cube_from_library("cube-a")
    assert [entry.source for entry in modal._staging_stack.entries()] == [
        "existing",
        "new",
    ]
    assert modal._apply_button.isEnabled() is True

    modal._reset_draft_stack()

    assert modal._staging_stack.entries() == (initial_entry,)
    assert modal._apply_button.isEnabled() is False


def test_cart_modal_model_role_card_activation_stages_cube() -> None:
    """Activating a model-role card should stage the underlying cube id."""

    _app()
    modal = CubeStackCartModal(
        records=_pack_catalog_records(),
        classifications=_pack_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    modal._cards["SDXL/base-start.cube"].activated.emit("SDXL/base-start.cube")

    assert [entry.cube_id for entry in modal._staging_stack.entries()] == [
        "SDXL/base-start.cube"
    ]


def test_library_click_appends_copy_to_cart_stack() -> None:
    """Clicking a library card should add a new draft copy instead of accepting."""

    _app()
    modal = CubeStackCartModal(
        records=_six_catalog_records(),
        classifications=_six_catalog_classifications(),
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    modal._cards["inpaint"].activated.emit("inpaint")

    entries = modal._staging_stack.entries()
    assert [entry.cube_id for entry in entries] == ["inpaint"]
    assert entries[0].source == "new"
    assert modal._apply_button.isEnabled() is True


def test_edit_stack_returns_applied_draft_and_hides_modal() -> None:
    """Applying should return the draft result and close the modal."""

    _app()
    modal = CubeStackCartModal(
        records=[
            CubeCatalogRecord(cube_id="cube-a", version="1.0.0", display_name="A")
        ],
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )
    modal._stage_cube_from_library("cube-a")

    QTimer.singleShot(0, modal.accept)
    result = modal.edit_stack()

    assert result is not None
    assert [entry.cube_id for entry in result.entries] == ["cube-a"]
    assert modal.isHidden()


def test_legacy_staging_drawer_name_uses_cart_modal() -> None:
    """The old public staging name should resolve to the modal implementation."""

    _app()
    picker = CubeStagingDrawer(
        records=[],
        initial_draft=CubeStackDraft(entries=()),
        icon_factory=_IconFactory(),
        parent=QWidget(),
    )

    assert isinstance(picker, CubeStackCartModal)

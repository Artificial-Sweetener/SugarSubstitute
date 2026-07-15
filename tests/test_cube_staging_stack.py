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

"""Widget tests for the cube staging stack surface."""

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QIcon
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from substitute.application.cubes import CubeStackDraftEntry
from substitute.presentation.cube_picker.cube_drag_ghost import CubeDragGhost
from substitute.presentation.cube_picker.cube_staging_stack import CubeDraftStack
from substitute.presentation.cubes.cube_card_visual import CubeCardVisual
from substitute.presentation.cubes.cube_placeholder_card import CubePlaceholderCard
from substitute.presentation.cubes.cube_stack_metrics import (
    CUBE_ITEM_CLOSE_BUTTON_SIZE,
    CUBE_ITEM_EXPANDED_WIDTH,
    CUBE_ITEM_HEIGHT,
)


def _app() -> QApplication:
    """Return a QApplication for lightweight widget construction."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def test_staging_stack_keeps_duplicate_cube_types_distinct() -> None:
    """Staged entries are identified by staged id, not cube id."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a")
    second = _entry("copy-b")

    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())

    assert [entry.draft_id for entry in stack.entries()] == ["copy-a", "copy-b"]
    assert stack.staged_entry("copy-a") == first
    assert stack.staged_entry("copy-b") == second


def test_staging_stack_plans_new_aliases_around_existing_duplicates() -> None:
    """Visible staged aliases should keep existing entries locked."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a", display_name="Diffusion Upscale")
    existing = _existing_entry("existing:upscale", alias="Diffusion Upscale")
    second = _entry("copy-b", display_name="Diffusion Upscale")

    stack.set_entries([first, existing, second], icons={})
    stack.show()
    QApplication.processEvents()

    assert [stack.planned_alias_for(entry.draft_id) for entry in stack.entries()] == [
        "Diffusion Upscale 2",
        "Diffusion Upscale",
        "Diffusion Upscale 3",
    ]
    assert _card_accessible_names(stack) == [
        "Diffusion Upscale 2",
        "Diffusion Upscale",
        "Diffusion Upscale 3",
    ]


def test_staging_stack_removal_recomputes_new_aliases() -> None:
    """Removing one new duplicate should compact later planned suffixes."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a", display_name="Shared")
    existing = _existing_entry("existing:shared", alias="Shared")
    second = _entry("copy-b", display_name="Shared")
    stack.set_entries([first, existing, second], icons={})

    removed = stack.remove_staged_id("copy-a")

    assert removed == first
    assert stack.planned_alias_for("existing:shared") == "Shared"
    assert stack.planned_alias_for("copy-b") == "Shared 2"


def test_staging_stack_insert_recomputes_alias_above_existing_duplicate() -> None:
    """A new duplicate inserted before an existing card should receive the suffix."""

    _app()
    stack = CubeDraftStack()
    existing = _existing_entry("existing:shared", alias="Shared")
    new_entry = _entry("copy-a", display_name="Shared")
    stack.set_entries([existing], icons={})

    stack.insert_entry(0, new_entry, QIcon())

    assert [stack.planned_alias_for(entry.draft_id) for entry in stack.entries()] == [
        "Shared 2",
        "Shared",
    ]


def test_staging_stack_reorder_moves_new_suffix_ownership() -> None:
    """Reordering new duplicates should reassign generated suffixes by cart order."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a", display_name="Shared")
    second = _entry("copy-b", display_name="Shared")
    stack.set_entries([first, second], icons={})

    moved = stack.remove_staged_id("copy-a")
    assert moved == first
    stack.insert_entry(1, first, QIcon())

    assert stack.entries() == (second, first)
    assert stack.planned_alias_for("copy-b") == "Shared"
    assert stack.planned_alias_for("copy-a") == "Shared 2"


def test_staging_stack_removes_by_staged_id() -> None:
    """Removing one staged copy should leave other copies of the same cube."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a")
    second = _entry("copy-b")
    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())

    removed = stack.remove_staged_id("copy-a")

    assert removed == first
    assert stack.entries() == (second,)


def test_staging_stack_can_insert_after_empty_state_is_cleared() -> None:
    """Inserting after an empty rebuild should not reuse a deleted empty widget."""

    _app()
    stack = CubeDraftStack()
    QApplication.processEvents()

    stack.insert_entry(0, _entry("copy-a"), QIcon())
    QApplication.processEvents()
    stack.clear_entries()
    QApplication.processEvents()
    stack.insert_entry(0, _entry("copy-b"), QIcon())

    assert [entry.draft_id for entry in stack.entries()] == ["copy-b"]


def test_staging_stack_empty_placeholder_and_insertion_placeholder_are_exclusive() -> (
    None
):
    """Empty drop target and insertion placeholder should not both be visible."""

    _app()
    stack = CubeDraftStack()
    stack.show()
    QApplication.processEvents()

    empty_widgets = stack.findChildren(
        CubePlaceholderCard,
        "cubeStagingEmptyPlaceholder",
    )
    assert len(empty_widgets) == 1
    assert empty_widgets[0].isVisible() is True
    assert empty_widgets[0].isPlusVisible() is False
    assert empty_widgets[0].width() == CUBE_ITEM_EXPANDED_WIDTH
    assert empty_widgets[0].height() == CUBE_ITEM_HEIGHT

    stack.set_placeholder_index(0)
    QApplication.processEvents()

    placeholder_widgets = stack.findChildren(
        CubePlaceholderCard,
        "cubeStagingPlaceholder",
    )
    assert len(empty_widgets) == 1
    assert len(placeholder_widgets) == 1
    assert empty_widgets[0].isVisible() is False
    assert placeholder_widgets[0].isVisible() is True
    assert placeholder_widgets[0].width() == CUBE_ITEM_EXPANDED_WIDTH
    assert placeholder_widgets[0].height() <= CUBE_ITEM_HEIGHT


def test_staging_stack_placeholder_uses_shared_cube_placeholder_card() -> None:
    """Insertion feedback should use the shared cube placeholder visual."""

    _app()
    stack = CubeDraftStack()
    stack.show()
    QApplication.processEvents()

    stack.set_placeholder_index(0)
    QApplication.processEvents()

    placeholder = stack.findChildren(CubePlaceholderCard, "cubeStagingPlaceholder")[0]

    assert placeholder.isPlusVisible() is False
    assert placeholder.width() == CUBE_ITEM_EXPANDED_WIDTH
    assert placeholder.maximumHeight() <= CUBE_ITEM_HEIGHT
    assert placeholder.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_staging_stack_insertion_index_uses_pointer_y_position() -> None:
    """Drag insertion should track the stack card midpoint."""

    _app()
    stack = CubeDraftStack()
    stack.resize(280, 240)
    first = _entry("copy-a")
    second = _entry("copy-b")
    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())
    stack.show()
    QApplication.processEvents()

    assert stack.insertion_index_at_global_pos(stack.mapToGlobal(QPoint(20, 16))) == 0
    assert stack.insertion_index_at_global_pos(stack.mapToGlobal(QPoint(20, 230))) == 2


def test_draft_stack_and_drag_ghost_use_real_cube_stack_card_size() -> None:
    """Draft placement affordances should match real cube-stack card metrics."""

    _app()
    stack = CubeDraftStack()
    entry = _entry("copy-a")
    stack.insert_entry(0, entry, QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    ghost = CubeDragGhost(entry=entry, icon=QIcon(), parent=stack)

    assert card.size().width() == CUBE_ITEM_EXPANDED_WIDTH
    assert card.size().height() == CUBE_ITEM_HEIGHT
    assert ghost.size().width() == CUBE_ITEM_EXPANDED_WIDTH
    assert ghost.size().height() == CUBE_ITEM_HEIGHT


def test_draft_stack_card_exposes_real_stack_sized_close_button() -> None:
    """Draft cards should expose an X button matching real stack card metrics."""

    _app()
    stack = CubeDraftStack()
    entry = _entry("copy-a")
    stack.insert_entry(0, entry, QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    close_button = getattr(card, "closeButton")
    close_x = CubeCardVisual.close_button_x(
        CUBE_ITEM_EXPANDED_WIDTH,
        CUBE_ITEM_CLOSE_BUTTON_SIZE,
    )
    reserve_center = close_x + (CUBE_ITEM_CLOSE_BUTTON_SIZE / 2)

    assert close_button.isVisible() is True
    assert close_button.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert close_button.width() == CUBE_ITEM_CLOSE_BUTTON_SIZE
    assert close_button.height() == CUBE_ITEM_CLOSE_BUTTON_SIZE
    assert close_button.x() + (close_button.width() / 2) == reserve_center


def test_draft_stack_card_uses_painted_visual_without_label_hit_targets() -> None:
    """Draft card visuals should not add child labels that split the hit target."""

    _app()
    stack = CubeDraftStack()
    stack.insert_entry(0, _entry("copy-a"), QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    labels = card.findChildren(QLabel)

    assert card.testAttribute(Qt.WidgetAttribute.WA_SetCursor) is False
    assert card.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert labels == []


def test_draft_stack_card_close_button_is_only_mouse_child() -> None:
    """The shared painted card visual should leave only the X button as a child."""

    _app()
    stack = CubeDraftStack()
    stack.insert_entry(0, _entry("copy-a"), QIcon())
    stack.show()
    QApplication.processEvents()

    card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    close_button = getattr(card, "closeButton")
    labels = card.findChildren(QLabel)

    assert labels == []
    assert (
        close_button.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        is False
    )
    assert close_button.isEnabled() is True
    assert close_button.isVisible() is True


def test_draft_stack_card_close_button_requests_removal() -> None:
    """Clicking a draft-card X button should remove that card from the draft stack."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a")
    second = _entry("copy-b")
    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())
    stack.remove_requested.connect(stack.remove_staged_id)
    stack.show()
    QApplication.processEvents()

    first_card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    close_button = getattr(first_card, "closeButton")
    close_button.click()
    QApplication.processEvents()

    assert stack.entries() == (second,)


@pytest.mark.skipif(
    bool(os.environ.get("PYTEST_XDIST_WORKER")),
    reason="real Qt mouse delivery is verified in serial outside xdist",
)
def test_draft_stack_card_close_button_receives_mouse_clicks() -> None:
    """Mouse clicks on the X button should remove through the real button."""

    _app()
    stack = CubeDraftStack()
    first = _entry("copy-a")
    second = _entry("copy-b")
    stack.insert_entry(0, first, QIcon())
    stack.insert_entry(1, second, QIcon())
    stack.remove_requested.connect(stack.remove_staged_id)
    stack.show()
    QApplication.processEvents()

    first_card = stack.findChildren(QFrame, "cubeStagingCard")[0]
    close_button = getattr(first_card, "closeButton")
    QTest.mouseClick(
        close_button,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        close_button.rect().center(),
    )
    QApplication.processEvents()

    assert stack.entries() == (second,)


def _entry(
    staged_id: str,
    *,
    display_name: str = "Text to Image",
) -> CubeStackDraftEntry:
    """Return one draft entry for stack tests."""

    return CubeStackDraftEntry(
        draft_id=staged_id,
        source="new",
        cube_id="Example/Base-Cubes/text-to-image.cube",
        display_name=display_name,
        secondary_text="v1.0.0 - base-cubes",
        icon=None,
    )


def _existing_entry(staged_id: str, *, alias: str) -> CubeStackDraftEntry:
    """Return one existing draft entry for stack tests."""

    return CubeStackDraftEntry(
        draft_id=staged_id,
        source="existing",
        cube_id="Example/Base-Cubes/text-to-image.cube",
        display_name=alias,
        secondary_text="v1.0.0 - base-cubes",
        icon=None,
        existing_alias=alias,
    )


def _card_accessible_names(stack: CubeDraftStack) -> list[str]:
    """Return accessible names for rendered staging cards."""

    return [
        card.accessibleName() for card in stack.findChildren(QFrame, "cubeStagingCard")
    ]

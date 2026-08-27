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

"""Cube staging entry and alias-planning contracts."""

from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from substitute.presentation.cube_picker.cube_staging_stack import CubeDraftStack
from tests.presentation.cube_picker.support import (
    card_accessible_names as _card_accessible_names,
    ensure_application as _app,
    entry as _entry,
    existing_entry as _existing_entry,
)


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

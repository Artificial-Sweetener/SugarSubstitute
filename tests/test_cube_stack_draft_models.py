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

"""Tests for Qt-free cube stack draft models."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.cubes import (
    CubeStackDraftEntry,
    cube_stack_draft,
    cube_stack_draft_entry_from_record,
    cube_stack_draft_from_workflow,
    cube_stack_draft_result,
    plan_cube_stack_aliases,
)
from substitute.application.ports import CubeCatalogRecord


def test_workflow_draft_preserves_stack_order_and_existing_alias_display() -> None:
    """Existing workflow cubes should seed the drawer in stack order."""

    icon_descriptor = object()
    workflow = SimpleNamespace(
        stack_order=["Text", "Detailer"],
        cubes={
            "Text": SimpleNamespace(
                cube_id="Example/Base-Cubes/text-to-image.cube",
                version="1.0.0",
                display_name="Original display name",
                ui={"cube_icon": icon_descriptor},
            ),
            "Detailer": SimpleNamespace(
                cube_id="Example/Base-Cubes/automask-detailer.cube",
                version="2.0.0",
                display_name="Automask Detailer",
                ui={},
            ),
        },
    )

    draft = cube_stack_draft_from_workflow(workflow)

    assert [entry.display_name for entry in draft.entries] == ["Text", "Detailer"]
    assert [entry.existing_alias for entry in draft.entries] == ["Text", "Detailer"]
    assert [entry.source for entry in draft.entries] == ["existing", "existing"]
    assert draft.entries[0].secondary_text == "v1.0.0 · base-cubes"
    assert draft.entries[0].icon is icon_descriptor


def test_workflow_draft_skips_missing_stack_aliases() -> None:
    """Missing workflow aliases should not create unusable draft entries."""

    workflow = SimpleNamespace(
        stack_order=["Missing", "Present"],
        cubes={
            "Present": SimpleNamespace(
                cube_id="Example/Base-Cubes/present.cube",
                version="1.0.0",
                ui={},
            )
        },
    )

    draft = cube_stack_draft_from_workflow(workflow)

    assert [entry.display_name for entry in draft.entries] == ["Present"]


def test_catalog_draft_entries_allow_repeated_cube_ids_with_unique_draft_ids() -> None:
    """Dragging the same library cube more than once should create copies."""

    record = CubeCatalogRecord(
        cube_id="Example/Base-Cubes/text-to-image.cube",
        version="1.0.0",
        display_name="Text to Image",
    )

    first = cube_stack_draft_entry_from_record(record, draft_id="copy-a")
    second = cube_stack_draft_entry_from_record(record, draft_id="copy-b")
    result = cube_stack_draft_result([first, second])

    assert [entry.cube_id for entry in result.entries] == [
        "Example/Base-Cubes/text-to-image.cube",
        "Example/Base-Cubes/text-to-image.cube",
    ]
    assert [entry.source for entry in result.entries] == ["new", "new"]
    assert result.entries[0].secondary_text == "v1.0.0 · base-cubes"


def test_draft_result_detects_changes_from_initial_draft() -> None:
    """Draft results should expose no-op detection for the shell transaction."""

    entry = CubeStackDraftEntry(
        draft_id="existing:Text",
        source="existing",
        cube_id="cube-a",
        display_name="Text",
        secondary_text="v1.0.0",
        icon=None,
        existing_alias="Text",
    )
    initial = cube_stack_draft([entry])

    assert cube_stack_draft_result([entry]).has_changes_from(initial) is False
    assert cube_stack_draft_result([]).has_changes_from(initial) is True


def test_draft_validation_rejects_invalid_identity_and_source_shapes() -> None:
    """Draft entries should validate temporary ids and existing alias invariants."""

    existing = CubeStackDraftEntry(
        draft_id="existing:Text",
        source="existing",
        cube_id="cube-a",
        display_name="Text",
        secondary_text="v1.0.0",
        icon=None,
        existing_alias="Text",
    )
    missing_alias = CubeStackDraftEntry(
        draft_id="existing:Missing",
        source="existing",
        cube_id="cube-b",
        display_name="Missing",
        secondary_text="v1.0.0",
        icon=None,
        existing_alias=None,
    )
    new_with_alias = CubeStackDraftEntry(
        draft_id="copy-a",
        source="new",
        cube_id="cube-c",
        display_name="Copy",
        secondary_text="v1.0.0",
        icon=None,
        existing_alias="Copy",
    )

    with pytest.raises(ValueError, match="Draft cube ids must be unique"):
        cube_stack_draft_result([existing, existing])
    with pytest.raises(ValueError, match="Existing draft entries must include"):
        cube_stack_draft_result([missing_alias])
    with pytest.raises(ValueError, match="New draft entries must not include"):
        cube_stack_draft_result([new_with_alias])
    with pytest.raises(ValueError, match="Existing draft aliases must be unique"):
        cube_stack_draft_result(
            [
                existing,
                CubeStackDraftEntry(
                    draft_id="existing:Text-duplicate",
                    source="existing",
                    cube_id="cube-a",
                    display_name="Text",
                    secondary_text="v1.0.0",
                    icon=None,
                    existing_alias="Text",
                ),
            ]
        )


def test_alias_plan_locks_existing_aliases() -> None:
    """Existing cart entries should keep their workflow aliases exactly."""

    existing = _existing_entry("existing:upscale", "Diffusion Upscale")

    plan = plan_cube_stack_aliases([existing])

    planned = plan.planned_alias_for("existing:upscale")
    assert planned == "Diffusion Upscale"
    assert plan.alias_for("existing:upscale").locked is True
    assert plan.alias_for("existing:upscale").requested_alias == "Diffusion Upscale"


def test_alias_plan_assigns_new_aliases_around_locked_existing_duplicates() -> None:
    """New cart entries should resolve around existing aliases without renaming them."""

    entries = [
        _new_entry("copy-a", "Diffusion Upscale"),
        _existing_entry("existing:upscale", "Diffusion Upscale"),
        _new_entry("copy-b", "Diffusion Upscale"),
    ]

    plan = plan_cube_stack_aliases(entries)

    assert [plan.planned_alias_for(entry.draft_id) for entry in entries] == [
        "Diffusion Upscale 2",
        "Diffusion Upscale",
        "Diffusion Upscale 3",
    ]
    assert plan.alias_for("copy-a").locked is False
    assert plan.alias_for("copy-b").locked is False


def test_alias_plan_assigns_new_duplicates_by_cart_order() -> None:
    """Repeated new entries should receive suffixes according to draft order."""

    entries = [
        _new_entry("copy-a", "Shared"),
        _new_entry("copy-b", "Shared"),
        _new_entry("copy-c", "Shared"),
    ]

    plan = plan_cube_stack_aliases(entries)

    assert [plan.planned_alias_for(entry.draft_id) for entry in entries] == [
        "Shared",
        "Shared 2",
        "Shared 3",
    ]


def test_alias_plan_reordered_new_entries_move_suffix_ownership() -> None:
    """Changing cart order should change which draft id owns each generated suffix."""

    first = _new_entry("copy-a", "Shared")
    second = _new_entry("copy-b", "Shared")

    initial_plan = plan_cube_stack_aliases([first, second])
    reordered_plan = plan_cube_stack_aliases([second, first])

    assert initial_plan.planned_alias_for("copy-a") == "Shared"
    assert initial_plan.planned_alias_for("copy-b") == "Shared 2"
    assert reordered_plan.planned_alias_for("copy-b") == "Shared"
    assert reordered_plan.planned_alias_for("copy-a") == "Shared 2"


def test_alias_plan_reordered_existing_entries_keep_locked_aliases() -> None:
    """Changing existing entry order should not rename workflow-owned aliases."""

    first = _existing_entry("existing:shared", "Shared")
    second = _existing_entry("existing:shared-2", "Shared 2")

    plan = plan_cube_stack_aliases([second, first])

    assert plan.planned_alias_for("existing:shared") == "Shared"
    assert plan.planned_alias_for("existing:shared-2") == "Shared 2"


def test_alias_plan_reserves_existing_aliases_below_new_duplicates() -> None:
    """Existing aliases should reserve names globally before new entries resolve."""

    entries = [
        _new_entry("copy-a", "Shared"),
        _new_entry("copy-b", "Shared"),
        _existing_entry("existing:shared", "Shared"),
    ]

    plan = plan_cube_stack_aliases(entries)

    assert [plan.planned_alias_for(entry.draft_id) for entry in entries] == [
        "Shared 2",
        "Shared 3",
        "Shared",
    ]


def test_alias_plan_empty_entries_are_supported() -> None:
    """Empty cart drafts should produce an empty alias plan."""

    plan = plan_cube_stack_aliases([])

    assert plan.aliases_by_draft_id == {}
    with pytest.raises(KeyError):
        plan.planned_alias_for("missing")


def test_alias_plan_rejects_invalid_draft_entries() -> None:
    """Planning should reuse draft validation rather than accepting invalid state."""

    invalid = _existing_entry("existing:missing", "Missing")
    invalid = CubeStackDraftEntry(
        draft_id=invalid.draft_id,
        source=invalid.source,
        cube_id=invalid.cube_id,
        display_name=invalid.display_name,
        secondary_text=invalid.secondary_text,
        icon=invalid.icon,
        existing_alias=None,
    )

    with pytest.raises(ValueError, match="Existing draft entries must include"):
        plan_cube_stack_aliases([invalid])


def _existing_entry(draft_id: str, alias: str) -> CubeStackDraftEntry:
    """Build one existing draft entry for alias planning tests."""

    return CubeStackDraftEntry(
        draft_id=draft_id,
        source="existing",
        cube_id=f"{alias}.cube",
        display_name=alias,
        secondary_text="v1.0.0",
        icon=None,
        existing_alias=alias,
    )


def _new_entry(draft_id: str, display_name: str) -> CubeStackDraftEntry:
    """Build one new draft entry for alias planning tests."""

    return CubeStackDraftEntry(
        draft_id=draft_id,
        source="new",
        cube_id=f"{display_name}.cube",
        display_name=display_name,
        secondary_text="v1.0.0",
        icon=None,
        existing_alias=None,
    )

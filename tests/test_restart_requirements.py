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

"""Tests for process-local restart requirement deltas."""

from __future__ import annotations

import pytest

from substitute.application.restart_requirements import (
    RestartRequirementItem,
    RestartRequirementService,
    RestartScope,
)


def test_restart_requirement_service_adds_delta_when_saved_differs() -> None:
    """A changed saved value should appear as one pending restart item."""

    service = RestartRequirementService()

    snapshot = service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="E:\\ImageGen Models",
        saved_value="F:\\Models",
        scope=RestartScope.FULL_APP,
        detail="ComfyUI will use this folder after restart.",
    )

    assert snapshot.count == 1
    assert snapshot.required_scope is RestartScope.FULL_APP
    assert snapshot.items[0].key == "comfy.model_root"
    assert snapshot.items[0].label == "Model folder"
    assert snapshot.items[0].detail == "ComfyUI will use this folder after restart."


def test_restart_requirement_service_updates_existing_key() -> None:
    """Registering the same key should replace the old pending item in place."""

    service = RestartRequirementService()

    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )
    snapshot = service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="C",
        scope=RestartScope.FULL_APP,
    )

    assert snapshot.count == 1
    assert snapshot.items[0].saved_value == "C"


def test_restart_requirement_service_clears_when_saved_matches_active() -> None:
    """Changing a setting back to the active value should clear its restart item."""

    service = RestartRequirementService()

    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )
    snapshot = service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="A",
        scope=RestartScope.FULL_APP,
    )

    assert snapshot.count == 0
    assert snapshot.required_scope is RestartScope.NONE


def test_restart_requirement_service_preserves_insertion_order_and_max_scope() -> None:
    """Snapshots should keep stable item order and report the most expensive scope."""

    service = RestartRequirementService()

    service.register_delta(
        key="appearance.theme",
        label="Theme",
        active_value="dark",
        saved_value="light",
        scope=RestartScope.WINDOW,
    )
    snapshot = service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )

    assert [item.key for item in snapshot.items] == [
        "appearance.theme",
        "comfy.model_root",
    ]
    assert snapshot.required_scope is RestartScope.FULL_APP


def test_restart_requirement_service_notifies_observers_on_mutation() -> None:
    """Observers should receive snapshots when pending restart state changes."""

    service = RestartRequirementService()
    observed_counts: list[int] = []
    service.add_observer(lambda snapshot: observed_counts.append(snapshot.count))

    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )
    service.clear("comfy.model_root")

    assert observed_counts == [1, 0]


def test_restart_requirement_service_removes_observers() -> None:
    """Removed observers should stop receiving changed snapshots."""

    service = RestartRequirementService()
    observed_counts: list[int] = []

    def observe(snapshot: object) -> None:
        """Record one observer call."""

        _ = snapshot
        observed_counts.append(1)

    service.add_observer(observe)
    service.remove_observer(observe)

    service.register_delta(
        key="comfy.model_root",
        label="Model folder",
        active_value="A",
        saved_value="B",
        scope=RestartScope.FULL_APP,
    )

    assert observed_counts == []


def test_restart_requirement_item_rejects_invalid_values() -> None:
    """Invalid pending items should fail before they reach presentation code."""

    with pytest.raises(ValueError, match="key"):
        RestartRequirementItem(
            key=" ",
            label="Model folder",
            active_value="A",
            saved_value="B",
            scope=RestartScope.FULL_APP,
        )
    with pytest.raises(ValueError, match="label"):
        RestartRequirementItem(
            key="comfy.model_root",
            label=" ",
            active_value="A",
            saved_value="B",
            scope=RestartScope.FULL_APP,
        )
    with pytest.raises(ValueError, match="scope"):
        RestartRequirementItem(
            key="comfy.model_root",
            label="Model folder",
            active_value="A",
            saved_value="B",
            scope=RestartScope.NONE,
        )

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

"""Verify grouped-field registrations across node-card rebuilds."""

from __future__ import annotations

from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.field_sync_controller import (
    EditorPanelFieldSyncController,
    EditorPanelFieldSyncHost,
)
from tests.presentation.editor.node_card.rebuild.support import (
    create_rebuild_scenario,
    ksampler_definitions,
    ksampler_inputs,
)


def test_rebuild_replaces_stale_column_widget_registrations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Register the widgets belonging to the current grouped-row generation."""

    scenario = create_rebuild_scenario(
        monkeypatch,
        node_name="ksampler",
        node_type="KSampler",
    )
    definitions = ksampler_definitions()
    inputs = ksampler_inputs()
    first_wrapper = scenario.build(inputs=inputs, definitions=definitions)
    sampler_key = ("A", "ksampler", "sampler_name")
    scheduler_key = ("A", "ksampler", "scheduler")
    first_sampler_registration = scenario.panel.col_widgets[sampler_key]
    first_scheduler_registration = scenario.panel.col_widgets[scheduler_key]
    second_wrapper = scenario.build(inputs=inputs, definitions=definitions)
    try:
        second_sampler_registration = scenario.panel.col_widgets[sampler_key]
        second_scheduler_registration = scenario.panel.col_widgets[scheduler_key]
        assert second_sampler_registration[0] is second_scheduler_registration[0]
        assert second_sampler_registration[1] is not first_sampler_registration[1]
        assert second_scheduler_registration[1] is not first_scheduler_registration[1]
        assert (
            scenario.panel.row_widgets[sampler_key][1] is second_sampler_registration[0]
        )
    finally:
        scenario.destroy(first_wrapper, second_wrapper)


def test_rebuild_removes_columns_missing_from_current_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remove registrations for grouped columns absent from the new card."""

    scenario = create_rebuild_scenario(
        monkeypatch,
        node_name="ksampler",
        node_type="KSampler",
    )
    initial_wrapper = scenario.build(
        inputs=ksampler_inputs(),
        definitions=ksampler_definitions(),
    )
    scheduler_key = ("A", "ksampler", "scheduler")
    assert scheduler_key in scenario.panel.col_widgets
    rebuilt_wrapper = scenario.build(
        inputs=ksampler_inputs(include_scheduler=False),
        definitions=ksampler_definitions(include_scheduler=False),
    )
    try:
        assert scheduler_key not in scenario.panel.col_widgets
        assert scheduler_key not in scenario.panel.row_widgets
        assert scheduler_key not in scenario.panel.input_widgets_by_field_key
    finally:
        scenario.destroy(initial_wrapper, rebuilt_wrapper)


def test_rebuild_applies_partial_global_override_visibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Honor left-only, right-only, whole-row, and restored visibility."""

    scenario = create_rebuild_scenario(
        monkeypatch,
        node_name="ksampler",
        node_type="KSampler",
    )
    stale_wrapper = scenario.build(
        inputs=ksampler_inputs(),
        definitions=ksampler_definitions(),
    )
    wrapper = scenario.build(
        inputs=ksampler_inputs(),
        definitions=ksampler_definitions(),
    )
    try:
        sampler_key = ("A", "ksampler", "sampler_name")
        scheduler_key = ("A", "ksampler", "scheduler")
        row_container, sampler_column, _ = scenario.panel.col_widgets[sampler_key]
        scheduler_row, scheduler_column, _ = scenario.panel.col_widgets[scheduler_key]
        assert isinstance(row_container, QWidget)
        assert isinstance(sampler_column, QWidget)
        assert isinstance(scheduler_column, QWidget)
        assert row_container is scheduler_row
        assert scenario.panel.row_widgets[sampler_key][1] is row_container

        controller = EditorPanelFieldSyncController(
            cast(EditorPanelFieldSyncHost, scenario.panel)
        )
        controller.apply_hidden_field_keys({scheduler_key})
        assert not row_container.isHidden()
        assert not sampler_column.isHidden()
        assert scheduler_column.isHidden()

        controller.apply_hidden_field_keys({sampler_key})
        assert not row_container.isHidden()
        assert sampler_column.isHidden()
        assert not scheduler_column.isHidden()

        controller.apply_hidden_field_keys({sampler_key, scheduler_key})
        assert row_container.isHidden()
        assert sampler_column.isHidden()
        assert scheduler_column.isHidden()

        controller.apply_hidden_field_keys(set())
        assert not row_container.isHidden()
        assert not sampler_column.isHidden()
        assert not scheduler_column.isHidden()
    finally:
        scenario.destroy(stale_wrapper, wrapper)

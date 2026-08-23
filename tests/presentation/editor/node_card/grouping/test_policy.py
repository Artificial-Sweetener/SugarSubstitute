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

"""Verify field-group ordering and grouped-row composition."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QWidget

from substitute.presentation.editor.panel.field_grouping import (
    group_visible_field_keys,
)
from tests.presentation.editor.node_card.builder_support import build_node_card_builder
from tests.presentation.editor.node_card.support import (
    Gateway,
    WidgetPanel,
    content_body_for,
    content_layout_for,
    ensure_qapp,
)
from tests.support.node_behavior import build_behavior_snapshot
from tests.support.qt.lifecycle import destroy_qt_object


def test_override_groups_follow_input_discovery_order() -> None:
    """Emit configured groups at the position of their first discovered key."""

    groups = group_visible_field_keys(
        input_keys=["steps", "foo", "scheduler", "sampler_name", "cfg"],
        field_groups=(("sampler_name", "scheduler"), ("steps", "cfg")),
        skip_keys=set(),
    )

    assert groups == [["steps", "cfg"], ["foo"], ["sampler_name", "scheduler"]]


def test_inferred_sampler_groups_apply_without_overrides() -> None:
    """Group the common KSampler pairs derived by node behavior."""

    cube = SimpleNamespace(
        buffer={
            "nodes": {
                "ksampler": {
                    "class_type": "KSampler",
                    "inputs": {
                        "steps": 20,
                        "cfg": 7.0,
                        "sampler_name": "euler",
                        "scheduler": "normal",
                    },
                }
            },
            "definitions": {},
        },
        ui={},
    )
    behavior = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
    ).resolved_nodes_by_alias["A"]["ksampler"]

    groups = group_visible_field_keys(
        input_keys=["steps", "cfg", "sampler_name", "scheduler", "seed"],
        field_groups=behavior.field_groups,
        skip_keys=set(),
    )

    assert groups == [["steps", "cfg"], ["sampler_name", "scheduler"], ["seed"]]


def test_inferred_dimension_pair_forms_one_group() -> None:
    """Group dimensions sharing a resolved semantic stem."""

    cube = SimpleNamespace(
        buffer={
            "nodes": {
                "resize": {
                    "class_type": "CustomResize",
                    "inputs": {
                        "mode": "fit",
                        "source_width": 512,
                        "source_height": 768,
                    },
                }
            },
            "definitions": {},
        },
        ui={},
    )
    behavior = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
    ).resolved_nodes_by_alias["A"]["resize"]

    groups = group_visible_field_keys(
        input_keys=["mode", "source_width", "source_height"],
        field_groups=behavior.field_groups,
        skip_keys=set(),
    )

    assert groups == [["mode"], ["source_width", "source_height"]]


def test_unmatched_dimension_stems_remain_independent() -> None:
    """Keep dimensions with different semantic stems in separate rows."""

    cube = SimpleNamespace(
        buffer={
            "nodes": {
                "resize": {
                    "class_type": "CustomResize",
                    "inputs": {"source_width": 512, "target_height": 768},
                }
            },
            "definitions": {},
        },
        ui={},
    )
    behavior = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
    ).resolved_nodes_by_alias["A"]["resize"]

    groups = group_visible_field_keys(
        input_keys=["source_width", "target_height"],
        field_groups=behavior.field_groups,
        skip_keys=set(),
    )

    assert groups == [["source_width"], ["target_height"]]


def test_detailer_steps_and_cfg_build_as_one_grouped_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Render the inferred DetailerForEach pair through one row owner."""

    ensure_qapp()
    node_name = "detailer_segs"
    node_type = "DetailerForEach"
    definitions: dict[str, dict[str, object]] = {
        node_type: {"input": {"required": {"steps": ["INT"], "cfg": ["FLOAT"]}}}
    }
    inputs: dict[str, object] = {"steps": 8, "cfg": 7.0}
    nodes: dict[str, dict[str, object]] = {
        node_name: {"class_type": node_type, "inputs": inputs}
    }
    cube_state = SimpleNamespace(
        buffer={"nodes": nodes, "definitions": definitions},
        ui={},
    )
    panel = WidgetPanel()
    panel._stack_order = ["A"]
    panel._cube_states = {"A": cube_state}
    snapshot = build_behavior_snapshot(
        cube_states={"A": cube_state},
        stack_order=["A"],
        definitions_by_class=definitions,
    )
    builder = build_node_card_builder(panel, Gateway())
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.node_card_builder.build_widget_for_field_spec",
        lambda **_kwargs: QWidget(panel),
    )

    wrapper = builder.build_node_card(
        node_name=node_name,
        inputs=inputs,
        node_type=node_type,
        field_specs=snapshot.field_specs_by_alias["A"][node_name],
        cube_state=cube_state,
        resolved_behavior=snapshot.resolved_nodes_by_alias["A"][node_name],
        display_decision=snapshot.card_decisions_by_alias["A"][node_name],
        alias="A",
    )
    try:
        assert wrapper is not None
        assert snapshot.resolved_nodes_by_alias["A"][node_name].field_groups == (
            ("steps", "cfg"),
        )
        steps_key = ("A", node_name, "steps")
        cfg_key = ("A", node_name, "cfg")
        assert steps_key in panel.col_widgets
        assert cfg_key in panel.col_widgets
        steps_registration = panel.col_widgets[steps_key]
        cfg_registration = panel.col_widgets[cfg_key]
        assert isinstance(steps_registration, tuple)
        assert isinstance(cfg_registration, tuple)
        assert steps_registration[0] is cfg_registration[0]

        content_layout = content_layout_for(content_body_for(wrapper))
        assert content_layout.count() == 2
    finally:
        if wrapper is not None:
            destroy_qt_object(wrapper)
        destroy_qt_object(panel)

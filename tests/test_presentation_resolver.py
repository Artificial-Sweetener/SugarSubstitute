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

"""Contract tests for layered node-behavior resolution."""

from __future__ import annotations

from substitute.application.node_behavior import (
    EnabledSwitchPolicy,
    NodeBehaviorContext,
    resolve_node_behavior,
)
from tests.node_behavior_test_helpers import behavior_payload


def _context(*, node_name: str, class_type: str, patch=None) -> NodeBehaviorContext:
    return NodeBehaviorContext(
        stack_order=("A",),
        cube_alias="A",
        node_name=node_name,
        class_type=class_type,
        node_title=None,
        live_node_definition=None,
        declarative_patch=patch,
        hook_patch=None,
        workflow_overrides={},
        node_instance_patch=None,
    )


def test_should_hide_node_overrides_by_class_string():
    patch = behavior_payload({"hide": {"nodes": ["KSampler", {"class": "XYZ"}]}})
    resolved = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=(),
        context=_context(node_name="ksampler", class_type="KSampler", patch=patch),
    )
    assert resolved.card.hidden is False
    assert "KSampler" in patch.hidden_strings


def test_enabled_switch_precedence():
    patch = behavior_payload(
        {
            "controls": {
                "by_class": {"KSampler": {"enabled_switch": False}},
                "by_node": {"ksampler": {"enabled_switch": True}},
            }
        }
    )
    by_node = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=(),
        context=_context(node_name="ksampler", class_type="KSampler", patch=patch),
    )
    by_class = resolve_node_behavior(
        node_name="other",
        class_type="KSampler",
        input_keys=(),
        context=_context(node_name="other", class_type="KSampler", patch=patch),
    )
    no_rule = resolve_node_behavior(
        node_name="other",
        class_type="Other",
        input_keys=(),
        context=_context(node_name="other", class_type="Other", patch=patch),
    )

    assert by_node.card.enabled_switch_policy == EnabledSwitchPolicy.ALWAYS
    assert by_class.card.enabled_switch_policy == EnabledSwitchPolicy.NEVER
    assert no_rule.card.enabled_switch_policy == EnabledSwitchPolicy.AUTO


def test_groups_for_variants():
    patch = behavior_payload({"layout": {"groups": {"VectorscopeCC": [["x", "y"]]}}})
    grouped = resolve_node_behavior(
        node_name="vectorscope",
        class_type="VectorscopeCC",
        input_keys=("x", "y"),
        context=_context(
            node_name="vectorscope",
            class_type="VectorscopeCC",
            patch=patch,
        ),
    )
    ksampler = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=("sampler_name", "scheduler", "steps", "cfg"),
        context=_context(node_name="ksampler", class_type="KSampler"),
    )

    assert grouped.field_groups == (("x", "y"),)
    assert ksampler.field_groups == (
        ("sampler_name", "scheduler"),
        ("steps", "cfg"),
    )


def test_empty_latent_image_groups_dimensions_from_generic_behavior() -> None:
    """EmptyLatentImage should keep width/height grouping through generic inference."""

    resolved = resolve_node_behavior(
        node_name="latent",
        class_type="EmptyLatentImage",
        input_keys=("width", "height", "batch_size"),
        context=_context(node_name="latent", class_type="EmptyLatentImage"),
    )

    assert resolved.field_groups == (("width", "height"),)


def test_empty_authored_groups_override_default_grouping() -> None:
    """Explicit empty group declarations should suppress default grouping."""

    patch = behavior_payload({"by_node": {"latent": {"groups": []}}})
    resolved = resolve_node_behavior(
        node_name="latent",
        class_type="EmptyLatentImage",
        input_keys=("width", "height", "batch_size"),
        context=_context(
            node_name="latent",
            class_type="EmptyLatentImage",
            patch=patch,
        ),
    )

    assert resolved.field_groups == ()


def test_field_style_for_maps_to_resolved_field_behavior():
    patch = behavior_payload(
        {
            "controls": {
                "by_field": {
                    "Node.gain": {
                        "control": "color_slider",
                        "style": {"start": "#00b2ff", "end": "#ffd000"},
                        "column_span": 2,
                    }
                }
            }
        }
    )
    resolved = resolve_node_behavior(
        node_name="Node",
        class_type="VectorscopeCC",
        input_keys=("gain",),
        context=_context(node_name="Node", class_type="VectorscopeCC", patch=patch),
    )

    field = resolved.fields["gain"]
    assert field.control_name == "color_slider"
    assert field.column_span == 2
    assert field.style == {"start": "#00b2ff", "end": "#ffd000"}

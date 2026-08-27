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

"""Verify common and dimension group inference."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    NodeBehaviorPatch,
    PackageBehaviorPatch,
    resolve_node_behavior,
)
from tests.domain.node_behavior.resolver.support import context


def test_resolver_infers_unqualified_dimension_groups() -> None:
    """Custom nodes with width and height should resolve a dimension group."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("foo", "width", "height", "bar"),
        context=context(),
    )

    assert resolved.field_groups == (("width", "height"),)


def test_resolver_infers_stemmed_dimension_groups() -> None:
    """Shared dimension stems should resolve independent width/height groups."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=(
            "source_width",
            "source_height",
            "target_width",
            "target_height",
        ),
        context=context(),
    )

    assert resolved.field_groups == (
        ("source_width", "source_height"),
        ("target_width", "target_height"),
    )


def test_resolver_does_not_infer_mixed_stem_dimension_groups() -> None:
    """Width and height fields with different stems should remain ungrouped."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("source_width", "target_height", "width"),
        context=context(),
    )

    assert resolved.field_groups == ()


def test_resolver_infers_steps_cfg_common_group_for_arbitrary_class() -> None:
    """Any node with steps and cfg should resolve the common scalar group."""

    resolved = resolve_node_behavior(
        node_name="sampler_like",
        class_type="CustomSampler",
        input_keys=("seed", "steps", "cfg"),
        context=context(node_name="sampler_like", class_type="CustomSampler"),
    )

    assert resolved.field_groups == (("steps", "cfg"),)


def test_resolver_infers_steps_cfg_common_group_for_detailer() -> None:
    """DetailerForEach should group steps and cfg without a class-specific patch."""

    resolved = resolve_node_behavior(
        node_name="detailer_segs",
        class_type="DetailerForEach",
        input_keys=("guide_size", "steps", "cfg", "denoise"),
        context=context(node_name="detailer_segs", class_type="DetailerForEach"),
    )

    assert resolved.field_groups == (("steps", "cfg"),)


def test_resolver_does_not_infer_partial_steps_cfg_common_group() -> None:
    """Steps and cfg should not group unless both fields are present."""

    steps_only = resolve_node_behavior(
        node_name="steps_only",
        class_type="CustomSampler",
        input_keys=("seed", "steps"),
        context=context(node_name="steps_only", class_type="CustomSampler"),
    )
    cfg_only = resolve_node_behavior(
        node_name="cfg_only",
        class_type="CustomSampler",
        input_keys=("seed", "cfg"),
        context=context(node_name="cfg_only", class_type="CustomSampler"),
    )

    assert steps_only.field_groups == ()
    assert cfg_only.field_groups == ()


def test_resolver_infers_sampler_scheduler_common_group_for_arbitrary_class() -> None:
    """Any node with sampler_name and scheduler should resolve the common group."""

    resolved = resolve_node_behavior(
        node_name="sampler_like",
        class_type="CustomSampler",
        input_keys=("sampler_name", "scheduler", "seed"),
        context=context(node_name="sampler_like", class_type="CustomSampler"),
    )

    assert resolved.field_groups == (("sampler_name", "scheduler"),)


def test_resolver_authored_groups_override_inferred_common_groups() -> None:
    """Explicit authored groups should remain authoritative over common inference."""

    declarative = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(field_groups=(("steps", "seed"),)),
        }
    )
    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("seed", "sampler_name", "scheduler", "steps", "cfg"),
        context=context(declarative_patch=declarative),
    )

    assert resolved.field_groups == (("steps", "seed"),)


def test_resolver_appends_dimensions_after_common_groups() -> None:
    """Dimension groups should remain inferred after non-conflicting common groups."""

    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("width", "height", "steps", "cfg"),
        context=context(),
    )

    assert resolved.field_groups == (("steps", "cfg"), ("width", "height"))


def test_resolver_appends_dimension_groups_after_host_defaults() -> None:
    """Common groups should resolve before non-conflicting dimensions are appended."""

    resolved = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=("sampler_name", "scheduler", "steps", "cfg", "width", "height"),
        context=context(node_name="ksampler", class_type="KSampler"),
    )

    assert resolved.field_groups == (
        ("sampler_name", "scheduler"),
        ("steps", "cfg"),
        ("width", "height"),
    )

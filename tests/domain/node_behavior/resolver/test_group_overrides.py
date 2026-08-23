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

"""Verify authored group overrides and conflicts."""

from __future__ import annotations

from substitute.domain.node_behavior import (
    NodeBehaviorPatch,
    PackageBehaviorPatch,
    resolve_node_behavior,
)
from tests.domain.node_behavior.resolver.support import context


def test_resolver_authored_groups_override_inferred_dimension_groups() -> None:
    """Declarative groups should remain authoritative over dimension inference."""

    declarative = PackageBehaviorPatch(
        by_node={
            "node": NodeBehaviorPatch(field_groups=(("width", "steps"),)),
        }
    )
    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("width", "height", "steps"),
        context=context(declarative_patch=declarative),
    )

    assert resolved.field_groups == (("width", "steps"),)


def test_resolver_empty_authored_groups_opt_out_of_dimension_inference() -> None:
    """An explicit empty group override should suppress inferred dimensions."""

    declarative = PackageBehaviorPatch(
        by_node={"node": NodeBehaviorPatch(field_groups=())}
    )
    resolved = resolve_node_behavior(
        node_name="node",
        class_type="CustomNode",
        input_keys=("width", "height"),
        context=context(declarative_patch=declarative),
    )

    assert resolved.field_groups == ()


def test_resolver_skips_dimensions_that_conflict_with_existing_groups() -> None:
    """Inferred dimensions should not reuse fields already owned by common groups."""

    resolved = resolve_node_behavior(
        node_name="ksampler",
        class_type="KSampler",
        input_keys=("steps", "cfg", "height", "source_width", "source_height"),
        context=context(node_name="ksampler", class_type="KSampler"),
    )

    assert resolved.field_groups == (
        ("steps", "cfg"),
        ("source_width", "source_height"),
    )

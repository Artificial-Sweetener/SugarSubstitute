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

"""Contract tests for reusable prompt conditioning context and topology."""

from __future__ import annotations

from substitute.application.prompt_editor.conditioning import (
    PromptConditioningContext,
    PromptConditioningMode,
    PromptConditioningScopeRole,
    PromptConditioningTopologyService,
    PromptConditioningTopology,
)
from substitute.application.prompt_editor.document.projector import (
    PromptDocumentProjector,
)
from substitute.domain.links.prompt_endpoints import PromptEndpoint
from substitute.domain.node_behavior.models import PromptRole


def test_independent_sep_partitions_are_distinct_emitted_roots() -> None:
    """Detailer-style separator partitions should not inherit from each other."""

    text = "first\n[SEP]\nsecond\n[SEP]\nthird"
    topology = _topology(text, PromptConditioningMode.INDEPENDENT)

    assert [scope.role for scope in topology.scopes] == [
        PromptConditioningScopeRole.CONDITION,
        PromptConditioningScopeRole.CONDITION,
        PromptConditioningScopeRole.CONDITION,
    ]
    assert topology.root_scopes == topology.scopes
    assert topology.emitted_scopes == topology.scopes
    assert [
        tuple(
            source_range.slice(text)
            for source_range in topology.effective_source_ranges(scope.scope_id)
        )
        for scope in topology.emitted_scopes
    ] == [("first\n",), ("second\n",), ("third",)]


def test_unresolved_sep_context_fails_closed_to_independent_roots() -> None:
    """Unavailable workflow context should avoid false cross-partition inheritance."""

    topology = _topology(
        "first\n[SEP]\nsecond",
        PromptConditioningMode.UNRESOLVED,
    )

    assert topology.root_scopes == topology.scopes
    assert topology.emitted_scopes == topology.scopes


def test_regional_sep_partitions_inherit_global_scope_independently() -> None:
    """Regional conditions should share global source without sharing sibling source."""

    text = "global\n[SEP]\nred\n[SEP]\nblue"
    topology = _topology(text, PromptConditioningMode.REGIONAL)

    assert topology.scopes[0].role is PromptConditioningScopeRole.GLOBAL
    assert not topology.scopes[0].emits_condition
    assert [scope.role for scope in topology.emitted_scopes] == [
        PromptConditioningScopeRole.REGION,
        PromptConditioningScopeRole.REGION,
    ]
    assert [
        tuple(
            source_range.slice(text)
            for source_range in topology.effective_source_ranges(scope.scope_id)
        )
        for scope in topology.emitted_scopes
    ] == [("global\n", "red\n"), ("global\n", "blue")]


def test_conditioning_topology_exposes_source_partition_queries() -> None:
    """Consumers should resolve source ownership without parsing separator syntax."""

    text = "global\n[SEP]\nregion"
    topology = _topology(text, PromptConditioningMode.REGIONAL)

    assert topology.scope_at_source_position(1) == topology.scope_for_partition(0)
    assert topology.scope_at_source_position(
        text.index("region")
    ) == topology.scope_for_partition(1)
    assert topology.scope_at_source_position(text.index("[SEP]")) is None
    assert topology.children_of("partition:0") == (topology.scope_for_partition(1),)


def test_conditioning_topology_preserves_named_separator_source_boundaries() -> None:
    """Topology ranges should derive from canonical parsing without rewriting source."""

    text = "global  \r\n[SEP|Face]\r\n region"
    topology = _topology(text, PromptConditioningMode.REGIONAL)

    region = topology.emitted_scopes[0]
    assert tuple(
        source_range.slice(text)
        for source_range in topology.effective_source_ranges(region.scope_id)
    ) == ("global  \r\n", " region")
    assert topology.scope_at_source_position(text.index("[SEP|Face]")) is None


def test_separator_free_prompt_is_one_condition_in_every_context() -> None:
    """Graph context should not invent batches when the source has no separators."""

    for mode in PromptConditioningMode:
        topology = _topology("one prompt", mode)
        assert len(topology.scopes) == 1
        assert topology.scopes[0].role is PromptConditioningScopeRole.CONDITION
        assert topology.emitted_scopes == topology.scopes


def _topology(
    text: str,
    mode: PromptConditioningMode,
) -> PromptConditioningTopology:
    """Build topology for one stable test endpoint and prompt source."""

    endpoint = PromptEndpoint(
        cube_alias="cube",
        role=PromptRole.POSITIVE,
        node_name="prompt",
        field_key="value",
    )
    context = PromptConditioningContext(mode=mode, endpoint=endpoint)
    document_view = PromptDocumentProjector().build_document_view(text)
    return PromptConditioningTopologyService().build(
        context,
        document_view.region_structure,
    )

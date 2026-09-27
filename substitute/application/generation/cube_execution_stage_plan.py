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

"""Freeze authored Cube order for one graph-backed generation run."""

from __future__ import annotations

from substitute.domain.workflow import WorkflowState


def cube_execution_stage_ids(workflow: WorkflowState) -> tuple[str, ...]:
    """Return active Cube identities in the order displayed by Substitute."""

    document = workflow.direct_workflow
    analysis = document.cube_analysis if document is not None else None
    if not workflow.is_graph_backed_cube_workflow or analysis is None:
        raise ValueError("Graph-backed Cube order is unavailable for execution.")
    instances = {instance.instance_id: instance for instance in analysis.instances}
    ordered_ids = tuple(
        instance_id
        for segment in analysis.segments
        for instance_id in segment.instance_ids
    )
    if any(instance_id not in instances for instance_id in ordered_ids):
        raise ValueError("Cube execution order contains an unknown instance.")
    if len(ordered_ids) != len(set(ordered_ids)):
        raise ValueError("Cube execution order contains duplicate instances.")
    ordered_ids = tuple(
        instance_id
        for instance_id in ordered_ids
        if instances[instance_id].execution_mode not in {2, 4}
    )
    active_ids = {
        instance.instance_id
        for instance in analysis.instances
        if instance.execution_mode not in {2, 4}
    }
    if set(ordered_ids) != active_ids:
        raise ValueError("Cube execution order does not cover active instances.")
    aliases = tuple(instances[instance_id].alias for instance_id in ordered_ids)
    active_aliases = tuple(
        alias for alias in workflow.stack_order if not workflow.cubes[alias].bypassed
    )
    if aliases != active_aliases:
        raise ValueError("Cube execution order differs from the visible stack.")
    positions = {instance_id: index for index, instance_id in enumerate(ordered_ids)}
    if any(
        positions[edge.source_instance_id] >= positions[edge.target_instance_id]
        for edge in analysis.edges
        if edge.source_instance_id in positions and edge.target_instance_id in positions
    ):
        raise ValueError("Cube execution order conflicts with graph dependencies.")
    return ordered_ids


def cube_execution_stages(workflow: WorkflowState) -> tuple[tuple[str, ...], ...]:
    """Group connected Cubes and order independent groups by authored position."""

    ordered_ids = cube_execution_stage_ids(workflow)
    if not ordered_ids:
        return ()
    document = workflow.direct_workflow
    assert document is not None
    analysis = document.cube_analysis
    assert analysis is not None
    nodes = document.source_workflow.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != len(analysis.instances):
        return (ordered_ids,)

    connected: dict[str, set[str]] = {
        instance_id: {instance_id} for instance_id in ordered_ids
    }
    for edge in analysis.edges:
        if (
            edge.source_instance_id not in connected
            or edge.target_instance_id not in connected
        ):
            continue
        group = connected[edge.source_instance_id] | connected[edge.target_instance_id]
        for instance_id in group:
            connected[instance_id] = group
    stages: list[tuple[str, ...]] = []
    seen: set[str] = set()
    for instance_id in ordered_ids:
        if instance_id in seen:
            continue
        group = connected[instance_id]
        seen.update(group)
        stages.append(tuple(item for item in ordered_ids if item in group))
    if tuple(item for stage in stages for item in stage) != ordered_ids:
        raise ValueError("Connected Cube order interleaves independent Cubes.")
    return tuple(stages)


__all__ = ["cube_execution_stage_ids", "cube_execution_stages"]

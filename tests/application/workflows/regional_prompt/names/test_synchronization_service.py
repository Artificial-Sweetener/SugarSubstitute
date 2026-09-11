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

"""Prove canonical regional prompt names remain one shared ordinal identity."""

from __future__ import annotations

from substitute.application.workflows.regional_prompt_name_synchronization_service import (
    RegionalPromptNameSynchronizationService,
)
from substitute.domain.workspace_snapshot.codecs import (
    workflow_state_from_json,
    workflow_state_to_json,
)
from substitute.domain.workflow import WorkflowState
from tests.application.workflows.regional_prompt.support import build_workflow


def _set_prompt(workflow: WorkflowState, node_name: str, source_text: str) -> None:
    """Set one fixture prompt through its canonical graph buffer."""

    nodes = workflow.cubes["Region"].buffer["nodes"]
    assert isinstance(nodes, dict)
    node = nodes[node_name]
    assert isinstance(node, dict)
    inputs = node["inputs"]
    assert isinstance(inputs, dict)
    inputs["value"] = source_text


def _prompt(workflow: WorkflowState, node_name: str) -> str:
    """Return one fixture prompt from its canonical graph buffer."""

    nodes = workflow.cubes["Region"].buffer["nodes"]
    assert isinstance(nodes, dict)
    node = nodes[node_name]
    assert isinstance(node, dict)
    inputs = node["inputs"]
    assert isinstance(inputs, dict)
    value = inputs["value"]
    assert isinstance(value, str)
    return value


def test_normalization_projects_first_authored_names_into_every_prompt() -> None:
    """Normalize restored conflicts without replacing distinct prompt content."""

    workflow = build_workflow(
        "positive global\n[SEP|Subject]\npositive one\n[SEP|Scene]\npositive two",
        mask_count=2,
    )
    _set_prompt(
        workflow,
        "negative",
        "negative global\n[SEP]\nnegative one\n[SEP|Wrong]\nnegative two",
    )

    result = RegionalPromptNameSynchronizationService().normalize_for_prompt(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
    )

    assert {update.node_name for update in result.updates} == {"negative"}
    assert _prompt(workflow, "positive") == (
        "positive global\n[SEP|Subject]\npositive one\n[SEP|Scene]\npositive two"
    )
    assert _prompt(workflow, "negative") == (
        "negative global\n[SEP|Subject]\nnegative one\n[SEP|Scene]\nnegative two"
    )


def test_rename_clear_undo_and_redo_each_propagate_from_the_changed_prompt() -> None:
    """Treat every observed name transition as the shared ordinal edit authority."""

    workflow = build_workflow(
        "positive\n[SEP|Subject]\nregion",
        mask_count=1,
    )
    _set_prompt(workflow, "negative", "negative\n[SEP|Subject]\nregion")
    service = RegionalPromptNameSynchronizationService()

    renamed = "positive\n[SEP|Character]\nregion"
    _set_prompt(workflow, "positive", renamed)
    service.synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
        previous_source_text="positive\n[SEP|Subject]\nregion",
        current_source_text=renamed,
    )
    assert "[SEP|Character]" in _prompt(workflow, "negative")

    cleared = "positive\n[SEP]\nregion"
    _set_prompt(workflow, "positive", cleared)
    service.synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
        previous_source_text=renamed,
        current_source_text=cleared,
    )
    assert "[SEP]" in _prompt(workflow, "negative")
    assert "[SEP|" not in _prompt(workflow, "negative")

    _set_prompt(workflow, "positive", renamed)
    service.synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
        previous_source_text=cleared,
        current_source_text=renamed,
    )
    assert "[SEP|Character]" in _prompt(workflow, "negative")

    _set_prompt(workflow, "positive", cleared)
    service.synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
        previous_source_text=renamed,
        current_source_text=cleared,
    )
    assert "[SEP]" in _prompt(workflow, "negative")
    assert "[SEP|" not in _prompt(workflow, "negative")


def test_bulk_edit_propagates_multiple_names_without_copying_prompt_bodies() -> None:
    """Synchronize several pasted names and preserve unrelated source bytes."""

    previous = "P global\n[SEP|One]\nP one\n[SEP|Two]\nP two"
    current = "P global\n[SEP|Alice]\nP one changed\n[SEP|Forest]\nP two"
    workflow = build_workflow(previous, mask_count=2)
    _set_prompt(
        workflow,
        "negative",
        "N global\n[SEP|One]\nN one\n[SEP|Two]\nN two",
    )
    _set_prompt(workflow, "positive", current)

    RegionalPromptNameSynchronizationService().synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
        previous_source_text=previous,
        current_source_text=current,
    )

    assert _prompt(workflow, "negative") == (
        "N global\n[SEP|Alice]\nN one\n[SEP|Forest]\nN two"
    )


def test_unequal_and_malformed_structures_never_invent_or_destroy_regions() -> None:
    """Limit synchronization to separators each prompt actually exposes."""

    previous = "P\n[SEP|One]\none\n[SEP|Two]\ntwo"
    current = "P\n[SEP|Alice]\none\n[SEP|Forest]\ntwo"
    workflow = build_workflow(previous, mask_count=2)
    _set_prompt(workflow, "negative", "N\n[SEP]\none\n[SEP|broken\ntwo")
    _set_prompt(workflow, "positive", current)

    RegionalPromptNameSynchronizationService().synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
        previous_source_text=previous,
        current_source_text=current,
    )

    assert _prompt(workflow, "negative") == "N\n[SEP|Alice]\none\n[SEP|broken\ntwo"


def test_body_only_edit_repairs_conflicts_without_copying_the_body() -> None:
    """Converge restored identity conflicts during any ordinary prompt edit."""

    workflow = build_workflow("P\n[SEP|Subject]\none", mask_count=1)
    _set_prompt(workflow, "negative", "N\n[SEP|Wrong]\ntwo")
    current = "P changed\n[SEP|Subject]\none"
    _set_prompt(workflow, "positive", current)

    RegionalPromptNameSynchronizationService().synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
        previous_source_text="P\n[SEP|Subject]\none",
        current_source_text=current,
    )

    assert _prompt(workflow, "positive") == current
    assert _prompt(workflow, "negative") == "N\n[SEP|Subject]\ntwo"


def test_synchronized_names_survive_workspace_serialization() -> None:
    """Persist synchronized identity only through canonical prompt graph values."""

    workflow = build_workflow("P\n[SEP|Subject]\none", mask_count=1)
    _set_prompt(workflow, "negative", "N\n[SEP]\ntwo")
    RegionalPromptNameSynchronizationService().normalize_for_mask(
        workflow,
        ("Region", "masks"),
    )

    restored = workflow_state_from_json(workflow_state_to_json(workflow))

    assert _prompt(restored, "positive") == "P\n[SEP|Subject]\none"
    assert _prompt(restored, "negative") == "N\n[SEP|Subject]\ntwo"


def test_unrelated_prompt_topology_is_ignored() -> None:
    """Avoid treating ordinary prompt text as regional shared identity."""

    workflow = build_workflow("P\n[SEP|Subject]\none", mask_count=1)
    before = workflow_state_to_json(workflow)

    result = RegionalPromptNameSynchronizationService().synchronize_prompt_edit(
        workflow,
        section_key="Region",
        prompt_node_name="not-a-prompt",
        previous_source_text="old",
        current_source_text="new",
    )

    assert result.updates == ()
    assert workflow_state_to_json(workflow) == before


def test_names_synchronize_before_ordered_masks_are_materialized() -> None:
    """Use graph endpoint topology without requiring canvas-side mask state."""

    workflow = build_workflow("P\n[SEP|Subject]\none", mask_count=0)
    _set_prompt(workflow, "negative", "N\n[SEP]\ntwo")
    workflow.canvas.regional_mask_collections.clear()

    RegionalPromptNameSynchronizationService().normalize_for_prompt(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
    )

    assert _prompt(workflow, "negative") == "N\n[SEP|Subject]\ntwo"


def test_many_regions_converge_without_changing_any_region_body() -> None:
    """Keep a large adversarial prompt pair exact outside separator tokens."""

    region_count = 128
    positive = "\n".join(
        ["positive global"]
        + [
            part
            for index in range(region_count)
            for part in (f"[SEP|Region {index + 1}]", f"positive body {index + 1}")
        ]
    )
    negative = "\n".join(
        ["negative global"]
        + [
            part
            for index in range(region_count)
            for part in ("[SEP]", f"negative body {index + 1}")
        ]
    )
    workflow = build_workflow(positive, mask_count=region_count)
    _set_prompt(workflow, "negative", negative)

    RegionalPromptNameSynchronizationService().normalize_for_prompt(
        workflow,
        section_key="Region",
        prompt_node_name="positive",
    )

    synchronized_negative = _prompt(workflow, "negative")
    assert synchronized_negative.count("[SEP|Region ") == region_count
    assert all(
        f"negative body {index + 1}" in synchronized_negative
        for index in range(region_count)
    )
    assert _prompt(workflow, "positive") == positive

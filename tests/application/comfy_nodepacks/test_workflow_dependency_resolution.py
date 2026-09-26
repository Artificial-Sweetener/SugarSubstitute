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

"""Tests for workflow-scoped missing nodepack resolution."""

from dataclasses import dataclass, field

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    UnresolvedWorkflowNodeReason,
    WorkflowNodepackResolutionService,
    WorkflowNodepackSourceKind,
)
from substitute.domain.comfy_workflow.node_inventory import (
    PersistedNodepackHint,
    WorkflowNodeInventoryItem,
)


@dataclass
class _Registry:
    """Record resolution calls while returning configured packages."""

    by_class: dict[str, ResolvedWorkflowNodepack] = field(default_factory=dict)
    class_calls: list[str] = field(default_factory=list)

    def infer_nodepack(self, class_type: str) -> ResolvedWorkflowNodepack | None:
        """Return configured class inference evidence."""

        self.class_calls.append(class_type)
        return self.by_class.get(class_type)


def _node(
    node_id: str,
    class_type: str,
    *,
    registry_id: str | None = None,
    auxiliary_id: str | None = None,
    version: str | None = None,
) -> WorkflowNodeInventoryItem:
    """Build one concise persisted node fact."""

    return WorkflowNodeInventoryItem(
        node_id=node_id,
        class_type=class_type,
        title=class_type,
        cube_alias="Wild Cube",
        nodepack_hint=(
            PersistedNodepackHint(registry_id, auxiliary_id, version)
            if registry_id is not None or auxiliary_id is not None
            else None
        ),
    )


def test_uses_class_ownership_and_deduplicates_saved_package_hints() -> None:
    """Class ownership should collapse nodes while retaining saved version context."""

    impact = ResolvedWorkflowNodepack(
        identifier="comfyui-impact-pack",
        display_name="ComfyUI Impact Pack",
        source_kind=WorkflowNodepackSourceKind.REGISTRY,
        repository_url="https://github.com/ltdrdata/ComfyUI-Impact-Pack",
        version="8.28.3",
    )
    registry = _Registry(
        by_class={
            "DetailerForEach": impact,
            "SEGSPreview": impact,
        }
    )

    plan = WorkflowNodepackResolutionService(registry).resolve(
        (
            _node(
                "one",
                "DetailerForEach",
                registry_id="comfyui-impact-pack",
                version="8.28.0",
            ),
            _node(
                "two",
                "SEGSPreview",
                auxiliary_id="comfyui-impact-pack",
                version="8.22.2",
            ),
        )
    )

    assert registry.class_calls == ["DetailerForEach", "SEGSPreview"]
    assert len(plan.candidates) == 1
    assert plan.candidates[0].class_types == ("DetailerForEach", "SEGSPreview")
    assert plan.candidates[0].persisted_versions == ("8.22.2", "8.28.0")
    assert plan.candidates[0].nodepack.version == "8.28.3"
    assert plan.unresolved == ()


def test_authoritative_class_ownership_overrides_stale_saved_identity() -> None:
    """Saved package claims must not override authoritative class ownership."""

    package = ResolvedWorkflowNodepack(
        identifier="current-pack",
        display_name="Current Pack",
        source_kind=WorkflowNodepackSourceKind.REGISTRY,
        repository_url=None,
        version="2.0.0",
    )
    registry = _Registry(by_class={"RenamedNode": package})

    plan = WorkflowNodepackResolutionService(registry).resolve(
        (_node("one", "RenamedNode", registry_id="old-pack"),)
    )

    assert registry.class_calls == ["RenamedNode"]
    assert plan.candidates[0].nodepack == package


def test_rejects_unverified_saved_package_identity() -> None:
    """A saved package identity alone must never authorize code installation."""

    registry = _Registry()

    plan = WorkflowNodepackResolutionService(registry).resolve(
        (_node("one", "PrivateNode", registry_id="unrelated-public-package"),)
    )

    assert plan.candidates == ()
    assert [item.reason for item in plan.unresolved] == [
        UnresolvedWorkflowNodeReason.NOT_IN_CATALOG
    ]
    assert registry.class_calls == ["PrivateNode"]


def test_keeps_core_and_unknown_nodes_explicitly_unresolved() -> None:
    """Core repair and unknown third-party code must never become guessed installs."""

    registry = _Registry()

    plan = WorkflowNodepackResolutionService(registry).resolve(
        (
            _node("core", "FutureCoreNode", registry_id="comfy-core"),
            _node("unknown", "UnlistedNode"),
        )
    )

    assert plan.candidates == ()
    assert [item.reason for item in plan.unresolved] == [
        UnresolvedWorkflowNodeReason.CORE_UNAVAILABLE,
        UnresolvedWorkflowNodeReason.NOT_IN_CATALOG,
    ]
    assert registry.class_calls == ["UnlistedNode"]

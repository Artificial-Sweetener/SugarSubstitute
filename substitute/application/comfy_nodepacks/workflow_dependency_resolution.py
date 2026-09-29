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

"""Resolve missing workflow node classes to reviewable install sources."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from substitute.domain.comfy_workflow.node_inventory import WorkflowNodeInventoryItem

_COMFY_CORE_ID = "comfy-core"


class WorkflowNodepackSourceKind(StrEnum):
    """Identify the authoritative acquisition route for one nodepack."""

    REGISTRY = "registry"
    GIT_REPOSITORY = "git_repository"


@dataclass(frozen=True, slots=True)
class ResolvedWorkflowNodepack:
    """Describe one nodepack resolved through an authoritative catalog."""

    identifier: str
    display_name: str
    source_kind: WorkflowNodepackSourceKind
    repository_url: str | None
    version: str | None


class WorkflowNodepackCatalog(Protocol):
    """Resolve missing class names through authoritative ownership metadata."""

    def infer_nodepack(self, class_type: str) -> ResolvedWorkflowNodepack | None:
        """Return the authoritative package for one Comfy node class."""


class UnresolvedWorkflowNodeReason(StrEnum):
    """Classify why a missing node cannot become an install candidate."""

    CORE_UNAVAILABLE = "core_unavailable"
    NOT_IN_CATALOG = "not_in_catalog"


@dataclass(frozen=True, slots=True)
class UnresolvedWorkflowNode:
    """Retain a missing node that cannot be installed from known catalogs."""

    node: WorkflowNodeInventoryItem
    reason: UnresolvedWorkflowNodeReason


@dataclass(frozen=True, slots=True)
class WorkflowNodepackInstallCandidate:
    """Group missing workflow nodes behind one explicit install decision."""

    nodepack: ResolvedWorkflowNodepack
    nodes: tuple[WorkflowNodeInventoryItem, ...]
    persisted_versions: tuple[str, ...]

    @property
    def class_types(self) -> tuple[str, ...]:
        """Return the distinct affected class names in stable order."""

        return tuple(sorted({node.class_type for node in self.nodes}))


@dataclass(frozen=True, slots=True)
class WorkflowNodepackResolutionPlan:
    """Carry installable packages and explicit unresolved missing nodes."""

    candidates: tuple[WorkflowNodepackInstallCandidate, ...]
    unresolved: tuple[UnresolvedWorkflowNode, ...]


class WorkflowNodepackResolutionService:
    """Resolve missing nodes without trusting persisted package ownership."""

    def __init__(self, catalog: WorkflowNodepackCatalog) -> None:
        """Store the authoritative package-catalog boundary."""

        self._catalog = catalog

    def resolve(
        self,
        missing_nodes: tuple[WorkflowNodeInventoryItem, ...],
    ) -> WorkflowNodepackResolutionPlan:
        """Return a deterministic deduplicated install review plan."""

        inferred_cache: dict[str, ResolvedWorkflowNodepack | None] = {}
        grouped: dict[
            str, tuple[ResolvedWorkflowNodepack, list[WorkflowNodeInventoryItem]]
        ] = {}
        unresolved: list[UnresolvedWorkflowNode] = []
        for node in missing_nodes:
            explicit_id = _explicit_registry_id(node)
            if explicit_id is not None and explicit_id.casefold() == _COMFY_CORE_ID:
                unresolved.append(
                    UnresolvedWorkflowNode(
                        node=node,
                        reason=UnresolvedWorkflowNodeReason.CORE_UNAVAILABLE,
                    )
                )
                continue
            if node.class_type not in inferred_cache:
                inferred_cache[node.class_type] = self._catalog.infer_nodepack(
                    node.class_type
                )
            nodepack = inferred_cache[node.class_type]
            if nodepack is None:
                unresolved.append(
                    UnresolvedWorkflowNode(
                        node=node,
                        reason=UnresolvedWorkflowNodeReason.NOT_IN_CATALOG,
                    )
                )
                continue
            group_key = f"{nodepack.source_kind.value}:{nodepack.identifier}".casefold()
            grouped.setdefault(group_key, (nodepack, []))[1].append(node)
        candidates = tuple(
            WorkflowNodepackInstallCandidate(
                nodepack=nodepack,
                nodes=tuple(
                    sorted(
                        nodes,
                        key=lambda node: (
                            node.cube_alias or "",
                            node.node_id,
                            node.class_type,
                        ),
                    )
                ),
                persisted_versions=tuple(
                    sorted(
                        {
                            version
                            for node in nodes
                            if node.nodepack_hint is not None
                            and (version := node.nodepack_hint.version) is not None
                        }
                    )
                ),
            )
            for nodepack, nodes in sorted(
                grouped.values(),
                key=lambda group: (
                    group[0].source_kind.value,
                    group[0].identifier.casefold(),
                ),
            )
        )
        return WorkflowNodepackResolutionPlan(
            candidates=candidates,
            unresolved=tuple(
                sorted(
                    unresolved,
                    key=lambda item: (
                        item.node.cube_alias or "",
                        item.node.node_id,
                        item.node.class_type,
                    ),
                )
            ),
        )


def _explicit_registry_id(node: WorkflowNodeInventoryItem) -> str | None:
    """Return standard CNR identity, falling back to its legacy alias."""

    hint = node.nodepack_hint
    if hint is None:
        return None
    return hint.registry_id or hint.auxiliary_id


__all__ = [
    "ResolvedWorkflowNodepack",
    "UnresolvedWorkflowNode",
    "UnresolvedWorkflowNodeReason",
    "WorkflowNodepackInstallCandidate",
    "WorkflowNodepackCatalog",
    "WorkflowNodepackResolutionPlan",
    "WorkflowNodepackResolutionService",
    "WorkflowNodepackSourceKind",
]

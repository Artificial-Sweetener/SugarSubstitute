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

"""Tests for Registry-first arbitrary workflow nodepack lookup."""

from __future__ import annotations

from typing import cast

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
    WorkflowNodepackSourceKind,
)
from substitute.infrastructure.comfy.comfy_manager_nodepack_client import (
    ComfyManagerNodepackClient,
)
from substitute.infrastructure.comfy.comfy_registry_nodepack_client import (
    ComfyRegistryNodepackClient,
)
from substitute.infrastructure.comfy.comfy_workflow_nodepack_catalog import (
    ComfyWorkflowNodepackCatalog,
)
from substitute.infrastructure.comfy.github_repository_revision_client import (
    GitHubRepositoryRevisionClient,
)

_REVISION = "3740add9dbdc9f254a2befda30e95ba95e3b115d"


class _Lookup:
    """Return configured lookup results while recording requested identities."""

    def __init__(self, result: ResolvedWorkflowNodepack | None) -> None:
        """Store the result returned by every lookup."""

        self.result = result
        self.calls: list[str] = []

    def infer_nodepack(self, value: str) -> ResolvedWorkflowNodepack | None:
        """Record a class lookup."""

        self.calls.append(f"class:{value}")
        return self.result


def _package(identifier: str) -> ResolvedWorkflowNodepack:
    """Build one concise Registry result."""

    return ResolvedWorkflowNodepack(
        identifier=identifier,
        display_name=identifier,
        source_kind=WorkflowNodepackSourceKind.REGISTRY,
        repository_url=None,
        version="1.0.0",
    )


class _RevisionLookup:
    """Resolve every confirmed GitHub repository to one immutable commit."""

    def __init__(self) -> None:
        """Initialize without calls."""

        self.calls: list[str] = []

    def resolve_head(self, repository_url: str) -> str:
        """Record the repository and return the fixed revision."""

        self.calls.append(repository_url)
        return _REVISION


def test_prefers_registry_and_uses_manager_only_for_missing_class() -> None:
    """Legacy mapping should not override an authoritative Registry owner."""

    registry_result = _package("registry")
    manager_result = ResolvedWorkflowNodepack(
        identifier="https://github.com/owner/manager",
        display_name="manager",
        source_kind=WorkflowNodepackSourceKind.GIT_REPOSITORY,
        repository_url="https://github.com/owner/manager",
        version=None,
    )
    registry = _Lookup(registry_result)
    manager = _Lookup(manager_result)
    revisions = _RevisionLookup()
    catalog = ComfyWorkflowNodepackCatalog(
        registry=cast(ComfyRegistryNodepackClient, registry),
        manager=cast(ComfyManagerNodepackClient, manager),
        repository_revisions=cast(GitHubRepositoryRevisionClient, revisions),
    )

    assert catalog.infer_nodepack("Node") == registry_result
    assert registry.calls == ["class:Node"]
    assert manager.calls == []

    registry.result = None
    assert catalog.infer_nodepack("Legacy") == ResolvedWorkflowNodepack(
        identifier=manager_result.identifier,
        display_name=manager_result.display_name,
        source_kind=manager_result.source_kind,
        repository_url=manager_result.repository_url,
        version=_REVISION,
    )
    assert manager.calls == ["class:Legacy"]
    assert revisions.calls == ["https://github.com/owner/manager"]
    assert manager.calls == ["class:Legacy"]

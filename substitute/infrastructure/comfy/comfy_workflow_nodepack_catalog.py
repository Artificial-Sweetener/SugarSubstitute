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

"""Compose authoritative Registry and legacy Manager nodepack resolution."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.comfy_nodepacks.workflow_dependency_resolution import (
    ResolvedWorkflowNodepack,
)
from substitute.infrastructure.comfy.comfy_manager_nodepack_client import (
    ComfyManagerNodepackClient,
)
from substitute.infrastructure.comfy.comfy_registry_nodepack_client import (
    ComfyRegistryNodepackClient,
)
from substitute.infrastructure.comfy.github_repository_revision_client import (
    GitHubRepositoryRevisionClient,
)


class ComfyWorkflowNodepackCatalog:
    """Prefer Registry packages and use confirmed Manager mappings as fallback."""

    def __init__(
        self,
        *,
        registry: ComfyRegistryNodepackClient | None = None,
        manager: ComfyManagerNodepackClient | None = None,
        repository_revisions: GitHubRepositoryRevisionClient | None = None,
    ) -> None:
        """Store the two authoritative package lookup providers."""

        self._registry = registry or ComfyRegistryNodepackClient()
        self._manager = manager or ComfyManagerNodepackClient()
        self._repository_revisions = (
            repository_revisions or GitHubRepositoryRevisionClient()
        )

    def infer_nodepack(self, class_type: str) -> ResolvedWorkflowNodepack | None:
        """Resolve a class through Registry before the legacy Manager catalog."""

        registry_nodepack = self._registry.infer_nodepack(class_type)
        if registry_nodepack is not None:
            return registry_nodepack
        manager_nodepack = self._manager.infer_nodepack(class_type)
        if manager_nodepack is None or manager_nodepack.repository_url is None:
            return None
        return replace(
            manager_nodepack,
            version=self._repository_revisions.resolve_head(
                manager_nodepack.repository_url
            ),
        )


__all__ = ["ComfyWorkflowNodepackCatalog"]

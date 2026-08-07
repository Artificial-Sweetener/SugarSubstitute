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

"""Inspect installed core nodepack identity and management ownership."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
import tomllib

from substitute.domain.comfy_nodepacks import NodepackManagementKind
from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    resolve_installed_nodepack_root,
)
from substitute.infrastructure.version_control import RepositoryService


@dataclass(frozen=True, slots=True)
class NodepackInstallationSnapshot:
    """Describe authoritative source facts for one installed nodepack."""

    root: Path
    management: NodepackManagementKind
    project_name: str | None
    version: str | None
    repository_url: str | None
    sentinels_present: bool
    tracked_worktree_dirty: bool
    official_git_remote: bool

    def matches(self, nodepack: CoreComfyNodepack) -> bool:
        """Return whether identity, version, and sentinels satisfy the manifest."""

        return (
            self.project_name is not None
            and self.project_name.casefold() == nodepack.registry_id.casefold()
            and self.version == nodepack.required_version
            and self.sentinels_present
        )


class NodepackInstallationInspector:
    """Read nodepack source facts without mutating the Comfy workspace."""

    def __init__(self, repositories: RepositoryService) -> None:
        """Store the repository boundary used only for Git worktree evidence."""

        self._repositories = repositories

    def inspect(
        self,
        *,
        workspace: Path,
        nodepack: CoreComfyNodepack,
    ) -> NodepackInstallationSnapshot:
        """Return current identity, version, ownership, and dirty-state evidence."""

        root = resolve_installed_nodepack_root(workspace, nodepack)
        if not root.is_dir():
            return NodepackInstallationSnapshot(
                root=root,
                management=NodepackManagementKind.MISSING,
                project_name=None,
                version=None,
                repository_url=None,
                sentinels_present=False,
                tracked_worktree_dirty=False,
                official_git_remote=False,
            )
        management = self._management_kind(root)
        project_name, version, repository_url = read_nodepack_project_identity(
            root / "pyproject.toml"
        )
        sentinels_present = all(
            (root / sentinel).exists() for sentinel in nodepack.sentinel_files
        )
        return NodepackInstallationSnapshot(
            root=root,
            management=management,
            project_name=project_name,
            version=version,
            repository_url=repository_url,
            sentinels_present=sentinels_present,
            tracked_worktree_dirty=(
                self._tracked_worktree_dirty(root)
                if management is NodepackManagementKind.GIT
                else False
            ),
            official_git_remote=(
                repository_urls_match(
                    self._repositories.remote_urls(root).values(),
                    nodepack.fallback_repository_url,
                )
                if management is NodepackManagementKind.GIT
                else False
            ),
        )

    def _management_kind(self, root: Path) -> NodepackManagementKind:
        """Classify the source owner from mutually exclusive metadata."""

        if (root / ".git").exists():
            return NodepackManagementKind.GIT
        if (root / "pyproject.toml").is_file() and (root / ".tracking").is_file():
            return NodepackManagementKind.REGISTRY
        return NodepackManagementKind.PLAIN

    def _tracked_worktree_dirty(self, root: Path) -> bool:
        """Return whether Git reports modifications to tracked source files."""

        return git_status_has_tracked_changes(self._repositories.status_excerpt(root))


def git_status_has_tracked_changes(status_excerpt: str) -> bool:
    """Return whether concise repository status contains tracked-file changes."""

    status_lines = status_excerpt.splitlines()[1:]
    return any(line and not line.startswith("??") for line in status_lines)


def repository_urls_match(
    observed_urls: Iterable[str],
    expected_url: str,
) -> bool:
    """Return whether any observed Git remote is the trusted repository."""

    expected = _normalize_repository_url(expected_url)
    return any(_normalize_repository_url(url) == expected for url in observed_urls)


def _normalize_repository_url(url: str) -> str:
    """Normalize an HTTPS repository URL for ownership comparison."""

    return url.strip().rstrip("/").removesuffix(".git").casefold()


def read_nodepack_project_identity(
    pyproject_path: Path,
) -> tuple[str | None, str | None, str | None]:
    """Return project identity and repository from one valid TOML document."""

    if not pyproject_path.is_file():
        return None, None, None
    try:
        with pyproject_path.open("rb") as pyproject_file:
            payload = tomllib.load(pyproject_file)
    except (OSError, tomllib.TOMLDecodeError):
        return None, None, None
    project = payload.get("project")
    if not isinstance(project, dict):
        return None, None, None
    name = project.get("name")
    version = project.get("version")
    urls = project.get("urls")
    repository = urls.get("Repository") if isinstance(urls, dict) else None
    return (
        name.strip() if isinstance(name, str) and name.strip() else None,
        version.strip() if isinstance(version, str) and version.strip() else None,
        (
            repository.strip()
            if isinstance(repository, str) and repository.strip()
            else None
        ),
    )


__all__ = [
    "NodepackInstallationInspector",
    "NodepackInstallationSnapshot",
    "git_status_has_tracked_changes",
    "read_nodepack_project_identity",
    "repository_urls_match",
]

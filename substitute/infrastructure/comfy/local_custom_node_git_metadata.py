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

"""Resolve extension repository metadata from local custom-node Git remotes."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from substitute.application.ports.comfy_extension_metadata_provider import (
    ComfyExtensionMetadata,
)
from substitute.domain.comfy_startup_diagnostics import (
    ExtensionRepositoryLinks,
    normalize_repository_links,
)
from substitute.infrastructure.version_control import (
    RepositoryOperationError,
    RepositoryService,
    repository_service,
)
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.local_custom_node_git_metadata")
_REMOTE_NAMES = ("origin", "upstream")
_SOURCE = "local_git_remote"


class LocalCustomNodeGitMetadataProvider:
    """Resolve installed extension metadata from local Git remotes."""

    def __init__(
        self,
        *,
        custom_nodes_dir: Path,
        repositories: RepositoryService | None = None,
    ) -> None:
        """Store the custom-node directory and repository metadata service."""

        self._custom_nodes_dir = custom_nodes_dir
        self._repositories = repositories or repository_service()

    def installed_extensions(self) -> Mapping[str, ComfyExtensionMetadata]:
        """Return local Git repository metadata keyed by extension folder name."""

        if not self._custom_nodes_dir.is_dir():
            return {}
        metadata: dict[str, ComfyExtensionMetadata] = {}
        for child in self._custom_nodes_dir.iterdir():
            if not child.is_dir() or child.name in {"__pycache__", ".disabled"}:
                continue
            links = self._links_for(child)
            if links is None:
                continue
            metadata[child.name] = ComfyExtensionMetadata(
                key=child.name,
                repository_url=links.repository_url,
                issues_url=links.issues_url,
                source=links.source,
            )
        return metadata

    def _links_for(self, extension_path: Path) -> ExtensionRepositoryLinks | None:
        """Return repository links for one local extension folder."""

        if not (extension_path / ".git").exists():
            return None
        try:
            remote_urls = self._repositories.remote_urls(extension_path)
        except RepositoryOperationError as error:
            log_warning(
                _LOGGER,
                "Failed to read custom-node repository metadata",
                path=str(extension_path),
                error=repr(error),
            )
            return None
        for remote_name in (*_REMOTE_NAMES, *remote_urls):
            remote_url = remote_urls.get(remote_name)
            if remote_url is None:
                continue
            links = normalize_repository_links(remote_url, source=_SOURCE)
            if links is not None:
                return links
        return None


__all__ = ["LocalCustomNodeGitMetadataProvider"]

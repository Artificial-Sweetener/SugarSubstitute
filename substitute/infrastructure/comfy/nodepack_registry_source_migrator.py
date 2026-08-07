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

"""Migrate recognized nodepack source folders into Registry ownership."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from substitute.infrastructure.comfy.nodepack_installation_inspector import (
    git_status_has_tracked_changes,
    repository_urls_match,
)
from substitute.infrastructure.comfy.nodepack_manifest import CoreComfyNodepack
from substitute.infrastructure.comfy.nodepack_registry_tracking import (
    write_registry_tracking_file,
)
from substitute.infrastructure.comfy.nodepack_source_identity import (
    validate_nodepack_source_identity,
)
from substitute.infrastructure.comfy.nodepack_workspace_inspector import (
    tracked_source_files,
)
from substitute.infrastructure.filesystem import remove_app_owned_path
from substitute.infrastructure.version_control import RepositoryService
from substitute.shared.logging.logger import get_logger, log_info

LogCallback = Callable[[str], None]
_LOGGER = get_logger("infrastructure.comfy.nodepack_registry_source_migrator")


class NodepackRegistrySourceMigrator:
    """Transfer recognized Git or plain folders to CNR ownership."""

    def __init__(self, repositories: RepositoryService) -> None:
        """Store the repository evidence reader for Git migrations."""

        self._repositories = repositories

    def migrate_clean_git_installation(
        self,
        *,
        target_path: Path,
        nodepack: CoreComfyNodepack,
        on_log: LogCallback | None,
    ) -> None:
        """Convert a clean official checkout without touching mutable data."""

        git_path = target_path / ".git"
        if not git_path.exists():
            raise RuntimeError(f"Git metadata is missing from {target_path}.")
        if git_status_has_tracked_changes(
            self._repositories.status_excerpt(target_path)
        ):
            raise RuntimeError(
                f"Refusing to migrate changed Git checkout: {target_path}"
            )
        if not repository_urls_match(
            self._repositories.remote_urls(target_path).values(),
            nodepack.fallback_repository_url,
        ):
            raise RuntimeError(
                f"Refusing to migrate unrecognized Git checkout: {target_path}"
            )
        tracked_files = self._repositories.tracked_files(target_path)
        validate_nodepack_source_identity(
            target_path,
            nodepack,
            require_version=False,
        )
        write_registry_tracking_file(
            target_path=target_path,
            tracked_files=tracked_files,
        )
        remove_app_owned_path(git_path)
        self._emit(
            on_log,
            f"[ComfyNodepacks] Migrated {nodepack.display_name} from Git "
            "ownership to Comfy Registry ownership.",
        )

    def migrate_plain_installation(
        self,
        *,
        target_path: Path,
        nodepack: CoreComfyNodepack,
        on_log: LogCallback | None,
    ) -> None:
        """Adopt a recognized plain source folder without touching mutable data."""

        validate_nodepack_source_identity(
            target_path,
            nodepack,
            require_version=False,
        )
        write_registry_tracking_file(
            target_path=target_path,
            tracked_files=tracked_source_files(target_path),
        )
        self._emit(
            on_log,
            f"[ComfyNodepacks] Adopted existing {nodepack.display_name} "
            "source into Comfy Registry ownership.",
        )

    @staticmethod
    def _emit(callback: LogCallback | None, message: str) -> None:
        """Emit one structured migration record."""

        log_info(_LOGGER, message)
        if callback is not None:
            callback(message)


__all__ = ["NodepackRegistrySourceMigrator"]

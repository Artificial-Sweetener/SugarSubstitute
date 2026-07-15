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

"""Move persisted install data from legacy roots into the owned data layout."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from pathlib import Path
import shutil

from substitute.domain.onboarding import InstallationConfiguration, InstallationContext
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.onboarding.installation_layout_migration_service")


@dataclass(frozen=True)
class InstallationLayoutMigrationService:
    """Migrate one install root from legacy `config` and `state` directories."""

    configuration: InstallationConfiguration

    def migrate(self) -> None:
        """Move known legacy files and directories without overwriting destinations."""

        root = self.configuration.installation_root
        moves = (
            (
                root / "config" / "installation.json",
                self.configuration.user_settings_dir / "installation.json",
            ),
            (
                root / "config" / "runtime.json",
                self.configuration.user_settings_dir / "runtime.json",
            ),
            (
                root / "config" / "comfy_target.json",
                self.configuration.user_settings_dir / "comfy_target.json",
            ),
            (
                root / "config" / "appearance.json",
                self.configuration.user_settings_dir / "appearance.json",
            ),
            (
                root / "config" / "danbooru.json",
                self.configuration.user_settings_dir / "danbooru.json",
            ),
            (
                root / "config" / "generation_preview.json",
                self.configuration.user_settings_dir / "generation_preview.json",
            ),
            (
                root / "config" / "output_organization.json",
                self.configuration.user_settings_dir / "output_organization.json",
            ),
            (
                root / "config" / "prompt_editor.json",
                self.configuration.user_settings_dir / "prompt_editor.json",
            ),
            (
                root / "config" / "prompt_wildcards.json",
                self.configuration.user_settings_dir / "prompt_wildcards.json",
            ),
            (
                root / "state" / "session" / "session.json",
                self.configuration.session_dir / "session.json",
            ),
            (
                root / "state" / "session" / "session.json.bak",
                self.configuration.session_dir / "session.json.bak",
            ),
            (
                root / "state" / "restore-projection-cache.json",
                self.configuration.cache_dir / "restore-projection-cache.json",
            ),
            (
                root / "state" / "cube_icon_cache.sqlite3",
                self.configuration.cache_dir / "cube" / "cube_icon_cache.sqlite3",
            ),
            (
                root / "state" / "cube_classification_cache.sqlite3",
                self.configuration.cache_dir
                / "cube"
                / "cube_classification_cache.sqlite3",
            ),
            (
                root / "state" / "danbooru_cache.sqlite3",
                self.configuration.cache_dir / "danbooru" / "danbooru_cache.sqlite3",
            ),
            (
                root / "state" / "danbooru_images",
                self.configuration.cache_dir / "danbooru" / "images",
            ),
            (
                root / "state" / "managed_runtime.json",
                self.configuration.runtime_state_dir / "managed_runtime.json",
            ),
            (
                root / "state" / "managed_comfy_process.json",
                self.configuration.runtime_state_dir / "managed_comfy_process.json",
            ),
            (
                root / "state" / "setup_transaction.json",
                self.configuration.runtime_state_dir / "setup_transaction.json",
            ),
            (
                root / "state" / "startup_diagnostics_ignores.json",
                self.configuration.diagnostics_dir / "startup_diagnostics_ignores.json",
            ),
            (root / "state" / "logs", self.configuration.logs_dir),
            (root / "user" / "model_metadata", self.configuration.model_metadata_dir),
        )
        for source, destination in moves:
            self._move_if_available(source=source, destination=destination)

    def _move_if_available(self, *, source: Path, destination: Path) -> None:
        """Move one legacy path unless the destination already exists."""

        if not source.exists():
            return
        if destination.exists():
            log_warning(
                _LOGGER,
                "Skipped legacy layout migration because destination exists.",
                source=str(source),
                destination=str(destination),
            )
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        log_info(
            _LOGGER,
            "Migrated legacy install layout path.",
            source=str(source),
            destination=str(destination),
        )


@dataclass(frozen=True)
class ManagedWorkspaceLayoutMigrationService:
    """Migrate legacy managed-Comfy workspace layouts for launch-owned targets."""

    migrate_nested_workspace_layout: Callable[[Path], bool]

    def migrate(self, installation_context: InstallationContext | None) -> bool:
        """Run managed workspace migration when the active target owns launch."""

        if installation_context is None:
            return False
        target = installation_context.comfy_target
        workspace = target.workspace_path
        if not target.launch_owned or workspace is None:
            return False
        migrated = self.migrate_nested_workspace_layout(workspace)
        if migrated:
            log_warning(
                _LOGGER,
                "Migrated legacy nested managed ComfyUI workspace layout.",
                target_mode=target.mode.value,
                workspace_name=workspace.name,
            )
        return migrated


__all__ = [
    "InstallationLayoutMigrationService",
    "ManagedWorkspaceLayoutMigrationService",
]

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

"""Coordinate persisted installation configuration lifecycle operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from substitute.application.ports.installation_repository import (
    InstallationConfigurationRepository,
)
from substitute.application.onboarding.installation_layout_migration_service import (
    InstallationLayoutMigrationService,
)
from substitute.domain.onboarding import InstallationConfiguration
from substitute.shared.logging.logger import get_logger, log_info, log_warning

_LOGGER = get_logger("application.onboarding.installation_service")


@dataclass
class InstallationService:
    """Load, create, persist, and materialize installation configuration state."""

    repository: InstallationConfigurationRepository

    def load_persisted(self) -> InstallationConfiguration | None:
        """Load persisted configuration when it exists."""

        if not self.repository.exists():
            return None
        configuration = self.repository.load()
        migrated_configuration = self.migrate_legacy_user_data(configuration)
        InstallationLayoutMigrationService(migrated_configuration).migrate()
        self.ensure_directories(migrated_configuration)
        self.repository.save(migrated_configuration)
        return migrated_configuration

    def create_default(self) -> InstallationConfiguration:
        """Create the default configuration model without persisting it."""

        return self.repository.build_default()

    def save(
        self, configuration: InstallationConfiguration
    ) -> InstallationConfiguration:
        """Persist and materialize one installation configuration."""

        migrated_configuration = self.migrate_legacy_user_data(configuration)
        InstallationLayoutMigrationService(migrated_configuration).migrate()
        self.ensure_directories(migrated_configuration)
        self.repository.save(migrated_configuration)
        return migrated_configuration

    @staticmethod
    def ensure_directories(configuration: InstallationConfiguration) -> None:
        """Create the visible install-root directories expected by the product."""

        required_roots: tuple[Path, ...] = (
            configuration.installation_root,
            configuration.user_dir,
            configuration.user_settings_dir,
            configuration.projects_dir,
            configuration.outputs_dir,
            configuration.sugar_scripts_dir,
            configuration.wildcards_dir,
            configuration.appdata_dir,
            configuration.session_dir,
            configuration.cache_dir,
            configuration.cache_dir / "cube",
            configuration.cache_dir / "danbooru",
            configuration.cache_dir / "danbooru" / "images",
            configuration.model_metadata_dir,
            configuration.model_metadata_dir / "catalog",
            configuration.model_metadata_dir / "thumbnails",
            configuration.model_metadata_dir / "fingerprints",
            configuration.runtime_state_dir,
            configuration.diagnostics_dir,
            configuration.logs_dir,
            configuration.runtime_dir,
            configuration.default_managed_comfy_dir,
        )
        for root in required_roots:
            root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def migrate_legacy_user_data(
        configuration: InstallationConfiguration,
    ) -> InstallationConfiguration:
        """Move legacy default user artifacts into `user` without overwriting data."""

        default_configuration = InstallationConfiguration.create_default(
            configuration.installation_root
        )
        legacy_projects_dir = configuration.installation_root / "projects"
        projects_dir = configuration.projects_dir

        if (
            configuration.projects_dir.resolve() == legacy_projects_dir.resolve()
            and configuration.projects_dir.resolve()
            != default_configuration.projects_dir.resolve()
        ):
            projects_dir = default_configuration.projects_dir
            InstallationService._move_legacy_directory(
                source=legacy_projects_dir,
                destination=projects_dir,
                description="legacy projects root",
            )

        InstallationService._move_legacy_directory(
            source=configuration.installation_root / "saved_masks",
            destination=default_configuration.user_dir / "legacy" / "saved_masks",
            description="legacy saved masks root",
        )

        return InstallationConfiguration(
            installation_root=configuration.installation_root,
            user_dir=configuration.user_dir,
            user_settings_dir=configuration.user_settings_dir,
            projects_dir=projects_dir,
            outputs_dir=configuration.outputs_dir,
            sugar_scripts_dir=projects_dir,
            wildcards_dir=configuration.wildcards_dir,
            appdata_dir=configuration.appdata_dir,
            session_dir=configuration.session_dir,
            cache_dir=configuration.cache_dir,
            diagnostics_dir=configuration.diagnostics_dir,
            logs_dir=configuration.logs_dir,
            runtime_state_dir=configuration.runtime_state_dir,
            model_metadata_dir=configuration.model_metadata_dir,
            runtime_dir=configuration.runtime_dir,
            default_managed_comfy_dir=configuration.default_managed_comfy_dir,
        )

    @staticmethod
    def _move_legacy_directory(
        *,
        source: Path,
        destination: Path,
        description: str,
    ) -> None:
        """Move one legacy user-data directory when the destination is unclaimed."""

        if not source.exists():
            return
        if not source.is_dir():
            log_warning(
                _LOGGER,
                "Legacy user-data path is not a directory; leaving source in place.",
                description=description,
                source=source,
            )
            return
        if destination.exists():
            log_warning(
                _LOGGER,
                "Legacy user-data directory already has a destination; leaving source in place.",
                description=description,
                source=source,
                destination=destination,
            )
            return
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        log_info(
            _LOGGER,
            "Moved legacy user-data directory into Substitute user data.",
            description=description,
            source=source,
            destination=destination,
        )

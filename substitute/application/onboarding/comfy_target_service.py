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

"""Coordinate persisted Comfy target configuration lifecycle work."""

from __future__ import annotations

from dataclasses import dataclass

from substitute.application.ports.comfy_target_repository import (
    ComfyTargetConfigurationRepository,
)
from substitute.domain.onboarding import ComfyTargetConfiguration, ComfyTargetMode


@dataclass
class ComfyTargetService:
    """Load, create, validate, and persist the selected Comfy target."""

    repository: ComfyTargetConfigurationRepository

    def load_persisted(self) -> ComfyTargetConfiguration | None:
        """Load persisted target configuration when it exists."""

        if not self.repository.exists():
            return None
        return self.repository.load()

    def create_default(self) -> ComfyTargetConfiguration:
        """Create the default target configuration without persisting it."""

        return self.repository.build_default()

    def configure(
        self, configuration: ComfyTargetConfiguration
    ) -> ComfyTargetConfiguration:
        """Validate and persist one explicit Comfy target configuration."""

        if (
            configuration.mode is ComfyTargetMode.MANAGED_LOCAL
            and configuration.workspace_path is None
        ):
            raise ValueError("Managed local target requires a workspace path.")
        if (
            configuration.mode is ComfyTargetMode.ATTACHED_LOCAL
            and configuration.workspace_path is None
        ):
            raise ValueError("Existing local target requires a ComfyUI folder.")
        self.repository.save(configuration)
        return configuration

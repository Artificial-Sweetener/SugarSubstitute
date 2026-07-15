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

"""Coordinate install, runtime, and target state for onboarding flows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from substitute.application.onboarding.comfy_target_service import ComfyTargetService
from substitute.application.onboarding.installation_service import InstallationService
from substitute.application.onboarding.runtime_service import RuntimeService
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationContext,
)


@dataclass
class OnboardingService:
    """Load draft state and persist completed onboarding selections together."""

    installation_service: InstallationService
    runtime_service: RuntimeService
    comfy_target_service: ComfyTargetService

    def create_default_context(self) -> InstallationContext:
        """Build the default context model without persisting anything."""

        installation = self.installation_service.create_default()
        runtime = self.runtime_service.create_default()
        comfy_target = self.comfy_target_service.create_default()
        return InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=comfy_target,
        )

    def load_persisted_context(self) -> InstallationContext | None:
        """Load the fully persisted installation context when all files exist."""

        installation = self.installation_service.load_persisted()
        if installation is None:
            return None
        runtime = self.runtime_service.load_persisted()
        comfy_target = self.comfy_target_service.load_persisted()
        if runtime is None or comfy_target is None:
            return None
        return InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=comfy_target,
        )

    def load_draft_context(self) -> InstallationContext:
        """Load persisted state when present and fall back to in-memory defaults."""

        installation = (
            self.installation_service.load_persisted()
            or self.installation_service.create_default()
        )
        runtime = (
            self.runtime_service.load_persisted()
            or self.runtime_service.create_default()
        )
        comfy_target = (
            self.comfy_target_service.load_persisted()
            or self.comfy_target_service.create_default()
        )
        return InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=comfy_target,
        )

    def configure_managed_local(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Configure managed-local Comfy ownership and provision runtime state."""

        pending_context = self.build_managed_local_context(
            endpoint=endpoint,
            workspace_path=workspace_path,
        )
        installation = self.installation_service.save(pending_context.installation)
        runtime = self.runtime_service.provision()
        comfy_target = self.comfy_target_service.configure(pending_context.comfy_target)
        return InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=comfy_target,
        )

    def build_managed_local_context(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Build managed-local configuration without persisting active state."""

        context = self.load_draft_context()
        target = ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=endpoint,
            workspace_path=workspace_path,
            install_owned=True,
            launch_owned=True,
        )
        return InstallationContext(
            installation=context.installation,
            runtime=context.runtime,
            comfy_target=target,
        )

    def configure_attached_local(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Configure an existing local ComfyUI folder for Substitute-managed launch."""

        pending_context = self.build_attached_local_context(
            endpoint=endpoint,
            workspace_path=workspace_path,
        )
        installation = self.installation_service.save(pending_context.installation)
        runtime = self.runtime_service.provision()
        comfy_target = self.comfy_target_service.configure(pending_context.comfy_target)
        return InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=comfy_target,
        )

    def build_attached_local_context(
        self,
        *,
        endpoint: ComfyEndpoint,
        workspace_path: Path,
    ) -> InstallationContext:
        """Build existing-local launch configuration without persisting active state."""

        context = self.load_draft_context()
        target = ComfyTargetConfiguration(
            mode=ComfyTargetMode.ATTACHED_LOCAL,
            endpoint=endpoint,
            workspace_path=workspace_path,
            install_owned=False,
            launch_owned=True,
        )
        return InstallationContext(
            installation=context.installation,
            runtime=context.runtime,
            comfy_target=target,
        )

    def configure_remote(
        self,
        *,
        endpoint: ComfyEndpoint,
    ) -> InstallationContext:
        """Configure remote Comfy connectivity while retaining local runtime."""

        pending_context = self.build_remote_context(endpoint=endpoint)
        installation = self.installation_service.save(pending_context.installation)
        runtime = self.runtime_service.provision()
        comfy_target = self.comfy_target_service.configure(pending_context.comfy_target)
        return InstallationContext(
            installation=installation,
            runtime=runtime,
            comfy_target=comfy_target,
        )

    def build_remote_context(
        self,
        *,
        endpoint: ComfyEndpoint,
    ) -> InstallationContext:
        """Build remote Comfy configuration without persisting active state."""

        context = self.load_draft_context()
        target = ComfyTargetConfiguration(
            mode=ComfyTargetMode.REMOTE,
            endpoint=endpoint,
            workspace_path=None,
            install_owned=False,
            launch_owned=False,
        )
        return InstallationContext(
            installation=context.installation,
            runtime=context.runtime,
            comfy_target=target,
        )

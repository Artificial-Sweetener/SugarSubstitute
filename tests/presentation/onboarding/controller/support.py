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

"""Provide deterministic onboarding controller collaborators and context builders."""

from __future__ import annotations

import threading
from pathlib import Path

from substitute.application.onboarding import (
    OnboardingCompletionResult,
    OnboardingDraftState,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)


class FakeFlowService:
    """Return fixed onboarding draft and provisioning results for tests."""

    def __init__(
        self,
        *,
        draft: OnboardingDraftState,
        provision_result: OnboardingCompletionResult | None,
        provision_error: Exception | None = None,
    ) -> None:
        """Store the deterministic onboarding draft and completion result."""

        self._draft = draft
        self._provision_result = provision_result
        self._provision_error = provision_error
        self.provision_kwargs: dict[str, object] = {}
        self.provision_thread_id: int | None = None

    def load_draft(self, _installation_root: Path) -> OnboardingDraftState:
        """Return the configured onboarding draft."""

        return self._draft

    def provision(self, **kwargs: object) -> OnboardingCompletionResult:
        """Return the configured onboarding completion result."""

        self.provision_thread_id = threading.get_ident()
        self.provision_kwargs = dict(kwargs)
        on_status = kwargs.get("on_status")
        if callable(on_status):
            on_status("Starting setup.")
        if self._provision_error is not None:
            raise self._provision_error
        assert self._provision_result is not None
        return self._provision_result


class BlockingProgressFlowService(FakeFlowService):
    """Hold provisioning open after publishing deterministic live progress."""

    def __init__(
        self,
        *,
        draft: OnboardingDraftState,
        provision_result: OnboardingCompletionResult,
    ) -> None:
        """Store the completion and expose an explicit release barrier."""

        super().__init__(draft=draft, provision_result=provision_result)
        self.release = threading.Event()

    def provision(self, **kwargs: object) -> OnboardingCompletionResult:
        """Publish progress, then block on test-owned release or fail boundedly."""

        self.provision_thread_id = threading.get_ident()
        self.provision_kwargs = dict(kwargs)
        on_status = kwargs.get("on_status")
        on_log = kwargs.get("on_log")
        assert callable(on_status)
        assert callable(on_log)
        on_status("Installing ComfyUI.")
        on_log("Cloning the ComfyUI repository.")
        if not self.release.wait(timeout=5.0):
            raise TimeoutError("Test did not release blocked onboarding provisioning.")
        assert self._provision_result is not None
        return self._provision_result


def build_context(tmp_path: Path, mode: ComfyTargetMode) -> InstallationContext:
    """Build a deterministic onboarding context for controller tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / ".venv" / "Scripts" / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=mode,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=(
            installation.default_managed_comfy_dir
            if mode is ComfyTargetMode.MANAGED_LOCAL
            else None
        ),
        install_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
        launch_owned=mode is ComfyTargetMode.MANAGED_LOCAL,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )


__all__ = ["BlockingProgressFlowService", "FakeFlowService", "build_context"]

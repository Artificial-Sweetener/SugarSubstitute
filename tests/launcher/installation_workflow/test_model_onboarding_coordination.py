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

"""Verify installer execution coordinates with optional model onboarding."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from types import SimpleNamespace

from launcher.sugarsubstitute_launcher.application.model_onboarding import (
    ManagedComfyModelFolders,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.ui.experience_models import ExperiencePage
from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from sugarsubstitute_shared.model_acquisition import ModelAcquisitionService
from sugarsubstitute_shared.model_discovery import (
    DiscoveredModel,
    ModelCategory,
    ModelDiscoveryPlanner,
    ModelOnboardingService,
)
from tests.launcher.installation_workflow.support import (
    close_and_delete_launcher_window,
    release_source_for_test,
    wait_for_launcher_condition,
    workflow_factory,
)
from tests.launcher.support import launcher_test_application


class _NoDiscovery:
    """Fail if provider discovery starts before explicit user interest."""

    def discover_monthly_popular(
        self,
        category: ModelCategory,
        *,
        limit: int,
    ) -> tuple[DiscoveredModel, ...]:
        """Reject unexpected provider access."""

        raise AssertionError(f"unexpected discovery: {category}, {limit}")


class _LayoutPreparer:
    """Return the requested installation layout without filesystem work."""

    def __init__(self, layout: InstallLayout) -> None:
        """Store the prepared layout."""

        self._layout = layout

    def prepare(self, install_root: Path) -> object:
        """Return the expected prepared root."""

        assert install_root == self._layout.root
        return SimpleNamespace(layout=self._layout)


class _ArtifactInstaller:
    """Return one deterministic app payload result."""

    def __init__(self, layout: InstallLayout) -> None:
        """Store the installed layout."""

        self._layout = layout

    def continue_install(
        self, *, layout: InstallLayout, release_source: object
    ) -> object:
        """Return an app command without artifact mutation."""

        _ = release_source
        assert layout == self._layout
        return SimpleNamespace(
            layout=layout,
            app_version="test",
            app_command=("python.exe", "main.py"),
        )


class _RuntimeProvisioner:
    """Record runtime work after onboarding releases the flow."""

    def __init__(self) -> None:
        """Initialize an empty call log."""

        self.calls = 0

    def provision(self, *, layout: InstallLayout) -> object:
        """Return a representative runtime result."""

        self.calls += 1
        return SimpleNamespace(python_executable=layout.runtime_python)


def _service_factory() -> Callable[[Path], ModelOnboardingService]:
    """Build a read-only-gated service whose provider boundary must remain idle."""

    def build(model_root: Path) -> ModelOnboardingService:
        """Compose shared planning and acquisition for the selected root."""

        folders = ManagedComfyModelFolders(model_root)
        return ModelOnboardingService(
            planner=ModelDiscoveryPlanner(
                inventory=folders,
                discovery=_NoDiscovery(),
                destinations=folders,
            ),
            acquisition=ModelAcquisitionService(allowed_roots=(model_root,)),
        )

    return build


def _window(
    *,
    layout: InstallLayout,
    runtime: _RuntimeProvisioner,
    handoffs: list[Sequence[str]],
) -> LauncherMainWindow:
    """Build one production window with inert external boundaries."""

    return LauncherMainWindow(
        initial_layout=layout,
        continue_install=False,
        repair=False,
        update_check_enabled=True,
        initial_release_source=release_source_for_test(),
        workflow_factory=workflow_factory(
            layout_preparer=_LayoutPreparer(layout),
            artifact_installer=_ArtifactInstaller(layout),
            runtime_provisioner=runtime,
            process_starter=lambda command: handoffs.append(tuple(command)),
        ),
        model_onboarding_service_factory=_service_factory(),
    )


def test_zero_model_checklist_holds_runtime_and_handoff_until_skip(
    tmp_path: Path,
) -> None:
    """Installation must not close or launch the app beneath active onboarding."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    runtime = _RuntimeProvisioner()
    handoffs: list[Sequence[str]] = []
    window = _window(layout=layout, runtime=runtime, handoffs=handoffs)

    window.view.primary_button.click()
    wait_for_launcher_condition(
        application,
        lambda: not window.execution.initial_running,
    )

    assert window.view.experience_snapshot().page is ExperiencePage.MODEL_INTERESTS
    assert runtime.calls == 0
    assert handoffs == []

    window.view.model_interest_page.skip_requested.emit()
    wait_for_launcher_condition(
        application,
        lambda: runtime.calls == 1 and not window.execution.setup_running,
    )

    assert len(handoffs) == 1
    close_and_delete_launcher_window(window)


def test_existing_supported_model_bypasses_onboarding_without_provider_access(
    tmp_path: Path,
) -> None:
    """Any compatible local model should keep the normal installation route."""

    application = launcher_test_application()
    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    checkpoint = (
        layout.root
        / "comfyui"
        / "models"
        / ModelCategory.CHECKPOINTS.value
        / "already-here.safetensors"
    )
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"owned")
    runtime = _RuntimeProvisioner()
    handoffs: list[Sequence[str]] = []
    window = _window(layout=layout, runtime=runtime, handoffs=handoffs)

    window.view.primary_button.click()
    wait_for_launcher_condition(
        application,
        lambda: runtime.calls == 1 and not window.execution.setup_running,
    )

    assert window.view.experience_snapshot().page is ExperiencePage.INSTALL_LOCATION
    assert len(handoffs) == 1
    close_and_delete_launcher_window(window)

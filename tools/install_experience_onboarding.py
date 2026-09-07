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

"""Compose application-owned ComfyUI setup without external side effects."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.onboarding_execution import (
    create_onboarding_provisioning_submitter_factory,
)
from substitute.domain.onboarding import BootstrapRoute, ReadinessAssessment
from substitute.presentation.onboarding import OnboardingController, OnboardingWindow
from substitute.presentation.onboarding.comfy_environment_coordinator import (
    ComfyEnvironmentCoordinator,
)
from substitute.presentation.onboarding.model_onboarding_coordinator import (
    ModelOnboardingCoordinator,
)
from substitute.presentation.onboarding.onboarding_models import OnboardingFlowMode
from substitute.presentation.onboarding.path_selector import DirectoryChooser
from tools.install_experience_models import SyntheticModelOnboardingCoordinator
from tools.install_experience_live_models import (
    create_live_model_onboarding_coordinator,
)
from tools.install_experience_preparation import SyntheticBackgroundPreparationService
from tools.install_experience_scenarios import InstallExperienceScenario
from tools.install_experience_setup import (
    CapturedErrorPresenter,
    SetupSideEffectAudit,
    SyntheticComfyEnvironmentCoordinator,
    SyntheticOnboardingFlowService,
)


class OnboardingCheckSession:
    """Own one production onboarding window and its synthetic execution runtime."""

    def __init__(
        self,
        *,
        install_root: Path,
        install_root_locked: bool,
        scenario: InstallExperienceScenario | None = None,
        directory_chooser: DirectoryChooser | None = None,
        live_model_discovery: bool = False,
    ) -> None:
        """Compose production presentation over inert qualification adapters."""

        self.audit = SetupSideEffectAudit()
        self.error_presenter = CapturedErrorPresenter()
        self._runtime = ExecutionRuntime()
        self._preparation = SyntheticBackgroundPreparationService(
            hold_until_released=(
                scenario.background_finishes_after_choices if scenario else False
            )
        )
        readiness = ReadinessAssessment(route=BootstrapRoute.ONBOARDING, issues=())
        self.controller = OnboardingController(
            initial_install_root=install_root,
            flow_mode=OnboardingFlowMode.FIRST_RUN,
            readiness_assessment=readiness,
            flow_service=SyntheticOnboardingFlowService(
                install_root=install_root,
                audit=self.audit,
                provisioning_failures=(
                    scenario.provisioning_failures if scenario else 0
                ),
            ),
            preparation_service=self._preparation,
            submitter_factory=create_onboarding_provisioning_submitter_factory(
                self._runtime
            ),
        )
        coordinator = SyntheticComfyEnvironmentCoordinator(
            install_root=install_root,
            parent=self.controller,
        )
        model_coordinator: (
            ModelOnboardingCoordinator | SyntheticModelOnboardingCoordinator
        )
        if live_model_discovery:
            model_coordinator = create_live_model_onboarding_coordinator(
                runtime=self._runtime,
                parent=self.controller,
            )
        else:
            model_coordinator = SyntheticModelOnboardingCoordinator(
                detected_families=(scenario.detected_families if scenario else ()),
                recommendation_failure=(
                    scenario.recommendation_failure if scenario else False
                ),
                thumbnail_failure=(scenario.thumbnail_failure if scenario else False),
                scan_failure=(scenario.scan_failure if scenario else False),
                scan_unknown_count=(scenario.scan_unknown_count if scenario else 0),
                parent=self.controller,
            )
        self.window = OnboardingWindow(
            controller=self.controller,
            environment_coordinator=cast(ComfyEnvironmentCoordinator, coordinator),
            model_coordinator=cast(ModelOnboardingCoordinator, model_coordinator),
            install_root_locked=install_root_locked,
            error_presenter=self.error_presenter,
            directory_chooser=directory_chooser,
        )

    @property
    def preparation_started(self) -> bool:
        """Return whether background ComfyUI preparation started."""

        return self._preparation.started.is_set()

    @property
    def preparation_completed(self) -> bool:
        """Return whether background ComfyUI preparation completed."""

        return self._preparation.completed.is_set()

    def release_preparation(self) -> None:
        """Allow a held background preparation scenario to finish."""

        self._preparation.release.set()

    def close(self) -> None:
        """Close Qt owners before stopping their execution runtime."""

        self.release_preparation()
        self.window._emit_close_requested_on_close = False
        self.window.close()
        self.controller.shutdown()
        self._runtime.shutdown()
        self.window.deleteLater()
        self.controller.deleteLater()


def capture_onboarding_matrix(
    *,
    artifact_root: Path,
    install_root_locked: bool,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Drive every local/remote route headlessly and capture semantic evidence."""

    from tools.install_experience_driver import capture_onboarding_matrix as capture

    return capture(
        artifact_root=artifact_root,
        install_root_locked=install_root_locked,
    )


def open_interactive_onboarding(
    *,
    install_root: Path,
    install_root_locked: bool,
) -> OnboardingCheckSession:
    """Open production ComfyUI setup for an explicit maintainer walkthrough."""

    from tools.install_experience_driver import open_interactive_onboarding as open_flow

    return open_flow(
        install_root=install_root,
        install_root_locked=install_root_locked,
    )


__all__ = [
    "OnboardingCheckSession",
    "SetupSideEffectAudit",
    "capture_onboarding_matrix",
    "open_interactive_onboarding",
]

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

"""Drive production onboarding pages for no-install qualification."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import RadioButton  # type: ignore[import-untyped]

from substitute.domain.model_recommendations import ModelFamilyId
from substitute.presentation.onboarding import OnboardingWindow
from substitute.presentation.onboarding.onboarding_models import OnboardingTargetMode
from tools.install_experience_scenarios import (
    INSTALL_EXPERIENCE_SCENARIOS,
    InstallExperienceScenario,
)
from tools.install_experience_capture import (
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)
from tools.install_experience_setup import SetupSideEffectAudit
from tools.install_experience_model_evidence import recommendation_identity
from tools.install_experience_navigation import (
    click_installer_control as _click,
    installer_widget as _widget,
    wait_for_installer_condition as _wait_until,
    wait_for_installer_page as _wait_for_page,
)

if TYPE_CHECKING:
    from tools.install_experience_onboarding import OnboardingCheckSession


def capture_onboarding_matrix(
    *,
    artifact_root: Path,
    install_root_locked: bool,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Drive every local/remote route headlessly and capture semantic evidence."""

    from tools.install_experience_onboarding import OnboardingCheckSession

    evidence: list[dict[str, object]] = []
    combined_audit = SetupSideEffectAudit()
    for scenario in INSTALL_EXPERIENCE_SCENARIOS:
        session = OnboardingCheckSession(
            install_root=artifact_root / "sandbox" / scenario.slug,
            install_root_locked=install_root_locked,
            scenario=scenario,
            directory_chooser=_synthetic_directory_chooser(
                artifact_root / "sandbox" / scenario.slug
            ),
        )
        prepare_opaque_dark_capture_surface(session.window)
        session.window.show()
        QApplication.processEvents()
        try:
            _drive_onboarding_scenario(
                session=session,
                scenario=scenario,
                artifact_root=artifact_root,
                evidence=evidence,
                install_root_locked=install_root_locked,
            )
            _merge_audit(combined_audit, session.audit)
        finally:
            session.close()
            QApplication.processEvents()
    return evidence, combined_audit.forbidden_counts()


def open_interactive_onboarding(
    *,
    install_root: Path,
    install_root_locked: bool,
) -> OnboardingCheckSession:
    """Open production ComfyUI setup for an explicit maintainer walkthrough."""

    from tools.install_experience_onboarding import OnboardingCheckSession

    session = OnboardingCheckSession(
        install_root=install_root,
        install_root_locked=install_root_locked,
        live_model_discovery=True,
    )
    session.window.show()
    return session


def _drive_onboarding_scenario(
    *,
    session: OnboardingCheckSession,
    scenario: InstallExperienceScenario,
    artifact_root: Path,
    evidence: list[dict[str, object]],
    install_root_locked: bool,
) -> None:
    """Drive one production route to completion using named controls."""

    window = session.window
    if install_root_locked:
        _wait_for_page(window, "OnboardingTargetModePage")
    else:
        _wait_for_page(window, "OnboardingWelcomePage")
        _capture(window, artifact_root, scenario.slug, "install-root", evidence)
        _click(window, "OnboardingPrimaryButton")
    _wait_for_page(window, "OnboardingTargetModePage")
    _capture(window, artifact_root, scenario.slug, "target-mode", evidence)
    target_value = {
        "managed": OnboardingTargetMode.MANAGED_LOCAL.value,
        "attached": OnboardingTargetMode.ATTACHED_LOCAL.value,
        "remote": OnboardingTargetMode.REMOTE.value,
    }[scenario.target]
    radio = _widget(
        window,
        RadioButton,
        f"OnboardingTargetCardRadio_{target_value}",
    )
    QTest.mouseClick(radio, Qt.MouseButton.LeftButton)
    _click(window, "OnboardingPrimaryButton")
    configuration_page = {
        "managed": "OnboardingManagedLocalPage",
        "attached": "OnboardingAttachedLocalPage",
        "remote": "OnboardingRemotePage",
    }[scenario.target]
    _wait_for_page(window, configuration_page)
    _capture(window, artifact_root, scenario.slug, "configuration", evidence)
    if scenario.slug == "managed-sdxl-and-anima":
        _click(window, "OnboardingAdvancedButton")
        QTest.qWait(20)
        _capture(
            window,
            artifact_root,
            scenario.slug,
            "configuration-advanced",
            evidence,
            capture_widget=window.managed_local_page.connection_settings_dialog,
        )
        _click(window, "OnboardingConnectionSettingsDoneButton")
    _click(window, "OnboardingPrimaryButton")
    if scenario.target != "remote":
        _wait_for_page(window, "OnboardingExistingModelsQuestionPage")
        _capture(
            window,
            artifact_root,
            scenario.slug,
            "existing-models-question",
            evidence,
        )
        existing_answer = (
            "OnboardingYesExistingModelsButton"
            if scenario.existing_models
            else "OnboardingNoExistingModelsButton"
        )
        _click(
            window,
            existing_answer,
        )
        _capture(
            window,
            artifact_root,
            scenario.slug,
            "existing-models-answer-yes"
            if scenario.existing_models
            else "existing-models-answer-no",
            evidence,
        )
    if scenario.target != "remote" and not scenario.background_finishes_after_choices:
        _wait_until(
            lambda: session.preparation_completed,
            description=f"{scenario.slug} early background preparation",
        )
    if scenario.target == "remote" or scenario.existing_models:
        _wait_for_page(window, "OnboardingFolderSetupPage")
        if (
            scenario.target == "remote"
            and not window.folder_setup_page.managed_model_section.isHidden()
        ):
            raise RuntimeError("Remote setup exposed local model-folder controls.")
        _capture(window, artifact_root, scenario.slug, "folders", evidence)
        if scenario.existing_models:
            _click(window, "OnboardingManagedModelRootBrowseButton")
        _click(window, "OnboardingPrimaryButton")
    if scenario.scan_failure:
        _wait_until(
            lambda: window.primary_button.text() == "Try again",
            description=f"{scenario.slug} scan recovery",
        )
        _capture(window, artifact_root, scenario.slug, "scan-recovery", evidence)
        _click(window, "OnboardingBackButton")
        _wait_for_page(window, "OnboardingExistingModelsQuestionPage")
        _click(window, "OnboardingNoExistingModelsButton")
    missing_families = tuple(
        family
        for family in (ModelFamilyId.SDXL, ModelFamilyId.ANIMA)
        if family not in frozenset(scenario.detected_families)
    )
    if scenario.target != "remote" and missing_families:
        _drive_model_recommendations(
            window=window,
            scenario=scenario,
            missing_families=missing_families,
            artifact_root=artifact_root,
            evidence=evidence,
        )
    _wait_for_page(window, "OnboardingIntegrationsPage")
    _capture(window, artifact_root, scenario.slug, "integrations", evidence)
    _click(window, "OnboardingPrimaryButton")
    if scenario.background_finishes_after_choices:
        _wait_for_page(window, "OnboardingProvisioningPage")
        _capture(window, artifact_root, scenario.slug, "provisioning", evidence)
        if scenario.slug == "managed-sdxl-and-anima":
            _click(window, "OnboardingShowSetupLogButton")
            QTest.qWait(20)
            _capture(
                window,
                artifact_root,
                scenario.slug,
                "setup-log",
                evidence,
                capture_widget=window.setup_log_dialog,
            )
            window.setup_log_dialog.close()
        if not session.preparation_started:
            raise RuntimeError("Background preparation did not start before choices.")
        session.release_preparation()
    if scenario.provisioning_failures:
        _wait_for_page(window, "OnboardingProvisioningPage")
        _wait_until(
            lambda: len(session.error_presenter.reports) == 1,
            description=f"{scenario.slug} structured failure report",
        )
        if window.setup_log_dialog.isHidden():
            raise RuntimeError("Setup failure did not reveal the diagnostic log.")
        report = session.error_presenter.reports[0]
        if report.operation_context is None or not report.operation_context.trace_id:
            raise RuntimeError("Setup failure report lacks transaction context.")
        _capture(window, artifact_root, scenario.slug, "download-failure", evidence)
        _click(window, "OnboardingPrimaryButton")
    _wait_for_page(window, "OnboardingCompletionPage")
    _capture(window, artifact_root, scenario.slug, "completion", evidence)
    if scenario.slug == "managed-sdxl-and-anima":
        _click(window, "OnboardingCompletionDetailsButton")
        QTest.qWait(20)
        _capture(
            window,
            artifact_root,
            scenario.slug,
            "completion-details",
            evidence,
        )


def _drive_model_recommendations(
    *,
    window: OnboardingWindow,
    scenario: InstallExperienceScenario,
    missing_families: tuple[ModelFamilyId, ...],
    artifact_root: Path,
    evidence: list[dict[str, object]],
) -> None:
    """Drive per-family provider recovery, portrait cards, skipping, and review."""

    if scenario.recommendation_failure:
        _wait_until(
            lambda: window.primary_button.text() == "Try again",
            description=f"{scenario.slug} recommendation recovery",
        )
        _capture(
            window, artifact_root, scenario.slug, "model-provider-recovery", evidence
        )
        _click(window, "OnboardingPrimaryButton")
    if scenario.thumbnail_failure:
        _wait_for_page(window, "OnboardingModelRecommendationPage")
        _capture(
            window, artifact_root, scenario.slug, "model-provider-recovery", evidence
        )
        _click(window, "OnboardingFindOwnModelsButton")
        return
    selected_any = False
    for family in missing_families:
        _wait_for_page(window, "OnboardingModelRecommendationPage")
        _assert_recommendation_page(window, family)
        _capture(
            window,
            artifact_root,
            scenario.slug,
            f"recommendations-{family.value}",
            evidence,
        )
        if scenario.slug == "managed-sdxl-and-anima" and family == missing_families[0]:
            settled_pages = window._controller.model_session.state.recommendation_pages
            settled_identity = recommendation_identity(window)
            _click(window, "OnboardingBackButton")
            _wait_for_page(window, "OnboardingExistingModelsQuestionPage")
            _click(window, "OnboardingNoExistingModelsButton")
            _wait_for_page(window, "OnboardingModelRecommendationPage")
            _assert_recommendation_page(window, family)
            if (
                window._controller.model_session.state.recommendation_pages
                is not settled_pages
                or recommendation_identity(window) != settled_identity
            ):
                raise RuntimeError(
                    "Back/Continue replaced the settled CivitAI recommendation session."
                )
            _capture(
                window,
                artifact_root,
                scenario.slug,
                f"recommendations-{family.value}-revisit",
                evidence,
            )
        if family in scenario.selected_families:
            version_id = (100 if family.value == "sdxl" else 200) * 10 + 1
            _click(window, f"OnboardingRecommendationSelect_{version_id}")
            _click(window, "OnboardingPrimaryButton")
            selected_any = True
            continue
        if not selected_any and not scenario.selected_families:
            _click(window, "OnboardingFindOwnModelsButton")
            return
        _click(window, "OnboardingRecommendationSkipButton")
    if selected_any:
        _wait_for_page(window, "OnboardingModelDownloadReviewPage")
        _capture(
            window, artifact_root, scenario.slug, "model-download-review", evidence
        )
        _click(window, "OnboardingPrimaryButton")


def _assert_recommendation_page(
    window: OnboardingWindow,
    family: object,
) -> None:
    """Require three real, initially unchecked portrait cards."""

    from PySide6.QtWidgets import QCheckBox

    from substitute.presentation.onboarding.onboarding_recommendation_pages import (
        RecommendationPortrait,
    )

    card_widgets: list[QWidget] = []
    for index in range(window.model_recommendation_page.card_grid.count()):
        item = window.model_recommendation_page.card_grid.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is not None:
            card_widgets.append(widget)
    selectable = [
        checkbox
        for card in card_widgets
        for checkbox in card.findChildren(QCheckBox)
        if checkbox.objectName().startswith("OnboardingRecommendationSelect_")
    ]
    if len(selectable) != 3 or any(card.isChecked() for card in selectable):
        raise RuntimeError(
            f"{family} recommendation cards are not three unchecked choices."
        )
    portraits = [
        portrait
        for card in card_widgets
        for portrait in card.findChildren(RecommendationPortrait)
    ]
    if len(portraits) != 3 or any(
        portrait.source_size().height() < 960 for portrait in portraits
    ):
        raise RuntimeError(f"{family} recommendations lack real prepared thumbnails.")


def _capture(
    window: OnboardingWindow,
    artifact_root: Path,
    scenario: str,
    checkpoint: str,
    evidence: list[dict[str, object]],
    capture_widget: QWidget | None = None,
) -> None:
    """Capture one production page and its stable semantic identity."""

    QApplication.processEvents()
    path = artifact_root / "comfy-setup" / scenario / f"{checkpoint}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    save_opaque_dark_widget_capture(capture_widget or window, path)
    current = window.page_stack.currentWidget()
    evidence.append(
        {
            "scenario": f"comfy-setup/{scenario}/{checkpoint}",
            "surface": "comfy-setup",
            "route": scenario,
            "page": current.objectName() if current is not None else "",
            "primary_action": window.primary_button.text(),
            "screenshot": str(path),
        }
    )


def _merge_audit(target: SetupSideEffectAudit, source: SetupSideEffectAudit) -> None:
    """Accumulate one session audit without obscuring forbidden counters."""

    target.network_calls += source.network_calls
    target.subprocess_calls += source.subprocess_calls
    target.provisioning_calls += source.provisioning_calls
    target.credential_reads += source.credential_reads
    target.user_configuration_writes += source.user_configuration_writes
    target.model_downloads += source.model_downloads
    target.simulated_provisioning_calls += source.simulated_provisioning_calls


def _synthetic_directory_chooser(root: Path) -> Callable[[QWidget, str, str], str]:
    """Return an inert existing-model directory chooser for headless scenarios."""

    def choose(_parent: QWidget, _title: str, _initial: str) -> str:
        """Return a deterministic path without opening native UI."""

        return str(root / "existing-models")

    return choose


__all__ = [
    "capture_onboarding_matrix",
    "open_interactive_onboarding",
]

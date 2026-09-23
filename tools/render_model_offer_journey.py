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

"""Render every installer model offer in its production window headlessly."""

from __future__ import annotations

import json
import os
from pathlib import Path
import struct
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped] # noqa: E402

from substitute.domain.model_recommendations import ModelFamilyId  # noqa: E402
from substitute.presentation.onboarding import OnboardingWindow  # noqa: E402
from substitute.presentation.onboarding.onboarding_model_link_import import (  # noqa: E402
    ModelLinkImportOverlay,
)
from tools.install_experience_capture import (  # noqa: E402
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)
from tools.install_experience_navigation import (  # noqa: E402
    click_installer_control,
    wait_for_installer_condition,
    wait_for_installer_page,
)
from tools.install_experience_onboarding import OnboardingCheckSession  # noqa: E402

_ARTIFACT_ROOT = (
    Path(__file__).resolve().parents[1]
    / "build"
    / "qualification"
    / "model-offer-journey"
)


def _register_font(application: QApplication) -> None:
    """Apply the installed Fluent-compatible Windows UI font."""

    windows_root = os.environ.get("WINDIR")
    if windows_root is None:
        raise RuntimeError("WINDIR is required for this Windows render.")
    font_id = QFontDatabase.addApplicationFont(
        str(Path(windows_root) / "Fonts" / "segoeui.ttf")
    )
    families = QFontDatabase.applicationFontFamilies(font_id)
    if font_id < 0 or not families:
        raise RuntimeError("Could not load the Windows UI font.")
    application.setFont(QFont(families[0], 10))


def _capture(window: OnboardingWindow, root: Path, name: str) -> str:
    """Save the entire production installer window at one settled checkpoint."""

    QApplication.processEvents()
    path = root / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    save_opaque_dark_widget_capture(window, path)
    return str(path)


def _wait_for_family(window: OnboardingWindow, family: ModelFamilyId) -> None:
    """Wait for the requested offer and all visible thumbnail attempts."""

    wait_for_installer_page(window, "OnboardingModelRecommendationPage")
    wait_for_installer_condition(
        lambda: (
            window.model_recommendation_page.current_family() is family
            and len(window.model_recommendation_page.visible_cards()) == 8
        ),
        description=f"eight real {family.value} offers",
        timeout_seconds=90.0,
    )
    wait_for_installer_condition(
        lambda: all(
            not card.portrait.thumbnail_is_loading()
            for card in window.model_recommendation_page.visible_cards()
        ),
        description=f"settled {family.value} thumbnails",
        timeout_seconds=120.0,
    )


def _start_managed(window: OnboardingWindow) -> None:
    """Enter the production managed-local installer path."""

    wait_for_installer_page(window, "OnboardingTargetModePage")
    click_installer_control(window, "OnboardingPrimaryButton")
    wait_for_installer_page(window, "OnboardingManagedLocalPage")
    click_installer_control(window, "OnboardingPrimaryButton")
    wait_for_installer_page(window, "OnboardingExistingModelsQuestionPage")


def _render_new_install(root: Path) -> dict[str, object]:
    """Capture all three real recommendation families and completion."""

    session = OnboardingCheckSession(
        install_root=root / "new-install" / "synthetic-install",
        install_root_locked=True,
        live_model_discovery=True,
    )
    window = session.window
    prepare_opaque_dark_capture_surface(window)
    window.show()
    QApplication.processEvents()
    screenshots: dict[str, str] = {}
    try:
        _start_managed(window)
        screenshots["existing_models_question"] = _capture(
            window, root, "01-existing-models-question"
        )
        click_installer_control(window, "OnboardingNoExistingModelsButton")
        for index, family in enumerate(
            (ModelFamilyId.SDXL, ModelFamilyId.ANIMA, ModelFamilyId.UPSCALERS),
            start=2,
        ):
            _wait_for_family(window, family)
            screenshots[f"offer_{family.value}"] = _capture(
                window, root, f"{index:02d}-offer-{family.value}"
            )
            offer_scroll = window.page_stage.verticalScrollBar()
            if offer_scroll.maximum() <= 0:
                raise AssertionError(
                    f"The {family.value} offer did not expose its last row."
                )
            offer_scroll.setValue(offer_scroll.maximum())
            screenshots[f"offer_{family.value}_last_row"] = _capture(
                window, root, f"{index:02d}-offer-{family.value}-last-row"
            )
            if family is not ModelFamilyId.UPSCALERS:
                click_installer_control(window, "OnboardingOwnModelChoice")
            else:
                selected = session.controller.model_session.state.selected_version_ids
                if len(selected) != 8:
                    raise AssertionError(
                        f"Expected eight default upscaler selections, got {len(selected)}."
                    )
                click_installer_control(window, "OnboardingOpenModelDbImportCard")
                overlay = window.findChild(ModelLinkImportOverlay)
                if overlay is None:
                    raise AssertionError("The upscaler link overlay did not open.")
                screenshots["add_upscaler_links"] = _capture(
                    window, root, "04a-add-upscaler-links"
                )
                overlay.link_edit.setPlainText(
                    "https://openmodeldb.info/models/4x-UltraSharpV2\n"
                    "https://civitai.com/models/116225?modelVersionId=125843"
                )
                click_installer_control(window, "OnboardingModelLinkCheckButton")
                wait_for_installer_condition(
                    lambda: len(overlay.ready_cards()) == 2,
                    description="ready OpenModelDB and CivitAI upscaler links",
                    timeout_seconds=60.0,
                )
                screenshots["verified_upscaler_links"] = _capture(
                    window, root, "04b-verified-upscaler-links"
                )
                click_installer_control(window, "OnboardingModelLinkCancelButton")
            click_installer_control(window, "OnboardingPrimaryButton")
        wait_for_installer_page(window, "OnboardingModelDownloadReviewPage")
        screenshots["download_review"] = _capture(window, root, "05-download-review")
        review_scroll = (
            window.model_download_review_page.cards_scroll.verticalScrollBar()
        )
        if review_scroll.maximum() <= 0:
            raise AssertionError("The eight-model review did not expose its last row.")
        review_scroll.setValue(review_scroll.maximum())
        window.page_stage.verticalScrollBar().setValue(
            window.page_stage.verticalScrollBar().maximum()
        )
        screenshots["download_review_last_row"] = _capture(
            window, root, "05-download-review-last-row"
        )
        click_installer_control(window, "OnboardingPrimaryButton")
        wait_for_installer_page(window, "OnboardingIntegrationsPage")
        screenshots["integrations"] = _capture(window, root, "06-integrations")
        click_installer_control(window, "OnboardingPrimaryButton")
        wait_for_installer_page(window, "OnboardingCompletionPage")
        screenshots["after_install"] = _capture(
            window, root, "07-after-simulated-install"
        )
        click_installer_control(window, "OnboardingCompletionDetailsButton")
        screenshots["after_install_details"] = _capture(
            window, root, "08-after-simulated-install-details"
        )
        return {
            "screenshots": screenshots,
            "selected_upscalers": 8,
            "real_models": [
                {
                    "family": page.family_id.value,
                    "names": [card.recommendation.model_name for card in page.cards],
                    "providers": [
                        card.recommendation.provider_name for card in page.cards
                    ],
                    "rendered_thumbnails": sum(
                        card.thumbnail is not None for card in page.cards
                    ),
                }
                for page in session.controller.model_session.state.recommendation_pages
            ],
            "side_effect_audit": session.audit.forbidden_counts(),
        }
    finally:
        session.close()
        QApplication.processEvents()


def _write_existing_generation_models(root: Path) -> None:
    """Seed scan-valid headers while leaving the upscaler folder empty."""

    checkpoint = root / "checkpoints" / "existing-sdxl.safetensors"
    anima = root / "diffusion_models" / "existing-anima.safetensors"
    for path, header in (
        (checkpoint, {"__metadata__": {"modelspec.architecture": "SDXL 1.0"}}),
        (anima, {"model.diffusion_model.double_blocks.0.img_attn.qkv.weight": {}}),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(header).encode("utf-8")
        path.write_bytes(struct.pack("<Q", len(payload)) + payload)
    (root / "upscale_models").mkdir(parents=True, exist_ok=True)


def _render_existing_folder(root: Path) -> dict[str, object]:
    """Show that an existing model library with no upscalers gets the offer."""

    models_root = root / "existing-library" / "models"
    _write_existing_generation_models(models_root)

    def choose_models(_parent: QWidget, _title: str, _initial: str) -> str:
        """Return the bounded qualification library without opening a dialog."""

        return str(models_root)

    session = OnboardingCheckSession(
        install_root=root / "existing-library" / "synthetic-install",
        install_root_locked=True,
        directory_chooser=choose_models,
        live_model_discovery=True,
    )
    window = session.window
    prepare_opaque_dark_capture_surface(window)
    window.show()
    QApplication.processEvents()
    try:
        _start_managed(window)
        click_installer_control(window, "OnboardingYesExistingModelsButton")
        wait_for_installer_page(window, "OnboardingFolderSetupPage")
        click_installer_control(window, "OnboardingManagedModelRootBrowseButton")
        folder_path = _capture(window, root, "09-existing-folder-selected")
        click_installer_control(window, "OnboardingPrimaryButton")
        _wait_for_family(window, ModelFamilyId.UPSCALERS)
        offer_path = _capture(window, root, "10-empty-upscalers-offer")
        detected = session.controller.model_session.state.scan_result
        if detected is None or detected.detected_families != {
            ModelFamilyId.SDXL,
            ModelFamilyId.ANIMA,
        }:
            raise AssertionError(
                "The existing-library scan did not identify both models."
            )
        return {
            "screenshots": {
                "existing_folder_selected": folder_path,
                "empty_upscalers_offer": offer_path,
            },
            "detected_families": sorted(
                item.value for item in detected.detected_families
            ),
            "side_effect_audit": session.audit.forbidden_counts(),
        }
    finally:
        session.close()
        QApplication.processEvents()


def run_headless_model_offer_journey(
    *, artifact_root: Path = _ARTIFACT_ROOT
) -> dict[str, object]:
    """Render real offers in whole production windows with inert install effects."""

    artifact_root = artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    application = cast(QApplication, QApplication.instance() or QApplication([]))
    _register_font(application)
    setTheme(Theme.DARK)
    evidence = {
        "result": "passed",
        "headless": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "install_effects": "simulated",
        "new_install": _render_new_install(artifact_root),
        "existing_folder": _render_existing_folder(artifact_root),
    }
    (artifact_root / "evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return evidence


if __name__ == "__main__":
    run_headless_model_offer_journey()
    print(_ARTIFACT_ROOT / "evidence.json")

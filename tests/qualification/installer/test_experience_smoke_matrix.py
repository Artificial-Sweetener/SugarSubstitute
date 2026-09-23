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

"""Qualify the complete installer experience render matrix."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtGui import QImage

from tools.installer_experience_smoke import run_headless_smoke


def test_headless_smoke_renders_complete_matrix_without_side_effects() -> None:
    """Render key install, onboarding, repair, failure, and completion states."""

    artifact_root = (
        Path(__file__).resolve().parents[3]
        / "build"
        / "qualification"
        / "test-installer-smoke"
    )

    result = run_headless_smoke(artifact_root=artifact_root)

    assert result["headless"] is True
    assert result["schema_version"] == 4
    assert result["journey"] == (
        "bootstrap-launcher",
        "comfy-setup",
        "ready",
    )
    assert result["journey_invariants"] == {
        "installation_root_decision_owner": "bootstrap-launcher",
        "installation_root_prompt_occurrences": 1,
        "comfy_setup_initial_page": "OnboardingTargetModePage",
        "verified_setup_routes": 14,
        "first_interaction": "language",
    }
    scenario_values = cast(list[dict[str, object]], result["scenarios"])
    scenarios = {str(item["scenario"]): item for item in scenario_values}
    assert {
        "install",
        "install-failure",
        "install-complete",
        "repair",
        "repair-full",
        "repair-protected-data",
        "repair-failure",
        "repair-rollback",
        "repair-complete",
        "comfy-setup/managed-existing-sdxl/recommendations-anima",
        "comfy-setup/managed-existing-sdxl/completion",
        "comfy-setup/managed-existing-anima/recommendations-sdxl",
        "comfy-setup/managed-existing-anima/completion",
        "comfy-setup/managed-existing-mixed/completion",
        "comfy-setup/managed-existing-unsupported/recommendations-sdxl",
        "comfy-setup/managed-scan-unavailable/scan-recovery",
        "comfy-setup/managed-decline-model/recommendations-sdxl",
        "comfy-setup/managed-decline-model/completion",
        "comfy-setup/managed-sdxl/recommendations-sdxl",
        "comfy-setup/managed-anima/recommendations-anima",
        "comfy-setup/managed-sdxl-and-anima/recommendations-sdxl",
        "comfy-setup/managed-sdxl-and-anima/recommendations-anima",
        "comfy-setup/managed-sdxl-and-anima/model-download-review",
        "comfy-setup/managed-sdxl-and-anima/configuration-advanced",
        "comfy-setup/managed-sdxl-and-anima/setup-log",
        "comfy-setup/managed-sdxl-and-anima/completion-details",
        "comfy-setup/managed-model-download-retry/download-failure",
        "comfy-setup/managed-model-download-retry/completion",
        "comfy-setup/managed-civitai-unavailable/model-provider-recovery",
        "comfy-setup/managed-thumbnail-unavailable/model-provider-recovery",
        "comfy-setup/attached-decline-model/configuration",
        "comfy-setup/attached-decline-model/completion",
        "comfy-setup/remote-no-local-models/folders",
        "comfy-setup/remote-no-local-models/completion",
    }.issubset(scenarios)
    assert "comfy-setup/managed-decline-model/folders" not in scenarios
    assert "comfy-setup/managed-existing-sdxl/recommendations-sdxl" not in scenarios
    assert "comfy-setup/managed-existing-anima/recommendations-anima" not in scenarios
    assert not any(
        key.startswith("comfy-setup/managed-existing-mixed/recommendations-")
        for key in scenarios
    )
    assert "restored" in cast(str, scenarios["repair-rollback"]["status"])
    assert scenarios["comfy-setup/managed-sdxl-and-anima/provisioning"][
        "visible_progress_bars"
    ] == ["OnboardingOverallProgressBar"]
    assert scenarios["comfy-setup/managed-sdxl-and-anima/provisioning-model-download"][
        "visible_progress_bars"
    ] == ["OnboardingOverallProgressBar"]
    assert scenarios["comfy-setup/managed-sdxl-and-anima/setup-log"][
        "visible_progress_bars"
    ] == ["OnboardingOverallProgressBar"]
    assert (
        scenarios["comfy-setup/managed-civitai-unavailable/model-provider-recovery"][
            "page"
        ]
        == "OnboardingModelRecommendationPage"
    )
    side_effect_audit = cast(dict[str, int], result["side_effect_audit"])
    assert all(value == 0 for value in side_effect_audit.values())
    protected_sentinels = cast(dict[str, str], result["protected_sentinels"])
    assert len(protected_sentinels) == 5
    screenshot_paths = tuple(
        Path(cast(str, item["screenshot"])) for item in scenarios.values()
    )
    assert all(path.is_file() for path in screenshot_paths)
    for path in screenshot_paths:
        image = QImage(str(path))
        assert not image.isNull()
        assert not image.hasAlphaChannel()
        assert image.pixelColor(0, 0).lightness() < 80
        footer_start = (image.height() * 3) // 4
        assert any(
            image.pixelColor(x, y).name() != "#181818"
            for y in range(footer_start, image.height(), 8)
            for x in range(0, image.width(), 8)
        ), f"{path} leaves the high-DPI footer region unrendered"

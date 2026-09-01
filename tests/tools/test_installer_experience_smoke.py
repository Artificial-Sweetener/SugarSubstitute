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

"""Qualify the installer and repair presentation smoke harness headlessly."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from tools.installer_experience_smoke import run_headless_smoke


def test_headless_smoke_renders_complete_matrix_without_side_effects() -> None:
    """Render key install, onboarding, repair, failure, and completion states."""

    artifact_root = (
        Path(__file__).resolve().parents[2]
        / "build"
        / "qualification"
        / "test-installer-smoke"
    )

    result = run_headless_smoke(artifact_root=artifact_root)

    assert result["headless"] is True
    scenario_values = cast(list[dict[str, object]], result["scenarios"])
    scenarios = {str(item["scenario"]): item for item in scenario_values}
    assert {
        "install",
        "install-failure",
        "install-complete",
        "existing-model-skip",
        "repair",
        "repair-full",
        "repair-protected-data",
        "repair-failure",
        "repair-rollback",
        "repair-complete",
        "model-interests",
        "model-discovery-failure",
        "model-gallery",
        "model-gallery-selected",
        "model-download-failure",
        "model-download-complete",
    }.issubset(scenarios)
    gallery = scenarios["model-gallery"]["snapshot"]
    assert isinstance(gallery, dict)
    assert len(gallery["visible_models"]) == 3
    assert gallery["selected_models"] == ()
    selected_gallery = cast(
        dict[str, object], scenarios["model-gallery-selected"]["snapshot"]
    )
    assert selected_gallery["selected_models"]
    assert "restored" in cast(str, scenarios["repair-rollback"]["status"])
    side_effect_audit = cast(dict[str, int], result["side_effect_audit"])
    assert all(value == 0 for value in side_effect_audit.values())
    protected_sentinels = cast(dict[str, str], result["protected_sentinels"])
    assert len(protected_sentinels) == 5
    assert all(
        Path(cast(str, item["screenshot"])).is_file() for item in scenarios.values()
    )

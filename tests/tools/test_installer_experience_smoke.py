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
from typing import Never, cast

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tools import installer_experience_smoke
from tools import install_experience_interactive
from tools.install_experience_onboarding import OnboardingCheckSession
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
    assert result["schema_version"] == 3
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


def test_default_cli_runs_headless_without_opening_interactive_ui(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep visible qualification behind the explicit interactive flag."""

    calls: list[str] = []

    def record_headless(**_kwargs: object) -> dict[str, bool]:
        """Record deterministic headless routing."""

        calls.append("headless")
        return {"headless": True}

    def reject_interactive(*_args: object, **_kwargs: object) -> int:
        """Record an invalid visible route if the default ever reaches it."""

        calls.append("interactive")
        return 0

    monkeypatch.setattr(
        installer_experience_smoke,
        "run_headless_smoke",
        record_headless,
    )
    monkeypatch.setattr(
        installer_experience_smoke,
        "run_interactive_smoke",
        reject_interactive,
    )

    assert installer_experience_smoke.main([]) == 0
    assert calls == ["headless"]
    assert '"headless": true' in capsys.readouterr().out


def test_interactive_cli_requires_explicit_flag_and_preserves_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route an explicit setup walkthrough without running headless capture."""

    calls: list[tuple[str, str]] = []

    def record_interactive(
        page: str,
        *,
        surface: str,
        artifact_root: Path,
    ) -> int:
        """Record explicit interactive routing without creating a window."""

        _ = artifact_root
        calls.append((surface, page))
        return 17

    monkeypatch.setattr(
        installer_experience_smoke,
        "run_interactive_smoke",
        record_interactive,
    )
    monkeypatch.setattr(
        installer_experience_smoke,
        "run_headless_smoke",
        lambda **_kwargs: pytest.fail("Interactive mode invoked headless capture."),
    )

    assert (
        installer_experience_smoke.main(["--interactive", "--surface", "comfy-setup"])
        == 17
    )
    assert calls == [("comfy-setup", "install")]


def test_full_interactive_route_hands_real_launcher_into_setup_offscreen(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Prove the explicit full walkthrough joins both production windows safely."""

    application = cast(QApplication, QApplication.instance())
    opened_setups: list[tuple[Path, bool]] = []
    closed_sessions: list[bool] = []

    class SyntheticSession:
        """Record cleanup for the intercepted onboarding window boundary."""

        def close(self) -> None:
            """Record that the full-experience owner released setup."""

            closed_sessions.append(True)

    def record_setup(
        *,
        install_root: Path,
        install_root_locked: bool,
    ) -> OnboardingCheckSession:
        """Record the handoff without placing another window in this focused test."""

        opened_setups.append((install_root, install_root_locked))
        return cast(OnboardingCheckSession, SyntheticSession())

    monkeypatch.setattr(
        install_experience_interactive,
        "open_interactive_onboarding",
        record_setup,
    )

    attempts = 0

    def drive_launcher() -> None:
        """Click the enabled production action until synthetic handoff completes."""

        nonlocal attempts
        attempts += 1
        launchers = tuple(
            widget
            for widget in application.topLevelWidgets()
            if isinstance(widget, LauncherMainWindow)
        )
        for launcher in launchers:
            if launcher.view.primary_button.isEnabled():
                launcher.view.primary_button.click()
        if opened_setups or attempts >= 200:
            application.exit(0 if opened_setups else 1)
            return
        QTimer.singleShot(10, drive_launcher)

    class InertReleaseSource:
        """Fail if the synthetic workflow unexpectedly requests network metadata."""

        def load_manifest(self) -> Never:
            """Reject provider access in the no-install walkthrough."""

            raise AssertionError("Synthetic walkthrough requested a release manifest.")

    artifact_root = tmp_path / "qualification"
    QTimer.singleShot(0, drive_launcher)
    exit_code = install_experience_interactive.run_interactive_full_experience(
        application=application,
        artifact_root=artifact_root,
        release_source=InertReleaseSource(),
    )

    assert exit_code == 0
    assert opened_setups == [
        (artifact_root / "interactive" / "synthetic-install", True)
    ]
    assert closed_sessions == [True]
    assert not artifact_root.exists()

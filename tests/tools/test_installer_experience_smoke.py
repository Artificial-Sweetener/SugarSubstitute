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
from PySide6.QtWidgets import QApplication

from launcher.sugarsubstitute_launcher.ui.main_window import LauncherMainWindow
from tools import installer_experience_smoke
from tools import install_experience_interactive
from tools.install_experience_onboarding import OnboardingCheckSession


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


def test_live_model_capture_requires_explicit_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Keep real CivitAI access behind its named qualification action."""

    calls: list[Path] = []

    def record_live_capture(*, artifact_root: Path) -> dict[str, str]:
        """Record explicit provider routing without performing network work."""

        calls.append(artifact_root)
        return {"family": "sdxl"}

    monkeypatch.setattr(
        installer_experience_smoke,
        "capture_live_recommendation_page",
        record_live_capture,
    )

    assert installer_experience_smoke.main(["--live-model-capture"]) == 0
    assert len(calls) == 1
    assert '"family": "sdxl"' in capsys.readouterr().out


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

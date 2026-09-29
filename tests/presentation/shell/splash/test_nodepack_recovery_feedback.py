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

"""Render animated, stage-specific custom-node recovery in the real splash."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.nodepack_recovery_handoff import NodepackRecoveryHandoff
from substitute.presentation.shell.splash_window import SplashWindow
from sugarsubstitute_shared.presentation.localization import app_text
from tests.support.qt.lifecycle import destroy_qt_object

pytest_plugins = ("tests.support.qt.rendering_font",)


class _Clock:
    """Expose deterministic splash animation time."""

    def __init__(self) -> None:
        """Start the recovery clock before the first animated frame."""

        self.now = 0.0

    def __call__(self) -> float:
        """Return controlled monotonic time."""

        return self.now


class _Shell:
    """Record the old shell's visibility during the recovery splash."""

    def __init__(self) -> None:
        """Start with the workflow visible."""

        self.visible = True

    def hide(self) -> None:
        """Cover the old workflow only after the splash appears."""

        self.visible = False

    def show(self) -> None:
        """Restore the old workflow after a failed recovery."""

        self.visible = True


def test_recovery_splash_animates_and_explains_package_stages(
    qt_application_owner: QApplication,
    tmp_path: Path,
    offscreen_rendering_font: None,
) -> None:
    """The rendered status and console must advance together during recovery."""

    _ = offscreen_rendering_font
    clock = _Clock()
    shell = _Shell()
    splash = SplashWindow(
        backdrop_mode=None,
        activity_clock=clock,
        defer_animation_until_first_paint=True,
    )
    handoff = NodepackRecoveryHandoff(
        current_shell=lambda: shell,
        has_cancellable_jobs=lambda: False,
        create_splash=lambda: splash,
        reload_gui=lambda: True,
    )
    try:
        assert handoff.begin()
        qt_application_owner.processEvents()
        presenter = splash._feedback._presenter
        panel = splash._feedback._panel
        assert presenter is not None and panel is not None
        assert panel.status.text() == "Installing required custom nodes."
        clock.now = 1.0
        presenter.refresh()
        assert panel.status.text() == "Installing required custom nodes.."

        handoff.report(app_text("Getting source for %1 (%2/%3)", "NegPiP", 1, 1))
        assert panel.status.text() == "Getting source for NegPiP (1/1)."
        handoff.report(
            app_text("Installing dependencies for %1 (%2/%3)", "NegPiP", 1, 1)
        )
        assert panel.status.text() == "Installing dependencies for NegPiP (1/1)."
        assert splash._feedback._stream.snapshot()[-3:] == (
            "Installing required custom nodes",
            "Getting source for NegPiP (1/1)",
            "Installing dependencies for NegPiP (1/1).",
        )
        assert panel.status.grab().save(str(tmp_path / "nodepack-recovery-status.png"))
        splash._feedback.set_details_visible(True)
        qt_application_owner.processEvents()
        assert panel.grab().save(str(tmp_path / "nodepack-recovery-splash.png"))
    finally:
        handoff.cancel()
        destroy_qt_object(splash)

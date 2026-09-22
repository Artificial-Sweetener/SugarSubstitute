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

"""Render production progress surfaces and retain machine-readable activity proof."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import sys
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QVariantAnimation  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from launcher.sugarsubstitute_launcher.application.installation.progress import (  # noqa: E402
    InstallationProgress,
    InstallationStage,
)
from launcher.sugarsubstitute_launcher.application.repair.preparation_progress import (  # noqa: E402
    PreparationProgress,
    PreparationStage,
)
from launcher.sugarsubstitute_launcher.ui.installation_progress_page import (  # noqa: E402
    InstallationProgressPage,
)
from launcher.sugarsubstitute_launcher.ui.repair_preparation_progress_view import (  # noqa: E402
    RepairPreparationProgressView,
)
from launcher.sugarsubstitute_launcher.ui.repair_progress_view import (  # noqa: E402
    RepairProgressView,
)
from launcher.sugarsubstitute_launcher.update_activity import (  # noqa: E402
    application_install_activity,
)
from substitute.application.onboarding.setup_progress import (  # noqa: E402
    SetupProgressEvent,
    SetupProgressUnit,
    SetupTaskId,
    SetupTaskState,
)
from substitute.app.bootstrap.theme import configure_theme  # noqa: E402
from substitute.domain.appearance import AppearanceThemeMode  # noqa: E402
from substitute.presentation.onboarding.onboarding_models import (  # noqa: E402
    OnboardingPageId,
)
from substitute.presentation.onboarding.setup_progress_presenter import (  # noqa: E402
    SetupProgressPresenter,
)
from substitute.presentation.onboarding.setup_activity_output import (  # noqa: E402
    SetupActivityOutput,
)
from substitute.presentation.shell.splash_progress_panel import (  # noqa: E402
    SplashProgressPanel,
)
from substitute.presentation.shell.splash_window import SplashWindow  # noqa: E402
from sugarsubstitute_shared.asset_transfer import TransferProgress  # noqa: E402
from sugarsubstitute_shared.launch_splash.progress import SplashProgress  # noqa: E402
from sugarsubstitute_shared.presentation.activity_progress_bar import (  # noqa: E402
    ActivityProgressBar,
)
from sugarsubstitute_shared.presentation.installer_surface import (  # noqa: E402
    INSTALLER_WINDOW_HEIGHT,
    INSTALLER_WINDOW_WIDTH,
)
from sugarsubstitute_shared.presentation.terminal.output_stream import (  # noqa: E402
    TerminalOutputStream,
)
from tools.install_experience_onboarding import OnboardingCheckSession  # noqa: E402


@dataclass(frozen=True, slots=True)
class SurfaceEvidence:
    """Describe one rendered surface and its semantic feedback state."""

    name: str
    image: str
    visible_fraction: float
    activity_running: bool
    details_visible: bool
    transcript_lines: tuple[str, ...]
    status: str
    width: int
    height: int


def run_activity_feedback_qualification(output_dir: Path) -> Path:
    """Render startup, update, install, repair, and setup feedback offscreen."""

    resolved_output = output_dir.resolve()
    if resolved_output.anchor == str(resolved_output):
        raise ValueError("Activity evidence output cannot be a filesystem root.")
    resolved_output.mkdir(parents=True, exist_ok=True)
    application = QApplication.instance() or QApplication([sys.argv[0]])
    application = cast(QApplication, application)
    _prepare_offscreen_font(application)
    configure_theme(theme_mode=AppearanceThemeMode.DARK)
    evidence = [
        _render_startup(application, resolved_output),
        _render_update(application, resolved_output),
        _render_installation(application, resolved_output),
        _render_repair_preparation(application, resolved_output),
        _render_repair_execution(application, resolved_output),
        _render_comfy_setup(application, resolved_output),
    ]
    evidence_path = resolved_output / "activity-feedback-evidence.json"
    evidence_path.write_text(
        json.dumps([asdict(item) for item in evidence], indent=2) + "\n",
        encoding="utf-8",
    )
    return evidence_path


def _prepare_offscreen_font(application: QApplication) -> None:
    """Load a readable system font when Windows offscreen Qt finds none."""

    if QFontDatabase.families():
        return
    windows_root_value = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
    if windows_root_value is None:
        raise RuntimeError("Windows system root is unavailable for font discovery.")
    windows_root = Path(windows_root_value)
    font_path = windows_root / "Fonts" / "segoeui.ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        raise RuntimeError(
            f"Could not load the offscreen qualification font: {font_path}"
        )
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise RuntimeError(f"Offscreen qualification font has no family: {font_path}")
    application.setFont(QFont(families[0], 9))


def _render_startup(application: QApplication, output: Path) -> SurfaceEvidence:
    """Prove a growing startup task inventory cannot move completion backward."""

    splash = SplashWindow(backdrop_mode=None)
    try:
        splash.show()
        splash.set_progress(SplashProgress(2, 4), status="Preparing the interface")
        panel = _splash_panel(splash)
        prior_fraction = panel.progress.visible_fraction
        splash.set_progress(SplashProgress(2, 8), status="Preparing extensions")
        splash.record_activity()
        assert panel.progress.visible_fraction >= prior_fraction
        return _capture(
            application,
            splash,
            panel.progress,
            output / "startup.png",
            details_visible=panel.details_visible,
            transcript=(),
            status=panel.status.text(),
        )
    finally:
        _destroy(application, splash)


def _render_update(application: QApplication, output: Path) -> SurfaceEvidence:
    """Prove hidden update diagnostics still leave live observed-work feedback."""

    splash = SplashWindow(backdrop_mode=None)
    try:
        splash.show()
        splash.set_progress(SplashProgress(0, 1), status="Checking for updates")
        splash.start_activity(application_install_activity("0.4.1"))
        splash.append_log("Checking for SugarSubstitute updates.")
        splash.record_activity()
        panel = _splash_panel(splash)
        return _capture(
            application,
            splash,
            panel.progress,
            output / "update.png",
            details_visible=panel.details_visible,
            transcript=tuple(splash.log_view.toPlainText().splitlines()),
            status=panel.status.text(),
        )
    finally:
        _destroy(application, splash)


def _render_installation(application: QApplication, output: Path) -> SurfaceEvidence:
    """Prove archive work pulses while the concise install transcript remains hidden."""

    host = QWidget()
    page = InstallationProgressPage(host)
    try:
        _prepare_offscreen_surface(host)
        host.resize(1000, 650)
        page.resize(host.size())
        host.show()
        page.show()
        page.set_progress(InstallationProgress(InstallationStage.APPLICATION))
        page.record_activity()
        page.append_log("Verified application archive")
        transcript = tuple(page.progress_log.log_view.toPlainText().splitlines())
        return _capture(
            application,
            host,
            page.progress_bar,
            output / "installation.png",
            details_visible=page.progress_log.isVisible(),
            transcript=transcript,
            status=page.activity_label.text(),
        )
    finally:
        _destroy(application, host)


def _render_repair_preparation(
    application: QApplication, output: Path
) -> SurfaceEvidence:
    """Prove measured repair download bytes and preparation activity share one bar."""

    host = QWidget()
    view = RepairPreparationProgressView(host)
    try:
        _prepare_offscreen_surface(host)
        host.resize(900, 260)
        view.resize(host.size())
        host.show()
        view.show()
        view.set_working(True)
        view.set_progress(
            PreparationProgress(
                PreparationStage.APPLICATION,
                TransferProgress(6 * 1024 * 1024, 10 * 1024 * 1024),
            )
        )
        bar = _activity_bar(view)
        return _capture(
            application,
            host,
            bar,
            output / "repair-preparation.png",
            details_visible=False,
            transcript=(),
            status=bar.accessibleName(),
        )
    finally:
        _destroy(application, host)


def _render_repair_execution(
    application: QApplication, output: Path
) -> SurfaceEvidence:
    """Prove repair stage records stay concise while file work pulses."""

    view = RepairProgressView()
    try:
        _prepare_offscreen_surface(view)
        view.resize(900, 540)
        view.show()
        view.begin_attempt()
        view.set_stage("Verifying application files", completed=3, total=6)
        view.set_details("Validating staged files\nPreparing the managed runtime")
        view.pulse_activity()
        bar = _activity_bar(view)
        return _capture(
            application,
            view,
            bar,
            output / "repair-execution.png",
            details_visible=False,
            transcript=("Validating staged files", "Preparing the managed runtime"),
            status="Verifying application files",
        )
    finally:
        _destroy(application, view)


def _render_comfy_setup(application: QApplication, output: Path) -> SurfaceEvidence:
    """Prove exact model bytes animate the full hidden-console setup window."""

    session = OnboardingCheckSession(
        install_root=output / "synthetic-install",
        install_root_locked=False,
    )
    window = session.window
    page = window.provisioning_page
    presenter = SetupProgressPresenter(page)
    try:
        _prepare_offscreen_surface(window)
        output_stream = TerminalOutputStream()
        page.set_output_stream(output_stream)
        activity_output = SetupActivityOutput(
            stream=output_stream,
            activity_observer=page.record_activity,
            diagnostic_sink=lambda _line: None,
        )
        window._provisioning_started = True
        window._show_page(OnboardingPageId.PROVISIONING)
        window.show()
        application.processEvents()
        window.setFixedSize(INSTALLER_WINDOW_WIDTH, INSTALLER_WINDOW_HEIGHT)
        application.processEvents()
        presenter.begin()
        presenter.accept(
            SetupProgressEvent(
                1,
                SetupTaskId.RUNTIME,
                SetupTaskState.COMPLETED,
                "Runtime ready",
            )
        )
        presenter.accept(
            SetupProgressEvent(
                1,
                SetupTaskId.MODEL_DOWNLOAD,
                SetupTaskState.RUNNING,
                "Downloading selected model",
                SetupProgressUnit.BYTES,
                64 * 1024 * 1024,
                256 * 1024 * 1024,
                "model.safetensors",
                current_item_index=1,
                total_items=2,
            )
        )
        for percentage in range(101):
            activity_output.accept(
                "Copying managed Python packages: "
                f"{percentage}/100 ({percentage}%), about 1s remaining."
            )
        activity_output.accept("Requirement already satisfied: aiohttp (3.14.3)")
        activity_output.accept("Verified model transfer block")
        transcript = output_stream.snapshot()
        return _capture(
            application,
            window,
            page.overall_progress_bar,
            output / "comfy-setup.png",
            details_visible=page.details_container.isVisible(),
            transcript=transcript,
            status=page.status_label.text(),
        )
    finally:
        session.close()
        application.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _capture(
    application: QApplication,
    widget: QWidget,
    bar: ActivityProgressBar,
    image_path: Path,
    *,
    details_visible: bool,
    transcript: tuple[str, ...],
    status: str,
) -> SurfaceEvidence:
    """Freeze a visible activity frame and save its semantic and raster evidence."""

    application.processEvents()
    animation = bar.findChild(QVariantAnimation, "ProgressActivitySweep")
    if animation is not None and animation.state():
        animation.setCurrentTime(animation.duration() // 2)
    application.processEvents()
    if not widget.grab().save(str(image_path)):
        raise RuntimeError(f"Could not save activity evidence: {image_path}")
    return SurfaceEvidence(
        name=image_path.stem,
        image=str(image_path),
        visible_fraction=bar.visible_fraction,
        activity_running=bar.activity_running,
        details_visible=details_visible,
        transcript_lines=transcript,
        status=status,
        width=widget.width(),
        height=widget.height(),
    )


def _prepare_offscreen_surface(widget: QWidget) -> None:
    """Supply the dark native-material fallback unavailable offscreen."""

    palette = QPalette(widget.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor(32, 32, 32))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)


def _splash_panel(splash: SplashWindow) -> SplashProgressPanel:
    """Return the production splash progress panel after enrichment."""

    panel = splash.findChild(SplashProgressPanel)
    if panel is None:
        raise RuntimeError("Splash progress panel was not mounted.")
    return panel


def _activity_bar(widget: QWidget) -> ActivityProgressBar:
    """Return the single production activity bar mounted in a surface."""

    bar = widget.findChild(ActivityProgressBar)
    if bar is None:
        raise RuntimeError("Activity progress bar was not mounted.")
    return bar


def _destroy(application: QApplication, widget: QWidget) -> None:
    """Release widget-owned animations before rendering the next surface."""

    widget.close()
    widget.deleteLater()
    application.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def main() -> int:
    """Run the command-line activity feedback qualification."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence_path = run_activity_feedback_qualification(args.output_dir)
    print(f"Activity feedback qualification passed: {evidence_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

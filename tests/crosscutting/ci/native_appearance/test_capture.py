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

"""Test native appearance capture request and fixture ownership."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget

from substitute.domain.appearance import AppearanceThemeMode
from substitute.domain.onboarding import ComfyTargetMode, RuntimeBootstrapStatus
from tools.ci.capture_native_appearance import (
    _shutdown_capture_surface,
    build_capture_context,
    parse_args,
)


class _ExecutionRuntime:
    """Record capture worker shutdown."""

    def __init__(self) -> None:
        """Initialize the shutdown count."""

        self.shutdown_count = 0

    def shutdown(self) -> None:
        """Record one process-worker shutdown."""

        self.shutdown_count += 1


class _RuntimeServices:
    """Expose the capture cleanup collaborator used by the helper."""

    def __init__(self) -> None:
        """Create the recording execution runtime."""

        self.execution_runtime = _ExecutionRuntime()


class _CaptureApplicationBoundary:
    """Drain deferred deletion while recording capture-specific application quit."""

    def __init__(self) -> None:
        """Initialize empty boundary call history."""

        self.deferred_delete_count = 0
        self.quit_count = 0

    def sendPostedEvents(
        self,
        receiver: QObject | None,
        event_type: int,
    ) -> None:
        """Drain only the requested posted events through the real application."""

        assert event_type == QEvent.Type.DeferredDelete
        self.deferred_delete_count += 1
        QApplication.sendPostedEvents(receiver, event_type)

    def quit(self) -> None:
        """Record capture-local application termination intent."""

        self.quit_count += 1


def test_build_capture_context_owns_isolated_visual_fixture(tmp_path: Path) -> None:
    """Build a ready attached-local context without an external Comfy process."""

    context = build_capture_context(tmp_path)

    assert context.installation.installation_root == tmp_path.resolve()
    assert context.runtime.bootstrap_status is RuntimeBootstrapStatus.READY
    assert context.comfy_target.mode is ComfyTargetMode.ATTACHED_LOCAL
    assert context.comfy_target.workspace_path is not None
    assert context.comfy_target.workspace_path.is_dir()
    assert context.user_settings_dir.is_dir()
    assert context.session_dir.is_dir()
    assert context.cache_dir.is_dir()


def test_parse_args_builds_explicit_dark_capture_request(tmp_path: Path) -> None:
    """Parse deterministic dimensions and theme from the CI command line."""

    output_path = tmp_path / "dark.png"

    request = parse_args(
        [
            "--install-root",
            str(tmp_path / "install"),
            "--output",
            str(output_path),
            "--theme",
            "dark",
            "--width",
            "1280",
            "--height",
            "800",
            "--settle-ms",
            "250",
        ]
    )

    assert request.output_path == output_path
    assert request.theme is AppearanceThemeMode.DARK
    assert request.width == 1280
    assert request.height == 800
    assert request.settle_ms == 250


def test_capture_shutdown_destroys_frame_before_application_quit(
    qt_application_owner: QApplication,
) -> None:
    """Dispose shell-owned callbacks while localization translators remain valid."""

    _ = qt_application_owner
    app = _CaptureApplicationBoundary()
    frame = QWidget()
    destroyed: list[bool] = []
    frame.destroyed.connect(lambda: destroyed.append(True))
    runtime_services = _RuntimeServices()

    _shutdown_capture_surface(
        cast(Any, app),
        frame,
        cast(Any, runtime_services),
    )

    assert runtime_services.execution_runtime.shutdown_count == 1
    assert app.deferred_delete_count == 1
    assert app.quit_count == 1
    assert destroyed == [True]

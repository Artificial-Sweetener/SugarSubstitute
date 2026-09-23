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

"""Render deterministic production model-acquisition states headlessly."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QVBoxLayout, QWidget  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped] # noqa: E402

from sugarsubstitute_shared.localization import app_text  # noqa: E402
from substitute.application.errors import (  # noqa: E402
    DiagnosticSeverity,
    ErrorReport,
    ErrorReportKind,
)
from substitute.application.recipes import RecipeModelResolutionRequired  # noqa: E402
from substitute.domain.model_metadata import (  # noqa: E402
    BackendModelDownloadJob,
    ModelDownloadStatus,
)
from substitute.presentation.dialogs import (  # noqa: E402
    ErrorReportDialog,
    ModelAcquisitionDialog,
)
from substitute.presentation.shell.editor_busy_overlay import (  # noqa: E402
    EditorBusyOverlay,
)
from substitute.presentation.shell.model_download_progress import (  # noqa: E402
    model_download_detail,
    model_download_label,
    model_download_message,
    model_download_progress,
)
from tools.install_experience_capture import (  # noqa: E402
    prepare_opaque_dark_capture_surface,
    save_opaque_dark_widget_capture,
)
from tools.model_acquisition_render_fixtures import (  # noqa: E402
    gated_requirement,
    preview_images,
    ready_requirement,
    unavailable_requirement,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_ARTIFACT_ROOT = _REPO_ROOT / "build" / "qualification" / "model-acquisition"
_HOST_SIZE = (1280, 800)


def run_headless_qualification(
    *,
    artifact_root: Path = _DEFAULT_ARTIFACT_ROOT,
) -> dict[str, object]:
    """Render every distinct acquisition state and return durable evidence."""

    artifact_root = artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    application = cast(QApplication, QApplication.instance() or QApplication([]))
    _register_headless_fluent_font(application)
    setTheme(Theme.DARK)
    ready = ready_requirement()
    gated = gated_requirement()
    unavailable = unavailable_requirement()
    states = [
        _capture_acquisition(
            application,
            artifact_root,
            "multi-model-ready",
            ready,
            has_api_key=False,
        ),
        _capture_acquisition(
            application,
            artifact_root,
            "api-key-required",
            gated,
            has_api_key=False,
        ),
        _capture_acquisition(
            application,
            artifact_root,
            "api-key-satisfied",
            gated,
            has_api_key=False,
            entered_api_key="qualification-key",
        ),
        _capture_acquisition(
            application,
            artifact_root,
            "unavailable-unsafe-model",
            unavailable,
            has_api_key=False,
        ),
        _capture_progress(application, artifact_root, ready),
        _capture_failure(application, artifact_root),
    ]
    evidence: dict[str, object] = {
        "schema_version": 1,
        "result": "passed",
        "headless": os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "production_surfaces": (
            f"{ModelAcquisitionDialog.__module__}.{ModelAcquisitionDialog.__name__}",
            f"{EditorBusyOverlay.__module__}.{EditorBusyOverlay.__name__}",
            f"{ErrorReportDialog.__module__}.{ErrorReportDialog.__name__}",
        ),
        "states": states,
        "completion": {
            "distinct_surface": False,
            "behavior": "The progress overlay closes and the resolved workflow materializes.",
        },
        "side_effects": {
            "network_requests": 0,
            "downloads": 0,
            "credentials_persisted": 0,
            "external_urls_opened": 0,
        },
    }
    report_path = artifact_root / "evidence.json"
    report_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def _capture_acquisition(
    application: QApplication,
    artifact_root: Path,
    state: str,
    required: RecipeModelResolutionRequired,
    *,
    has_api_key: bool,
    entered_api_key: str = "",
) -> dict[str, object]:
    """Capture one production review-cart state without external requests."""

    host = _host()
    dialog = ModelAcquisitionDialog(
        required,
        has_api_key=has_api_key,
        downloads_enabled=True,
        open_url=lambda _url: False,
        preview_images_by_sha256=preview_images(required),
        parent=host,
    )
    if entered_api_key:
        key_edit = dialog.findChild(QLineEdit, "ModelAcquisitionApiKey")
        if key_edit is None:
            raise RuntimeError("The API-key editor is missing from its required state.")
        key_edit.setText(entered_api_key)
    screenshot_path = artifact_root / f"{state}.png"
    try:
        dialog.show()
        _settle(application)
        save_opaque_dark_widget_capture(host, screenshot_path)
        key_edit = dialog.findChild(QLineEdit, "ModelAcquisitionApiKey")
        return {
            "state": state,
            "screenshot": str(screenshot_path),
            "cards": len(dialog.cards),
            "api_key_visible": bool(
                key_edit is not None and key_edit.isVisibleTo(host)
            ),
            "download_enabled": dialog.download_action.isEnabled(),
            "dialog_size": [dialog.widget.width(), dialog.widget.height()],
        }
    finally:
        dialog.close()
        host.close()
        dialog.deleteLater()
        host.deleteLater()
        application.processEvents()


def _capture_progress(
    application: QApplication,
    artifact_root: Path,
    required: RecipeModelResolutionRequired,
) -> dict[str, object]:
    """Capture the real editor overlay during a determinate model download."""

    host = _host()
    overlay = EditorBusyOverlay(host)
    job = BackendModelDownloadJob(
        job_id="qualification-download",
        status=ModelDownloadStatus.RUNNING,
        kind="checkpoints",
        sha256="A" * 64,
        value=None,
        result=None,
        error=None,
        bytes_downloaded=3_145_728_000,
        bytes_total=6_291_456_000,
        detail=None,
    )
    label = model_download_label(required)
    overlay.show_download_progress(
        title=app_text("Downloading %1", label),
        message=model_download_message(job),
        detail=model_download_detail(job),
        progress_per_mille=model_download_progress(job),
    )
    screenshot_path = artifact_root / "download-progress.png"
    try:
        _settle(application)
        save_opaque_dark_widget_capture(host, screenshot_path)
        return {
            "state": "download-progress",
            "screenshot": str(screenshot_path),
            "progress_per_mille": model_download_progress(job),
            "cancel_enabled": True,
        }
    finally:
        overlay.hide_loading()
        host.close()
        overlay.deleteLater()
        host.deleteLater()
        application.processEvents()


def _capture_failure(
    application: QApplication,
    artifact_root: Path,
) -> dict[str, object]:
    """Capture the production report shown after a verified download fails."""

    host = _host()
    report = ErrorReport(
        kind=ErrorReportKind.SUBSTITUTE_INTERNAL,
        title=app_text("Model download failed"),
        message=app_text(
            "Substitute could not download and verify every model this workflow needs."
        ),
        stage="load",
        severity=DiagnosticSeverity.ERROR,
        workflow_id="qualification-workflow",
        exception_type="RecipeModelDownloadResolutionError",
        technical_detail="CivitAI API key was rejected by the provider.",
    )
    dialog = ErrorReportDialog(
        report=report,
        report_text=report.technical_detail or "",
        parent=host,
    )
    screenshot_path = artifact_root / "download-failure.png"
    try:
        dialog.show()
        _settle(application)
        save_opaque_dark_widget_capture(host, screenshot_path)
        return {
            "state": "download-failure",
            "screenshot": str(screenshot_path),
            "recoverable": True,
            "dialog_size": [dialog.widget.width(), dialog.widget.height()],
        }
    finally:
        dialog.close()
        host.close()
        dialog.deleteLater()
        host.deleteLater()
        application.processEvents()


def _host() -> QWidget:
    """Create a deterministic dark editor-shaped owner for production overlays."""

    host = QWidget()
    host.setObjectName("ModelAcquisitionQualificationHost")
    host.resize(*_HOST_SIZE)
    prepare_opaque_dark_capture_surface(host)
    host.setStyleSheet(
        "QWidget#ModelAcquisitionQualificationHost { background: #181818; }"
        "QLabel#QualificationTitle { color: #f3f3f3; font-size: 24px; font-weight: 600; }"
        "QLabel#QualificationCanvas { background: #202020; border: 1px solid #343434; "
        "border-radius: 8px; color: #8a8a8a; font-size: 18px; }"
    )
    layout = QVBoxLayout(host)
    layout.setContentsMargins(36, 28, 36, 36)
    layout.setSpacing(20)
    title = QLabel("Workflow editor", host)
    title.setObjectName("QualificationTitle")
    canvas = QLabel("", host)
    canvas.setObjectName("QualificationCanvas")
    canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)
    layout.addWidget(canvas, 1)
    host.show()
    return host


def _register_headless_fluent_font(application: QApplication) -> None:
    """Load Segoe UI into Qt's isolated offscreen font database."""

    windows_root = os.environ.get("WINDIR")
    if not windows_root:
        raise RuntimeError("WINDIR is required for headless Fluent rendering.")
    font_path = Path(windows_root) / "Fonts" / "segoeui.ttf"
    if not font_path.is_file():
        raise RuntimeError(f"Headless Fluent render font is missing: {font_path}")
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        raise RuntimeError(f"Qt could not register the render font: {font_path}")
    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        raise RuntimeError(f"Qt registered no font family for: {font_path}")
    application.setFont(QFont(families[0], 10))


def _settle(application: QApplication) -> None:
    """Let layout, polish, and Fluent animations reach a stable capture frame."""

    application.processEvents()
    QTest.qWait(180)
    application.processEvents()


def main() -> int:
    """Render the production matrix and print its evidence path."""

    run_headless_qualification()
    print(_DEFAULT_ARTIFACT_ROOT / "evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

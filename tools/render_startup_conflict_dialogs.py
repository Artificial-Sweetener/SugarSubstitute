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

"""Render startup conflict dialogs through Qt's offscreen platform."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence, cast

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QFont, QFontDatabase  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from launcher.sugarsubstitute_launcher.active_instance_dialog import (  # noqa: E402
    _build_active_instance_dialog,
)
from launcher.sugarsubstitute_launcher.ui.launcher_theme import (  # noqa: E402
    configure_launcher_theme,
)
from substitute.app.bootstrap.default_comfy_preflight import (  # noqa: E402
    _build_default_comfy_dialog,
)
from substitute.domain.onboarding import LocalComfyProcess  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    """Render both production Fluent dialogs into PNG evidence."""

    output_dir = _parse_arguments(argv).output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_application = QApplication.instance()
    application = (
        QApplication([])
        if existing_application is None
        else cast(QApplication, existing_application)
    )
    _load_headless_windows_fonts(application)
    configure_launcher_theme()

    duplicate_dialog = _build_active_instance_dialog()
    _render_dialog(
        application,
        duplicate_dialog,
        output_dir / "duplicate-instance-dialog.png",
    )
    comfy_dialog = _build_default_comfy_dialog(
        LocalComfyProcess(
            pid=8188,
            create_time=1.0,
            python_executable=Path("ComfyUI") / "python" / "python.exe",
            workspace=Path("ComfyUI"),
        )
    )
    _render_dialog(
        application,
        comfy_dialog,
        output_dir / "default-comfy-dialog.png",
    )
    print(output_dir)
    return 0


def _load_headless_windows_fonts(application: QApplication) -> None:
    """Register Segoe UI because Qt's offscreen plugin omits system fonts."""

    font_dir = Path(os.environ["WINDIR"]) / "Fonts"
    for filename in ("segoeui.ttf", "seguisb.ttf", "segoeuib.ttf"):
        if QFontDatabase.addApplicationFont(str(font_dir / filename)) < 0:
            raise OSError(f"Could not load the headless UI font: {filename}")
    application.setFont(QFont("Segoe UI", 9))


def _render_dialog(
    application: QApplication,
    dialog: QDialog,
    output_path: Path,
) -> None:
    """Capture one fully laid-out offscreen dialog and close it immediately."""

    dialog.show()
    application.processEvents()
    if not dialog.grab().save(str(output_path), "PNG"):
        raise OSError(f"Could not save rendered dialog: {output_path}")
    dialog.close()
    dialog.deleteLater()
    application.processEvents()


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse the explicit evidence directory."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("build") / "qualification" / "startup-dialogs",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())

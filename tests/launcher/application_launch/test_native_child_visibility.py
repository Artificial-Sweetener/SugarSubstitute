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

"""Prove supervised Windows GUI children retain native window visibility."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

from launcher.sugarsubstitute_launcher.process import spawn_detached_process


pytestmark = pytest.mark.platforms("windows")


def test_spawned_qt_child_is_natively_visible(tmp_path: Path) -> None:
    """Keep the first native show request visible across process supervision."""

    install_root = tmp_path / "SugarSubstitute"
    window_handle_path = tmp_path / "window-handle.txt"
    child_script = tmp_path / "visible_qt_child.py"
    child_script.write_text(
        "\n".join(
            (
                "from pathlib import Path",
                "import sys",
                "import win32gui",
                "from PySide6.QtWidgets import QApplication, QWidget",
                "application = QApplication([])",
                "window = QWidget()",
                "window.setWindowTitle('SugarSubstitute visibility probe')",
                "window.show()",
                "application.processEvents()",
                "visible = bool(win32gui.IsWindowVisible(int(window.winId())))",
                "Path(sys.argv[1]).write_text('visible' if visible else 'hidden', encoding='utf-8')",
                "raise SystemExit(0 if visible else 5)",
            )
        ),
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["QT_QPA_PLATFORM"] = "windows"
    process, _log_path = spawn_detached_process(
        (
            sys.executable,
            str(child_script),
            str(window_handle_path),
            f"--install-root={install_root}",
        ),
        environment=environment,
    )

    try:
        return_code = process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)

    assert return_code == 0
    assert window_handle_path.read_text(encoding="utf-8") == "visible"

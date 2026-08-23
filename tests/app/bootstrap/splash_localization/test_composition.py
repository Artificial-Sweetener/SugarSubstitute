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

"""Test splash-localization composition through the real splash window."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.splash_localization import (
    build_splash_localization_runtime,
)
from substitute.presentation.shell.splash_window import SplashWindow


def test_japanese_splash_constructs_with_localized_title_and_cancel_help(
    qt_application_owner: QApplication,
) -> None:
    """Show translated fixed chrome on the first visible application surface."""

    runtime = build_splash_localization_runtime(
        qt_application_owner,
        locale_override="ja",
    )
    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)

    assert splash.windowTitle() == "読み込み中..."
    assert cast(Any, splash.titleBar).closeBtn.toolTip() == "読み込みをキャンセル"
    splash.close()
    splash.deleteLater()
    runtime.manager.close()

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

"""Test localization of the isolated first-visible splash process."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.shared_splash_host import _parse_args
from substitute.app.bootstrap.splash_localization import (
    build_splash_localization_runtime,
)
from substitute.presentation.shell.splash_window import SplashWindow


def test_splash_host_locale_argument_uses_shared_validation() -> None:
    """Normalize the launcher or direct-app handoff before creating widgets."""

    assert _parse_args(["--locale=zh_CN"]).locale == "zh-Hans"
    assert _parse_args(["--locale=ja-JP"]).locale == "ja"


def test_japanese_splash_constructs_with_localized_title_and_cancel_help() -> None:
    """Show translated fixed chrome on the first visible application surface."""

    application = _application()
    runtime = build_splash_localization_runtime(
        application,
        locale_override="ja",
    )

    splash = SplashWindow(icon=QIcon(), backdrop_mode=None)

    assert splash.windowTitle() == "読み込み中..."
    assert cast(Any, splash.titleBar).closeBtn.toolTip() == "読み込みをキャンセル"
    splash.close()
    splash.deleteLater()
    runtime.manager.close()


def _application() -> QApplication:
    """Return the process application used by the isolated splash runtime."""

    return cast(QApplication, QApplication.instance() or QApplication([]))

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

"""Verify one cohesive onboarding-window capability."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTranslator

from substitute.presentation.onboarding.onboarding_shell_presentation import (
    OnboardingIssuePanel,
)
from sugarsubstitute_shared.localization import app_text

from tests.support.qt.lifecycle import ensure_qt_application


def test_onboarding_issue_panel_retains_semantic_copy_across_language_change() -> None:
    """Render stored application messages in the active locale on every read."""

    app = ensure_qt_application()
    resource_root = (
        Path(__file__).resolve().parents[4]
        / "substitute"
        / "presentation"
        / "resources"
        / "i18n"
    )
    chinese = QTranslator()
    japanese = QTranslator()
    assert chinese.load(str(resource_root / "sugarsubstitute_zh_CN.qm"))
    assert japanese.load(str(resource_root / "sugarsubstitute_ja_JP.qm"))
    assert app.installTranslator(chinese)
    panel = OnboardingIssuePanel()
    panel.set_issue_content(
        title=app_text("Finishing your setup"),
        body=app_text("Open Substitute"),
        detail="python.exe --technical-detail",
    )
    try:
        assert panel.text() == "正在完成设置\n打开 Substitute\npython.exe --technical-detail"

        assert app.removeTranslator(chinese)
        assert app.installTranslator(japanese)
        for widget in (panel, panel.title_label, panel.body_label):
            app.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

        assert (
            panel.text()
            == "セットアップを完了しています\nSubstitute を開く\npython.exe --technical-detail"
        )
        assert panel.toolTip() == "python.exe --technical-detail"
    finally:
        app.removeTranslator(japanese)
        app.removeTranslator(chinese)
        panel.close()

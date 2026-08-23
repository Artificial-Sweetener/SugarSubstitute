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

"""Test Comfy connection routing and localized copy."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QObject, QTranslator

from tests.presentation.settings.comfy_connection.support import (
    application,
    build_page,
)


def test_comfy_connection_page_wizard_escape_hatch_routes_to_callback(
    tmp_path: Path,
) -> None:
    """The explicit wizard button should keep reconfigure available."""

    application()
    calls: list[str] = []
    page = build_page(tmp_path, open_reconfigure_window=lambda: calls.append("open"))

    page.wizard_button.click()

    assert calls == ["open"]
    page.close()


def test_comfy_connection_page_switches_all_primary_copy_in_place(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    """The production Settings surface must not retain its English scaffold."""

    app = application()
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
    request.addfinalizer(lambda: app.removeTranslator(chinese))
    request.addfinalizer(lambda: app.removeTranslator(japanese))
    assert app.installTranslator(chinese)
    page = build_page(tmp_path)
    page.show()
    app.processEvents()

    assert page.source_group.title_label.text() == "ComfyUI 来源"
    assert page.configuration_group.title_label.text() == "受管理的本地设置"
    assert page.source_row.title_label.text() == "ComfyUI 来源"
    assert page.source_row.description_label.text() == (
        "选择 Substitute 用于生成图像的 ComfyUI 实例。"
    )
    assert page.managed_folder_row.title_label.text() == "ComfyUI 文件夹"
    assert page.model_folder_row.title_label.text() == "模型文件夹"
    assert page.endpoint_row.title_label.text() == "本地端点"
    assert page.setup_action_row.title_label.text() == "设置向导"
    assert page.connection_check_group.title_label.text() == "连接检查"
    assert page.refresh_button.text() == "刷新"
    assert page.test_button.text() == "测试连接"

    assert app.removeTranslator(chinese)
    assert app.installTranslator(japanese)
    for widget in (page, *page.findChildren(QObject)):
        app.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

    assert page.source_group.title_label.text() == "ComfyUI ソース"
    assert page.configuration_group.title_label.text() == (
        "管理対象のローカルセットアップ"
    )
    assert page.source_row.description_label.text() == (
        "画像生成に使用する ComfyUI 環境を選択します。"
    )
    assert page.managed_folder_row.title_label.text() == "ComfyUI フォルダー"
    assert page.model_folder_row.title_label.text() == "モデルフォルダー"
    assert page.endpoint_row.title_label.text() == "ローカルエンドポイント"
    assert page.setup_action_row.title_label.text() == "セットアップウィザード"
    assert page.connection_check_group.title_label.text() == "接続確認"
    assert page.refresh_button.text() == "更新"
    assert page.test_button.text() == "接続をテスト"

    assert app.removeTranslator(japanese)
    page.close()

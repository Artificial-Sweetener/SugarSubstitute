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

"""Test live localization of persistent Danbooru wiki header controls."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTranslator
from PySide6.QtWidgets import QApplication

from tests.presentation.danbooru.wiki_dialog.collaborators import (
    DanbooruWikiDialogOwner,
    ImmediateDispatcher,
    StubDanbooruWikiService,
)
from tests.presentation.danbooru.wiki_dialog.content_support import (
    page_view,
    success_result,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_header_actions_retranslate_without_recreating_dialog(
    danbooru_dialog_owner: DanbooruWikiDialogOwner,
    qt_application_owner: QApplication,
) -> None:
    """Keep persistent tooltips and accessibility in the active locale."""

    resource_root = PROJECT_ROOT / "substitute" / "presentation" / "resources" / "i18n"
    chinese = QTranslator()
    japanese = QTranslator()
    assert chinese.load(str(resource_root / "sugarsubstitute_zh_CN.qm"))
    assert japanese.load(str(resource_root / "sugarsubstitute_ja_JP.qm"))
    assert qt_application_owner.installTranslator(chinese)
    dialog = danbooru_dialog_owner.build(
        wiki_service=StubDanbooruWikiService(
            selection_results={"long hair": success_result(page_view())}
        ),
        selection_text="long hair",
        lookup_dispatcher=ImmediateDispatcher(),
    )
    buttons = (
        dialog._back_button,
        dialog._forward_button,
        dialog._copy_button,
        dialog._open_button,
        dialog._close_button,
    )
    try:
        assert [button.toolTip() for button in buttons] == [
            "返回",
            "前进",
            "复制标签标题",
            "在浏览器中打开标签百科文章",
            "关闭",
        ]
        assert [button.accessibleName() for button in buttons] == [
            button.toolTip() for button in buttons
        ]

        assert qt_application_owner.removeTranslator(chinese)
        assert qt_application_owner.installTranslator(japanese)
        for button in buttons:
            qt_application_owner.sendEvent(button, QEvent(QEvent.Type.LanguageChange))

        assert [button.toolTip() for button in buttons] == [
            "戻る",
            "進む",
            "タグのタイトルをコピー",
            "タグの Wiki 記事をブラウザーで開く",
            "閉じる",
        ]
        assert [button.accessibleName() for button in buttons] == [
            button.toolTip() for button in buttons
        ]
    finally:
        qt_application_owner.removeTranslator(japanese)
        qt_application_owner.removeTranslator(chinese)

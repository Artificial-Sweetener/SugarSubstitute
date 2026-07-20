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

"""Exercise packaged Chinese and Japanese application text through real Qt QMs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTranslator
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLineEdit, QWidget

from substitute.presentation.localization import (
    LocalizedLabel,
    LocalizedNativePushButton,
)
from substitute.presentation.dialogs import LocalizedColorDialog
from substitute.presentation.editor.panel.widgets.fields.native import (
    AudioRecordField,
    BoundingBoxField,
    ColorField,
    CurveField,
)
from substitute.application.ports.civitai_credential_store import CredentialStoreStatus
from substitute.presentation.settings.civitai_credential_status import (
    api_key_status_text,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasSceneGroup,
    OutputCanvasSourceGroup,
)
from substitute.presentation.canvas.output.output_canvas_navigation_bar import (
    scene_selector_full_text,
    source_selector_full_text,
)
from sugarsubstitute_shared.localization import app_text
from sugarsubstitute_shared.presentation.localization import (
    apply_application_text,
    set_localized_placeholder,
)
from tools.localization_catalog import extract_application_messages

_RESOURCE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "substitute"
    / "presentation"
    / "resources"
    / "i18n"
)


def test_catalog_extraction_includes_every_explicit_conditional_message() -> None:
    """Both branches of app_text conditionals must enter release catalogs."""

    sources = {
        message.source
        for message in extract_application_messages(Path(__file__).resolve().parents[1])
    }

    assert "Undock canvas" in sources
    assert "Redock canvas" in sources


def test_catalog_extraction_includes_every_localized_property_owner() -> None:
    """Keep placeholders, accessibility copy, and tooltips in release catalogs."""

    sources = {
        message.source
        for message in extract_application_messages(Path(__file__).resolve().parents[1])
    }

    assert {
        "Automatically detect",
        "Direct Comfy workflows contain no cube stack.",
        "Number of queued generations to create",
        "Search…",
        "Select model",
        "Toggle between expanded and compact cube cards.",
    } <= sources


def test_packaged_catalogs_switch_common_ui_copy_without_touching_authored_text() -> (
    None
):
    """Real QMs should retranslate visible properties and preserve editor values."""

    application = _application()
    chinese = _translator("sugarsubstitute_zh_CN.qm")
    japanese = _translator("sugarsubstitute_ja_JP.qm")
    assert application.installTranslator(chinese)
    owner = QWidget()
    status = LocalizedLabel(app_text("Close"), owner)
    status.setToolTip(app_text("Generation queue"))
    status.setAccessibleName(app_text("Close"))
    status.setAccessibleDescription(app_text("Generation queue"))
    action = LocalizedNativePushButton(app_text("Apply"), owner)
    editor = QLineEdit(owner)
    editor.setText("Close")
    set_localized_placeholder(editor, "Search settings")

    assert status.text() == "关闭"
    assert status.toolTip() == "生成队列"
    assert status.accessibleName() == "关闭"
    assert status.accessibleDescription() == "生成队列"
    assert action.text() == "应用"
    assert editor.text() == "Close"
    assert editor.placeholderText() == "搜索设置"

    assert application.removeTranslator(chinese)
    assert application.installTranslator(japanese)
    for widget in (owner, status, action, editor):
        application.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

    assert status.text() == "閉じる"
    assert status.toolTip() == "生成キュー"
    assert status.accessibleName() == "閉じる"
    assert status.accessibleDescription() == "生成キュー"
    assert action.text() == "適用"
    assert editor.text() == "Close"
    assert editor.placeholderText() == "設定を検索"

    assert application.removeTranslator(japanese)
    for widget in (owner, status, action, editor):
        application.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

    assert status.text() == "Close"
    assert status.accessibleName() == "Close"
    assert action.text() == "Apply"
    assert editor.text() == "Close"
    assert editor.placeholderText() == "Search settings"

    assert application.installTranslator(chinese)
    for widget in (owner, status, action, editor):
        application.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

    assert status.text() == "关闭"
    assert status.accessibleName() == "关闭"
    assert action.text() == "应用"
    assert editor.text() == "Close"
    assert editor.placeholderText() == "搜索设置"

    assert application.removeTranslator(chinese)
    owner.deleteLater()


def test_packaged_catalogs_translate_output_fallbacks_but_not_authored_matches() -> (
    None
):
    """Fallback metadata must translate without guessing from authored content."""

    application = _application()
    chinese = _translator("sugarsubstitute_zh_CN.qm")
    assert application.installTranslator(chinese)
    fallback_source = OutputCanvasSourceGroup(
        "fallback",
        "Output",
        {},
        label_is_default=True,
    )
    authored_source = OutputCanvasSourceGroup("authored", "Output", {})
    fallback_scene = OutputCanvasSceneGroup(
        "run-fallback",
        "fallback",
        "Scene",
        0,
        (),
        title_is_default=True,
    )
    authored_scene = OutputCanvasSceneGroup(
        "run-authored",
        "authored",
        "Scene",
        1,
        (),
    )

    assert (
        source_selector_full_text((fallback_source,), active_source_key="fallback")
        == "输出"
    )
    assert (
        source_selector_full_text((authored_source,), active_source_key="authored")
        == "Output"
    )
    assert (
        scene_selector_full_text(
            (fallback_scene,),
            active_scene_key="fallback",
            active_scene_overview=False,
        )
        == "场景"
    )
    assert (
        scene_selector_full_text(
            (authored_scene,),
            active_scene_key="authored",
            active_scene_overview=False,
        )
        == "Scene"
    )

    assert application.removeTranslator(chinese)


def test_packaged_catalogs_translate_native_widget_and_qfluent_dialog_chrome() -> None:
    """Exercise newly owned native controls through the compiled release catalogs."""

    application = _application()
    chinese = _translator("sugarsubstitute_zh_CN.qm")
    japanese = _translator("sugarsubstitute_ja_JP.qm")
    assert application.installTranslator(chinese)
    owner = QWidget()
    audio = AudioRecordField(None, owner)
    box = BoundingBoxField({"x": 1, "y": 2, "width": 3, "height": 4}, owner)
    curve = CurveField({}, owner)
    color_field = ColorField("#123456", owner)
    color_dialog = LocalizedColorDialog(
        QColor("#123456"),
        app_text("Choose color"),
        owner,
        enable_alpha=True,
    )
    try:
        assert audio.status_label.text() == "无音频"
        assert audio.record_button.toolTip() == "使用默认麦克风录制音频"
        assert box.text() == "x 1，y 2，3×4"
        assert curve.text() == "编辑曲线（2 个点）"
        assert color_field.picker.toolTip() == "选择颜色"
        assert color_dialog.editLabel.text() == "编辑颜色"
        assert color_dialog.opacityLabel.text() == "不透明度"
        assert color_dialog.yesButton.text() == "确定"

        assert application.removeTranslator(chinese)
        assert application.installTranslator(japanese)
        for widget in (
            owner,
            *owner.findChildren(QWidget),
            color_dialog,
            *color_dialog.findChildren(QWidget),
        ):
            application.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

        assert audio.status_label.text() == "音声なし"
        assert audio.record_button.toolTip() == "デフォルトのマイクで音声を録音"
        assert box.text() == "x 1・y 2・3×4"
        assert curve.text() == "カーブを編集（2点）"
        assert color_field.picker.toolTip() == "色を選択"
        assert color_dialog.editLabel.text() == "色を編集"
        assert color_dialog.opacityLabel.text() == "不透明度"
        assert color_dialog.yesButton.text() == "決定"
        assert color_field.value() == "#123456"
    finally:
        application.removeTranslator(japanese)
        application.removeTranslator(chinese)
        color_dialog.close()
        color_dialog.deleteLater()
        owner.deleteLater()


def test_nested_credential_status_copy_retranslates_in_place() -> None:
    """Translate composed secure-storage guidance without freezing opaque values."""

    application = _application()
    chinese = _translator("sugarsubstitute_zh_CN.qm")
    japanese = _translator("sugarsubstitute_ja_JP.qm")
    assert application.installTranslator(chinese)
    label = LocalizedLabel("")
    status = CredentialStoreStatus(
        available=False,
        backend_name="Linux Secret Service/KWallet",
        reason=app_text(
            "No compatible operating-system credential store is available."
        ),
        remediation=app_text(
            "Enable a supported operating-system credential store, then restart Substitute."
        ),
    )
    apply_application_text(label, api_key_status_text(status=status, has_key=False))
    try:
        assert label.text() == (
            "安全凭据存储不可用。 没有可用的兼容操作系统凭据存储。 "
            "启用受支持的操作系统凭据存储，然后重启 Substitute。"
        )

        assert application.removeTranslator(chinese)
        assert application.installTranslator(japanese)
        application.sendEvent(label, QEvent(QEvent.Type.LanguageChange))

        assert label.text() == (
            "安全な認証情報ストレージを利用できません。 "
            "対応しているオペレーティングシステムの認証情報ストアがありません。 "
            "対応しているオペレーティングシステムの認証情報ストアを有効にしてから、"
            "Substitute を再起動してください。"
        )
    finally:
        application.removeTranslator(japanese)
        application.removeTranslator(chinese)
        label.close()


def _translator(filename: str) -> QTranslator:
    """Load one packaged catalog or fail with its concrete filename."""

    translator = QTranslator()
    if not translator.load(str(_RESOURCE_ROOT / filename)):
        raise AssertionError(f"Could not load packaged catalog: {filename}")
    return translator


def _application() -> QApplication:
    """Return the shared QApplication used by Qt tests."""

    instance = QApplication.instance()
    if isinstance(instance, QApplication):
        return instance
    return QApplication([])

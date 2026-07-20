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

"""Test live localized-property refresh without rebuilding editable state."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QCoreApplication, QEvent, QTranslator
from PySide6.QtWidgets import QApplication, QComboBox, QLabel, QLineEdit, QWidget

from sugarsubstitute_shared.presentation.localization import (
    CompositeTranslator,
    LocalizationBindings,
    LocalizedComboItem,
    app_text,
    apply_application_text,
)
from substitute.presentation.localization import LocalizedBodyLabel


def test_composite_translator_uses_delegate_priority_and_replacement() -> None:
    """Resolve the first nonempty delegate and detach the old generation."""

    app_specific = _DictionaryTranslator({("Panel", "Open"): "打开"})
    qt_base = _DictionaryTranslator(
        {
            ("Panel", "Open"): "Qt 打开",
            ("Panel", "Cancel"): "取消",
        }
    )
    translator = CompositeTranslator((app_specific, qt_base))

    assert translator.translate("Panel", "Open") == "打开"
    assert translator.translate("Panel", "Cancel") == "取消"
    assert translator.translate("Panel", "Missing") == "Missing"

    japanese = _DictionaryTranslator({("Panel", "Open"): "開く"})
    detached = translator.replace_delegates((japanese,))

    assert detached == (app_specific, qt_base)
    assert translator.delegates == (japanese,)
    assert translator.translate("Panel", "Open") == "開く"
    assert translator.translate("Panel", "Cancel") == "Cancel"


def test_bound_widget_properties_refresh_on_language_change() -> None:
    """Reapply common visible and accessibility properties in one event pass."""

    _application()
    owner = QWidget()
    label = QLabel(owner)
    editor = QLineEdit(owner)
    current = {
        "title": "Generation",
        "tooltip": "Start generation",
        "placeholder": "Describe an image",
        "accessible": "Prompt",
    }
    bindings = LocalizationBindings(owner)
    bindings.bind_text(label, lambda: current["title"])
    bindings.bind_tooltip(label, lambda: current["tooltip"])
    bindings.bind_placeholder(editor, lambda: current["placeholder"])
    bindings.bind_accessible_name(editor, lambda: current["accessible"])

    assert label.text() == "Generation"
    assert label.toolTip() == "Start generation"
    assert editor.placeholderText() == "Describe an image"
    assert editor.accessibleName() == "Prompt"

    current.update(
        title="生成",
        tooltip="开始生成",
        placeholder="描述图像",
        accessible="提示词",
    )
    QCoreApplication.sendEvent(owner, QEvent(QEvent.Type.LanguageChange))

    assert label.text() == "生成"
    assert label.toolTip() == "开始生成"
    assert editor.placeholderText() == "描述图像"
    assert editor.accessibleName() == "提示词"
    owner.deleteLater()


def test_combo_binding_preserves_stable_selection_and_blocks_change_signal() -> None:
    """Rebuild localized labels without changing the selected domain identifier."""

    _application()
    owner = QWidget()
    combo = QComboBox(owner)
    current_labels = {"system": "System default", "ja": "日本語"}
    bindings = LocalizationBindings(owner)
    bindings.bind_combo_items(
        combo,
        lambda: (
            LocalizedComboItem("system", current_labels["system"]),
            LocalizedComboItem("ja", current_labels["ja"]),
        ),
    )
    combo.setCurrentIndex(combo.findData("ja"))
    changes: list[int] = []
    combo.currentIndexChanged.connect(changes.append)

    current_labels.update(system="システム設定", ja="日本語")
    QCoreApplication.sendEvent(owner, QEvent(QEvent.Type.LanguageChange))

    assert combo.currentData() == "ja"
    assert [combo.itemText(index) for index in range(combo.count())] == [
        "システム設定",
        "日本語",
    ]
    assert changes == []
    owner.deleteLater()


def test_retranslation_keeps_line_edit_text_selection_and_undo_history() -> None:
    """Change presentation properties without reconstructing an editable control."""

    _application()
    owner = QWidget()
    editor = QLineEdit(owner)
    editor.setText("日本語の入力")
    editor.setSelection(0, 3)
    current_placeholder = {"value": "Search"}
    bindings = LocalizationBindings(owner)
    bindings.bind_placeholder(editor, lambda: current_placeholder["value"])

    current_placeholder["value"] = "検索"
    QCoreApplication.sendEvent(owner, QEvent(QEvent.Type.LanguageChange))

    assert editor.text() == "日本語の入力"
    assert editor.selectedText() == "日本語"
    assert editor.placeholderText() == "検索"
    owner.deleteLater()


def test_localized_widget_retranslates_only_explicit_application_messages() -> None:
    """Keep opaque content literal while marked app copy follows LanguageChange."""

    application = _application()
    translator = _DictionaryTranslator({("AppText", "Search"): "検索"})
    assert application.installTranslator(translator)
    marked = LocalizedBodyLabel(app_text("Search"))
    authored = LocalizedBodyLabel("作者が入力した文字")
    try:
        QCoreApplication.sendEvent(marked, QEvent(QEvent.Type.LanguageChange))
        QCoreApplication.sendEvent(authored, QEvent(QEvent.Type.LanguageChange))

        assert marked.text() == "検索"
        assert authored.text() == "作者が入力した文字"
    finally:
        application.removeTranslator(translator)
        marked.deleteLater()
        authored.deleteLater()


def test_opaque_replacement_releases_prior_localized_binding() -> None:
    """Language changes must not resurrect app copy replaced by authored text."""

    application = _application()
    translator = _DictionaryTranslator({("AppText", "Search"): "検索"})
    assert application.installTranslator(translator)
    wrapped = LocalizedBodyLabel(app_text("Search"))
    applied = QLabel()
    apply_application_text(applied, app_text("Search"))
    try:
        wrapped.setText("用户输入")
        apply_application_text(applied, "作者が入力した文字")
        QCoreApplication.sendEvent(wrapped, QEvent(QEvent.Type.LanguageChange))
        QCoreApplication.sendEvent(applied, QEvent(QEvent.Type.LanguageChange))

        assert wrapped.text() == "用户输入"
        assert applied.text() == "作者が入力した文字"
    finally:
        application.removeTranslator(translator)
        wrapped.deleteLater()
        applied.deleteLater()


def _application() -> QApplication:
    """Return the process application required by offscreen widget tests."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


class _DictionaryTranslator(QTranslator):
    """Provide deterministic translations without compiling test catalogs."""

    def __init__(self, translations: dict[tuple[str, str], str]) -> None:
        """Store translations indexed by Qt context and source text."""

        super().__init__()
        self._translations = translations

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: str | None = None,
        n: int = -1,
    ) -> str:
        """Return a mapped translation while ignoring unused plural metadata."""

        del disambiguation, n
        return self._translations.get((context, source_text), "")

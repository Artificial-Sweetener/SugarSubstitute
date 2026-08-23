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

"""Verify About page snapshot, localization, and async-refresh contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtCore import QEvent, QObject, QTranslator
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QLabel, QWidget

from substitute.application.about import AboutInfoService
from tests.presentation.settings.about.about_settings_harness import (
    AboutInfoServiceDouble,
    AboutPageFactory,
    BlockingAboutInfoService,
    application,
    bind_refreshed_snapshot,
    label_texts,
    threaded_task_runner_factory,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _NoBackendCapabilities:
    """Provide an unavailable backend for production About copy tests."""

    def get_capabilities(self) -> None:
        """Return no connected backend capabilities."""

        return None


def test_about_page_renders_refreshed_snapshot(
    about_page_factory: AboutPageFactory,
) -> None:
    """Render version, project, license, and acknowledgement content."""

    app = application()
    service = AboutInfoServiceDouble()
    page = about_page_factory(service, None)
    bind_refreshed_snapshot(page, service)
    page.resize(1000, 640)
    page.show()
    app.processEvents()

    labels = label_texts(page)
    assert "SugarSubstitute" in labels
    assert "Version information" in labels
    sugar_subtitle = page.findChild(QLabel, "AboutVersionSubtitle-SugarSubstitute")
    assert sugar_subtitle is not None
    assert sugar_subtitle.toolTip() == "The desktop native Qt frontend for ComfyUI"
    assert "QPane" in labels
    assert "2.0.1" in labels
    pyside_author = page.findChild(QLabel, "AboutVersionAuthor-PySide6")
    assert pyside_author is not None
    assert pyside_author.toolTip() == "by the Qt Company"
    assert "Project" in labels
    assert "Widget project summary" in labels
    assert "License" in labels
    assert "GNU General Public License v3" in labels
    assert "Supporters" in labels
    assert "Patron One" in labels
    assert "Special thanks" in labels
    assert "Contributor One" in labels
    assert page.findChild(QWidget, "AboutLicenseActionRow") is not None


def test_about_page_switches_production_copy_without_reconstruction(
    request: pytest.FixtureRequest,
    about_page_factory: AboutPageFactory,
) -> None:
    """Translate app copy in place while retaining the mounted widget owners."""

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
    service = AboutInfoService(
        backend_capabilities=cast(Any, _NoBackendCapabilities()),
        comfy_runtime_info=lambda: None,
        local_versions=lambda _names, *, fallback: fallback,
        app_version=lambda: "1.0.0",
    )
    page = about_page_factory(service, None)
    page.show()
    app.processEvents()
    original_project_card = page._project_card

    labels = label_texts(page)
    assert "版本信息" in labels
    assert "项目" in labels
    assert "许可证" in labels
    assert "支持者" in labels
    assert "特别鸣谢" in labels
    sugar_subtitle = page.findChild(QLabel, "AboutVersionSubtitle-SugarSubstitute")
    assert sugar_subtitle is not None
    assert sugar_subtitle.toolTip() == "适用于 ComfyUI 的原生 Qt 桌面前端"
    assert page._project_card.description_label.text() == (
        "SugarSubstitute 为 ComfyUI 提供专注的 PySide6 工作区，支持基于方块的"
        "工作流组合、托管模型元数据、提示词工具以及集成的图像画布工作流。"
    )
    assert any(text.startswith("SugarSubstitute 是自由软件") for text in labels)

    assert app.removeTranslator(chinese)
    assert app.installTranslator(japanese)
    for widget in (page, *page.findChildren(QObject)):
        app.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

    labels = label_texts(page)
    assert "バージョン情報" in labels
    assert "プロジェクト" in labels
    assert "ライセンス" in labels
    assert "支援者" in labels
    assert "スペシャルサンクス" in labels
    assert sugar_subtitle.toolTip() == (
        "ComfyUI 用のデスクトップネイティブ Qt フロントエンド"
    )
    assert page._project_card.description_label.text() == (
        "SugarSubstitute は ComfyUI 用の使いやすい PySide6 ワークスペースです。"
        "キューブによるワークフロー構成、管理されたモデルメタデータ、"
        "プロンプトツール、統合画像キャンバスのワークフローに対応しています。"
    )
    assert any(
        text.startswith("SugarSubstitute は自由ソフトウェアです") for text in labels
    )
    assert page._project_card is original_project_card
    assert app.removeTranslator(japanese)


def test_about_page_rebinds_snapshot_without_widget_growth(
    about_page_factory: AboutPageFactory,
) -> None:
    """Reuse the rendered subtree when a refreshed snapshot keeps the same rows."""

    service = AboutInfoServiceDouble()
    page = about_page_factory(service, None)
    bind_refreshed_snapshot(page, service)
    initial_count = len(page.findChildren(QWidget))

    bind_refreshed_snapshot(page, service)

    assert len(page.findChildren(QWidget)) == initial_count


def test_about_page_starts_snapshot_without_blocking_owner_thread(
    about_page_factory: AboutPageFactory,
) -> None:
    """Return from activation while snapshot work remains behind its barrier."""

    service = BlockingAboutInfoService(qpane_version="3.1.4")
    page = about_page_factory(service, threaded_task_runner_factory())
    runner = cast(Any, page)._async_runner
    completed = QSignalSpy(runner.taskCompleted)
    page.show()
    application().processEvents()

    page.set_settings_page_active(True)

    assert service.started.wait(timeout=5.0)
    assert not service.release_timed_out
    assert "placeholder" in label_texts(page)
    service.release.set()
    wait_for_qt_condition(lambda: "3.1.4" in label_texts(page), timeout_ms=5000)
    assert completed.count() == 1
    assert "3.1.4" in label_texts(page)

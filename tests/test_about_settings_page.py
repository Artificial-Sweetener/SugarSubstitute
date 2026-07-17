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

"""Widget tests for the About Settings page."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, cast

import pytest
from PySide6.QtCore import QObject, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QAbstractButton,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from substitute.application.about import (
    GPL_V3_LICENSE_HTML,
    AboutInfoService,
    AboutInfoSnapshot,
    AboutVersionRow,
    AboutVersionStatus,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.app.bootstrap.settings_execution import (
    create_settings_task_runner_factory,
)
from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)
from substitute.presentation.settings.about_page import AboutSettingsPage
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunner,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_style import SETTINGS_CARD_GROUP_SPACING
from tests.execution_test_helpers import ExecutionRuntimeStub

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "About Settings Qt tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _AboutInfoService:
    """Return deterministic About snapshots for widget tests."""

    def __init__(self, *, qpane_version: str = "2.0.1") -> None:
        """Store deterministic version values for refreshed snapshots."""

        self._qpane_version = qpane_version

    def placeholder_snapshot(self) -> AboutInfoSnapshot:
        """Return the initial placeholder snapshot."""

        return _snapshot("placeholder")

    def snapshot(self) -> AboutInfoSnapshot:
        """Return the refreshed snapshot."""

        return _snapshot(self._qpane_version)


class _SlowAboutInfoService(_AboutInfoService):
    """Return an About snapshot after a deterministic worker delay."""

    def snapshot(self) -> AboutInfoSnapshot:
        """Delay long enough to prove route activation does not block."""

        time.sleep(0.05)
        return super().snapshot()


def _task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for About page tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def _threaded_task_runner_factory() -> SettingsAsyncTaskRunnerFactory:
    """Create a runtime-backed Settings factory for async timing assertions."""

    return create_settings_task_runner_factory(
        ExecutionRuntimeStub(),
        resource_lifecycle=ShellResourceLifecycle(),
    )


def test_about_settings_page_renders_refreshed_snapshot() -> None:
    """About page should render versions, project copy, and acknowledgement rows."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(1000, 640)
    page.show()
    app.processEvents()

    labels = _label_texts(page)
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
    page.close()


def test_about_settings_page_rebinds_matching_snapshot_without_widget_growth() -> None:
    """Repeated About binds with the same rows should reuse the rendered subtree."""

    _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )
    _bind_refreshed_snapshot(page)
    initial_count = len(page.findChildren(QWidget))

    _bind_refreshed_snapshot(page)

    assert len(page.findChildren(QWidget)) == initial_count
    page.close()


def test_about_settings_page_loads_first_active_snapshot_asynchronously() -> None:
    """Route activation should request About data without blocking the UI thread."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _SlowAboutInfoService(qpane_version="3.1.4")),
        task_runner_factory=_threaded_task_runner_factory(),
    )
    page.show()
    app.processEvents()

    started_at = time.perf_counter()
    page.set_settings_page_active(True)
    elapsed_ms = (time.perf_counter() - started_at) * 1000.0

    assert elapsed_ms < 40.0
    assert "placeholder" in _label_texts(page)

    _process_events_until(app, lambda: "3.1.4" in _label_texts(page))

    assert "3.1.4" in _label_texts(page)
    page.close()


def test_about_settings_page_uses_two_version_columns_when_wide() -> None:
    """Version information should use two card columns at normal Settings widths."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(1000, 640)
    page.show()
    app.processEvents()

    group = page.findChild(QWidget, "AboutVersionCardGroup")
    assert group is not None
    assert group.sizePolicy().verticalPolicy() is QSizePolicy.Policy.Maximum
    group.resize(1000, group.height())
    app.processEvents()

    grid_container = group.findChild(QWidget, "AboutVersionCardGrid")
    assert grid_container is not None
    layout = grid_container.layout()
    assert isinstance(layout, QGridLayout)
    assert layout.horizontalSpacing() == SETTINGS_CARD_GROUP_SPACING
    assert layout.verticalSpacing() == SETTINGS_CARD_GROUP_SPACING
    assert group.property("aboutVersionColumnCount") == 2
    assert _card_position(page, layout, "SugarSubstitute") == (0, 0)
    assert _card_position(page, layout, "ComfyUI") == (0, 1)
    assert _card_position(page, layout, "SugarCubes") == (1, 0)
    assert _card_position(page, layout, "SubstituteBackend") == (1, 1)
    assert _card_position(page, layout, "SugarDSL") == (2, 0)
    assert _card_position(page, layout, "QPane") == (2, 1)
    assert _card_position(page, layout, "PySide6FluentWidgets") == (3, 0)
    assert _card_position(page, layout, "PySide6") == (3, 1)
    assert _version_card(page, "QPane").height() == 80
    assert _version_card(page, "QPane").property("aboutVersionLayoutMode") == "wide"
    page.close()


def test_about_settings_page_uses_one_full_width_version_column_when_width_starved() -> (
    None
):
    """Version cards should use the normal Settings card span in one column."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(760, 720)
    page.show()
    app.processEvents()

    group = page.findChild(QWidget, "AboutVersionCardGroup")
    assert group is not None
    grid_container = group.findChild(QWidget, "AboutVersionCardGrid")
    assert grid_container is not None
    layout = grid_container.layout()
    assert isinstance(layout, QGridLayout)
    assert group.property("aboutVersionColumnCount") == 1

    for object_key in _VERSION_OBJECT_KEYS:
        card = _version_card(page, object_key)
        assert _card_position(page, layout, object_key)[1] == 0
        assert card.width() == grid_container.width()
        _assert_card_children_do_not_overlap(card)
        assert card.property("aboutVersionLayoutMode") == "wide"
    page.close()


def test_about_settings_page_elides_wide_subtitles_under_two_column_pressure() -> None:
    """Wide cards should elide bounded subtitles instead of clipping hidden lines."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(940, 720)
    page.show()
    app.processEvents()

    group = page.findChild(QWidget, "AboutVersionCardGroup")
    assert group is not None
    assert group.property("aboutVersionColumnCount") == 2
    for object_key in ("ComfyUI", "SugarDSL"):
        card = _version_card(page, object_key)
        subtitle = _version_child_label(card, f"AboutVersionSubtitle-{object_key}")
        assert card.property("aboutVersionLayoutMode") == "wide"
        assert subtitle.text().count("\n") <= 1
        assert "…" in subtitle.text()
        assert subtitle.toolTip() != subtitle.text()
        assert subtitle.height() >= (
            subtitle.fontMetrics().lineSpacing()
            * max(1, len(subtitle.text().splitlines()))
        )
        _assert_card_children_do_not_overlap(card)
    page.close()


def test_about_settings_page_uses_compact_version_card_layout_at_narrow_width() -> None:
    """Narrow one-column cards should use an intentional stacked layout."""

    app = _app()
    page = AboutSettingsPage(
        cast(
            AboutInfoService,
            _AboutInfoService(qpane_version="2.0.1.dev1.gabcdef.d20260525"),
        ),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(420, 760)
    page.show()
    app.processEvents()

    group = page.findChild(QWidget, "AboutVersionCardGroup")
    assert group is not None
    assert group.property("aboutVersionColumnCount") == 1
    qpane_card = _version_card(page, "QPane")
    qpane_value = _version_child_label(qpane_card, "AboutVersionValue-QPane")
    qpane_title = _version_child_label(qpane_card, "AboutVersionTitle-QPane")
    qpane_subtitle = _version_child_label(qpane_card, "AboutVersionSubtitle-QPane")
    qpane_author = _version_child_label(qpane_card, "AboutVersionAuthor-QPane")
    qpane_icon = _version_child(qpane_card, "AboutVersionLinkIconSlot-QPane")

    assert qpane_card.property("aboutVersionLayoutMode") == "compact"
    assert qpane_card.height() == 108
    assert qpane_value.text() != qpane_value.toolTip()
    assert qpane_value.toolTip().startswith("2.0.1.dev1.gabcdef")
    assert (
        abs(
            _mapped_rect(qpane_title, qpane_card).center().y()
            - _mapped_rect(qpane_value, qpane_card).center().y()
        )
        <= 2
    )
    assert (
        _mapped_rect(qpane_subtitle, qpane_card).top()
        > _mapped_rect(
            qpane_title,
            qpane_card,
        ).bottom()
    )
    assert (
        _mapped_rect(qpane_author, qpane_card).top()
        > _mapped_rect(
            qpane_subtitle,
            qpane_card,
        ).bottom()
    )
    icon_rect = _mapped_rect(qpane_icon, qpane_card)
    subtitle_rect = _mapped_rect(qpane_subtitle, qpane_card)
    author_rect = _mapped_rect(qpane_author, qpane_card)
    assert subtitle_rect.top() <= icon_rect.center().y() <= author_rect.bottom()
    assert qpane_card.rect().contains(icon_rect)
    for object_key in _VERSION_OBJECT_KEYS:
        _assert_card_children_do_not_overlap(_version_card(page, object_key))
    page.close()


def test_about_settings_page_uses_minimum_version_card_layout_at_minimum_width() -> (
    None
):
    """Minimum-width cards should remain bounded and overlap-free."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(320, 760)
    page.show()
    app.processEvents()

    group = page.findChild(QWidget, "AboutVersionCardGroup")
    assert group is not None
    grid_container = group.findChild(QWidget, "AboutVersionCardGrid")
    assert grid_container is not None
    assert group.property("aboutVersionColumnCount") == 1
    for object_key in _VERSION_OBJECT_KEYS:
        card = _version_card(page, object_key)
        assert card.property("aboutVersionLayoutMode") == "minimum"
        assert card.height() == 116
        assert card.width() <= group.width()
        assert card.width() == grid_container.width()
        _assert_card_children_do_not_overlap(card)
    page.close()


def test_about_settings_page_links_version_cards_to_external_projects() -> None:
    """Version cards should expose passive project icons and card links."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(1000, 640)
    page.show()
    app.processEvents()

    expected_github_urls = {
        "SugarSubstitute": "https://github.com/Artificial-Sweetener/SugarSubstitute",
        "ComfyUI": "https://github.com/Comfy-Org/ComfyUI",
        "SubstituteBackend": "https://github.com/Artificial-Sweetener/Substitute-Backend",
        "SugarCubes": "https://github.com/Artificial-Sweetener/SugarCubes",
        "SugarDSL": "https://github.com/Artificial-Sweetener/Sugar-DSL",
        "QPane": "https://github.com/Artificial-Sweetener/QPane",
        "PySide6FluentWidgets": "https://github.com/zhiyiYo/PyQt-Fluent-Widgets",
    }

    for object_key, url in expected_github_urls.items():
        card = _version_card(page, object_key)
        assert card.property("externalUrl") == url
        assert (
            page.findChild(QAbstractButton, f"AboutVersionGitHub-{object_key}") is None
        )
        icon_slot = page.findChild(QWidget, f"AboutVersionLinkIconSlot-{object_key}")
        assert icon_slot is not None
        assert "GitHub" in icon_slot.accessibleName()
        assert (
            page.findChild(QWidget, f"AboutVersionGitHubIcon-{object_key}") is not None
        )

    pyside_card = _version_card(page, "PySide6")
    assert pyside_card.property("externalUrl") == "https://pyside.org/"
    assert page.findChild(QAbstractButton, "AboutVersionQt-PySide6") is None
    pyside_icon_slot = page.findChild(QWidget, "AboutVersionLinkIconSlot-PySide6")
    assert pyside_icon_slot is not None
    assert pyside_icon_slot.accessibleName() == "PySide6 project website"
    assert page.findChild(QWidget, "AboutVersionQtIcon-PySide6") is not None
    page.close()


def test_about_settings_page_version_cards_keep_hover_and_press_feedback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Linked version cards should retain Fluent hover and pressed feedback state."""

    app = _app()
    opened_urls: list[str] = []

    def record_opened_url(url: str) -> bool:
        """Record one URL that would have opened in the desktop shell."""

        opened_urls.append(url)
        return True

    monkeypatch.setattr(
        "substitute.presentation.settings.about_page._open_external_url",
        record_opened_url,
    )
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(1000, 640)
    page.show()
    app.processEvents()

    card = _version_card(page, "SugarSubstitute")
    cursor_targets = (
        card,
        _version_child_label(card, "AboutVersionTitle-SugarSubstitute"),
        _version_child_label(card, "AboutVersionSubtitle-SugarSubstitute"),
        _version_child_label(card, "AboutVersionValue-SugarSubstitute"),
        _version_child_label(card, "AboutVersionAuthor-SugarSubstitute"),
        _version_child(card, "AboutVersionLinkIconSlot-SugarSubstitute"),
        _version_child(card, "AboutVersionGitHubIcon-SugarSubstitute"),
    )
    for target in cursor_targets:
        assert target.cursor().shape() is Qt.CursorShape.PointingHandCursor

    assert card.property("aboutVersionHovered") is False
    assert card.property("aboutVersionPressed") is False

    QTest.mouseMove(card, card.rect().center())
    app.processEvents()

    assert card.property("aboutVersionHovered") is True

    QTest.mousePress(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )
    app.processEvents()

    assert card.property("aboutVersionPressed") is True

    QTest.mouseRelease(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )
    app.processEvents()

    assert card.property("aboutVersionPressed") is False
    assert opened_urls == ["https://github.com/Artificial-Sweetener/SugarSubstitute"]
    page.close()


def test_about_settings_page_opens_project_link_from_version_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking a version card body should open its external project link."""

    app = _app()
    opened_urls: list[str] = []

    def record_opened_url(url: str) -> bool:
        """Record one URL that would have opened in the desktop shell."""

        opened_urls.append(url)
        return True

    monkeypatch.setattr(
        "substitute.presentation.settings.about_page._open_external_url",
        record_opened_url,
    )
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(900, 640)
    page.show()
    app.processEvents()

    card = _version_card(page, "SugarSubstitute")
    QTest.mouseClick(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(24, card.height() // 2),
    )

    assert opened_urls == ["https://github.com/Artificial-Sweetener/SugarSubstitute"]
    page.close()


def test_about_settings_page_opens_project_link_from_version_icon_area(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking the passive icon area should activate the owning version card."""

    app = _app()
    opened_urls: list[str] = []

    def record_opened_url(url: str) -> bool:
        """Record one URL that would have opened in the desktop shell."""

        opened_urls.append(url)
        return True

    monkeypatch.setattr(
        "substitute.presentation.settings.about_page._open_external_url",
        record_opened_url,
    )
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(900, 640)
    page.show()
    app.processEvents()

    icon_slot = page.findChild(QWidget, "AboutVersionLinkIconSlot-SugarSubstitute")
    assert icon_slot is not None
    QTest.mouseClick(
        icon_slot,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        icon_slot.rect().center(),
    )

    assert opened_urls == ["https://github.com/Artificial-Sweetener/SugarSubstitute"]
    page.close()


def test_about_settings_page_renders_version_metadata_as_two_lines() -> None:
    """Version cards should pair title/subtitle with version/author trailing lines."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(1000, 640)
    page.show()
    app.processEvents()

    pyside_author = page.findChild(QLabel, "AboutVersionAuthor-PySide6")
    pyside_value = page.findChild(QLabel, "AboutVersionValue-PySide6")
    assert pyside_author is not None
    assert pyside_value is not None
    assert pyside_author.toolTip() == "by the Qt Company"
    assert pyside_author.text().startswith("by the Qt")
    assert pyside_value.text() == "6.9.0"
    page.close()


def test_about_settings_page_aligns_version_metadata_columns() -> None:
    """Wide version cards should keep metadata aligned beside link icons."""

    app = _app()
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    page.resize(1000, 640)
    page.show()
    app.processEvents()

    value = page.findChild(QLabel, "AboutVersionValue-PySide6FluentWidgets")
    author = page.findChild(QLabel, "AboutVersionAuthor-PySide6FluentWidgets")
    trailing = page.findChild(QWidget, "AboutVersionTrailing-PySide6FluentWidgets")
    icon_slot = page.findChild(QWidget, "AboutVersionLinkIconSlot-PySide6FluentWidgets")
    icon = page.findChild(QWidget, "AboutVersionGitHubIcon-PySide6FluentWidgets")
    assert value is not None
    assert author is not None
    assert trailing is not None
    assert icon_slot is not None
    assert icon is not None
    assert value.alignment() & Qt.AlignmentFlag.AlignRight
    assert author.alignment() & Qt.AlignmentFlag.AlignRight
    assert abs(value.geometry().right() - author.geometry().right()) <= 1
    assert trailing.width() == 228
    metadata_stack = page.findChild(
        QWidget,
        "AboutVersionMetadata-PySide6FluentWidgets",
    )
    assert metadata_stack is not None
    metadata_text = page.findChild(
        QWidget,
        "AboutVersionMetadataText-PySide6FluentWidgets",
    )
    assert metadata_text is not None
    assert (
        abs(metadata_stack.geometry().center().y() - icon_slot.geometry().center().y())
        <= 1
    )
    qpane_card = page.findChild(QWidget, "AboutVersionCard-QPane")
    assert qpane_card is not None
    assert qpane_card.height() == 80
    assert icon_slot.size().width() == 38
    assert icon_slot.size().height() == 38
    assert icon.size().width() == 24
    assert icon.size().height() == 24

    fluent_widgets_subtitle = page.findChild(
        QLabel,
        "AboutVersionSubtitle-PySide6FluentWidgets",
    )
    assert fluent_widgets_subtitle is not None
    assert fluent_widgets_subtitle.font().pixelSize() == 11
    page.close()


def test_about_settings_page_license_button_opens_modal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """License action should open the GPLv3 modal with About license copy."""

    app = _app()
    opened_dialogs: list[_RecordedLicenseDialog] = []

    class _RecordedLicenseDialog:
        """Record license dialog construction and execution."""

        def __init__(
            self,
            *,
            license_html: str,
            parent: QWidget | None = None,
        ) -> None:
            """Store dialog construction arguments."""

            self.license_html = license_html
            self.parent = parent
            self.exec_calls = 0
            opened_dialogs.append(self)

        def exec(self) -> int:
            """Record a modal execution request."""

            self.exec_calls += 1
            return 0

    monkeypatch.setattr(
        "substitute.presentation.settings.about_page.LicenseDialog",
        _RecordedLicenseDialog,
    )
    page = AboutSettingsPage(
        cast(AboutInfoService, _AboutInfoService()),
        task_runner_factory=_task_runner_factory,
    )

    _bind_refreshed_snapshot(page)
    button = page.findChild(QAbstractButton, "AboutReadLicenseButton")
    assert button is not None
    button.click()
    app.processEvents()

    assert len(opened_dialogs) == 1
    assert opened_dialogs[0].license_html == GPL_V3_LICENSE_HTML
    assert opened_dialogs[0].exec_calls == 1


def _snapshot(qpane_version: str) -> AboutInfoSnapshot:
    """Return one deterministic About snapshot."""

    return AboutInfoSnapshot(
        versions=(
            AboutVersionRow(
                label="SugarSubstitute",
                value="0.5.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="The desktop native Qt frontend for ComfyUI",
                authors="Artificial Sweetener",
                external_url=(
                    "https://github.com/Artificial-Sweetener/SugarSubstitute"
                ),
            ),
            AboutVersionRow(
                label="ComfyUI",
                value="0.3.2",
                status=AboutVersionStatus.AVAILABLE,
                subtitle=(
                    "The most powerful and modular diffusion model GUI, api and backend"
                ),
                authors="Comfy Org",
                external_url="https://github.com/Comfy-Org/ComfyUI",
            ),
            AboutVersionRow(
                label="SugarCubes",
                value="0.9.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="Composable workflow units for ComfyUI",
                authors="Artificial Sweetener",
                external_url="https://github.com/Artificial-Sweetener/SugarCubes",
            ),
            AboutVersionRow(
                label="Substitute Backend",
                value="1.4.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="Allow communication between ComfyUI deployments & Substitute",
                authors="Artificial Sweetener",
                external_url=(
                    "https://github.com/Artificial-Sweetener/Substitute-Backend"
                ),
            ),
            AboutVersionRow(
                label="Sugar-DSL",
                value="0.2.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle=(
                    "The scripting language for composing ComfyUI workflows "
                    "with SugarCubes"
                ),
                authors="Artificial Sweetener",
                external_url="https://github.com/Artificial-Sweetener/Sugar-DSL",
            ),
            AboutVersionRow(
                label="QPane",
                value=qpane_version,
                status=AboutVersionStatus.AVAILABLE,
                subtitle="High-performance PySide6 image viewer",
                authors="Artificial Sweetener",
                external_url="https://github.com/Artificial-Sweetener/QPane",
            ),
            AboutVersionRow(
                label="PySide6-Fluent-Widgets",
                value="1.11.2",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="A fluent design widgets library for PySide6",
                authors="zhiyiYo",
                external_url="https://github.com/zhiyiYo/PyQt-Fluent-Widgets",
            ),
            AboutVersionRow(
                label="PySide6",
                value="6.9.0",
                status=AboutVersionStatus.AVAILABLE,
                subtitle="Qt for Python",
                authors="the Qt Company",
                external_url="https://pyside.org/",
            ),
        ),
        project_summary="Widget project summary",
        supporters=("Patron One",),
        special_thanks=("Contributor One",),
    )


def _card_position(
    page: AboutSettingsPage,
    layout: QGridLayout,
    object_key: str,
) -> tuple[int, int]:
    """Return the grid row and column for one version card."""

    card = page.findChild(QWidget, f"AboutVersionCard-{object_key}")
    assert card is not None
    index = layout.indexOf(card)
    assert index >= 0
    position = cast(tuple[int, int, int, int], layout.getItemPosition(index))
    return position[:2]


_VERSION_OBJECT_KEYS = (
    "SugarSubstitute",
    "ComfyUI",
    "SugarCubes",
    "SubstituteBackend",
    "SugarDSL",
    "QPane",
    "PySide6FluentWidgets",
    "PySide6",
)


def _version_card(page: AboutSettingsPage, object_key: str) -> QWidget:
    """Return one rendered About version card by object key."""

    card = page.findChild(QWidget, f"AboutVersionCard-{object_key}")
    assert card is not None
    return card


def _version_child(card: QWidget, object_name: str) -> QWidget:
    """Return one rendered version-card child by object name."""

    child = card.findChild(QWidget, object_name)
    assert child is not None
    return child


def _version_child_label(card: QWidget, object_name: str) -> QLabel:
    """Return one rendered version-card label by object name."""

    child = card.findChild(QLabel, object_name)
    assert child is not None
    return child


def _assert_card_children_do_not_overlap(card: QWidget) -> None:
    """Assert visible About version-card content stays bounded and separated."""

    content_widgets = _visible_version_content_widgets(card)
    for widget in content_widgets:
        assert card.rect().contains(_mapped_rect(widget, card))

    content_rects = tuple(
        _mapped_rect(widget, card).adjusted(1, 1, -1, -1) for widget in content_widgets
    )
    for index, first_rect in enumerate(content_rects):
        for second_rect in content_rects[index + 1 :]:
            assert not first_rect.intersects(second_rect)


def _visible_version_content_widgets(card: QWidget) -> tuple[QWidget, ...]:
    """Return visible text labels and passive icon slots for one version card."""

    labels: list[QWidget] = [
        label
        for label in card.findChildren(QLabel)
        if label.isVisibleTo(card)
        and label.text().strip()
        and label.objectName().startswith(
            (
                "AboutVersionTitle-",
                "AboutVersionSubtitle-",
                "AboutVersionValue-",
                "AboutVersionAuthor-",
            )
        )
    ]
    icons = [
        widget
        for widget in card.findChildren(QWidget)
        if widget.isVisibleTo(card)
        and widget.objectName().startswith("AboutVersionLinkIconSlot-")
    ]
    return tuple(labels + icons)


def _mapped_rect(widget: QWidget, ancestor: QWidget) -> QRect:
    """Return one child widget geometry mapped into an ancestor's coordinates."""

    return QRect(widget.mapTo(ancestor, QPoint(0, 0)), widget.size())


def _bind_refreshed_snapshot(page: AboutSettingsPage) -> None:
    """Bind the page's deterministic service snapshot without worker scheduling."""

    service = cast(Any, page)._service
    page.bind_snapshot(cast(AboutInfoSnapshot, service.snapshot()))


def _process_events_until(
    app: QApplication,
    condition: Callable[[], bool],
    *,
    timeout_ms: int = 1000,
) -> None:
    """Process Qt events until a condition passes or a test timeout expires."""

    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        app.processEvents()
        if condition():
            return
        QTest.qWait(10)
    app.processEvents()
    assert condition()


def _label_texts(widget: AboutSettingsPage) -> tuple[str, ...]:
    """Return visible QLabel texts below one About page."""

    return tuple(
        text for label in widget.findChildren(QLabel) if (text := label.text().strip())
    )


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication([])

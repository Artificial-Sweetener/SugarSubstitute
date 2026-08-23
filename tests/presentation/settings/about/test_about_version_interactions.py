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

"""Verify About version-card links and pointer feedback."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QEnterEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractButton, QLabel, QWidget

from substitute.presentation.settings.about_page import AboutSettingsPage
from tests.presentation.settings.about.about_settings_harness import (
    AboutInfoServiceDouble,
    AboutPageFactory,
    application,
    bind_refreshed_snapshot,
)
from tests.support.qt.semantic_wait import wait_for_qt_condition


def test_about_version_cards_expose_external_project_links(
    about_page_factory: AboutPageFactory,
) -> None:
    """Expose passive project icons and card-owned external links."""

    page = _shown_page(about_page_factory)
    expected_github_urls = {
        "SugarSubstitute": "https://github.com/Artificial-Sweetener/SugarSubstitute",
        "ComfyUI": "https://github.com/Comfy-Org/ComfyUI",
        "SubstituteBackend": (
            "https://github.com/Artificial-Sweetener/Substitute-Backend"
        ),
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


def test_about_version_card_keeps_hover_and_press_feedback(
    monkeypatch: pytest.MonkeyPatch,
    about_page_factory: AboutPageFactory,
) -> None:
    """Retain Fluent hover and pressed state while the card owns navigation."""

    opened_urls = _record_opened_urls(monkeypatch)
    page = _shown_page(about_page_factory)
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

    _send_pointer_enter(card)
    wait_for_qt_condition(lambda: card.property("aboutVersionHovered") is True)
    assert card.property("aboutVersionHovered") is True
    QTest.mousePress(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )
    wait_for_qt_condition(lambda: card.property("aboutVersionPressed") is True)
    assert card.property("aboutVersionPressed") is True
    QTest.mouseRelease(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        card.rect().center(),
    )
    wait_for_qt_condition(lambda: card.property("aboutVersionPressed") is False)
    assert card.property("aboutVersionPressed") is False
    assert opened_urls == ["https://github.com/Artificial-Sweetener/SugarSubstitute"]


def test_about_version_card_body_opens_project_link(
    monkeypatch: pytest.MonkeyPatch,
    about_page_factory: AboutPageFactory,
) -> None:
    """Open the external project when the card body is clicked."""

    opened_urls = _record_opened_urls(monkeypatch)
    page = _shown_page(about_page_factory)
    card = _version_card(page, "SugarSubstitute")
    QTest.mouseClick(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(24, card.height() // 2),
    )
    assert opened_urls == ["https://github.com/Artificial-Sweetener/SugarSubstitute"]


def test_about_version_card_icon_area_opens_project_link(
    monkeypatch: pytest.MonkeyPatch,
    about_page_factory: AboutPageFactory,
) -> None:
    """Delegate passive-icon clicks to the owning version card."""

    opened_urls = _record_opened_urls(monkeypatch)
    page = _shown_page(about_page_factory)
    icon_slot = page.findChild(QWidget, "AboutVersionLinkIconSlot-SugarSubstitute")
    assert icon_slot is not None
    QTest.mouseClick(
        icon_slot,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        icon_slot.rect().center(),
    )
    assert opened_urls == ["https://github.com/Artificial-Sweetener/SugarSubstitute"]


def _record_opened_urls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Patch desktop navigation and return its recorded URL list."""

    opened_urls: list[str] = []

    def record_opened_url(url: str) -> bool:
        """Record one URL that would have opened in the desktop shell."""

        opened_urls.append(url)
        return True

    monkeypatch.setattr(
        "substitute.presentation.settings.about_page._open_external_url",
        record_opened_url,
    )
    return opened_urls


def _shown_page(factory: AboutPageFactory) -> AboutSettingsPage:
    """Return a visible About page with its refreshed snapshot bound."""

    service = AboutInfoServiceDouble()
    page = factory(service, None)
    bind_refreshed_snapshot(page, service)
    page.resize(1000, 640)
    page.show()
    application().processEvents()
    return page


def _send_pointer_enter(widget: QWidget) -> None:
    """Deliver one positioned native enter event to the visible card."""

    local_point = widget.rect().center()
    global_point = widget.mapToGlobal(local_point)
    QApplication.sendEvent(
        widget,
        QEnterEvent(
            QPointF(local_point),
            QPointF(local_point),
            QPointF(global_point),
        ),
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

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

"""Verify responsive layout and metadata presentation of About version cards."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QSizePolicy, QWidget

from substitute.presentation.settings.about_page import AboutSettingsPage
from substitute.presentation.settings.settings_style import SETTINGS_CARD_GROUP_SPACING
from tests.presentation.settings.about.about_settings_harness import (
    AboutInfoServiceDouble,
    AboutPageFactory,
    application,
    bind_refreshed_snapshot,
)

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


def test_about_version_group_uses_two_columns_when_wide(
    about_page_factory: AboutPageFactory,
) -> None:
    """Use two card columns at normal Settings widths."""

    page = _shown_page(about_page_factory, width=1000, height=640)
    group = _version_group(page)
    assert group.sizePolicy().verticalPolicy() is QSizePolicy.Policy.Maximum
    group.resize(1000, group.height())
    application().processEvents()

    grid_container, layout = _version_grid(group)
    assert grid_container is not None
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


def test_about_version_group_uses_full_width_column_when_width_starved(
    about_page_factory: AboutPageFactory,
) -> None:
    """Give one-column cards the complete Settings card span."""

    page = _shown_page(about_page_factory, width=760, height=720)
    group = _version_group(page)
    grid_container, layout = _version_grid(group)
    assert group.property("aboutVersionColumnCount") == 1

    for object_key in _VERSION_OBJECT_KEYS:
        card = _version_card(page, object_key)
        assert _card_position(page, layout, object_key)[1] == 0
        assert card.width() == grid_container.width()
        _assert_card_children_do_not_overlap(card)
        assert card.property("aboutVersionLayoutMode") == "wide"


def test_about_version_group_elides_subtitles_under_column_pressure(
    about_page_factory: AboutPageFactory,
) -> None:
    """Elide bounded subtitles instead of clipping hidden lines."""

    page = _shown_page(about_page_factory, width=940, height=720)
    group = _version_group(page)
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


def test_about_version_cards_use_compact_layout_at_narrow_width(
    about_page_factory: AboutPageFactory,
) -> None:
    """Use an intentional stacked layout for narrow one-column cards."""

    service = AboutInfoServiceDouble(qpane_version="2.0.1.dev1.gabcdef.d20260525")
    page = about_page_factory(service, None)
    bind_refreshed_snapshot(page, service)
    page.resize(420, 760)
    page.show()
    application().processEvents()

    group = _version_group(page)
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


def test_about_version_cards_use_minimum_layout_at_minimum_width(
    about_page_factory: AboutPageFactory,
) -> None:
    """Keep minimum-width cards bounded and overlap-free."""

    page = _shown_page(about_page_factory, width=320, height=760)
    group = _version_group(page)
    grid_container, _layout = _version_grid(group)
    assert group.property("aboutVersionColumnCount") == 1
    for object_key in _VERSION_OBJECT_KEYS:
        card = _version_card(page, object_key)
        assert card.property("aboutVersionLayoutMode") == "minimum"
        assert card.height() == 116
        assert card.width() <= group.width()
        assert card.width() == grid_container.width()
        _assert_card_children_do_not_overlap(card)


def test_about_version_cards_render_metadata_as_two_lines(
    about_page_factory: AboutPageFactory,
) -> None:
    """Pair title/subtitle with version/author trailing lines."""

    page = _shown_page(about_page_factory, width=1000, height=640)
    pyside_author = page.findChild(QLabel, "AboutVersionAuthor-PySide6")
    pyside_value = page.findChild(QLabel, "AboutVersionValue-PySide6")
    assert pyside_author is not None
    assert pyside_value is not None
    assert pyside_author.toolTip() == "by the Qt Company"
    assert pyside_author.text().startswith("by the Qt")
    assert pyside_value.text() == "6.9.0"


def test_about_version_cards_align_metadata_columns(
    about_page_factory: AboutPageFactory,
) -> None:
    """Align wide-card metadata beside bounded link icons."""

    page = _shown_page(about_page_factory, width=1000, height=640)
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
        QWidget, "AboutVersionMetadata-PySide6FluentWidgets"
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
    subtitle = page.findChild(QLabel, "AboutVersionSubtitle-PySide6FluentWidgets")
    assert subtitle is not None
    assert subtitle.font().pixelSize() == 11


def _shown_page(
    factory: AboutPageFactory,
    *,
    width: int,
    height: int,
) -> AboutSettingsPage:
    """Return a visible About page with its refreshed snapshot bound."""

    service = AboutInfoServiceDouble()
    page = factory(service, None)
    bind_refreshed_snapshot(page, service)
    page.resize(width, height)
    page.show()
    application().processEvents()
    return page


def _version_group(page: AboutSettingsPage) -> QWidget:
    """Return the mounted About version-card group."""

    group = page.findChild(QWidget, "AboutVersionCardGroup")
    assert group is not None
    return group


def _version_grid(group: QWidget) -> tuple[QWidget, QGridLayout]:
    """Return the version-card grid container and layout."""

    container = group.findChild(QWidget, "AboutVersionCardGrid")
    assert container is not None
    layout = container.layout()
    assert isinstance(layout, QGridLayout)
    return container, layout


def _card_position(
    page: AboutSettingsPage,
    layout: QGridLayout,
    object_key: str,
) -> tuple[int, int]:
    """Return the grid row and column for one version card."""

    card = _version_card(page, object_key)
    index = layout.indexOf(card)
    assert index >= 0
    position = cast(tuple[int, int, int, int], layout.getItemPosition(index))
    return position[:2]


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
    """Assert visible version-card content stays bounded and separated."""

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
    """Return one child geometry mapped into an ancestor's coordinates."""

    return QRect(widget.mapTo(ancestor, QPoint(0, 0)), widget.size())

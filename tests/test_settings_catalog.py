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

"""Contract tests for Settings catalog and search metadata."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from substitute.presentation.settings.settings_catalog import (
    SettingsControlEntry,
    SettingsPageEntry,
    SettingsSectionEntry,
    ordered_settings_pages,
)
from substitute.presentation.settings.settings_card import InteractiveSettingsCard
from substitute.presentation.settings.settings_search import search_settings_catalog
from substitute.presentation.settings.settings_search_page import SettingsSearchPage
from substitute.presentation.settings.settings_page_renderer import CatalogSettingsPage


def test_settings_catalog_orders_pages_sections_and_controls() -> None:
    """Settings catalog ordering should be deterministic at every level."""

    pages = (_page("second", 20), _page("first", 10))

    ordered = ordered_settings_pages(pages)

    assert tuple(page.page_id for page in ordered) == ("first", "second")
    assert tuple(section.section_id for section in ordered[0].visible_sections()) == (
        "first.section",
    )
    assert tuple(
        control.setting_id
        for section in ordered[0].visible_sections()
        for control in section.visible_controls()
    ) == ("first.control",)


def test_settings_search_matches_aliases_and_preserves_catalog_order() -> None:
    """Settings search should match aliases and return catalog-order results."""

    pages = (
        _page("generation", 10, title="Generation", keywords=("thumbnail",)),
        _page("model_sources", 20, title="Model Sources", keywords=("thumbnail",)),
    )

    results = search_settings_catalog(pages, "picture")

    assert tuple(result.page.page_id for result in results) == (
        "generation",
        "model_sources",
    )


def test_settings_control_factories_create_fresh_widgets() -> None:
    """Catalog controls should create a new widget for each requested parent."""

    _app()
    parent_a = QWidget()
    parent_b = QWidget()
    control = _control("fresh.control", keywords=("fresh",))

    first = control.factory(parent_a)
    second = control.factory(parent_b)

    assert first is not second
    assert first.parentWidget() is parent_a
    assert second.parentWidget() is parent_b


def test_settings_search_page_renders_metadata_without_control_factories() -> None:
    """Search results should not instantiate real Settings controls while typing."""

    _app()

    def fail_factory(parent: QWidget) -> QWidget:
        """Fail if search rendering asks for a live control widget."""

        raise AssertionError("search page rendered a concrete control")

    page = SettingsPageEntry(
        page_id="model_sources",
        title="Model Sources",
        subtitle="",
        icon=None,
        order=10,
        sections=(
            SettingsSectionEntry(
                "model_sources.account",
                "CivitAI account",
                "",
                10,
                (
                    SettingsControlEntry(
                        setting_id="model_sources.civitai.api_key",
                        title="API key",
                        description="Use CivitAI credentials for requests.",
                        keywords=("credential",),
                        order=10,
                        factory=fail_factory,
                    ),
                ),
            ),
        ),
    )
    results = search_settings_catalog((page,), "credential")
    activated: list[str] = []

    widget = SettingsSearchPage(
        results,
        on_result_activated=lambda result: activated.append(result.setting_id),
    )

    labels = _label_texts(widget)
    cards = widget.findChildren(InteractiveSettingsCard)
    assert "Model Sources > CivitAI account" in labels
    assert "API key" in labels
    assert "Use CivitAI credentials for requests." in labels
    assert len(cards) == 1

    cards[0].activated.emit()

    assert activated == ["model_sources.civitai.api_key"]


def test_catalog_settings_page_refresh_reuses_visible_control_widgets() -> None:
    """Catalog refresh should keep unchanged setting widgets alive."""

    _app()
    factory_calls: list[str] = []

    def make_control(setting_id: str) -> SettingsControlEntry:
        """Return one control entry that records widget construction."""

        return SettingsControlEntry(
            setting_id=setting_id,
            title="Control",
            description="Control description",
            keywords=("refresh",),
            order=10,
            factory=lambda parent: _recorded_label(
                setting_id,
                factory_calls,
                parent,
            ),
        )

    page = SettingsPageEntry(
        page_id="generation",
        title="Generation",
        subtitle="",
        icon=None,
        order=10,
        sections=(
            SettingsSectionEntry(
                "generation.preview",
                "Preview",
                "",
                10,
                (make_control("generation.preview.enabled"),),
            ),
        ),
    )
    widget = CatalogSettingsPage(page)
    first_label = widget.findChild(QLabel, "generation.preview.enabled")

    widget.refresh()

    assert factory_calls == ["generation.preview.enabled"]
    assert widget.findChild(QLabel, "generation.preview.enabled") is first_label


def test_catalog_settings_page_refresh_reconciles_visibility_by_setting_id() -> None:
    """Catalog refresh should only construct controls that become visible."""

    _app()
    show_second = False
    factory_calls: list[str] = []

    def second_visible() -> bool:
        """Return whether the second test control is visible."""

        return show_second

    page = SettingsPageEntry(
        page_id="generation",
        title="Generation",
        subtitle="",
        icon=None,
        order=10,
        sections=(
            SettingsSectionEntry(
                "generation.preview",
                "Preview",
                "",
                10,
                (
                    SettingsControlEntry(
                        "generation.preview.enabled",
                        "Generation previews",
                        "",
                        (),
                        10,
                        lambda parent: _recorded_label(
                            "generation.preview.enabled",
                            factory_calls,
                            parent,
                        ),
                    ),
                    SettingsControlEntry(
                        "generation.preview.type",
                        "Preview type",
                        "",
                        (),
                        20,
                        lambda parent: _recorded_label(
                            "generation.preview.type",
                            factory_calls,
                            parent,
                        ),
                        is_visible=second_visible,
                    ),
                ),
            ),
        ),
    )
    widget = CatalogSettingsPage(page)

    show_second = True
    widget.refresh()

    assert factory_calls == [
        "generation.preview.enabled",
        "generation.preview.type",
    ]
    assert widget.findChild(QLabel, "generation.preview.enabled") is not None
    assert widget.findChild(QLabel, "generation.preview.type") is not None


def _page(
    page_id: str,
    order: int,
    *,
    title: str | None = None,
    keywords: tuple[str, ...] = (),
) -> SettingsPageEntry:
    """Return a compact page entry for catalog tests."""

    return SettingsPageEntry(
        page_id=page_id,
        title=title or page_id.title(),
        subtitle="",
        icon=None,
        order=order,
        sections=(
            SettingsSectionEntry(
                f"{page_id}.section",
                "Section",
                "",
                10,
                (_control(f"{page_id}.control", keywords=keywords),),
            ),
        ),
    )


def _control(
    setting_id: str,
    *,
    keywords: tuple[str, ...],
) -> SettingsControlEntry:
    """Return a compact control entry for catalog tests."""

    return SettingsControlEntry(
        setting_id=setting_id,
        title="Control",
        description="Control description",
        keywords=keywords + ("picture",),
        order=10,
        factory=lambda parent: QLabel(setting_id, parent),
    )


def _recorded_label(
    setting_id: str,
    factory_calls: list[str],
    parent: QWidget,
) -> QLabel:
    """Create a label while recording one catalog factory call."""

    factory_calls.append(setting_id)
    label = QLabel(setting_id, parent)
    label.setObjectName(setting_id)
    return label


def _app() -> QApplication:
    """Return the existing QApplication or create one for widget tests."""

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _label_texts(widget: QWidget) -> tuple[str, ...]:
    """Return visible label text descendants for Settings widget assertions."""

    return tuple(child.text() for child in widget.findChildren(QLabel) if child.text())

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

"""Verify integrated Settings search ownership and results."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from qfluentwidgets import (  # type: ignore[import-untyped]
    SearchLineEdit,
    TitleLabel,
)
from substitute.presentation.settings.comfy_environment_page import ComfyEnvironmentPage
from substitute.presentation.settings.cube_library_page import CubeLibrarySettingsPage
from substitute.presentation.settings.settings_workspace import (
    ABOUT_SECTION_ID,
    SettingsWorkspaceWidgets,
)
from substitute.presentation.shell.settings_toolbar_search import (
    SettingsToolbarSearchBox,
)
from substitute.presentation.settings.settings_card import (
    InteractiveSettingsCard,
)
from PySide6.QtTest import QSignalSpy
from tests.presentation.settings.generation.support import (
    application,
)
from tests.presentation.settings.workspace.support import (
    build_settings_workspace,
    close_and_delete_widget,
    close_settings_workspace,
    label_texts as workspace_label_texts,
)


@pytest.fixture()
def settings_workspace_factory() -> Iterator[
    Callable[[Path], SettingsWorkspaceWidgets]
]:
    """Build and deterministically release each real Settings workspace."""

    workspaces: list[SettingsWorkspaceWidgets] = []

    def build(tmp_path: Path) -> SettingsWorkspaceWidgets:
        """Build one workspace whose independent widgets require cleanup."""

        workspace = build_settings_workspace(tmp_path)
        workspaces.append(workspace)
        return workspace

    yield build

    for workspace in reversed(workspaces):
        close_settings_workspace(workspace)


def test_settings_page_shell_does_not_own_search_bar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """Settings detail shells should leave search ownership to shell chrome."""

    application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = settings_workspace_factory(tmp_path)
    shell = widgets.panel.page_shell(ABOUT_SECTION_ID)

    assert shell is not None
    assert not widgets.navigation_pane.findChildren(SearchLineEdit)
    assert not hasattr(shell, "search_edit")
    assert not hasattr(shell, "title_label")
    assert isinstance(shell.breadcrumb_label, TitleLabel)
    assert shell.breadcrumb_label.text() == "Settings > About"
    assert shell._content_layout.indexOf(shell.breadcrumb_label) == 0


def test_settings_toolbar_search_box_emits_debounced_queries() -> None:
    """Toolbar Settings search should preserve debounced query emission."""

    app = application()
    search_box = SettingsToolbarSearchBox()
    emitted: list[str] = []
    emitted_spy = QSignalSpy(search_box.searchQueryChanged)
    search_box.searchQueryChanged.connect(emitted.append)

    try:
        search_box.setText("credential")
        app.processEvents()

        assert emitted == []

        assert emitted_spy.wait(2_000), "debounced query was not emitted"

        assert emitted == ["credential"]

        search_box.set_search_text("panel-owned")
        app.processEvents()

        assert search_box._search_debounce_timer.isActive() is False
        assert emitted_spy.count() == 1
        assert emitted == ["credential"]
    finally:
        close_and_delete_widget(search_box)


def test_settings_workspace_search_replaces_page_and_clearing_restores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """Settings search should show a synthetic page without changing active page id."""

    app = application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = settings_workspace_factory(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("credential")
    app.processEvents()

    assert widgets.panel.is_search_active() is True
    assert widgets.panel.active_page_id() == ABOUT_SECTION_ID
    assert "Settings > Search settings" in workspace_label_texts(widgets.panel)
    assert "Model Sources > CivitAI account" in workspace_label_texts(widgets.panel)
    assert "API key" in workspace_label_texts(widgets.panel)

    assert widgets.panel.search_query() == "credential"

    widgets.panel.set_search_query("")
    app.processEvents()

    assert widgets.panel.is_search_active() is False
    assert widgets.panel.active_page_id() == ABOUT_SECTION_ID


def test_settings_search_excludes_about_page_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """About copy and acknowledgements should not be indexed as settings."""

    app = application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = settings_workspace_factory(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("About-only patron")
    app.processEvents()

    search_shell = widgets.panel._search_shell
    assert search_shell is not None
    labels = workspace_label_texts(search_shell)
    assert widgets.panel.is_search_active() is True
    assert "No settings found" in labels
    assert "About-only patron" not in labels
    assert "About-only special thanks" not in labels


def test_settings_workspace_search_orders_results_by_navigation_sections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """Settings search results should follow page and section ordering."""

    app = application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = settings_workspace_factory(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("thumbnail")
    app.processEvents()

    labels = workspace_label_texts(widgets.panel)
    generation_index = labels.index("Generation > Preview")
    model_sources_index = labels.index("Model Sources > Thumbnails and safety")
    assert generation_index < model_sources_index


def test_settings_workspace_keeps_danbooru_under_prompt_editing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """Danbooru controls should be grouped as prompt reference support."""

    app = application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = settings_workspace_factory(tmp_path)
    widgets.panel.select_page("prompt_editing", animated=False)
    prompt_shell = widgets.panel.page_shell("prompt_editing")
    widgets.panel.select_page("model_sources", animated=False)
    model_sources_shell = widgets.panel.page_shell("model_sources")
    assert prompt_shell is not None
    assert model_sources_shell is not None

    prompt_labels = workspace_label_texts(prompt_shell.content_widget())
    model_source_labels = workspace_label_texts(model_sources_shell.content_widget())

    assert "Danbooru reference" in prompt_labels
    assert "Show images in wiki viewer" in prompt_labels
    assert "Danbooru cache maintenance" in prompt_labels
    assert "Danbooru reference" not in model_source_labels
    assert "Show images in wiki viewer" not in model_source_labels
    assert "Danbooru cache maintenance" not in model_source_labels

    widgets.panel.show()
    app.processEvents()
    widgets.panel.set_search_query("danbooru")
    app.processEvents()

    labels = workspace_label_texts(widgets.panel)
    assert "Prompt Editing > Danbooru prompt integration" in labels
    assert "Prompt Editing > Danbooru reference" in labels
    assert not any(label.startswith("Model Sources >") for label in labels)


def test_settings_workspace_search_no_results_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """Settings search should render an explicit no-results row."""

    app = application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = settings_workspace_factory(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("definitelynotasetting")
    app.processEvents()

    assert "No settings found" in workspace_label_texts(widgets.panel)


def test_settings_workspace_search_does_not_refresh_dynamic_pages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """Settings search should not trigger dynamic page refresh work while typing."""

    app = application()
    refresh_calls: list[str] = []
    monkeypatch.setattr(
        ComfyEnvironmentPage,
        "refresh",
        lambda _page: refresh_calls.append("environment"),
    )
    monkeypatch.setattr(
        CubeLibrarySettingsPage,
        "refresh",
        lambda _page: refresh_calls.append("library"),
    )
    widgets = settings_workspace_factory(tmp_path)
    widgets.panel.show()
    app.processEvents()
    refresh_calls.clear()

    widgets.panel.set_search_query("server")
    app.processEvents()

    assert widgets.panel.is_search_active() is True
    assert refresh_calls == []


def test_settings_workspace_search_result_activation_selects_owner_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    settings_workspace_factory: Callable[[Path], SettingsWorkspaceWidgets],
) -> None:
    """Opening a Settings search result should navigate instead of embedding controls."""

    app = application()
    monkeypatch.setattr(ComfyEnvironmentPage, "refresh", lambda _page: None)
    monkeypatch.setattr(CubeLibrarySettingsPage, "refresh", lambda _page: None)
    widgets = settings_workspace_factory(tmp_path)
    widgets.panel.show()
    app.processEvents()

    widgets.panel.set_search_query("account credential")
    app.processEvents()

    cards = widgets.panel.findChildren(
        InteractiveSettingsCard, "SettingsSearchResultCard"
    )
    assert cards

    cards[0].activated.emit()
    app.processEvents()

    assert widgets.panel.search_query() == ""
    assert widgets.panel.is_search_active() is False
    assert widgets.panel.active_page_id() == "model_sources"
    assert widgets.panel.page_shell("model_sources") is not None

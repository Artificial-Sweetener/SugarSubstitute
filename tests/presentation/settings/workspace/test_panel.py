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

"""Verify integrated Settings panel lifecycle and layout."""

from __future__ import annotations
from pathlib import Path
from typing import Callable
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget
from substitute.application.generation import (
    GenerationPreviewPreferenceService,
    OutputPreferenceService,
)
from substitute.presentation.motion import (
    SETTINGS_PAGE_TRANSITION_DURATION_MS,
)
from substitute.presentation.settings.generation_page import GenerationSettingsPage
from substitute.presentation.settings.settings_card import (
    SettingsCard,
)
from substitute.presentation.settings.settings_workspace_panel import (
    SETTINGS_CONTENT_MAX_WIDTH,
    SettingsPageDescriptor,
    SettingsWorkspacePanel,
)
from tests.presentation.settings.generation.support import (
    MemoryOutputPreferenceRepository,
    MemoryPreviewPreferenceRepository,
    application,
    immediate_task_runner,
)
from tests.presentation.settings.workspace.support import (
    RefreshableWidget,
    tall_widget,
)
from tests.support.qt.lifecycle import destroy_qt_object


def test_settings_workspace_panel_switches_active_pages() -> None:
    """Settings panel should show one active page instead of a continuous document."""

    app = application()
    panel = SettingsWorkspacePanel()
    emitted: list[str] = []
    panel.currentPageChanged.connect(emitted.append)
    panel.resize(520, 220)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance",
                "Appearance",
                "Theme",
                None,
                tall_widget("A"),
            ),
            SettingsPageDescriptor(
                "prompt_editing",
                "Prompt Editing",
                "Features",
                None,
                tall_widget("B"),
            ),
        )
    )
    panel.show()
    app.processEvents()
    panel.select_page("prompt_editing", animated=False)
    app.processEvents()

    assert panel.page_ids() == ("appearance", "prompt_editing")
    assert panel.active_page_id() == "prompt_editing"
    assert emitted[-1] == "prompt_editing"
    appearance_shell = panel.page_shell("appearance")
    assert appearance_shell is not None
    assert appearance_shell.isEnabled() is False


def test_settings_workspace_panel_clamps_content_column_width() -> None:
    """Settings content should not stretch across the full route width."""

    app = application()
    panel = SettingsWorkspacePanel()
    panel.resize(1500, 260)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance",
                "Appearance",
                "Theme",
                None,
                tall_widget("A"),
            ),
        )
    )
    panel.show()
    app.processEvents()
    shell = panel.page_shell("appearance")

    assert shell is not None
    assert shell._content_column.maximumWidth() == SETTINGS_CONTENT_MAX_WIDTH
    assert shell.content_column_width() == SETTINGS_CONTENT_MAX_WIDTH
    assert shell.content_column_x() > 0


def test_settings_workspace_resize_updates_active_page_width() -> None:
    """Visible Settings resizes should propagate to active page row modes."""

    app = application()
    page = QWidget()
    page_layout = QVBoxLayout(page)
    card = SettingsCard(
        title="Resize",
        description="Tracks shell width",
        trailing_widget=QWidget(),
    )
    page_layout.addWidget(card)
    panel = SettingsWorkspacePanel()
    panel.resize(1500, 300)
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance",
                "Appearance",
                "Theme",
                None,
                page,
            ),
        )
    )
    panel.show()
    app.processEvents()
    shell = panel.page_shell("appearance")

    assert shell is not None
    assert shell.content_column_width() == SETTINGS_CONTENT_MAX_WIDTH
    assert card.layout_mode() == "wide"

    panel.resize(260, 300)
    app.processEvents()

    assert shell.content_column_width() < SETTINGS_CONTENT_MAX_WIDTH
    assert card.layout_mode() == "wrapped_no_icon"
    assert card.width() <= shell.content_column_width()
    panel.close()


def test_settings_workspace_resyncs_width_after_hidden_route_resize(
    tmp_path: Path,
) -> None:
    """Settings should not reuse a stale wide column after hidden route resizing."""

    app = application()
    route_stack = QStackedWidget()
    workflow_page = QWidget()
    panel = SettingsWorkspacePanel()
    generation_page = GenerationSettingsPage(
        preference_service=GenerationPreviewPreferenceService(
            MemoryPreviewPreferenceRepository()
        ),
        output_preference_service=OutputPreferenceService(
            MemoryOutputPreferenceRepository(),
            default_output_root=tmp_path / "outputs",
        ),
        task_runner_factory=immediate_task_runner,
    )
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "generation",
                "Generation",
                "Preview",
                None,
                generation_page,
            ),
        )
    )
    route_stack.addWidget(workflow_page)
    route_stack.addWidget(panel)
    route_stack.resize(1300, 720)
    route_stack.setCurrentWidget(panel)
    route_stack.show()
    app.processEvents()
    shell = panel.page_shell("generation")

    assert shell is not None
    assert shell.content_column_width() == SETTINGS_CONTENT_MAX_WIDTH

    route_stack.setCurrentWidget(workflow_page)
    route_stack.resize(760, 720)
    app.processEvents()
    route_stack.setCurrentWidget(panel)
    panel.select_page("generation", animated=False)
    app.processEvents()

    viewport_width = shell._scroll_surface.viewport().width()
    assert shell.content_column_width() <= viewport_width
    assert shell.content_column_width() < SETTINGS_CONTENT_MAX_WIDTH
    for card in generation_page.findChildren(SettingsCard):
        assert card.width() <= shell.content_column_width()
        if card.trailing_widget is not None:
            assert card.trailing_widget.width() <= card.width()

    route_stack.close()
    destroy_qt_object(route_stack)


def test_settings_workspace_panel_configures_page_transition() -> None:
    """Settings page selection should configure the shared page transition tokens."""

    application()
    panel = SettingsWorkspacePanel()
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance", "Appearance", "Theme", None, QWidget()
            ),
            SettingsPageDescriptor(
                "generation", "Generation", "Preview", None, QWidget()
            ),
        )
    )

    panel.select_page("generation", animated=True)

    assert (
        panel._transition_animation.duration() == SETTINGS_PAGE_TRANSITION_DURATION_MS
    )
    assert panel._transition_animation.endValue() == 0


def test_settings_workspace_panel_respects_reduced_motion_override() -> None:
    """Settings page transition duration should collapse under reduced motion."""

    app = application()
    app.setProperty("substitute.reduce_motion", True)
    try:
        panel = SettingsWorkspacePanel()
        panel.set_pages(
            (
                SettingsPageDescriptor(
                    "appearance", "Appearance", "Theme", None, QWidget()
                ),
                SettingsPageDescriptor(
                    "generation", "Generation", "Preview", None, QWidget()
                ),
            )
        )

        panel.select_page("generation", animated=True)

        assert panel._transition_animation.duration() == 0
    finally:
        app.setProperty("substitute.reduce_motion", None)


def test_settings_workspace_panel_refreshes_only_active_page() -> None:
    """Integrated Settings projection should refresh only the active page."""

    application()
    panel = SettingsWorkspacePanel()
    appearance_page = RefreshableWidget()
    environment_page = RefreshableWidget()
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance", "Appearance", "Theme", None, appearance_page
            ),
            SettingsPageDescriptor(
                "comfy_environment",
                "Comfy Environment",
                "Packages",
                None,
                environment_page,
            ),
        )
    )
    panel.set_route_active(True)

    panel.refresh()

    assert appearance_page.refresh_count == 1
    assert environment_page.refresh_count == 0

    panel.select_page("comfy_environment", animated=False)

    assert appearance_page.refresh_count == 1
    assert environment_page.refresh_count == 1


def test_settings_workspace_panel_refreshes_visible_selected_page_without_route_flag() -> (
    None
):
    """Visible Settings selection should refresh even without explicit route state."""

    app = application()
    panel = SettingsWorkspacePanel()
    appearance_page = RefreshableWidget()
    environment_page = RefreshableWidget()
    panel.set_pages(
        (
            SettingsPageDescriptor(
                "appearance", "Appearance", "Theme", None, appearance_page
            ),
            SettingsPageDescriptor(
                "comfy_environment",
                "Comfy Environment",
                "Packages",
                None,
                environment_page,
            ),
        )
    )
    panel.show()
    app.processEvents()

    panel.select_page("comfy_environment", animated=False)

    assert appearance_page.refresh_count == 0
    assert environment_page.refresh_count == 1

    panel.close()
    destroy_qt_object(panel)


def test_settings_workspace_panel_constructs_pages_lazily() -> None:
    """Settings pages should be constructed only when first selected."""

    application()
    constructed: list[str] = []
    panel = SettingsWorkspacePanel()

    def page_factory(page_id: str) -> Callable[[QWidget], QWidget]:
        """Return a factory that records construction for one page."""

        def create(parent: QWidget) -> QWidget:
            """Create one recorded page widget."""

            constructed.append(page_id)
            return QWidget(parent)

        return create

    panel.set_pages(
        (
            SettingsPageDescriptor(
                "about",
                "About",
                "Version",
                None,
                create_widget=page_factory("about"),
            ),
            SettingsPageDescriptor(
                "generation",
                "Generation",
                "Preview",
                None,
                create_widget=page_factory("generation"),
            ),
        )
    )

    assert constructed == ["about"]
    assert panel.constructed_page_ids() == ("about",)
    assert panel.page_shell("generation") is None

    panel.select_page("generation", animated=False)

    assert constructed == ["about", "generation"]
    assert panel.constructed_page_ids() == ("about", "generation")
    assert panel.page_shell("generation") is not None

    panel.select_page("about", animated=False)
    panel.select_page("generation", animated=False)

    assert constructed == ["about", "generation"]

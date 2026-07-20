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

"""Verify Settings route/runtime behavior lives outside MainWindow."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from substitute.presentation.errors import ErrorReportPresenterProtocol
from substitute.presentation.shell import settings_route_controller
from substitute.presentation.shell.shell_chrome_controller import ShellChromeController


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW_SOURCE = (
    PROJECT_ROOT / "substitute" / "presentation" / "shell" / "main_window.py"
)


class _Layout:
    """Record Settings workspace layout mutations."""

    def __init__(self) -> None:
        """Create empty layout records."""

        self.widgets: list[object] = []
        self.stretches: list[tuple[int, int]] = []

    def addWidget(self, widget: object) -> None:
        """Record a widget insertion."""

        self.widgets.append(widget)

    def setStretch(self, index: int, stretch: int) -> None:
        """Record a stretch assignment."""

        self.stretches.append((index, stretch))


class _Signal:
    """Capture connected callbacks."""

    def __init__(self) -> None:
        """Create empty callback records."""

        self.callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        """Record one callback."""

        self.callbacks.append(callback)


def _shell() -> SimpleNamespace:
    """Create a shell surface for Settings controller tests."""

    return SimpleNamespace(
        comfy_environment_service=object(),
        cube_library_management_service=object(),
        invalidate_cube_catalog_cache=lambda: None,
        about_info_service=object(),
        localization_manager=object(),
        appearance_runtime=object(),
        appearance_restart_coordinator=object(),
        comfy_connection_settings_service=object(),
        prompt_editor_preference_service=object(),
        danbooru_preference_service=object(),
        danbooru_cache_repository=object(),
        civitai_preference_service=object(),
        civitai_credential_service=object(),
        civitai_cache_service=object(),
        generation_preview_preference_service=object(),
        output_preference_service=object(),
        settings_task_runner_factory=object(),
        prompt_wildcard_preference_service=object(),
        prompt_wildcard_file_management_service=object(),
        open_wildcard_management_modal=object(),
        open_autocomplete_list_management_modal=object(),
        request_reconfigure=lambda: None,
        shell_frame_integration_controller=SimpleNamespace(
            show_pending_restart_requirements=lambda: None,
        ),
        settings_workspace_layout=_Layout(),
        settingsToolbarSearchBox=SimpleNamespace(
            searchQueryChanged=_Signal(),
            set_search_text=lambda _query: None,
        ),
    )


def test_create_settings_workspace_wires_callbacks_and_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings widget construction should pass controller-owned callbacks."""

    calls: list[dict[str, object]] = []
    navigation_pane = object()
    panel = SimpleNamespace(
        searchQueryChanged=_Signal(),
        set_search_query=lambda _query: None,
        search_query=lambda: "models",
    )

    def _create_settings_workspace(**kwargs: object) -> object:
        calls.append(kwargs)
        return SimpleNamespace(navigation_pane=navigation_pane, panel=panel)

    monkeypatch.setattr(
        settings_route_controller,
        "create_settings_workspace",
        _create_settings_workspace,
    )
    shell = _shell()
    error_presenter = cast(ErrorReportPresenterProtocol, object())
    controller = settings_route_controller.SettingsRouteController(
        shell,
        error_presenter=error_presenter,
    )

    controller.create_settings_workspace()

    assert shell.settings_navigation_pane is navigation_pane
    assert shell.settings_workspace_panel is panel
    assert shell.settings_workspace_layout.widgets == [navigation_pane, panel]
    assert shell.settings_workspace_layout.stretches == [(0, 0), (1, 1)]
    assert calls[0]["cube_library_restart_required_changed"] == (
        controller.handle_cube_library_restart_required_changed
    )
    assert calls[0]["cube_library_post_restart_refresh"] == (
        controller.refresh_runtime_contracts_after_cube_dependency_restart
    )
    assert calls[0]["appearance_restart_coordinator"] is (
        shell.appearance_restart_coordinator
    )
    assert calls[0]["localization_manager"] is shell.localization_manager
    assert (
        calls[0]["prompt_editor_preferences_changed"]
        == controller.handle_prompt_editor_preferences_changed
    )
    assert (
        calls[0]["show_restart_requirements"]
        == controller.show_pending_restart_requirements
    )
    assert calls[0]["error_presenter"] is error_presenter
    assert calls[0]["task_runner_factory"] is shell.settings_task_runner_factory


def test_prompt_editor_preferences_changed_refreshes_active_surface() -> None:
    """Prompt preference changes should refresh the active workflow surface."""

    calls: list[str] = []
    shell = SimpleNamespace(
        active_workflow_surface_refresher=SimpleNamespace(
            refresh_active_workflow_surface=lambda: calls.append("refresh")
        )
    )

    settings_route_controller.SettingsRouteController(
        shell,
        error_presenter=None,
    ).handle_prompt_editor_preferences_changed()

    assert calls == ["refresh"]


def test_shell_appearance_reload_prefers_full_gui_reload_command() -> None:
    """Appearance changes should use the sanctioned full-GUI reload when wired."""

    calls: list[str] = []
    shell = SimpleNamespace(
        request_full_gui_reload=lambda: calls.append("full"),
        window=lambda: SimpleNamespace(
            reload_shell_backdrop_from_preferences=lambda: calls.append("frame")
        ),
        workflow_session_service=SimpleNamespace(
            active_workflow_id="wf-a",
            workflows={"wf-a": object()},
        ),
        _active_workspace_route="wf-a",
    )

    settings_route_controller.SettingsRouteController(
        shell,
        error_presenter=None,
    ).request_shell_appearance_reload()

    assert calls == ["full"]


def test_runtime_contract_refresh_invalidates_cube_and_node_caches() -> None:
    """Cube Library restart refresh should invalidate runtime discovery caches."""

    calls: list[str] = []
    shell = SimpleNamespace(
        invalidate_cube_catalog_cache=lambda: calls.append("cube-cache"),
        node_definition_gateway=SimpleNamespace(
            clear_cache=lambda: calls.append("node-cache")
        ),
    )

    settings_route_controller.SettingsRouteController(
        shell,
        error_presenter=None,
    ).refresh_runtime_contracts_after_cube_dependency_restart()

    assert calls == ["cube-cache", "node-cache"]


def test_cube_library_restart_required_blocks_and_restores_generation() -> None:
    """Restart-required state should block generation until dependencies are ready."""

    calls: list[tuple[object, ...]] = []
    backend_states: list[str] = []
    shell = SimpleNamespace(
        _backend_state="ready",
        workspace_generation_controller=SimpleNamespace(
            set_backend_available=lambda available, *, message: calls.append(
                ("backend", available, message)
            )
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: calls.append(
                ("availability",)
            ),
            set_backend_state=lambda state: backend_states.append(state),
        ),
    )
    controller = settings_route_controller.SettingsRouteController(
        shell,
        error_presenter=None,
    )

    controller.handle_cube_library_restart_required_changed(True)
    controller.handle_cube_library_restart_required_changed(False)

    assert shell._backend_state == "unavailable"
    assert calls == [
        (
            "backend",
            False,
            "ComfyUI must restart before repaired cube dependencies can be used.",
        ),
        ("availability",),
    ]
    assert backend_states == ["ready"]


def test_route_helpers_switch_workspace_pages_without_geometry_changes() -> None:
    """Settings and workflow routes should switch pages without resizing workflow UI."""

    route_calls: list[object] = []
    material_regions: list[object | None] = []
    cube_stack_container = object()
    workflow_page = object()
    settings_page = object()
    settings_route_active: list[bool] = []
    shell = SimpleNamespace(
        cube_stack_container=cube_stack_container,
        cubeStackModeButton=SimpleNamespace(setEnabled=lambda _enabled: None),
        orbActionCluster=SimpleNamespace(setVisible=lambda _visible: None),
        settingsToolbarSearchBox=SimpleNamespace(setVisible=lambda _visible: None),
        appOrbMenuButton=SimpleNamespace(
            set_workflow_file_actions_enabled=lambda _enabled: None
        ),
        workspace_body_material_surface=SimpleNamespace(
            set_cube_stack_region_widget=lambda widget: material_regions.append(widget)
        ),
        workspace_route_container=SimpleNamespace(
            setCurrentWidget=lambda widget: route_calls.append(widget)
        ),
        workflow_workspace_page=workflow_page,
        settings_workspace_page=settings_page,
        settings_workspace_panel=SimpleNamespace(
            set_route_active=settings_route_active.append
        ),
    )
    shell.shell_chrome_controller = ShellChromeController(shell)
    shell.cube_stack_presentation_controller = SimpleNamespace(
        set_workflow_route_active=lambda active: material_regions.append(
            cube_stack_container if active else None
        )
    )

    controller = settings_route_controller.SettingsRouteController(
        shell,
        error_presenter=None,
    )
    controller.show_settings_workspace()
    controller.show_workflow_workspace()

    assert route_calls == [settings_page, workflow_page]
    assert material_regions == [None, cube_stack_container]
    assert settings_route_active == [True, False]


def test_settings_shortcuts_select_target_pages() -> None:
    """Settings shortcut routes should project Settings before selecting pages."""

    selected_pages: list[tuple[str, bool]] = []

    class _Controller(settings_route_controller.SettingsRouteController):
        """Record Settings projection before shortcut selection."""

        def project_settings_workspace(self) -> None:
            """Record one Settings workspace projection."""

            selected_pages.append(("project", False))

    controller = _Controller(
        SimpleNamespace(
            settings_workspace_panel=SimpleNamespace(
                select_page=lambda page_id, *, animated: selected_pages.append(
                    (page_id, animated)
                )
            )
        ),
        error_presenter=None,
    )

    controller.project_generation_model_download_settings()
    controller.project_model_sources_settings()

    assert selected_pages == [
        ("project", False),
        ("generation", False),
        ("project", False),
        ("model_sources", False),
    ]


def test_main_window_delegates_settings_route_private_owners() -> None:
    """Verify MainWindow no longer owns private Settings route internals."""

    source = MAIN_WINDOW_SOURCE.read_text(encoding="utf-8")
    composition_source = (
        MAIN_WINDOW_SOURCE.parent / "main_window_composition.py"
    ).read_text(encoding="utf-8")

    assert "SettingsRouteController(" in composition_source
    assert "def _create_settings_workspace" not in source
    assert "def _connect_settings_toolbar_search" not in source
    assert "def _refresh_runtime_contracts_after_cube_dependency_restart" not in source
    assert "def _handle_cube_library_restart_required_changed" not in source
    assert "def _request_shell_appearance_reload" not in source
    assert "shell._error_presenter" not in (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "shell"
        / "settings_route_controller.py"
    ).read_text(encoding="utf-8")

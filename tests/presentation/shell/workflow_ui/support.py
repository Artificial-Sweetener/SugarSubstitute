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

"""Provide typed workflow UI composition doubles."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from substitute.domain.workflow import WorkflowState


class FakeEditorPanel:
    """Record editor-panel construction and configuration."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.model_choice_snapshot_controller = object()
        self.minimum_widths: list[int] = []
        self.mainwindow: object | None = None

    def setMinimumWidth(self, width: int) -> None:
        """Record the configured minimum width."""
        self.minimum_widths.append(width)


class Signal:
    """Record connected slots."""

    def __init__(self) -> None:
        self.connections: list[object] = []

    def connect(self, slot: object) -> None:
        """Record one connected slot."""
        self.connections.append(slot)


class FakeCubeStack:
    """Record cube-stack construction and configuration."""

    def __init__(self, parent: object) -> None:
        self.parent = parent
        self.cubeMoved = Signal()
        self.currentCubeChanged = Signal()
        self.movable_calls: list[bool] = []
        self.maximum_width_calls: list[int] = []
        self.close_button_modes: list[object] = []
        self.deleted = False

    def setMovable(self, movable: bool) -> None:
        """Record movable configuration."""
        self.movable_calls.append(movable)

    def setTabMaximumWidth(self, width: int) -> None:
        """Record tab maximum width configuration."""
        self.maximum_width_calls.append(width)

    def setCloseButtonDisplayMode(self, mode: object) -> None:
        """Record close-button visibility mode."""
        self.close_button_modes.append(mode)

    def deleteLater(self) -> None:
        """Record deferred widget disposal."""
        self.deleted = True


class FakeOverrideManager:
    """Record override-manager construction and injected UI handles."""

    def __init__(self, shell: object, **kwargs: object) -> None:
        self.shell = shell
        self.kwargs = kwargs
        self.override_dropdown_btn: object | None = None
        self._global_override_menu: object | None = None


class Container:
    """Record stacked-widget membership and current selection."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.current: object | None = None

    def addWidget(self, widget: object) -> None:
        """Record one widget addition."""
        self.added.append(widget)

    def setCurrentWidget(self, widget: object) -> None:
        """Record current widget selection."""
        self.current = widget

    def removeWidget(self, widget: object) -> None:
        """Record removal from this stacked container."""
        self.added.remove(widget)
        if self.current is widget:
            self.current = None


def build_workflow_shell() -> SimpleNamespace:
    """Build a shell double containing workflow UI dependencies."""
    connected_editor_panels: list[object] = []
    connected_cube_stacks: list[object] = []
    layout_applied_stacks: list[object] = []
    values: dict[str, Any] = {
        "node_definition_gateway": object(),
        "node_presentation_service": object(),
        "prompt_autocomplete_gateway": object(),
        "prompt_wildcard_catalog_gateway": object(),
        "danbooru_url_import_service": object(),
        "danbooru_wiki_service": object(),
        "danbooru_image_preview_service": object(),
        "danbooru_recent_posts_service": object(),
        "prompt_lora_catalog_service": object(),
        "scheduled_lora_provider": object(),
        "prompt_scheduled_lora_service": object(),
        "prompt_spellcheck_service": object(),
        "prompt_feature_profile_service": object(),
        "prompt_editor_preference_service": SimpleNamespace(
            load_preferences=lambda: SimpleNamespace(wheel_adjustment_mode="precise")
        ),
        "model_catalog_service": object(),
        "model_choice_resolver": object(),
        "thumbnail_asset_repository": object(),
        "model_metadata_context_action_handler": object(),
        "node_behavior_service": object(),
        "user_preset_service": object(),
        "_error_presenter": object(),
        "workflow_issue_state": object(),
        "editor_panel_execution_factories": object(),
        "synthetic_canvas_resolution_role_service": object(),
        "synthetic_canvas_resolution_controller": SimpleNamespace(
            open_for_role=lambda _workflow_id, _role: None
        ),
        "pinned_override_service": object(),
        "override_dropdown_btn": object(),
        "_global_override_menu": object(),
        "editor_panels": {},
        "cube_stacks": {},
        "override_managers": {},
        "editor_panel_container": Container(),
        "cube_stack_container": Container(),
        "connected_editor_panels": connected_editor_panels,
        "connected_cube_stacks": connected_cube_stacks,
        "layout_applied_stacks": layout_applied_stacks,
        "workflow_session_service": SimpleNamespace(
            workflows={"wf-1": WorkflowState()}
        ),
        "cube_stack_presentation_controller": SimpleNamespace(
            prepare_stack=layout_applied_stacks.append
        ),
    }
    return SimpleNamespace(**values)


def install_signal_binder(
    monkeypatch: pytest.MonkeyPatch,
    shell: SimpleNamespace,
) -> None:
    """Route signal binding through an observable composed binder."""
    binder = SimpleNamespace(
        connect_editor_panel_signals=shell.connected_editor_panels.append,
        connect_cube_stack_signals=shell.connected_cube_stacks.append,
    )

    def binder_for(candidate: object) -> SimpleNamespace:
        """Return the test binder for the expected shell."""
        assert candidate is shell
        return binder

    monkeypatch.setattr(
        "substitute.presentation.shell.workflow_ui_factory.main_window_signal_binder_for",
        binder_for,
    )

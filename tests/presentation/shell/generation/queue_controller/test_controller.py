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

"""Tests for the shell generation queue presentation controller."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.presentation.shell.generation_queue_controller import (
    GenerationQueueController,
)
from substitute.presentation.widgets.menu_model import MenuItem, MenuModel


def test_generation_queue_controller_user_toggle_uses_transition() -> None:
    """User queue-panel toggles should animate and request session persistence."""

    transition_calls: list[bool] = []
    autosaves: list[bool] = []
    availability_refreshes: list[bool] = []
    shell = SimpleNamespace(
        sidePanelHost=SimpleNamespace(is_queue_panel_visible=lambda: False),
        _generation_queue_panel_transition=SimpleNamespace(
            transition_to=lambda visible: transition_calls.append(visible)
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: availability_refreshes.append(
                True
            )
        ),
        request_session_autosave=lambda: autosaves.append(True),
    )
    controller = GenerationQueueController(shell)

    controller.set_panel_visible(True)

    assert transition_calls == [True]
    assert shell._generation_queue_panel_visible is True
    assert availability_refreshes == [True]
    assert autosaves == [True]


def test_generation_queue_controller_restore_visibility_skips_transition() -> None:
    """Restored queue-panel visibility should apply directly without autosave."""

    transition_calls: list[bool] = []
    host_calls: list[bool] = []
    autosaves: list[bool] = []
    availability_refreshes: list[bool] = []
    shell = SimpleNamespace(
        sidePanelHost=SimpleNamespace(
            is_queue_panel_visible=lambda: (
                bool(host_calls[-1]) if host_calls else False
            ),
            set_queue_panel_visible=lambda visible: host_calls.append(visible),
        ),
        _generation_queue_panel_transition=SimpleNamespace(
            transition_to=lambda visible: transition_calls.append(visible)
        ),
        generation_action_controller=SimpleNamespace(
            apply_generation_action_availability=lambda: availability_refreshes.append(
                True
            )
        ),
        request_session_autosave=lambda: autosaves.append(True),
    )
    controller = GenerationQueueController(shell)

    controller.apply_panel_visibility(
        True,
        request_autosave=False,
        animated=False,
    )

    assert transition_calls == []
    assert host_calls == [True]
    assert shell._generation_queue_panel_visible is True
    assert availability_refreshes == [True]
    assert autosaves == []


def test_generation_queue_controller_opens_snapshots_through_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue surfaces should call the extracted generation-result opener."""

    queue_controller_mod = importlib.import_module(
        "substitute.presentation.shell.generation_queue_controller"
    )
    delegated: list[dict[str, object]] = []
    open_callbacks: list[Callable[[str], None]] = []
    surfaces: list[FakeQueueSurface] = []
    panels: list[object] = []

    def fake_open_generation_job_as_workflow_for_view(**kwargs: object) -> None:
        """Record generation-result opener collaborator wiring."""

        delegated.append(kwargs)

    class FakeSignal:
        """Record connected hide callbacks from the fake queue panel."""

        def __init__(self) -> None:
            """Create an empty callback list."""

            self.callbacks: list[Callable[[], None]] = []

        def connect(self, callback: Callable[[], None]) -> None:
            """Store a connected callback."""

            self.callbacks.append(callback)

    class FakeQueueSurface:
        """Capture queue surface construction without creating widgets."""

        def __init__(
            self,
            queue_service: object,
            *,
            open_snapshot_requested: Callable[[str], None],
            parent: object,
        ) -> None:
            """Store construction inputs and snapshot callback."""

            self.queue_service = queue_service
            self.open_snapshot_requested = open_snapshot_requested
            self.parent = parent
            self.hideRequested = FakeSignal()
            open_callbacks.append(open_snapshot_requested)
            surfaces.append(self)

    file_actions = SimpleNamespace(name="file-actions")
    queue_service = object()
    side_panel_host = SimpleNamespace(
        set_queue_panel=lambda panel: panels.append(panel)
    )
    shell = SimpleNamespace(
        generation_job_queue_service=queue_service,
        sidePanelHost=side_panel_host,
        workspace_file_actions=file_actions,
    )
    monkeypatch.setattr(
        queue_controller_mod,
        "open_generation_job_as_workflow_for_view",
        fake_open_generation_job_as_workflow_for_view,
    )
    monkeypatch.setattr(
        queue_controller_mod, "GenerationQueueDropdown", FakeQueueSurface
    )
    monkeypatch.setattr(queue_controller_mod, "GenerationQueuePanel", FakeQueueSurface)

    GenerationQueueController(shell).install_surfaces()
    open_callbacks[0]("job-1")

    assert delegated == [
        {
            "generation_view": shell,
            "file_actions": file_actions,
            "job_id": "job-1",
        }
    ]
    assert surfaces[0].queue_service is queue_service
    assert surfaces[0].parent is shell
    assert surfaces[1].parent is side_panel_host
    assert panels == [surfaces[1]]
    assert shell._generation_queue_dropdown is surfaces[0]
    assert shell.generationQueuePanel is surfaces[1]


def test_generation_queue_controller_uses_supplied_titlebar_anchor() -> None:
    """Queue display should anchor to the titlebar queue segment target."""

    anchor = cast(QWidget, object())
    targets: list[object] = []
    shell = SimpleNamespace(
        _generation_queue_dropdown=SimpleNamespace(
            toggle_for=lambda target: targets.append(target)
        )
    )

    GenerationQueueController(shell).show_for(anchor)

    assert targets == [anchor]


def test_generation_queue_controller_context_menu_toggles_side_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queue context menu should expose a titlebar path to the full queue panel."""

    queue_controller_mod = importlib.import_module(
        "substitute.presentation.shell.generation_queue_controller"
    )

    class FakeAction:
        """Record menu action construction and expose a manual trigger."""

        def __init__(
            self,
            icon: object,
            text: str,
            *,
            triggered: Callable[[bool], object],
        ) -> None:
            """Store text and callback for assertions."""

            self.icon = icon
            self.text = text
            self._triggered = triggered

        def trigger(self) -> None:
            """Invoke the stored triggered callback."""

            self._triggered(False)

    class FakeMenu:
        """Record menu actions and popup coordinates."""

        def __init__(self, *, parent: object) -> None:
            """Create an empty menu bound to the supplied parent."""

            self.parent = parent
            self.actions: list[FakeAction] = []
            self.exec_calls: list[tuple[object, object]] = []
            created_menus.append(self)

        def addAction(self, action: FakeAction) -> None:
            """Append one action to the fake menu."""

            self.actions.append(action)

        def exec(self, point: object, *, aniType: object) -> None:
            """Record where the menu would open."""

            self.exec_calls.append((point, aniType))

    def fake_trigger(callback: Callable[[], None] | None) -> Callable[[bool], object]:
        """Return a fake QAction triggered callback wrapper."""

        def trigger(_checked: bool = False) -> object:
            """Dispatch the stored no-argument menu callback."""

            _ = _checked
            if callback is not None:
                callback()
            return None

        return trigger

    class FakeRenderer:
        """Render shared menu models into fake queue context menus."""

        def __init__(self, *, parent: object) -> None:
            """Store the parent target for fake menu creation."""

            self._parent = parent

        def render(self, model: MenuModel) -> FakeMenu:
            """Return a fake menu populated from shared menu entries."""

            menu = FakeMenu(parent=self._parent)
            for entry in model.entries:
                if isinstance(entry, MenuItem):
                    menu.addAction(
                        FakeAction(
                            entry.icon,
                            entry.label,
                            triggered=fake_trigger(entry.callback),
                        )
                    )
            return menu

    class FakeSidePanelHost:
        """Expose side-panel visibility state for the menu toggle."""

        def __init__(self) -> None:
            """Create a hidden fake side panel host."""

            self.visible = False

        def is_queue_panel_visible(self) -> bool:
            """Return current fake queue panel visibility."""

            return self.visible

        def set_queue_panel_visible(self, visible: bool) -> None:
            """Store fake queue panel visibility."""

            self.visible = visible

    class FakeTarget:
        """Provide titlebar-button geometry used by the context menu."""

        def height(self) -> int:
            """Return a stable titlebar segment height."""

            return 32

        def mapToGlobal(self, point: object) -> tuple[str, object]:
            """Return a recognizable global coordinate token."""

            return ("global", point)

    class FakeShell:
        """Expose the controller dependencies needed by the menu path."""

        def __init__(self) -> None:
            """Create a fake shell with a queue side panel host."""

            self.sidePanelHost = FakeSidePanelHost()
            self.autosaves: list[bool] = []
            self.generation_action_controller = SimpleNamespace(
                apply_generation_action_availability=lambda: None
            )

        def request_session_autosave(self) -> None:
            """Record that visibility changes request session persistence."""

            self.autosaves.append(True)

    created_menus: list[FakeMenu] = []
    monkeypatch.setattr(queue_controller_mod, "QFluentMenuRenderer", FakeRenderer)
    shell = FakeShell()
    controller = GenerationQueueController(shell)
    target = cast(QWidget, FakeTarget())

    controller.show_context_menu_for(target)

    first_menu = created_menus[0]
    assert first_menu.actions[0].text == "Show Full Queue Panel"
    assert (
        first_menu.actions[0].icon
        is queue_controller_mod.AppIcon.PANEL_RIGHT_20_REGULAR
    )
    assert first_menu.exec_calls == [
        (
            ("global", queue_controller_mod.QPoint(0, 32)),
            queue_controller_mod.MenuAnimationType.DROP_DOWN,
        )
    ]
    first_menu.actions[0].trigger()
    assert shell.sidePanelHost.visible is True

    controller.show_context_menu_for(target)

    second_menu = created_menus[1]
    assert second_menu.actions[0].text == "Hide Full Queue Panel"
    assert (
        second_menu.actions[0].icon
        is queue_controller_mod.AppIcon.PANEL_RIGHT_20_FILLED
    )
    second_menu.actions[0].trigger()
    assert shell.sidePanelHost.visible is False

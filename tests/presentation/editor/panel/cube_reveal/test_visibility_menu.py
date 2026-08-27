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

"""Verify editor-panel cube reveal-menu behavior and visibility commands."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from pytest import MonkeyPatch

import substitute.presentation.editor.panel.cube_reveal_controller as cube_reveal_controller
from substitute.presentation.editor.panel.cube_reveal_controller import (
    EditorPanelCubeRevealController,
    RevealScrollSurfaceProtocol,
    ScrollBarProtocol,
    SignalEmitterProtocol,
    ViewportProtocol,
    VisibilityButtonProtocol,
)


class _Button:
    """Button double recording enabled and visible state changes."""

    def __init__(self) -> None:
        self.enabled: bool | None = None
        self.visible: bool | None = None

    def setEnabled(self, enabled: bool) -> None:
        """Record enabled state."""

        self.enabled = enabled

    def setVisible(self, visible: bool) -> None:
        """Record visibility state."""

        self.visible = visible


class _Menu:
    """Menu double recording clear and addAction calls."""

    def __init__(self) -> None:
        self.cleared = 0
        self.actions: list[_Action] = []

    def clear(self) -> None:
        """Record clear calls."""

        self.cleared += 1
        self.actions.clear()

    def addAction(self, action: object) -> None:
        """Store one action."""

        if not isinstance(action, _Action):
            raise TypeError("Cube reveal tests require the local action double.")
        self.actions.append(action)


class _Signal:
    """Small signal double storing connected callbacks."""

    def __init__(self) -> None:
        """Initialize empty callback storage."""

        self.callbacks: list[Callable[[bool], object]] = []

    def connect(self, callback: Callable[[bool], object]) -> None:
        """Record one signal callback."""

        self.callbacks.append(callback)

    def emit(self, checked: bool) -> None:
        """Invoke recorded callbacks with supplied arguments."""

        for callback in list(self.callbacks):
            callback(checked)


class _Action:
    """Action double storing check state and payload data."""

    def __init__(self, text: str, parent: object | None) -> None:
        """Initialize one test-only reveal action."""

        del parent
        self.text = text
        self.checked = False
        self.payload: dict[str, str] = {}
        self.toggled = _Signal()

    def setCheckable(self, _checkable: bool) -> None:
        """Accept checkable configuration."""

    def setChecked(self, checked: bool) -> None:
        """Record checked state."""

        self.checked = checked

    def isChecked(self) -> bool:
        """Return current recorded checked state."""

        return bool(self.checked)

    def setData(self, payload: object) -> None:
        """Record action payload."""

        if not isinstance(payload, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in payload.items()
        ):
            raise TypeError(
                "Cube reveal action payload must contain string keys and values."
            )
        self.payload = payload

    def data(self) -> dict[str, str]:
        """Return the configured action payload."""

        return self.payload


@dataclass(frozen=True)
class _RevealEntry:
    """Represent one current cube reveal configuration entry."""

    label: str
    checked: bool
    node_name: str


@dataclass(frozen=True)
class _BehaviorSnapshot:
    """Expose reveal entries through the controller's current snapshot contract."""

    reveal_entries_by_alias: Mapping[str, Sequence[_RevealEntry]]


class _UnusedScrollSurface:
    """Provide the unused scroll protocol members required by the reveal host."""

    def widget(self) -> None:
        """Return no scroll-content widget for menu-only tests."""

        return None

    def viewport(self) -> ViewportProtocol:
        """Return a zero-height viewport for menu-only controller paths."""

        return _UnusedViewport()

    def verticalScrollBar(self) -> ScrollBarProtocol:  # noqa: N802
        """Return an inert scrollbar for menu-only controller paths."""

        return _UnusedScrollBar()

    def visible_content_top(self) -> int:
        """Reject visibility reads outside the menu-only controller paths."""

        raise AssertionError("Menu-only tests must not read visible content.")

    def visible_content_bottom(self) -> int:
        """Reject visibility reads outside the menu-only controller paths."""

        raise AssertionError("Menu-only tests must not read visible content.")

    def content_y_to_scroll_value(self, content_y: int) -> int:
        """Reject geometry conversion outside the menu-only controller paths."""

        del content_y
        raise AssertionError("Menu-only tests must not convert scroll geometry.")


class _UnusedViewport:
    """Provide an inert viewport for menu-only controller construction."""

    def height(self) -> int:
        """Return the unused viewport height."""

        return 0


class _UnusedScrollBar:
    """Provide an inert scrollbar for menu-only controller construction."""

    def value(self) -> int:
        """Return the current inert value."""

        return 0

    def setValue(self, value: int) -> None:  # noqa: N802
        """Reject scroll writes outside menu-only controller paths."""

        del value
        raise AssertionError("Menu-only tests must not set scroll position.")

    def maximum(self) -> int:
        """Return the inert maximum scroll value."""

        return 0


class _CurrentCubeSignal:
    """Provide the controller-required visible-cube signal without side effects."""

    def emit(self, route_key: str) -> None:
        """Accept a route key outside the menu-only contract under test."""

        del route_key


class _NodeBehaviorService:
    """Record visibility and activation commands emitted by reveal menu actions."""

    def __init__(self) -> None:
        """Initialize empty command recording collections."""

        self.visibility_calls: list[tuple[object, str, bool | None]] = []
        self.activation_calls: list[tuple[object, str, bool | None]] = []

    def set_node_visibility_override(
        self,
        cube_state: object,
        node_name: str,
        explicit_revealed: bool | None,
    ) -> None:
        """Record one visibility override command."""

        self.visibility_calls.append((cube_state, node_name, explicit_revealed))

    def set_node_activation_override(
        self,
        cube_state: object,
        node_name: str,
        explicit_enabled: bool | None,
    ) -> None:
        """Record one activation override command."""

        self.activation_calls.append((cube_state, node_name, explicit_enabled))


class _PanelDouble:
    """Provide the exact reveal-controller host surface used by menu contracts."""

    def __init__(
        self,
        *,
        snapshot: _BehaviorSnapshot | None = None,
        cube_states: dict[str, object] | None = None,
        menus: dict[str, object] | None = None,
        buttons: Mapping[str, VisibilityButtonProtocol] | None = None,
        behavior_service: _NodeBehaviorService | None = None,
        sender: object | None = None,
    ) -> None:
        """Initialize menu-specific host state with safe inert defaults."""

        self.scroll: RevealScrollSurfaceProtocol = _UnusedScrollSurface()
        self.cube_sections: Mapping[str, object] = {}
        self._cube_states = cube_states
        self._cube_visibility_btns: dict[str, VisibilityButtonProtocol] = dict(
            buttons or {}
        )
        self._cube_visibility_menus = menus or {}
        self._stack_order: Sequence[str] | None = None
        self.node_behavior_service: object = behavior_service or _NodeBehaviorService()
        self.currentCubeVisibleChanged: SignalEmitterProtocol = _CurrentCubeSignal()
        self._snapshot = snapshot
        self._sender = sender
        self.refresh_calls: list[dict[str, str]] = []

    def sender(self) -> object | None:
        """Return the configured signal sender for alias recovery."""

        return self._sender

    def current_behavior_snapshot(self) -> _BehaviorSnapshot | None:
        """Return the configured prepared behavior snapshot."""

        return self._snapshot

    def refresh_node_behavior_state(self, *, reason: str) -> None:
        """Record one refresh request after a visibility mutation."""

        self.refresh_calls.append({"reason": reason})


def _controller(panel: _PanelDouble) -> EditorPanelCubeRevealController:
    """Create the real reveal controller through its typed host boundary."""

    return EditorPanelCubeRevealController(panel)


def test_rebuild_cube_visibility_menu_hides_button_without_entries() -> None:
    """Reveal menu rebuild should hide the button when no entries remain."""

    menu = _Menu()
    button = _Button()
    panel = _PanelDouble(
        snapshot=_BehaviorSnapshot(reveal_entries_by_alias={"CubeA": ()}),
        menus={"CubeA": menu},
        buttons={"CubeA": button},
    )

    _controller(panel).rebuild_cube_visibility_menu("CubeA")

    assert menu.cleared == 1
    assert button.enabled is False
    assert button.visible is False


def test_rebuild_cube_visibility_menu_builds_checked_actions(
    monkeypatch: MonkeyPatch,
) -> None:
    """Reveal menu rebuild should materialize checked actions with alias payloads."""

    monkeypatch.setattr(cube_reveal_controller, "QAction", _Action)
    menu = _Menu()
    button = _Button()
    panel = _PanelDouble(
        snapshot=_BehaviorSnapshot(
            reveal_entries_by_alias={"CubeA": (_RevealEntry("ksampler", True, "N1"),)}
        ),
        menus={"CubeA": menu},
        buttons={"CubeA": button},
    )

    _controller(panel).rebuild_cube_visibility_menu("CubeA")

    assert button.enabled is True
    assert button.visible is True
    assert len(menu.actions) == 1
    assert menu.actions[0].checked is True
    assert menu.actions[0].payload == {"alias": "CubeA", "node_name": "N1"}
    assert len(menu.actions[0].toggled.callbacks) == 1


def test_rebuild_cube_visibility_menu_actions_persist_new_checked_state(
    monkeypatch: MonkeyPatch,
) -> None:
    """Reveal actions should dispatch the new toggled state, not triggered state."""

    monkeypatch.setattr(cube_reveal_controller, "QAction", _Action)
    menu = _Menu()
    button = _Button()
    cube_state = object()
    behavior_service = _NodeBehaviorService()
    panel = _PanelDouble(
        snapshot=_BehaviorSnapshot(
            reveal_entries_by_alias={
                "CubeA": (_RevealEntry("VAE Override", False, "vae"),)
            }
        ),
        cube_states={"CubeA": cube_state},
        menus={"CubeA": menu},
        buttons={"CubeA": button},
        behavior_service=behavior_service,
    )
    builder = _controller(panel)
    rebuilt: list[str] = []
    original_rebuild = builder.rebuild_cube_visibility_menu

    def _recording_rebuild(alias: str) -> None:
        rebuilt.append(alias)

    monkeypatch.setattr(builder, "rebuild_cube_visibility_menu", _recording_rebuild)
    original_rebuild("CubeA")

    action = menu.actions[0]
    action.toggled.emit(True)

    assert behavior_service.visibility_calls == [(cube_state, "vae", True)]
    assert panel.refresh_calls == [{"reason": "node_activation_changed"}]
    assert rebuilt == ["CubeA"]


def test_on_cube_visibility_menu_triggered_resolves_alias_from_sender(
    monkeypatch: MonkeyPatch,
) -> None:
    """Menu-trigger routing should recover alias from the sender menu when needed."""

    menu = object()
    calls: list[tuple[str, object]] = []
    panel = _PanelDouble(menus={"CubeA": menu}, sender=menu)
    builder = _controller(panel)

    def _record_toggle(alias: str, action: object) -> None:
        """Record one routed alias and action."""

        calls.append((alias, action))

    monkeypatch.setattr(builder, "on_cube_visibility_menu_toggled", _record_toggle)
    action = _Action("unused", None)

    builder.on_cube_visibility_menu_triggered(action)

    assert calls == [("CubeA", action)]


def test_on_cube_visibility_menu_toggled_uses_service_command_and_refreshes(
    monkeypatch: MonkeyPatch,
) -> None:
    """Reveal toggles should dispatch through the visibility command surface."""

    cube_state = object()
    behavior_service = _NodeBehaviorService()
    rebuilt: list[str] = []
    panel = _PanelDouble(
        cube_states={"CubeA": cube_state},
        behavior_service=behavior_service,
    )
    builder = _controller(panel)

    def _record_rebuild(alias: str) -> None:
        """Record one requested menu rebuild."""

        rebuilt.append(alias)

    monkeypatch.setattr(builder, "rebuild_cube_visibility_menu", _record_rebuild)
    action = _Action("KSampler", None)
    action.setData({"node_name": "ksampler"})
    action.setChecked(True)

    builder.on_cube_visibility_menu_toggled("CubeA", action)

    assert behavior_service.visibility_calls == [(cube_state, "ksampler", True)]
    assert behavior_service.activation_calls == []
    assert panel.refresh_calls == [{"reason": "node_activation_changed"}]
    assert rebuilt == ["CubeA"]


def test_on_cube_visibility_menu_toggled_clears_override_when_unchecked(
    monkeypatch: MonkeyPatch,
) -> None:
    """Unchecking the reveal menu should clear the reveal override."""

    cube_state = object()
    behavior_service = _NodeBehaviorService()
    panel = _PanelDouble(
        cube_states={"CubeA": cube_state},
        behavior_service=behavior_service,
    )
    builder = _controller(panel)

    def _ignore_rebuild(alias: str) -> None:
        """Discard the expected post-command rebuild request."""

        del alias

    monkeypatch.setattr(builder, "rebuild_cube_visibility_menu", _ignore_rebuild)
    action = _Action("KSampler", None)
    action.setData({"node_name": "ksampler"})
    action.setChecked(False)

    builder.on_cube_visibility_menu_toggled("CubeA", action)

    assert behavior_service.visibility_calls == [(cube_state, "ksampler", None)]

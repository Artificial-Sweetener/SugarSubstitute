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

"""Contract tests for extracted cube-section assembly and reveal-menu logic."""

from __future__ import annotations

import importlib
from types import SimpleNamespace


def _import_module():
    """Import the cube reveal controller module."""

    return importlib.import_module(
        "substitute.presentation.editor.panel.cube_reveal_controller"
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
        self.actions: list[object] = []

    def clear(self) -> None:
        """Record clear calls."""

        self.cleared += 1
        self.actions.clear()

    def addAction(self, action: object) -> None:
        """Store one action."""

        self.actions.append(action)


class _Signal:
    """Small signal double storing connected callbacks."""

    def __init__(self) -> None:
        """Initialize empty callback storage."""

        self.callbacks = []

    def connect(self, callback) -> None:
        """Record one signal callback."""

        self.callbacks.append(callback)

    def emit(self, *args) -> None:
        """Invoke recorded callbacks with supplied arguments."""

        for callback in list(self.callbacks):
            callback(*args)


class _Action:
    """Action double storing check state and payload data."""

    def __init__(self, text: str, _parent: object) -> None:
        self.text = text
        self.checked: bool | None = None
        self.payload = None
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

        self.payload = payload


def test_rebuild_cube_visibility_menu_hides_button_without_entries() -> None:
    """Reveal menu rebuild should hide the button when no entries remain."""

    mod = _import_module()
    menu = _Menu()
    button = _Button()
    panel = SimpleNamespace(
        _cube_visibility_menus={"CubeA": menu},
        _cube_visibility_btns={"CubeA": button},
        _last_behavior_snapshot=SimpleNamespace(reveal_entries_by_alias={"CubeA": []}),
    )

    mod.EditorPanelCubeRevealController(panel).rebuild_cube_visibility_menu("CubeA")

    assert menu.cleared == 1
    assert button.enabled is False
    assert button.visible is False


def test_rebuild_cube_visibility_menu_builds_checked_actions(
    monkeypatch,
) -> None:
    """Reveal menu rebuild should materialize checked actions with alias payloads."""

    mod = _import_module()
    monkeypatch.setattr(mod, "QAction", _Action)
    menu = _Menu()
    button = _Button()
    panel = SimpleNamespace(
        _cube_visibility_menus={"CubeA": menu},
        _cube_visibility_btns={"CubeA": button},
        _last_behavior_snapshot=SimpleNamespace(
            reveal_entries_by_alias={
                "CubeA": [
                    SimpleNamespace(label="ksampler", checked=True, node_name="N1")
                ]
            }
        ),
    )

    mod.EditorPanelCubeRevealController(panel).rebuild_cube_visibility_menu("CubeA")

    assert button.enabled is True
    assert button.visible is True
    assert len(menu.actions) == 1
    assert menu.actions[0].checked is True
    assert menu.actions[0].payload == {"alias": "CubeA", "node_name": "N1"}
    assert len(menu.actions[0].toggled.callbacks) == 1


def test_rebuild_cube_visibility_menu_actions_persist_new_checked_state(
    monkeypatch,
) -> None:
    """Reveal actions should dispatch the new toggled state, not triggered state."""

    mod = _import_module()
    monkeypatch.setattr(mod, "QAction", _Action)
    menu = _Menu()
    button = _Button()
    cube_state = object()
    visibility_calls: list[tuple[object, str, bool | None]] = []
    refresh_calls: list[dict[str, object]] = []
    panel = SimpleNamespace(
        _cube_visibility_menus={"CubeA": menu},
        _cube_visibility_btns={"CubeA": button},
        _cube_states={"CubeA": cube_state},
        node_behavior_service=SimpleNamespace(
            set_node_visibility_override=lambda cube_state, node_name, explicit_revealed: (
                visibility_calls.append((cube_state, node_name, explicit_revealed))
            )
        ),
        refresh_node_behavior_state=lambda **kwargs: refresh_calls.append(kwargs),
        _last_behavior_snapshot=SimpleNamespace(
            reveal_entries_by_alias={
                "CubeA": [
                    SimpleNamespace(
                        label="VAE Override", checked=False, node_name="vae"
                    )
                ]
            }
        ),
    )
    builder = mod.EditorPanelCubeRevealController(panel)
    rebuilt: list[str] = []
    original_rebuild = builder.rebuild_cube_visibility_menu

    def _recording_rebuild(alias: str) -> None:
        rebuilt.append(alias)

    builder.rebuild_cube_visibility_menu = _recording_rebuild
    original_rebuild("CubeA")

    action = menu.actions[0]
    action.toggled.emit(True)

    assert visibility_calls == [(cube_state, "vae", True)]
    assert refresh_calls == [{"reason": "node_activation_changed"}]
    assert rebuilt == ["CubeA"]


def test_on_cube_visibility_menu_triggered_resolves_alias_from_sender(
    monkeypatch,
) -> None:
    """Menu-trigger routing should recover alias from the sender menu when needed."""

    mod = _import_module()
    menu = object()
    calls: list[tuple[str, object]] = []
    panel = SimpleNamespace(
        _cube_visibility_menus={"CubeA": menu},
        sender=lambda: menu,
    )
    builder = mod.EditorPanelCubeRevealController(panel)
    monkeypatch.setattr(
        builder,
        "on_cube_visibility_menu_toggled",
        lambda alias, action: calls.append((alias, action)),
    )
    action = SimpleNamespace(data=lambda: {})

    builder.on_cube_visibility_menu_triggered(action)

    assert calls == [("CubeA", action)]


def test_on_cube_visibility_menu_toggled_uses_service_command_and_refreshes() -> None:
    """Reveal toggles should dispatch through the visibility command surface."""

    mod = _import_module()
    cube_state = object()
    visibility_calls: list[tuple[object, str, bool | None]] = []
    activation_calls: list[tuple[object, str, bool | None]] = []
    refresh_calls: list[dict[str, object]] = []
    rebuilt: list[str] = []
    panel = SimpleNamespace(
        _cube_states={"CubeA": cube_state},
        node_behavior_service=SimpleNamespace(
            set_node_visibility_override=lambda cube_state, node_name, explicit_revealed: (
                visibility_calls.append((cube_state, node_name, explicit_revealed))
            ),
            set_node_activation_override=lambda cube_state, node_name, explicit_enabled: (
                activation_calls.append((cube_state, node_name, explicit_enabled))
            ),
        ),
        refresh_node_behavior_state=lambda **kwargs: refresh_calls.append(kwargs),
    )
    builder = mod.EditorPanelCubeRevealController(panel)
    builder.rebuild_cube_visibility_menu = lambda alias: rebuilt.append(alias)
    action = SimpleNamespace(
        data=lambda: {"node_name": "ksampler"},
        isChecked=lambda: True,
    )

    builder.on_cube_visibility_menu_toggled("CubeA", action)

    assert visibility_calls == [(cube_state, "ksampler", True)]
    assert activation_calls == []
    assert refresh_calls == [{"reason": "node_activation_changed"}]
    assert rebuilt == ["CubeA"]


def test_on_cube_visibility_menu_toggled_clears_override_when_unchecked() -> None:
    """Unchecking the reveal menu should clear the reveal override."""

    mod = _import_module()
    cube_state = object()
    service_calls: list[tuple[object, str, bool | None]] = []
    panel = SimpleNamespace(
        _cube_states={"CubeA": cube_state},
        node_behavior_service=SimpleNamespace(
            set_node_visibility_override=lambda cube_state, node_name, explicit_revealed: (
                service_calls.append((cube_state, node_name, explicit_revealed))
            )
        ),
        refresh_node_behavior_state=lambda **_kwargs: None,
    )
    builder = mod.EditorPanelCubeRevealController(panel)
    builder.rebuild_cube_visibility_menu = lambda _alias: None
    action = SimpleNamespace(
        data=lambda: {"node_name": "ksampler"},
        isChecked=lambda: False,
    )

    builder.on_cube_visibility_menu_toggled("CubeA", action)

    assert service_calls == [(cube_state, "ksampler", None)]

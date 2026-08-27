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

"""Test editor-panel behavior-snapshot application contracts."""

from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace
from typing import Any

from _pytest.monkeypatch import MonkeyPatch


class _CardWrapper:
    """Record node-card visibility and dynamic properties."""

    def __init__(self, visible: bool) -> None:
        """Initialize card visibility."""

        self.visible = visible
        self.props: dict[str, object] = {}

    def isVisible(self) -> bool:  # noqa: N802
        """Return current visibility."""

        return self.visible

    def setVisible(self, visible: bool) -> None:  # noqa: N802
        """Record a visibility update."""

        self.visible = visible

    def setProperty(self, name: str, value: object) -> None:  # noqa: N802
        """Record one dynamic property update."""

        self.props[name] = value


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_refresh_node_behavior_state_reapplies_last_state_on_snapshot_failure(
    monkeypatch: MonkeyPatch,
) -> None:
    """Snapshot failures should fall back to last known card and hidden-field state."""

    module = _panel_module()
    monkeypatch.setattr(module, "isValid", lambda _object: True)

    card = _CardWrapper(visible=True)
    cube_state = SimpleNamespace(buffer={"nodes": {"N1": {"inputs": {}}}}, ui={})
    hidden_calls: list[set[str]] = []
    rebuild_calls: list[bool] = []

    panel = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        card_wrappers={("CubeA", "N1"): card},
        _last_card_decisions={("CubeA", "N1"): (False, True, "previous")},
        _last_hidden_field_keys={"seed"},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _build_behavior_snapshot=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
        set_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
        _rebuild_all_cube_visibility_menus=lambda: rebuild_calls.append(True),
    )

    module.EditorPanel.refresh_node_behavior_state(panel)

    assert card.visible is False
    assert hidden_calls == [{"seed"}]
    assert rebuild_calls == []


def test_refresh_node_behavior_state_updates_cards_buffers_and_hidden_fields(
    monkeypatch: MonkeyPatch,
) -> None:
    """Successful snapshot application should update wrappers, hidden fields, and menus."""

    module = _panel_module()
    monkeypatch.setattr(module, "isValid", lambda _object: True)

    card = _CardWrapper(visible=False)
    cube_state = SimpleNamespace(buffer={"nodes": {"N1": {"inputs": {}}}}, ui={})
    hidden_calls: list[set[str]] = []
    rebuild_calls: list[bool] = []
    snapshot_calls: list[dict[str, object]] = []
    snapshot = SimpleNamespace(
        card_decisions_by_alias={
            "CubeA": {
                "N1": SimpleNamespace(
                    visible=True,
                    enabled=False,
                    reason="search_and_policy",
                )
            }
        },
        hidden_field_keys_by_alias={"CubeA": {"seed"}},
        reveal_entries_by_alias={"CubeA": []},
    )

    def build_behavior_snapshot(**kwargs: object) -> Any:
        """Record and return the prepared behavior snapshot."""

        snapshot_calls.append(kwargs)
        return snapshot

    panel = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        card_wrappers={("CubeA", "N1"): card},
        _last_card_decisions={},
        _last_hidden_field_keys=set(),
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _build_behavior_snapshot=build_behavior_snapshot,
        refresh_prompt_scene_diagnostics=lambda: None,
        set_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
        _rebuild_all_cube_visibility_menus=lambda: rebuild_calls.append(True),
    )

    module.EditorPanel.refresh_node_behavior_state(
        panel,
        search_hidden_keys={"sampler_name"},
        node_search_text="ksampler",
    )

    assert snapshot_calls == [
        {
            "search_hidden_keys": {"sampler_name"},
            "node_search_text": "ksampler",
        }
    ]
    assert card.visible is True
    assert panel._last_hidden_field_keys == {"seed"}
    assert hidden_calls == [{"seed"}]
    assert panel._last_card_decisions[("CubeA", "N1")] == (
        True,
        False,
        "search_and_policy",
    )
    assert rebuild_calls == [True]

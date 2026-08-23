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

"""Focused tests for editor behavior application collaborators."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest


class _CardWrapper:
    """Minimal node-card wrapper for visibility assertions."""

    def __init__(self, visible: bool) -> None:
        self.visible = visible
        self.props: dict[str, object] = {}

    def setVisible(self, visible: bool) -> None:
        """Record visibility updates."""

        self.visible = visible

    def setProperty(self, name: str, value: object) -> None:
        """Record one dynamic property update."""

        self.props[name] = value


def test_restore_previous_state_reapplies_last_cards_and_hidden_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Snapshot-failure fallback should restore wrappers and hidden keys only."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.behavior.behavior_applier"
    )
    monkeypatch.setattr(mod, "isValid", lambda _obj: True)

    card = _CardWrapper(visible=True)
    cube_state = SimpleNamespace(buffer={"nodes": {"N1": {"inputs": {}}}})
    hidden_calls: list[set[object]] = []
    _ = cube_state
    state = mod.EditorBehaviorState(
        last_card_decisions={("CubeA", "N1"): (False, True, "previous")},
        last_hidden_field_keys={"seed"},
    )
    ports = mod.EditorBehaviorApplicationPorts(
        card_wrapper=lambda _alias, _node_name: card,
        apply_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
        apply_node_card_decisions=lambda _decisions: None,
        publish_behavior_snapshot=lambda _snapshot: None,
        rebuild_cube_visibility_menus=lambda: None,
    )

    mod.EditorBehaviorApplier(state, ports).restore_previous_state()

    assert card.visible is False
    assert hidden_calls == [{"seed"}]


def test_apply_snapshot_updates_wrappers_buffers_and_visibility_menus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Applying a snapshot should update wrappers, hidden keys, and menus only."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.behavior.behavior_applier"
    )
    monkeypatch.setattr(mod, "isValid", lambda _obj: True)

    card = _CardWrapper(visible=False)
    cube_state = SimpleNamespace(buffer={"nodes": {"N1": {"inputs": {}}}})
    hidden_calls: list[set[object]] = []
    rebuild_calls: list[bool] = []
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
    )
    _ = cube_state
    state = mod.EditorBehaviorState()
    published_snapshots: list[object] = []
    node_card_decisions: list[object] = []
    ports = mod.EditorBehaviorApplicationPorts(
        card_wrapper=lambda _alias, _node_name: card,
        apply_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
        apply_node_card_decisions=lambda decisions: node_card_decisions.append(
            decisions
        ),
        publish_behavior_snapshot=lambda current: published_snapshots.append(current),
        rebuild_cube_visibility_menus=lambda: rebuild_calls.append(True),
    )

    mod.EditorBehaviorApplier(state, ports).apply_snapshot(snapshot)

    assert card.visible is True
    assert card.props["base_card_visible"] is True
    assert state.last_card_decisions == {
        ("CubeA", "N1"): (True, False, "search_and_policy")
    }
    assert state.last_hidden_field_keys == {"seed"}
    assert hidden_calls == [{"seed"}]
    assert node_card_decisions == [snapshot.card_decisions_by_alias]
    assert published_snapshots == [snapshot]
    assert rebuild_calls == [True]


def test_apply_snapshot_does_not_write_derived_enabled_state_back_into_buffers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Snapshot application must not persist computed enabled values."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.behavior.behavior_applier"
    )
    monkeypatch.setattr(mod, "isValid", lambda _obj: True)

    card = _CardWrapper(visible=False)
    cube_state = SimpleNamespace(buffer={"nodes": {"N1": {"inputs": {}}}})
    snapshot = SimpleNamespace(
        card_decisions_by_alias={
            "CubeA": {
                "N1": SimpleNamespace(
                    visible=True,
                    enabled=False,
                    reason="policy:hidden",
                )
            }
        },
        hidden_field_keys_by_alias={"CubeA": set()},
    )
    _ = cube_state
    ports = mod.EditorBehaviorApplicationPorts(
        card_wrapper=lambda _alias, _node_name: card,
        apply_hidden_field_keys=lambda _keys: None,
        apply_node_card_decisions=lambda _decisions: None,
        publish_behavior_snapshot=lambda _snapshot: None,
        rebuild_cube_visibility_menus=lambda: None,
    )

    mod.EditorBehaviorApplier(mod.EditorBehaviorState(), ports).apply_snapshot(snapshot)

    assert "enabled" not in cube_state.buffer["nodes"]["N1"]

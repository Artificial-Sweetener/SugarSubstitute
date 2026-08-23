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

"""Test editor-panel behavior-refresh transaction contracts."""

from __future__ import annotations

import importlib
import logging
from types import ModuleType, SimpleNamespace
from typing import Any

from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch


def _panel_module() -> ModuleType:
    """Return the production editor-panel module."""

    return importlib.import_module("substitute.presentation.editor.panel.view")


def test_behavior_refresh_transaction_reuses_matching_snapshot(
    caplog: LogCaptureFixture,
) -> None:
    """A refresh transaction should reuse one matching behavior snapshot."""

    module = _panel_module()
    snapshots = [object()]
    build_calls: list[dict[str, object]] = []

    class _NodeBehaviorService:
        def build_snapshot(self, **kwargs: object) -> object:
            build_calls.append(kwargs)
            return snapshots[0]

    cube_state = SimpleNamespace(buffer={"nodes": {}}, ui={})
    panel: Any = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _last_behavior_snapshot=None,
        _behavior_refresh_transaction=None,
        node_behavior_service=_NodeBehaviorService(),
        _workflow_overrides=lambda: {"seed": {"value": 7}},
        current_behavior_snapshot=lambda: None,
    )
    panel._prompt_context_controller = module.EditorPanelPromptContextController(panel)
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.prompt.context",
    )

    module.EditorPanel.begin_behavior_refresh_transaction(
        panel,
        reason="full_workflow_projection",
    )
    first_snapshot = module.EditorPanel._build_behavior_snapshot(panel)
    second_snapshot = module.EditorPanel._build_behavior_snapshot(panel)
    module.EditorPanel.end_behavior_refresh_transaction(
        panel,
        reason="full_workflow_projection",
    )

    assert first_snapshot is snapshots[0]
    assert second_snapshot is snapshots[0]
    assert len(build_calls) == 1
    assert "Reused editor behavior snapshot from refresh transaction" in caplog.text
    assert panel._behavior_refresh_transaction is None


def test_behavior_refresh_transaction_builds_fresh_after_link_change() -> None:
    """State-changing behavior refresh reasons should invalidate transactions."""

    module = _panel_module()
    snapshots = [
        SimpleNamespace(card_decisions_by_alias={}, hidden_field_keys_by_alias={}),
        SimpleNamespace(card_decisions_by_alias={}, hidden_field_keys_by_alias={}),
    ]
    build_calls: list[dict[str, object]] = []
    applied: list[object] = []

    class _NodeBehaviorService:
        def build_snapshot(self, **kwargs: object) -> object:
            build_calls.append(kwargs)
            return snapshots[len(build_calls) - 1]

    cube_state = SimpleNamespace(buffer={"nodes": {}}, ui={})
    panel: Any = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _last_behavior_snapshot=None,
        _behavior_refresh_transaction=None,
        node_behavior_service=_NodeBehaviorService(),
        _workflow_overrides=lambda: {},
        _build_behavior_snapshot=lambda **kwargs: (
            module.EditorPanel._build_behavior_snapshot(
                panel,
                **kwargs,
            )
        ),
        set_hidden_field_keys=lambda _keys: None,
        apply_node_card_behavior_decisions=lambda decisions: applied.append(decisions),
        _rebuild_all_cube_visibility_menus=lambda: None,
        current_behavior_snapshot=lambda: None,
        refresh_prompt_scene_diagnostics=lambda: None,
    )
    panel._prompt_context_controller = module.EditorPanelPromptContextController(panel)

    module.EditorPanel.begin_behavior_refresh_transaction(panel, reason="cube_added")
    module.EditorPanel._build_behavior_snapshot(panel)
    module.EditorPanel.refresh_node_behavior_state(panel, reason="node_link_changed")

    assert len(build_calls) == 2
    assert panel._last_behavior_snapshot is snapshots[1]
    assert panel._behavior_refresh_transaction is None
    assert applied == [{}]


def test_model_option_refresh_invalidates_behavior_without_projection(
    monkeypatch: MonkeyPatch,
) -> None:
    """Fresh model values should not mark the rendered editor structure stale."""

    module = _panel_module()
    calls: list[tuple[str, object]] = []
    snapshot = SimpleNamespace(
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
    )
    panel: Any = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": SimpleNamespace(buffer={"nodes": {}}, ui={})},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _build_behavior_snapshot=lambda **_kwargs: snapshot,
        refresh_prompt_scene_diagnostics=lambda: None,
    )
    monkeypatch.setattr(
        module.EditorPanel,
        "invalidate_behavior_refresh_transaction",
        lambda _panel, *, reason: calls.append(("behavior", reason)),
    )
    monkeypatch.setattr(
        module.EditorPanel,
        "invalidate_projection",
        lambda _panel, *, reason: calls.append(("projection", reason)),
    )
    monkeypatch.setattr(
        module,
        "behavior_applier_for_panel",
        lambda _panel: SimpleNamespace(
            apply_snapshot=lambda applied: calls.append(("applied", applied)),
            restore_previous_state=lambda: None,
        ),
    )
    module.EditorPanel.refresh_node_behavior_state(
        panel,
        reason="model_options_changed",
        use_cached_snapshot=False,
    )

    assert calls == [
        ("behavior", "model_options_changed"),
        ("applied", snapshot),
    ]

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

"""Verify workflow override application and behavior refresh."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.overrides import PinnedOverrideService
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)
from tests.presentation.editor.panel.overrides.support import (
    _DummyWidget,
    _field_spec,
    _install_toolbar_view_stubs,
    _snapshot,
)


def test_apply_global_overrides_falls_back_to_hidden_tuple_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback hidden-field updates should use resolved tuple keys when recompute fails."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("seed"),
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=5,
            order=10,
        )
    )
    hidden_calls: list[set[object]] = []
    cube = SimpleNamespace(
        buffer={"nodes": {"ksampler": {"inputs": {"seed": 0}}}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={"seed": {"value": 5, "mode": "global"}},
    )
    panel = SimpleNamespace(
        current_behavior_snapshot=lambda: snapshot,
        refresh_node_behavior_state=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
        set_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
    )
    mainwindow = SimpleNamespace(
        active_editor_panel=panel,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()

    manager.apply_global_overrides()

    assert cube.buffer["nodes"]["ksampler"]["inputs"]["seed"] == 5
    assert hidden_calls == [{("A", "ksampler", "seed")}]


def test_apply_global_overrides_rebuilds_snapshot_after_buffer_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changed override writes should force a fresh behavior snapshot refresh."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("sampler"),
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="",
            order=20,
        )
    )
    refresh_calls: list[dict[str, object]] = []
    cube = SimpleNamespace(
        buffer={"nodes": {"ksampler": {"inputs": {"sampler_name": ""}}}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={
            "sampler_name": {"value": "euler_ancestral", "mode": "global"}
        },
    )
    panel = SimpleNamespace(
        current_behavior_snapshot=lambda: snapshot,
        refresh_node_behavior_state=lambda **kwargs: refresh_calls.append(kwargs),
    )
    manager = GlobalOverridesManager(
        SimpleNamespace(
            active_editor_panel=panel, get_active_workflow=lambda: workflow
        ),
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()

    manager.apply_global_overrides(use_cached_behavior_snapshot=True)

    assert cube.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == (
        "euler_ancestral"
    )
    assert refresh_calls == [
        {"reason": "global_override_changed", "use_cached_snapshot": False}
    ]


def test_apply_global_overrides_reuses_cached_snapshot_when_buffers_do_not_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged override writes may keep the caller-requested cached snapshot path."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("sampler"),
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="euler_ancestral",
            order=20,
        )
    )
    refresh_calls: list[dict[str, object]] = []
    cube = SimpleNamespace(
        buffer={"nodes": {"ksampler": {"inputs": {"sampler_name": "euler_ancestral"}}}},
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        cubes={"A": cube},
        global_overrides={
            "sampler_name": {"value": "euler_ancestral", "mode": "global"}
        },
    )
    panel = SimpleNamespace(
        current_behavior_snapshot=lambda: snapshot,
        refresh_node_behavior_state=lambda **kwargs: refresh_calls.append(kwargs),
    )
    manager = GlobalOverridesManager(
        SimpleNamespace(
            active_editor_panel=panel, get_active_workflow=lambda: workflow
        ),
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()

    manager.apply_global_overrides(use_cached_behavior_snapshot=True)

    assert cube.buffer["nodes"]["ksampler"]["inputs"]["sampler_name"] == (
        "euler_ancestral"
    )
    assert refresh_calls == [
        {"reason": "global_override_changed", "use_cached_snapshot": True}
    ]

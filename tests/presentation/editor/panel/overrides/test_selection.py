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

"""Verify override selection and default materialization behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.node_behavior import OverridePinPolicy
from substitute.application.overrides import PinnedOverrideService
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)
from tests.presentation.editor.panel.overrides.support import (
    _DummyAction,
    _DummyLayout,
    _DummyWidget,
    _SnapshotSource,
    _field_spec,
    _install_toolbar_view_stubs,
    _snapshot,
)


def test_toggle_unpins_override_without_reapplying_default_toolbar_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unpinning from the menu should stay local so default-pinned fields remain unpinned."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("seed"),
    )
    local_refresh_calls: list[str] = []
    shell_refresh_calls: list[bool] = []
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 123, "mode": "global"}},
        global_override_selections={"seed": True},
    )
    mainwindow = SimpleNamespace(
        active_editor_panel=SimpleNamespace(
            current_behavior_snapshot=lambda: _snapshot(
                _field_spec(
                    override_key="seed",
                    field_key="seed",
                    value=123,
                    order=10,
                )
            )
        ),
        get_active_workflow=lambda: workflow,
        refresh_active_workflow_surface=lambda: shell_refresh_calls.append(True),
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.sync_state_from_workflow()
    monkeypatch.setattr(
        manager,
        "rebuild_override_menu",
        lambda: local_refresh_calls.append("menu"),
    )
    monkeypatch.setattr(
        manager,
        "rebuild_active_override_controls",
        lambda: local_refresh_calls.append("controls"),
    )
    monkeypatch.setattr(
        manager,
        "apply_global_overrides",
        lambda: local_refresh_calls.append("apply"),
    )

    manager._on_override_menu_toggled(
        _DummyAction({"override_key": "seed"}, checked=False)
    )

    assert workflow.global_overrides == {}
    assert workflow.global_override_selections == {"seed": False}
    assert local_refresh_calls == ["menu", "controls", "apply"]
    assert shell_refresh_calls == []


def test_unchecked_default_selection_blocks_default_rematerialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A restored unchecked default-pinned field should remain absent after refresh."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={},
        global_override_selections={"seed": False},
    )
    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            )
        )
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=source,
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    manager.override_dropdown_btn = override_button
    manager.sync_state_from_workflow()

    changed = manager.materialize_default_overrides()
    manager.rebuild_active_override_controls()

    assert changed is False
    assert workflow.global_overrides == {}
    assert workflow.global_override_selections == {"seed": False}
    assert manager._global_override_controls == {}


def test_checking_optional_override_persists_selection_and_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checking an optional candidate should persist menu intent and active value."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda **_kwargs: _DummyWidget("cfg"),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={},
        global_override_selections={},
    )
    mainwindow = SimpleNamespace(
        active_editor_panel=SimpleNamespace(
            current_behavior_snapshot=lambda: _snapshot(
                _field_spec(
                    override_key="cfg",
                    field_key="cfg",
                    value=5.5,
                    order=40,
                    pin_policy=OverridePinPolicy.OPTIONAL,
                    field_type="FLOAT",
                )
            )
        ),
        get_active_workflow=lambda: workflow,
    )
    manager = GlobalOverridesManager(
        mainwindow,
        pinned_override_service=PinnedOverrideService(),
        node_definition_gateway=SimpleNamespace(get_node_definition=lambda _node: {}),
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
    )
    monkeypatch.setattr(manager, "rebuild_override_menu", lambda: None)
    monkeypatch.setattr(manager, "rebuild_active_override_controls", lambda: None)
    monkeypatch.setattr(manager, "apply_global_overrides", lambda: None)

    manager.sync_state_from_workflow()
    manager._on_override_menu_toggled(_DummyAction({"override_key": "cfg"}, True))

    assert workflow.global_override_selections == {"cfg": True}
    assert workflow.global_overrides == {"cfg": {"value": 5.5, "mode": "global"}}

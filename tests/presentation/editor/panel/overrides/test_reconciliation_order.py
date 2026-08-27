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

"""Verify toolbar control removal, ordering, and field replacement."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from substitute.application.node_behavior import ResolvedFieldSpec
from substitute.application.overrides import PinnedOverrideService
from substitute.presentation.editor.panel.overrides_controller import (
    GlobalOverridesManager,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
)
from tests.presentation.editor.panel.overrides.support import (
    _DummyLayout,
    _DummyWidget,
    _SnapshotSource,
    _field_spec,
    _install_toolbar_view_stubs,
    _snapshot,
)


def test_rebuild_active_override_controls_removes_inactive_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Controls no longer active in the toolbar snapshot should be disposed."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            ),
            _field_spec(
                override_key="cfg",
                field_key="cfg",
                value=5.5,
                order=20,
                field_type="FLOAT",
            ),
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "cfg": {"value": 5.5, "mode": "global"},
        },
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
    manager.rebuild_active_override_controls()
    removed_label, removed_widget = manager._global_override_controls["cfg"]

    workflow.global_overrides = {"seed": {"value": 7, "mode": "global"}}
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    assert set(manager._global_override_controls) == {"seed"}
    assert removed_label.deleted is True
    assert removed_widget.deleted is True
    assert removed_label not in layout.widgets
    assert removed_widget not in layout.widgets


def test_rebuild_active_override_controls_reorders_reused_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reused controls should be moved to the active snapshot order."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            ),
            _field_spec(
                override_key="cfg",
                field_key="cfg",
                value=5.5,
                order=20,
                field_type="FLOAT",
            ),
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "cfg": {"value": 5.5, "mode": "global"},
        },
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
    manager.rebuild_active_override_controls()
    seed_control = manager._global_override_controls["seed"]
    cfg_control = manager._global_override_controls["cfg"]

    source.snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=30,
        ),
        _field_spec(
            override_key="cfg",
            field_key="cfg",
            value=5.5,
            order=10,
            field_type="FLOAT",
        ),
    )
    manager.rebuild_active_override_controls()

    assert manager._global_override_controls["seed"] == seed_control
    assert manager._global_override_controls["cfg"] == cfg_control
    assert layout.widgets == [
        override_button,
        cfg_control[0],
        cfg_control[1],
        seed_control[0],
        seed_control[1],
    ]


def test_rebuild_active_override_controls_inserts_after_layout_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active controls should follow the under-orb layout anchor when present."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value=7,
                order=10,
            ),
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 7, "mode": "global"}},
    )
    anchor = object()
    override_button = SimpleNamespace(
        property=lambda name: anchor if name == "layoutAnchorWidget" else None
    )
    layout = _DummyLayout()
    layout.widgets.append(anchor)
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
    manager.rebuild_active_override_controls()

    seed_label, seed_widget = manager._global_override_controls["seed"]
    assert layout.widgets == [anchor, seed_label, seed_widget]


def test_rebuild_active_override_controls_replaces_changed_field_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed field render contract should replace only the affected control."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(
        *, field_spec: ResolvedFieldSpec, **_kwargs: object
    ) -> _DummyWidget | None:
        assert field_spec.field_type is not None
        build_calls.append(field_spec.field_type)
        return _DummyWidget(f"{field_spec.field_key}-{field_spec.field_type}")

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="seed",
                field_key="seed",
                value="7",
                order=10,
            )
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": "7", "mode": "global"}},
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
    manager.rebuild_active_override_controls()
    old_label, old_widget = manager._global_override_controls["seed"]

    source.snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
            field_type="INT",
        )
    )
    workflow.global_overrides = {"seed": {"value": 7, "mode": "global"}}
    manager.sync_state_from_workflow()
    manager.rebuild_active_override_controls()

    assert build_calls == ["STRING", "INT"]
    assert manager._global_override_controls["seed"] != (old_label, old_widget)
    assert old_label.deleted is True
    assert old_widget.deleted is True

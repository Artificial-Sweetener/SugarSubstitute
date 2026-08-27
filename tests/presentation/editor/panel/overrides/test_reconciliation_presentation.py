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

"""Verify toolbar control sizing, tooltip, and spacing presentation."""

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
    _DummyLabel,
    _DummyLayout,
    _DummyWidget,
    _RestartToolbarButton,
    _field_spec,
    _install_toolbar_view_stubs,
    _snapshot,
)


def test_rebuild_active_override_controls_refreshes_restart_toolbar_spacing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override rebuilds should restore the single end absorber for toolbar slack."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="er_sde",
            order=10,
            field_type="LIST",
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"sampler_name": {"value": "er_sde", "mode": "global"}},
    )
    restart_button = _RestartToolbarButton()
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        pendingRestartButton=restart_button,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
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

    assert restart_button.refresh_calls == 1


def test_rebuild_active_override_controls_refreshes_spacing_when_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged override rows still need restart spacer reconciliation."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="er_sde",
            order=10,
            field_type="LIST",
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"sampler_name": {"value": "er_sde", "mode": "global"}},
    )
    restart_button = _RestartToolbarButton()
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        pendingRestartButton=restart_button,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
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
    manager.rebuild_active_override_controls()

    assert restart_button.refresh_calls == 2


def test_rebuild_active_override_controls_binds_fluent_tooltip_to_label_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Toolbar override tooltips should use one QFluent label owner for label and control."""

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=lambda *, field_spec, **_kwargs: _DummyWidget(
            field_spec.field_key
        ),
    )
    tooltip_text = "The number of denoise steps."
    snapshot = _snapshot(
        _field_spec(
            override_key="steps",
            field_key="steps",
            value=20,
            order=10,
            field_type="INT",
            meta_info={"tooltip": tooltip_text},
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"steps": {"value": 20, "mode": "global"}},
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
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
    manager._toolbar_snapshot = manager._service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides=manager._global_overrides,
    )

    manager.rebuild_active_override_controls()

    label, widget = manager._global_override_controls["steps"]
    assert isinstance(label, _DummyLabel)
    assert isinstance(widget, _DummyWidget)
    assert label.size_policy == ("fixed", "preferred")
    assert widget.size_policy == ("maximum", "fixed")
    assert label.tooltip == tooltip_text
    assert len(label.filters) == 1
    assert widget.filters == label.filters


def test_rebuild_active_override_controls_uses_toolbar_numeric_height(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Numeric toolbar overrides should align to the normal toolbar control height."""

    created_widgets: dict[str, _DummyWidget] = {}

    def _build_widget_for_field_spec(
        *, field_spec: ResolvedFieldSpec, **_kwargs: object
    ) -> _DummyWidget | None:
        widget = _DummyWidget(field_spec.field_key)
        created_widgets[field_spec.field_key] = widget
        return widget

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="steps",
            field_key="steps",
            value=28,
            order=40,
            field_type="INT",
        ),
        _field_spec(
            override_key="cfg",
            field_key="cfg",
            value=5.5,
            order=50,
            field_type="FLOAT",
        ),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "steps": {"value": 28, "mode": "global"},
            "cfg": {"value": 5.5, "mode": "global"},
        },
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=SimpleNamespace(current_behavior_snapshot=lambda: snapshot),
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

    assert created_widgets["steps"].fixed_width is None
    assert created_widgets["cfg"].fixed_width is None
    assert created_widgets["steps"].fixed_height == 32
    assert created_widgets["cfg"].fixed_height == 32
    assert created_widgets["steps"].size_policy == ("maximum", "fixed")
    assert created_widgets["cfg"].size_policy == ("maximum", "fixed")
    assert created_widgets["steps"].stylesheet is None
    assert created_widgets["cfg"].stylesheet is None
    assert created_widgets["steps"].maximum_width is None
    assert created_widgets["cfg"].maximum_width is None

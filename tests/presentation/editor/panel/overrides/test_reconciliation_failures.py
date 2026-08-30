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

"""Verify toolbar construction failure isolation."""

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
    _field_spec,
    _install_toolbar_view_stubs,
    _snapshot,
)


def test_rebuild_active_override_controls_skips_failed_control_without_clearing_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One control build failure should not clear unrelated pinned override state."""

    def _build_widget_for_field_spec(
        *, field_spec: ResolvedFieldSpec, **_kwargs: object
    ) -> _DummyWidget | None:
        if field_spec.field_key == "scheduler":
            return None
        return _DummyWidget(field_spec.field_key)

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
        ),
        _field_spec(
            override_key="scheduler",
            field_key="scheduler",
            value="karras",
            order=30,
        ),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "scheduler": {"value": "karras", "mode": "global"},
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
    manager._toolbar_snapshot = manager._service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides=manager._global_overrides,
    )

    manager.rebuild_active_override_controls()

    assert set(manager._global_overrides) == {"seed", "scheduler"}
    assert set(manager._global_override_controls) == {"seed"}


def test_rebuild_active_override_controls_skips_raising_control_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One toolbar widget factory exception should not abort the whole rebuild."""

    def _build_widget_for_field_spec(
        *, field_spec: ResolvedFieldSpec, **_kwargs: object
    ) -> _DummyWidget | None:
        if field_spec.field_key == "sampler_name":
            raise RuntimeError("missing live choices")
        return _DummyWidget(field_spec.field_key)

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
    )
    snapshot = _snapshot(
        _field_spec(
            override_key="seed",
            field_key="seed",
            value=7,
            order=10,
        ),
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="euler",
            order=20,
        ),
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "seed": {"value": 7, "mode": "global"},
            "sampler_name": {"value": "euler", "mode": "global"},
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
    manager._toolbar_snapshot = manager._service.build_toolbar_snapshot(
        behavior_snapshot=snapshot,
        stack_order=["A"],
        overrides=manager._global_overrides,
    )

    manager.rebuild_active_override_controls()

    assert set(manager._global_overrides) == {"seed", "sampler_name"}
    assert set(manager._global_override_controls) == {"seed"}

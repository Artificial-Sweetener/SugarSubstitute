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

"""Verify toolbar control reuse and live-contract replacement."""

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


def test_rebuild_active_override_controls_reuses_unchanged_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged pinned override controls should stay mounted across rebuilds."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(
        *, field_spec: ResolvedFieldSpec, **_kwargs: object
    ) -> _DummyWidget | None:
        build_calls.append(field_spec.field_key)
        return _DummyWidget(f"{field_spec.field_key}-{len(build_calls)}")

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
        )
    )
    source = _SnapshotSource(snapshot)
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 7, "mode": "global"}},
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
    first_label, first_widget = manager._global_override_controls["seed"]
    manager.rebuild_active_override_controls()

    assert build_calls == ["seed"]
    assert manager._global_override_controls["seed"] == (first_label, first_widget)
    assert layout.widgets == [override_button, first_label, first_widget]
    assert first_label.deleted is False
    assert first_widget.deleted is False


def test_rebuild_active_override_controls_remounts_detached_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tab switches should remount cached controls without rebuilding widgets."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(
        *, field_spec: ResolvedFieldSpec, **_kwargs: object
    ) -> _DummyWidget | None:
        build_calls.append(field_spec.field_key)
        return _DummyWidget(f"{field_spec.field_key}-{len(build_calls)}")

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
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={"seed": {"value": 7, "mode": "global"}},
    )
    override_button = object()
    layout = _DummyLayout()
    layout.widgets.append(override_button)
    mainwindow = SimpleNamespace(
        menu_bar=object(),
        menu_bar_layout=layout,
        active_editor_panel=_SnapshotSource(snapshot),
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
    first_label, first_widget = manager._global_override_controls["seed"]

    manager.detach_override_widgets()
    assert first_label.visible is False
    assert first_widget.visible is False

    manager.rebuild_active_override_controls()

    assert build_calls == ["seed"]
    assert manager._global_override_controls["seed"] == (first_label, first_widget)
    assert layout.widgets == [override_button, first_label, first_widget]
    assert first_label.deleted is False
    assert first_widget.deleted is False
    assert first_label.visible is True
    assert first_widget.visible is True


def test_rebuild_active_override_controls_replaces_choice_fallback_after_live_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Choice controls should wait for resolved inventories instead of fallbacks."""

    build_calls: list[str] = []

    def _build_widget_for_field_spec(
        *, field_spec: ResolvedFieldSpec, **_kwargs: object
    ) -> _DummyWidget | None:
        build_calls.append(field_spec.field_key)
        return _DummyWidget(f"{field_spec.field_key}-{len(build_calls)}")

    _install_toolbar_view_stubs(
        monkeypatch,
        build_widget_callback=_build_widget_for_field_spec,
        choice_options_callback=lambda **kwargs: tuple(kwargs["field_info"][0]),
    )
    source = _SnapshotSource(
        _snapshot(
            _field_spec(
                override_key="sampler_name",
                field_key="sampler_name",
                value="euler_ancestral",
                order=10,
                field_type="LIST",
                field_info=["LIST", {"dynamic": True}],
            )
        )
    )
    workflow = SimpleNamespace(
        stack_order=["A"],
        global_overrides={
            "sampler_name": {"value": "euler_ancestral", "mode": "global"}
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

    assert "sampler_name" not in manager._global_override_controls
    assert build_calls == []

    source.snapshot = _snapshot(
        _field_spec(
            override_key="sampler_name",
            field_key="sampler_name",
            value="euler_ancestral",
            order=10,
            field_type="LIST",
            field_info=[["euler", "euler_ancestral", "heun"], {"default": "euler"}],
        )
    )
    manager.rebuild_active_override_controls()

    assert build_calls == ["sampler_name"]
    assert "sampler_name" in manager._global_override_controls
    label, widget = manager._global_override_controls["sampler_name"]
    assert label.size_policy == ("fixed", "preferred")
    assert widget.size_policy == ("maximum", "fixed")
    assert widget.maximum_width == 180

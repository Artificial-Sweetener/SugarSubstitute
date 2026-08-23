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

"""Test full-projection preparation, reconciliation, and layout reset."""

from __future__ import annotations

from __future__ import annotations
import importlib
from types import SimpleNamespace
import substitute.presentation.editor.panel.projection_preparation as projection_preparation
from tests.presentation.editor.panel.projection_support import (
    _Layout,
    _LayoutItem,
    _NestedLayout,
    _Signal,
    _Widget,
)


def test_load_all_cubes_reconciles_widgets_and_applies_cached_refresh() -> None:
    """Coordinator should reuse widgets, remove stale aliases, and refresh once."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )

    keep_widget = _Widget()
    old_widget = object()
    new_widget = _Widget()
    layout_parent = _Widget("layout-parent")
    layout = _Layout(
        [_LayoutItem(widget=old_widget), _LayoutItem(widget=keep_widget)],
        parent_widget=layout_parent,
    )
    removed_widgets: list[object] = []
    built_aliases: list[str] = []
    scroll_signal = _Signal()
    scrollbar = SimpleNamespace(valueChanged=scroll_signal, value=lambda: 17)
    scroll_updates: list[int] = []
    recompute_calls: list[str] = []
    prompt_calls: list[tuple[str, object]] = []
    widget_refresh_calls: list[str] = []
    refresh_kwargs: list[dict[str, object]] = []

    cube_keep = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _build_cube_widget(alias: str, _state: object) -> object:
        built_aliases.append(alias)
        return new_widget

    def _remove_cube_widget(widget: object) -> None:
        removed_widgets.append(widget)

    def _record_scroll(value: int) -> None:
        scroll_updates.append(value)

    def _record_refresh(**kwargs: object) -> None:
        recompute_calls.append("recompute")
        refresh_kwargs.append(kwargs)

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Keep": keep_widget, "Old": old_widget},
        cube_sections={"Keep": keep_widget, "Old": old_widget},
        cube_headers={"Old": object()},
        card_wrappers={("Old", "Node"): object(), ("Keep", "Node"): object()},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: prompt_calls.append(("sanitize", None)),
        reconcile_prompt_link_state=lambda **kwargs: prompt_calls.append(
            ("reconcile", kwargs)
        ),
        sync_prompt_editor_values_from_buffers=lambda: widget_refresh_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: widget_refresh_calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: None,
        _remove_cube_widget_from_layout=_remove_cube_widget,
        _build_cube_widget=_build_cube_widget,
        _build_behavior_snapshot=lambda **_kwargs: None,
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=_record_scroll,
        refresh_node_behavior_state=_record_refresh,
    )

    mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
        [("Keep", cube_keep), ("New", cube_new)],
        cube_states={"Keep": cube_keep, "New": cube_new},
        stack_order=["Keep", "New"],
    )

    assert removed_widgets == [old_widget]
    assert built_aliases == ["New"]
    assert ("Old", "Node") not in panel.card_wrappers
    assert panel.cube_sections == {"Keep": keep_widget, "New": new_widget}
    assert panel.cube_headers == {}
    assert layout.added == [
        ("spacing", 8),
        ("widget", keep_widget),
        ("spacing", 8),
        ("widget", new_widget),
    ]
    assert layout.activate_calls == 1
    assert layout_parent.updates_enabled_changes == [False, True]
    assert layout_parent.update_calls == 1
    assert scroll_updates == [17]
    assert len(scroll_signal.connected) == 1
    assert widget_refresh_calls == ["prompt_values", "links"]
    assert prompt_calls == [
        (
            "reconcile",
            {
                "previous_cube_states": None,
                "previous_stack_order": None,
                "cube_states": {"Keep": cube_keep, "New": cube_new},
                "stack_order": ["Keep", "New"],
            },
        ),
    ]
    assert recompute_calls == ["recompute"]
    assert refresh_kwargs == [
        {"reason": "full_workflow_projection", "use_cached_snapshot": True}
    ]


def test_load_all_cubes_marks_clean_with_post_reconciliation_signature() -> None:
    """Clean-projection reuse should key off the final reconciled surface state."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    widget = _Widget()
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    cube = SimpleNamespace(buffer={"nodes": {}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _workflow_overrides=lambda: {},
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _current_node_search_text=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: None,
        reconcile_prompt_link_state=lambda **_kwargs: None,
        sync_prompt_editor_values_from_buffers=lambda: None,
        _refresh_link_widgets=lambda: None,
        _refresh_sampler_scheduler_link_state=lambda: None,
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: widget,
        _build_behavior_snapshot=lambda **_kwargs: None,
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: None,
        refresh_node_behavior_state=lambda **_kwargs: None,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    cube_states = {"A": cube}

    coordinator.load_all_cubes(
        [("A", cube)],
        cube_states=cube_states,
        stack_order=["A"],
        projection_signature=object(),
    )

    clean_signature = coordinator._composition.projection_state.clean_signature
    assert clean_signature == coordinator.current_projection_signature(
        workflow_id="",
        cube_entries=[("A", cube)],
        cube_states=cube_states,
        stack_order=["A"],
    )


def test_load_all_cubes_hydrates_before_reconciliation_and_behavior_snapshot() -> None:
    """Full projection should hydrate definitions before migration or widgets."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    calls: list[str] = []
    layout = _Layout([])
    scroll_signal = _Signal()
    scrollbar = SimpleNamespace(valueChanged=scroll_signal, value=lambda: 0)
    cube = SimpleNamespace(buffer={"nodes": {"sampler": {"class_type": "KSampler"}}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: calls.append("reconcile"),
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: _Widget("new"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=lambda **_kwargs: calls.append("snapshot"),
        _on_scroll_updated=lambda _value: None,
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )

    mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
        [("A", cube)],
        cube_states={"A": cube},
        stack_order=["A"],
    )

    assert calls.index("hydrate") < calls.index("reconcile")
    assert calls.index("hydrate") < calls.index("snapshot")


def test_load_all_cubes_preparation_owns_prompt_context_and_identity() -> None:
    """Full projection preparation should publish identity and context lifetime."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    calls: list[str] = []
    widget = _Widget("prepared")
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    cube = SimpleNamespace(
        cube_id="cube-a",
        version="1.0",
        original_cube={
            "surface": {"nodes": ["node"]},
            "nodes": {"node": {"class_type": "KSampler"}},
        },
        buffer={"nodes": {"node": {"class_type": "KSampler", "inputs": {}}}},
    )
    cube_states = {"A": cube}

    def _begin_projection_prompt_context(**kwargs: object) -> None:
        stack_order = kwargs.get("stack_order")
        stack_order_token = (
            tuple(stack_order) if isinstance(stack_order, (list, tuple)) else ()
        )
        calls.append(f"context_begin:{stack_order_token}:{kwargs.get('reason')}")

    def _build_cube_widget(_alias: str, _state: object) -> object:
        calls.append("build")
        return widget

    def _build_behavior_snapshot(**_kwargs: object) -> str:
        calls.append("snapshot")
        return "snapshot"

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: calls.append("reconcile"),
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=_build_cube_widget,
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=_build_behavior_snapshot,
        begin_projection_prompt_context=_begin_projection_prompt_context,
        clear_projection_prompt_context=lambda *, reason: calls.append(
            f"context_clear:{reason}"
        ),
        _on_scroll_updated=lambda _value: calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.load_all_cubes(
        [("A", cube)],
        cube_states=cube_states,
        stack_order=["A"],
    )

    record = coordinator._composition.build_registry.record_for("A")
    assert record is not None
    identity = record.snapshot_identity
    assert isinstance(
        identity, projection_preparation.EditorProjectionPreparationIdentity
    )
    assert identity.workflow_id == ""
    assert identity.reason == "full_workflow_projection"
    assert identity.stack_order == ("A",)
    assert identity.cube_state_map_id == id(cube_states)
    assert identity.errored_aliases == frozenset()
    assert identity.cube_definition_identities[0][0] == "A"
    assert calls.index("context_begin:('A',):full_workflow_projection") < calls.index(
        "build"
    )
    assert calls[-1] == "context_clear:full_workflow_projection_complete"


def test_load_all_cubes_clears_legacy_root_layout_content() -> None:
    """Full projection should remove obsolete top-level editor layout content."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )

    keep_widget = _Widget("keep")
    stale_widget = _Widget("stale")
    stale_nested_widget = _Widget("nested")
    legacy_layout = _NestedLayout([_LayoutItem(widget=stale_nested_widget)])
    layout = _Layout(
        [
            _LayoutItem(layout=legacy_layout),
            _LayoutItem(widget=stale_widget),
            _LayoutItem(widget=keep_widget),
        ]
    )
    scroll_signal = _Signal()
    scrollbar = SimpleNamespace(valueChanged=scroll_signal, value=lambda: 0)
    cube_keep = SimpleNamespace(buffer={"nodes": {}})

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Keep": keep_widget},
        cube_sections={"Keep": keep_widget},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: None,
        reconcile_prompt_link_state=lambda **_kwargs: None,
        sync_prompt_editor_values_from_buffers=lambda: None,
        _refresh_link_widgets=lambda: None,
        _refresh_sampler_scheduler_link_state=lambda: None,
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: keep_widget,
        _build_behavior_snapshot=lambda **_kwargs: None,
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: None,
        refresh_node_behavior_state=lambda **_kwargs: None,
    )

    mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
        [("Keep", cube_keep)],
        cube_states={"Keep": cube_keep},
        stack_order=["Keep"],
    )

    assert stale_widget.deleted == 1
    assert stale_nested_widget.deleted == 1
    assert keep_widget.deleted == 0
    assert keep_widget.parents == [None]
    assert layout.count() == 0
    assert legacy_layout.count() == 0
    assert layout.added == [("spacing", 8), ("widget", keep_widget)]

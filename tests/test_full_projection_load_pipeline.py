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

"""Focused tests for full projection load pipeline behavior."""

from __future__ import annotations

import ast
import importlib
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import substitute.presentation.editor.panel.hidden_build_scheduler as hidden_build_scheduler
import substitute.presentation.editor.panel.projection_preparation as projection_preparation
from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild
from tests.editor_projection_test_helpers import (
    _BuildSession,
    _FailingAddLayout,
    _FinalizingWidget,
    _Layout,
    _LayoutItem,
    _NestedLayout,
    _Signal,
    _TimerQueue,
    _Widget,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "full_projection_load_pipeline.py"
)
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)
COMPOSITION_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_composition.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "substitute.presentation.editor.panel.projection_coordinator",
)


def _imported_module_names(path: Path) -> set[str]:
    """Return all imported module names in a Python source file."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _patch_hidden_build_timer(
    monkeypatch: pytest.MonkeyPatch,
    timer_queue: _TimerQueue,
) -> None:
    """Route hidden-build scheduler timers through a deterministic queue."""

    timer = cast(Any, getattr(hidden_build_scheduler, "QTimer"))
    monkeypatch.setattr(
        timer,
        "singleShot",
        staticmethod(timer_queue.singleShot),
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


def test_load_all_cubes_clears_preparation_prompt_context_after_widget_failure() -> (
    None
):
    """Widget-preparation failures should clear full projection prompt context."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    cube = SimpleNamespace(buffer={"nodes": {}})

    def _raise_build_failure(_alias: str, _state: object) -> object:
        calls.append("build")
        raise RuntimeError("build failed")

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
        _build_cube_widget=_raise_build_failure,
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        _build_behavior_snapshot=_build_behavior_snapshot,
        begin_behavior_refresh_transaction=lambda *, reason: calls.append(
            f"begin_transaction:{reason}"
        ),
        end_behavior_refresh_transaction=lambda *, reason: calls.append(
            f"end_transaction:{reason}"
        ),
        begin_projection_prompt_context=lambda **_kwargs: calls.append("context_begin"),
        clear_projection_prompt_context=lambda *, reason: calls.append(
            f"context_clear:{reason}"
        ),
        _on_scroll_updated=lambda _value: None,
        refresh_node_behavior_state=lambda **_kwargs: None,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    with pytest.raises(RuntimeError, match="build failed"):
        coordinator.load_all_cubes(
            [("A", cube)],
            cube_states={"A": cube},
            stack_order=["A"],
        )

    assert "context_begin" in calls
    assert "context_clear:full_workflow_projection_error" in calls
    assert calls.count("end_transaction:full_workflow_projection") == 1


def test_load_all_cubes_stops_when_hydration_fails() -> None:
    """Missing live definitions should block prompt migration and projection."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    cube = SimpleNamespace(buffer={"nodes": {"sampler": {"class_type": "KSampler"}}})
    live_error = error_mod.LiveNodeDefinitionError(
        operation="hydrate editor projection node definitions",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(class_type="KSampler"),
        ),
    )

    def _raise_hydration_error(**_kwargs: object) -> None:
        calls.append("hydrate")
        raise live_error

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
        hydrate_node_definitions_for_projection=_raise_hydration_error,
        _build_behavior_snapshot=lambda **_kwargs: calls.append("snapshot"),
        _on_scroll_updated=lambda _value: None,
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )

    with pytest.raises(error_mod.LiveNodeDefinitionError):
        mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
            [("A", cube)],
            cube_states={"A": cube},
            stack_order=["A"],
        )

    assert calls == ["hydrate"]
    assert panel._cube_states == {"A": cube}
    assert panel._stack_order == ["A"]


def test_projection_metadata_retry_stops_when_issue_aliases_do_not_change() -> None:
    """Recoverable metadata retries should stop when no new bad cube is isolated."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    live_error = error_mod.LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=("Bad",),
                node_names=("resize_by_factor",),
            ),
        ),
    )

    def _register_projection_error(
        _error: object,
        *,
        reason: str,
        source: object,
    ) -> bool:
        """Record recoverable registration without changing errored aliases."""

        _ = reason, source
        calls.append("register")
        return True

    def _present_recoverable_error(
        _error: object,
        *,
        reason: str,
    ) -> None:
        """Record recoverable report presentation."""

        _ = reason
        calls.append("present")

    panel = SimpleNamespace(
        _cube_states={"Bad": object()},
        _stack_order=["Bad"],
        register_projection_live_node_definition_error=_register_projection_error,
        present_recoverable_live_node_definition_error=_present_recoverable_error,
        cube_runtime_error_aliases=lambda: (),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    def _raise_metadata_error(_aliases: frozenset[str]) -> None:
        calls.append("metadata")
        raise live_error

    with pytest.raises(error_mod.LiveNodeDefinitionError):
        coordinator._composition.runtime_issues.run_projection_metadata_step(
            workflow_id="workflow-a",
            reason="behavior_snapshot",
            action=_raise_metadata_error,
        )

    assert calls == ["metadata", "register", "present"]


def test_load_all_cubes_recovers_when_prompt_reconciliation_finds_bad_cube() -> None:
    """Cube-attributed prompt-link metadata failures should render error sections."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    good_cube = SimpleNamespace(buffer={"nodes": {"good": {"class_type": "Good"}}})
    bad_cube = SimpleNamespace(buffer={"nodes": {"bad": {"class_type": "Bad"}}})
    good_widget = _Widget("good")
    bad_widget = _Widget("bad-error")
    live_error = error_mod.LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=("Bad",),
                node_names=("resize_by_factor",),
            ),
        ),
    )
    errored_aliases: set[str] = set()

    def _reconcile(**kwargs: object) -> None:
        current_stack = kwargs.get("stack_order")
        current_aliases = (
            tuple(current_stack) if isinstance(current_stack, list) else ()
        )
        calls.append(f"reconcile:{current_aliases}")
        if "Bad" in current_aliases:
            raise live_error

    def _register(
        _error: object,
        *,
        reason: str,
        source: object,
    ) -> bool:
        calls.append(f"register:{reason}:{source}")
        errored_aliases.add("Bad")
        return True

    def _present_recoverable(
        error: object,
        *,
        reason: str,
    ) -> None:
        calls.append(f"present:{reason}:{error is live_error}")

    def _build_behavior_snapshot(**_kwargs: object) -> str:
        calls.append("snapshot")
        assert panel._stack_order == ["Good"]
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
        mainwindow=SimpleNamespace(workflow_session_service=SimpleNamespace()),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=_reconcile,
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda alias, _state: (
            good_widget if alias == "Good" else None
        ),
        _build_error_cube_widget=lambda alias, _state: (
            bad_widget if alias == "Bad" else None
        ),
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        register_projection_live_node_definition_error=_register,
        present_recoverable_live_node_definition_error=_present_recoverable,
        cube_runtime_error_aliases=lambda: tuple(sorted(errored_aliases)),
        begin_live_node_definition_report_projection=lambda: calls.append(
            "begin_reports"
        ),
        clear_projection_runtime_issues=lambda: calls.append("clear_issues"),
        _build_behavior_snapshot=_build_behavior_snapshot,
        _on_scroll_updated=lambda _value: calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )

    mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
        [("Good", good_cube), ("Bad", bad_cube)],
        cube_states={"Good": good_cube, "Bad": bad_cube},
        stack_order=["Good", "Bad"],
    )

    assert "register:prompt_link_reconciliation:projection" in calls
    assert calls.count("present:prompt_link_reconciliation:True") == 1
    assert calls.index("begin_reports") < calls.index(
        "present:prompt_link_reconciliation:True"
    )
    assert "reconcile:('Good',)" in calls
    assert panel.cube_widgets == {"Good": good_widget, "Bad": bad_widget}
    assert panel.cube_sections == {"Good": good_widget, "Bad": bad_widget}


def test_load_all_cubes_recovers_when_behavior_snapshot_finds_bad_cube() -> None:
    """Cube-attributed behavior snapshot failures should retry without bad cubes."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    error_mod = importlib.import_module(
        "substitute.application.node_behavior.live_definition_authority"
    )
    calls: list[str] = []
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 0)
    good_cube = SimpleNamespace(buffer={"nodes": {"good": {"class_type": "Good"}}})
    bad_cube = SimpleNamespace(buffer={"nodes": {"bad": {"class_type": "Bad"}}})
    good_widget = _Widget("good")
    bad_widget = _Widget("bad-error")
    live_error = error_mod.LiveNodeDefinitionError(
        operation="resolve wrapper body node metadata",
        missing_definitions=(
            error_mod.MissingLiveNodeDefinition(
                class_type="SimpleSyrup.KSamplerMixtureOfDiffusers",
                cube_aliases=("Bad",),
                node_names=("resize_by_factor",),
            ),
        ),
    )
    errored_aliases: set[str] = set()

    def _register(
        _error: object,
        *,
        reason: str,
        source: object,
    ) -> bool:
        calls.append(f"register:{reason}:{source}")
        errored_aliases.add("Bad")
        return True

    def _present_recoverable(
        error: object,
        *,
        reason: str,
    ) -> None:
        calls.append(f"present:{reason}:{error is live_error}")

    def _build_behavior_snapshot(**_kwargs: object) -> str:
        current_stack = tuple(panel._stack_order or ())
        calls.append(f"snapshot:{current_stack}")
        if "Bad" in current_stack:
            raise live_error
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
        mainwindow=SimpleNamespace(workflow_session_service=SimpleNamespace()),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: calls.append("reconcile"),
        sync_prompt_editor_values_from_buffers=lambda: calls.append("prompt_values"),
        _refresh_link_widgets=lambda: calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: calls.append("sampler_scheduler"),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda alias, _state: (
            good_widget if alias == "Good" else None
        ),
        _build_error_cube_widget=lambda alias, _state: (
            bad_widget if alias == "Bad" else None
        ),
        hydrate_node_definitions_for_projection=lambda **_kwargs: calls.append(
            "hydrate"
        ),
        register_projection_live_node_definition_error=_register,
        present_recoverable_live_node_definition_error=_present_recoverable,
        cube_runtime_error_aliases=lambda: tuple(sorted(errored_aliases)),
        clear_projection_runtime_issues=lambda: calls.append("clear_issues"),
        _build_behavior_snapshot=_build_behavior_snapshot,
        _on_scroll_updated=lambda _value: calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: calls.append("visibility"),
    )

    mod.EditorPanelProjectionCoordinator(panel).load_all_cubes(
        [("Good", good_cube), ("Bad", bad_cube)],
        cube_states={"Good": good_cube, "Bad": bad_cube},
        stack_order=["Good", "Bad"],
    )

    assert "register:behavior_snapshot:projection" in calls
    assert calls.count("present:behavior_snapshot:True") == 1
    assert "snapshot:('Good', 'Bad')" in calls
    assert "snapshot:('Good',)" in calls
    assert panel._stack_order == ["Good", "Bad"]
    assert panel.cube_widgets == {"Good": good_widget, "Bad": bad_widget}


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


def test_load_all_cubes_defers_missing_widget_builds(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Full projection should use busy state while staged sections build."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
    new_widget = _FinalizingWidget("built", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[False, True])
    busy_calls: list[tuple[str, object]] = []
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _begin_busy(message: str = "Loading") -> str:
        """Record one projection busy begin call."""

        busy_calls.append(("begin", message))
        return "busy-token"

    def _end_busy(token: object) -> None:
        """Record one projection busy end call."""

        busy_calls.append(("end", token))

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: scrollbar,
            schedule_metrics_refresh=lambda: registry_calls.append("metrics_scheduled"),
            refresh_metrics_now=lambda: registry_calls.append("metrics_now"),
        ),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_from_buffers=lambda: registry_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: registry_calls.append("links"),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: (_ for _ in ()).throw(
            AssertionError("full projection should prefer incremental build sessions")
        ),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        _begin_projection_busy=_begin_busy,
        _end_projection_busy=_end_busy,
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.full_projection_load_pipeline",
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.projection_coordinator",
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.projection_busy_adapter",
    )
    caplog.set_level(
        logging.DEBUG,
        logger="sugarsubstitute.presentation.editor.panel.rendering.render_reconciler",
    )

    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states={"New": cube_new},
        stack_order=["New"],
    )

    assert panel.cube_widgets == {}
    assert panel.cube_sections == {}
    assert layout.added == []
    assert build_session.step_calls == 0
    assert busy_calls == [("begin", "Loading")]
    assert new_widget.visible_changes == [False]
    assert new_widget.updates_enabled_changes == [False]
    assert registry_calls == [
        "reconcile",
        "snapshot",
        "sampler_scheduler",
    ]

    timer_queue.run_all()

    assert panel.cube_widgets == {"New": new_widget}
    assert panel.cube_sections == {"New": new_widget}
    assert layout.added[-1] == ("widget", new_widget)
    assert build_session.step_calls == 2
    assert new_widget.visible_changes == [False, True]
    assert new_widget.updates_enabled_changes == [False, True]
    assert new_widget.update_calls == 1
    assert registry_calls[-5:] == [
        "finalize:projected_reveal",
        "metrics_scheduled",
        "prompt_values",
        "links",
        "visibility",
    ]
    assert coordinator._composition.build_registry.record_for("New").state == "complete"
    assert busy_calls == [("begin", "Loading"), ("end", "busy-token")]
    assert "Started editor full projection cube load" in caplog.text
    assert "Began editor projection busy state" in caplog.text
    assert "Scheduled editor cube load reconciliation" in caplog.text
    assert "Revealed projected editor cube section" in caplog.text
    assert "Ended editor projection busy state" in caplog.text
    assert "Completed editor cube load reconciliation" in caplog.text
    assert "busy_started=True" in caplog.text


def test_load_all_cubes_continues_hidden_build_and_defers_visible_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Inactive full projection should keep building without revealing hidden widgets."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
    completion_calls: list[str] = []
    busy_calls: list[tuple[str, object]] = []
    new_widget = _FinalizingWidget("built", registry_calls)
    build_session = _BuildSession(new_widget, step_results=[False, True])
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _begin_projection_busy(message: str = "Loading") -> str:
        """Record projection busy start and return its token."""

        busy_calls.append(("begin", message))
        return "busy-token"

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
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: scrollbar,
            schedule_metrics_refresh=lambda: registry_calls.append("metrics_scheduled"),
            refresh_metrics_now=lambda: registry_calls.append("metrics_now"),
        ),
        mainwindow=SimpleNamespace(workflow_session_service=workflow_session_service),
        node_definition_gateway=object(),
        isVisible=lambda: workflow_session_service.active_workflow_id == "workflow-a",
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_from_buffers=lambda: registry_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: registry_calls.append("links"),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: (_ for _ in ()).throw(
            AssertionError("full projection should prefer incremental build sessions")
        ),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        _begin_projection_busy=_begin_projection_busy,
        _end_projection_busy=lambda token: busy_calls.append(("end", token)),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    cube_states = {"New": cube_new}

    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states=cube_states,
        stack_order=["New"],
        on_complete=lambda: completion_calls.append("complete"),
    )
    timer_queue.run_next()
    workflow_session_service.active_workflow_id = "workflow-b"
    timer_queue.run_all()

    assert build_session.step_calls == 2
    assert coordinator.has_pending_visible_projection_commit()
    assert panel.cube_widgets == {}
    assert panel.cube_sections == {}
    assert layout.added == []
    assert new_widget.visible_changes == [False]
    assert completion_calls == []
    assert coordinator._composition.projection_state.clean_signature is None
    assert busy_calls == [("begin", "Loading")]
    assert "prompt_values" not in registry_calls
    assert "links" not in registry_calls
    assert "visibility" not in registry_calls


def test_load_all_cubes_ends_busy_when_staged_reveal_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Busy state should be released when a staged reveal hits an expected failure."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    new_widget = _Widget("built")
    build_session = _BuildSession(new_widget, step_results=[True])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    registry_calls: list[str] = []
    busy_calls: list[tuple[str, object]] = []
    cube_new = SimpleNamespace(buffer={"nodes": {}})

    def _begin_busy(message: str = "Loading") -> str:
        """Record one projection busy begin call."""

        busy_calls.append(("begin", message))
        return "busy-token"

    def _end_busy(token: object) -> None:
        """Record one projection busy end call."""

        busy_calls.append(("end", token))

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=_FailingAddLayout([]),
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_from_buffers=lambda: registry_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: registry_calls.append("links"),
        sync_prompt_editor_values_for_cube=lambda alias: registry_calls.append(
            f"prompt_values:{alias}"
        ),
        refresh_link_widgets_for_cube=lambda alias: registry_calls.append(
            f"links:{alias}"
        ),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: (_ for _ in ()).throw(
            AssertionError("full projection should prefer incremental build sessions")
        ),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        _begin_projection_busy=_begin_busy,
        _end_projection_busy=_end_busy,
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.full_projection_load_pipeline",
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.projection_coordinator",
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.projection_busy_adapter",
    )

    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states={"New": cube_new},
        stack_order=["New"],
    )

    timer_queue.run_all()

    assert busy_calls == [("begin", "Loading"), ("end", "busy-token")]
    assert "prompt_values" not in registry_calls
    assert "links" not in registry_calls
    assert "visibility" not in registry_calls
    assert coordinator._composition.build_registry.record_for("New").state == "failed"
    assert "Failed editor visible projection commit" in caplog.text
    assert "Ended editor projection busy state" in caplog.text


def test_load_all_cubes_does_not_complete_when_staged_finalization_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Projected builds should remain non-complete when reveal finalization fails."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    registry_calls: list[str] = []
    new_widget = _FinalizingWidget(
        "built",
        registry_calls,
        fail_on_finalize=True,
    )
    build_session = _BuildSession(new_widget, step_results=[True])
    layout = _Layout([])
    scrollbar = SimpleNamespace(valueChanged=_Signal(), value=lambda: 11)
    cube_new = SimpleNamespace(buffer={"nodes": {}})
    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _stack_order=None,
        _layout=layout,
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: scrollbar,
            schedule_metrics_refresh=lambda: registry_calls.append("metrics_scheduled"),
            refresh_metrics_now=lambda: registry_calls.append("metrics_now"),
        ),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("sanitize"),
        reconcile_prompt_link_state=lambda **_kwargs: registry_calls.append(
            "reconcile"
        ),
        sync_prompt_editor_values_from_buffers=lambda: registry_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: registry_calls.append("links"),
        _refresh_sampler_scheduler_link_state=lambda: registry_calls.append(
            "sampler_scheduler"
        ),
        _remove_cube_widget_from_layout=lambda _widget: None,
        _build_cube_widget=lambda _alias, _state: (_ for _ in ()).throw(
            AssertionError("full projection should prefer incremental build sessions")
        ),
        _begin_build_cube_widget=lambda _alias, _state: build_session,
        _begin_projection_busy=lambda _message="Loading": "busy-token",
        _end_projection_busy=lambda _token: registry_calls.append("busy_end"),
        _build_behavior_snapshot=lambda **_kwargs: registry_calls.append("snapshot"),
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        _on_scroll_updated=lambda _value: registry_calls.append("scroll"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "visibility"
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)

    coordinator.load_all_cubes(
        [("New", cube_new)],
        cube_states={"New": cube_new},
        stack_order=["New"],
    )
    timer_queue.run_all()

    assert "finalize:projected_reveal" in registry_calls
    assert "metrics_now" not in registry_calls
    assert "prompt_values" not in registry_calls
    assert "links" not in registry_calls
    assert "visibility" not in registry_calls
    assert registry_calls[-1] == "busy_end"
    assert coordinator._composition.build_registry.record_for("New").state == "failed"


def test_projected_cube_builds_reveal_once_after_all_sections_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full projection should batch staged reveals into one layout commit."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    timer_queue = _TimerQueue()
    _patch_hidden_build_timer(monkeypatch, timer_queue)

    workflow_session_service = SimpleNamespace(active_workflow_id="workflow-a")
    panel = SimpleNamespace(
        mainwindow=SimpleNamespace(workflow_session_service=workflow_session_service),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    widget_a = _Widget("A")
    widget_b = _Widget("B")
    session_a = _BuildSession(widget_a, step_results=[False, True])
    session_b = _BuildSession(widget_b, step_results=[True])
    token_a = coordinator._composition.build_registry.start(
        alias="A",
        widget=widget_a,
        session=session_a,
        snapshot_identity=None,
        definition_identity=None,
    )
    token_b = coordinator._composition.build_registry.start(
        alias="B",
        widget=widget_b,
        session=session_b,
        snapshot_identity=None,
        definition_identity=None,
    )
    projected_builds = [
        ProjectedCubeBuild(
            cube_alias="A",
            final_widget=widget_a,
            build_session=session_a,
            started_at=0.0,
            token=token_a,
        ),
        ProjectedCubeBuild(
            cube_alias="B",
            final_widget=widget_b,
            build_session=session_b,
            started_at=0.0,
            token=token_b,
        ),
    ]
    revealed_batches: list[tuple[str, ...]] = []
    completions: list[str] = []
    cancellations: list[str] = []

    def reveal_batch(
        builds: list[object],
        *,
        workflow_id: str,
    ) -> None:
        """Record the exact reveal batch requested by the scheduler."""

        revealed_batches.append(
            tuple(getattr(build, "cube_alias") for build in builds) + (workflow_id,)
        )

    monkeypatch.setattr(
        coordinator._composition.render_reconciler,
        "reveal_projected_cube_builds",
        reveal_batch,
    )
    monkeypatch.setattr(
        coordinator._composition.render_reconciler,
        "reveal_projected_cube_build",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("single reveal path should not run")
        ),
    )

    coordinator._composition.hidden_build_scheduler.schedule_projected_cube_builds(
        projected_builds,
        on_complete=lambda: completions.append("complete"),
        on_cancel=lambda: cancellations.append("cancel"),
        workflow_id="workflow-a",
        is_current=lambda: True,
    )
    timer_queue.run_all()

    assert revealed_batches == [("A", "B", "workflow-a")]
    assert completions == ["complete"]
    assert cancellations == []
    assert coordinator._composition.build_registry.record_for("A").state == "complete"
    assert coordinator._composition.build_registry.record_for("B").state == "complete"


def test_full_projection_load_pipeline_does_not_import_coordinator_or_fluent() -> None:
    """Full projection load orchestration should stay out of the coordinator monolith."""

    imports = _imported_module_names(PIPELINE_SOURCE)
    source = PIPELINE_SOURCE.read_text(encoding="utf-8")

    assert not any(
        module == prefix or module.startswith(f"{prefix}.")
        for module in imports
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )
    assert "_coordinator" not in source
    assert "EditorFullProjectionLoadPorts(" in (
        PROJECT_ROOT
        / "substitute"
        / "presentation"
        / "editor"
        / "panel"
        / "projection_composition.py"
    ).read_text(encoding="utf-8")


def test_projection_coordinator_no_longer_defines_full_load_pipeline() -> None:
    """Moved full projection pipeline class should not return to the coordinator."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    coordinator_imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    composition_imported_names = {
        alias.name
        for node in ast.walk(ast.parse(COMPOSITION_SOURCE.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "EditorFullProjectionLoadPipeline" not in class_names
    assert "EditorFullProjectionLoadPipeline" not in coordinator_imported_names
    assert "EditorFullProjectionLoadPipeline" in composition_imported_names

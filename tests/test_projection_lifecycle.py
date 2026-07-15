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

"""Focused tests for projection lifecycle behavior."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from types import SimpleNamespace

from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild
from tests.editor_projection_test_helpers import (
    _Layout,
    _LayoutItem,
    _Widget,
)


def test_remove_cube_discards_widget_and_alias_scoped_registries() -> None:
    """Explicit cube removal should immediately clear editor projection state."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )

    removed_widget = _Widget("removed")
    kept_widget = _Widget("kept")
    removed_widgets: list[object] = []
    visibility_reasons: list[object] = []
    removed_node_link_cubes: list[str] = []

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Remove": removed_widget, "Keep": kept_widget},
        cube_sections={"Remove": removed_widget, "Keep": kept_widget},
        cube_headers={"Remove": object(), "Keep": object()},
        card_wrappers={
            ("Remove", "Node"): object(),
            ("Keep", "Node"): object(),
        },
        input_widgets_by_field_key={
            ("Remove", "Node", "field"): object(),
            ("Keep", "Node", "field"): object(),
        },
        row_widgets={
            ("Remove", "Node", "field"): object(),
            ("Keep", "Node", "field"): object(),
        },
        col_widgets={
            ("Remove", "Node", "field"): object(),
            ("Keep", "Node", "field"): object(),
        },
        _last_card_decisions={
            ("Remove", "Node"): (True, True, "shown"),
            ("Keep", "Node"): (True, True, "shown"),
        },
        _last_hidden_field_keys={
            ("Remove", "Node", "field"),
            ("Keep", "Node", "field"),
        },
        _cube_states=None,
        _stack_order=["Keep"],
        _layout=SimpleNamespace(count=lambda: 0),
        scroll=SimpleNamespace(),
        node_definition_gateway=object(),
        meta_registry=SimpleNamespace(
            remove_node_link_cube=removed_node_link_cubes.append
        ),
        _remove_cube_widget_from_layout=lambda widget: removed_widgets.append(widget),
        refresh_node_behavior_state=lambda **kwargs: visibility_reasons.append(
            kwargs.get("reason")
        ),
    )

    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    clean_signature = coordinator.current_projection_signature(
        workflow_id="",
        cube_entries=[],
        cube_states={},
        stack_order=[],
    )
    coordinator.mark_projection_clean(clean_signature)
    assert coordinator.is_projection_clean(clean_signature)

    coordinator.remove_cube("Remove")

    assert removed_widgets == [removed_widget]
    assert removed_widget.visible_changes == [False]
    assert panel.cube_widgets == {"Keep": kept_widget}
    assert panel.cube_sections == {"Keep": kept_widget}
    assert set(panel.cube_headers) == {"Keep"}
    assert ("Remove", "Node") not in panel.card_wrappers
    assert list(panel.input_widgets_by_field_key) == [("Keep", "Node", "field")]
    assert list(panel.row_widgets) == [("Keep", "Node", "field")]
    assert list(panel.col_widgets) == [("Keep", "Node", "field")]
    assert set(panel._last_card_decisions) == {("Keep", "Node")}
    assert panel._last_hidden_field_keys == {("Keep", "Node", "field")}
    assert removed_node_link_cubes == ["Remove"]
    assert visibility_reasons == ["cube_removed"]
    assert not coordinator.is_projection_clean(clean_signature)


def test_clear_layout_cancels_projection_lifecycle_state() -> None:
    """Layout clearing should close pending projection lifecycle state."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    visible_commit_mod = importlib.import_module(
        "substitute.presentation.editor.panel.visible_projection_commit"
    )

    class _EmptyLayout:
        def count(self) -> int:
            """Return an empty layout count."""

            return 0

        def takeAt(self, _index: int) -> object:
            """No layout item can be taken from an empty layout."""

            raise AssertionError("layout is empty")

    completed: list[str] = []
    cancelled: list[str] = []
    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={},
        cube_sections={},
        cube_headers={},
        card_wrappers={},
        cube_positions={},
        input_widgets_by_field_key={},
        row_widgets={},
        col_widgets={},
        node_link_widgets={},
        node_link_title_surfaces={},
        meta_registry=SimpleNamespace(),
        _cube_visibility_btns={},
        _cube_visibility_menus={},
        _cube_states={},
        _stack_order=[],
        _layout=_EmptyLayout(),
        clear_model_field_load_progress=lambda: None,
        _clear_layout_recursive=lambda _layout: None,
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    token = coordinator._composition.build_registry.start(
        alias="Cube",
        widget=object(),
        session=None,
        snapshot_identity=None,
        definition_identity=None,
    )
    coordinator._composition.projection_completions.register_pending_insert(
        workflow_id="workflow-a",
        cube_alias="Cube",
        token=token,
        completion_phase="complete",
        on_complete=lambda: completed.append("insert"),
    )
    session = coordinator._composition.active_sessions.start(
        workflow_id="workflow-a",
        cube_entries=[("Cube", object())],
    )
    coordinator._composition.projection_completions.register_projection_completion(
        session,
        workflow_id="workflow-a",
        aliases={"Cube"},
        on_complete=lambda: completed.append("projection"),
        reason="test",
    )
    pending = visible_commit_mod.PendingVisibleProjectionCommit(
        workflow_id="workflow-a",
        projection_session=session,
        projected_builds=(),
        finish_refresh=lambda: completed.append("visible"),
        cancel_refresh=cancelled.append,
        created_at=0.0,
    )
    coordinator._composition.visible_commits.store_pending_visible_projection_commit(
        pending
    )

    coordinator.clear_layout()

    assert completed == []
    assert cancelled == ["layout_cleared"]
    assert (
        coordinator._composition.projection_completions.pending_insert_completions == {}
    )
    assert coordinator._composition.active_sessions.active_session is None
    assert coordinator._composition.build_registry.record_for("Cube") is None


def test_cancelled_projected_build_clears_alias_scoped_registries() -> None:
    """Unrevealed staged-build cancellation should not leave stale child widgets."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )

    cancelled_widget = _Widget("cancelled")
    kept_widget = _Widget("kept")
    removed_node_link_cubes: list[str] = []
    panel = SimpleNamespace(
        cube_widgets={"Keep": kept_widget},
        cube_sections={"Keep": kept_widget},
        cube_headers={"Keep": object()},
        card_wrappers={
            ("Cancel", "Node"): object(),
            ("Keep", "Node"): object(),
        },
        input_widgets_by_field_key={
            ("Cancel", "Node", "field"): object(),
            ("Keep", "Node", "field"): object(),
        },
        row_widgets={
            ("Cancel", "Node", "field"): object(),
            ("Keep", "Node", "field"): object(),
        },
        col_widgets={
            ("Cancel", "Node", "field"): object(),
            ("Keep", "Node", "field"): object(),
        },
        _last_card_decisions={
            ("Cancel", "Node"): (True, True, "shown"),
            ("Keep", "Node"): (True, True, "shown"),
        },
        _last_hidden_field_keys={
            ("Cancel", "Node", "field"),
            ("Keep", "Node", "field"),
        },
        meta_registry=SimpleNamespace(
            remove_node_link_cube=removed_node_link_cubes.append
        ),
    )
    coordinator = mod.EditorPanelProjectionCoordinator(panel)
    token = coordinator._composition.build_registry.start(
        alias="Cancel",
        widget=cancelled_widget,
        session=None,
        snapshot_identity=None,
        definition_identity=None,
    )
    projected_build = ProjectedCubeBuild(
        cube_alias="Cancel",
        final_widget=cancelled_widget,
        build_session=object(),
        started_at=0.0,
        token=token,
    )

    coordinator._composition.projected_widget_builder.discard_cancelled_projected_build(
        projected_build,
        workflow_id="workflow-a",
        reason="test_cancelled",
    )

    assert panel.cube_widgets == {"Keep": kept_widget}
    assert panel.cube_sections == {"Keep": kept_widget}
    assert ("Cancel", "Node") not in panel.card_wrappers
    assert list(panel.input_widgets_by_field_key) == [("Keep", "Node", "field")]
    assert list(panel.row_widgets) == [("Keep", "Node", "field")]
    assert list(panel.col_widgets) == [("Keep", "Node", "field")]
    assert set(panel._last_card_decisions) == {("Keep", "Node")}
    assert panel._last_hidden_field_keys == {("Keep", "Node", "field")}
    assert removed_node_link_cubes == ["Cancel"]
    assert cancelled_widget.parents == [None]
    assert cancelled_widget.deleted == 1


def test_reorder_cube_widgets_reattaches_widgets_in_stack_order() -> None:
    """Coordinator reorder should clear the layout and add widgets in stack order."""

    mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )

    widget_a = _Widget()
    widget_b = _Widget()
    layout = _Layout(
        [
            _LayoutItem(widget=widget_a),
            _LayoutItem(spacer=True),
            _LayoutItem(widget=widget_b),
        ]
    )
    registry_calls: list[str] = []

    def _record_state() -> None:
        registry_calls.append("state")

    def _record_widgets() -> None:
        registry_calls.append("widgets")

    def _record_refresh(**kwargs: object) -> None:
        registry_calls.append("recompute")
        registry_calls.append(str(kwargs["reason"]))

    panel = SimpleNamespace(
        CUBE_SPACING=8,
        _stack_order=["B", "A"],
        cube_widgets={"A": widget_a, "B": widget_b},
        cube_sections={"A": widget_a, "B": widget_b},
        cube_headers={},
        card_wrappers={},
        _cube_states=None,
        _layout=layout,
        scroll=SimpleNamespace(verticalScrollBar=lambda: None),
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: registry_calls.append("prompt_state"),
        reconcile_prompt_link_state=lambda **_kwargs: None,
        _refresh_sampler_scheduler_link_state=_record_state,
        _refresh_link_widgets=_record_widgets,
        refresh_node_behavior_state=_record_refresh,
    )

    mod.EditorPanelProjectionCoordinator(panel).reorder_cube_widgets()

    assert layout.added == [
        ("spacing", 8),
        ("widget", widget_b),
        ("spacing", 8),
        ("widget", widget_a),
    ]
    assert widget_a.parents == [None]
    assert widget_b.parents == [None]
    assert registry_calls == [
        "prompt_state",
        "state",
        "widgets",
        "recompute",
        "stack_reordered",
    ]


def test_projection_coordinator_no_longer_defines_lifecycle_wrappers() -> None:
    """Lifecycle pass-through methods should not return to the coordinator."""

    module_path = (
        Path(__file__).resolve().parents[1]
        / "substitute"
        / "presentation"
        / "editor"
        / "panel"
        / "projection_coordinator.py"
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    assert "_discard_cube_widget" not in coordinator_methods
    assert "_clear_alias_scoped_panel_registries" not in coordinator_methods
    assert "_clear_layout" not in coordinator_methods
    assert "_remove_closed_aliases" not in coordinator_methods
    assert "_refresh_visibility" not in coordinator_methods

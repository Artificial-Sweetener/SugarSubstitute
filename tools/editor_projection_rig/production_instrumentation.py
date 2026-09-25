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

"""Instrument production editor projection owners for performance traces."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.presentation.editor.panel.cube_section_build_session import (
    CubeSectionBuildSession,
)
from substitute.presentation.editor.panel.full_projection_load_pipeline import (
    EditorFullProjectionLoadPipeline,
)
from substitute.presentation.editor.panel.hidden_build_scheduler import (
    HiddenBuildScheduler,
)
from substitute.presentation.editor.panel.node_card_builder import NodeCardBuilder
from substitute.presentation.editor.panel.node_card import (
    field_factory_adapter as field_factory_adapter_module,
)
from substitute.presentation.editor.panel.node_card import (
    title_composer as title_composer_module,
)
from substitute.presentation.editor.panel.node_card.body_composer import (
    NodeCardBodyComposer,
)
from substitute.presentation.editor.panel.node_card.field_realizer import (
    NodeCardFieldRealizer,
)
from substitute.presentation.editor.panel.node_card.title_composer import (
    NodeCardTitleComposer,
)
from substitute.presentation.editor.panel.projection_coordinator import (
    EditorPanelProjectionCoordinator,
)
from substitute.presentation.editor.panel.projection_lifecycle import (
    EditorProjectionLifecyclePipeline,
)
from substitute.presentation.editor.panel.projection_preparation import (
    EditorProjectionPreparationController,
)
from substitute.presentation.editor.panel.rendering.render_reconciler import (
    EditorPanelRenderReconciler,
)
from substitute.presentation.editor.panel.widgets import field_row as field_row_view
from substitute.presentation.editor.panel.widgets import (
    field_row_geometry as field_row_geometry_view,
)

from .trace_events import ProjectionTraceRecorder

MethodDetailReader = Callable[
    [Any, tuple[Any, ...], dict[str, Any]],
    dict[str, Any],
]
FunctionDetailReader = Callable[[tuple[Any, ...], dict[str, Any]], dict[str, Any]]


@contextmanager
def instrument_projection(recorder: ProjectionTraceRecorder) -> Iterator[None]:
    """Temporarily wrap production methods with timing/counter instrumentation."""

    patches: list[tuple[Any, str, object]] = []

    def patch_attribute(
        owner: Any,
        attribute_name: str,
        replacement: object,
    ) -> None:
        """Patch one attribute and remember how to restore it."""

        original = getattr(owner, attribute_name)
        patches.append((owner, attribute_name, original))
        setattr(owner, attribute_name, replacement)

    def patch_method(
        owner: type[Any],
        method_name: str,
        event_name: str,
        counter_name: str,
        detail_reader: MethodDetailReader | None = None,
    ) -> None:
        """Patch one method and remember how to restore it."""

        original = getattr(owner, method_name)

        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            """Record one production method call and delegate to the original."""

            recorder.increment(counter_name)
            details = detail_reader(self, args, kwargs) if detail_reader else {}
            with recorder.timed(event_name, **details):
                return original(self, *args, **kwargs)

        patch_attribute(owner, method_name, wrapped)

    def patch_function(
        owner: Any,
        function_name: str,
        event_name: str,
        counter_name: str,
        detail_reader: FunctionDetailReader | None = None,
    ) -> None:
        """Patch one module-level function and remember how to restore it."""

        original = getattr(owner, function_name)

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            """Record one production function call and delegate to the original."""

            recorder.increment(counter_name)
            details = detail_reader(args, kwargs) if detail_reader else {}
            with recorder.timed(event_name, **details):
                return original(*args, **kwargs)

        patch_attribute(owner, function_name, wrapped)

    patch_method(
        EditorPanelProjectionCoordinator,
        "load_all_cubes",
        "production.editor.load_all_cubes",
        "projection.load_all_cubes.calls",
        lambda _self, args, _kwargs: {"cube_entries": len(args[0]) if args else 0},
    )
    patch_method(
        EditorProjectionPreparationController,
        "prepare_projection",
        "production.editor.prepare_projection",
        "projection.prepare_projection.calls",
    )
    patch_method(
        EditorFullProjectionLoadPipeline,
        "_build_ordered_widgets",
        "production.editor.build_ordered_widgets",
        "projection.build_ordered_widgets.calls",
    )
    patch_method(
        EditorPanelRenderReconciler,
        "repopulate_layout",
        "production.editor.repopulate_layout",
        "projection.repopulate_layout.calls",
        lambda _self, args, _kwargs: {"ordered_widgets": len(args[0]) if args else 0},
    )
    patch_method(
        HiddenBuildScheduler,
        "schedule_projected_cube_builds",
        "production.editor.schedule_projected_cube_builds",
        "projection.schedule_projected_cube_builds.calls",
        lambda _self, args, _kwargs: {"projected_builds": len(args[0]) if args else 0},
    )
    patch_method(
        EditorPanelRenderReconciler,
        "reveal_projected_cube_build",
        "production.editor.reveal_projected_cube_build",
        "projection.reveal_projected_cube_build.calls",
        lambda _self, args, _kwargs: {
            "cube_alias": getattr(args[0], "cube_alias", "") if args else ""
        },
    )
    patch_method(
        EditorPanelRenderReconciler,
        "reveal_projected_cube_builds",
        "production.editor.reveal_projected_cube_builds",
        "projection.reveal_projected_cube_builds.calls",
        lambda _self, args, _kwargs: {"projected_builds": len(args[0]) if args else 0},
    )
    patch_method(
        EditorProjectionLifecyclePipeline,
        "refresh_visibility",
        "production.editor.refresh_visibility",
        "projection.refresh_visibility.calls",
    )
    patch_method(
        EditorPanelProjectionCoordinator,
        "begin_build_cube_widget",
        "production.cube.begin_build_cube_widget",
        "cube.begin_build_cube_widget.calls",
        lambda _self, args, _kwargs: {"cube_alias": str(args[0]) if args else ""},
    )
    patch_method(
        CubeSectionBuildSession,
        "step",
        "production.cube.build_step",
        "cube.build_step.calls",
        lambda self, _args, _kwargs: {
            "cube_alias": getattr(self, "_route_key", ""),
            "next_index": getattr(self, "_next_index", -1),
        },
    )
    patch_method(
        CubeSectionBuildSession,
        "finish",
        "production.cube.finish",
        "cube.finish.calls",
        lambda self, _args, _kwargs: {
            "cube_alias": getattr(self, "_route_key", ""),
            "node_count": len(getattr(self, "_node_order", ())),
        },
    )
    patch_method(
        NodeCardBuilder,
        "build_node_card",
        "production.node_card.build_node_card",
        "node_card.build.calls",
        lambda _self, _args, kwargs: {
            "cube_alias": kwargs.get("alias", ""),
            "node_name": kwargs.get("node_name", ""),
            "node_class": kwargs.get("node_type", ""),
            "field_count": len(kwargs.get("field_specs", {})),
        },
    )
    patch_method(
        NodeCardTitleComposer,
        "create",
        "production.node_card.create_title_row",
        "node_card.title_row.calls",
        lambda _self, _args, kwargs: {
            "node_name": kwargs.get("node_name", ""),
            "node_class": kwargs.get("node_type", ""),
            "field_count": len(kwargs.get("field_specs", {})),
        },
    )
    patch_method(
        NodeCardBodyComposer,
        "add_input_row",
        "production.node_card.add_input_row",
        "node_card.input_row.calls",
        lambda _self, _args, kwargs: {
            "label": kwargs.get("label", ""),
            "widget_type": type(kwargs.get("widget")).__name__,
        },
    )
    patch_method(
        NodeCardBodyComposer,
        "add_n_column_row",
        "production.node_card.add_n_column_row",
        "node_card.n_column_row.calls",
        lambda _self, _args, kwargs: {
            "field_count": len(kwargs.get("fields", ())),
            "node_name": kwargs.get("node_name", ""),
        },
    )
    patch_method(
        NodeCardFieldRealizer,
        "realize",
        "production.field.create_field_for_key",
        "field.create.calls",
        lambda _self, _args, kwargs: _field_spec_details(
            kwargs.get("field_spec"),
            cube_alias=kwargs.get("alias", ""),
            node_name=kwargs.get("node_name", ""),
        ),
    )
    patch_function(
        field_factory_adapter_module,
        "build_widget_for_field_spec",
        "production.field.factory",
        "field.factory.calls",
        lambda _args, kwargs: _field_spec_details(kwargs.get("field_spec")),
    )
    patch_function(
        field_row_geometry_view,
        "_apply_field_row_divider_style",
        "production.field_row.apply_divider_style",
        "field_row.divider_style.calls",
        lambda args, _kwargs: {"widget_type": type(args[0]).__name__ if args else ""},
    )
    patch_function(
        field_row_view,
        "bind_fluent_tooltip",
        "production.field_row.bind_tooltip",
        "field_row.bind_tooltip.calls",
        lambda args, _kwargs: {"target_count": max(0, len(args) - 2)},
    )
    patch_function(
        title_composer_module,
        "bind_fluent_tooltip",
        "production.node_card.bind_tooltip",
        "node_card.bind_tooltip.calls",
        lambda args, _kwargs: {"target_count": max(0, len(args) - 2)},
    )
    patch_method(
        NodeBehaviorService,
        "build_snapshot",
        "production.behavior.build_snapshot",
        "behavior.build_snapshot.calls",
        lambda _self, _args, kwargs: {
            "callsite": _behavior_snapshot_callsite(),
            "cube_count": len(kwargs.get("cube_states", {})),
            "stack_order_count": len(kwargs.get("stack_order", ())),
            "workflow_override_count": len(kwargs.get("workflow_overrides") or {}),
            "search_hidden_key_count": len(kwargs.get("search_hidden_keys") or ()),
            "override_hidden_field_key_count": len(
                kwargs.get("override_hidden_field_keys") or ()
            ),
            "node_search_text": str(kwargs.get("node_search_text") or ""),
            "search_matching_node_count": len(
                kwargs.get("search_matching_nodes") or ()
            ),
        },
    )
    try:
        yield
    finally:
        for owner, method_name, original in reversed(patches):
            setattr(owner, method_name, original)


def _field_spec_details(
    field_spec: object,
    *,
    cube_alias: object = "",
    node_name: object = "",
) -> dict[str, Any]:
    """Return trace details for one resolved field spec."""

    field_behavior = getattr(field_spec, "field_behavior", None)
    presentation = getattr(field_behavior, "presentation", None)
    return {
        "cube_alias": str(cube_alias or getattr(field_spec, "cube_alias", "") or ""),
        "node_name": str(node_name or getattr(field_spec, "node_name", "") or ""),
        "node_class": str(getattr(field_spec, "class_type", "") or ""),
        "field_key": str(getattr(field_spec, "field_key", "") or ""),
        "field_type": str(getattr(field_spec, "field_type", "") or ""),
        "presentation": str(getattr(presentation, "value", presentation) or ""),
        "value_source": str(
            getattr(getattr(field_spec, "value_source", None), "value", "") or ""
        ),
    }


def _behavior_snapshot_callsite() -> str:
    """Return the nearest application frame that requested a behavior snapshot."""

    for frame in inspect.stack()[2:12]:
        path = Path(frame.filename)
        if "substitute" not in path.parts:
            continue
        if path.name == "behavior_service.py":
            continue
        return f"{path.name}:{frame.function}:{frame.lineno}"
    return ""

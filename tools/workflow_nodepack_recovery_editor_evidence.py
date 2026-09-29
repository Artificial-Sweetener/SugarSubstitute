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

"""Render exact workflow editor states as deterministic qualification evidence."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from substitute.domain.comfy_workflow import DirectWorkflowState
from substitute.domain.workflow import WorkflowState
from substitute.presentation.shell.main_window_editor_surface_adapter import (
    MainWindowEditorSurfaceAdapter,
)
from tools.editor_panel_baseline.rendering import (
    save_editor_panel_host,
    settle_editor_panel_layout,
)
from tools.editor_projection_rig.production_mount import (
    build_editor_panel,
    build_trace_shell,
)
from tools.editor_projection_rig.qt_harness import (
    create_hidden_host,
    drain_qt_events,
    drain_until,
)
from tools.editor_projection_rig.trace_events import ProjectionTraceRecorder

_HOST_SIZE = (1440, 1000)
_BACKGROUND = QColor("#202020")


def render_editor(
    *,
    workflow_id: str,
    document: DirectWorkflowState,
    definitions: Mapping[str, object],
    path: Path,
) -> dict[str, object]:
    """Render a production editor projection and return degraded-card evidence."""

    workflow = WorkflowState(direct_workflow=document)
    host = create_hidden_host(show_window=True)
    host.resize(*_HOST_SIZE)
    host.setStyleSheet("background: #202020;")
    panel = build_editor_panel(
        host=host,
        workflow_id=workflow_id,
        definitions=definitions,
    )
    recorder = ProjectionTraceRecorder()
    trace_shell = build_trace_shell(
        workflow_id=workflow_id,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
    )
    panel.mainwindow = trace_shell.shell
    try:
        result = MainWindowEditorSurfaceAdapter(
            trace_shell.shell
        ).refresh_editor_surface(
            workflow_id,
            force=True,
            on_complete=lambda _result: setattr(
                trace_shell,
                "projection_complete",
                True,
            ),
        )
        if result.error:
            raise RuntimeError(f"Editor projection failed: {result.error}")
        drain_until(lambda: trace_shell.projection_complete, max_turns=1_000)
        settle_editor_panel_layout(host, panel)
        scroll = panel.scroll
        scrollbar = scroll.verticalScrollBar()
        scroll_positions = {
            "top": 0,
            "middle": max(0, scrollbar.maximum() // 2),
            "bottom": max(0, scrollbar.maximum()),
        }
        render_paths: dict[str, str] = {}
        rendered_scroll_values: dict[str, int] = {}
        rendered_content_ranges: dict[str, list[int]] = {}
        for position, value in scroll_positions.items():
            scrollbar.setValue(value)
            drain_qt_events(20)
            render_path = (
                path
                if position == "top"
                else path.with_name(f"{path.stem}-{position}{path.suffix}")
            )
            save_editor_panel_host(host, render_path, background=_BACKGROUND)
            render_paths[position] = str(render_path.resolve())
            rendered_scroll_values[position] = scrollbar.value()
            rendered_content_ranges[position] = [
                int(scroll.visible_content_top()),
                int(scroll.visible_content_bottom()),
            ]
        snapshot = panel.current_behavior_snapshot()
        degraded_by_alias = (
            snapshot.degraded_nodes_by_alias if snapshot is not None else {}
        )
        degraded_nodes: list[dict[str, object]] = []
        scroll_content = scroll.widget()
        if scroll_content is None:
            raise RuntimeError("Editor scroll surface has no content widget.")
        for alias, nodes in sorted(degraded_by_alias.items()):
            for node_name, node in sorted(nodes.items()):
                card = panel.card_wrappers.get((alias, node_name))
                if (
                    not isinstance(card, QWidget)
                    or card.objectName() != "DegradedNodeCard"
                ):
                    raise RuntimeError(
                        f"Missing degraded card widget for {alias}/{node_name}."
                    )
                content_position = card.mapTo(scroll_content, QPoint(0, 0))
                content_top = content_position.y()
                content_bottom = content_top + card.height()
                captured = any(
                    content_top < visible_bottom and content_bottom > visible_top
                    for visible_top, visible_bottom in rendered_content_ranges.values()
                )
                if not card.isVisible() or card.isHidden():
                    raise RuntimeError(
                        f"Degraded card is not visible for {alias}/{node_name}."
                    )
                if not captured:
                    raise RuntimeError(
                        f"No qualification render contains {alias}/{node_name}."
                    )
                degraded_nodes.append(
                    {
                        "cube_alias": alias,
                        "node_name": node_name,
                        "class_type": node.class_type,
                        "title": node.title,
                        "missing_definition_classes": list(
                            node.missing_definition_classes
                        ),
                        "missing_fields": list(node.missing_fields),
                        "widget_visible": card.isVisible(),
                        "widget_hidden": card.isHidden(),
                        "widget_geometry": [
                            card.x(),
                            card.y(),
                            card.width(),
                            card.height(),
                        ],
                        "widget_size_hint": [
                            card.sizeHint().width(),
                            card.sizeHint().height(),
                        ],
                        "content_position": [
                            content_position.x(),
                            content_position.y(),
                        ],
                        "captured": captured,
                    }
                )
        degraded_cards = panel.findChildren(QWidget, "DegradedNodeCard")
        if len(degraded_cards) != len(degraded_nodes):
            raise RuntimeError("Degraded card registry and rendered widgets disagree.")
        return {
            "degraded_card_count": len(degraded_cards),
            "degraded_nodes": degraded_nodes,
            "degraded_definition_classes": [
                class_type
                for node in degraded_nodes
                for class_type in node["missing_definition_classes"]
                if isinstance(class_type, str)
            ],
            "render_paths": render_paths,
            "scroll_maximum": scrollbar.maximum(),
            "scroll_values": rendered_scroll_values,
            "visible_content_ranges": rendered_content_ranges,
            "stack_order": list(workflow.stack_order),
            "interactive": host.isEnabled() and panel.isEnabled(),
        }
    finally:
        host.close()
        host.deleteLater()
        drain_qt_events(25)


__all__ = ["render_editor"]

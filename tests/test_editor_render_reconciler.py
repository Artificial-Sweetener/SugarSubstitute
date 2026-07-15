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

"""Tests for editor render reconciliation helpers."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import cast

from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from substitute.presentation.editor.panel.rendering.render_reconciler import (
    EditorPanelRenderReconciler,
    ProjectedCubeBuildProtocol,
    _LayoutLike,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COORDINATOR_SOURCE = (
    PROJECT_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "panel"
    / "projection_coordinator.py"
)


def _ensure_qapp() -> QApplication:
    """Return the active Qt application for layout reconciliation tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def test_cube_layout_matches_order_ignores_spacers() -> None:
    """The reconciler should compare cube widget order without spacer noise."""

    _ensure_qapp()
    host = QWidget()
    layout = QVBoxLayout(host)
    first = QWidget(host)
    second = QWidget(host)
    layout.addSpacing(12)
    layout.addWidget(first)
    layout.addSpacing(12)
    layout.addWidget(second)

    assert EditorPanelRenderReconciler.cube_layout_matches_order(
        cast(_LayoutLike, layout),
        [first, second],
    )
    assert not EditorPanelRenderReconciler.cube_layout_matches_order(
        cast(_LayoutLike, layout),
        [second, first],
    )


class _Signal:
    """Record scroll signal connections for render reconciliation tests."""

    def __init__(self) -> None:
        """Initialize an empty connection log."""

        self.connected: list[object] = []
        self.disconnects = 0

    def connect(self, callback: object) -> None:
        """Record one callback connection."""

        self.connected.append(callback)

    def disconnect(self, _callback: object) -> None:
        """Record one attempted disconnect."""

        self.disconnects += 1


class _LayoutItem:
    """Represent one fake layout item."""

    def __init__(self, widget: object | None) -> None:
        """Store the item widget."""

        self._widget = widget

    def widget(self) -> object | None:
        """Return the item widget."""

        return self._widget

    def layout(self) -> object | None:
        """Return no nested layout."""

        return None


class _Layout:
    """Fake root layout used by panel render reconciliation tests."""

    def __init__(self, widgets: list[object]) -> None:
        """Initialize layout items around the supplied widgets."""

        self.items = [_LayoutItem(widget) for widget in widgets]
        self.added: list[tuple[str, object]] = []
        self.activated = 0

    def count(self) -> int:
        """Return the current item count."""

        return len(self.items)

    def takeAt(self, index: int) -> _LayoutItem:
        """Remove and return one item."""

        return self.items.pop(index)

    def itemAt(self, index: int) -> _LayoutItem | None:
        """Return one item without removing it."""

        try:
            return self.items[index]
        except IndexError:
            return None

    def addSpacing(self, spacing: int) -> None:
        """Record one spacing item."""

        self.added.append(("spacing", spacing))
        self.items.append(_LayoutItem(None))

    def addWidget(self, widget: object) -> None:
        """Record one widget item."""

        self.added.append(("widget", widget))
        self.items.append(_LayoutItem(widget))

    def activate(self) -> None:
        """Record layout activation."""

        self.activated += 1


class _Widget:
    """Fake widget with reveal/finalization hooks."""

    def __init__(self, name: str) -> None:
        """Initialize call logs."""

        self.name = name
        self.parents: list[object | None] = []
        self.deleted = 0
        self.visible: list[bool] = []
        self.updates: list[bool] = []
        self.finalized: list[str] = []
        self.repaint_requests = 0

    def setParent(self, parent: object | None) -> None:
        """Record parent detachment."""

        self.parents.append(parent)

    def deleteLater(self) -> None:
        """Record deferred deletion."""

        self.deleted += 1

    def show(self) -> None:
        """Record reveal visibility."""

        self.visible.append(True)

    def setUpdatesEnabled(self, enabled: bool) -> None:
        """Record update suppression changes."""

        self.updates.append(enabled)

    def update(self) -> None:
        """Record repaint requests."""

        self.repaint_requests += 1

    def finalize_layout_for_reveal(self, *, reason: str) -> None:
        """Record reveal finalization."""

        self.finalized.append(reason)


def test_panel_render_reconciler_reveals_builds_and_cleans_stale_widgets() -> None:
    """Panel render reconciliation should own layout replacement and reveal hooks."""

    managed = _Widget("managed")
    stale = _Widget("stale")
    final = _Widget("final")
    signal = _Signal()
    scroll_calls: list[str] = []
    panel = SimpleNamespace(
        CUBE_SPACING=8,
        cube_widgets={"Managed": managed},
        cube_sections={},
        _stack_order=["Final"],
        _layout=_Layout([managed, stale]),
        scroll=SimpleNamespace(
            verticalScrollBar=lambda: SimpleNamespace(
                valueChanged=signal,
                value=lambda: 4,
            ),
            schedule_metrics_refresh=lambda: scroll_calls.append("scheduled"),
        ),
        _on_scroll_updated=lambda value: scroll_calls.append(f"scroll:{value}"),
    )
    build = cast(
        ProjectedCubeBuildProtocol,
        SimpleNamespace(
            cube_alias="Final",
            final_widget=final,
            build_session=object(),
            started_at=0.0,
            token=object(),
        ),
    )

    EditorPanelRenderReconciler(panel).reveal_projected_cube_builds(
        (build,),
        workflow_id="workflow",
    )

    assert panel.cube_widgets == {"Managed": managed, "Final": final}
    assert panel.cube_sections == {"Final": final}
    assert managed.parents == [None]
    assert stale.deleted == 1
    assert panel._layout.added[-2:] == [("spacing", 8), ("widget", final)]
    assert final.visible == [True]
    assert final.updates == [True]
    assert final.finalized == ["projected_reveal"]
    assert scroll_calls == ["scroll:4", "scheduled"]


def test_projection_coordinator_no_longer_defines_render_reconciler_wrappers() -> None:
    """Render reconciliation methods should not return to the coordinator facade."""

    tree = ast.parse(COORDINATOR_SOURCE.read_text(encoding="utf-8"))
    class_methods: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_methods[node.name] = {
                child.name
                for child in node.body
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
            }

    coordinator_methods = class_methods["EditorPanelProjectionCoordinator"]
    removed_wrappers = {
        "_reveal_projected_cube_builds",
        "_reveal_projected_cube_build",
        "_log_projected_cube_revealed",
        "_finalize_cube_widget_for_reveal",
        "_schedule_scroll_metrics_refresh",
    }
    assert coordinator_methods.isdisjoint(removed_wrappers)

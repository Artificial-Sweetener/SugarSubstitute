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

"""Reconcile visible editor panel cube widgets with prepared projection results."""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from typing import Protocol, cast

from PySide6.QtWidgets import QWidget

from substitute.shared.logging.logger import (
    elapsed_ms_since,
    get_logger,
    log_debug,
    log_info,
    log_warning,
)

from ..projection_observability import log_panel_projection_event

_LOGGER = get_logger("presentation.editor.panel.rendering.render_reconciler")
_SLOW_PROJECTED_CUBE_BUILD_MS = 1000.0


class ProjectedCubeBuildProtocol(Protocol):
    """Describe a completed hidden cube build ready for visible publication."""

    @property
    def cube_alias(self) -> str:
        """Return the cube alias represented by the projected build."""
        ...

    @property
    def final_widget(self) -> object:
        """Return the widget ready to publish into the visible layout."""
        ...

    @property
    def build_session(self) -> object:
        """Return the build session that produced the widget."""
        ...

    @property
    def started_at(self) -> float:
        """Return the build start time used for reveal timing logs."""
        ...

    @property
    def token(self) -> object:
        """Return the build-registry token for this projected build."""
        ...

    @property
    def build_elapsed_ms(self) -> float | None:
        """Return the elapsed build work measured when the session completed."""
        ...

    @property
    def completed_at(self) -> float | None:
        """Return when the build session completed before visible publication."""
        ...


class _LayoutItemLike(Protocol):
    """Describe layout-item access used during render reconciliation."""

    def widget(self) -> object | None:
        """Return the contained widget when the item stores one."""

    def layout(self) -> object | None:
        """Return the nested layout when the item stores one."""


class _LayoutLike(Protocol):
    """Describe layout operations used to replace cube-section widgets."""

    def count(self) -> int:
        """Return number of items currently tracked by the layout."""

    def takeAt(self, index: int) -> _LayoutItemLike:
        """Remove and return one layout item."""

    def itemAt(self, index: int) -> _LayoutItemLike | None:
        """Return one layout item without removing it."""

    def addSpacing(self, spacing: int) -> None:
        """Append one spacing item to the layout."""

    def addWidget(self, widget: object) -> None:
        """Append one widget to the layout."""


class EditorPanelRenderReconciler:
    """Own visible cube-section layout mutation and reveal finalization."""

    def __init__(self, panel: object) -> None:
        """Store the panel whose root cube layout will be reconciled."""

        self._panel = panel

    @staticmethod
    def cube_layout_matches_order(
        layout: _LayoutLike,
        ordered_widgets: Sequence[object],
    ) -> bool:
        """Return whether the layout already contains the requested cube order."""

        current_widgets = _widgets_in_layout(layout)
        return current_widgets == [widget for widget in ordered_widgets]

    def clear_layout(self) -> None:
        """Remove all widgets and spacers from the main cube layout."""

        panel = self._panel
        layout = cast(_LayoutLike, getattr(panel, "_layout"))
        for index in reversed(range(layout.count())):
            item = layout.takeAt(index)
            widget = item.widget()
            if widget is not None:
                _detach_widget(widget)

    def repopulate_layout(
        self,
        ordered_widgets: Sequence[tuple[str, object]],
    ) -> None:
        """Replace root editor layout contents with managed cube sections."""

        panel = self._panel
        layout = cast(_LayoutLike, getattr(panel, "_layout"))
        cube_widgets = cast(dict[str, object], getattr(panel, "cube_widgets"))
        managed_widgets = set(cube_widgets.values())
        requested_widgets = [cube_widget for _route_key, cube_widget in ordered_widgets]
        if self.cube_layout_matches_order(layout, requested_widgets):
            return
        update_hosts = _repopulate_update_hosts(panel)
        _set_widgets_updates_enabled(update_hosts, False)
        try:
            while layout.count():
                item = layout.takeAt(0)
                self._dispose_removed_layout_item(
                    item,
                    managed_widgets=managed_widgets,
                )

            for _route_key, cube_widget in ordered_widgets:
                self.append_cube_widget_to_layout(cube_widget)
            _activate_layout(layout)
        finally:
            _set_widgets_updates_enabled(update_hosts, True)
            _request_widget_updates(update_hosts)

    def append_cube_widget_to_layout(self, cube_widget: object) -> None:
        """Append one cube section with the editor's standard leading gap."""

        panel = self._panel
        layout = cast(_LayoutLike, getattr(panel, "_layout"))
        layout.addSpacing(cast(int, getattr(panel, "CUBE_SPACING")))
        layout.addWidget(cube_widget)

    def refresh_scroll_tracking(
        self,
        ordered_widgets: Sequence[tuple[str, object]],
    ) -> None:
        """Refresh heading/widget mappings and scrollbar-driven selection tracking."""

        panel = self._panel
        cube_sections = cast(dict[str, object], getattr(panel, "cube_sections"))
        cube_sections.clear()
        for route_key, cube_widget in ordered_widgets:
            cube_sections[route_key] = cube_widget

        scroll = getattr(panel, "scroll")
        on_scroll_updated = getattr(panel, "_on_scroll_updated")
        scrollbar = scroll.verticalScrollBar()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            try:
                scrollbar.valueChanged.disconnect(on_scroll_updated)
            except (TypeError, RuntimeError):
                pass
        scrollbar.valueChanged.connect(on_scroll_updated)
        on_scroll_updated(scrollbar.value())

    def reconcile_ordered_widgets(
        self,
        ordered_widgets: Sequence[tuple[str, object]],
    ) -> None:
        """Attach ordered cube widgets and refresh scroll tracking in one boundary."""

        self.repopulate_layout(ordered_widgets)
        self.refresh_scroll_tracking(ordered_widgets)

    def reveal_projected_cube_builds(
        self,
        projected_builds: Sequence[ProjectedCubeBuildProtocol],
        *,
        workflow_id: str,
    ) -> None:
        """Swap completed projected cube sections into the visible layout once."""

        panel = self._panel
        cube_widgets = cast(dict[str, object], getattr(panel, "cube_widgets"))
        cube_sections = cast(dict[str, object], getattr(panel, "cube_sections"))
        for projected_build in projected_builds:
            cube_widgets[projected_build.cube_alias] = projected_build.final_widget
            cube_sections[projected_build.cube_alias] = projected_build.final_widget

        ordered_widgets = [
            (alias, cube_widgets[alias])
            for alias in (getattr(panel, "_stack_order") or [])
            if alias in cube_widgets
        ]
        self.repopulate_layout(ordered_widgets)
        for projected_build in projected_builds:
            _show_projected_widget_for_reveal(projected_build.final_widget)
        self.refresh_scroll_tracking(ordered_widgets)
        for projected_build in projected_builds:
            self.finalize_cube_widget_for_reveal(
                projected_build.cube_alias,
                projected_build.final_widget,
                reason="projected_reveal",
                workflow_id=workflow_id,
            )
            self.log_projected_cube_revealed(
                projected_build,
                workflow_id=workflow_id,
            )
            _finish_projected_widget_reveal(projected_build.final_widget)

    def reveal_projected_cube_build(
        self,
        projected_build: ProjectedCubeBuildProtocol,
        *,
        workflow_id: str,
    ) -> None:
        """Swap one completed projected cube section into the visible layout."""

        self.reveal_projected_cube_builds(
            (projected_build,),
            workflow_id=workflow_id,
        )

    def finalize_cube_widget_for_reveal(
        self,
        cube_alias: str,
        cube_widget: object,
        *,
        reason: str,
        workflow_id: str,
    ) -> None:
        """Settle one cube section and coalesce editor scroll metric refresh."""

        finalize = getattr(cube_widget, "finalize_layout_for_reveal", None)
        if callable(finalize):
            finalize(reason=reason)
        self.schedule_scroll_metrics_refresh(
            cube_alias=cube_alias,
            reason=reason,
            workflow_id=workflow_id,
        )

    def schedule_scroll_metrics_refresh(
        self,
        *,
        cube_alias: str,
        reason: str,
        workflow_id: str,
    ) -> None:
        """Coalesce scroll metrics after reveal without blocking cube insertion."""

        schedule_refresh = getattr(
            getattr(self._panel, "scroll"),
            "schedule_metrics_refresh",
            None,
        )
        if callable(schedule_refresh):
            schedule_refresh()
            log_debug(
                _LOGGER,
                "Scheduled editor scroll metrics after cube-section finalization",
                workflow_id=workflow_id,
                cube_alias=cube_alias,
                reason=reason,
                refresh_mode="scheduled",
            )
            return
        refresh_metrics = getattr(
            getattr(self._panel, "scroll"),
            "refresh_metrics_now",
            None,
        )
        if not callable(refresh_metrics):
            return
        refresh_metrics()
        log_debug(
            _LOGGER,
            "Refreshed editor scroll metrics after cube-section finalization",
            workflow_id=workflow_id,
            cube_alias=cube_alias,
            reason=reason,
            refresh_mode="synchronous_fallback",
        )

    def log_projected_cube_revealed(
        self,
        projected_build: ProjectedCubeBuildProtocol,
        *,
        workflow_id: str,
    ) -> None:
        """Log completion timing for one projected cube section reveal."""

        build_elapsed_ms = getattr(projected_build, "build_elapsed_ms", None)
        elapsed_ms = (
            build_elapsed_ms
            if isinstance(build_elapsed_ms, float)
            else elapsed_ms_since(projected_build.started_at)
        )
        completed_at = getattr(projected_build, "completed_at", None)
        reveal_wait_elapsed_ms = (
            elapsed_ms_since(completed_at) if isinstance(completed_at, float) else 0.0
        )
        log_context = {
            "cube_alias": projected_build.cube_alias,
            "elapsed_ms": f"{elapsed_ms:.3f}",
            "build_elapsed_ms": f"{elapsed_ms:.3f}",
            "reveal_wait_elapsed_ms": f"{reveal_wait_elapsed_ms:.3f}",
            "workflow_id": workflow_id,
            "slow_threshold_ms": f"{_SLOW_PROJECTED_CUBE_BUILD_MS:.3f}",
            "final_section_revealed": True,
        }
        log_panel_projection_event(
            "render_reconciler.projected_cube_revealed",
            cube_alias=projected_build.cube_alias,
            elapsed_ms=f"{elapsed_ms:.3f}",
            build_elapsed_ms=f"{elapsed_ms:.3f}",
            reveal_wait_elapsed_ms=f"{reveal_wait_elapsed_ms:.3f}",
            workflow_id=workflow_id,
            final_section_revealed=True,
        )
        if elapsed_ms >= _SLOW_PROJECTED_CUBE_BUILD_MS:
            log_warning(
                _LOGGER,
                "Projected editor cube section build was slow",
                **log_context,
            )
        else:
            log_info(
                _LOGGER,
                "Revealed projected editor cube section",
                **log_context,
            )

    def set_cube_widget_update_wash(self, widget: object, *, visible: bool) -> None:
        """Toggle a cube-section-local update wash when the widget supports it."""

        set_cube_widget_update_wash(widget, visible=visible)

    def _dispose_removed_layout_item(
        self,
        item: object,
        *,
        managed_widgets: set[object],
    ) -> None:
        """Detach reusable cube sections and delete obsolete layout content."""

        widget_getter = getattr(item, "widget", None)
        widget = widget_getter() if callable(widget_getter) else None
        if widget is not None:
            self._dispose_removed_layout_widget(
                widget,
                managed_widgets=managed_widgets,
            )
            return

        layout_getter = getattr(item, "layout", None)
        nested_layout = layout_getter() if callable(layout_getter) else None
        if nested_layout is None:
            return
        while nested_layout.count():
            child_item = nested_layout.takeAt(0)
            self._dispose_removed_layout_item(
                child_item,
                managed_widgets=managed_widgets,
            )

    @staticmethod
    def _dispose_removed_layout_widget(
        widget: object,
        *,
        managed_widgets: set[object],
    ) -> None:
        """Detach managed widgets and delete stale widgets no longer owned here."""

        if widget in managed_widgets:
            _detach_widget(widget)
            return

        delete_later = getattr(widget, "deleteLater", None)
        if callable(delete_later):
            delete_later()
            return

        _detach_widget(widget)


def set_cube_widget_update_wash(widget: object, *, visible: bool) -> None:
    """Toggle a cube-section-local update wash when the widget supports it."""

    method_name = "showUpdatingWash" if visible else "hideUpdatingWash"
    method = getattr(widget, method_name, None)
    if not callable(method):
        return
    if visible:
        method("Updating")
        return
    method()


def _widgets_in_layout(layout: _LayoutLike) -> list[object]:
    """Return the widgets currently present in a layout, ignoring spacers."""

    widgets: list[object] = []
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item is None:
            continue
        widget = item.widget()
        if isinstance(widget, QWidget):
            widgets.append(widget)
    return widgets


def _show_projected_widget_for_reveal(widget: object) -> None:
    """Make one staged cube section visible after it has entered the root layout."""

    show = getattr(widget, "show", None)
    if callable(show):
        show()
        return
    _call_widget_bool_method(widget, "setVisible", True)


def _finish_projected_widget_reveal(widget: object) -> None:
    """Re-enable painting for one staged cube section after reveal finalization."""

    _call_widget_bool_method(widget, "setUpdatesEnabled", True)
    update = getattr(widget, "update", None)
    if callable(update):
        update()


def _repopulate_update_hosts(panel: object) -> tuple[object, ...]:
    """Return unique widgets whose painting should pause during bulk layout edits."""

    candidates = [
        panel,
        getattr(panel, "scroll", None),
        _layout_parent_widget(getattr(panel, "_layout", None)),
    ]
    hosts: list[object] = []
    seen: set[int] = set()
    for candidate in candidates:
        if candidate is None:
            continue
        identifier = id(candidate)
        if identifier in seen:
            continue
        seen.add(identifier)
        hosts.append(candidate)
    return tuple(hosts)


def _layout_parent_widget(layout: object | None) -> object | None:
    """Return a layout parent widget when the layout implementation exposes one."""

    parent_widget = getattr(layout, "parentWidget", None)
    if callable(parent_widget):
        return cast(object | None, parent_widget())
    return None


def _activate_layout(layout: object) -> None:
    """Run one final layout activation pass when supported."""

    activate = getattr(layout, "activate", None)
    if callable(activate):
        activate()


def _set_widgets_updates_enabled(widgets: Sequence[object], enabled: bool) -> None:
    """Toggle updates on every widget-like object that supports it."""

    for widget in widgets:
        _call_widget_bool_method(widget, "setUpdatesEnabled", enabled)


def _request_widget_updates(widgets: Sequence[object]) -> None:
    """Request one repaint on every widget-like object that supports it."""

    for widget in widgets:
        update = getattr(widget, "update", None)
        if callable(update):
            update()


def _detach_widget(widget: object) -> None:
    """Detach one widget-like object when it exposes Qt parent ownership."""

    set_parent = getattr(widget, "setParent", None)
    if callable(set_parent):
        set_parent(None)


def _call_widget_bool_method(widget: object, method_name: str, value: bool) -> None:
    """Call a one-argument widget boolean method when the object supports it."""

    method = getattr(widget, method_name, None)
    if callable(method):
        method(value)

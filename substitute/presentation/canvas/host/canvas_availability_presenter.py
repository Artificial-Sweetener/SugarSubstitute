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

"""Present generic canvas availability without owning Input or Output policy."""

from __future__ import annotations

from typing import Any


class CanvasAvailabilityPresenter:
    """Apply availability state to a named host page."""

    @staticmethod
    def set_canvas_available(
        host: Any,
        label: str,
        available: bool,
        *,
        reason: str = "",
        fallback_label: str | None = None,
    ) -> None:
        """Show or hide one docked canvas selector and update its passive view."""

        availability = getattr(host, "_canvas_availability", None)
        if not isinstance(availability, dict):
            availability = {}
            host._canvas_availability = availability
        availability[label] = available
        canvas = getattr(host, "canvas_map", {}).get(label)
        set_available = getattr(canvas, "set_available", None)
        if callable(set_available):
            set_available(available, reason)

        floating_windows = getattr(host, "floating_windows", {})
        if label in floating_windows:
            return
        if available:
            CanvasAvailabilityPresenter.restore_pivot_item(host, label)
            return
        CanvasAvailabilityPresenter.hide_pivot_item(
            host,
            label,
            fallback_label=fallback_label,
        )

    @staticmethod
    def hide_pivot_item(
        host: Any,
        label: str,
        *,
        fallback_label: str | None = None,
    ) -> None:
        """Remove one docked selector while preserving its canvas widget."""

        pivot = getattr(host, "pivot", None)
        if pivot is None:
            host.update_tab_visibility()
            return
        if label not in getattr(pivot, "items", {}):
            host.update_tab_visibility()
            return
        current_route_key = getattr(pivot, "currentRouteKey", None)
        if (
            callable(current_route_key)
            and current_route_key() == label
            and fallback_label is not None
        ):
            host.focus_attached_canvas(fallback_label)
        pivot.removeWidget(label)
        CanvasAvailabilityPresenter.remove_stacked_wrapper(host, label)
        host.update_tab_visibility()

    @staticmethod
    def restore_pivot_item(host: Any, label: str) -> None:
        """Restore one docked selector when its page becomes available."""

        pivot = getattr(host, "pivot", None)
        if pivot is None:
            host.update_tab_visibility()
            return
        floating_windows = getattr(host, "floating_windows", {})
        canvas_map = getattr(host, "canvas_map", {})
        if label in getattr(pivot, "items", {}) or label in floating_windows:
            host.update_tab_visibility()
            return
        if label not in canvas_map:
            host.update_tab_visibility()
            return
        from substitute.presentation.canvas.host.canvas_tabs_view import (
            CanvasTabManager,
        )

        insert_index = host.insertion_index_for_label(label)
        pivot.insertWidget(
            insert_index,
            label,
            CanvasTabManager._pivot_item_for(host, label),
        )
        CanvasAvailabilityPresenter.restore_stacked_wrapper(
            host,
            label,
            insert_index=insert_index,
        )
        host.rebuild_tab_indices()
        host.update_tab_visibility()

    @staticmethod
    def remove_stacked_wrapper(host: Any, label: str) -> None:
        """Remove an unavailable docked page from the visible stack."""

        stack = getattr(host, "stack", None)
        wrapper = getattr(host, "wrapper_map", {}).get(label)
        remove_widget = getattr(stack, "removeWidget", None)
        if wrapper is not None and callable(remove_widget):
            remove_widget(wrapper)

    @staticmethod
    def restore_stacked_wrapper(
        host: Any,
        label: str,
        *,
        insert_index: int,
    ) -> None:
        """Restore an available docked page to the visible stack."""

        stack = getattr(host, "stack", None)
        wrapper = getattr(host, "wrapper_map", {}).get(label)
        if wrapper is None:
            return
        stack_index_for_label = getattr(host, "_stack_index_for_label", None)
        if callable(stack_index_for_label) and stack_index_for_label(label) >= 0:
            return
        insert_widget = getattr(stack, "insertWidget", None)
        if callable(insert_widget):
            insert_widget(insert_index, wrapper)


__all__ = ["CanvasAvailabilityPresenter"]

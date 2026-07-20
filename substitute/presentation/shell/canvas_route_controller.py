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

"""Coordinate attached canvas route availability and workflow route memory."""

from __future__ import annotations

from typing import Any

from sugarsubstitute_shared.presentation.localization import app_text


class CanvasRouteController:
    """Own active workflow canvas-route projection for the shell."""

    def __init__(self, shell: Any) -> None:
        """Store the shell whose canvas tabs should be coordinated."""

        self._shell = shell

    def refresh_input_canvas_availability(self) -> None:
        """Apply active workflow input-canvas availability to canvas widgets."""

        active_workflow = self._shell.get_active_workflow()
        needs_input_canvas = (
            self._shell.input_canvas_capability_service.workflow_needs_input_canvas(
                active_workflow
            )
        )
        set_canvas_available = getattr(
            self._shell.canvas_tabs,
            "set_canvas_available",
            None,
        )
        if callable(set_canvas_available):
            set_canvas_available(
                "Input",
                needs_input_canvas,
                reason=app_text("No input canvas nodes"),
                fallback_label="Output",
            )
        self.restore_active_canvas_route(
            active_workflow,
            input_canvas_available=needs_input_canvas,
        )

    def connect_canvas_route_signals(self) -> None:
        """Record the selected attached canvas route on the active workflow."""

        route_changed = getattr(self._shell.canvas_tabs, "canvas_activated", None)
        if route_changed is not None:
            route_changed.connect(self.record_active_canvas_route)

    def record_active_canvas_route(self, route_key: str) -> None:
        """Persist the selected attached canvas route for the active workflow."""

        if route_key not in {"Input", "Output"}:
            return
        active_workflow = self._shell.get_active_workflow()
        canvas = getattr(active_workflow, "canvas", None)
        if canvas is not None:
            canvas.active_canvas_route = route_key

    def restore_active_canvas_route(
        self,
        active_workflow: object,
        *,
        input_canvas_available: bool,
    ) -> None:
        """Focus the active workflow's last attached canvas route when valid."""

        canvas = getattr(active_workflow, "canvas", None)
        if canvas is None:
            return
        route_key = getattr(canvas, "active_canvas_route", None)
        if (
            route_key is None
            and input_canvas_available
            and self.workflow_has_active_input_canvas_state(canvas)
        ):
            route_key = "Input"
            canvas.active_canvas_route = route_key
        if route_key == "Input" and not input_canvas_available:
            canvas.active_canvas_route = "Output"
            route_key = "Output"
        if route_key not in {"Input", "Output"}:
            return
        focus_attached_canvas = getattr(
            self._shell.canvas_tabs,
            "focus_attached_canvas",
            None,
        )
        if callable(focus_attached_canvas):
            focus_attached_canvas(route_key)

    @staticmethod
    def workflow_has_active_input_canvas_state(canvas: object) -> bool:
        """Return whether workflow canvas state has a concrete input editing target."""

        if canvas is None:
            return False
        if getattr(canvas, "input_image_uuid", None) is not None:
            return True
        mask_associations = getattr(canvas, "mask_associations", {})
        return isinstance(mask_associations, dict) and bool(mask_associations)


def canvas_route_controller_for(shell: Any) -> CanvasRouteController:
    """Return the composed canvas route controller for a shell."""

    controller = getattr(shell, "canvas_route_controller", None)
    if isinstance(controller, CanvasRouteController):
        return controller
    controller = CanvasRouteController(shell)
    setattr(shell, "canvas_route_controller", controller)
    return controller


__all__ = [
    "CanvasRouteController",
    "canvas_route_controller_for",
]

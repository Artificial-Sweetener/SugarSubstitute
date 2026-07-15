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

"""Cover attached canvas route coordination outside MainWindow."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.canvas_route_controller import CanvasRouteController


def test_refresh_input_canvas_availability_projects_active_capability() -> None:
    """Input-canvas availability should be derived from the active workflow."""

    workflow = SimpleNamespace(canvas=SimpleNamespace(active_canvas_route=None))
    availability_calls: list[tuple[str, bool, str, str]] = []
    shell = _canvas_route_shell(
        workflow=workflow,
        input_canvas_capability_service=SimpleNamespace(
            workflow_needs_input_canvas=lambda active_workflow: (
                active_workflow is workflow
            )
        ),
        canvas_tabs=SimpleNamespace(
            set_canvas_available=lambda label, available, *, reason, fallback_label: (
                availability_calls.append((label, available, reason, fallback_label))
            )
        ),
    )

    CanvasRouteController(shell).refresh_input_canvas_availability()

    assert availability_calls == [("Input", True, "No input canvas nodes", "Output")]


def test_refresh_input_canvas_availability_restores_remembered_input_route() -> None:
    """Returning to an input workflow should refocus its attached Input canvas."""

    workflow = SimpleNamespace(canvas=SimpleNamespace(active_canvas_route="Input"))
    focus_calls: list[str] = []
    shell = _canvas_route_shell(
        workflow=workflow,
        input_canvas_capability_service=SimpleNamespace(
            workflow_needs_input_canvas=lambda _workflow: True
        ),
        canvas_tabs=SimpleNamespace(
            set_canvas_available=lambda *_args, **_kwargs: None,
            focus_attached_canvas=lambda route: focus_calls.append(route),
        ),
    )

    CanvasRouteController(shell).refresh_input_canvas_availability()

    assert focus_calls == ["Input"]
    assert workflow.canvas.active_canvas_route == "Input"


def test_refresh_input_canvas_availability_defaults_loaded_input_workflow_to_input() -> (
    None
):
    """Loaded input canvas state should restore Input before route memory exists."""

    workflow = SimpleNamespace(
        canvas=SimpleNamespace(
            active_canvas_route=None,
            input_image_uuid=object(),
            mask_associations={},
        )
    )
    focus_calls: list[str] = []
    shell = _canvas_route_shell(
        workflow=workflow,
        input_canvas_capability_service=SimpleNamespace(
            workflow_needs_input_canvas=lambda _workflow: True
        ),
        canvas_tabs=SimpleNamespace(
            set_canvas_available=lambda *_args, **_kwargs: None,
            focus_attached_canvas=lambda route: focus_calls.append(route),
        ),
    )

    CanvasRouteController(shell).refresh_input_canvas_availability()

    assert focus_calls == ["Input"]
    assert workflow.canvas.active_canvas_route == "Input"


def test_refresh_input_canvas_availability_coerces_unavailable_input_route() -> None:
    """A workflow without input canvas support should not restore Input focus."""

    workflow = SimpleNamespace(canvas=SimpleNamespace(active_canvas_route="Input"))
    focus_calls: list[str] = []
    shell = _canvas_route_shell(
        workflow=workflow,
        input_canvas_capability_service=SimpleNamespace(
            workflow_needs_input_canvas=lambda _workflow: False
        ),
        canvas_tabs=SimpleNamespace(
            set_canvas_available=lambda *_args, **_kwargs: None,
            focus_attached_canvas=lambda route: focus_calls.append(route),
        ),
    )

    CanvasRouteController(shell).refresh_input_canvas_availability()

    assert focus_calls == ["Output"]
    assert workflow.canvas.active_canvas_route == "Output"


def test_record_active_canvas_route_persists_known_route_on_active_workflow() -> None:
    """Canvas pivot changes should update active workflow route memory."""

    workflow = SimpleNamespace(canvas=SimpleNamespace(active_canvas_route=None))
    shell = _canvas_route_shell(workflow=workflow)
    controller = CanvasRouteController(shell)

    controller.record_active_canvas_route("Input")
    controller.record_active_canvas_route("Unknown")

    assert workflow.canvas.active_canvas_route == "Input"


def test_connect_canvas_route_signals_records_route_changes() -> None:
    """Canvas route signals should connect to route persistence."""

    workflow = SimpleNamespace(canvas=SimpleNamespace(active_canvas_route=None))
    signal = _Signal()
    shell = _canvas_route_shell(
        workflow=workflow,
        canvas_tabs=SimpleNamespace(canvas_activated=signal),
    )

    CanvasRouteController(shell).connect_canvas_route_signals()
    signal.emit("Output")

    assert workflow.canvas.active_canvas_route == "Output"


def test_workflow_has_active_input_canvas_state_detects_images_and_masks() -> None:
    """Input route defaults should require concrete image or mask state."""

    assert not CanvasRouteController.workflow_has_active_input_canvas_state(None)
    assert CanvasRouteController.workflow_has_active_input_canvas_state(
        SimpleNamespace(input_image_uuid=object(), mask_associations={})
    )
    assert CanvasRouteController.workflow_has_active_input_canvas_state(
        SimpleNamespace(input_image_uuid=None, mask_associations={"mask": object()})
    )
    assert not CanvasRouteController.workflow_has_active_input_canvas_state(
        SimpleNamespace(input_image_uuid=None, mask_associations={})
    )


class _Signal:
    """Record and emit one connected slot."""

    def __init__(self) -> None:
        """Initialize with no connected slot."""

        self._slot: object | None = None

    def connect(self, slot: object) -> None:
        """Record the connected slot."""

        self._slot = slot

    def emit(self, route_key: str) -> None:
        """Emit the route key to the connected slot."""

        if callable(self._slot):
            self._slot(route_key)


def _canvas_route_shell(
    *,
    workflow: object | None = None,
    input_canvas_capability_service: object | None = None,
    canvas_tabs: object | None = None,
) -> SimpleNamespace:
    """Build a shell fake with canvas route dependencies."""

    active_workflow = workflow or SimpleNamespace(
        canvas=SimpleNamespace(active_canvas_route=None)
    )
    return SimpleNamespace(
        get_active_workflow=lambda: active_workflow,
        input_canvas_capability_service=input_canvas_capability_service
        or SimpleNamespace(workflow_needs_input_canvas=lambda _workflow: False),
        canvas_tabs=canvas_tabs
        or SimpleNamespace(
            set_canvas_available=lambda *_args, **_kwargs: None,
            focus_attached_canvas=lambda _route: None,
        ),
    )

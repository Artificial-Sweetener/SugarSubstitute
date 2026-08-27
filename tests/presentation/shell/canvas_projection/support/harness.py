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

"""Characterize canvas projection coordinator harness contracts."""

from __future__ import annotations

import uuid
from collections.abc import Mapping

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.input_canvas_state_service import (
    InputCanvasStateService,
)
from substitute.application.workflows.output_canvas_projection_coordinator import (
    OutputCanvasProjectionCoordinator,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputCanvasFocusService,
)
from substitute.application.workflows.output_generated_result_service import (
    OutputGeneratedResultService,
)
from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_canvas_timing_service import (
    OutputCanvasTimingService,
)
from substitute.domain.workflow import (
    CanvasSessionBoundary,
    ImageMeta,
    WorkflowState,
)
from substitute.presentation.canvas.input.input_route_projector import (
    InputRouteProjector,
)


from .input_document import _FakeInputDocument
from .output_document import (
    _FakeOutputCanvas,
    _FakeOutputContentSynchronizer,
    _FakeOutputDocument,
)


class _CanvasProjectionHarness:
    def __init__(
        self,
        *,
        image_registry: CanvasImageRegistry,
        canvas_session_boundary: CanvasSessionBoundary,
        output_canvas_state_service: OutputCanvasStateService,
        output_canvas_focus_service: OutputCanvasFocusService,
        output_navigation_session_service: OutputNavigationSessionService,
        output_generated_result_service: OutputGeneratedResultService,
        output_canvas_timing_service: OutputCanvasTimingService,
        input_canvas_state_service: InputCanvasStateService,
        output_canvas_projection_coordinator: OutputCanvasProjectionCoordinator,
    ) -> None:
        self.image_registry = image_registry
        self.canvas_session_boundary = canvas_session_boundary
        self.output_canvas_state_service = output_canvas_state_service
        self.output_canvas_focus_service = output_canvas_focus_service
        self.output_navigation_session_service = output_navigation_session_service
        self.output_generated_result_service = output_generated_result_service
        self.output_canvas_timing_service = output_canvas_timing_service
        self._input_canvas_state_service = input_canvas_state_service
        self._output_canvas_projection_coordinator = (
            output_canvas_projection_coordinator
        )

    def project_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
    ) -> None:
        self._input_canvas_state_service.project_workflow(
            workflows,
            active_workflow_id,
        )
        self._output_canvas_projection_coordinator.project_workflow(
            workflows,
            active_workflow_id,
        )

    def project_output(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
        *,
        registered_image_id: uuid.UUID | None = None,
    ) -> None:
        self._output_canvas_projection_coordinator.project_workflow(
            workflows,
            active_workflow_id,
            registered_image_id=registered_image_id,
        )

    def clear_output_for_workflow(
        self,
        workflows: Mapping[str, WorkflowState],
        active_workflow_id: str,
    ) -> None:
        self._output_canvas_projection_coordinator.clear_output_for_workflow(
            workflows,
            active_workflow_id,
        )

    def prune_closed_workflow_images(
        self,
        closed_workflow_id: str,
        closed_workflow: WorkflowState,
        remaining_workflows: Mapping[str, WorkflowState],
    ) -> None:
        self._output_canvas_projection_coordinator.prune_closed_workflow_images(
            closed_workflow_id,
            closed_workflow,
            remaining_workflows,
        )


def _build_services() -> tuple[
    _CanvasProjectionHarness,
    InputCanvasStateService,
    _FakeInputDocument,
    _FakeOutputDocument,
    _FakeOutputCanvas,
]:
    input_pane = _FakeInputDocument()
    output_document = _FakeOutputDocument()
    output_canvas = _FakeOutputCanvas(output_document)
    canvas_session_boundary = CanvasSessionBoundary()
    image_registry = CanvasImageRegistry()
    input_canvas_state_service = InputCanvasStateService(
        input_document=input_pane,
        input_route_projector=InputRouteProjector(
            input_pane,
            session_boundary=canvas_session_boundary,
        ),
        canvas_session_boundary=canvas_session_boundary,
        image_registry=image_registry,
    )
    output_canvas_state_service = OutputCanvasStateService(
        image_registry=image_registry,
    )
    output_canvas_focus_service = OutputCanvasFocusService(
        image_registry=image_registry,
    )
    output_navigation_session_service = OutputNavigationSessionService()
    output_generated_result_service = OutputGeneratedResultService(
        image_registry=image_registry,
        output_state_service=output_canvas_state_service,
        navigation_session_service=output_navigation_session_service,
    )
    output_canvas_timing_service = OutputCanvasTimingService(
        image_registry=image_registry,
    )
    output_canvas_projection_coordinator = OutputCanvasProjectionCoordinator(
        image_registry=image_registry,
        output_canvas_state_service=output_canvas_state_service,
        output_canvas_focus_service=output_canvas_focus_service,
        output_navigation_session_service=output_navigation_session_service,
        canvas_session_boundary=canvas_session_boundary,
        content_synchronizer=_FakeOutputContentSynchronizer(
            image_registry,
            output_document,
        ),
        projection_sink=output_canvas,
    )
    service = _CanvasProjectionHarness(
        image_registry=image_registry,
        canvas_session_boundary=canvas_session_boundary,
        output_canvas_state_service=output_canvas_state_service,
        output_canvas_focus_service=output_canvas_focus_service,
        output_navigation_session_service=output_navigation_session_service,
        output_generated_result_service=output_generated_result_service,
        output_canvas_timing_service=output_canvas_timing_service,
        input_canvas_state_service=input_canvas_state_service,
        output_canvas_projection_coordinator=output_canvas_projection_coordinator,
    )
    return (
        service,
        input_canvas_state_service,
        input_pane,
        output_document,
        output_canvas,
    )


def _build_service() -> tuple[
    _CanvasProjectionHarness,
    _FakeInputDocument,
    _FakeOutputDocument,
    _FakeOutputCanvas,
]:
    service, _input_service, input_pane, output_document, output_canvas = (
        _build_services()
    )
    return service, input_pane, output_document, output_canvas


def _app() -> QApplication:
    """Return a QApplication for Qt-backed scheduler tests."""

    app = QCoreApplication.instance()
    if isinstance(app, QApplication):
        return app
    return QApplication([])


def _store_image_record(
    service: _CanvasProjectionHarness,
    image_id: uuid.UUID,
    image_meta: ImageMeta,
    *,
    payload: object | None = None,
) -> None:
    """Store a test image record through the shared registry."""

    service.image_registry.store(image_id, payload=payload, metadata=image_meta)


def _add_output_image(
    service: _CanvasProjectionHarness,
    workflows: dict[str, WorkflowState],
    *,
    origin_workflow_id: str,
    active_workflow_id: str,
    image: object,
    image_meta: ImageMeta,
) -> uuid.UUID:
    """Register and project an output image through Phase 7 owners."""

    result = service.output_canvas_state_service.register_output_image(
        workflows,
        origin_workflow_id,
        active_workflow_id,
        image,
        image_meta,
    )
    assert result.image_id is not None
    if result.projection_intent.should_schedule:
        service.project_output(
            workflows,
            active_workflow_id,
            registered_image_id=result.projection_intent.registered_image_id,
        )
    return result.image_id

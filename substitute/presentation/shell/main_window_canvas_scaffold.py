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

"""Compose the MainWindow canvas host and its application state owners."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, cast

from PySide6.QtWidgets import QVBoxLayout, QWidget
from cutecanvas import ExecutionRuntime

from substitute.application.workflows import (
    OutputCanvasProjectionCoordinator,
    WorkflowCanvasProjectionCoordinator,
)
from substitute.application.workflows import input_canvas_state_composition
from substitute.application.workflows.canvas_image_registry import CanvasImageRegistry
from substitute.application.workflows.canvas_route_projector_port import (
    create_canvas_session_boundary,
)
from substitute.application.workflows.output_canvas_focus_service import (
    OutputCanvasFocusService,
)
from substitute.application.workflows.output_canvas_state_service import (
    OutputCanvasStateService,
)
from substitute.application.workflows.output_canvas_timing_service import (
    OutputCanvasTimingService,
)
from substitute.application.workflows.output_generated_result_service import (
    OutputGeneratedResultService,
)
from substitute.application.workflows.output_navigation_session_service import (
    OutputNavigationSessionService,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewRegistry,
)
from substitute.domain.generation import VideoPlaybackSettings
from substitute.infrastructure.comfy.session_video_artifact_store import (
    release_temporary_video_artifact,
)
from substitute.presentation.canvas import (
    create_canvas_host,
    create_output_floating_chrome_factory,
)
from substitute.presentation.canvas.host import CanvasHost
from substitute.presentation.canvas.output.output_floating_chrome import (
    OutputFloatingChromeFactory,
)
from substitute.presentation.canvas.shared.types import OutputImageMeta
from substitute.presentation.shell.output_media_retirement import (
    OutputMediaRetirementCoordinator,
    RetirableVideoPresentation,
)
from substitute.shared.startup_trace import trace_span

OutputSingleExternalEditor = Callable[[object, OutputImageMeta], bool]
OutputAllExternalEditor = Callable[[list[tuple[object, OutputImageMeta]]], bool]
OutputAssetReveal = Callable[[OutputImageMeta], bool]


class _OutputCanvasMediaOwner(Protocol):
    """Expose the video presentation owner mounted by Output canvas."""

    video_presentation: RetirableVideoPresentation


@dataclass(frozen=True, slots=True)
class MainWindowCanvasScaffold:
    """Bundle the canvas host and state owners assembled around it."""

    canvas_host: CanvasHost
    input_canvas_state: input_canvas_state_composition.InputCanvasStateComposition
    output_canvas_state_service: OutputCanvasStateService
    output_canvas_focus_service: OutputCanvasFocusService
    output_navigation_session_service: OutputNavigationSessionService
    output_generated_result_service: OutputGeneratedResultService
    output_canvas_timing_service: OutputCanvasTimingService
    output_canvas_projection_coordinator: OutputCanvasProjectionCoordinator
    workflow_canvas_projection_coordinator: WorkflowCanvasProjectionCoordinator
    canvas_image_registry: CanvasImageRegistry
    output_floating_chrome_factory: OutputFloatingChromeFactory
    canvas_host_container: QWidget


def build_main_window_canvas_scaffold(
    *,
    canvas_execution_runtime: ExecutionRuntime,
    output_preview_registry: OutputPreviewRegistry,
    open_single_external_editor: OutputSingleExternalEditor | None,
    open_all_external_editor: OutputAllExternalEditor | None,
    reveal_output_asset: OutputAssetReveal | None = None,
    video_settings_provider: Callable[[], VideoPlaybackSettings] | None = None,
) -> MainWindowCanvasScaffold:
    """Build the canvas host, state owners, and its container widget."""

    canvas_session_boundary = create_canvas_session_boundary()
    canvas_host: CanvasHost | None = None

    def current_video_presentation() -> RetirableVideoPresentation | None:
        """Resolve the player owner lazily after host construction."""

        if canvas_host is None:
            return None
        output_canvas = canvas_host.canvas_for("Output")
        if output_canvas is None:
            return None
        return cast(_OutputCanvasMediaOwner, output_canvas).video_presentation

    media_retirement = OutputMediaRetirementCoordinator(
        video_presentation=current_video_presentation,
        release_artifact=release_temporary_video_artifact,
    )
    canvas_image_registry = CanvasImageRegistry(
        on_record_removed=media_retirement.retire_record
    )
    output_floating_chrome_factory = create_output_floating_chrome_factory()
    with trace_span("mainwindow.build_workspace.canvas.create_host"):
        canvas_host = create_canvas_host(
            execution_runtime=canvas_execution_runtime,
            output_preview_registry=output_preview_registry,
            open_single_external_editor=open_single_external_editor,
            open_all_external_editor=open_all_external_editor,
            reveal_output_asset=reveal_output_asset,
            final_output_payload_lookup=canvas_image_registry.payload_for,
            final_output_metadata_lookup=canvas_image_registry.metadata_for,
            output_floating_chrome_factory=output_floating_chrome_factory,
            route_session_boundary=canvas_session_boundary,
            video_settings_provider=video_settings_provider,
        )
    with trace_span("mainwindow.build_workspace.canvas.validate_host"):
        output_canvas = cast(Any, canvas_host.canvas_for("Output"))
        input_canvas = cast(Any, canvas_host.canvas_for("Input"))
        if input_canvas is None or output_canvas is None:
            raise RuntimeError("Canvas host must include Input and Output canvases.")

    with trace_span("mainwindow.build_workspace.canvas.state_service"):
        input_canvas_state = input_canvas_state_composition.compose_input_canvas_state(
            document=input_canvas.document,
            route_projector=input_canvas.route_projector,
            session_boundary=canvas_session_boundary,
            image_registry=canvas_image_registry,
        )
        output_canvas_state_service = OutputCanvasStateService(
            image_registry=canvas_image_registry,
        )
        output_canvas_focus_service = OutputCanvasFocusService(
            image_registry=canvas_image_registry,
        )
        output_navigation_session_service = OutputNavigationSessionService()
        output_generated_result_service = OutputGeneratedResultService(
            image_registry=canvas_image_registry,
            output_state_service=output_canvas_state_service,
            navigation_session_service=output_navigation_session_service,
        )
        output_canvas_timing_service = OutputCanvasTimingService(
            image_registry=canvas_image_registry,
        )
        output_projection_content_synchronizer = (
            output_canvas.create_projection_content_synchronizer(canvas_image_registry)
        )
        output_canvas_projection_coordinator = OutputCanvasProjectionCoordinator(
            image_registry=canvas_image_registry,
            output_canvas_state_service=output_canvas_state_service,
            output_canvas_focus_service=output_canvas_focus_service,
            output_navigation_session_service=output_navigation_session_service,
            canvas_session_boundary=canvas_session_boundary,
            content_synchronizer=output_projection_content_synchronizer,
            projection_sink=output_canvas,
        )
        workflow_canvas_projection_coordinator = WorkflowCanvasProjectionCoordinator(
            input_routes=input_canvas_state.routes,
            output_canvas_projection_coordinator=output_canvas_projection_coordinator,
        )

    with trace_span("mainwindow.build_workspace.canvas.container"):
        canvas_host_container = QWidget()
        container_layout = QVBoxLayout(canvas_host_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(canvas_host)
    return MainWindowCanvasScaffold(
        canvas_host=canvas_host,
        input_canvas_state=input_canvas_state,
        output_canvas_state_service=output_canvas_state_service,
        output_canvas_focus_service=output_canvas_focus_service,
        output_navigation_session_service=output_navigation_session_service,
        output_generated_result_service=output_generated_result_service,
        output_canvas_timing_service=output_canvas_timing_service,
        output_canvas_projection_coordinator=output_canvas_projection_coordinator,
        workflow_canvas_projection_coordinator=workflow_canvas_projection_coordinator,
        canvas_image_registry=canvas_image_registry,
        output_floating_chrome_factory=output_floating_chrome_factory,
        canvas_host_container=canvas_host_container,
    )


__all__ = [
    "MainWindowCanvasScaffold",
    "OutputAllExternalEditor",
    "OutputAssetReveal",
    "OutputSingleExternalEditor",
    "build_main_window_canvas_scaffold",
]

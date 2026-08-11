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

"""Exercise mounted workflow-reactive Input tool projection and lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from uuid import UUID, uuid4

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget
from cutecanvas import CuteCanvas, EditorTransformTarget
from sugarsubstitute_shared.presentation.localization import app_text

from substitute.domain.workflow import (
    InputCanvasInteractionCapability,
    InputCanvasInteractionProfile,
    WorkflowState,
)
from substitute.presentation.canvas.input.input_canvas_tool_catalog import (
    INPUT_CANVAS_CONTEXT,
    INPUT_IMAGE_CAPABILITY,
    INPUT_RASTER_ANALYSIS_CONTEXT,
    InputCanvasToolId,
    create_input_canvas_tool_system,
)
from substitute.presentation.canvas.input.input_canvas_tool_context import (
    InputCanvasToolContextSnapshot,
)
from substitute.presentation.canvas.input.input_canvas_tool_controller import (
    InputCanvasToolController,
)
from substitute.presentation.canvas.input.input_canvas_tool_layout import (
    create_input_canvas_tool_layout,
)
from substitute.presentation.canvas.input.input_canvas_tool_profile_controller import (
    InputCanvasToolProfileController,
)
from substitute.presentation.canvas.tools import (
    CanvasToolContribution,
    CanvasToolKind,
    CanvasToolStrip,
)
from substitute.presentation.shell.main_window_canvas_route_adapter import (
    MainWindowCanvasRouteAdapter,
)
from substitute.presentation.shell.workflow_surface_results import (
    SurfaceRefreshStatus,
)


@dataclass
class _DocumentContext:
    """Expose mutable mounted-document readiness and transform activation."""

    image_id: UUID | None
    has_active_mask: bool = True
    sam_ready: bool = True
    edit_session_active: bool = False

    @property
    def snapshot(self) -> InputCanvasToolContextSnapshot:
        """Return current transient readiness facts."""

        return InputCanvasToolContextSnapshot(
            image_id=self.image_id,
            has_active_mask=self.has_active_mask,
            smart_segmentation_ready=self.sam_ready,
            has_pixel_selection=False,
            selection_transform_available=False,
            layer_transform_available=True,
            selection_clear_available=False,
            edit_session_active=self.edit_session_active,
        )

    def activate_transform(self, _target: EditorTransformTarget) -> bool:
        """Reject unused transform requests in this workflow projection harness."""

        return False


class _MountedProjection:
    """Mount production palette, layout, activation, and Qt tool strip owners."""

    def __init__(self) -> None:
        """Create one authored workflow projection ready for transitions."""

        self.application = _application()
        self.workflow = WorkflowState()
        self.profile = _authored_profile()
        self.document = _DocumentContext(uuid4())
        self.runtime = create_input_canvas_tool_system()
        self.layout = create_input_canvas_tool_layout()
        self.operation = CuteCanvas.CONTROL_MODE_PANZOOM
        self.activation = InputCanvasToolController(
            transform_activator=self.document.activate_transform,
            operation_setter=self._set_operation,
            current_operation_provider=lambda: self.operation,
            runtime=self.runtime,
            layout=self.layout,
        )
        self.projection = InputCanvasToolProfileController(
            document_context=self.document,
            active_workflow=lambda: self.workflow,
            interaction_profile=lambda _workflow, _image_id: self.profile,
            palette=self.runtime.palette,
            activation=self.activation,
        )
        self.parent = QWidget()
        self.strip = CanvasToolStrip(self.parent)
        self.strip.bind_palette(self.runtime.palette, self.layout)
        self.parent.show()
        self.projection.refresh_workflow_profile()

    def close(self) -> None:
        """Release mounted Qt chrome and reject later profile refreshes."""

        self.projection.close()
        self.parent.close()
        self.parent.deleteLater()

    def _set_operation(self, operation_id: str) -> bool:
        """Accept and record one native document operation."""

        self.operation = operation_id
        return True


def test_mounted_synthetic_authored_transitions_preserve_layout_and_hidden_state() -> (
    None
):
    """Structural smart-tool changes must not rewrite runtime arrangement state."""

    mounted = _MountedProjection()
    assert mounted.layout.select_group_tool(
        "input.slot.selection_shapes",
        InputCanvasToolId.SELECT_LASSO,
    )
    assert mounted.layout.set_tool_hidden(InputCanvasToolId.SMART_SELECT, True)
    try:
        mounted.profile = _synthetic_profile()
        assert mounted.projection.refresh_workflow_profile()
        assert mounted.strip.button_for(InputCanvasToolId.SMART_SELECT) is None
        assert mounted.strip.button_for(InputCanvasToolId.SMART_MASK) is None
        assert (
            mounted.strip.button_for(InputCanvasToolId.SHARED_EDGE_RESIZE) is not None
        )
        assert mounted.activation.request_tool(InputCanvasToolId.SHARED_EDGE_RESIZE)
        transform_slot = next(
            slot
            for slot in mounted.layout.snapshot().slots
            if slot.slot_id == "input.slot.transform"
        )
        assert transform_slot.selected_tool_id == InputCanvasToolId.SHARED_EDGE_RESIZE
        remembered_layout = mounted.layout.snapshot()

        mounted.profile = _authored_profile()
        assert mounted.projection.refresh_workflow_profile()
        assert (
            mounted.runtime.palette.active_tool_id
            == InputCanvasToolId.SHARED_EDGE_RESIZE
        )
        assert mounted.strip.button_for(InputCanvasToolId.SMART_SELECT) is None
        assert mounted.strip.button_for(InputCanvasToolId.SMART_MASK) is not None

        mounted.profile = _synthetic_profile()
        assert mounted.projection.refresh_workflow_profile()
        assert (
            mounted.runtime.palette.active_tool_id
            == InputCanvasToolId.SHARED_EDGE_RESIZE
        )
        assert mounted.strip.button_for(InputCanvasToolId.SMART_SELECT) is None
        assert mounted.strip.button_for(InputCanvasToolId.SMART_MASK) is None

        mounted.profile = _authored_profile()
        assert mounted.projection.refresh_workflow_profile()
        assert mounted.strip.button_for(InputCanvasToolId.SMART_MASK) is not None
        assert mounted.layout.snapshot() == remembered_layout
    finally:
        mounted.close()


def test_active_smart_tool_recovers_to_pan_without_reactivation_on_return() -> None:
    """Losing raster applicability should leave a safe stable navigation mode."""

    mounted = _MountedProjection()
    try:
        assert mounted.activation.request_tool(InputCanvasToolId.SMART_MASK)
        assert mounted.runtime.palette.active_tool_id == InputCanvasToolId.SMART_MASK

        mounted.profile = _synthetic_profile()
        assert mounted.projection.refresh_workflow_profile()
        assert mounted.runtime.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM
        assert mounted.operation == CuteCanvas.CONTROL_MODE_PANZOOM

        mounted.profile = _authored_profile()
        assert mounted.projection.refresh_workflow_profile()
        assert mounted.runtime.palette.active_tool_id == InputCanvasToolId.PAN_ZOOM
        assert (
            mounted.runtime.palette.presentation_for(InputCanvasToolId.SMART_MASK)
            is not None
        )
    finally:
        mounted.close()


def test_runtime_contribution_obeys_the_same_raster_applicability_tag() -> None:
    """Provider tools should use ordinary semantic tags without toolbar changes."""

    mounted = _MountedProjection()
    tool_id = "provider.raster-analysis"
    mounted.runtime.registry.register(
        CanvasToolContribution(
            tool_id=tool_id,
            label=app_text("Provider raster analysis"),
            icon=QIcon(),
            kind=CanvasToolKind.MODE,
            section="provider",
            order=475,
            required_context_tags=frozenset(
                {INPUT_CANVAS_CONTEXT, INPUT_RASTER_ANALYSIS_CONTEXT}
            ),
            required_capabilities=frozenset({INPUT_IMAGE_CAPABILITY}),
            document_operation_id="provider.raster-analysis",
        )
    )

    try:
        assert mounted.runtime.palette.presentation_for(tool_id) is not None
        mounted.profile = _synthetic_profile()
        assert mounted.projection.refresh_workflow_profile()
        assert mounted.runtime.palette.presentation_for(tool_id) is None
        assert mounted.runtime.registry.contribution(tool_id) is not None
    finally:
        mounted.close()


def test_document_refresh_reuses_profile_and_workflow_refresh_recomputes_it() -> None:
    """Transient editor changes should not repeatedly rebuild graph-derived plans."""

    document = _DocumentContext(uuid4(), sam_ready=False)
    workflow = WorkflowState()
    resolutions: list[tuple[WorkflowState | None, UUID | None]] = []
    runtime = create_input_canvas_tool_system()
    activation = InputCanvasToolController(
        transform_activator=document.activate_transform,
        operation_setter=lambda _operation: True,
        current_operation_provider=lambda: CuteCanvas.CONTROL_MODE_PANZOOM,
        runtime=runtime,
    )

    def resolve(
        candidate: WorkflowState | None,
        image_id: UUID | None,
    ) -> InputCanvasInteractionProfile:
        """Record graph-derived profile resolutions."""

        resolutions.append((candidate, image_id))
        return _authored_profile()

    projection = InputCanvasToolProfileController(
        document_context=document,
        active_workflow=lambda: workflow,
        interaction_profile=resolve,
        palette=runtime.palette,
        activation=activation,
    )

    assert projection.refresh_workflow_profile()
    document.sam_ready = True
    assert projection.refresh_document_context()
    assert len(resolutions) == 1
    assert not projection.refresh_workflow_profile()
    assert len(resolutions) == 2


def test_active_edit_session_disables_competing_tools_until_resolution() -> None:
    """An unresolved provisional edit should retain only its active tool."""

    mounted = _MountedProjection()
    try:
        assert mounted.activation.request_tool(InputCanvasToolId.SHARED_EDGE_RESIZE)

        mounted.document.edit_session_active = True
        assert mounted.projection.refresh_document_context()

        edge = mounted.runtime.palette.presentation_for(
            InputCanvasToolId.SHARED_EDGE_RESIZE
        )
        pan = mounted.runtime.palette.presentation_for(InputCanvasToolId.PAN_ZOOM)
        assert edge is not None and edge.enabled and edge.active
        assert pan is not None and not pan.enabled
        assert not mounted.activation.request_tool(InputCanvasToolId.PAN_ZOOM)

        mounted.document.edit_session_active = False
        assert mounted.projection.refresh_document_context()
        assert mounted.activation.request_tool(InputCanvasToolId.PAN_ZOOM)
    finally:
        mounted.close()


def test_active_image_identity_change_recomputes_surface_applicability() -> None:
    """Changing the routed composition should resolve its exact workflow surface."""

    authored_image_id = uuid4()
    synthetic_image_id = uuid4()
    document = _DocumentContext(authored_image_id)
    workflow = WorkflowState()
    runtime = create_input_canvas_tool_system()
    activation = InputCanvasToolController(
        transform_activator=document.activate_transform,
        operation_setter=lambda _operation: True,
        current_operation_provider=lambda: CuteCanvas.CONTROL_MODE_PANZOOM,
        runtime=runtime,
    )
    projection = InputCanvasToolProfileController(
        document_context=document,
        active_workflow=lambda: workflow,
        interaction_profile=lambda _workflow, image_id: (
            _authored_profile()
            if image_id == authored_image_id
            else _synthetic_profile()
        ),
        palette=runtime.palette,
        activation=activation,
    )

    assert projection.refresh_workflow_profile()
    assert runtime.palette.presentation_for(InputCanvasToolId.SMART_SELECT) is not None

    document.image_id = synthetic_image_id
    assert projection.refresh_document_context()
    assert runtime.palette.presentation_for(InputCanvasToolId.SMART_SELECT) is None


def test_queued_refresh_uses_current_workflow_and_close_rejects_late_work() -> None:
    """Queued callbacks must neither restore stale tools nor run after teardown."""

    mounted = _MountedProjection()
    replacement_workflow = WorkflowState()
    try:
        QTimer.singleShot(0, mounted.projection.refresh_document_context)
        mounted.workflow = replacement_workflow
        mounted.profile = _synthetic_profile()
        _drain_queued_event()
        assert (
            mounted.runtime.palette.presentation_for(InputCanvasToolId.SMART_MASK)
            is None
        )

        mounted.projection.close()
        mounted.workflow = WorkflowState()
        mounted.profile = _authored_profile()
        QTimer.singleShot(0, mounted.projection.refresh_workflow_profile)
        _drain_queued_event()
        assert (
            mounted.runtime.palette.presentation_for(InputCanvasToolId.SMART_MASK)
            is None
        )
    finally:
        mounted.close()


def test_canvas_route_projection_refreshes_the_workflow_tool_profile() -> None:
    """The workflow canvas surface owner should force profile reprojection."""

    profile_refreshes: list[str] = []
    projected: list[str] = []
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            active_workflow_id="workflow-a",
            workflows={"workflow-a": WorkflowState()},
        ),
        workflow_canvas_projection_coordinator=SimpleNamespace(
            project_workflow=lambda _workflows, workflow_id: projected.append(
                workflow_id
            )
        ),
        input_canvas_tool_profile_controller=SimpleNamespace(
            refresh_workflow_profile=lambda: profile_refreshes.append("refreshed")
        ),
    )

    result = MainWindowCanvasRouteAdapter(shell).project_workflow_canvas("workflow-a")

    assert result.status is SurfaceRefreshStatus.SUCCESS
    assert projected == ["workflow-a"]
    assert profile_refreshes == ["refreshed"]


def test_canvas_availability_refresh_reprojects_the_workflow_tool_profile() -> None:
    """Graph availability reprojection should also invalidate cached applicability."""

    availability_refreshes: list[str] = []
    profile_refreshes: list[str] = []
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="workflow-a"),
        canvas_route_controller=SimpleNamespace(
            refresh_input_canvas_availability=lambda: availability_refreshes.append(
                "refreshed"
            )
        ),
        input_canvas_tool_profile_controller=SimpleNamespace(
            refresh_workflow_profile=lambda: profile_refreshes.append("refreshed")
        ),
    )

    result = MainWindowCanvasRouteAdapter(shell).refresh_input_canvas_availability(
        "workflow-a"
    )

    assert result.status is SurfaceRefreshStatus.SUCCESS
    assert availability_refreshes == ["refreshed"]
    assert profile_refreshes == ["refreshed"]


def _application() -> QApplication:
    """Return the shared Qt application used by mounted projection tests."""

    instance = QCoreApplication.instance()
    return instance if isinstance(instance, QApplication) else QApplication([])


def _drain_queued_event() -> None:
    """Run queued zero-delay work with a bounded event-loop deadline."""

    loop = QEventLoop()
    QTimer.singleShot(0, loop.quit)
    QTimer.singleShot(1_000, loop.quit)
    loop.exec()


def _authored_profile() -> InputCanvasInteractionProfile:
    """Return authored raster-analysis applicability."""

    return InputCanvasInteractionProfile(
        frozenset({InputCanvasInteractionCapability.RASTER_ANALYSIS_SOURCE})
    )


def _synthetic_profile() -> InputCanvasInteractionProfile:
    """Return synthetic canvas applicability without raster analysis."""

    return InputCanvasInteractionProfile()

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

"""Verify shell-owned synthetic canvas and graph transaction ordering."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

from PySide6.QtCore import QObject, Signal

import substitute.presentation.shell.synthetic_canvas_resolution_controller as controller_module
from substitute.application.workflows.synthetic_canvas_resolution_role_service import (
    SyntheticCanvasResolutionRole,
    SyntheticCanvasResolutionRoleService,
)
from substitute.application.workflows.synthetic_canvas_resolution_transaction_service import (
    SyntheticCanvasResolutionProjectionError,
    SyntheticCanvasResolutionTransactionService,
)
from substitute.application.workflows.workflow_graph_section_service import (
    WorkflowGraphSectionService,
)
from substitute.domain.workflow import (
    CanvasDimensionAuthority,
    CanvasDimensions,
    SyntheticCanvasResizeRequest,
    WorkflowState,
)
from substitute.presentation.canvas.input.synthetic_canvas_geometry_adapter import (
    SyntheticCanvasGeometryAdapter,
    SyntheticCanvasGeometryOperation,
    SyntheticCanvasGeometryResult,
    SyntheticCanvasGeometryStatus,
)
from substitute.presentation.shell.synthetic_canvas_resolution_controller import (
    SyntheticCanvasResolutionController,
)


class _Geometry(QObject):
    """Publish test-controlled geometry outcomes and rollback calls."""

    operationCompleted = Signal(object)
    geometryChanged = Signal(object, object, object)

    def __init__(self) -> None:
        """Initialize operation and rollback state."""

        super().__init__()
        self.operation: SyntheticCanvasGeometryOperation | None = None
        self.undo_calls = 0

    def capture_revision(self, composition_id: UUID) -> object:
        """Return a stable revision token."""

        return SimpleNamespace(composition_id=composition_id)

    def begin(
        self, *, composition_id: UUID, **_kwargs: object
    ) -> SyntheticCanvasGeometryOperation:
        """Create and retain one operation identity."""

        self.operation = SyntheticCanvasGeometryOperation(uuid4(), composition_id)
        return self.operation

    def cancel(self, _operation: SyntheticCanvasGeometryOperation) -> bool:
        """Accept cancellation."""

        return True

    def undo_last_geometry_edit(self) -> bool:
        """Record one rollback."""

        self.undo_calls += 1
        return True


class _Transactions:
    """Validate roles and record or reject graph projections."""

    def __init__(self, role: SyntheticCanvasResolutionRole) -> None:
        """Store expected role and projection history."""

        self.role = role
        self.projected: list[CanvasDimensions] = []
        self.reject_projection = False

    def validate(
        self,
        _workflow: WorkflowState,
        _expected: SyntheticCanvasResolutionRole,
    ) -> SyntheticCanvasResolutionRole:
        """Return the current role."""

        return self.role

    def project(
        self,
        _workflow: WorkflowState,
        *,
        expected: SyntheticCanvasResolutionRole,
        dimensions: CanvasDimensions,
    ) -> object:
        """Record a projection or raise the configured failure."""

        del expected
        if self.reject_projection:
            raise SyntheticCanvasResolutionProjectionError("test rejection")
        self.projected.append(dimensions)
        return object()


class _Dialog(QObject):
    """Expose the modal signals and terminal feedback used by the controller."""

    resizeRequested = Signal(object)
    cancellationRequested = Signal()
    finished = Signal(int)

    def __init__(self, **_kwargs: object) -> None:
        """Initialize observable dialog state."""

        super().__init__()
        self.shown = False
        self.completed = False
        self.errors: list[str] = []

    def show(self) -> None:
        """Record presentation."""

        self.shown = True

    def raise_(self) -> None:
        """Accept duplicate open requests."""

    def activateWindow(self) -> None:
        """Accept duplicate open requests."""

    def show_error(self, message: str) -> None:
        """Record one actionable failure."""

        self.errors.append(message)

    def finish_successfully(self) -> None:
        """Record terminal success."""

        self.completed = True

    def finish_cancelled(self) -> None:
        """Record terminal cancellation."""


class _Roles:
    """Resolve one role for external geometry synchronization."""

    def __init__(self, role: SyntheticCanvasResolutionRole) -> None:
        """Store the semantic role."""

        self.role = role

    def resolve_for_surface(self, **_kwargs: object) -> SyntheticCanvasResolutionRole:
        """Return the configured role."""

        return self.role


class _GraphSections:
    """Return one structurally present section graph."""

    def graph(self, _workflow: WorkflowState, _section_key: str) -> dict[str, object]:
        """Return a nonempty graph marker."""

        return {"nodes": {}}


def test_success_commits_mask_identity_then_graph_and_publishes_once(
    monkeypatch: Any,
) -> None:
    """A successful resize should leave canvas identities and graph size coherent."""

    monkeypatch.setattr(controller_module, "SyntheticCanvasResolutionDialog", _Dialog)
    role = _role()
    workflow, composition_id, old_mask_id = _workflow(role)
    new_mask_id = uuid4()
    geometry = _Geometry()
    transactions = _Transactions(role)
    published: list[str] = []
    refreshed: list[str] = []
    autosaves: list[bool] = []
    controller = _controller(
        role=role,
        workflow=workflow,
        geometry=geometry,
        transactions=transactions,
        published=published,
        refreshed=refreshed,
        autosaves=autosaves,
    )
    dialog = cast(_Dialog, controller.open_for_role("workflow", role))
    request = SyntheticCanvasResizeRequest(CanvasDimensions(1216, 832))
    dialog.resizeRequested.emit(request)
    assert geometry.operation is not None

    geometry.operationCompleted.emit(
        SyntheticCanvasGeometryResult(
            operation=geometry.operation,
            status=SyntheticCanvasGeometryStatus.COMPLETED,
            dimensions=request.dimensions,
            changed=True,
            mask_id_remap=((old_mask_id, new_mask_id),),
        )
    )

    assert workflow.canvas.mask_ids() == (new_mask_id,)
    assert transactions.projected == [CanvasDimensions(1216, 832)]
    assert published == ["workflow"]
    assert refreshed == ["workflow"]
    assert autosaves == [True]
    assert dialog.completed


def test_graph_projection_failure_undoes_canvas_and_mask_identity(
    monkeypatch: Any,
) -> None:
    """Graph rejection should restore the complete pre-dialog workflow identity."""

    monkeypatch.setattr(controller_module, "SyntheticCanvasResolutionDialog", _Dialog)
    role = _role()
    workflow, _composition_id, old_mask_id = _workflow(role)
    new_mask_id = uuid4()
    geometry = _Geometry()
    transactions = _Transactions(role)
    transactions.reject_projection = True
    controller = _controller(
        role=role,
        workflow=workflow,
        geometry=geometry,
        transactions=transactions,
    )
    dialog = cast(_Dialog, controller.open_for_role("workflow", role))
    request = SyntheticCanvasResizeRequest(CanvasDimensions(1216, 832))
    dialog.resizeRequested.emit(request)
    assert geometry.operation is not None

    geometry.operationCompleted.emit(
        SyntheticCanvasGeometryResult(
            operation=geometry.operation,
            status=SyntheticCanvasGeometryStatus.COMPLETED,
            dimensions=request.dimensions,
            changed=True,
            mask_id_remap=((old_mask_id, new_mask_id),),
        )
    )

    assert geometry.undo_calls == 1
    assert workflow.canvas.mask_ids() == (old_mask_id,)
    assert dialog.errors


def _controller(
    *,
    role: SyntheticCanvasResolutionRole,
    workflow: WorkflowState,
    geometry: _Geometry,
    transactions: _Transactions,
    published: list[str] | None = None,
    refreshed: list[str] | None = None,
    autosaves: list[bool] | None = None,
) -> SyntheticCanvasResolutionController:
    """Build one controller around observable test boundaries."""

    changed = published if published is not None else []
    editor_refreshes = refreshed if refreshed is not None else []
    save_requests = autosaves if autosaves is not None else []
    return SyntheticCanvasResolutionController(
        geometry=cast(SyntheticCanvasGeometryAdapter, geometry),
        roles=cast(SyntheticCanvasResolutionRoleService, _Roles(role)),
        transactions=cast(SyntheticCanvasResolutionTransactionService, transactions),
        graph_sections=cast(WorkflowGraphSectionService, _GraphSections()),
        workflows=lambda: {"workflow": workflow},
        modal_parent=lambda: None,
        preset_source=lambda _workflow_id: None,
        refresh_editor=editor_refreshes.append,
        mark_changed=changed.append,
        request_autosave=lambda: save_requests.append(True),
    )


def _role() -> SyntheticCanvasResolutionRole:
    """Build one graph authority snapshot."""

    return SyntheticCanvasResolutionRole(
        section_key="Region",
        surface_key="@synthetic/region",
        authority=CanvasDimensionAuthority(
            dimensions=CanvasDimensions(960, 1344),
            node_names=("latent",),
            field_pairs=(("width", "height"),),
            convergence_node_names=("sampler",),
            structural_fingerprint="structure",
            dimension_fingerprint="dimensions",
        ),
    )


def _workflow(
    role: SyntheticCanvasResolutionRole,
) -> tuple[WorkflowState, UUID, UUID]:
    """Build one materialized synthetic surface with an ordered region mask."""

    workflow = WorkflowState()
    composition_id = uuid4()
    old_mask_id = uuid4()
    workflow.canvas.bind_image(
        f"{role.section_key}:{role.surface_key}",
        composition_id,
    )
    workflow.canvas.bind_mask(
        (role.section_key, "mask"),
        old_mask_id,
        composition_id,
    )
    return workflow, composition_id, old_mask_id

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

"""Provide shared Output document fixtures and observations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID
from PySide6.QtCore import QPoint, QPointF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QWheelEvent,
)
from PySide6.QtWidgets import QApplication, QWidget
from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteSessionBoundaryPort,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasImageItem,
    OutputCanvasProjection,
    OutputCanvasSourceGroup,
)
from substitute.application.workflows.output_canvas_session import (
    OutputCanvasSession,
    bind_output_canvas_session,
)
from substitute.application.workflows.output_compare_state import (
    OutputCompareState,
)
from substitute.application.workflows.output_preview_registry import (
    OutputPreviewLane,
    OutputPreviewLaneKey,
)
from substitute.application.ports import PreviewImageUpdate
from substitute.application.workflows.output_visual_events import LivePreviewEvent
from substitute.domain.workflow import ImageMeta
from tests.support.qt.lifecycle import destroy_qt_object

if TYPE_CHECKING:
    from substitute.presentation.canvas.output.output_canvas_view import OutputCanvas


def _destroy_output_canvas(canvas: OutputCanvas) -> None:
    """Close the mounted document before destroying its Qt host."""

    canvas.document.close()
    canvas.close()
    destroy_qt_object(canvas)


def _image(color: str) -> QImage:
    """Return one non-null output image with a deterministic color."""

    image = QImage(QSize(32, 24), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(color))
    return image


def _sized_image(color: str, size: QSize) -> QImage:
    """Return one deterministic Output image with explicit source dimensions."""

    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(color))
    return image


def _app() -> QApplication:
    """Return a QApplication before constructing one Output workspace."""

    application = QApplication.instance()
    return application if isinstance(application, QApplication) else QApplication([])


class _DragProvider:
    """Capture output drag subjects without starting a native drag."""

    def __init__(self) -> None:
        """Initialize the captured subject collection."""
        self.subjects: list[object] = []

    def materialize(self, subject: object, _complete: object) -> None:
        """Capture the subject requested by the real pointer gesture."""
        self.subjects.append(subject)


def _wheel_event(target: QWidget, position: QPointF) -> QWheelEvent:
    """Create one local wheel gesture for a public Output canvas surface."""

    global_position = QPointF(target.mapToGlobal(position.toPoint()))
    return QWheelEvent(
        position,
        global_position,
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )


def _projection(
    first_id: UUID,
    second_id: UUID,
    *,
    compare_state: OutputCompareState = OutputCompareState(),
) -> OutputCanvasProjection:
    """Build one two-image source projection for workspace interaction coverage."""

    first = OutputCanvasImageItem(
        image_id=first_id,
        image_meta=_image_meta(1),
        set_index=1,
    )
    second = OutputCanvasImageItem(
        image_id=second_id,
        image_meta=_image_meta(2),
        set_index=2,
    )
    source = OutputCanvasSourceGroup(
        source_key="source",
        label="Source",
        images_by_set={1: first, 2: second},
    )
    return OutputCanvasProjection(
        sources=(source,),
        active_source_key="source",
        active_set_index=1,
        active_uuid=first.image_id,
        set_count=2,
        compare_state=compare_state,
    )


def _linked_projection(
    first_id: UUID,
    second_id: UUID,
) -> OutputCanvasProjection:
    """Build two source peers in the same unscened batch."""

    first = OutputCanvasImageItem(
        image_id=first_id,
        image_meta=_image_meta(1),
        set_index=1,
    )
    second = OutputCanvasImageItem(
        image_id=second_id,
        image_meta=_image_meta(2),
        set_index=1,
    )
    return OutputCanvasProjection(
        sources=(
            OutputCanvasSourceGroup(
                source_key="first-source",
                label="First source",
                images_by_set={1: first},
            ),
            OutputCanvasSourceGroup(
                source_key="second-source",
                label="Second source",
                images_by_set={1: second},
            ),
        ),
        active_source_key="first-source",
        active_set_index=1,
        active_uuid=first.image_id,
        set_count=1,
    )


def _session(
    boundary: CanvasRouteSessionBoundaryPort,
    projection: OutputCanvasProjection,
) -> OutputCanvasSession:
    """Bind one current Output route session for a test projection."""

    return bind_output_canvas_session(
        boundary,
        workflow_id="workflow",
        projection=projection,
        image_metadata_lookup={
            item.image_id: item.image_meta
            for source in projection.sources
            for item in source.images_by_set.values()
        },
    )


def _image_meta(number: int) -> ImageMeta:
    """Return minimal valid metadata for one generated source image."""

    return ImageMeta(
        workflow_name="workflow",
        cube_name="Source",
        image_number=number,
        suffix="",
        path="",
        source_key="source",
    )


def _source_preview_lane(
    preview_id: UUID,
    session: OutputCanvasSession,
) -> OutputPreviewLane:
    """Return one accepted source-preview lane for the active Output session."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.source(
            workflow_id="workflow",
            generation_run_id="run",
            prompt_id="prompt",
            source_key="source",
            scene_key=None,
        ),
        preview_id=preview_id,
        image=_image("green"),
        source_label="Source",
        client_id="client",
        session_revision=session.revision,
    )


def _live_preview_event(image: QImage) -> LivePreviewEvent:
    """Build one strict source preview emitted by the Comfy feedback path."""

    event = LivePreviewEvent.from_update(
        PreviewImageUpdate(
            workflow_id="workflow",
            image=image,
            generation_run_id="run",
            prompt_id="prompt",
            client_id="client",
            node_id="preview-node",
            source_key="source",
            source_label="Source",
        )
    )
    assert event is not None
    return event


def _scene_preview_lane(
    preview_id: UUID,
    session: OutputCanvasSession,
) -> OutputPreviewLane:
    """Return one accepted scene-overview preview lane for the active session."""

    return OutputPreviewLane(
        key=OutputPreviewLaneKey.scene(
            workflow_id="workflow",
            generation_run_id="run",
            prompt_id="prompt",
            scene_run_id="scene-run",
            scene_key="scene",
            source_key="source",
        ),
        preview_id=preview_id,
        image=_image("blue"),
        source_label="Source",
        client_id="client",
        session_revision=session.revision,
        scene_title="Scene",
        scene_order=0,
        scene_count=2,
        accepted_for_overview=True,
    )

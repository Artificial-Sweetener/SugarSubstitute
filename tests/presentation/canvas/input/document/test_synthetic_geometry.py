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

"""Verify synthetic resize intent at the real CuteCanvas adapter boundary."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from PySide6.QtCore import QObject, QSize, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication
from cutecanvas import (
    CanvasAnchor,
    CanvasResamplingMode,
    CuteCanvas,
)

from substitute.domain.workflow import (
    CanvasDimensions,
    SyntheticCanvasAnchor,
    SyntheticCanvasResamplingMode,
    SyntheticCanvasResizeRequest,
    SyntheticCanvasResizeScope,
)
from substitute.presentation.canvas.input.synthetic_canvas_geometry_adapter import (
    SyntheticCanvasGeometryAdapter,
    SyntheticCanvasGeometryResult,
    SyntheticCanvasGeometryStatus,
)
from tests.support.cutecanvas.input_document import InputDocumentFactory
from tests.support.qt.semantic_wait import wait_for_qt_condition


class _CanvasGeometryFake(QObject):
    """Record public CuteCanvas geometry calls without reimplementing policy."""

    canvasResamplingCompleted = Signal(object)
    sceneChanged = Signal(object)

    def __init__(self) -> None:
        """Initialize current revision and geometry call history."""

        super().__init__()
        self.stale = False
        self.resize_calls: list[tuple[UUID, QSize, CanvasAnchor]] = []
        self.resampling_calls: list[tuple[UUID, QSize, CanvasResamplingMode, UUID]] = []

    def document(self) -> _CanvasGeometryFake:
        """Return the fake revision owner."""

        return self

    def resolve_content(self, _reference: object) -> SimpleNamespace:
        """Return the configured revision state."""

        return SimpleNamespace(stale=self.stale)

    def resizeCanvasBounds(
        self,
        composition_id: UUID,
        size: QSize,
        *,
        anchor: CanvasAnchor,
    ) -> bool:
        """Record one lossless bounds request."""

        self.resize_calls.append((composition_id, QSize(size), anchor))
        return True

    def requestCanvasResampling(
        self,
        composition_id: UUID,
        size: QSize,
        *,
        mode: CanvasResamplingMode,
    ) -> UUID:
        """Record one whole-layer resampling request."""

        request_id = uuid4()
        self.resampling_calls.append((composition_id, QSize(size), mode, request_id))
        return request_id

    def cancelCanvasResampling(self, _request_id: UUID) -> bool:
        """Accept cancellation for an in-flight test request."""

        return True

    def listMasksForComposition(self, _composition_id: UUID) -> tuple[object, ...]:
        """Expose no masks for enum-forwarding unit scenarios."""

        return ()


@pytest.mark.parametrize("anchor", tuple(SyntheticCanvasAnchor))
def test_canvas_only_forwards_every_anchor_without_resampling(
    anchor: SyntheticCanvasAnchor,
) -> None:
    """Every spatial option should map exactly to CuteCanvas bounds geometry."""

    canvas = _CanvasGeometryFake()
    _app()
    adapter = SyntheticCanvasGeometryAdapter(cast(CuteCanvas, canvas))
    composition_id = uuid4()
    results: list[SyntheticCanvasGeometryResult] = []
    adapter.operationCompleted.connect(results.append)

    adapter.begin(
        composition_id=composition_id,
        expected_revision=cast(
            Any,
            SimpleNamespace(composition_id=composition_id),
        ),
        request=SyntheticCanvasResizeRequest(
            dimensions=CanvasDimensions(1200, 900),
            scope=SyntheticCanvasResizeScope.CANVAS_ONLY,
            anchor=anchor,
        ),
    )
    wait_for_qt_condition(lambda: len(results) == 1)

    assert canvas.resize_calls == [
        (composition_id, QSize(1200, 900), CanvasAnchor(anchor.value))
    ]
    assert canvas.resampling_calls == []
    assert results[0].status is SyntheticCanvasGeometryStatus.COMPLETED


@pytest.mark.parametrize("mode", tuple(SyntheticCanvasResamplingMode))
def test_all_layers_forwards_resampling_quality_and_terminal_result(
    mode: SyntheticCanvasResamplingMode,
) -> None:
    """Fast and smooth options should retain request identity through completion."""

    canvas = _CanvasGeometryFake()
    adapter = SyntheticCanvasGeometryAdapter(cast(CuteCanvas, canvas))
    composition_id = uuid4()
    results: list[SyntheticCanvasGeometryResult] = []
    adapter.operationCompleted.connect(results.append)
    operation = adapter.begin(
        composition_id=composition_id,
        expected_revision=cast(
            Any,
            SimpleNamespace(composition_id=composition_id),
        ),
        request=SyntheticCanvasResizeRequest(
            dimensions=CanvasDimensions(800, 600),
            scope=SyntheticCanvasResizeScope.CANVAS_AND_LAYERS,
            resampling_mode=mode,
        ),
    )
    assert canvas.resampling_calls == [
        (
            composition_id,
            QSize(800, 600),
            CanvasResamplingMode(mode.value),
            operation.operation_id,
        )
    ]

    canvas.canvasResamplingCompleted.emit(
        SimpleNamespace(
            request_id=operation.operation_id,
            composition_id=composition_id,
            target_size=QSize(800, 600),
            succeeded=True,
            status="completed",
            changed=True,
            message="",
        )
    )

    assert len(results) == 1
    assert results[0].operation == operation
    assert results[0].status is SyntheticCanvasGeometryStatus.COMPLETED
    assert results[0].dimensions == CanvasDimensions(800, 600)


def test_real_cutecanvas_resamples_every_regional_mask_and_undoes_atomically(
    input_document_factory: InputDocumentFactory,
) -> None:
    """Whole-layer mode should preserve mask identities through resize and undo."""

    _app()
    document = input_document_factory()
    canvas = document.canvas
    image_id = uuid4()
    image = QImage(12, 10, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    assert document.ensure_image_cached(image_id, image, None)
    assert document.set_current_image_id(image_id)
    mask_ids = (
        document.create_blank_mask(image_id, QSize(12, 10)),
        document.create_blank_mask(image_id, QSize(12, 10)),
    )
    assert all(mask_id is not None for mask_id in mask_ids)
    resolved_mask_ids = cast(tuple[UUID, UUID], mask_ids)
    original_masks_by_layer = {
        mask.layer_id: mask.mask_id
        for mask in canvas.listMasksForComposition(image_id)
        if mask.layer_id is not None
    }
    adapter = SyntheticCanvasGeometryAdapter(canvas)
    results: list[SyntheticCanvasGeometryResult] = []
    adapter.operationCompleted.connect(results.append)
    try:
        adapter.begin(
            composition_id=image_id,
            expected_revision=adapter.capture_revision(image_id),
            request=SyntheticCanvasResizeRequest(
                dimensions=CanvasDimensions(24, 20),
                scope=SyntheticCanvasResizeScope.CANVAS_AND_LAYERS,
                resampling_mode=SyntheticCanvasResamplingMode.SMOOTH,
            ),
        )
        wait_for_qt_condition(lambda: bool(results), timeout_ms=5000)

        assert results[0].status is SyntheticCanvasGeometryStatus.COMPLETED
        assert adapter.current_dimensions(image_id) == CanvasDimensions(24, 20)
        resized_masks_by_layer = {
            mask.layer_id: mask.mask_id
            for mask in canvas.listMasksForComposition(image_id)
            if mask.layer_id is not None
        }
        assert resized_masks_by_layer.keys() == original_masks_by_layer.keys()
        assert set(results[0].mask_id_remap) == {
            (original_masks_by_layer[layer_id], resized_masks_by_layer[layer_id])
            for layer_id in original_masks_by_layer
        }
        resized_mask_ids = tuple(resized_masks_by_layer.values())
        exported_masks = tuple(
            document.export_mask_image(mask_id) for mask_id in resized_mask_ids
        )
        assert all(mask is not None for mask in exported_masks)
        assert all(
            mask.size() == QSize(24, 20) for mask in exported_masks if mask is not None
        )

        assert adapter.undo_last_geometry_edit()
        assert adapter.current_dimensions(image_id) == CanvasDimensions(12, 10)
        assert {
            mask.mask_id for mask in canvas.listMasksForComposition(image_id)
        } == set(resolved_mask_ids)
    finally:
        document.close()


def _app() -> QApplication:
    """Return the process application for Qt delivery."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)

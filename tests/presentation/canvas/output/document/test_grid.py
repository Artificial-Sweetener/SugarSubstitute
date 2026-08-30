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

"""Verify Output grid, detail, and comparison presentation contracts."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4
from pytest import approx
from PySide6.QtGui import (
    QColor,
    QImage,
)
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from cutecanvas import ExecutionRuntime
from tests.support.qt.lifecycle import destroy_qt_object

from .rendering_support import (
    _wait_for_rendered_color,
    _assert_rendered_horizontal_seam,
)
from .support import _app


def test_output_grid_preserves_compact_native_tile_packing(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Pack Output grid tiles by their native aspect with compact gutters."""
    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_ids = tuple(uuid4() for _index in range(3))
    image = QImage(1144, 1608, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    try:
        for image_id in image_ids:
            assert document.admit_image(image_id, image)
        document.workspace.resize(848, 946)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()

        snapshot = document.workspace.gridSnapshot()
        assert snapshot is not None
        assert (snapshot.columns, snapshot.rows) == (2, 2)
        first, second, final = snapshot.frames
        expected_raster_gutter = 2
        expected_scene_gutter = max(2.0, 3216.0 / 511.0)
        stable_scale = min(
            (848.0 - expected_raster_gutter) / (2.0 * 1144.0),
            (946.0 - expected_raster_gutter) / (2.0 * 1608.0),
        )
        assert first.cell.width() == approx(1144.0 * stable_scale, abs=0.1)
        assert first.cell.height() == approx(1608.0 * stable_scale, abs=0.1)
        assert second.cell.x() - first.cell.right() == approx(
            expected_scene_gutter * first.cell.width() / 1144.0,
            abs=0.1,
        )
        assert final.cell.center().x() == snapshot.viewport.center().x()

        first_target = document.workspace.canvasFor(cast(UUID, first.target_id))
        second_target = document.workspace.canvasFor(cast(UUID, second.target_id))
        final_target = document.workspace.canvasFor(cast(UUID, final.target_id))
        assert first_target is not None
        assert second_target is not None
        assert final_target is not None
        first_mount = first_target.parentWidget()
        second_mount = second_target.parentWidget()
        final_mount = final_target.parentWidget()
        assert first_mount is not None
        assert second_mount is not None
        assert final_mount is not None
        for target in (first_target, second_target, final_target):
            assert _wait_for_rendered_color(app, target, QColor("red"))
        assert second_mount.x() - first_mount.x() - first_mount.width() == (
            expected_raster_gutter
        )
        assert final_mount.y() - first_mount.y() - first_mount.height() == (
            expected_raster_gutter
        )
        shared_left = max(first_mount.x(), final_mount.x())
        shared_right = min(
            first_mount.x() + first_mount.width(),
            final_mount.x() + final_mount.width(),
        )
        assert shared_left < shared_right
        _assert_rendered_horizontal_seam(
            document.workspace,
            (shared_left + shared_right) // 2,
            first_mount.y() + first_mount.height(),
            expected_raster_gutter,
        )

        document.workspace.resize(856, 954)
        app.processEvents()
        assert second_mount.x() - first_mount.x() - first_mount.width() == (
            expected_raster_gutter
        )
        assert final_mount.y() - first_mount.y() - first_mount.height() == (
            expected_raster_gutter
        )
        shared_left = max(first_mount.x(), final_mount.x())
        shared_right = min(
            first_mount.x() + first_mount.width(),
            final_mount.x() + final_mount.width(),
        )
        assert shared_left < shared_right
        _assert_rendered_horizontal_seam(
            document.workspace,
            (shared_left + shared_right) // 2,
            first_mount.y() + first_mount.height(),
            expected_raster_gutter,
        )
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_grid_preserves_legacy_mixed_source_cells(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Mount each mixed-source image in its old common grid cell."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_ids = tuple(uuid4() for _index in range(3))
    images = (
        QImage(1144, 1608, QImage.Format.Format_RGB32),
        QImage(1608, 1144, QImage.Format.Format_RGB32),
        QImage(1144, 1608, QImage.Format.Format_RGB32),
    )
    for image, color in zip(images, ("red", "blue", "green"), strict=True):
        image.fill(QColor(color))
    try:
        for image_id, image in zip(image_ids, images, strict=True):
            assert document.admit_image(image_id, image)
        document.workspace.resize(1600, 850)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()

        snapshot = document.workspace.gridSnapshot()
        assert snapshot is not None
        assert (snapshot.columns, snapshot.rows) == (3, 1)
        first, middle, final = snapshot.frames
        assert first.cell == middle.cell.translated(-middle.cell.x(), 0.0)
        assert middle.content.top() > first.content.top()
        assert middle.content.bottom() < first.content.bottom()

        mounts = []
        for frame in snapshot.frames:
            target = document.workspace.canvasFor(cast(UUID, frame.target_id))
            assert target is not None
            mount = target.parentWidget()
            assert mount is not None
            mounts.append(mount)
        assert mounts[0].size() == mounts[1].size() == mounts[2].size()
        assert mounts[1].x() - mounts[0].x() - mounts[0].width() == 2
        assert mounts[2].x() - mounts[1].x() - mounts[1].width() == 2

        document.workspace.resize(1608, 858)
        app.processEvents()
        resized = document.workspace.gridSnapshot()
        assert resized is not None
        resized_mounts = []
        for frame in resized.frames:
            target = document.workspace.canvasFor(cast(UUID, frame.target_id))
            assert target is not None
            mount = target.parentWidget()
            assert mount is not None
            resized_mounts.append(mount)
        assert (
            resized_mounts[0].size()
            == resized_mounts[1].size()
            == resized_mounts[2].size()
        )
        assert (
            resized_mounts[1].x() - resized_mounts[0].x() - resized_mounts[0].width()
            == 2
        )
        assert (
            resized_mounts[2].x() - resized_mounts[1].x() - resized_mounts[1].width()
            == 2
        )
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_grid_keeps_fixed_gutters_and_equal_tiles_during_width_resize(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep equal Output images aligned through one-pixel width changes."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_ids = tuple(uuid4() for _index in range(3))
    image = QImage(960, 1344, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    try:
        for image_id in image_ids:
            assert document.admit_image(image_id, image)
        document.workspace.resize(1500, 1000)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()

        composition_ids = tuple(
            document.composition_id_for(image_id) for image_id in image_ids
        )
        assert all(composition_id is not None for composition_id in composition_ids)
        targets = tuple(
            document.workspace.canvasFor(composition_id)
            for composition_id in composition_ids
            if composition_id is not None
        )
        assert all(target is not None for target in targets)
        mounts = tuple(
            target.parentWidget() for target in targets if target is not None
        )
        assert len(mounts) == 3
        assert all(mount is not None for mount in mounts)

        for width in range(1500, 1511):
            document.workspace.resize(width, 1000)
            app.processEvents()
            snapshot = document.workspace.gridSnapshot()
            assert snapshot is not None
            assert (snapshot.columns, snapshot.rows) == (3, 1)
            first, second, final = mounts
            assert first is not None
            assert second is not None
            assert final is not None
            assert first.width() == second.width() == final.width()
            assert first.height() == second.height() == final.height()
            assert second.x() - first.x() - first.width() == 2
            assert final.x() - second.x() - second.width() == 2
    finally:
        document.close()
        destroy_qt_object(document)


def test_output_grid_keeps_two_row_targets_relatively_fixed_during_width_resize(
    execution_runtime: ExecutionRuntime,
) -> None:
    """Keep a centered final-row target fixed relative to its full grid row."""

    app = _app()
    document = OutputCanvasDocument(execution_runtime=execution_runtime)
    image_ids = tuple(uuid4() for _index in range(3))
    image = QImage(960, 1344, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    try:
        for image_id in image_ids:
            assert document.admit_image(image_id, image)
        document.workspace.resize(920, 1000)
        document.workspace.show()
        assert document.present_grid(image_ids)
        app.processEvents()
        composition_ids = tuple(
            document.composition_id_for(image_id) for image_id in image_ids
        )
        assert all(composition_id is not None for composition_id in composition_ids)
        targets = tuple(
            document.workspace.canvasFor(composition_id)
            for composition_id in composition_ids
            if composition_id is not None
        )
        assert all(target is not None for target in targets)
        mounts = tuple(
            target.parentWidget() for target in targets if target is not None
        )
        assert len(mounts) == 3
        assert all(mount is not None for mount in mounts)

        relative_final_x: int | None = None
        for width in range(920, 931):
            document.workspace.resize(width, 1000)
            app.processEvents()
            snapshot = document.workspace.gridSnapshot()
            assert snapshot is not None
            assert (snapshot.columns, snapshot.rows) == (2, 2)
            first, second, final = mounts
            assert first is not None
            assert second is not None
            assert final is not None
            assert first.size() == second.size() == final.size()
            assert second.x() - first.x() - first.width() == 2
            assert final.y() - first.y() - first.height() == 2
            current_relative_final_x = final.x() - first.x()
            if relative_final_x is None:
                relative_final_x = current_relative_final_x
            assert current_relative_final_x == relative_final_x
    finally:
        document.close()
        destroy_qt_object(document)

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

"""Render deterministic motion frames through a real production editor panel."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEasingCurve, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped]  # noqa: E402

from substitute.presentation.editor.panel.rendering.render_reconciler import (  # noqa: E402
    EditorPanelRenderReconciler,
)
from substitute.presentation.editor.panel.surface_motion import (  # noqa: E402
    EditorSurfaceMotionController,
)
from substitute.presentation.motion import MotionClock  # noqa: E402
from substitute.presentation.editor.panel.view import EditorPanel  # noqa: E402
from tools.editor_panel_baseline.rendering import (  # noqa: E402
    BACKGROUNDS,
    HOST_SIZE,
    register_headless_fluent_font,
    save_editor_panel_host,
    settle_editor_panel_layout,
)
from tools.editor_panel_baseline.sources import (  # noqa: E402
    sha256,
    validate_base_cube_sources,
)
from tools.editor_projection_rig.fixtures import read_json, write_json  # noqa: E402
from tools.editor_projection_rig.production_fixture import (  # noqa: E402
    workflow_from_fixture,
)
from tools.editor_projection_rig.production_mount import (  # noqa: E402
    build_editor_panel,
    build_trace_shell,
)
from tools.editor_projection_rig.production_signatures import (  # noqa: E402
    parent_chain_violations,
)
from tools.editor_projection_rig.qt_harness import (  # noqa: E402
    create_hidden_host,
    drain_qt_events,
    drain_until,
    ensure_qapplication,
)
from tools.editor_projection_rig.scenarios import WORKFLOW_SDXL_BASELINE  # noqa: E402
from tools.editor_projection_rig.trace_events import (  # noqa: E402
    ProjectionTraceRecorder,
)
from substitute.presentation.shell.main_window_editor_surface_adapter import (  # noqa: E402
    MainWindowEditorSurfaceAdapter,
)


class ManualEasedMotionClock:
    """Drive production easing at deterministic normalized frame positions."""

    def __init__(self) -> None:
        """Initialize an idle clock without retained callbacks."""

        self._running = False
        self._duration_ms = 0
        self._curve = QEasingCurve(QEasingCurve.Type.Linear)
        self._frame: Callable[[float], None] | None = None
        self._finished: Callable[[], None] | None = None

    def start(
        self,
        *,
        duration_ms: int,
        easing: QEasingCurve.Type | QEasingCurve,
        frame: Callable[[float], None],
        finished: Callable[[], None],
    ) -> None:
        """Retain one timeline and its exact production easing curve."""

        self._running = True
        self._duration_ms = duration_ms
        self._curve = QEasingCurve(easing)
        self._frame = frame
        self._finished = finished

    def stop(self) -> None:
        """Stop the active timeline without publishing completion."""

        self._running = False
        self._frame = None
        self._finished = None

    def is_running(self) -> bool:
        """Return whether a transition is awaiting deterministic frames."""

        return self._running

    def advance(self, progress: float) -> None:
        """Publish one eased frame at a normalized wall-clock position."""

        if self._frame is None:
            raise RuntimeError("Cannot advance an idle motion clock.")
        clamped = max(0.0, min(1.0, progress))
        eased = self._curve.valueForProgress(clamped)
        self._frame(self._duration_ms * eased)

    def finish(self) -> None:
        """Publish natural completion exactly once."""

        finished = self._finished
        self._running = False
        self._frame = None
        self._finished = None
        if finished is not None:
            finished()


def render_editor_panel_motion(
    *,
    fixture_path: Path,
    output_dir: Path,
    base_cubes_dir: Path,
) -> dict[str, Any]:
    """Render real-editor reorder, removal, and insertion frame sequences."""

    application = ensure_qapplication()
    application.setProperty("substitute.reduce_motion", False)
    register_headless_fluent_font()
    setTheme(Theme.DARK)
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture = read_json(fixture_path)
    validate_base_cube_sources(
        scenarios=(WORKFLOW_SDXL_BASELINE,),
        fixtures_dir=fixture_path.parent,
        base_cubes_dir=base_cubes_dir,
    )
    host, panel = _mount_editor(fixture)
    clock = ManualEasedMotionClock()
    motion = EditorSurfaceMotionController(
        panel,
        clock_factory=lambda _parent: cast(MotionClock, clock),
    )
    reconciler = EditorPanelRenderReconciler(panel)
    frame_records: list[dict[str, Any]] = []
    try:
        cube_widgets = cast(dict[str, object], getattr(panel, "cube_widgets"))
        aliases = list(cube_widgets)
        if len(aliases) < 3:
            raise RuntimeError("Motion qualification requires at least three cubes.")
        original_widgets = dict(cube_widgets)
        reordered = [aliases[1], aliases[0], *aliases[2:]]
        generation = motion.prepare_cube_reorder()
        _apply_cube_order(panel, reconciler, reordered, original_widgets)
        if not motion.present_cube_reorder(generation):
            raise RuntimeError("Reorder motion did not start.")
        _capture_sequence(host, output_dir, "reorder", clock, frame_records)

        removed_alias = reordered[0]
        generation = motion.prepare_cube_removal(removed_alias)
        remaining = [alias for alias in reordered if alias != removed_alias]
        _apply_cube_order(panel, reconciler, remaining, original_widgets)
        cube_widgets.pop(removed_alias, None)
        if not motion.present_cube_removal(generation):
            raise RuntimeError("Removal motion did not start.")
        _capture_sequence(host, output_dir, "remove", clock, frame_records)

        generation = motion.prepare_cube_insert(removed_alias)
        cube_widgets[removed_alias] = original_widgets[removed_alias]
        inserted = [removed_alias, *remaining]
        _apply_cube_order(panel, reconciler, inserted, original_widgets)
        if not motion.present_cube_insert(
            generation=generation,
            cube_alias=removed_alias,
            cube_widget=original_widgets[removed_alias],
        ):
            raise RuntimeError("Insertion motion did not start.")
        _capture_sequence(host, output_dir, "insert", clock, frame_records)

        contact_sheet = output_dir / "motion-contact-sheet.png"
        _write_contact_sheet(frame_records, contact_sheet)
        manifest: dict[str, Any] = {
            "schema_version": 1,
            "platform": "Windows offscreen Qt",
            "fixture": str(fixture_path.resolve()),
            "base_cubes": str(base_cubes_dir.resolve()),
            "theme": "dark",
            "host_size": list(HOST_SIZE),
            "frames": frame_records,
            "contact_sheet": str(contact_sheet.resolve()),
            "contact_sheet_sha256": sha256(contact_sheet),
            "parent_chain_violations": parent_chain_violations(panel),
            "telemetry": {
                "plans_started": motion.telemetry.plans_started,
                "plans_finished": motion.telemetry.plans_finished,
                "plans_cancelled": motion.telemetry.plans_cancelled,
                "last_capture_target_count": (
                    motion.telemetry.last_capture_target_count
                ),
                "last_capture_target_pixels": (
                    motion.telemetry.last_capture_target_pixels
                ),
            },
        }
        if manifest["parent_chain_violations"]:
            raise RuntimeError("Motion qualification found parent-chain violations.")
        if len({record["sha256"] for record in frame_records}) < 6:
            raise RuntimeError("Motion frames did not contain enough visual change.")
        write_json(output_dir / "manifest.json", manifest)
        return manifest
    finally:
        host.close()
        host.deleteLater()
        drain_qt_events(25)


def _mount_editor(fixture: dict[str, Any]) -> tuple[QWidget, EditorPanel]:
    """Mount and fully project one production editor fixture offscreen."""

    workflow, definitions = workflow_from_fixture(fixture)
    recorder = ProjectionTraceRecorder()
    host = create_hidden_host(show_window=True)
    host.resize(*HOST_SIZE)
    host.setObjectName("EditorPanelMotionHost")
    host.setStyleSheet("QWidget#EditorPanelMotionHost { background-color: #202020; }")
    panel = build_editor_panel(
        host=host,
        workflow_id=WORKFLOW_SDXL_BASELINE.workflow_id,
        definitions=definitions,
    )
    trace_shell = build_trace_shell(
        workflow_id=WORKFLOW_SDXL_BASELINE.workflow_id,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
    )
    panel.mainwindow = trace_shell.shell
    result = MainWindowEditorSurfaceAdapter(trace_shell.shell).refresh_editor_surface(
        WORKFLOW_SDXL_BASELINE.workflow_id,
        force=False,
        on_complete=lambda _result: setattr(trace_shell, "projection_complete", True),
    )
    if result.error:
        raise RuntimeError(f"Motion fixture projection failed: {result.error}")
    drain_until(lambda: trace_shell.projection_complete, max_turns=1_000)
    settle_editor_panel_layout(host, panel)
    return host, panel


def _apply_cube_order(
    panel: EditorPanel,
    reconciler: EditorPanelRenderReconciler,
    aliases: Sequence[str],
    widgets: dict[str, object],
) -> None:
    """Commit one cube order without processing an intermediate paint event."""

    panel._stack_order = list(aliases)
    reconciler.repopulate_layout(tuple((alias, widgets[alias]) for alias in aliases))
    layout = getattr(panel, "_layout")
    layout.activate()


def _capture_sequence(
    host: QWidget,
    output_dir: Path,
    name: str,
    clock: ManualEasedMotionClock,
    records: list[dict[str, Any]],
) -> None:
    """Capture start, middle, end-overlay, and settled transition states."""

    for label, progress in (("start", 0.0), ("middle", 0.5), ("end", 1.0)):
        clock.advance(progress)
        QApplication.processEvents()
        _capture_frame(host, output_dir, name, label, records)
    clock.finish()
    QApplication.processEvents()
    _capture_frame(host, output_dir, name, "settled", records)


def _capture_frame(
    host: QWidget,
    output_dir: Path,
    transition: str,
    phase: str,
    records: list[dict[str, Any]],
) -> None:
    """Write one opaque real-editor frame and record its evidence."""

    path = output_dir / f"{transition}-{phase}.png"
    save_editor_panel_host(host, path, background=BACKGROUNDS["dark"])
    records.append(
        {
            "transition": transition,
            "phase": phase,
            "path": str(path.resolve()),
            "sha256": sha256(path),
        }
    )


def _write_contact_sheet(records: Sequence[dict[str, Any]], path: Path) -> None:
    """Compose labeled motion frames into one compact inspection image."""

    columns = 4
    tile_width = 480
    tile_height = 333
    label_height = 28
    rows = (len(records) + columns - 1) // columns
    sheet = QImage(
        columns * tile_width,
        rows * (tile_height + label_height),
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    sheet.fill(QColor("#151515"))
    painter = QPainter(sheet)
    painter.setPen(QColor("#FFFFFF"))
    painter.setFont(QFont("Segoe UI", 11))
    for index, record in enumerate(records):
        image = QImage(str(record["path"]))
        row, column = divmod(index, columns)
        x = column * tile_width
        y = row * (tile_height + label_height)
        painter.drawImage(
            x,
            y,
            image.scaled(
                tile_width,
                tile_height,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ),
        )
        label = f"{record['transition']} · {record['phase']}"
        painter.drawText(x + 10, y + tile_height + 20, label)
    painter.end()
    if not sheet.save(str(path), "PNG"):  # type: ignore[call-overload]
        raise OSError(f"Could not save motion contact sheet: {path}")


__all__ = ["ManualEasedMotionClock", "render_editor_panel_motion"]

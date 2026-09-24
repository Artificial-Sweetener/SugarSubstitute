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

"""Render deterministic editor-panel images through the production surface."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402
from qfluentwidgets import Theme, setTheme  # type: ignore[import-untyped]  # noqa: E402

from substitute.presentation.editor.panel.view import EditorPanel  # noqa: E402
from substitute.presentation.editor.panel.widgets.scroll_surface import (  # noqa: E402
    EditorPanelScrollSurface,
)
from substitute.presentation.shell.main_window_editor_surface_adapter import (  # noqa: E402
    MainWindowEditorSurfaceAdapter,
)
from tools.editor_panel_baseline.environment import runtime_environment  # noqa: E402
from tools.editor_panel_baseline.sources import (  # noqa: E402
    git_output,
    sha256,
    validate_base_cube_sources,
)
from tools.editor_projection_rig.fixtures import (  # noqa: E402
    read_json,
    stable_json_hash,
    workflow_fixture_path,
    write_json,
)
from tools.editor_projection_rig.production_mount import (  # noqa: E402
    build_editor_panel,
    build_trace_shell,
)
from tools.editor_projection_rig.production_signatures import (  # noqa: E402
    parent_chain_violations,
    signature_from_panel,
)
from tools.editor_projection_rig.production_fixture import (  # noqa: E402
    workflow_from_fixture,
)
from tools.editor_projection_rig.qt_harness import (  # noqa: E402
    create_hidden_host,
    drain_qt_events,
    drain_until,
    ensure_qapplication,
)
from tools.editor_projection_rig.scenarios import WorkflowScenario  # noqa: E402
from tools.editor_projection_rig.trace_events import (  # noqa: E402
    ProjectionTraceRecorder,
)

HOST_SIZE = (1440, 1000)
THEMES = {"light": Theme.LIGHT, "dark": Theme.DARK}
BACKGROUNDS = {"light": QColor("#F3F3F3"), "dark": QColor("#202020")}


def render_editor_panel_baseline(
    *,
    scenarios: Sequence[WorkflowScenario],
    fixtures_dir: Path,
    output_dir: Path,
    base_cubes_dir: Path,
    theme_names: Sequence[str],
    position_names: Sequence[str],
) -> dict[str, Any]:
    """Render the requested production editor matrix and write its manifest."""

    application = ensure_qapplication()
    application.setProperty("substitute.reduce_motion", True)
    _register_headless_fluent_font()
    output_dir.mkdir(parents=True, exist_ok=True)
    fixture_records = validate_base_cube_sources(
        scenarios=scenarios,
        fixtures_dir=fixtures_dir,
        base_cubes_dir=base_cubes_dir,
    )
    renders: list[dict[str, Any]] = []
    for scenario in scenarios:
        fixture = read_json(workflow_fixture_path(fixtures_dir, scenario.workflow_id))
        for theme_name in theme_names:
            renders.extend(
                _render_scenario_theme(
                    scenario=scenario,
                    fixture=fixture,
                    output_dir=output_dir,
                    theme_name=theme_name,
                    position_names=position_names,
                )
            )
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "environment": runtime_environment(),
        "sugarsubstitute_commit": git_output(Path.cwd(), "rev-parse", "HEAD"),
        "base_cubes": {
            "path": str(base_cubes_dir.resolve()),
            "commit": git_output(base_cubes_dir, "rev-parse", "HEAD"),
            "status": git_output(base_cubes_dir, "status", "--short", "--branch"),
            "fixtures": fixture_records,
        },
        "host_size": list(HOST_SIZE),
        "reduced_motion": True,
        "renders": renders,
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest


def _render_scenario_theme(
    *,
    scenario: WorkflowScenario,
    fixture: Mapping[str, Any],
    output_dir: Path,
    theme_name: str,
    position_names: Sequence[str],
) -> list[dict[str, Any]]:
    """Mount one production editor and capture requested viewport positions."""

    theme = THEMES.get(theme_name)
    if theme is None:
        raise ValueError(f"Unknown editor baseline theme {theme_name!r}.")
    setTheme(theme)
    drain_qt_events(5)
    workflow, definitions = workflow_from_fixture(fixture)
    recorder = ProjectionTraceRecorder()
    host = create_hidden_host(show_window=True)
    host.resize(*HOST_SIZE)
    host.setObjectName("EditorPanelBaselineHost")
    host.setStyleSheet(
        f"QWidget#EditorPanelBaselineHost {{ background-color: "
        f"{BACKGROUNDS[theme_name].name()}; }}"
    )
    panel = build_editor_panel(
        host=host,
        workflow_id=scenario.workflow_id,
        definitions=definitions,
    )
    trace_shell = build_trace_shell(
        workflow_id=scenario.workflow_id,
        workflow=workflow,
        panel=panel,
        recorder=recorder,
    )
    panel.mainwindow = trace_shell.shell
    try:
        result = MainWindowEditorSurfaceAdapter(
            trace_shell.shell
        ).refresh_editor_surface(
            scenario.workflow_id,
            force=False,
            on_complete=lambda _result: setattr(
                trace_shell,
                "projection_complete",
                True,
            ),
        )
        if result.error:
            raise RuntimeError(
                f"Editor baseline projection failed for {scenario.workflow_id}: "
                f"{result.error}"
            )
        drain_until(lambda: trace_shell.projection_complete, max_turns=1_000)
        _settle_layout(host, panel)
        scroll_surface = cast(
            EditorPanelScrollSurface,
            getattr(panel, "scroll"),
        )
        scrollbar = scroll_surface.verticalScrollBar()
        scroll_values = scroll_capture_values(
            maximum=scrollbar.maximum(),
            position_names=position_names,
        )
        geometry = _surface_geometry(panel)
        signature = signature_from_panel(
            workflow_id=scenario.workflow_id,
            workflow=workflow,
            panel=panel,
        ).to_json()
        renders: list[dict[str, Any]] = []
        for position_name, scroll_value in scroll_values:
            scrollbar.setValue(scroll_value)
            drain_qt_events(20)
            path = output_dir / (
                f"{scenario.workflow_id}-{theme_name}-{position_name}.png"
            )
            _save_host(host, path, background=BACKGROUNDS[theme_name])
            renders.append(
                {
                    "scenario_id": scenario.workflow_id,
                    "theme": theme_name,
                    "position": position_name,
                    "scroll_value": scrollbar.value(),
                    "scroll_maximum": scrollbar.maximum(),
                    "path": str(path.resolve()),
                    "sha256": sha256(path),
                    "width": HOST_SIZE[0],
                    "height": HOST_SIZE[1],
                    "fixture_hash": stable_json_hash(fixture),
                    "settled_signature_hash": stable_json_hash(signature),
                    "parent_chain_violations": parent_chain_violations(panel),
                    "geometry": geometry,
                }
            )
        return renders
    finally:
        host.close()
        host.deleteLater()
        drain_qt_events(25)


def scroll_capture_values(
    *,
    maximum: int,
    position_names: Sequence[str],
) -> tuple[tuple[str, int], ...]:
    """Resolve named viewport positions to deterministic scrollbar values."""

    positions = {
        "top": 0,
        "middle": max(0, maximum // 2),
        "bottom": max(0, maximum),
    }
    resolved: list[tuple[str, int]] = []
    for name in position_names:
        if name not in positions:
            raise ValueError(f"Unknown editor baseline position {name!r}.")
        resolved.append((name, positions[name]))
    return tuple(resolved)


def _settle_layout(host: QWidget, panel: EditorPanel) -> None:
    """Settle host, viewport, and content geometry before pixel capture."""

    host.ensurePolished()
    host_layout = host.layout()
    if host_layout is not None:
        host_layout.activate()
    panel.ensurePolished()
    panel_layout = panel.layout()
    if panel_layout is not None:
        panel_layout.activate()
    scroll_surface = cast(EditorPanelScrollSurface, getattr(panel, "scroll"))
    content = scroll_surface.widget()
    if content is not None:
        content_layout = content.layout()
        if content_layout is not None:
            content_layout.activate()
    scroll_surface.schedule_metrics_refresh()
    drain_qt_events(50)


def _surface_geometry(panel: EditorPanel) -> dict[str, Any]:
    """Return stable content-relative cube, card, and field geometry."""

    scroll_surface = cast(EditorPanelScrollSurface, getattr(panel, "scroll"))
    content = scroll_surface.widget()
    if content is None:
        raise RuntimeError("Editor baseline panel has no scroll content.")

    def rectangle(widget: QWidget) -> list[int]:
        """Return one widget rectangle in content coordinates."""

        origin = widget.mapTo(content, QPoint())
        return [origin.x(), origin.y(), widget.width(), widget.height()]

    cube_widgets = cast(Mapping[str, object], getattr(panel, "cube_widgets"))
    cube_geometry = {
        alias: rectangle(widget)
        for alias, widget in sorted(cube_widgets.items())
        if isinstance(widget, QWidget)
    }
    card_wrappers = cast(
        Mapping[tuple[str, str], object],
        getattr(panel, "card_wrappers"),
    )
    card_geometry = {
        f"{identity[0]}::{identity[1]}": rectangle(widget)
        for identity, widget in sorted(card_wrappers.items())
        if isinstance(identity, tuple)
        and len(identity) == 2
        and isinstance(widget, QWidget)
    }
    input_widgets = cast(
        Mapping[tuple[str, str, str], object],
        getattr(panel, "input_widgets_by_field_key"),
    )
    field_geometry = {
        "::".join(identity): rectangle(widget)
        for identity, widget in sorted(input_widgets.items())
        if len(identity) == 3 and isinstance(widget, QWidget)
    }
    return {
        "content_size": [content.width(), content.height()],
        "viewport_size": [
            scroll_surface.viewport().width(),
            scroll_surface.viewport().height(),
        ],
        "cubes": cube_geometry,
        "cards": card_geometry,
        "fields": field_geometry,
    }


def _save_host(host: QWidget, path: Path, *, background: QColor) -> None:
    """Save one opaque host render to a PNG file."""

    image = QImage(host.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(background)
    painter = QPainter(image)
    host.render(painter, QPoint())
    painter.end()
    # PySide6 6.9 requires str here despite its stub declaring a bytes-like format.
    if not image.save(str(path), "PNG"):  # type: ignore[call-overload]
        raise OSError(f"Could not save editor baseline render: {path}")


def _register_headless_fluent_font() -> None:
    """Register Segoe UI for deterministic Windows offscreen rendering."""

    windows_root = os.environ.get("WINDIR")
    if not windows_root:
        raise RuntimeError("WINDIR is required for editor baseline rendering.")
    font_path = Path(windows_root) / "Fonts/segoeui.ttf"
    if QFontDatabase.addApplicationFont(str(font_path)) < 0:
        raise RuntimeError(f"Could not register baseline font: {font_path}")

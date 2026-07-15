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

"""Tests for prompt editor performance reorder measurement helpers."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.devtools.prompt_editor_performance.qt_app import (
    prompt_performance_application,
)
from substitute.devtools.prompt_editor_performance.reorder_measurements import (
    build_reorder_measurement_state,
    capture_reorder_interaction_counts,
    chip_drop_target_global,
    current_reorder_overlay,
    overlay_chip_by_segment_index,
    reorder_cache_counts,
    surface_for,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.overlays import SegmentReorderOverlay


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REORDER_MEASUREMENTS_MODULE = (
    PROJECT_ROOT
    / "substitute"
    / "devtools"
    / "prompt_editor_performance"
    / "reorder_measurements.py"
)
FORBIDDEN_IMPORT_PREFIXES = (
    "qfluentwidgets",
    "qframelesswindow",
    "tests",
    "tools",
)


class _CounterSource:
    """Expose mixed reorder counters for capture filtering tests."""

    def reorder_performance_counters(self) -> dict[str, object]:
        """Return counters that include unsupported values."""

        return {
            "drag_move_count": 3,
            "max_drag_move_ms": 1.25,
            "ignored": object(),
        }


class _EditorWithCounters:
    """Expose mixed cache counters for reorder counter filtering tests."""

    def __init__(self, surface: object) -> None:
        """Store the marker surface returned by ``surface_for``."""

        self._surface = surface

    def reorder_geometry_cache_counters(self) -> dict[str, object]:
        """Return counters that include unsupported values."""

        return {
            "base_chip_geometry_cache_hit_count": 5,
            "preview_chip_geometry_cache_miss_count": 2,
            "ignored": object(),
        }


def test_prompt_editor_performance_reorder_measurements_imports_no_tools() -> None:
    """Reorder measurements may use Qt and presentation, but not tests or tools."""

    imported_modules = _imported_module_names(
        ast.parse(REORDER_MEASUREMENTS_MODULE.read_text(encoding="utf-8"))
    )

    forbidden_imports = {
        imported_module
        for imported_module in imported_modules
        for forbidden_import in FORBIDDEN_IMPORT_PREFIXES
        if imported_module == forbidden_import
        or imported_module.startswith(f"{forbidden_import}.")
    }

    assert forbidden_imports == set()


def test_overlay_chip_lookup_uses_segment_index_property() -> None:
    """Overlay chip lookup should select chips by source segment index."""

    prompt_performance_application()
    overlay = QWidget()
    first_chip = QWidget(overlay)
    first_chip.setObjectName("segmentChip")
    first_chip.setProperty("segmentIndex", 0)
    second_chip = QWidget(overlay)
    second_chip.setObjectName("segmentChip")
    second_chip.setProperty("segmentIndex", 2)

    try:
        assert (
            overlay_chip_by_segment_index(
                cast(SegmentReorderOverlay, overlay),
                2,
            )
            is second_chip
        )
        with pytest.raises(RuntimeError, match="Missing reorder chip"):
            overlay_chip_by_segment_index(cast(SegmentReorderOverlay, overlay), 1)
    finally:
        overlay.deleteLater()


def test_chip_drop_target_global_uses_leading_or_trailing_edge() -> None:
    """Drop-target points should be stable near the requested chip edge."""

    prompt_performance_application()
    chip = QWidget()
    chip.resize(80, 20)

    try:
        assert chip.mapFromGlobal(chip_drop_target_global(chip)).x() == 4
        assert (
            chip.mapFromGlobal(chip_drop_target_global(chip, trailing=True)).x() == 76
        )
    finally:
        chip.deleteLater()


def test_capture_reorder_interaction_counts_keeps_numeric_values() -> None:
    """Interaction counter capture should preserve only numeric counters."""

    extra_counts: dict[str, int | float] = {}

    capture_reorder_interaction_counts(_CounterSource(), extra_counts)

    assert extra_counts == {
        "drag_move_count": 3,
        "max_drag_move_ms": 1.25,
    }


def test_build_reorder_measurement_state_prepares_preview_and_base_state() -> None:
    """Geometry-cache measurement state should include preview and base layouts."""

    state = build_reorder_measurement_state("blue hair, red eyes, smile")

    assert state.preview_state.dragged_chip_index == 1
    assert state.preview_state.base_drag_snapshot is not None
    assert state.preview_layout_view is not state.base_drag_layout_view


def test_current_reorder_overlay_requires_real_overlay() -> None:
    """Overlay lookup should fail closed when Alt did not create the overlay."""

    editor = cast(PromptEditor, object())

    with pytest.raises(RuntimeError, match="Alt did not create"):
        current_reorder_overlay(editor)


def test_surface_and_reorder_cache_helpers_read_editor_ports() -> None:
    """Editor helper reads should filter counters without mutating the editor."""

    marker_surface = object()
    editor = _EditorWithCounters(marker_surface)

    assert surface_for(cast(PromptEditor, editor)) is marker_surface
    assert reorder_cache_counts(cast(PromptEditor, editor)) == {
        "base_chip_geometry_cache_hit_count": 5,
        "preview_chip_geometry_cache_miss_count": 2,
    }


def _imported_module_names(tree: ast.AST) -> set[str]:
    """Return all imported module names from one Python source tree."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules

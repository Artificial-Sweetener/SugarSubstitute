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

"""Calculate shell layout capture and restore values for MainWindow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

MIN_EDITOR_PANEL_WIDTH = 320
MIN_CANVAS_PANEL_WIDTH = 120
MIN_SIDE_PANEL_WIDTH = 240
MIN_OUTPUT_PANEL_HEIGHT = 120


@dataclass(frozen=True, slots=True)
class LiveShellLayoutMeasurements:
    """Carry live shell dimensions captured from Qt widgets."""

    main_splitter_sizes: tuple[int, ...]
    editor_output_splitter_sizes: tuple[int, ...]
    cube_stack_width: int | None
    editor_panel_width: int | None
    canvas_panel_width: int | None
    side_panel_visible: bool
    side_panel_width: int | None
    output_panel_height: int | None


@dataclass(frozen=True, slots=True)
class CanonicalShellLayout:
    """Represent durable user-intent shell dimensions."""

    cube_stack_width: int | None
    editor_panel_width: int | None
    canvas_panel_width: int | None
    side_panel_visible: bool
    side_panel_width: int | None
    output_panel_height: int | None


@dataclass(frozen=True, slots=True)
class ShellLayoutRestorePlan:
    """Describe concrete widget sizes to apply during shell restore."""

    main_splitter_sizes: tuple[int, ...]
    editor_output_splitter_sizes: tuple[int, ...]
    cube_stack_width: int
    cube_stack_compact: bool
    side_panel_visible: bool
    side_panel_width: int | None
    output_panel_height: int | None
    used_legacy_splitter: bool
    clamped_fields: tuple[str, ...] = ()


class ShellLayoutSnapshotProtocol(Protocol):
    """Describe shell snapshot fields needed by presentation restore arithmetic."""

    @property
    def main_splitter_sizes(self) -> tuple[int, ...]:
        """Return raw main splitter sizes."""
        ...

    @property
    def editor_output_splitter_sizes(self) -> tuple[int, ...]:
        """Return raw editor/output splitter sizes."""
        ...

    @property
    def cube_stack_width(self) -> int | None:
        """Return durable cube-stack width."""
        ...

    @property
    def editor_panel_width(self) -> int | None:
        """Return durable editor panel width."""
        ...

    @property
    def canvas_panel_width(self) -> int | None:
        """Return durable canvas panel width."""
        ...

    @property
    def cube_stack_compact(self) -> bool:
        """Return whether the cube stack should be compact."""
        ...

    @property
    def output_panel_height(self) -> int | None:
        """Return durable output panel height."""
        ...

    @property
    def side_panel_visible(self) -> bool:
        """Return whether the side panel should be visible."""
        ...

    @property
    def side_panel_width(self) -> int | None:
        """Return durable side panel width."""
        ...

    @property
    def generation_queue_panel_visible(self) -> bool:
        """Return whether the generation queue panel should be visible."""
        ...

    @property
    def generation_queue_panel_width(self) -> int | None:
        """Return durable generation queue panel width."""
        ...


def canonical_layout_from_measurements(
    measurements: LiveShellLayoutMeasurements,
) -> CanonicalShellLayout:
    """Build canonical shell layout dimensions from live measurements."""

    return CanonicalShellLayout(
        cube_stack_width=_positive_or_none(measurements.cube_stack_width),
        editor_panel_width=_positive_or_none(measurements.editor_panel_width),
        canvas_panel_width=_positive_or_none(measurements.canvas_panel_width),
        side_panel_visible=measurements.side_panel_visible,
        side_panel_width=_positive_or_none(measurements.side_panel_width),
        output_panel_height=_positive_or_none(measurements.output_panel_height),
    )


def build_shell_layout_restore_plan(
    snapshot: ShellLayoutSnapshotProtocol,
    *,
    available_width: int,
    target_pane_count: int,
    compact_cube_stack_width: int,
    expanded_cube_stack_width: int,
) -> ShellLayoutRestorePlan:
    """Create stable splitter sizes from canonical snapshot layout facts."""

    target_count = max(2, target_pane_count)
    clamped_fields: list[str] = []
    cube_stack_width = _cube_stack_width_for_snapshot(
        snapshot,
        compact_cube_stack_width=compact_cube_stack_width,
        expanded_cube_stack_width=expanded_cube_stack_width,
        clamped_fields=clamped_fields,
    )
    side_visible = (
        snapshot.side_panel_visible or snapshot.generation_queue_panel_visible
    )
    side_width = _side_width_for_snapshot(snapshot, side_visible, clamped_fields)
    side_pane_width = (side_width or 0) if side_visible and target_count >= 3 else 0

    if _has_canonical_main_layout(snapshot):
        main_sizes = _canonical_main_splitter_sizes(
            snapshot,
            available_width=max(1, available_width),
            target_pane_count=target_count,
            cube_stack_width=cube_stack_width,
            side_pane_width=side_pane_width,
            clamped_fields=clamped_fields,
        )
        used_legacy_splitter = False
    else:
        main_sizes = _legacy_main_splitter_sizes(
            snapshot.main_splitter_sizes,
            available_width=max(1, available_width),
            target_pane_count=target_count,
            clamped_fields=clamped_fields,
        )
        used_legacy_splitter = True

    return ShellLayoutRestorePlan(
        main_splitter_sizes=main_sizes,
        editor_output_splitter_sizes=tuple(snapshot.editor_output_splitter_sizes),
        cube_stack_width=cube_stack_width,
        cube_stack_compact=snapshot.cube_stack_compact,
        side_panel_visible=side_visible,
        side_panel_width=side_width if side_visible else None,
        output_panel_height=_positive_or_none(snapshot.output_panel_height),
        used_legacy_splitter=used_legacy_splitter,
        clamped_fields=tuple(clamped_fields),
    )


def _cube_stack_width_for_snapshot(
    snapshot: ShellLayoutSnapshotProtocol,
    *,
    compact_cube_stack_width: int,
    expanded_cube_stack_width: int,
    clamped_fields: list[str],
) -> int:
    """Return the cube-stack chrome width implied by restored mode."""

    expected_width = (
        compact_cube_stack_width
        if snapshot.cube_stack_compact
        else expanded_cube_stack_width
    )
    if snapshot.cube_stack_width not in (None, expected_width):
        clamped_fields.append("cube_stack_width")
    return expected_width


def _side_width_for_snapshot(
    snapshot: ShellLayoutSnapshotProtocol,
    side_visible: bool,
    clamped_fields: list[str],
) -> int | None:
    """Return side-panel width when the side panel should be visible."""

    if not side_visible:
        return None
    width = snapshot.side_panel_width or snapshot.generation_queue_panel_width
    if width is None:
        return MIN_SIDE_PANEL_WIDTH
    if width < MIN_SIDE_PANEL_WIDTH:
        clamped_fields.append("side_panel_width")
        return MIN_SIDE_PANEL_WIDTH
    return width


def _canonical_main_splitter_sizes(
    snapshot: ShellLayoutSnapshotProtocol,
    *,
    available_width: int,
    target_pane_count: int,
    cube_stack_width: int,
    side_pane_width: int,
    clamped_fields: list[str],
) -> tuple[int, ...]:
    """Return main splitter sizes derived from canonical dimensions."""

    side_width = min(side_pane_width, max(0, available_width - 1))
    available_without_side = max(1, available_width - side_width)
    editor_width = snapshot.editor_panel_width
    if editor_width is None:
        editor_width = _editor_width_from_legacy(snapshot, cube_stack_width)
    if editor_width is None:
        editor_width = max(
            MIN_EDITOR_PANEL_WIDTH,
            available_without_side - (snapshot.canvas_panel_width or 0),
        )
    if editor_width < MIN_EDITOR_PANEL_WIDTH:
        clamped_fields.append("editor_panel_width")
        editor_width = MIN_EDITOR_PANEL_WIDTH

    desired_left_width = cube_stack_width + editor_width
    max_left_width = max(1, available_without_side - MIN_CANVAS_PANEL_WIDTH)
    if desired_left_width > max_left_width:
        clamped_fields.append("editor_panel_width")
        desired_left_width = max(1, max_left_width)
    canvas_width = max(1, available_without_side - desired_left_width)
    if canvas_width < MIN_CANVAS_PANEL_WIDTH and available_without_side > (
        desired_left_width
    ):
        clamped_fields.append("canvas_panel_width")
        canvas_width = MIN_CANVAS_PANEL_WIDTH

    sizes = [desired_left_width, canvas_width]
    if target_pane_count >= 3:
        sizes.append(side_width)
    return tuple(sizes)


def _legacy_main_splitter_sizes(
    legacy_sizes: tuple[int, ...],
    *,
    available_width: int,
    target_pane_count: int,
    clamped_fields: list[str],
) -> tuple[int, ...]:
    """Return best-effort sizes for a snapshot without canonical layout fields."""

    if len(legacy_sizes) >= 2:
        sizes = [max(0, int(size)) for size in legacy_sizes[:target_pane_count]]
    else:
        left_width = max(1, available_width - MIN_CANVAS_PANEL_WIDTH)
        sizes = [left_width, MIN_CANVAS_PANEL_WIDTH]
    while len(sizes) < target_pane_count:
        sizes.append(0)
    if len(sizes) >= 2 and sizes[1] < MIN_CANVAS_PANEL_WIDTH:
        reducible = max(0, sizes[0] - MIN_EDITOR_PANEL_WIDTH)
        needed = MIN_CANVAS_PANEL_WIDTH - sizes[1]
        transfer = min(reducible, needed)
        if transfer > 0:
            sizes[0] -= transfer
            sizes[1] += transfer
            clamped_fields.append("main_splitter_sizes")
    return tuple(sizes)


def _editor_width_from_legacy(
    snapshot: ShellLayoutSnapshotProtocol,
    cube_stack_width: int,
) -> int | None:
    """Infer editor panel width from legacy left-pane splitter data."""

    if not snapshot.main_splitter_sizes:
        return None
    return max(0, int(snapshot.main_splitter_sizes[0]) - cube_stack_width)


def _has_canonical_main_layout(snapshot: ShellLayoutSnapshotProtocol) -> bool:
    """Return whether a snapshot includes user-owned main-layout dimensions."""

    return any(
        value is not None
        for value in (
            snapshot.editor_panel_width,
            snapshot.canvas_panel_width,
            snapshot.side_panel_width,
        )
    )


def _positive_or_none(value: int | None) -> int | None:
    """Return a positive integer value or None for unavailable dimensions."""

    if value is None or value < 0:
        return None
    return value


__all__ = [
    "CanonicalShellLayout",
    "LiveShellLayoutMeasurements",
    "MIN_CANVAS_PANEL_WIDTH",
    "MIN_EDITOR_PANEL_WIDTH",
    "MIN_OUTPUT_PANEL_HEIGHT",
    "MIN_SIDE_PANEL_WIDTH",
    "ShellLayoutRestorePlan",
    "ShellLayoutSnapshotProtocol",
    "build_shell_layout_restore_plan",
    "canonical_layout_from_measurements",
]

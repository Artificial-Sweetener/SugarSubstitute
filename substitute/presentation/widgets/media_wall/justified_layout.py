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

"""Solve justified thumbnail wall rows from aspect-ratio inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

TPayload = TypeVar("TPayload")

DEFAULT_JUSTIFIED_WALL_ASPECT_RATIO = 0.72
PICKER_JUSTIFIED_WALL_GUTTER = 4
_MIN_ALLOWED_ASPECT_RATIO = 0.2
_MAX_ALLOWED_ASPECT_RATIO = 6.0
_MIN_TILE_WIDTH = 40.0
_COST_COMPARISON_EPSILON = 0.001
_ROW_HEIGHT_SWING_WEIGHT = 0.18
_FINAL_ROW_HEIGHT_SWING_WEIGHT = 1.1
_FINAL_UNUSED_WIDTH_WEIGHT = 0.18
_FINAL_SHORT_ROW_WEIGHT = 6.5
_FINAL_EXCESS_ITEM_WEIGHT = 65.0
_FINAL_RAGGED_ROW_PENALTY = 18.0
_SINGLETON_JUSTIFIED_ROW_PENALTY = 24.0
_RELAXED_JUSTIFIED_CLAMP_WEIGHT = 12.0
_PREFERRED_TRAILING_ITEM_COUNT = 7


@dataclass(frozen=True, slots=True)
class PickerJustifiedWallProfile:
    """Define the compact picker wall row profile."""

    target_row_height: float = 132.0
    min_row_height: float = 104.0
    max_row_height: float = 172.0
    minimum_tile_width: float = 84.0
    gutter: float = PICKER_JUSTIFIED_WALL_GUTTER


@dataclass(frozen=True, slots=True)
class JustifiedLayoutItem(Generic[TPayload]):
    """Represent one item participating in justified wall layout."""

    aspect_ratio: float
    payload: TPayload


@dataclass(frozen=True, slots=True)
class JustifiedLayoutInput(Generic[TPayload]):
    """Describe one justified wall layout request."""

    items: tuple[JustifiedLayoutItem[TPayload], ...]
    container_width: float
    target_row_height: float
    min_row_height: float
    max_row_height: float
    gutter: float
    minimum_tile_width: float
    max_items_per_row: int | None = None


@dataclass(frozen=True, slots=True)
class JustifiedLayoutRowItem(Generic[TPayload]):
    """Describe one solved item box in a justified row."""

    width: float
    height: float
    payload: TPayload


@dataclass(frozen=True, slots=True)
class JustifiedLayoutRow(Generic[TPayload]):
    """Describe one solved justified wall row."""

    height: float
    items: tuple[JustifiedLayoutRowItem[TPayload], ...]


@dataclass(frozen=True, slots=True)
class _SolverOptions:
    """Store normalized solver options."""

    container_width: float
    target_row_height: float
    min_row_height: float
    max_row_height: float
    gutter: float
    max_items_per_row: int
    allow_relaxed_bounded_justification: bool
    allow_bounded_singleton_rows: bool


@dataclass(frozen=True, slots=True)
class _RowCandidate(Generic[TPayload]):
    """Store one legal row candidate while solving the partition."""

    start_index: int
    end_index_exclusive: int
    items: tuple[JustifiedLayoutItem[TPayload], ...]
    height: float
    widths: tuple[float, ...]
    coverage: float
    kind: str
    cost: float


def normalize_aspect_ratio(candidate: float) -> float:
    """Normalize unknown or invalid aspect ratios to a safe default."""

    if not isinstance(candidate, int | float) or candidate <= 0:
        return DEFAULT_JUSTIFIED_WALL_ASPECT_RATIO
    if candidate != candidate or candidate in {float("inf"), float("-inf")}:
        return DEFAULT_JUSTIFIED_WALL_ASPECT_RATIO
    return _clamp(candidate, _MIN_ALLOWED_ASPECT_RATIO, _MAX_ALLOWED_ASPECT_RATIO)


def build_justified_rows(
    layout_input: JustifiedLayoutInput[TPayload],
) -> tuple[JustifiedLayoutRow[TPayload], ...]:
    """Solve the whole wall so middle rows justify and the trailing row may rag."""

    if not layout_input.items or layout_input.container_width <= 0:
        return ()
    safe_min_row_height = max(1.0, layout_input.min_row_height)
    safe_max_row_height = max(safe_min_row_height, layout_input.max_row_height)
    safe_target_row_height = _clamp(
        layout_input.target_row_height,
        safe_min_row_height,
        safe_max_row_height,
    )
    safe_gutter = max(0.0, layout_input.gutter)
    safe_container_width = max(1.0, layout_input.container_width)
    safe_minimum_tile_width = max(_MIN_TILE_WIDTH, layout_input.minimum_tile_width)
    derived_max_items_per_row = max(
        1,
        int(
            (safe_container_width + safe_gutter)
            // (safe_minimum_tile_width + safe_gutter)
        ),
    )
    requested_max = layout_input.max_items_per_row
    safe_max_items_per_row = (
        derived_max_items_per_row
        if requested_max is None
        else int(_clamp(requested_max, 1, derived_max_items_per_row))
    )
    normalized_items = tuple(
        JustifiedLayoutItem(
            aspect_ratio=normalize_aspect_ratio(item.aspect_ratio),
            payload=item.payload,
        )
        for item in layout_input.items
    )
    strict_rows = _solve_candidate_partition(
        normalized_items,
        _SolverOptions(
            container_width=safe_container_width,
            target_row_height=safe_target_row_height,
            min_row_height=safe_min_row_height,
            max_row_height=safe_max_row_height,
            gutter=safe_gutter,
            max_items_per_row=safe_max_items_per_row,
            allow_relaxed_bounded_justification=False,
            allow_bounded_singleton_rows=False,
        ),
    )
    if strict_rows is not None:
        return strict_rows
    return (
        _solve_candidate_partition(
            normalized_items,
            _SolverOptions(
                container_width=safe_container_width,
                target_row_height=safe_target_row_height,
                min_row_height=safe_min_row_height,
                max_row_height=safe_max_row_height,
                gutter=safe_gutter,
                max_items_per_row=safe_max_items_per_row,
                allow_relaxed_bounded_justification=True,
                allow_bounded_singleton_rows=safe_max_items_per_row == 1,
            ),
        )
        or ()
    )


def _solve_candidate_partition(
    items: tuple[JustifiedLayoutItem[TPayload], ...],
    options: _SolverOptions,
) -> tuple[JustifiedLayoutRow[TPayload], ...] | None:
    """Solve a candidate graph and return ``None`` when no partition is legal."""

    candidates_by_start_index = _build_candidates_by_start_index(items, options)
    best_cost_by_index = [float("inf")] * (len(items) + 1)
    best_candidate_by_index: list[_RowCandidate[TPayload] | None] = [None] * (
        len(items) + 1
    )
    best_cost_by_index[len(items)] = 0.0
    for start_index in range(len(items) - 1, -1, -1):
        for candidate in candidates_by_start_index[start_index]:
            suffix_cost = best_cost_by_index[candidate.end_index_exclusive]
            if suffix_cost == float("inf"):
                continue
            next_candidate = best_candidate_by_index[candidate.end_index_exclusive]
            total_cost = (
                candidate.cost
                + _measure_transition_cost(candidate, next_candidate, len(items))
                + suffix_cost
            )
            if total_cost < best_cost_by_index[start_index] - _COST_COMPARISON_EPSILON:
                best_cost_by_index[start_index] = total_cost
                best_candidate_by_index[start_index] = candidate
    if best_cost_by_index[0] == float("inf"):
        return None
    rows: list[JustifiedLayoutRow[TPayload]] = []
    current_index = 0
    while current_index < len(items):
        selected_candidate = best_candidate_by_index[current_index]
        if selected_candidate is None:
            return None
        rows.append(_build_row_output(selected_candidate))
        current_index = selected_candidate.end_index_exclusive
    return tuple(rows)


def _build_candidates_by_start_index(
    items: tuple[JustifiedLayoutItem[TPayload], ...],
    options: _SolverOptions,
) -> tuple[tuple[_RowCandidate[TPayload], ...], ...]:
    """Enumerate legal contiguous row candidates by start index."""

    candidates_by_start_index: list[tuple[_RowCandidate[TPayload], ...]] = []
    for start_index in range(len(items)):
        row_candidates: list[_RowCandidate[TPayload]] = []
        maximum_end_index_exclusive = min(
            len(items),
            start_index + options.max_items_per_row,
        )
        for end_index_exclusive in range(
            start_index + 1,
            maximum_end_index_exclusive + 1,
        ):
            candidate_items = items[start_index:end_index_exclusive]
            justified = _build_justified_candidate(
                candidate_items,
                start_index,
                end_index_exclusive,
                options,
                len(items),
            )
            if justified is not None:
                row_candidates.append(justified)
            ragged = _build_ragged_final_candidate(
                candidate_items,
                start_index,
                end_index_exclusive,
                options,
                len(items),
            )
            if ragged is not None:
                row_candidates.append(ragged)
        candidates_by_start_index.append(tuple(row_candidates))
    return tuple(candidates_by_start_index)


def _build_justified_candidate(
    items: tuple[JustifiedLayoutItem[TPayload], ...],
    start_index: int,
    end_index_exclusive: int,
    options: _SolverOptions,
    total_item_count: int,
) -> _RowCandidate[TPayload] | None:
    """Build one legal justified row candidate."""

    justified_height = _calculate_justified_row_height(
        items,
        options.container_width,
        options.gutter,
    )
    is_final_row = end_index_exclusive == total_item_count
    needs_bounded_height = not (
        options.min_row_height <= justified_height <= options.max_row_height
    )
    may_use_relaxed_bounded_height = not is_final_row and (
        options.allow_relaxed_bounded_justification
        or (options.allow_bounded_singleton_rows and len(items) == 1)
    )
    if needs_bounded_height and not may_use_relaxed_bounded_height:
        return None
    bounded_height = (
        _clamp(justified_height, options.min_row_height, options.max_row_height)
        if needs_bounded_height
        else justified_height
    )
    widths = _build_justified_widths(
        items,
        bounded_height,
        options.container_width,
        options.gutter,
    )
    coverage = _measure_row_coverage(widths, options.container_width, options.gutter)
    if not is_final_row and abs(coverage - 1.0) > 0.01:
        return None
    candidate = _RowCandidate(
        start_index=start_index,
        end_index_exclusive=end_index_exclusive,
        items=items,
        height=bounded_height,
        widths=widths,
        coverage=coverage,
        kind="justified",
        cost=0.0,
    )
    base_cost = (
        _measure_final_row_cost(candidate, options)
        if is_final_row
        else abs(bounded_height - options.target_row_height)
    )
    clamp_penalty = (
        abs(bounded_height - justified_height) * _RELAXED_JUSTIFIED_CLAMP_WEIGHT
        if not is_final_row
        else 0.0
    )
    singleton_penalty = (
        _SINGLETON_JUSTIFIED_ROW_PENALTY
        if not is_final_row and len(items) == 1
        else 0.0
    )
    return _replace_candidate_cost(
        candidate,
        base_cost + clamp_penalty + singleton_penalty,
    )


def _build_ragged_final_candidate(
    items: tuple[JustifiedLayoutItem[TPayload], ...],
    start_index: int,
    end_index_exclusive: int,
    options: _SolverOptions,
    total_item_count: int,
) -> _RowCandidate[TPayload] | None:
    """Build one trailing ragged-row candidate for a suffix slice."""

    if end_index_exclusive != total_item_count:
        return None
    ragged_height = _clamp(
        min(
            options.target_row_height,
            _calculate_justified_row_height(
                items,
                options.container_width,
                options.gutter,
            ),
        ),
        1.0,
        options.max_row_height,
    )
    widths = tuple(
        max(1.0, normalize_aspect_ratio(item.aspect_ratio) * ragged_height)
        for item in items
    )
    candidate = _RowCandidate(
        start_index=start_index,
        end_index_exclusive=end_index_exclusive,
        items=items,
        height=ragged_height,
        widths=widths,
        coverage=_measure_row_coverage(widths, options.container_width, options.gutter),
        kind="ragged-final",
        cost=0.0,
    )
    return _replace_candidate_cost(
        candidate, _measure_final_row_cost(candidate, options)
    )


def _replace_candidate_cost(
    candidate: _RowCandidate[TPayload],
    cost: float,
) -> _RowCandidate[TPayload]:
    """Return a copy of one candidate with its computed cost."""

    return _RowCandidate(
        start_index=candidate.start_index,
        end_index_exclusive=candidate.end_index_exclusive,
        items=candidate.items,
        height=candidate.height,
        widths=candidate.widths,
        coverage=candidate.coverage,
        kind=candidate.kind,
        cost=cost,
    )


def _build_row_output(
    candidate: _RowCandidate[TPayload],
) -> JustifiedLayoutRow[TPayload]:
    """Convert one chosen candidate into the public row contract."""

    return JustifiedLayoutRow(
        height=candidate.height,
        items=tuple(
            JustifiedLayoutRowItem(
                width=max(1.0, candidate.widths[index]),
                height=candidate.height,
                payload=item.payload,
            )
            for index, item in enumerate(candidate.items)
        ),
    )


def _sum_aspect_ratios(
    items: tuple[JustifiedLayoutItem[TPayload], ...],
) -> float:
    """Sum normalized aspect ratios for row-fit math."""

    return sum(normalize_aspect_ratio(item.aspect_ratio) for item in items)


def _calculate_gap_width(item_count: int, gutter: float) -> float:
    """Calculate total gap pixels for one row item count."""

    return max(0, item_count - 1) * gutter


def _calculate_justified_row_height(
    items: tuple[JustifiedLayoutItem[TPayload], ...],
    container_width: float,
    gutter: float,
) -> float:
    """Solve the natural justified height that fills the container width."""

    return (container_width - _calculate_gap_width(len(items), gutter)) / max(
        _sum_aspect_ratios(items),
        0.001,
    )


def _build_justified_widths(
    items: tuple[JustifiedLayoutItem[TPayload], ...],
    row_height: float,
    container_width: float,
    gutter: float,
) -> tuple[float, ...]:
    """Build width-fill tile boxes for one justified row."""

    widths = [normalize_aspect_ratio(item.aspect_ratio) * row_height for item in items]
    if not widths:
        return ()
    available_width = container_width - _calculate_gap_width(len(items), gutter)
    width_delta = available_width - sum(widths)
    widths[-1] = max(1.0, widths[-1] + width_delta)
    return tuple(widths)


def _measure_row_coverage(
    widths: tuple[float, ...],
    container_width: float,
    gutter: float,
) -> float:
    """Measure how much of the container width one row visually occupies."""

    occupied_width = sum(widths) + _calculate_gap_width(len(widths), gutter)
    return occupied_width / max(container_width, 1.0)


def _measure_final_row_cost(
    candidate: _RowCandidate[TPayload],
    options: _SolverOptions,
) -> float:
    """Apply final-row penalties after height deviation."""

    cost = abs(candidate.height - options.target_row_height)
    trailing_comfort_min_height = max(
        options.min_row_height * 0.9,
        options.target_row_height * 0.82,
    )
    unused_width = max(0.0, (1.0 - candidate.coverage) * options.container_width)
    short_row_deficit = max(0.0, trailing_comfort_min_height - candidate.height)
    excess_trailing_items = max(
        0,
        len(candidate.items) - _PREFERRED_TRAILING_ITEM_COUNT,
    )
    cost += unused_width * _FINAL_UNUSED_WIDTH_WEIGHT
    cost += short_row_deficit * _FINAL_SHORT_ROW_WEIGHT
    cost += excess_trailing_items * _FINAL_EXCESS_ITEM_WEIGHT
    if candidate.kind == "ragged-final":
        cost += _FINAL_RAGGED_ROW_PENALTY
    return cost


def _measure_transition_cost(
    current_candidate: _RowCandidate[TPayload],
    next_candidate: _RowCandidate[TPayload] | None,
    item_count: int,
) -> float:
    """Penalize abrupt row-height swings, especially into the final row."""

    if next_candidate is None:
        return 0.0
    height_delta = abs(current_candidate.height - next_candidate.height)
    next_candidate_is_final_row = next_candidate.end_index_exclusive == item_count
    return height_delta * (
        _FINAL_ROW_HEIGHT_SWING_WEIGHT
        if next_candidate_is_final_row
        else _ROW_HEIGHT_SWING_WEIGHT
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Clamp one numeric value inside inclusive boundaries."""

    return min(maximum, max(minimum, value))


__all__ = [
    "DEFAULT_JUSTIFIED_WALL_ASPECT_RATIO",
    "PICKER_JUSTIFIED_WALL_GUTTER",
    "PickerJustifiedWallProfile",
    "JustifiedLayoutInput",
    "JustifiedLayoutItem",
    "JustifiedLayoutRow",
    "JustifiedLayoutRowItem",
    "build_justified_rows",
    "normalize_aspect_ratio",
]

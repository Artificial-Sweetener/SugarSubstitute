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

"""Infer semantic width/height field pairs from node input keys."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DimensionSide = Literal["width", "height"]


@dataclass(frozen=True)
class DimensionFieldPair:
    """Describe one matched width/height field pair with a shared semantic stem."""

    stem: str
    width_key: str
    height_key: str


@dataclass
class _DimensionCandidate:
    """Track one possible dimension pair while preserving first discovery order."""

    stem: str
    first_index: int
    width_key: str | None = None
    height_key: str | None = None


def infer_dimension_field_pairs(
    input_keys: tuple[str, ...],
) -> tuple[DimensionFieldPair, ...]:
    """Return ordered width/height pairs inferred from node input keys.

    The matcher intentionally accepts only exact ``width``/``height`` keys or
    exact ``<stem>_width``/``<stem>_height`` suffix pairs. This keeps unrelated
    fields such as ``source_width`` and ``target_height`` from being grouped.
    """

    candidates: dict[str, _DimensionCandidate] = {}
    for index, input_key in enumerate(input_keys):
        parsed = _parse_dimension_key(input_key)
        if parsed is None:
            continue
        stem, side = parsed
        candidate = candidates.get(stem)
        if candidate is None:
            candidate = _DimensionCandidate(stem=stem, first_index=index)
            candidates[stem] = candidate
        if side == "width" and candidate.width_key is None:
            candidate.width_key = input_key
        elif side == "height" and candidate.height_key is None:
            candidate.height_key = input_key

    pairs: list[DimensionFieldPair] = []
    for candidate in sorted(
        candidates.values(),
        key=lambda candidate: candidate.first_index,
    ):
        if candidate.width_key is None or candidate.height_key is None:
            continue
        pairs.append(
            DimensionFieldPair(
                stem=candidate.stem,
                width_key=candidate.width_key,
                height_key=candidate.height_key,
            )
        )
    return tuple(pairs)


def infer_dimension_field_groups(
    input_keys: tuple[str, ...],
    occupied_fields: frozenset[str] = frozenset(),
) -> tuple[tuple[str, ...], ...]:
    """Return inferred dimension groups that do not reuse occupied fields."""

    groups: list[tuple[str, str]] = []
    for pair in infer_dimension_field_pairs(input_keys):
        if pair.width_key in occupied_fields or pair.height_key in occupied_fields:
            continue
        groups.append((pair.width_key, pair.height_key))
    return tuple(groups)


def _parse_dimension_key(input_key: str) -> tuple[str, DimensionSide] | None:
    """Return a dimension stem and side for exact supported field-key patterns."""

    if input_key == "width":
        return "", "width"
    if input_key == "height":
        return "", "height"
    if input_key.endswith("_width"):
        stem = input_key[: -len("_width")]
        if stem:
            return stem, "width"
    if input_key.endswith("_height"):
        stem = input_key[: -len("_height")]
        if stem:
            return stem, "height"
    return None


__all__ = [
    "DimensionFieldPair",
    "infer_dimension_field_groups",
    "infer_dimension_field_pairs",
]

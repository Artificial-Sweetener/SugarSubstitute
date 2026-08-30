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

"""Contract tests for first-load cube seed initialization."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from substitute.application.cubes.seed_initialization import (
    initialize_fresh_seed_controls,
)


def _cube_buffer(
    *,
    symbol: str = "N1",
    class_type: str = "KSampler",
    seed_value: object = "missing",
    minimum: int = 0,
    maximum: int = 999,
) -> dict[str, Any]:
    """Return a minimal runtime cube buffer with one surface-backed seed control."""

    inputs: dict[str, object] = {}
    if seed_value != "missing":
        inputs["seed"] = seed_value
    return {
        "nodes": {
            symbol: {
                "class_type": class_type,
                "inputs": inputs,
            }
        },
        "surface": {
            "controls": [
                {
                    "control_id": f"{symbol}.seed",
                    "symbol": symbol,
                    "input_name": "seed",
                    "class_type": class_type,
                    "value_type": "number",
                }
            ]
        },
        "definitions": {
            class_type: {
                "input": {
                    "required": {
                        "seed": [
                            "INT",
                            {
                                "default": 0,
                                "min": minimum,
                                "max": maximum,
                            },
                        ]
                    }
                }
            }
        },
    }


def _constant_randint(value: int) -> Callable[[int, int], int]:
    """Return a deterministic randint replacement for seed tests."""

    def randint(_minimum: int, _maximum: int) -> int:
        """Return the configured deterministic value."""

        return value

    return randint


def _seed_value(cube_buffer: dict[str, Any], symbol: str = "N1") -> object:
    """Return one node seed from a test cube buffer."""

    return cube_buffer["nodes"][symbol]["inputs"]["seed"]


def test_initialize_fresh_seed_controls_writes_missing_surface_seed() -> None:
    """Missing surface-backed seed controls should receive a random seed."""

    cube_buffer = _cube_buffer()

    result = initialize_fresh_seed_controls(
        cube_buffer,
        buffer_patch=None,
        randint=_constant_randint(123),
    )

    assert _seed_value(cube_buffer) == 123
    assert result.initialized_count == 1
    assert result.skipped_explicit_patch_count == 0


def test_initialize_fresh_seed_controls_uses_surface_symbol_not_hardcoded_node_name() -> (
    None
):
    """Detailer-style seed controls should initialize through surface metadata."""

    cube_buffer = _cube_buffer(symbol="detailer_segs", class_type="DetailerForEach")

    initialize_fresh_seed_controls(
        cube_buffer,
        buffer_patch=None,
        randint=_constant_randint(456),
    )

    assert _seed_value(cube_buffer, "detailer_segs") == 456


@pytest.mark.parametrize(
    "seed_value",
    [None, "", "   ", 0, 0.0, "0"],
)
def test_initialize_fresh_seed_controls_replaces_unset_like_values(
    seed_value: object,
) -> None:
    """Unset-like seed values should be replaced during fresh cube load."""

    cube_buffer = _cube_buffer(seed_value=seed_value)

    initialize_fresh_seed_controls(
        cube_buffer,
        buffer_patch=None,
        randint=_constant_randint(789),
    )

    assert _seed_value(cube_buffer) == 789


def test_initialize_fresh_seed_controls_preserves_nonzero_values() -> None:
    """Existing nonzero seed values should remain authoritative."""

    cube_buffer = _cube_buffer(seed_value=42)

    result = initialize_fresh_seed_controls(
        cube_buffer,
        buffer_patch=None,
        randint=_constant_randint(789),
    )

    assert _seed_value(cube_buffer) == 42
    assert result.initialized_count == 0


def test_initialize_fresh_seed_controls_preserves_explicit_buffer_patch() -> None:
    """Explicit recipe/project seed patches should keep saved seed intent."""

    cube_buffer = _cube_buffer(seed_value=0)

    result = initialize_fresh_seed_controls(
        cube_buffer,
        buffer_patch={"nodes": {"N1": {"inputs": {"seed": 0}}}},
        randint=_constant_randint(789),
    )

    assert _seed_value(cube_buffer) == 0
    assert result.skipped_explicit_patch_count == 1


def test_initialize_fresh_seed_controls_uses_definition_range() -> None:
    """Seed generation should honor min and max from node definitions."""

    cube_buffer = _cube_buffer(minimum=10, maximum=20)
    calls: list[tuple[int, int]] = []

    def randint(minimum: int, maximum: int) -> int:
        """Record the requested range and return a valid deterministic seed."""

        calls.append((minimum, maximum))
        return minimum

    initialize_fresh_seed_controls(
        cube_buffer,
        buffer_patch=None,
        randint=randint,
    )

    assert calls == [(10, 20)]
    assert _seed_value(cube_buffer) == 10


def test_initialize_fresh_seed_controls_avoids_zero_when_definition_min_is_zero() -> (
    None
):
    """Seed generation should use one as the lower bound when definitions allow zero."""

    cube_buffer = _cube_buffer(minimum=0, maximum=20)
    calls: list[tuple[int, int]] = []

    def randint(minimum: int, maximum: int) -> int:
        """Record the requested range and return a valid deterministic seed."""

        calls.append((minimum, maximum))
        return minimum

    initialize_fresh_seed_controls(
        cube_buffer,
        buffer_patch=None,
        randint=randint,
    )

    assert calls == [(1, 20)]
    assert _seed_value(cube_buffer) == 1

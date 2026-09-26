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

"""Verify durable nodepack operation timing diagnostics."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from substitute.infrastructure.comfy.nodepack_operation_timing import (
    measure_nodepack_operation,
)


def _clock(*values: float) -> Iterator[float]:
    """Yield deterministic monotonic values for timing tests."""

    yield from values


def test_reports_successful_operation_duration() -> None:
    """Expose exact elapsed milliseconds through the setup log callback."""

    values = _clock(10.0, 11.2345)
    messages: list[str] = []

    with measure_nodepack_operation(
        operation="registry_install_exact",
        nodepack_id="sugarcubes",
        on_log=messages.append,
        clock=lambda: next(values),
    ):
        pass

    assert messages == [
        "[ComfyNodepacks][Timing] operation=registry_install_exact "
        "nodepack=sugarcubes outcome=completed elapsed_ms=1234.500"
    ]


def test_reports_failed_operation_without_hiding_exception() -> None:
    """Record failed duration while preserving the original exception."""

    values = _clock(2.0, 2.5)
    messages: list[str] = []

    with pytest.raises(RuntimeError, match="registry failed"):
        with measure_nodepack_operation(
            operation="registry_install_exact",
            nodepack_id="sugarcubes",
            on_log=messages.append,
            clock=lambda: next(values),
        ):
            raise RuntimeError("registry failed")

    assert messages == [
        "[ComfyNodepacks][Timing] operation=registry_install_exact "
        "nodepack=sugarcubes outcome=failed elapsed_ms=500.000"
    ]

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

"""Test execution cancellation sources and controllers."""

from __future__ import annotations

import pytest

from substitute.application.execution import (
    CancellationController,
    CancellationSource,
    NeverCancelled,
)


def test_cancellation_source_starts_uncancelled() -> None:
    """Expose initial cancellation state."""

    source = CancellationSource(generation=3)

    assert source.generation == 3
    assert source.is_cancelled is False
    assert source.reason is None


def test_cancellation_source_records_first_reason() -> None:
    """Keep cancellation idempotent after the first reason is stored."""

    source = CancellationSource(generation=1)

    source.cancel(reason="closed")
    source.cancel(reason="later")

    assert source.is_cancelled is True
    assert source.reason == "closed"


def test_cancellation_rejects_invalid_values() -> None:
    """Reject invalid generations and blank reasons."""

    with pytest.raises(ValueError, match="generation"):
        CancellationSource(generation=-1)
    with pytest.raises(ValueError, match="reason"):
        CancellationSource(generation=1).cancel(reason="")


def test_cancellation_controller_returns_monotonic_sources() -> None:
    """Allocate strictly increasing cancellation generations."""

    controller = CancellationController(initial_generation=4)

    first = controller.next_source()
    second = controller.next_source()

    assert first.generation == 5
    assert second.generation == 6


def test_never_cancelled_token_is_stable() -> None:
    """Provide a neutral token for immediate tests."""

    token = NeverCancelled()

    assert token.generation == 0
    assert token.is_cancelled is False
    assert token.reason is None

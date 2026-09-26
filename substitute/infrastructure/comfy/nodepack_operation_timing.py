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

"""Record exact wall-clock timings for nodepack maintenance operations."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from time import perf_counter

from substitute.shared.logging.logger import get_logger, log_info

Clock = Callable[[], float]
LogCallback = Callable[[str], None]

_LOGGER = get_logger("infrastructure.comfy.nodepack_operation_timing")


@contextmanager
def measure_nodepack_operation(
    *,
    operation: str,
    nodepack_id: str,
    on_log: LogCallback | None,
    clock: Clock = perf_counter,
) -> Iterator[None]:
    """Publish one successful or failed nodepack operation duration."""

    started_at = clock()
    outcome = "completed"
    try:
        yield
    except Exception:
        outcome = "failed"
        raise
    finally:
        elapsed_ms = max(0.0, (clock() - started_at) * 1_000.0)
        message = (
            "[ComfyNodepacks][Timing] "
            f"operation={operation} nodepack={nodepack_id} "
            f"outcome={outcome} elapsed_ms={elapsed_ms:.3f}"
        )
        log_info(
            _LOGGER,
            "Comfy nodepack operation timed",
            operation=operation,
            nodepack_id=nodepack_id,
            outcome=outcome,
            elapsed_ms=f"{elapsed_ms:.3f}",
        )
        if on_log is not None:
            on_log(message)


__all__ = ["measure_nodepack_operation"]

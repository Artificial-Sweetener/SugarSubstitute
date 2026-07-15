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

"""Own bounded parallel mapping for infrastructure operations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from types import TracebackType
from typing import TypeVar


_INPUT_T = TypeVar("_INPUT_T")
_OUTPUT_T = TypeVar("_OUTPUT_T")


class BoundedParallelMapper:
    """Keep one bounded thread pool behind a focused mapping interface."""

    def __init__(self, *, parallelism: int) -> None:
        """Store the maximum number of simultaneous operations."""

        if parallelism <= 0:
            raise ValueError("Parallelism must be positive.")
        self._parallelism = parallelism
        self._executor: ThreadPoolExecutor | None = None

    def __enter__(self) -> BoundedParallelMapper:
        """Start the bounded pool for a cohesive operation sequence."""

        if self._executor is not None:
            raise RuntimeError("Parallel mapper is already active.")
        self._executor = ThreadPoolExecutor(
            max_workers=self._parallelism,
            thread_name_prefix="bounded-parallel-map",
        )
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Stop the pool after every success or failure."""

        del exception_type, exception, traceback
        executor = self._executor
        self._executor = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    def map(
        self,
        operation: Callable[[_INPUT_T], _OUTPUT_T],
        items: Iterable[_INPUT_T],
    ) -> tuple[_OUTPUT_T, ...]:
        """Apply one operation in input order through the active bounded pool."""

        if self._executor is None:
            raise RuntimeError("Parallel mapper must be active before mapping.")
        return tuple(self._executor.map(operation, items))

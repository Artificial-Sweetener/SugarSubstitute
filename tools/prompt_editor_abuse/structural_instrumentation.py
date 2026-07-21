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

"""Install opt-in external owner counters for structural abuse campaigns."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields

from substitute.devtools.prompt_editor_performance.instrumentation import (
    InstrumentedMethods,
)
from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    OperationCounter,
)

_ACTIVE_INSTRUMENTATION: ContextVar[Instrumentation | None] = ContextVar(
    "prompt_abuse_structural_instrumentation",
    default=None,
)


@contextmanager
def prompt_abuse_structural_instrumentation(
    *,
    enabled: bool,
) -> Iterator[Instrumentation | None]:
    """Patch measured owners only for an explicitly instrumented campaign."""

    if not enabled:
        yield None
        return
    instrumentation = Instrumentation.create()
    token = _ACTIVE_INSTRUMENTATION.set(instrumentation)
    try:
        with InstrumentedMethods(
            instrumentation,
            suppress_context_menu_exec=False,
        ):
            yield instrumentation
    finally:
        _ACTIVE_INSTRUMENTATION.reset(token)


def active_structural_counter_counts() -> dict[str, float]:
    """Return current external call counts without adding hot-path work."""

    instrumentation = _ACTIVE_INSTRUMENTATION.get()
    if instrumentation is None:
        return {}
    return {
        f"instrumented_{instrumentation_field.name}_count": float(counter.count)
        for instrumentation_field in fields(instrumentation)
        if isinstance(
            counter := getattr(instrumentation, instrumentation_field.name),
            OperationCounter,
        )
    }


__all__ = [
    "active_structural_counter_counts",
    "prompt_abuse_structural_instrumentation",
]

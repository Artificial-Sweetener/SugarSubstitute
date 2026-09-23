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

"""Adapt stable prompt-editor owner events to benchmark counters."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    OperationCounter,
)
from substitute.presentation.editor.prompt_editor.shell.menu_presentation import (
    suppress_prompt_menu_presentation,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    observe_prompt_editor_work,
)


class PromptEditorInstrumentationObserver:
    """Record stable owner events into one benchmark counter collection."""

    def __init__(self, instrumentation: Instrumentation) -> None:
        """Store the benchmark counters addressed by stable event values."""

        self._instrumentation = instrumentation
        self._lock = Lock()
        self._owners: dict[int, object] = {}
        self._owner_event_counts: dict[tuple[int, PromptEditorWorkEvent], int] = {}

    def record(
        self,
        event: PromptEditorWorkEvent,
        elapsed_ms: float,
        owner: object | None = None,
    ) -> None:
        """Record one owner event and retain exact-owner attribution."""

        with self._lock:
            counter = getattr(self._instrumentation, event.value)
            if not isinstance(counter, OperationCounter):
                raise TypeError(
                    f"Prompt editor work event has no counter: {event.value}"
                )
            counter.record(elapsed_ms)
            if owner is not None:
                owner_id = id(owner)
                self._owners[owner_id] = owner
                owner_key = (owner_id, event)
                self._owner_event_counts[owner_key] = (
                    self._owner_event_counts.get(owner_key, 0) + 1
                )

    def owner_event_count(
        self,
        event: PromptEditorWorkEvent,
        owner: object,
    ) -> int:
        """Return event count attributed to one exact live owner instance."""

        with self._lock:
            owner_id = id(owner)
            if self._owners.get(owner_id) is not owner:
                return 0
            return self._owner_event_counts.get((owner_id, event), 0)


@contextmanager
def instrument_prompt_editor(
    instrumentation: Instrumentation,
    *,
    enabled: bool = True,
    suppress_context_menu_exec: bool = True,
) -> Iterator[PromptEditorInstrumentationObserver | None]:
    """Observe stable owner events for one benchmark or abuse campaign."""

    if not enabled:
        with _suppress_context_menu_execution(enabled=suppress_context_menu_exec):
            yield None
        return
    observer = PromptEditorInstrumentationObserver(instrumentation)
    with (
        observe_prompt_editor_work(observer),
        _suppress_context_menu_execution(enabled=suppress_context_menu_exec),
    ):
        yield observer


@contextmanager
def _suppress_context_menu_execution(*, enabled: bool) -> Iterator[None]:
    """Build prompt menus without opening their modal presentation loop."""

    if not enabled:
        yield
        return
    with suppress_prompt_menu_presentation():
        yield


__all__ = [
    "PromptEditorInstrumentationObserver",
    "instrument_prompt_editor",
]

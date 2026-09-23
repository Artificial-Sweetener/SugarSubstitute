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
from dataclasses import dataclass
from collections.abc import Mapping

from substitute.devtools.prompt_editor_performance.instrumentation import (
    PromptEditorInstrumentationObserver,
    instrument_prompt_editor,
)
from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    OperationCounter,
)
from substitute.shared.diagnostics.prompt_editor_work import PromptEditorWorkEvent


@dataclass(frozen=True, slots=True)
class _ActiveStructuralInstrumentation:
    """Store campaign counters with exact-owner attribution."""

    instrumentation: Instrumentation
    observer: PromptEditorInstrumentationObserver


_ACTIVE_INSTRUMENTATION: ContextVar[_ActiveStructuralInstrumentation | None] = (
    ContextVar(
        "prompt_abuse_structural_instrumentation",
        default=None,
    )
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
    with instrument_prompt_editor(
        instrumentation,
        suppress_context_menu_exec=False,
    ) as observer:
        if observer is None:
            raise RuntimeError("Enabled prompt-editor instrumentation has no observer")
        token = _ACTIVE_INSTRUMENTATION.set(
            _ActiveStructuralInstrumentation(instrumentation, observer)
        )
        try:
            yield instrumentation
        finally:
            _ACTIVE_INSTRUMENTATION.reset(token)


def active_structural_counter_counts(
    *,
    event_owners: Mapping[PromptEditorWorkEvent, object] | None = None,
) -> dict[str, float]:
    """Return external counts, scoped to exact owners where requested."""

    active = _ACTIVE_INSTRUMENTATION.get()
    if active is None:
        return {}
    counts = {
        f"instrumented_{instrumentation_field.name}_count": float(counter.count)
        for instrumentation_field in fields(active.instrumentation)
        if isinstance(
            counter := getattr(active.instrumentation, instrumentation_field.name),
            OperationCounter,
        )
    }
    for event, owner in (event_owners or {}).items():
        counts[f"instrumented_{event.value}_count"] = float(
            active.observer.owner_event_count(event, owner)
        )
    return counts


def structural_instrumentation_active() -> bool:
    """Return whether the current campaign attributes structural owner work."""

    return _ACTIVE_INSTRUMENTATION.get() is not None


__all__ = [
    "active_structural_counter_counts",
    "prompt_abuse_structural_instrumentation",
    "structural_instrumentation_active",
]

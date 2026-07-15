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

"""Tests for prompt editor performance instrumentation patches."""

from __future__ import annotations

from typing import Any, cast

from substitute.devtools.prompt_editor_performance.instrumentation import (
    InstrumentedMethods,
)
from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    OperationCounter,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)


class _PatchTarget:
    """Provide small methods for focused patch-stack tests."""

    def value(self, amount: int) -> int:
        """Return an incremented amount."""

        return amount + 1

    def branch(self, result: bool) -> bool:
        """Return the requested branch result."""

        return result


def test_instrumented_methods_patch_records_elapsed_time_and_restores() -> None:
    """Generic timed patches should call the original method and restore it."""

    manager = InstrumentedMethods(Instrumentation.create())
    counter = OperationCounter()
    original = _PatchTarget.value

    cast(Any, manager)._patch(_PatchTarget, "value", counter)

    assert _PatchTarget().value(4) == 5
    assert counter.count == 1
    assert counter.elapsed_ms >= 0.0

    manager.__exit__(None, None, None)

    assert _PatchTarget.value is original


def test_instrumented_methods_bool_patch_records_selected_branch() -> None:
    """Boolean patches should count true and false outcomes separately."""

    manager = InstrumentedMethods(Instrumentation.create())
    true_counter = OperationCounter()
    false_counter = OperationCounter()
    original = _PatchTarget.branch

    cast(Any, manager)._patch_bool_result(
        _PatchTarget,
        "branch",
        true_counter,
        false_counter=false_counter,
    )

    assert _PatchTarget().branch(True) is True
    assert _PatchTarget().branch(False) is False
    assert true_counter.count == 1
    assert false_counter.count == 1

    manager.__exit__(None, None, None)

    assert _PatchTarget.branch is original


def test_instrumented_methods_context_restores_prompt_editor_methods() -> None:
    """The benchmark context should restore real prompt editor methods on exit."""

    original = PromptProjectionSurface._rebuild_projection

    with InstrumentedMethods(Instrumentation.create()):
        patched = PromptProjectionSurface._rebuild_projection
        assert patched is not original

    assert PromptProjectionSurface._rebuild_projection is original

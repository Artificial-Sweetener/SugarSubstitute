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

"""Tests for stable prompt-editor performance instrumentation."""

from __future__ import annotations

from typing import Any, cast

from substitute.devtools.prompt_editor_performance.instrumentation import (
    PromptEditorInstrumentationObserver,
    instrument_prompt_editor,
)
from substitute.devtools.prompt_editor_performance.metrics import Instrumentation
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)
from substitute.presentation.editor.prompt_editor.shell import (
    context_menu_controller as prompt_context_menu_module,
)
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    prompt_editor_work_event,
)


def test_instrumentation_observer_records_stable_owner_event() -> None:
    """Map one stable event to its benchmark counter without owner inspection."""

    instrumentation = Instrumentation.create()
    observer = PromptEditorInstrumentationObserver(instrumentation)

    observer.record(PromptEditorWorkEvent.EDITING_REPLACE_RANGE, 2.5)

    assert instrumentation.editing_replace_range.count == 1
    assert instrumentation.editing_replace_range.elapsed_ms == 2.5


def test_instrumentation_supports_every_stable_owner_event() -> None:
    """Keep the stable event contract and benchmark counters exhaustive."""

    instrumentation = Instrumentation.create()
    observer = PromptEditorInstrumentationObserver(instrumentation)

    for event in PromptEditorWorkEvent:
        observer.record(event, 1.0)

    for event in PromptEditorWorkEvent:
        counter = cast(Any, getattr(instrumentation, event.value))
        assert counter.count == 1
        assert counter.elapsed_ms == 1.0


def test_instrumentation_context_observes_decorated_owner_boundary() -> None:
    """Collect owner events without replacing the measured method."""

    instrumentation = Instrumentation.create()

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_SELECTION)
    def selection() -> int:
        """Return one representative owner result."""

        return 3

    original = selection
    with instrument_prompt_editor(instrumentation):
        assert selection() == 3
        assert selection is original

    assert instrumentation.editing_selection.count == 1


def test_instrumentation_context_does_not_patch_prompt_editor_owners() -> None:
    """Keep measured owner methods stable throughout an instrumented run."""

    original = PromptProjectionSurface._rebuild_projection

    with instrument_prompt_editor(Instrumentation.create()):
        assert PromptProjectionSurface._rebuild_projection is original

    assert PromptProjectionSurface._rebuild_projection is original


def test_instrumentation_can_delegate_context_menu_suppression() -> None:
    """Leave menu execution to an outer harness when it owns popup capture."""

    menu_type = cast(Any, prompt_context_menu_module)._PromptEditorTextEditMenu
    original_exec = menu_type.exec

    with instrument_prompt_editor(
        Instrumentation.create(),
        suppress_context_menu_exec=False,
    ):
        assert menu_type.exec is original_exec

    assert menu_type.exec is original_exec


def test_instrumentation_suppresses_modal_context_menu_by_default() -> None:
    """Keep menu benchmarks non-modal without replacing menu owner methods."""

    menu_type = cast(Any, prompt_context_menu_module)._PromptEditorTextEditMenu
    original_exec = menu_type.exec

    with instrument_prompt_editor(Instrumentation.create()):
        assert menu_type.exec is original_exec

    assert menu_type.exec is original_exec

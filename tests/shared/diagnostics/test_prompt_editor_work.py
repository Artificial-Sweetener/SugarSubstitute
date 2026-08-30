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

"""Verify stable prompt-editor owner work observation."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Thread

import pytest
from pytest import MonkeyPatch, raises

from substitute.shared.diagnostics import prompt_editor_work
from substitute.shared.diagnostics.prompt_editor_work import (
    PromptEditorWorkEvent,
    begin_prompt_editor_work,
    complete_prompt_editor_result_work,
    observe_prompt_editor_work,
    prompt_editor_work_event,
    prompt_editor_work_result_event,
    record_prompt_editor_work_count,
)


@dataclass(slots=True)
class _RecordingObserver:
    """Collect owner events for focused observation tests."""

    events: list[tuple[PromptEditorWorkEvent, float]] = field(default_factory=list)

    def record(self, event: PromptEditorWorkEvent, elapsed_ms: float) -> None:
        """Append one measured event."""

        self.events.append((event, elapsed_ms))


def test_disabled_owner_observation_skips_clock_and_counter(
    monkeypatch: MonkeyPatch,
) -> None:
    """Keep the ordinary production path free of clocks and counter mutation."""

    def fail_clock() -> float:
        """Fail if disabled observation reaches the timing clock."""

        raise AssertionError("clock disabled")

    monkeypatch.setattr(prompt_editor_work, "perf_counter", fail_clock)

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_SELECTION)
    def operation(value: int) -> int:
        """Return the supplied test value."""

        return value

    assert operation(7) == 7


def test_enabled_owner_observation_records_elapsed_event(
    monkeypatch: MonkeyPatch,
) -> None:
    """Record one stable event and duration when a probe is installed."""

    clock_values = iter((1.0, 1.004))
    monkeypatch.setattr(prompt_editor_work, "perf_counter", lambda: next(clock_values))
    observer = _RecordingObserver()

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_REPLACE_RANGE)
    def operation() -> str:
        """Return a successful result."""

        return "result"

    with observe_prompt_editor_work(observer):
        assert operation() == "result"

    assert observer.events[0][0] is PromptEditorWorkEvent.EDITING_REPLACE_RANGE
    assert observer.events[0][1] == pytest.approx(4.0)


def test_result_classification_records_only_selected_event() -> None:
    """Classify branch work without exposing the owner's method to tooling."""

    observer = _RecordingObserver()

    def classify_result(applied: bool) -> PromptEditorWorkEvent | None:
        """Return an event only for applied results."""

        return PromptEditorWorkEvent.PROJECTION_FAST_INSERT_APPLIED if applied else None

    @prompt_editor_work_result_event(classify_result)
    def operation(applied: bool) -> bool:
        """Return the requested branch."""

        return applied

    with observe_prompt_editor_work(observer):
        assert operation(False) is False
        assert operation(True) is True

    assert [event for event, _elapsed_ms in observer.events] == [
        PromptEditorWorkEvent.PROJECTION_FAST_INSERT_APPLIED,
    ]


def test_explicit_result_observation_has_a_clock_free_disabled_path(
    monkeypatch: MonkeyPatch,
) -> None:
    """Time hot owner results without a disabled-path callable wrapper."""

    clock_values = iter((1.0, 1.003))
    monkeypatch.setattr(prompt_editor_work, "perf_counter", lambda: next(clock_values))
    observer = _RecordingObserver()

    assert begin_prompt_editor_work() is None
    complete_prompt_editor_result_work(
        lambda _result: PromptEditorWorkEvent.PAINT_CACHE_HIT,
        "hit",
        started_at=None,
    )
    with observe_prompt_editor_work(observer):
        started_at = begin_prompt_editor_work()
        complete_prompt_editor_result_work(
            lambda _result: PromptEditorWorkEvent.PAINT_CACHE_HIT,
            "hit",
            started_at=started_at,
        )

    assert len(observer.events) == 1
    assert observer.events[0][0] is PromptEditorWorkEvent.PAINT_CACHE_HIT
    assert observer.events[0][1] == pytest.approx(3.0)


def test_count_only_owner_event_skips_clock_and_records_zero_elapsed(
    monkeypatch: MonkeyPatch,
) -> None:
    """Record cache outcomes without adding a timing clock to the hot path."""

    monkeypatch.setattr(
        prompt_editor_work,
        "perf_counter",
        lambda: (_ for _ in ()).throw(AssertionError("clock must remain unused")),
    )
    observer = _RecordingObserver()

    record_prompt_editor_work_count(PromptEditorWorkEvent.FILL_BAND_CACHE_HIT)
    with observe_prompt_editor_work(observer):
        record_prompt_editor_work_count(PromptEditorWorkEvent.FILL_BAND_CACHE_HIT)

    assert observer.events == [(PromptEditorWorkEvent.FILL_BAND_CACHE_HIT, 0.0)]


def test_owner_observation_scope_restores_parent_observer() -> None:
    """Restore nested observation scopes without leaking benchmark state."""

    outer = _RecordingObserver()
    inner = _RecordingObserver()

    @prompt_editor_work_event(PromptEditorWorkEvent.EDITING_SELECTION)
    def operation() -> None:
        """Complete one observed operation."""

    with observe_prompt_editor_work(outer):
        operation()
        with observe_prompt_editor_work(inner):
            operation()
        operation()
    operation()

    assert len(outer.events) == 2
    assert len(inner.events) == 1


def test_owner_observation_records_failed_operation() -> None:
    """Retain owner-work evidence when the measured operation raises."""

    observer = _RecordingObserver()

    @prompt_editor_work_event(PromptEditorWorkEvent.PROJECTION_REBUILD)
    def operation() -> None:
        """Raise the expected test failure."""

        raise RuntimeError("expected")

    with observe_prompt_editor_work(observer), raises(RuntimeError, match="expected"):
        operation()

    assert [event for event, _elapsed_ms in observer.events] == [
        PromptEditorWorkEvent.PROJECTION_REBUILD,
    ]


def test_owner_observation_includes_background_owner_work() -> None:
    """Keep async semantic work inside the controlled structural probe scope."""

    observer = _RecordingObserver()

    @prompt_editor_work_event(PromptEditorWorkEvent.DOCUMENT_VIEW_BUILD)
    def operation() -> None:
        """Complete one representative background owner operation."""

    with observe_prompt_editor_work(observer):
        thread = Thread(target=operation)
        thread.start()
        thread.join(timeout=5.0)

    assert not thread.is_alive()

    assert [event for event, _elapsed_ms in observer.events] == [
        PromptEditorWorkEvent.DOCUMENT_VIEW_BUILD,
    ]

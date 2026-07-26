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

"""Expose opt-in prompt-editor owner work events without runtime patching."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import StrEnum
from functools import wraps
from threading import RLock
from time import perf_counter
from typing import ParamSpec, Protocol, TypeVar

_Parameters = ParamSpec("_Parameters")
_Result = TypeVar("_Result")


class PromptEditorWorkEvent(StrEnum):
    """Name stable owner operations measured by editor performance tooling."""

    PROJECTION_REBUILD = "projection_rebuild"
    DOCUMENT_VIEW_BUILD = "document_view_build"
    SYNTAX_RENDER_PLAN_BUILD = "syntax_render_plan_build"
    PROJECTION_DOCUMENT_BUILD = "projection_document_build"
    LAYOUT_SNAPSHOT = "layout_snapshot"
    AUTOCOMPLETE_REFRESH = "autocomplete_refresh"
    AUTOCOMPLETE_QUERY_RESOLUTION = "autocomplete_query_resolution"
    AUTOCOMPLETE_PANEL_UPDATE = "autocomplete_panel_update"
    AUTOCOMPLETE_LORA_WALL_UPDATE = "autocomplete_lora_wall_update"
    AUTOCOMPLETE_PREVIEW_UPDATE = "autocomplete_preview_update"
    DIAGNOSTICS_ACTIVATION = "diagnostics_activation"
    DIAGNOSTICS_VISIBLE_REFRESH = "diagnostics_visible_refresh"
    DIAGNOSTICS_VISIBLE_PUBLISH = "diagnostics_visible_publish"
    DIAGNOSTICS_ACTION_PREPARE = "diagnostics_action_prepare"
    CONTEXT_MENU_SNAPSHOT = "context_menu_snapshot"
    CONTEXT_MENU_SCENE_CONTEXT = "context_menu_scene_context"
    CONTEXT_MENU_LORA_ACTIONS = "context_menu_lora_actions"
    CONTEXT_MENU_SEGMENT_SNAPSHOT = "context_menu_segment_snapshot"
    CONTEXT_MENU_DANBOORU_SNAPSHOT = "context_menu_danbooru_snapshot"
    CONTEXT_MENU_OPEN = "context_menu_open"
    REORDER_PREVIEW_REQUEST = "reorder_preview_request"
    REORDER_PREVIEW_RUN = "reorder_preview_run"
    EDITING_REPLACE_RANGE = "editing_replace_range"
    EDITING_REPLACE_FULL_SOURCE = "editing_replace_full_source"
    EDITING_SET_CURSOR_POSITIONS = "editing_set_cursor_positions"
    EDITING_SELECTION = "editing_selection"
    EDITING_PASTE = "editing_paste"
    DANBOORU_IMPORT_APPLY = "danbooru_import_apply"
    SURFACE_SOURCE_APPLY = "surface_source_apply"
    PROJECTION_FAST_INSERT_APPLIED = "projection_fast_insert_applied"
    PROJECTION_FAST_DELETE_APPLIED = "projection_fast_delete_applied"
    PROJECTION_FAST_NEWLINE_APPLIED = "projection_fast_newline_applied"
    PROJECTION_INCREMENTAL_APPLIED = "projection_incremental_applied"
    PROJECTION_INCREMENTAL_DEFERRED = "projection_incremental_deferred"
    PROJECTION_INCREMENTAL_REJECTED = "projection_incremental_rejected"
    PROJECTION_WRAP_DEFERRED = "projection_wrap_deferred"
    PROJECTION_FALLBACK_DEFERRED = "projection_fallback_deferred"
    PROJECTION_PENDING_FLUSH_APPLIED = "projection_pending_flush_applied"
    PAINT_CACHE_HIT = "paint_cache_hit"
    PAINT_CACHE_MISS = "paint_cache_miss"
    PAINT_CACHE_BYPASS = "paint_cache_bypass"
    DIAGNOSTIC_FRAGMENT_LOOKUP = "diagnostic_fragment_lookup"
    DIAGNOSTIC_CACHE_PRESERVE = "diagnostic_cache_preserve"
    DIAGNOSTIC_CACHE_CLEAR = "diagnostic_cache_clear"
    FILL_BAND_CACHE_HIT = "fill_band_cache_hit"
    FILL_BAND_CACHE_MISS = "fill_band_cache_miss"
    SURFACE_PAINT_EVENT = "surface_paint_event"
    SURFACE_REFRESH_GEOMETRY = "surface_refresh_geometry"
    SURFACE_REFRESH_SCROLL = "surface_refresh_scroll"
    SURFACE_RESIZE_EVENT = "surface_resize_event"
    SURFACE_SYNC_LAYOUT = "surface_sync_layout"
    SHELL_SCROLL_EVENT = "shell_scroll_event"
    SHELL_GEOMETRY_SYNC = "shell_geometry_sync"
    SHELL_LAYOUT_SURFACE = "shell_layout_surface"
    FILL_PLANE_PAINT = "fill_plane_paint"
    HOVER_UPDATE = "hover_update"
    HOVER_MOVE = "hover_move"
    FOCUS_IN = "focus_in"


class PromptEditorWorkObserver(Protocol):
    """Receive one completed owner operation from an instrumented editor run."""

    def record(self, event: PromptEditorWorkEvent, elapsed_ms: float) -> None:
        """Record one operation without inspecting the measured owner."""


_ACTIVE_OBSERVER: PromptEditorWorkObserver | None = None
_OBSERVER_SCOPE_LOCK = RLock()


@contextmanager
def observe_prompt_editor_work(
    observer: PromptEditorWorkObserver,
) -> Iterator[None]:
    """Install one serialized process-wide observer for a measurement scope."""

    global _ACTIVE_OBSERVER
    with _OBSERVER_SCOPE_LOCK:
        previous_observer = _ACTIVE_OBSERVER
        _ACTIVE_OBSERVER = observer
        try:
            yield
        finally:
            _ACTIVE_OBSERVER = previous_observer


def prompt_editor_work_event(
    event: PromptEditorWorkEvent,
) -> Callable[
    [Callable[_Parameters, _Result]],
    Callable[_Parameters, _Result],
]:
    """Decorate one owner boundary with disabled-fast-path instrumentation."""

    def decorate(
        operation: Callable[_Parameters, _Result],
    ) -> Callable[_Parameters, _Result]:
        """Wrap one operation while preserving its public callable signature."""

        @wraps(operation)
        def measured(
            *args: _Parameters.args,
            **kwargs: _Parameters.kwargs,
        ) -> _Result:
            observer = _ACTIVE_OBSERVER
            if observer is None:
                return operation(*args, **kwargs)
            started_at = perf_counter()
            try:
                result = operation(*args, **kwargs)
            except BaseException:
                observer.record(event, (perf_counter() - started_at) * 1_000.0)
                raise
            observer.record(event, (perf_counter() - started_at) * 1_000.0)
            return result

        return measured

    return decorate


def record_prompt_editor_work_count(event: PromptEditorWorkEvent) -> None:
    """Record one count-only owner outcome without reading the timing clock."""

    observer = _ACTIVE_OBSERVER
    if observer is not None:
        observer.record(event, 0.0)


def begin_prompt_editor_work() -> float | None:
    """Start explicit owner timing only while an observer is active."""

    if _ACTIVE_OBSERVER is None:
        return None
    return perf_counter()


def complete_prompt_editor_work(
    event: PromptEditorWorkEvent,
    *,
    started_at: float | None,
) -> None:
    """Complete explicitly timed owner work without a disabled-path wrapper."""

    if started_at is None:
        return
    observer = _ACTIVE_OBSERVER
    if observer is not None:
        observer.record(event, (perf_counter() - started_at) * 1_000.0)


def complete_prompt_editor_result_work(
    result_event: Callable[[_Result], PromptEditorWorkEvent | None],
    result: _Result,
    *,
    started_at: float | None,
) -> None:
    """Record an explicitly timed result without a disabled-path call wrapper."""

    if started_at is None:
        return
    observer = _ACTIVE_OBSERVER
    if observer is None:
        return
    measured_event = result_event(result)
    if measured_event is not None:
        complete_prompt_editor_work(measured_event, started_at=started_at)


def prompt_editor_work_result_event(
    result_event: Callable[[_Result], PromptEditorWorkEvent | None],
) -> Callable[
    [Callable[_Parameters, _Result]],
    Callable[_Parameters, _Result],
]:
    """Decorate a branch owner and classify successful result work."""

    def decorate(
        operation: Callable[_Parameters, _Result],
    ) -> Callable[_Parameters, _Result]:
        """Wrap one result-classified operation with a disabled fast path."""

        @wraps(operation)
        def measured(
            *args: _Parameters.args,
            **kwargs: _Parameters.kwargs,
        ) -> _Result:
            observer = _ACTIVE_OBSERVER
            if observer is None:
                return operation(*args, **kwargs)
            started_at = perf_counter()
            result = operation(*args, **kwargs)
            measured_event = result_event(result)
            if measured_event is not None:
                observer.record(
                    measured_event,
                    (perf_counter() - started_at) * 1_000.0,
                )
            return result

        return measured

    return decorate


def prompt_editor_work_true_event(
    event: PromptEditorWorkEvent,
) -> Callable[[bool], PromptEditorWorkEvent | None]:
    """Return a reusable classifier that records only successful bool results."""

    def classify(result: bool) -> PromptEditorWorkEvent | None:
        """Return the configured event only for a true result."""

        return event if result else None

    return classify


def prompt_editor_work_bool_event(
    *,
    true_event: PromptEditorWorkEvent,
    false_event: PromptEditorWorkEvent,
) -> Callable[[bool], PromptEditorWorkEvent]:
    """Return a reusable classifier for both boolean result branches."""

    def classify(result: bool) -> PromptEditorWorkEvent:
        """Return the event associated with the supplied branch."""

        return true_event if result else false_event

    return classify


def prompt_editor_paint_cache_event(result: str) -> PromptEditorWorkEvent:
    """Classify one prepared projection paint-cache outcome."""

    if result == "hit":
        return PromptEditorWorkEvent.PAINT_CACHE_HIT
    if result in {"miss", "bypass_small_cache_miss"}:
        return PromptEditorWorkEvent.PAINT_CACHE_MISS
    return PromptEditorWorkEvent.PAINT_CACHE_BYPASS


__all__ = [
    "PromptEditorWorkEvent",
    "PromptEditorWorkObserver",
    "begin_prompt_editor_work",
    "complete_prompt_editor_result_work",
    "complete_prompt_editor_work",
    "observe_prompt_editor_work",
    "prompt_editor_paint_cache_event",
    "prompt_editor_work_bool_event",
    "prompt_editor_work_event",
    "prompt_editor_work_result_event",
    "prompt_editor_work_true_event",
    "record_prompt_editor_work_count",
]

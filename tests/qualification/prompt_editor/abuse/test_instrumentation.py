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

"""Test prompt-editor abuse runtime and Qt instrumentation contracts."""

from __future__ import annotations

import gc
import sys
from types import SimpleNamespace


from tools.prompt_editor_abuse.action_counter_probe import (
    PromptAbuseActionCounterProbe,
)
from tools.prompt_editor_abuse.runtime_probe import PromptAbuseRuntimeProbe
from tools.prompt_editor_abuse.qt_exception_capture import (
    PromptAbuseQtExceptionCapture,
)


def test_runtime_probe_attributes_gc_without_changing_collection_policy() -> None:
    """Harness telemetry should observe GC without suppressing or forcing policy."""

    enabled_before = gc.isenabled()
    callbacks_before = tuple(gc.callbacks)
    with PromptAbuseRuntimeProbe(enabled=True) as probe:
        probe.begin_sample()
        gc.collect()
        sample = probe.finish_sample()

    assert sample.gc_collection_count == 1
    assert sample.gc_pause_ms >= 0.0
    assert gc.isenabled() is enabled_before
    assert tuple(gc.callbacks) == callbacks_before


def test_qt_exception_capture_turns_uncaught_callbacks_into_violations() -> None:
    """Delayed callback failures should make harness correctness fail closed."""

    with PromptAbuseQtExceptionCapture() as capture:
        sys.excepthook(RuntimeError, RuntimeError("delayed preview failed"), None)

    assert capture.violations == (
        "uncaught_qt_callback:RuntimeError:delayed preview failed",
    )


def test_action_counter_probe_attributes_created_and_closed_overlay_work() -> None:
    """Deep traces should retain per-action counters across overlay lifecycle."""

    class _Overlay:
        """Expose mutable production-shaped performance counters."""

        def __init__(self) -> None:
            """Initialize an idle owner counter snapshot."""

            self.counters = {"raster_build_count": 0, "drag_move_count": 0}

        def reorder_performance_counters(self) -> dict[str, object]:
            """Return a copy of the current counter state."""

            return dict(self.counters)

    editor = SimpleNamespace(_segment_overlay=None)
    probe = PromptAbuseActionCounterProbe(editor)
    overlay = _Overlay()

    probe.begin_unit()
    editor._segment_overlay = overlay
    overlay.counters["raster_build_count"] = 8
    opened = probe.finish_unit(action_index=2, unit_index=0, label="key_press:alt")

    probe.begin_unit()
    overlay.counters["drag_move_count"] = 3
    editor._segment_overlay = None
    closed = probe.finish_unit(action_index=3, unit_index=0, label="key_release:alt")

    assert dict(opened.counter_deltas) == {"raster_build_count": 8.0}
    assert dict(closed.counter_deltas) == {"drag_move_count": 3.0}
    assert opened.reset_counter_names == ()
    assert closed.reset_counter_names == ()

    editor._segment_overlay = overlay
    overlay.counters["drag_move_count"] = 9
    probe.begin_unit()
    overlay.counters["drag_move_count"] = 1
    reset = probe.finish_unit(action_index=4, unit_index=0, label="owner_reset")
    assert reset.counter_deltas == ()
    assert reset.reset_counter_names == ("drag_move_count",)

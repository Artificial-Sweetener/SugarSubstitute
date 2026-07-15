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

"""Tests for shell layout trace record construction."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import substitute.presentation.shell.shell_layout_trace as shell_layout_trace


def test_log_editor_width_trace_collects_live_shell_layout_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trace records should include live shell layout fields and caller context."""

    records: list[dict[str, object]] = []
    shell = SimpleNamespace(
        workflow_session_service=SimpleNamespace(active_workflow_id="wf-1"),
        splitter=SimpleNamespace(sizes=lambda: [100, 200]),
        editor_output_splitter=SimpleNamespace(sizes=lambda: [300, 400]),
        cube_stack_container=SimpleNamespace(width=lambda: 80),
        editor_output_container=SimpleNamespace(width=lambda: 420),
        canvas_tabs_container=SimpleNamespace(width=lambda: 260),
        active_editor_panel=lambda: SimpleNamespace(width=lambda: 340),
        window=lambda: SimpleNamespace(width=lambda: 1280),
        width=lambda: 900,
        _active_workspace_route="workflow",
        _restored_shell_layout_applied=True,
        _remembered_workflow_splitter_sizes=(100, 200),
    )

    monkeypatch.setattr(
        shell_layout_trace,
        "log_debug",
        lambda _logger, _message, **context: records.append(context),
    )

    shell_layout_trace.log_editor_width_trace(
        object(),
        shell,
        "layout event",
        extra="value",
    )

    assert records == [
        {
            "trace_event": "layout event",
            "active_route": "workflow",
            "active_workflow_id": "wf-1",
            "restored_shell_layout_applied": True,
            "remembered_workflow_splitter_sizes": (100, 200),
            "live_main_splitter_sizes": (100, 200),
            "live_editor_output_splitter_sizes": (300, 400),
            "cube_stack_container_width": 80,
            "editor_output_container_width": 420,
            "canvas_tabs_container_width": 260,
            "active_editor_panel_width": 340,
            "main_window_width": 900,
            "shell_window_width": 1280,
            "extra": "value",
        }
    ]


def test_safe_trace_helpers_tolerate_missing_or_invalid_widgets() -> None:
    """Trace helper reads should fail closed for torn-down widgets."""

    class _BrokenWidth:
        def width(self) -> int:
            raise RuntimeError("widget deleted")

    class _BrokenSplitter:
        def sizes(self) -> list[int]:
            raise RuntimeError("splitter deleted")

    assert shell_layout_trace.safe_trace_width(None) is None
    assert shell_layout_trace.safe_trace_width(SimpleNamespace()) is None
    assert shell_layout_trace.safe_trace_width(_BrokenWidth()) is None
    assert shell_layout_trace.safe_trace_splitter_sizes(None) == ()
    assert shell_layout_trace.safe_trace_splitter_sizes(SimpleNamespace()) == ()
    assert shell_layout_trace.safe_trace_splitter_sizes(_BrokenSplitter()) == ()
    assert shell_layout_trace.safe_trace_splitter_sizes(
        SimpleNamespace(sizes=lambda: ["1", 2])
    ) == (1, 2)

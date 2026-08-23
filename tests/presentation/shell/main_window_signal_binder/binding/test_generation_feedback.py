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

"""Verify generation feedback signal routing."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.presentation.shell.main_window_signal_binder import (
    MainWindowSignalBinder,
)

from .support import _Signal


def test_generation_feedback_signals_route_to_view_and_workspace_controller() -> None:
    """Generation feedback signals should bind to the existing presentation targets."""

    progress_calls: list[tuple[object, object]] = []
    preview_calls: list[object] = []
    output_calls: list[tuple[object, object, object]] = []
    clear_calls: list[object] = []
    shell = SimpleNamespace(
        clear_output_signal=_Signal(),
        progress_update_signal=_Signal(),
        preview_image_signal=_Signal(),
        add_output_image_signal=_Signal(),
        generation_feedback_presenter=SimpleNamespace(
            clear_output_for_workflow=clear_calls.append
        ),
        generation_action_controller=SimpleNamespace(
            update_progress_labels=lambda workflow, sampler: progress_calls.append(
                (workflow, sampler)
            )
        ),
        workspace_canvas_actions=SimpleNamespace(
            display_preview_image=preview_calls.append,
            handle_add_output_image=lambda workflow_id, image, metadata: (
                output_calls.append((workflow_id, image, metadata))
            ),
        ),
    )

    MainWindowSignalBinder(shell).connect_generation_feedback_signals()
    shell.clear_output_signal.fire("wf-a")
    shell.progress_update_signal.fire(0.25, None)
    shell.preview_image_signal.fire("preview")
    shell.add_output_image_signal.fire("wf-a", "image", "metadata")

    assert clear_calls == ["wf-a"]
    assert progress_calls == [(0.25, None)]
    assert preview_calls == ["preview"]
    assert output_calls == [("wf-a", "image", "metadata")]

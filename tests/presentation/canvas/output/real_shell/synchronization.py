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

"""Synchronize real-shell Output tests on authoritative execution state."""

from __future__ import annotations

from tests.support.real_output_canvas.harness import RealShellOutputCanvasHarness


def wait_for_output_delivery(harness: RealShellOutputCanvasHarness) -> None:
    """Flush feedback and await decode plus GUI commit completion."""

    harness.shell.generation_feedback_dispatcher.flush_now()

    def preparation_publications_are_released() -> bool:
        """Return whether all accepted preparations published their callbacks."""

        dispatcher = harness.shell.output_image_pipeline._preparation_dispatcher
        return (
            not dispatcher._queued_preparations
            and not dispatcher._task_scope._handles
            and harness.shell.execution_runtime.lane("image_decode").pending_count == 0
        )

    harness.wait_until(preparation_publications_are_released)

    def output_delivery_is_idle() -> bool:
        """Return whether every observable Output delivery owner is idle."""

        fingerprint = harness.fingerprint()
        return fingerprint.pending_commit_count == 0 and not any(
            fingerprint.pending_feedback_counts.values()
        )

    harness.wait_until(output_delivery_is_idle)


def wait_for_output_failure(
    harness: RealShellOutputCanvasHarness,
    *,
    report_count: int,
) -> None:
    """Await presentation of the expected failed Output preparation."""

    harness.wait_until(lambda: len(harness.shell.error_reports) == report_count)
    wait_for_output_delivery(harness)

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

"""Characterize warning-log capture for bundled-workflow production audits."""

from __future__ import annotations

import logging

from tests.qualification.comfy.bundled_workflows.rendering_audit.runtime_logs import (
    WorkflowRuntimeLogCapture,
)


def test_capture_records_warning_context_and_exception_traceback() -> None:
    """Preserve actionable runtime evidence without disrupting the emitter."""

    logger = logging.getLogger("tests.bundled_workflow_audit.capture")
    capture = WorkflowRuntimeLogCapture()
    logger.addHandler(capture)
    try:
        try:
            raise ValueError("bad field")
        except ValueError:
            logger.warning("Rendering failed for %s", "node-1", exc_info=True)
    finally:
        logger.removeHandler(capture)

    observations = capture.observations()

    assert len(observations) == 1
    assert observations[0].level == "WARNING"
    assert observations[0].logger == logger.name
    assert observations[0].message == "Rendering failed for node-1"
    assert "ValueError: bad field" in observations[0].traceback


def test_capture_reset_discards_only_prior_workflow_evidence() -> None:
    """Start each workflow audit with a clean log-observation buffer."""

    logger = logging.getLogger("tests.bundled_workflow_audit.reset")
    capture = WorkflowRuntimeLogCapture()
    logger.addHandler(capture)
    try:
        logger.warning("first workflow")
        capture.reset()
        logger.error("second workflow")
    finally:
        logger.removeHandler(capture)

    observations = capture.observations()

    assert [observation.message for observation in observations] == ["second workflow"]

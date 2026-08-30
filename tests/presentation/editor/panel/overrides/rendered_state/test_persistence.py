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

"""Verify rendered override choices persist at their workflow owner."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QApplication

from substitute.domain.workspace_snapshot.codecs import workflow_state_from_json
from tests.presentation.editor.panel.overrides.rendered_state.support import (
    render_harness,
)


def _commit_choice(widget: Any, index: int) -> None:
    """Commit one choice through the production control's user boundary."""

    widget._commit_user_index(index)  # noqa: SLF001


def test_override_choice_edits_persist_through_autosave_restoration(
    qt_application_owner: QApplication,
) -> None:
    """Keep committed sampler and scheduler values across restoration."""

    harness = render_harness(qt_application_owner)
    try:
        sampler = harness.toolbar_widget("sampler_name")
        scheduler = harness.toolbar_widget("scheduler")

        _commit_choice(sampler, 1)
        _commit_choice(scheduler, 1)

        assert sampler.currentText() == "euler"
        assert scheduler.currentText() == "normal"
        assert harness.workflow.global_overrides["sampler_name"]["value"] == "euler"
        assert harness.workflow.global_overrides["scheduler"]["value"] == "normal"
        assert len(harness.autosave_payloads) == 2

        restored = workflow_state_from_json(harness.autosave_payloads[-1])
        restored_harness = render_harness(qt_application_owner, restored)
        try:
            assert restored_harness.toolbar_widget("sampler_name").currentText() == (
                "euler"
            )
            assert restored_harness.toolbar_widget("scheduler").currentText() == (
                "normal"
            )
        finally:
            restored_harness.close()
    finally:
        harness.close()


def test_each_committed_override_choice_requests_autosave_once(
    qt_application_owner: QApplication,
) -> None:
    """Request one durable snapshot for each committed override choice."""

    harness = render_harness(qt_application_owner)
    try:
        sampler = harness.toolbar_widget("sampler_name")
        scheduler = harness.toolbar_widget("scheduler")

        _commit_choice(sampler, 1)
        _commit_choice(scheduler, 1)

        assert sampler.currentText() == "euler"
        assert scheduler.currentText() == "normal"
        assert harness.workflow.global_overrides["sampler_name"]["value"] == "euler"
        assert harness.workflow.global_overrides["scheduler"]["value"] == "normal"
        assert len(harness.autosave_payloads) == 2
        assert harness.autosave_payloads[0]["global_overrides"] == {
            "sampler_name": {"value": "euler", "mode": "global"},
            "scheduler": {"value": "simple", "mode": "global"},
            "seed": {"value": 11, "mode": "global"},
        }
    finally:
        harness.close()

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

"""Test workspace output commit authorization."""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

from _pytest.logging import LogCaptureFixture
from PySide6.QtGui import QImage

from tests.presentation.shell.canvas_actions.support import _import_module


def test_commit_prepared_output_image_rejects_stale_authorized_run(
    caplog: LogCaptureFixture,
) -> None:
    """Prepared output commits should re-authorize before state mutation."""

    mod = _import_module()
    from substitute.presentation.shell.output_image_commit_pipeline import (
        OutputImageCommitRequest,
        PreparedOutputImage,
    )

    metadata_calls: list[object] = []
    state_calls: list[tuple[str, object]] = []
    image = QImage(8, 8, QImage.Format.Format_ARGB32)
    view = SimpleNamespace(
        workflow_session_service=SimpleNamespace(
            workflows={"wf-a": object()},
            active_workflow_id="wf-a",
        ),
        visual_authorization_service=SimpleNamespace(
            authorize_final_output=lambda _identity: False
        ),
        canvas_io_service=SimpleNamespace(
            build_output_image_metadata=lambda **kwargs: metadata_calls.append(kwargs)
        ),
        output_canvas_state_service=SimpleNamespace(
            register_output_image=lambda *args: state_calls.append(("register", args)),
        ),
    )
    caplog.set_level(
        logging.WARNING,
        logger="sugarsubstitute.presentation.shell.workspace_canvas_actions",
    )

    result = mod.WorkspaceCanvasActions(view).commit_prepared_output_image(
        PreparedOutputImage(
            request=OutputImageCommitRequest(
                workflow_id="wf-a",
                file_path=Path("E:/out.png"),
                node_id="save",
                node_meta_title="Cube.Output",
                workflow_name="Workflow",
                source_key="wf-a:save",
                source_label="Save",
                generation_run_id="run-stale",
                prompt_id="prompt-1",
                client_id="client-1",
            ),
            image=image,
        )
    )

    assert result.workflow_id == "wf-a"
    assert result.projection_intent.should_schedule is False
    assert result.active_output_changed is False
    assert metadata_calls == []
    assert state_calls == []
    assert "post_prepare_authorization_failed" in caplog.text

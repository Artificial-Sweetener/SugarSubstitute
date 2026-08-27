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

"""Characterize canvas projection generated-output event contracts."""

from __future__ import annotations

from pathlib import Path


from substitute.application.workflows.output_visual_events import (
    LiveFinalOutputEvent,
    OutputVisualIdentity,
    SourceOnlyOutputIdentity,
)
from substitute.domain.generation import OutputResultPosition


def _live_final_event() -> LiveFinalOutputEvent:
    """Build one strict live final event for generated-output registration tests."""

    return LiveFinalOutputEvent(
        identity=OutputVisualIdentity(
            workflow_id="wf",
            generation_run_id="run-1",
            prompt_id="pid-1",
            client_id="client-1",
            source_key="wf:node",
            source_label="Cube",
            scene=SourceOnlyOutputIdentity(),
        ),
        node_id="node",
        workflow_payload={"node": {"class_type": "SugarCubes.CubeOutput"}},
        file_path=Path("E:/out.png"),
        position=OutputResultPosition(list_index=0, batch_index=0),
        artifact_width=640,
        artifact_height=480,
    )

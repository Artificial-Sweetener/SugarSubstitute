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

"""Verify Output transfer composition owns native-transfer resource lifetime."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from substitute.application.generation.output_preference_service import (
    OutputPreferenceService,
)
from substitute.domain.generation import OutputPreferences
from substitute.presentation.canvas.output.output_document import OutputCanvasDocument
from substitute.presentation.canvas.output.output_transfer_composition import (
    compose_output_transfer_lifecycle,
)
from tests.presentation.canvas.output.transfer.support import (
    MemoryOutputPreferences,
    RejectingTaskSubmitter,
    transfer_image,
)


def test_transfer_lifecycle_closes_provider_dispatcher_and_staged_artifacts(
    tmp_path: Path,
    output_document: OutputCanvasDocument,
) -> None:
    """Shell cleanup must reclaim the provider route and every staged transfer file."""

    image_id = uuid4()
    closed_submitters: list[str] = []
    assert output_document.admit_image(image_id, transfer_image())
    lifecycle = compose_output_transfer_lifecycle(
        document=output_document,
        is_image_authorized=lambda candidate: candidate == image_id,
        preference_service=OutputPreferenceService(
            MemoryOutputPreferences(), default_output_root=tmp_path
        ),
        drag_submitter=RejectingTaskSubmitter(),
        close_drag_submitter=lambda: closed_submitters.append("drag"),
        clipboard_submitter=RejectingTaskSubmitter(),
        close_clipboard_submitter=lambda: closed_submitters.append("clipboard"),
        publish_clipboard_mime_data=lambda _mime_data: None,
        report_clipboard_failure=lambda _message: None,
        staging_directory=tmp_path / "transfers",
    )
    artifact = lifecycle.artifact_store.materialize(
        transfer_image(),
        canonical_path=None,
        transfer_format=OutputPreferences().transfer.preferred_format,
        jpeg_settings=OutputPreferences().jpeg,
    )
    assert artifact is not None

    lifecycle.close()
    lifecycle.close()

    assert closed_submitters == ["clipboard", "drag"]
    assert artifact.path.exists() is False

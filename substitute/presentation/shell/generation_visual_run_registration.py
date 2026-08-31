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

"""Register generation-run visual authorization from shell feedback events."""

from __future__ import annotations

from substitute.application.generation import (
    GenerationRunStarted,
    VisualAuthorizationService,
)


def register_generation_visual_run(
    authorization: VisualAuthorizationService | None,
    event: GenerationRunStarted,
) -> None:
    """Register every identity and placeholder source authorized for one run."""

    if authorization is None:
        return
    authorization.register_run(
        workflow_id=event.workflow_id,
        generation_run_id=event.generation_run_id,
        prompt_id=event.prompt_id,
        client_id=event.client_id,
        preview_source_keys=event.preview_source_keys,
    )


__all__ = ["register_generation_visual_run"]

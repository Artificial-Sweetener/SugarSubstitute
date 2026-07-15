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

"""Define workflow payload compilation boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from substitute.domain.common import JsonObject


class WorkflowPayloadCompiler(Protocol):
    """Compile Sugar script text into a Comfy payload artifact.

    Implementations may return either the legacy raw executable prompt node map or a
    wrapped artifact with `prompt` executable nodes plus `workflow` UI metadata.
    Callers that inspect nodes should use `executable_prompt_nodes()`.
    """

    def compile_workflow_payload(
        self,
        *,
        sugar_script_text: str,
        output_dir: Path,
    ) -> JsonObject:
        """Compile Sugar script text into a Comfy payload artifact."""


__all__ = ["WorkflowPayloadCompiler"]

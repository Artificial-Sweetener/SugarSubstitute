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

"""Provide an ordinary-workflow analyzer double for isolated load tests."""

from __future__ import annotations

from copy import deepcopy

from substitute.domain.comfy_workflow import CanonicalCubeGraphAnalysis
from substitute.domain.common import JsonObject


class PassthroughCubeWorkflowAnalyzer:
    """Return no Cube projection while preserving the supplied ordinary graph."""

    def analyze(self, workflow: JsonObject) -> CanonicalCubeGraphAnalysis:
        """Return detached ordinary workflow state without Cube interpretation."""

        return CanonicalCubeGraphAnalysis(
            workflow_semantic_hash="ordinary-test-workflow",
            instances=(),
            edges=(),
            proximity_edges=(),
            segments=(),
            workflow=deepcopy(workflow),
        )


__all__ = ["PassthroughCubeWorkflowAnalyzer"]

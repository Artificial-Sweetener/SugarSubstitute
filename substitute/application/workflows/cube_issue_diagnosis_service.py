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

"""Diagnose cube runtime issues against Cube Library catalog state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from substitute.application.cube_library import (
    CubeLibraryUpdateDetectionService,
    LoadedCubeUpdateCandidate,
)
from substitute.domain.cube_library import CubeCatalog

from .cube_runtime_issues import (
    CubeRuntimeIssue,
    CubeRuntimeIssueKind,
)


class CubeIssueDiagnosisService:
    """Attach Cube Library update candidates to stale-cube runtime issues."""

    def __init__(
        self,
        *,
        update_detection_service: CubeLibraryUpdateDetectionService | None = None,
    ) -> None:
        """Store collaborators used to diagnose update availability."""

        self._update_detection_service = (
            update_detection_service or CubeLibraryUpdateDetectionService()
        )

    def diagnose_missing_node_issues(
        self,
        *,
        issues: Sequence[CubeRuntimeIssue],
        workflows: Mapping[str, object],
        workflow_names: Mapping[str, str],
        catalog: CubeCatalog | None,
    ) -> tuple[CubeRuntimeIssue, ...]:
        """Attach update candidates to missing-node issues when catalog drift exists."""

        if catalog is None:
            return tuple(issues)
        candidates = self._update_detection_service.detect_updates(
            workflows=workflows,
            workflow_names=workflow_names,
            catalog=catalog,
        )
        candidate_by_issue_key = {
            (candidate.workflow_id, candidate.cube_alias): candidate
            for candidate in candidates
        }
        return tuple(
            self._with_candidate(
                issue,
                candidate_by_issue_key.get((issue.workflow_id, issue.cube_alias)),
            )
            for issue in issues
        )

    @staticmethod
    def _with_candidate(
        issue: CubeRuntimeIssue,
        candidate: LoadedCubeUpdateCandidate | None,
    ) -> CubeRuntimeIssue:
        """Return an issue with candidate-specific recommended action."""

        if (
            candidate is None
            or issue.kind != CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION
        ):
            return issue
        return replace(
            issue,
            update_candidate=candidate,
            recommended_action="Update this cube from the Cube Library.",
        )


__all__ = ["CubeIssueDiagnosisService"]

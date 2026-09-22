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

"""Resolve portable model metadata before canonical workflow materialization."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from substitute.application.recipes import (
    RecipeModelLoadResolver,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
)
from substitute.application.workflows.portable_model_projection import (
    CanonicalModelResolutionProjection,
    PortableModelManifestService,
)
from substitute.domain.common import JsonObject
from substitute.domain.recipes import ParsedSugarScript


@dataclass(frozen=True, slots=True)
class ResolvedPortableWorkflow:
    """Carry a detached canonical graph and its model-resolution evidence."""

    workflow: JsonObject
    summary: RecipeModelResolutionSummary


@dataclass(frozen=True, slots=True)
class PendingPortableWorkflowResolution:
    """Retain stable graph bindings while the user approves model downloads."""

    workflow: JsonObject
    projection: CanonicalModelResolutionProjection
    required: RecipeModelResolutionRequired


class PortableWorkflowModelResolutionRequired(ValueError):
    """Signal that a canonical workflow needs user-approved model acquisition."""

    def __init__(self, pending: PendingPortableWorkflowResolution) -> None:
        """Store the partially resolved graph and shared acquisition request."""

        super().__init__(str(pending.required))
        self.pending = pending


class PortableWorkflowModelResolutionService:
    """Coordinate canonical graph bindings with the shared model resolver."""

    def __init__(
        self,
        manifest: PortableModelManifestService,
        resolver_factory: Callable[[], RecipeModelLoadResolver],
    ) -> None:
        """Store portable projection and Backend-coordinated resolver owners."""

        self._manifest = manifest
        self._resolver_factory = resolver_factory

    def resolve(self, workflow: JsonObject) -> ResolvedPortableWorkflow:
        """Resolve current Backend model values in a detached canonical graph."""

        graph = deepcopy(workflow)
        projection = self._manifest.project_for_resolution(graph)
        if projection is None:
            return ResolvedPortableWorkflow(
                workflow=graph,
                summary=RecipeModelResolutionSummary(),
            )
        try:
            resolved = self._resolver_factory().resolve(projection.parsed_script)
        except RecipeModelResolutionRequired as error:
            self._manifest.apply_resolved_script(
                graph,
                projection=projection,
                parsed_script=error.partial_script,
            )
            raise PortableWorkflowModelResolutionRequired(
                PendingPortableWorkflowResolution(
                    workflow=graph,
                    projection=projection,
                    required=error,
                )
            ) from error
        self._manifest.apply_resolved_script(
            graph,
            projection=projection,
            parsed_script=resolved.parsed_script,
        )
        return ResolvedPortableWorkflow(workflow=graph, summary=resolved.summary)

    def complete(
        self,
        pending: PendingPortableWorkflowResolution,
        parsed_script: ParsedSugarScript,
    ) -> ResolvedPortableWorkflow:
        """Apply downloaded Backend values to a pending canonical graph."""

        graph = deepcopy(pending.workflow)
        self._manifest.apply_resolved_script(
            graph,
            projection=pending.projection,
            parsed_script=parsed_script,
        )
        return ResolvedPortableWorkflow(
            workflow=graph,
            summary=RecipeModelResolutionSummary(
                literal_matches=pending.required.summary.literal_matches,
                hash_matches=(
                    pending.required.summary.hash_matches
                    + pending.required.summary.unresolved_hashes
                ),
                unresolved_hashes=0,
            ),
        )


__all__ = [
    "PendingPortableWorkflowResolution",
    "PortableWorkflowModelResolutionRequired",
    "PortableWorkflowModelResolutionService",
    "ResolvedPortableWorkflow",
]

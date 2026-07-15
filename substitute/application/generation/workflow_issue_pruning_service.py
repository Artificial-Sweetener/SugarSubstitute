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

"""Build generation workflow snapshots that omit errored cubes."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import deepcopy
from dataclasses import replace
from typing import cast

from substitute.application.workflows import WorkflowLinkReconciliationService
from substitute.domain.recipes.sugar_ast import GlobalOverrideSerializationScope
from substitute.domain.workflow import WorkflowState


class WorkflowIssuePruningService:
    """Build generation-safe workflow snapshots by omitting errored cubes."""

    def __init__(
        self,
        *,
        link_reconciliation_service: WorkflowLinkReconciliationService | None = None,
    ) -> None:
        """Store optional link reconciliation for copied workflow cleanup."""

        self._link_reconciliation_service = link_reconciliation_service

    def pruned_for_generation(
        self,
        *,
        workflow: WorkflowState,
        errored_aliases: Collection[str],
    ) -> WorkflowState:
        """Return a copied workflow without errored cube aliases."""

        omitted_aliases = set(errored_aliases)
        pruned = deepcopy(workflow)
        pruned.stack_order = [
            alias for alias in pruned.stack_order if alias not in omitted_aliases
        ]
        for alias in omitted_aliases:
            pruned.cubes.pop(alias, None)
        if self._link_reconciliation_service is not None:
            self._link_reconciliation_service.sanitize_current_state(
                cube_states=pruned.cubes,
                stack_order=pruned.stack_order,
            )
        return pruned

    def pruned_activation_overrides(
        self,
        overrides: Mapping[str, tuple[str, ...]],
        *,
        errored_aliases: Collection[str],
    ) -> dict[str, tuple[str, ...]]:
        """Return activation overrides excluding omitted cube aliases."""

        omitted_aliases = set(errored_aliases)
        return {
            alias: tuple(node_keys)
            for alias, node_keys in overrides.items()
            if alias not in omitted_aliases
        }

    def pruned_global_override_scopes(
        self,
        scopes: Mapping[str, object] | None,
        *,
        errored_aliases: Collection[str],
    ) -> Mapping[str, object] | None:
        """Return override scopes with partial participants for omitted cubes removed."""

        if scopes is None:
            return None
        omitted_aliases = set(errored_aliases)
        pruned: dict[str, object] = {}
        for key, scope in scopes.items():
            if not isinstance(scope, GlobalOverrideSerializationScope):
                pruned[key] = scope
                continue
            if scope.full_participation:
                pruned[key] = scope
                continue
            participant_fields = frozenset(
                field
                for field in scope.participant_fields
                if field[0] not in omitted_aliases
            )
            if not participant_fields:
                continue
            pruned[key] = replace(scope, participant_fields=participant_fields)
        return cast(Mapping[str, object], pruned)


__all__ = ["WorkflowIssuePruningService"]

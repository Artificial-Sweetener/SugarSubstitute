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

"""Own the active generative-model candidate for one editor panel."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

from substitute.application.model_metadata import ModelCatalogItem, model_kind_for_field

GENERATIVE_MODEL_KINDS = frozenset({"checkpoints", "diffusion_models"})
_MISSING_STACK_INDEX = 1_000_000


@dataclass(frozen=True, slots=True)
class ActiveModelFieldCandidate:
    """Describe one generative-model input in panel display order."""

    cube_alias: str
    node_name: str
    node_type: str
    field_key: str
    model_kind: str
    value: str
    stack_index: int
    node_order: int

    @property
    def identity(self) -> tuple[str, str, str]:
        """Return the stable field identity used for candidate replacement."""

        return (self.cube_alias, self.node_name, self.field_key)

    @property
    def sort_key(self) -> tuple[int, int, str, str, str]:
        """Return deterministic panel order for active-model selection."""

        return (
            self.stack_index,
            self.node_order,
            self.field_key,
            self.cube_alias,
            self.node_name,
        )


class PanelActiveModelContextController:
    """Publish the first stack-ordered generative model in a panel."""

    def __init__(self) -> None:
        """Initialize an empty active-model context."""

        self._stack_indices: dict[str, int] = {}
        self._candidates: dict[tuple[str, str, str], ActiveModelFieldCandidate] = {}
        self._node_orders: dict[tuple[str, str], int] = {}
        self._next_node_order = 0

    def begin_projection(self, stack_order: Sequence[str] | None) -> None:
        """Clear candidates before a full workflow projection rebuild."""

        self._stack_indices = _stack_indices(stack_order)
        self._candidates.clear()
        self._node_orders.clear()
        self._next_node_order = 0

    def begin_cube_projection(
        self,
        *,
        cube_alias: str,
        stack_order: Sequence[str] | None,
    ) -> None:
        """Clear candidates for one cube before incremental rebuilding."""

        self._stack_indices = _stack_indices(stack_order)
        self._remove_cube_candidates(cube_alias)

    def update_cube_order(self, stack_order: Sequence[str] | None) -> None:
        """Update stack order for already prepared candidates."""

        self._stack_indices = _stack_indices(stack_order)
        self._candidates = {
            identity: ActiveModelFieldCandidate(
                cube_alias=candidate.cube_alias,
                node_name=candidate.node_name,
                node_type=candidate.node_type,
                field_key=candidate.field_key,
                model_kind=candidate.model_kind,
                value=candidate.value,
                stack_index=self._stack_index(candidate.cube_alias),
                node_order=candidate.node_order,
            )
            for identity, candidate in self._candidates.items()
        }

    def remove_cube(self, cube_alias: str) -> None:
        """Remove all active-model state owned by one cube."""

        self._remove_cube_candidates(cube_alias)

    def rename_cube(self, old_alias: str, new_alias: str) -> None:
        """Rename one cube across active-model candidate identities."""

        if old_alias in self._stack_indices:
            stack_index = self._stack_indices.pop(old_alias)
            self._stack_indices[new_alias] = stack_index
        renamed_candidates: dict[tuple[str, str, str], ActiveModelFieldCandidate] = {}
        for candidate in self._candidates.values():
            cube_alias = (
                new_alias if candidate.cube_alias == old_alias else candidate.cube_alias
            )
            renamed = ActiveModelFieldCandidate(
                cube_alias=cube_alias,
                node_name=candidate.node_name,
                node_type=candidate.node_type,
                field_key=candidate.field_key,
                model_kind=candidate.model_kind,
                value=candidate.value,
                stack_index=self._stack_index(cube_alias),
                node_order=candidate.node_order,
            )
            renamed_candidates[renamed.identity] = renamed
        self._candidates = renamed_candidates
        self._node_orders = {
            (new_alias if alias == old_alias else alias, node_name): order
            for (alias, node_name), order in self._node_orders.items()
        }

    def record_node_inputs(
        self,
        *,
        cube_alias: str | None,
        node_name: str,
        node_type: str,
        inputs: Mapping[str, object],
    ) -> None:
        """Record recognized generative-model inputs from one node payload."""

        if cube_alias is None:
            return
        self._remove_node_candidates(cube_alias, node_name)
        node_order = self._node_order(cube_alias, node_name)
        for field_key, value in inputs.items():
            model_kind = model_kind_for_field(
                class_type=node_type,
                input_key=field_key,
            )
            if (
                model_kind not in GENERATIVE_MODEL_KINDS
                or not isinstance(value, str)
                or not value.strip()
            ):
                continue
            self._candidates[(cube_alias, node_name, field_key)] = (
                ActiveModelFieldCandidate(
                    cube_alias=cube_alias,
                    node_name=node_name,
                    node_type=node_type,
                    field_key=field_key,
                    model_kind=model_kind,
                    value=value.strip(),
                    stack_index=self._stack_index(cube_alias),
                    node_order=node_order,
                )
            )

    def update_field_value(
        self,
        *,
        cube_alias: str | None,
        node_name: str | None,
        node_type: str | None,
        field_key: str,
        value: object,
    ) -> bool:
        """Update one candidate and return whether the field is generative-model state."""

        if cube_alias is None or node_name is None:
            return False
        identity = (cube_alias, node_name, field_key)
        existing = self._candidates.get(identity)
        model_kind = model_kind_for_field(
            class_type=node_type
            or (existing.node_type if existing is not None else ""),
            input_key=field_key,
        )
        if model_kind not in GENERATIVE_MODEL_KINDS:
            return False
        if not isinstance(value, str) or not value.strip():
            self._candidates.pop(identity, None)
            return True
        node_order = (
            existing.node_order
            if existing is not None
            else self._node_order(cube_alias, node_name)
        )
        self._candidates[identity] = ActiveModelFieldCandidate(
            cube_alias=cube_alias,
            node_name=node_name,
            node_type=node_type or (existing.node_type if existing is not None else ""),
            field_key=field_key,
            model_kind=model_kind,
            value=value.strip(),
            stack_index=self._stack_index(cube_alias),
            node_order=node_order,
        )
        return True

    def current_model(self) -> ActiveModelFieldCandidate | None:
        """Return the first prepared generative-model candidate."""

        return min(
            self._candidates.values(), key=lambda item: item.sort_key, default=None
        )

    def _node_order(self, cube_alias: str, node_name: str) -> int:
        """Return stable node order for this projection generation."""

        identity = (cube_alias, node_name)
        existing = self._node_orders.get(identity)
        if existing is not None:
            return existing
        node_order = self._next_node_order
        self._next_node_order += 1
        self._node_orders[identity] = node_order
        return node_order

    def _stack_index(self, cube_alias: str) -> int:
        """Return prepared stack index for one cube."""

        return self._stack_indices.get(cube_alias, _MISSING_STACK_INDEX)

    def _remove_cube_candidates(self, cube_alias: str) -> None:
        """Remove all candidates owned by one cube."""

        self._candidates = {
            identity: candidate
            for identity, candidate in self._candidates.items()
            if candidate.cube_alias != cube_alias
        }
        self._node_orders = {
            identity: order
            for identity, order in self._node_orders.items()
            if identity[0] != cube_alias
        }

    def _remove_node_candidates(self, cube_alias: str, node_name: str) -> None:
        """Remove all candidates owned by one node."""

        self._candidates = {
            identity: candidate
            for identity, candidate in self._candidates.items()
            if (candidate.cube_alias, candidate.node_name) != (cube_alias, node_name)
        }


def matching_catalog_item(
    model_value: str,
    catalog_items: tuple[ModelCatalogItem, ...],
) -> ModelCatalogItem | None:
    """Return the catalog item matching a backend path, basename, or stem."""

    normalized_value = _normalized_model_value(model_value)
    for item in catalog_items:
        if normalized_value in {
            _normalized_model_value(item.backend_value),
            _normalized_model_value(item.relative_path),
        }:
            return item
    model_stem = _normalized_model_stem(model_value)
    for item in catalog_items:
        if model_stem in {
            _normalized_model_stem(item.backend_value),
            _normalized_model_stem(item.relative_path),
            item.basename.strip().casefold(),
        }:
            return item
    return None


def _stack_indices(stack_order: Sequence[str] | None) -> dict[str, int]:
    """Return cube aliases mapped to stack indices."""

    if stack_order is None:
        return {}
    return {alias: index for index, alias in enumerate(stack_order)}


def _normalized_model_value(value: str) -> str:
    """Normalize one model path for stable matching."""

    return value.strip().replace("\\", "/").casefold()


def _normalized_model_stem(value: str) -> str:
    """Return a case-insensitive filename stem for one model value."""

    normalized = _normalized_model_value(value)
    return PurePosixPath(normalized).stem


__all__ = [
    "ActiveModelFieldCandidate",
    "GENERATIVE_MODEL_KINDS",
    "PanelActiveModelContextController",
    "matching_catalog_item",
]

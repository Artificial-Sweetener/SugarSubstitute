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

"""Derive sampler/scheduler value-link state from resolved editor behavior."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from substitute.application.node_behavior import EditorBehaviorSnapshot
from substitute.application.node_behavior.list_value_resolver import (
    extract_live_list_options,
)

_LINK_LABEL_PREFIX: Final[str] = "🔗"
_SAMPLER_LITERAL_KEY: Final[str] = "sampler_name"
_SAMPLER_LINK_KEY: Final[str] = "sampler_link"
_SCHEDULER_LITERAL_KEY: Final[str] = "scheduler"
_SCHEDULER_LINK_KEY: Final[str] = "scheduler_link"


@dataclass(frozen=True)
class ChoiceLinkTarget:
    """Describe one upstream value-link target."""

    from_cube: str
    from_node: str
    label: str

    def as_mapping(self) -> dict[str, str]:
        """Return the legacy mapping shape consumed by domain choice helpers."""

        return {
            "from_cube": self.from_cube,
            "from_node": self.from_node,
            "label": self.label,
        }


@dataclass(frozen=True)
class ChoiceLinkFieldState:
    """Describe one sampler/scheduler field's linkable choice state."""

    cube_alias: str
    node_name: str
    literal_key: str
    link_key: str
    literal_options: tuple[str, ...]
    link_targets: tuple[ChoiceLinkTarget, ...]
    active_link: ChoiceLinkTarget | None
    options_resolved: bool

    def link_target_mappings(self) -> list[dict[str, str]]:
        """Return link targets in the legacy mapping shape for combo builders."""

        return [target.as_mapping() for target in self.link_targets]


@dataclass(frozen=True)
class SamplerSchedulerLinkSnapshot:
    """Expose sampler and scheduler link state derived from editor behavior."""

    sampler_fields: dict[tuple[str, str], ChoiceLinkFieldState]
    scheduler_fields: dict[tuple[str, str], ChoiceLinkFieldState]

    def sampler_option_map(self) -> dict[tuple[str, str], list[str]]:
        """Return authoritative sampler literal options keyed by cube and node."""

        return {
            key: list(state.literal_options) if state.options_resolved else []
            for key, state in self.sampler_fields.items()
        }

    def scheduler_option_map(self) -> dict[tuple[str, str], list[str]]:
        """Return authoritative scheduler literal options keyed by cube and node."""

        return {
            key: list(state.literal_options) if state.options_resolved else []
            for key, state in self.scheduler_fields.items()
        }


class SamplerSchedulerLinkStateService:
    """Derive sampler/scheduler value-link state from resolved editor behavior."""

    def build_snapshot(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        all_buffers: Mapping[str, Mapping[str, object]],
        stack_order: Sequence[str],
    ) -> SamplerSchedulerLinkSnapshot:
        """Return current sampler/scheduler link state for presentation refreshes."""

        sampler_fields = self._build_field_states(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            stack_order=stack_order,
            literal_key=_SAMPLER_LITERAL_KEY,
            link_key=_SAMPLER_LINK_KEY,
        )
        scheduler_fields = self._build_field_states(
            behavior_snapshot=behavior_snapshot,
            all_buffers=all_buffers,
            stack_order=stack_order,
            literal_key=_SCHEDULER_LITERAL_KEY,
            link_key=_SCHEDULER_LINK_KEY,
        )
        return SamplerSchedulerLinkSnapshot(
            sampler_fields=sampler_fields,
            scheduler_fields=scheduler_fields,
        )

    def _build_field_states(
        self,
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        all_buffers: Mapping[str, Mapping[str, object]],
        stack_order: Sequence[str],
        literal_key: str,
        link_key: str,
    ) -> dict[tuple[str, str], ChoiceLinkFieldState]:
        """Build value-link state for one sampler/scheduler field family."""

        base_states = self._base_field_states(
            behavior_snapshot=behavior_snapshot,
            stack_order=stack_order,
            literal_key=literal_key,
            link_key=link_key,
        )
        result: dict[tuple[str, str], ChoiceLinkFieldState] = {}
        for index, cube_alias in enumerate(stack_order):
            for key, state in base_states.items():
                if key[0] != cube_alias:
                    continue
                link_targets = self._link_targets_before(
                    base_states=base_states,
                    current_state=state,
                    stack_order=stack_order,
                    current_index=index,
                    literal_key=literal_key,
                )
                active_link = self._active_link_target(
                    all_buffers=all_buffers,
                    cube_alias=state.cube_alias,
                    node_name=state.node_name,
                    link_key=link_key,
                    link_targets=link_targets,
                )
                result[key] = ChoiceLinkFieldState(
                    cube_alias=state.cube_alias,
                    node_name=state.node_name,
                    literal_key=state.literal_key,
                    link_key=state.link_key,
                    literal_options=state.literal_options,
                    link_targets=link_targets,
                    active_link=active_link,
                    options_resolved=state.options_resolved,
                )
        return result

    @staticmethod
    def _base_field_states(
        *,
        behavior_snapshot: EditorBehaviorSnapshot,
        stack_order: Sequence[str],
        literal_key: str,
        link_key: str,
    ) -> dict[tuple[str, str], ChoiceLinkFieldState]:
        """Return field states before upstream link targets are attached."""

        states: dict[tuple[str, str], ChoiceLinkFieldState] = {}
        for cube_alias in stack_order:
            nodes = behavior_snapshot.field_specs_by_alias.get(cube_alias, {})
            for node_name, field_specs in nodes.items():
                field_spec = field_specs.get(literal_key)
                if field_spec is None:
                    continue
                literal_options = extract_live_list_options(field_spec.field_info)
                states[(cube_alias, node_name)] = ChoiceLinkFieldState(
                    cube_alias=cube_alias,
                    node_name=node_name,
                    literal_key=literal_key,
                    link_key=link_key,
                    literal_options=literal_options,
                    link_targets=(),
                    active_link=None,
                    options_resolved=bool(literal_options),
                )
        return states

    @staticmethod
    def _link_targets_before(
        *,
        base_states: Mapping[tuple[str, str], ChoiceLinkFieldState],
        current_state: ChoiceLinkFieldState,
        stack_order: Sequence[str],
        current_index: int,
        literal_key: str,
    ) -> tuple[ChoiceLinkTarget, ...]:
        """Return eligible resolved field targets before the current stack index."""

        targets: list[ChoiceLinkTarget] = []
        earlier_aliases = set(stack_order[:current_index])
        for cube_alias in stack_order[:current_index]:
            for (state_alias, node_name), state in base_states.items():
                if state_alias != cube_alias:
                    continue
                if (
                    state_alias not in earlier_aliases
                    or state.literal_key != literal_key
                ):
                    continue
                if not state.options_resolved:
                    continue
                if state.literal_options != current_state.literal_options:
                    continue
                targets.append(
                    ChoiceLinkTarget(
                        from_cube=state_alias,
                        from_node=node_name,
                        label=f"{_LINK_LABEL_PREFIX} {state_alias} {node_name}",
                    )
                )
        return tuple(targets)

    @staticmethod
    def _active_link_target(
        *,
        all_buffers: Mapping[str, Mapping[str, object]],
        cube_alias: str,
        node_name: str,
        link_key: str,
        link_targets: Sequence[ChoiceLinkTarget],
    ) -> ChoiceLinkTarget | None:
        """Return the active link target when it matches a valid resolved target."""

        node = _node_payload(all_buffers, cube_alias, node_name)
        link = node.get(link_key) if isinstance(node, Mapping) else None
        if not isinstance(link, Mapping):
            return None
        from_cube = link.get("from_cube")
        from_node = link.get("from_node")
        if not isinstance(from_cube, str) or not isinstance(from_node, str):
            return None
        for target in link_targets:
            if target.from_cube == from_cube and target.from_node == from_node:
                return target
        return None


def _node_payload(
    all_buffers: Mapping[str, Mapping[str, object]],
    cube_alias: str,
    node_name: str,
) -> Mapping[str, object]:
    """Return one raw node payload from workflow buffers when available."""

    cube = all_buffers.get(cube_alias, {})
    nodes = cube.get("nodes") if isinstance(cube, Mapping) else None
    if not isinstance(nodes, Mapping):
        return {}
    node = nodes.get(node_name)
    return node if isinstance(node, Mapping) else {}


__all__ = [
    "ChoiceLinkFieldState",
    "ChoiceLinkTarget",
    "SamplerSchedulerLinkSnapshot",
    "SamplerSchedulerLinkStateService",
]

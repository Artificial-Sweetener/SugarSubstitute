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

"""Own editor-surface projection freshness identity."""

from __future__ import annotations

from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from substitute.shared.logging.logger import get_logger, log_info

from .projection_preparation import cube_projection_token

_LOGGER = get_logger("presentation.editor.panel.projection_surface_state")


class ProjectionSurfaceStateHost(Protocol):
    """Describe inputs required to identify the rendered editor surface."""

    _current_search_hidden_keys: set[object] | None
    _current_search_matching_nodes: set[object] | None
    _current_node_search_text: str | None
    _stack_order: list[str] | None

    def _workflow_overrides(self) -> Mapping[str, object]:
        """Return active workflow override values for projection signatures."""


@dataclass(frozen=True, slots=True)
class EditorSurfaceProjectionSignature:
    """Describe the structural workflow facts rendered by one editor surface."""

    workflow_id: str
    stack_order: tuple[str, ...]
    cube_state_map_id: int
    cube_tokens: tuple[tuple[Hashable, ...], ...]
    override_tokens: tuple[tuple[str, str], ...]
    hidden_field_tokens: tuple[str, ...]
    node_search_text: str | None
    search_match_tokens: tuple[str, ...]
    projection_mode: str = "live"


@dataclass(slots=True)
class EditorSurfaceProjectionState:
    """Track whether an editor surface is clean for one projection signature."""

    clean_signature: EditorSurfaceProjectionSignature | None = None
    invalidation_reason: str = "initial"


class ProjectionSurfaceStateController:
    """Own clean and stale projection identity for one editor surface."""

    def __init__(self, host: ProjectionSurfaceStateHost) -> None:
        """Store the host that supplies rendered-surface identity inputs."""

        self._host = host
        self._state = EditorSurfaceProjectionState()

    @property
    def clean_signature(self) -> EditorSurfaceProjectionSignature | None:
        """Return the current clean signature for diagnostics."""

        return self._state.clean_signature

    def current_projection_signature(
        self,
        *,
        workflow_id: str,
        cube_entries: Sequence[tuple[str, object]],
        cube_states: Mapping[str, object] | None,
        stack_order: Sequence[str] | None,
    ) -> EditorSurfaceProjectionSignature:
        """Return the structural signature required by a full projection."""

        resolved_stack_order = tuple(
            stack_order or [alias for alias, _ in cube_entries]
        )
        state_map = cube_states or {}
        cube_tokens = tuple(
            cube_projection_token(alias, state_map.get(alias))
            for alias in resolved_stack_order
        )
        overrides_reader = cast(
            Callable[[], Mapping[str, object]] | None,
            getattr(self._host, "_workflow_overrides", None),
        )
        overrides = overrides_reader() if overrides_reader is not None else {}
        override_tokens = tuple(
            (str(key), repr(value))
            for key, value in sorted(overrides.items(), key=lambda item: str(item[0]))
        )
        hidden_search_keys = cast(
            set[object] | None,
            getattr(self._host, "_current_search_hidden_keys", None),
        )
        matching_search_nodes = cast(
            set[object] | None,
            getattr(self._host, "_current_search_matching_nodes", None),
        )
        return EditorSurfaceProjectionSignature(
            workflow_id=workflow_id,
            stack_order=resolved_stack_order,
            cube_state_map_id=id(cube_states),
            cube_tokens=cube_tokens,
            override_tokens=override_tokens,
            hidden_field_tokens=tuple(
                sorted(repr(key) for key in (hidden_search_keys or set()))
            ),
            node_search_text=cast(
                str | None,
                getattr(self._host, "_current_node_search_text", None),
            ),
            search_match_tokens=tuple(
                sorted(repr(key) for key in (matching_search_nodes or set()))
            ),
        )

    def is_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> bool:
        """Return whether this surface already renders the signature."""

        return self._state.clean_signature == signature

    def mark_projection_clean(
        self,
        signature: EditorSurfaceProjectionSignature,
    ) -> None:
        """Record that the editor surface fully renders the signature."""

        self._state.clean_signature = signature
        self._state.invalidation_reason = ""
        log_info(
            _LOGGER,
            "Marked editor projection surface clean",
            workflow_id=signature.workflow_id,
            cube_section_count=len(signature.stack_order),
        )

    def invalidate_projection(self, *, reason: str) -> None:
        """Mark this editor surface as requiring projection before reuse."""

        self._state.clean_signature = None
        self._state.invalidation_reason = reason
        log_info(
            _LOGGER,
            "Invalidated editor projection surface",
            reason=reason,
            cube_section_count=len(self._host._stack_order or []),
        )

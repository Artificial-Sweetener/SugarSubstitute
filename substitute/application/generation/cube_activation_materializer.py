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

"""Materialize authoritative node activation into executable Cube documents."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from substitute.domain.common import JsonObject


class CubeActivationMaterializer:
    """Resolve authored modes and UI decisions into one executable node mode."""

    def materialize(
        self,
        buffers: Mapping[str, JsonObject],
        *,
        enabled_node_keys_by_alias: Mapping[str, Iterable[str]],
        disabled_node_keys_by_alias: Mapping[str, Iterable[str]],
    ) -> None:
        """Apply effective activation or reject projections that cannot be honored."""

        self._validate_aliases(
            buffers,
            enabled_node_keys_by_alias=enabled_node_keys_by_alias,
            disabled_node_keys_by_alias=disabled_node_keys_by_alias,
        )
        for alias, buffer in buffers.items():
            nodes = buffer.get("nodes")
            if not isinstance(nodes, dict):
                raise ValueError(f"Cube {alias!r} has invalid activation nodes.")
            enabled = frozenset(
                str(node_name)
                for node_name in enabled_node_keys_by_alias.get(alias, ())
            )
            disabled = frozenset(
                str(node_name)
                for node_name in disabled_node_keys_by_alias.get(alias, ())
            )
            overlap = enabled & disabled
            if overlap:
                joined = ", ".join(sorted(overlap))
                raise ValueError(
                    f"Cube {alias!r} has conflicting activation for nodes: {joined}."
                )
            unknown = (enabled | disabled) - {str(name) for name in nodes}
            if unknown:
                joined = ", ".join(sorted(unknown))
                raise ValueError(
                    f"Cube {alias!r} activation references unknown node(s): {joined}."
                )
            for node_name, payload in nodes.items():
                if not isinstance(payload, dict):
                    raise ValueError(
                        f"Cube {alias!r} node {str(node_name)!r} is invalid."
                    )
                self._materialize_node(
                    alias=alias,
                    node_name=str(node_name),
                    payload=payload,
                    projected_enabled=(
                        True
                        if str(node_name) in enabled
                        else False
                        if str(node_name) in disabled
                        else None
                    ),
                )

    @staticmethod
    def _validate_aliases(
        buffers: Mapping[str, JsonObject],
        *,
        enabled_node_keys_by_alias: Mapping[str, Iterable[str]],
        disabled_node_keys_by_alias: Mapping[str, Iterable[str]],
    ) -> None:
        """Reject activation projections for Cubes absent from execution."""

        unknown = (
            set(enabled_node_keys_by_alias) | set(disabled_node_keys_by_alias)
        ) - set(buffers)
        if unknown:
            joined = ", ".join(sorted(str(alias) for alias in unknown))
            raise ValueError(
                f"Node activation references unknown Cube alias(es): {joined}."
            )

    @staticmethod
    def _materialize_node(
        *,
        alias: str,
        node_name: str,
        payload: JsonObject,
        projected_enabled: bool | None,
    ) -> None:
        """Collapse authored mode plus override metadata into one effective mode."""

        persisted_override = payload.get("enabled")
        if persisted_override is not None and not isinstance(persisted_override, bool):
            raise ValueError(
                f"Cube {alias!r} node {node_name!r} has invalid enabled state."
            )
        effective_enabled = (
            projected_enabled
            if projected_enabled is not None
            else persisted_override
            if isinstance(persisted_override, bool)
            else None
        )
        if effective_enabled is True:
            payload["mode"] = 0
        elif effective_enabled is False:
            payload["mode"] = 4
        payload.pop("enabled", None)

        if effective_enabled is True and payload.get("mode", 0) == 4:
            raise ValueError(
                f"Cube {alias!r} node {node_name!r} remained bypassed after enabling."
            )
        if effective_enabled is False and payload.get("mode", 0) != 4:
            raise ValueError(
                f"Cube {alias!r} node {node_name!r} remained active after disabling."
            )


__all__ = ["CubeActivationMaterializer"]

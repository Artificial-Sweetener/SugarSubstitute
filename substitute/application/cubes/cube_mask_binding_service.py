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

"""Discover editable image-mask bindings from cube graphs."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.workflow import EditableMaskBinding, EditableMaskBindingIndex


class CubeMaskBindingService:
    """Build editable mask binding indexes from one cube graph."""

    def build_index(
        self,
        cube_alias: str,
        cube_graph: Mapping[str, object],
    ) -> EditableMaskBindingIndex:
        """Return unambiguous editable mask bindings discovered in one cube graph."""

        nodes = cube_graph.get("nodes", {})
        if not isinstance(nodes, dict):
            return EditableMaskBindingIndex()

        providers_for_consumer: dict[str, list[str]] = {}
        for node_name, node_data in nodes.items():
            if not isinstance(node_name, str) or not isinstance(node_data, dict):
                continue
            raw_inputs = node_data.get("inputs", {})
            if not isinstance(raw_inputs, dict):
                continue
            for input_value in raw_inputs.values():
                if not isinstance(input_value, list) or not input_value:
                    continue
                provider_name = input_value[0]
                if not isinstance(provider_name, str) or provider_name not in nodes:
                    continue
                providers_for_consumer.setdefault(node_name, []).append(provider_name)

        discovered: list[EditableMaskBinding] = []
        for consumer_name, provider_names in providers_for_consumer.items():
            image_providers: list[str] = []
            mask_providers: list[str] = []
            for provider_name in provider_names:
                provider_node = nodes.get(provider_name, {})
                if not isinstance(provider_node, dict):
                    continue
                class_type = provider_node.get("class_type")
                if class_type == "LoadImage":
                    image_providers.append(provider_name)
                elif class_type == "LoadImageMask":
                    mask_providers.append(provider_name)

            if len(image_providers) != 1 or not mask_providers:
                continue

            image_node_name = image_providers[0]
            for mask_node_name in mask_providers:
                discovered.append(
                    EditableMaskBinding(
                        cube_alias=cube_alias,
                        image_node_name=image_node_name,
                        mask_node_name=mask_node_name,
                        consumer_node_name=consumer_name,
                    )
                )

        return EditableMaskBindingIndex.from_bindings(discovered)


__all__ = ["CubeMaskBindingService"]

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

"""Build prompt endpoint indexes from resolved editor behavior snapshots."""

from __future__ import annotations

from typing import Mapping

from substitute.domain.links.prompt_endpoints import (
    PromptEndpoint,
    PromptEndpointIndex,
)
from substitute.domain.node_behavior import ResolvedNodeBehavior
from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("application.workflows.prompt_endpoint_service")


class PromptEndpointService:
    """Build prompt endpoint indexes from resolved node behavior."""

    def build_index(
        self,
        resolved_nodes_by_alias: Mapping[str, Mapping[str, ResolvedNodeBehavior]],
    ) -> PromptEndpointIndex:
        """Return the prompt endpoint index for one behavior snapshot."""

        endpoints: list[PromptEndpoint] = []
        for cube_alias, per_node in resolved_nodes_by_alias.items():
            for node_name, resolved_behavior in per_node.items():
                for field_key, field_behavior in resolved_behavior.fields.items():
                    prompt = field_behavior.prompt
                    if prompt is None:
                        continue
                    endpoints.append(
                        PromptEndpoint(
                            cube_alias=cube_alias,
                            role=prompt.role,
                            node_name=node_name,
                            field_key=field_key,
                            linkable=prompt.linkable,
                        )
                    )
        index = PromptEndpointIndex.from_endpoints(endpoints)
        for cube_alias, role in sorted(
            index.ambiguous_keys,
            key=lambda item: (item[0], item[1].value),
        ):
            log_warning(
                _LOGGER,
                "Omitted ambiguous prompt endpoints from link index",
                cube_alias=cube_alias,
                prompt_role=role.value,
            )
        return index


__all__ = ["PromptEndpointService"]

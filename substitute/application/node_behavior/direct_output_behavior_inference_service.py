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

"""Hide direct-workflow image sinks through shared node-card behavior."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.comfy_workflow import is_terminal_image_output_sink
from substitute.domain.node_behavior import (
    CardBehaviorPatch,
    EnabledSwitchPolicy,
    NodeBehaviorPatch,
    RevealMode,
)

from .section_node_source import SectionNodeSource


class DirectOutputBehaviorInferenceService:
    """Translate terminal image-output semantics into editor behavior patches."""

    def infer(
        self,
        *,
        graph: Mapping[str, object],
        sources: tuple[SectionNodeSource, ...],
    ) -> Mapping[str, NodeBehaviorPatch]:
        """Return hard-hide patches for safely replaceable terminal image sinks."""

        patches: dict[str, NodeBehaviorPatch] = {}
        for source in sources:
            if is_terminal_image_output_sink(
                node_id=source.node_name,
                node=source.node_data,
                graph=graph,
                node_definition=source.node_definition,
            ):
                patches[source.node_name] = NodeBehaviorPatch(
                    card=CardBehaviorPatch(
                        hidden=True,
                        reveal_mode=RevealMode.NONE,
                        enabled_switch_policy=EnabledSwitchPolicy.NEVER,
                    )
                )
        return patches


__all__ = ["DirectOutputBehaviorInferenceService"]

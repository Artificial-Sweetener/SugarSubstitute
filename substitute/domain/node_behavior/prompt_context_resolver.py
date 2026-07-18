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

"""Resolve reliable prompt-pair contexts from typed semantic sink anchors."""

from __future__ import annotations

from collections import defaultdict

from .models import PromptRole
from .prompt_graph import (
    PromptDetectionResult,
    PromptFieldLocator,
    PromptGraphContext,
)


class PromptGraphContextResolver:
    """Group detected prompt roles only where one typed sink owns both roles."""

    def resolve(
        self,
        detection_result: PromptDetectionResult,
    ) -> tuple[PromptGraphContext, ...]:
        """Return stable contexts without pairing authored-only prompt fields."""

        fields_by_anchor: dict[
            str,
            dict[PromptRole, list[PromptFieldLocator]],
        ] = defaultdict(lambda: defaultdict(list))
        anchor_order: list[str] = []
        for detection in detection_result.detections:
            for sink in detection.semantic_sinks:
                if sink.node_name not in fields_by_anchor:
                    anchor_order.append(sink.node_name)
                role_fields = fields_by_anchor[sink.node_name][detection.role]
                if detection.locator not in role_fields:
                    role_fields.append(detection.locator)

        contexts: list[PromptGraphContext] = []
        for anchor_node_name in anchor_order:
            by_role = fields_by_anchor[anchor_node_name]
            positive = tuple(by_role.get(PromptRole.POSITIVE, ()))
            negative = tuple(by_role.get(PromptRole.NEGATIVE, ()))
            if not positive or not negative:
                continue
            contexts.append(
                PromptGraphContext(
                    anchor_node_name=anchor_node_name,
                    positive_fields=positive,
                    negative_fields=negative,
                )
            )
        return tuple(contexts)


__all__ = ["PromptGraphContextResolver"]

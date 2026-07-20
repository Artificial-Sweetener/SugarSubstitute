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

"""Resolve field-label ownership during the existing behavior snapshot pass."""

from __future__ import annotations

from collections.abc import Mapping

from substitute.domain.node_behavior import FieldBehavior, FieldLabelSource


class FieldLabelSourceResolver:
    """Classify label ownership from behavior and definition provenance."""

    @staticmethod
    def resolve(
        *,
        field_behavior: FieldBehavior,
        metadata: Mapping[str, object],
    ) -> FieldLabelSource:
        """Return the authoritative owner without lookup or string comparison."""

        if field_behavior.label_override is not None:
            source = field_behavior.label_override_source
            if source is None:
                raise ValueError("Resolved field label override has no source.")
            return source
        if metadata.get("subgraph_wrapper") is True and _has_label(metadata):
            return FieldLabelSource.WRAPPER_AUTHORED
        return FieldLabelSource.COMFY_DEFINITION


def _has_label(metadata: Mapping[str, object]) -> bool:
    """Return whether wrapper metadata carries a nonempty public label."""

    label = metadata.get("label")
    return isinstance(label, str) and bool(label.strip())


__all__ = ["FieldLabelSourceResolver"]

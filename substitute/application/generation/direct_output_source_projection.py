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

"""Adapt direct-workflow output identities to listener contracts."""

from __future__ import annotations

from substitute.application.direct_workflows import DirectWorkflowExecutionProjection
from substitute.application.ports import ListenerOutputSource


def project_listener_output_sources(
    projection: DirectWorkflowExecutionProjection,
) -> tuple[ListenerOutputSource, ...]:
    """Return typed listener sources for one direct execution projection."""

    return tuple(
        ListenerOutputSource(
            node_id=source.node_id,
            source_key=source.source_key,
            source_label=source.source_label,
            media_kind=source.media_kind,
        )
        for source in projection.output_sources
    )


__all__ = ["project_listener_output_sources"]

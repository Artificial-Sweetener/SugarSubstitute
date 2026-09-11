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

"""Project accepted SugarCubes execution identities into visual run context."""

from __future__ import annotations

from dataclasses import replace

from substitute.application.ports.comfy_gateway import (
    ListenerOutputSource,
    QueueVisualRunContext,
)


def attach_native_visual_sources(
    context: QueueVisualRunContext,
    *,
    output_sources: tuple[ListenerOutputSource, ...],
    execution_sources: tuple[ListenerOutputSource, ...],
) -> QueueVisualRunContext:
    """Attach report-authoritative source identities before listener startup."""

    sources: dict[str, dict[str, str]] = {}
    for source in (*execution_sources, *output_sources):
        sources[source.node_id] = {
            "sourceKey": source.source_key,
            "sourceLabel": source.source_label,
            "cubeAlias": source.source_label,
        }
    return replace(context, sources=sources)


__all__ = ["attach_native_visual_sources"]

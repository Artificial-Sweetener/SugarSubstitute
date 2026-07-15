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

"""Adapt Output projection state for composition factories."""

from __future__ import annotations

from collections.abc import MutableMapping
from uuid import UUID

from substitute.application.workflows.canvas_route_projector_port import (
    CanvasRouteIdentity,
)
from substitute.application.workflows.output_canvas_projection import (
    OutputCanvasProjection,
)
from substitute.application.workflows.output_canvas_session import OutputCanvasSession
from substitute.application.workflows.output_canvas_route_scope import (
    scene_overview_route_identity,
    source_grid_route_identity,
)


def _output_projection_for(host: object) -> OutputCanvasProjection | None:
    """Return the host projection when it has the expected DTO type."""

    projection = getattr(host, "_output_projection", None)
    return projection if isinstance(projection, OutputCanvasProjection) else None


def _output_session_for(host: object) -> OutputCanvasSession | None:
    """Return the host Output session when bound."""

    session = getattr(host, "_output_session", None)
    return session if isinstance(session, OutputCanvasSession) else None


def _compare_clear_route_identity(host: object) -> CanvasRouteIdentity:
    """Return the Output route whose compare rendering should be cleared."""

    if bool(getattr(host, "active_scene_overview", False)):
        return scene_overview_route_identity(
            active_scene_key=getattr(host, "active_scene_key", None),
        )
    active_source_key = getattr(host, "active_source_key", None)
    if active_source_key is not None and int(getattr(host, "active_set_index", 0)) == 0:
        return source_grid_route_identity(
            source_key=str(active_source_key),
            active_scene_key=getattr(host, "active_scene_key", None),
        )
    return CanvasRouteIdentity.empty()


def _allowed_output_image_ids_for(host: object) -> frozenset[UUID]:
    """Return authorized final-output image ids for a bound Output host."""

    session = _output_session_for(host)
    return session.allowed_image_ids if session is not None else frozenset()


def _active_scene_key_for(host: object) -> str | None:
    """Return the active scene key when it is a concrete route key."""

    scene_key = getattr(host, "active_scene_key", None)
    return scene_key if isinstance(scene_key, str) else None


def _active_source_key_for(host: object) -> str | None:
    """Return the active source key when it is a concrete route key."""

    source_key = getattr(host, "active_source_key", None)
    return source_key if isinstance(source_key, str) else None


def _source_tab_cache_signature_for(
    host: object,
) -> tuple[tuple[str, str], ...] | None:
    """Return cached source-tab identity when the host has one."""

    signature = getattr(host, "_source_tab_cache_signature", None)
    return signature if isinstance(signature, tuple) else None


def _source_tab_tooltip_filters_for(host: object) -> MutableMapping[str, object]:
    """Return mutable source-tab tooltip filter storage for the host."""

    filters = getattr(host, "_source_tab_tooltip_filters", None)
    if isinstance(filters, dict):
        return filters
    filters = {}
    setattr(host, "_source_tab_tooltip_filters", filters)
    return filters


def _host_width_for(host: object) -> int | None:
    """Return the host widget width when it can be measured."""

    width = getattr(host, "width", None)
    return int(width()) if callable(width) else None

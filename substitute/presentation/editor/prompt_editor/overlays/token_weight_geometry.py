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

"""Prepare prompt token-weight control geometry for overlay consumers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import QWidget

from ..projection.model import (
    PromptProjectionDisplayMode,
    PromptProjectionToken,
    PromptProjectionTokenKind,
    PromptWeightControlIdentity,
    prompt_weight_control_identity,
)
from .token_weight_view import triangle_vertical_inset


_WEIGHT_CONTROL_TOKEN_KINDS = frozenset(
    {
        PromptProjectionTokenKind.EMPHASIS,
        PromptProjectionTokenKind.LORA,
        PromptProjectionTokenKind.WILDCARD,
    }
)


class PromptTokenWeightProjectionSnapshot(Protocol):
    """Describe the projection snapshot consumed by token-weight geometry."""

    @property
    def display_mode(self) -> PromptProjectionDisplayMode:
        """Return whether the projection is raw or rich/projected."""
        ...

    @property
    def tokens(self) -> Sequence[PromptProjectionToken]:
        """Return prepared projection tokens available to overlays."""
        ...


class PromptTokenWeightGeometrySurface(Protocol):
    """Describe projection APIs required to prepare token-weight geometry."""

    def viewport(self) -> QWidget:
        """Return the projection viewport used for coordinate mapping."""

    def projection_document(self) -> PromptTokenWeightProjectionSnapshot:
        """Return the current projection snapshot."""

    def token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the projected token painted at one viewport-local point."""

    def token_anchor_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local control anchor for one token."""

    def token_weight_text_rect(self, token: PromptProjectionToken) -> QRectF | None:
        """Return the viewport-local painted weight rect for one token."""


@dataclass(frozen=True, slots=True)
class PromptTokenWeightControlGeometry:
    """Describe one prepared host-local control geometry item."""

    token: PromptProjectionToken
    control_identity: PromptWeightControlIdentity
    anchor_rect: QRectF
    increase_rect: QRectF
    decrease_rect: QRectF
    activation_rect: QRectF
    weight_text_rect: QRectF | None = None
    weight_text_viewport_rect: QRectF | None = None


@dataclass(frozen=True, slots=True)
class PromptTokenWeightGeometrySnapshot:
    """Describe all prepared token-weight geometry for one projection state."""

    controls: tuple[PromptTokenWeightControlGeometry, ...] = ()

    def geometry_at_pointer(
        self,
        pointer_position: QPointF | None,
    ) -> PromptTokenWeightControlGeometry | None:
        """Return the nearest control whose activation rect contains the pointer."""

        if pointer_position is None:
            return None
        matching_geometries: list[tuple[float, PromptTokenWeightControlGeometry]] = []
        for geometry in self.controls:
            if not geometry.activation_rect.contains(pointer_position):
                continue
            delta_x = geometry.anchor_rect.center().x() - pointer_position.x()
            delta_y = geometry.anchor_rect.center().y() - pointer_position.y()
            matching_geometries.append(
                ((delta_x * delta_x) + (delta_y * delta_y), geometry)
            )
        if not matching_geometries:
            return None
        matching_geometries.sort(key=lambda entry: entry[0])
        return matching_geometries[0][1]

    def geometry_for_token(
        self,
        token: PromptProjectionToken | None,
    ) -> PromptTokenWeightControlGeometry | None:
        """Return prepared geometry matching one current or cached token."""

        if token is None:
            return None
        identity = prompt_weight_control_identity(token)
        for geometry in self.controls:
            if geometry.control_identity == identity:
                return geometry
        for geometry in self.controls:
            if tokens_share_content_range(geometry.token, token):
                return geometry
        return None

    def token_at_weight_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the token whose prepared weight rect contains the viewport point."""

        for geometry in self.controls:
            rect = geometry.weight_text_viewport_rect
            if rect is not None and rect.contains(position):
                return geometry.token
        return None

    def current_token_for(
        self,
        token: PromptProjectionToken,
    ) -> PromptProjectionToken | None:
        """Return the current prepared token matching one cached weighted token."""

        geometry = self.geometry_for_token(token)
        return None if geometry is None else geometry.token


class PromptTokenWeightGeometry:
    """Build token-weight control visibility and host-local geometry snapshots."""

    def __init__(
        self,
        surface: PromptTokenWeightGeometrySurface,
        *,
        host: QWidget,
        control_width: float,
        control_height: float,
        control_gap: float,
        control_margin: float,
        overlay_padding: float,
    ) -> None:
        """Create the geometry owner for one non-clipping token overlay host."""

        self._surface = surface
        self._host = host
        self._control_width = control_width
        self._control_height = control_height
        self._control_gap = control_gap
        self._control_margin = control_margin
        self._overlay_padding = overlay_padding

    def build_snapshot(self) -> PromptTokenWeightGeometrySnapshot:
        """Return prepared geometry for all currently visible weighted tokens."""

        document = self._surface.projection_document()
        if document.display_mode is PromptProjectionDisplayMode.RAW:
            return PromptTokenWeightGeometrySnapshot()
        controls: list[PromptTokenWeightControlGeometry] = []
        for token in document.tokens:
            geometry = self.geometry_for_token(token)
            if geometry is not None:
                controls.append(geometry)
        return PromptTokenWeightGeometrySnapshot(tuple(controls))

    def geometry_for_token(
        self,
        token: PromptProjectionToken,
    ) -> PromptTokenWeightControlGeometry | None:
        """Return host-local control geometry for one weighted token."""

        if not token_supports_numeric_controls(token):
            return None
        anchor_rect = self._surface.token_anchor_rect(token)
        if anchor_rect is None:
            return None

        host_anchor = self._viewport_rect_to_host_rect(anchor_rect)
        if host_anchor is None:
            return None
        increase_rect, decrease_rect = stacked_triangle_control_rects(
            anchor_rect=host_anchor,
            host_rect=self.host_rect(),
            control_width=self._control_width,
            control_height=self._control_height,
            vertical_gap=self._control_gap,
            margin=self._control_margin,
        )
        weight_text_viewport_rect = self._surface.token_weight_text_rect(token)
        weight_text_rect = (
            None
            if weight_text_viewport_rect is None
            else self._viewport_rect_to_host_rect(weight_text_viewport_rect)
        )
        return PromptTokenWeightControlGeometry(
            token=token,
            control_identity=prompt_weight_control_identity(token),
            anchor_rect=host_anchor,
            increase_rect=increase_rect,
            decrease_rect=decrease_rect,
            activation_rect=host_anchor.united(increase_rect).united(decrease_rect),
            weight_text_rect=weight_text_rect,
            weight_text_viewport_rect=weight_text_viewport_rect,
        )

    def weighted_token_at_viewport_position(
        self,
        position: QPointF,
    ) -> PromptProjectionToken | None:
        """Return the weighted token painted under one viewport-local point."""

        token = self._surface.token_at_viewport_position(position)
        if token is None or not token_supports_numeric_controls(token):
            return None
        return token

    def host_point_from_viewport_position(
        self,
        viewport_position: QPointF,
    ) -> QPointF | None:
        """Map one viewport-local point into host-local coordinates."""

        try:
            return QPointF(
                self._host.mapFromGlobal(
                    self._surface.viewport().mapToGlobal(viewport_position.toPoint())
                )
            )
        except RuntimeError:
            return None

    def host_point_from_global(self, global_position: QPointF) -> QPointF | None:
        """Map one global point into host-local coordinates."""

        try:
            return QPointF(self._host.mapFromGlobal(global_position.toPoint()))
        except RuntimeError:
            return None

    def global_position_from_host_position(
        self,
        host_position: QPointF,
    ) -> QPointF:
        """Map one host-local point into global coordinates."""

        try:
            return QPointF(self._host.mapToGlobal(host_position.toPoint()))
        except RuntimeError:
            return QPointF()

    def host_rect(self) -> QRectF:
        """Return the host rect, or an empty rect when Qt is tearing down."""

        try:
            return QRectF(self._host.rect())
        except RuntimeError:
            return QRectF()

    def overlay_bounds(
        self,
        rects: tuple[QRectF | None, ...],
    ) -> QRectF | None:
        """Return padded host-local overlay bounds for prepared visible rects."""

        visible_rects = [rect for rect in rects if rect is not None]
        if not visible_rects:
            return None
        bounds = QRectF(visible_rects[0])
        for rect in visible_rects[1:]:
            bounds = bounds.united(rect)
        return bounds.adjusted(
            -self._overlay_padding,
            -self._overlay_padding,
            self._overlay_padding,
            self._overlay_padding,
        )

    def _viewport_rect_to_host_rect(self, viewport_rect: QRectF) -> QRectF | None:
        """Map one viewport-local rect into host-local coordinates."""

        host_top_left = self.host_point_from_viewport_position(viewport_rect.topLeft())
        if host_top_left is None:
            return None
        return QRectF(host_top_left, viewport_rect.size())


def token_supports_numeric_controls(token: PromptProjectionToken) -> bool:
    """Return whether one projected token should expose numeric controls."""

    if token.kind is PromptProjectionTokenKind.WILDCARD:
        return token.wildcard_can_step_tag
    return token.kind in _WEIGHT_CONTROL_TOKEN_KINDS


def tokens_share_content_range(
    left: PromptProjectionToken,
    right: PromptProjectionToken,
) -> bool:
    """Return whether two tokens describe the same weighted source content."""

    if left.content_start is not None and right.content_start is not None:
        return (
            left.content_start == right.content_start
            and left.content_end == right.content_end
        )
    return (
        left.source_start == right.source_start and left.source_end == right.source_end
    )


def stacked_triangle_control_rects(
    *,
    anchor_rect: QRectF,
    host_rect: QRectF,
    control_width: float,
    control_height: float,
    vertical_gap: float,
    margin: float,
) -> tuple[QRectF, QRectF]:
    """Return control rects whose triangle glyphs hug one anchor rect."""

    clamped_width = max(1.0, min(control_width, host_rect.width() - margin * 2.0))
    triangle_inset = triangle_vertical_inset(control_height)
    left = max(
        host_rect.left() + margin,
        min(
            anchor_rect.center().x() - clamped_width / 2.0,
            host_rect.right() - clamped_width - margin,
        ),
    )
    increase_rect = QRectF(
        left,
        anchor_rect.top() - vertical_gap - control_height + triangle_inset,
        clamped_width,
        control_height,
    )
    decrease_rect = QRectF(
        left,
        anchor_rect.bottom() + vertical_gap - triangle_inset,
        clamped_width,
        control_height,
    )
    if increase_rect.top() < host_rect.top() + margin:
        increase_rect.moveTop(host_rect.top() + margin)
    if decrease_rect.bottom() > host_rect.bottom() - margin:
        decrease_rect.moveBottom(host_rect.bottom() - margin)
    return increase_rect, decrease_rect


__all__ = [
    "PromptTokenWeightControlGeometry",
    "PromptTokenWeightGeometry",
    "PromptTokenWeightGeometrySnapshot",
    "PromptTokenWeightGeometrySurface",
    "PromptTokenWeightProjectionSnapshot",
    "stacked_triangle_control_rects",
    "token_supports_numeric_controls",
    "tokens_share_content_range",
]

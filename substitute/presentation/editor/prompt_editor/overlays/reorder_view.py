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

"""Render prepared prompt-segment reorder chrome without owning reorder policy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPaintEvent, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import QWidget
from qfluentwidgets.common.style_sheet import isDarkTheme, themeColor  # type: ignore[import-untyped]

from ..projection.chip_painter import PromptProjectionChipPainter
from ..projection.observability import (
    log_reorder_drag_event,
    log_reorder_drag_timing,
    reorder_drag_started_at,
)
from ..projection.reorder_chip_geometry import PromptReorderChipGeometry
from ..projection.reorder_visual_snapshot import paint_reorder_projection_snapshot
from .chip_painter import PromptChipPaintStyle, PromptChipPainter
from .chip_visuals import PROMPT_CHIP_BUBBLE_RADIUS, PromptChipVisual
from .reorder_visual_cache import (
    PromptReorderChipVisualSnapshot,
    translated_snapshot_offset,
)
from .reorder_raster_cache import ReorderRasterEntry

_REORDER_MARKER_RADIUS = 3.0
_REORDER_PAINT_BUDGET_MS = 8.0
_MINIMUM_TEXT_CONTRAST_RATIO = 4.5


def _relative_luminance_component(component: float) -> float:
    """Convert one sRGB channel into the linear luminance component."""

    normalized = component / 255.0
    if normalized <= 0.03928:
        return normalized / 12.92
    return float(((normalized + 0.055) / 1.055) ** 2.4)


def _relative_luminance(color: QColor) -> float:
    """Return the WCAG relative luminance for the supplied color."""

    red = float(color.red())
    green = float(color.green())
    blue = float(color.blue())
    return (
        (0.2126 * _relative_luminance_component(red))
        + (0.7152 * _relative_luminance_component(green))
        + (0.0722 * _relative_luminance_component(blue))
    )


def _contrast_ratio(foreground: QColor, background: QColor) -> float:
    """Return the WCAG contrast ratio for one foreground/background pair."""

    lighter = max(_relative_luminance(foreground), _relative_luminance(background))
    darker = min(_relative_luminance(foreground), _relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _readable_surface_text_color(*, preferred: QColor, background: QColor) -> QColor:
    """Choose readable text color while honoring the preferred tone when safe."""

    if _contrast_ratio(preferred, background) >= _MINIMUM_TEXT_CONTRAST_RATIO:
        return QColor(preferred)

    dark_fallback = QColor(32, 34, 36)
    light_fallback = QColor(248, 249, 250)
    if _contrast_ratio(light_fallback, background) >= _contrast_ratio(
        dark_fallback,
        background,
    ):
        return light_fallback
    return dark_fallback


@dataclass(frozen=True, slots=True)
class PromptReorderChipPaintState:
    """Describe one prepared reorder chip chrome item to paint."""

    segment_index: int
    style: PromptChipPaintStyle
    geometry: PromptReorderChipGeometry | None = None
    visual: PromptChipVisual | None = None
    visual_snapshot: PromptReorderChipVisualSnapshot | None = None
    raster_entry: ReorderRasterEntry | None = None

    @property
    def owns_projection_text(self) -> bool:
        """Return whether this state can replace surface-painted chip text."""

        return self.visual is not None and (
            self.visual_snapshot is not None
            and bool(self.visual_snapshot.projection_snapshot.fragments)
        )


@dataclass(frozen=True, slots=True)
class PromptReorderMarkerPaintState:
    """Describe one prepared insertion marker to paint."""

    rect: QRectF
    color: QColor


@dataclass(frozen=True, slots=True)
class PromptReorderLandingPreviewPaintState:
    """Describe one prepared landing preview or pending shadow to paint."""

    style: PromptChipPaintStyle
    geometry: PromptReorderChipGeometry | None = None
    visual: PromptChipVisual | None = None


@dataclass(frozen=True, slots=True)
class PromptReorderChipInteractionState:
    """Describe logical interaction state for one pointer region."""

    segment_index: int
    active: bool
    dragging: bool
    hovered: bool
    pressed: bool
    cursor_shape: Qt.CursorShape
    style: PromptChipPaintStyle


@dataclass(frozen=True, slots=True)
class PromptReorderViewRenderState:
    """Describe all prepared chrome needed by the passive reorder view."""

    preview_active: bool = False
    live_chips: tuple[PromptReorderChipPaintState, ...] = ()
    preview_chips: tuple[PromptReorderChipPaintState, ...] = ()
    marker: PromptReorderMarkerPaintState | None = None
    landing_preview: PromptReorderLandingPreviewPaintState | None = None
    gesture_id: int | None = None
    event_id: int | None = None
    dragged_segment_index: int | None = None
    raster_paint_count: int = 0


@dataclass(frozen=True, slots=True)
class PromptReorderVisualStyle:
    """Own palette-derived reorder colors independently of source and commands."""

    rest_fill: QColor
    rest_border: QColor
    hover_fill: QColor
    hover_border: QColor
    active_fill: QColor
    active_border: QColor
    drag_fill: QColor
    drag_border: QColor
    marker_color: QColor
    _rest_style: PromptChipPaintStyle = field(init=False, repr=False, compare=False)
    _hover_style: PromptChipPaintStyle = field(
        init=False,
        repr=False,
        compare=False,
    )
    _active_style: PromptChipPaintStyle = field(
        init=False,
        repr=False,
        compare=False,
    )
    _drag_style: PromptChipPaintStyle = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Prepare the four immutable interaction styles once per theme state."""

        object.__setattr__(
            self,
            "_rest_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.rest_fill),
                border_color=QColor(self.rest_border),
            ),
        )
        object.__setattr__(
            self,
            "_hover_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.hover_fill),
                border_color=QColor(self.hover_border),
            ),
        )
        object.__setattr__(
            self,
            "_active_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.active_fill),
                border_color=QColor(self.active_border),
            ),
        )
        object.__setattr__(
            self,
            "_drag_style",
            PromptChipPaintStyle(
                fill_color=QColor(self.drag_fill),
                border_color=QColor(self.drag_border),
            ),
        )

    @classmethod
    def from_current_theme(cls) -> PromptReorderVisualStyle:
        """Build reorder colors from the current qfluent theme accent."""

        accent = QColor(themeColor())
        rest_border = QColor(accent)
        rest_border.setAlpha(96 if isDarkTheme() else 82)
        rest_fill = QColor(accent)
        rest_fill.setAlpha(18 if isDarkTheme() else 14)
        hover_fill = QColor(accent)
        hover_fill.setAlpha(28 if isDarkTheme() else 22)
        hover_border = QColor(accent)
        hover_border.setAlpha(138 if isDarkTheme() else 120)
        active_fill = QColor(accent)
        active_fill.setAlpha(34 if isDarkTheme() else 28)
        active_border = QColor(accent)
        active_border.setAlpha(160 if isDarkTheme() else 140)
        drag_fill = QColor(accent)
        drag_fill.setAlpha(38 if isDarkTheme() else 30)
        drag_border = QColor(accent)
        drag_border.setAlpha(176 if isDarkTheme() else 148)
        marker_color = QColor(accent)
        marker_color.setAlpha(240 if isDarkTheme() else 214)
        return cls(
            rest_fill=rest_fill,
            rest_border=rest_border,
            hover_fill=hover_fill,
            hover_border=hover_border,
            active_fill=active_fill,
            active_border=active_border,
            drag_fill=drag_fill,
            drag_border=drag_border,
            marker_color=marker_color,
        )

    def colors_for_segment(
        self,
        segment_index: int,
        *,
        dragged_segment_index: int | None,
        hovered_segment_index: int | None,
        active_segment_index: int | None,
    ) -> tuple[QColor, QColor]:
        """Return prepared chrome colors for one segment visual state."""

        if segment_index == dragged_segment_index:
            return QColor(self.drag_fill), QColor(self.drag_border)
        if segment_index == hovered_segment_index:
            return QColor(self.hover_fill), QColor(self.hover_border)
        if segment_index == active_segment_index:
            return QColor(self.active_fill), QColor(self.active_border)
        return QColor(self.rest_fill), QColor(self.rest_border)

    def paint_style_for_segment(
        self,
        segment_index: int,
        *,
        dragged_segment_index: int | None,
        hovered_segment_index: int | None,
        active_segment_index: int | None,
    ) -> PromptChipPaintStyle:
        """Return the prepared chip paint style for one segment."""

        if segment_index == dragged_segment_index:
            return self._drag_style
        if segment_index == hovered_segment_index:
            return self._hover_style
        if segment_index == active_segment_index:
            return self._active_style
        return self._rest_style

    def outline_style(
        self, *, opacity: float, outline_width: float
    ) -> PromptChipPaintStyle:
        """Return the prepared outline style for landing previews."""

        return PromptChipPaintStyle(
            fill_color=QColor(self.active_fill),
            border_color=QColor(self.active_border),
            outline_only=True,
            outline_width=outline_width,
            opacity=opacity,
        )


@dataclass(frozen=True, slots=True)
class PromptReorderViewRenderInput:
    """Carry prepared overlay state needed to build passive render state."""

    visual_style: PromptReorderVisualStyle
    preview_active: bool
    live_ordered_segment_indices: Sequence[int]
    preview_ordered_segment_indices: Sequence[int]
    live_geometries_by_index: Mapping[int, PromptReorderChipGeometry]
    preview_geometries_by_index: Mapping[int, PromptReorderChipGeometry]
    live_visuals_by_index: Mapping[int, PromptChipVisual]
    preview_visuals_by_index: Mapping[int, PromptChipVisual]
    dragged_segment_index: int | None
    hovered_segment_index: int | None
    active_segment_index: int | None
    live_visual_snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot] = (
        field(default_factory=dict)
    )
    preview_visual_snapshots_by_index: Mapping[int, PromptReorderChipVisualSnapshot] = (
        field(default_factory=dict)
    )
    live_raster_entries_by_index: Mapping[int, ReorderRasterEntry] = field(
        default_factory=dict
    )
    preview_raster_entries_by_index: Mapping[int, ReorderRasterEntry] = field(
        default_factory=dict
    )
    marker_rect: QRectF | None = None
    landing_preview: PromptReorderLandingPreviewPaintState | None = None
    gesture_id: int | None = None
    event_id: int | None = None
    paint_rect_overrides_by_index: Mapping[int, QRectF] = field(default_factory=dict)


def prompt_reorder_chip_interaction_state(
    segment_index: int,
    *,
    visual_style: PromptReorderVisualStyle,
    dragged_segment_index: int | None,
    hovered_segment_index: int | None,
    active_segment_index: int | None,
    pressed_segment_index: int | None,
) -> PromptReorderChipInteractionState:
    """Map gesture state to one logical pointer region."""

    active = segment_index == active_segment_index
    dragging = segment_index == dragged_segment_index
    hovered = segment_index == hovered_segment_index
    pressed = segment_index == pressed_segment_index
    cursor_shape = (
        Qt.CursorShape.ClosedHandCursor
        if dragging or pressed
        else Qt.CursorShape.OpenHandCursor
    )
    return PromptReorderChipInteractionState(
        segment_index=segment_index,
        active=active,
        dragging=dragging,
        hovered=hovered,
        pressed=pressed,
        cursor_shape=cursor_shape,
        style=visual_style.paint_style_for_segment(
            segment_index,
            dragged_segment_index=dragged_segment_index,
            hovered_segment_index=hovered_segment_index,
            active_segment_index=active_segment_index,
        ),
    )


def prompt_reorder_chip_interaction_states(
    segment_indices: Sequence[int],
    *,
    visual_style: PromptReorderVisualStyle,
    dragged_segment_index: int | None,
    hovered_segment_index: int | None,
    active_segment_index: int | None,
    pressed_segment_index: int | None,
) -> tuple[PromptReorderChipInteractionState, ...]:
    """Map gesture state to every visible logical pointer region."""

    return tuple(
        prompt_reorder_chip_interaction_state(
            segment_index,
            visual_style=visual_style,
            dragged_segment_index=dragged_segment_index,
            hovered_segment_index=hovered_segment_index,
            active_segment_index=active_segment_index,
            pressed_segment_index=pressed_segment_index,
        )
        for segment_index in segment_indices
    )


def prompt_reorder_chip_paint_states(
    segment_indices: Sequence[int],
    *,
    geometries_by_index: Mapping[int, PromptReorderChipGeometry],
    visuals_by_index: Mapping[int, PromptChipVisual],
    visual_snapshots_by_index: (
        Mapping[int, PromptReorderChipVisualSnapshot] | None
    ) = None,
    raster_entries_by_index: Mapping[int, ReorderRasterEntry] | None = None,
    paint_rect_overrides_by_index: Mapping[int, QRectF] | None = None,
    visual_style: PromptReorderVisualStyle,
    dragged_segment_index: int | None,
    hovered_segment_index: int | None,
    active_segment_index: int | None,
    skip_dragged_segment: bool,
) -> tuple[PromptReorderChipPaintState, ...]:
    """Build prepared chip paint state from projection geometry and visuals."""

    states: list[PromptReorderChipPaintState] = []
    paint_rect_overrides = paint_rect_overrides_by_index or {}
    visual_snapshots = visual_snapshots_by_index or {}
    raster_entries = raster_entries_by_index or {}
    for segment_index in segment_indices:
        if skip_dragged_segment and segment_index == dragged_segment_index:
            continue
        geometry = geometries_by_index.get(segment_index)
        visual = visuals_by_index.get(segment_index)
        visual_snapshot = visual_snapshots.get(segment_index)
        paint_rect_override = paint_rect_overrides.get(segment_index)
        if paint_rect_override is not None:
            visual = _visual_translated_to_hotspot_rect(
                visual
                if visual is not None
                else (
                    None
                    if geometry is None
                    else prompt_reorder_visual_for_chip_geometry(geometry)
                ),
                paint_rect_override,
            )
            geometry = None
        if geometry is None and visual is None:
            continue
        states.append(
            PromptReorderChipPaintState(
                segment_index=segment_index,
                geometry=geometry,
                visual=visual,
                visual_snapshot=visual_snapshot,
                raster_entry=raster_entries.get(segment_index),
                style=visual_style.paint_style_for_segment(
                    segment_index,
                    dragged_segment_index=dragged_segment_index,
                    hovered_segment_index=hovered_segment_index,
                    active_segment_index=active_segment_index,
                ),
            )
        )
    return tuple(states)


def prompt_reorder_marker_paint_state(
    marker_rect: QRectF | None,
    *,
    visual_style: PromptReorderVisualStyle,
) -> PromptReorderMarkerPaintState | None:
    """Build prepared insertion-marker paint state from a resolved marker rect."""

    if marker_rect is None:
        return None
    return PromptReorderMarkerPaintState(
        rect=QRectF(marker_rect),
        color=QColor(visual_style.marker_color),
    )


def prompt_reorder_view_render_state(
    render_input: PromptReorderViewRenderInput,
) -> PromptReorderViewRenderState:
    """Build all prepared reorder paint state for the passive overlay view."""

    preview_chips = (
        prompt_reorder_chip_paint_states(
            render_input.preview_ordered_segment_indices,
            geometries_by_index=render_input.preview_geometries_by_index,
            visuals_by_index=render_input.preview_visuals_by_index,
            visual_snapshots_by_index=render_input.preview_visual_snapshots_by_index,
            raster_entries_by_index=render_input.preview_raster_entries_by_index,
            paint_rect_overrides_by_index=(render_input.paint_rect_overrides_by_index),
            visual_style=render_input.visual_style,
            dragged_segment_index=render_input.dragged_segment_index,
            hovered_segment_index=render_input.hovered_segment_index,
            active_segment_index=render_input.active_segment_index,
            skip_dragged_segment=True,
        )
        if render_input.preview_active
        else ()
    )
    live_chips = (
        ()
        if render_input.preview_active
        else prompt_reorder_chip_paint_states(
            render_input.live_ordered_segment_indices,
            geometries_by_index=render_input.live_geometries_by_index,
            visuals_by_index=render_input.live_visuals_by_index,
            visual_snapshots_by_index=render_input.live_visual_snapshots_by_index,
            raster_entries_by_index=render_input.live_raster_entries_by_index,
            paint_rect_overrides_by_index=(render_input.paint_rect_overrides_by_index),
            visual_style=render_input.visual_style,
            dragged_segment_index=render_input.dragged_segment_index,
            hovered_segment_index=render_input.hovered_segment_index,
            active_segment_index=render_input.active_segment_index,
            skip_dragged_segment=False,
        )
    )
    painted_chips = preview_chips if render_input.preview_active else live_chips
    state = PromptReorderViewRenderState(
        preview_active=render_input.preview_active,
        live_chips=live_chips,
        preview_chips=preview_chips,
        marker=prompt_reorder_marker_paint_state(
            render_input.marker_rect,
            visual_style=render_input.visual_style,
        ),
        landing_preview=render_input.landing_preview,
        gesture_id=render_input.gesture_id,
        event_id=render_input.event_id,
        dragged_segment_index=render_input.dragged_segment_index,
        raster_paint_count=sum(1 for chip in painted_chips if chip.raster_entry),
    )
    return state


class PromptReorderView(QWidget):
    """Paint prepared reorder chrome while leaving gesture and layout elsewhere."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the passive reorder paint surface."""

        super().__init__(parent)
        self.setObjectName("segmentReorderView")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._render_state = PromptReorderViewRenderState()
        self._paint_region = QRegion()
        self._chip_painter = PromptChipPainter()
        self._projection_chip_painter = PromptProjectionChipPainter()

    @property
    def render_state(self) -> PromptReorderViewRenderState:
        """Return the prepared render state currently painted by the view."""

        return self._render_state

    def set_render_state(self, state: PromptReorderViewRenderState) -> None:
        """Replace the prepared render state and schedule a repaint."""

        previous_region = QRegion(self._paint_region)
        self._render_state = state
        self._paint_region = _paint_region_for_render_state(state)
        exposed_region = previous_region.subtracted(self._paint_region)
        parent = self.parentWidget()
        if parent is not None and not exposed_region.isEmpty():
            parent.update(exposed_region)
        self.update(self._paint_region)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint prepared reorder chips, landing previews, and insertion markers."""

        started_at = reorder_drag_started_at()
        state = self._render_state
        if self._paint_region.isEmpty():
            return
        painter = QPainter(self)
        paint_bounds = event.region().boundingRect()
        try:
            painter.setClipRegion(self._paint_region)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._paint_chips(
                painter,
                state.preview_chips if state.preview_active else state.live_chips,
            )
            if state.landing_preview is not None:
                self._paint_landing_preview(painter, state.landing_preview)
            if state.marker is not None:
                self._paint_marker(painter, state.marker)
        finally:
            painter.end()
        paint_elapsed_ms = log_reorder_drag_timing(
            "reorder_view.paint",
            started_at=started_at,
            gesture_id=state.gesture_id,
            event_id=state.event_id,
            preview_active=state.preview_active,
            preview_visual_count=len(state.preview_chips),
            live_visual_count=len(state.live_chips),
            marker_visible=state.marker is not None,
            landing_preview_visible=state.landing_preview is not None,
            dragged_segment_index=state.dragged_segment_index,
            paint_bounds_width=paint_bounds.width(),
            paint_bounds_height=paint_bounds.height(),
        )
        if paint_elapsed_ms >= _REORDER_PAINT_BUDGET_MS:
            log_reorder_drag_event(
                "budget.reorder_view_paint_exceeded",
                gesture_id=state.gesture_id,
                event_id=state.event_id,
                elapsed_ms=f"{paint_elapsed_ms:.3f}",
                threshold_ms=f"{_REORDER_PAINT_BUDGET_MS:.3f}",
            )

    def _paint_chips(
        self,
        painter: QPainter,
        chips: tuple[PromptReorderChipPaintState, ...],
    ) -> None:
        """Paint every prepared reorder chip in order."""

        for chip in chips:
            if chip.raster_entry is not None and chip.visual is not None:
                painter.drawPixmap(
                    chip.raster_entry.top_left_for_rect(
                        QRectF(chip.visual.hotspot_rect)
                    ),
                    chip.raster_entry.pixmap,
                )
                continue
            if chip.visual_snapshot is not None and chip.visual is not None:
                self._chip_painter.paint_chrome(
                    painter=painter,
                    visual=chip.visual,
                    style=chip.style,
                )
                dx, dy = translated_snapshot_offset(
                    painted_rect=QRectF(chip.visual.hotspot_rect),
                    snapshot=chip.visual_snapshot,
                )
                painter.save()
                painter.translate(dx, dy)
                paint_reorder_projection_snapshot(
                    painter,
                    chip.visual_snapshot.projection_snapshot,
                )
                painter.restore()
                continue
            if chip.geometry is not None:
                self._projection_chip_painter.paint_chip_geometry(
                    painter=painter,
                    geometry=chip.geometry,
                    style=chip.style,
                )
            elif chip.visual is not None:
                self._chip_painter.paint_chrome(
                    painter=painter,
                    visual=chip.visual,
                    style=chip.style,
                )

    def _paint_landing_preview(
        self,
        painter: QPainter,
        landing_preview: PromptReorderLandingPreviewPaintState,
    ) -> None:
        """Paint the prepared landing preview or pending fallback shadow."""

        if landing_preview.geometry is not None:
            self._projection_chip_painter.paint_chip_geometry(
                painter=painter,
                geometry=landing_preview.geometry,
                style=landing_preview.style,
            )
        elif landing_preview.visual is not None:
            self._chip_painter.paint_chrome(
                painter=painter,
                visual=landing_preview.visual,
                style=landing_preview.style,
            )

    @staticmethod
    def _paint_marker(
        painter: QPainter,
        marker: PromptReorderMarkerPaintState,
    ) -> None:
        """Paint one prepared insertion marker."""

        painter.setBrush(marker.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            marker.rect, _REORDER_MARKER_RADIUS, _REORDER_MARKER_RADIUS
        )


def prompt_reorder_visual_for_chip_geometry(
    geometry: PromptReorderChipGeometry,
) -> PromptChipVisual:
    """Return overlay visual chrome state for one projection-owned chip geometry."""

    return PromptChipVisual(
        bubble_rects=tuple(line.content_rect for line in geometry.visual_lines),
        fragment_union_rect=QRectF(geometry.outline_bounds),
        hotspot_rect=geometry.hotspot_rect,
        slot_before=geometry.slot_before,
        slot_after=geometry.slot_after,
        marker_height=geometry.marker_height,
    )


def _visual_translated_to_hotspot_rect(
    visual: PromptChipVisual | None,
    hotspot_rect: QRectF,
) -> PromptChipVisual | None:
    """Return a visual copy translated so its hotspot starts at the target rect."""

    if visual is None:
        return None
    current_hotspot = QRectF(visual.hotspot_rect)
    dx = hotspot_rect.left() - current_hotspot.left()
    dy = hotspot_rect.top() - current_hotspot.top()
    translated_hotspot = QRectF(hotspot_rect).toAlignedRect()
    return PromptChipVisual(
        bubble_rects=tuple(rect.translated(dx, dy) for rect in visual.bubble_rects),
        fragment_union_rect=visual.fragment_union_rect.translated(dx, dy),
        hotspot_rect=translated_hotspot,
        slot_before=visual.slot_before + QPointF(dx, dy),
        slot_after=visual.slot_after + QPointF(dx, dy),
        marker_height=visual.marker_height,
        preferred_size=visual.preferred_size,
        text_translation=visual.text_translation,
    )


def _paint_region_for_render_state(state: PromptReorderViewRenderState) -> QRegion:
    """Return the widget region owned by the current reorder paint state."""

    region = QRegion()
    chips = state.preview_chips if state.preview_active else state.live_chips
    for chip in chips:
        chip_region = _paint_region_for_chip(chip)
        if not chip_region.isEmpty():
            region = region.united(chip_region)
    if state.landing_preview is not None:
        landing_region = _paint_region_for_landing_preview(state.landing_preview)
        if not landing_region.isEmpty():
            region = region.united(landing_region)
    if state.marker is not None:
        region = region.united(QRegion(_expanded_aligned_rect(state.marker.rect)))
    return region


def _paint_region_for_chip(chip: PromptReorderChipPaintState) -> QRegion:
    """Return the exact overlay region needed to paint one chip."""

    if chip.geometry is not None:
        return _paint_region_for_path(chip.geometry.chrome_path)
    if chip.visual is not None:
        return _paint_region_for_visual(chip.visual)
    return QRegion()


def _paint_region_for_landing_preview(
    landing_preview: PromptReorderLandingPreviewPaintState,
) -> QRegion:
    """Return the overlay region needed to paint a landing preview."""

    if landing_preview.geometry is not None:
        return _paint_region_for_path(landing_preview.geometry.chrome_path)
    if landing_preview.visual is not None:
        return _paint_region_for_visual(landing_preview.visual)
    return QRegion()


def _paint_region_for_visual(visual: PromptChipVisual) -> QRegion:
    """Return the rounded chrome region owned by one prepared chip visual."""

    region = QRegion()
    for bubble_rect in visual.bubble_rects:
        bubble_path = QPainterPath()
        bubble_path.addRoundedRect(
            bubble_rect,
            PROMPT_CHIP_BUBBLE_RADIUS,
            PROMPT_CHIP_BUBBLE_RADIUS,
        )
        region = region.united(_paint_region_for_path(bubble_path))
    return region


def _paint_region_for_path(path: QPainterPath) -> QRegion:
    """Return the integer widget region covered by one prepared chrome path."""

    if path.isEmpty():
        return QRegion()
    return QRegion(path.toFillPolygon().toPolygon())


def _expanded_aligned_rect(rect: QRectF) -> QRect:
    """Return an integer paint rect with antialiasing slack."""

    return rect.toAlignedRect().adjusted(-2, -2, 2, 2)


__all__ = [
    "PromptReorderChipInteractionState",
    "PromptReorderChipPaintState",
    "PromptReorderLandingPreviewPaintState",
    "PromptReorderMarkerPaintState",
    "PromptReorderView",
    "PromptReorderViewRenderInput",
    "PromptReorderViewRenderState",
    "PromptReorderVisualStyle",
    "prompt_reorder_chip_paint_states",
    "prompt_reorder_chip_interaction_state",
    "prompt_reorder_chip_interaction_states",
    "prompt_reorder_marker_paint_state",
    "prompt_reorder_visual_for_chip_geometry",
    "prompt_reorder_view_render_state",
]

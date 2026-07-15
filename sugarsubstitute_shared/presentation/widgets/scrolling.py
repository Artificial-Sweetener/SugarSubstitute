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

"""Apply shared scroll interaction policies to presentation widgets."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast
from weakref import ReferenceType, ref

from PySide6.QtCore import Qt
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

_DELEGATE_ATTRIBUTE_NAMES = ("scrollDelegate", "scrollDelagate")
_SMOOTH_SCROLL_ATTRIBUTE_NAMES = (
    "verticalSmoothScroll",
    "horizonSmoothScroll",
    "smoothScroll",
)
_SCROLLBAR_ATTRIBUTE_NAMES = ("vScrollBar", "hScrollBar")
_EDITOR_PANEL_SCROLLBAR_THICKNESS = 12
_EDITOR_PANEL_SCROLLBAR_EDGE_INSET = 1


def configure_qfluent_scroll_surface(widget: object) -> None:
    """Apply the app's editor-matched QFluent scroll behavior and chrome."""

    disable_qfluent_smooth_scrolling(widget)
    match_editor_panel_scrollbar_position(widget)


def disable_qfluent_smooth_scrolling(widget: object) -> None:
    """Disable QFluent wheel smoothing while preserving scrollbar chrome."""

    for scroll_owner in _qfluent_scroll_owners(widget):
        _disable_animated_delegate_mode(scroll_owner)
        for smooth_scroll in _smooth_scroll_objects(scroll_owner):
            _set_no_smooth_mode(smooth_scroll)
        for scroll_bar in _scrollbar_objects(scroll_owner):
            _disable_scrollbar_animation(scroll_bar)


def match_editor_panel_scrollbar_position(widget: object) -> None:
    """Place QFluent scrollbars at the same relative edge as the editor panel."""

    for scroll_owner in _qfluent_scroll_owners(widget):
        for scroll_bar in _scrollbar_objects(scroll_owner):
            _install_editor_panel_scrollbar_position(scroll_bar)


def _qfluent_scroll_owners(widget: object) -> tuple[object, ...]:
    """Return the widget and any attached QFluent scroll delegates."""

    owners: list[object] = [widget]
    for attribute_name in _DELEGATE_ATTRIBUTE_NAMES:
        delegate = getattr(widget, attribute_name, None)
        if delegate is not None:
            owners.append(delegate)
    return tuple(owners)


def _disable_animated_delegate_mode(scroll_owner: object) -> None:
    """Turn off delegate-owned value animation when the owner exposes it."""

    if hasattr(scroll_owner, "useAni"):
        setattr(scroll_owner, "useAni", False)


def _smooth_scroll_objects(scroll_owner: object) -> tuple[object, ...]:
    """Return QFluent smooth-scroll engines attached to one owner."""

    return tuple(
        smooth_scroll
        for attribute_name in _SMOOTH_SCROLL_ATTRIBUTE_NAMES
        if (smooth_scroll := getattr(scroll_owner, attribute_name, None)) is not None
    )


def _scrollbar_objects(scroll_owner: object) -> tuple[object, ...]:
    """Return QFluent visible scrollbars attached to one owner."""

    return tuple(
        scroll_bar
        for attribute_name in _SCROLLBAR_ATTRIBUTE_NAMES
        if (scroll_bar := getattr(scroll_owner, attribute_name, None)) is not None
    )


def _set_no_smooth_mode(smooth_scroll: object) -> None:
    """Set one QFluent smooth-scroll engine to immediate wheel handling."""

    set_smooth_mode = getattr(smooth_scroll, "setSmoothMode", None)
    if callable(set_smooth_mode):
        call_set_smooth_mode = _one_argument_callable(set_smooth_mode)
        call_set_smooth_mode(SmoothMode.NO_SMOOTH)


def _disable_scrollbar_animation(scroll_bar: object) -> None:
    """Disable one QFluent visible scrollbar's value animation."""

    set_scroll_animation = getattr(scroll_bar, "setScrollAnimation", None)
    if callable(set_scroll_animation):
        call_set_scroll_animation = _one_argument_callable(set_scroll_animation)
        call_set_scroll_animation(0)


def _install_editor_panel_scrollbar_position(scroll_bar: object) -> None:
    """Install editor-panel edge geometry on one QFluent visible scrollbar."""

    orientation = _scrollbar_orientation(scroll_bar)
    if orientation is None:
        return
    scroll_bar_ref = _weak_ref_or_none(scroll_bar)
    strong_scroll_bar = None if scroll_bar_ref is not None else scroll_bar

    def adjust_pos(size: object) -> None:
        target_scroll_bar = _resolve_weak_target(scroll_bar_ref, strong_scroll_bar)
        if target_scroll_bar is None:
            return
        width = _dimension(size, "width")
        height = _dimension(size, "height")
        if width is None or height is None:
            return
        if orientation == Qt.Orientation.Vertical:
            _resize_widget(
                target_scroll_bar,
                _EDITOR_PANEL_SCROLLBAR_THICKNESS,
                max(0, height - (2 * _EDITOR_PANEL_SCROLLBAR_EDGE_INSET)),
            )
            _move_widget(
                target_scroll_bar,
                max(0, width - _EDITOR_PANEL_SCROLLBAR_THICKNESS - 1),
                _EDITOR_PANEL_SCROLLBAR_EDGE_INSET,
            )
            return
        if orientation == Qt.Orientation.Horizontal:
            _resize_widget(
                target_scroll_bar,
                max(0, width - (2 * _EDITOR_PANEL_SCROLLBAR_EDGE_INSET)),
                _EDITOR_PANEL_SCROLLBAR_THICKNESS,
            )
            _move_widget(
                target_scroll_bar,
                _EDITOR_PANEL_SCROLLBAR_EDGE_INSET,
                max(0, height - _EDITOR_PANEL_SCROLLBAR_THICKNESS - 1),
            )

    setattr(scroll_bar, "_adjustPos", adjust_pos)
    parent = _call_no_argument_method(scroll_bar, "parent")
    size = _call_no_argument_method(parent, "size") if parent is not None else None
    if size is not None:
        adjust_pos(size)


def _weak_ref_or_none(target: object) -> ReferenceType[object] | None:
    """Return a weak reference when the target supports weak references."""

    try:
        return ref(target)
    except TypeError:
        return None


def _resolve_weak_target(
    target_ref: ReferenceType[object] | None,
    fallback: object | None,
) -> object | None:
    """Return a weakly referenced target or a non-weakref fallback."""

    if target_ref is None:
        return fallback
    return target_ref()


def _scrollbar_orientation(scroll_bar: object) -> Qt.Orientation | None:
    """Return a QFluent scrollbar orientation when available."""

    orientation_method = getattr(scroll_bar, "orientation", None)
    if not callable(orientation_method):
        return None
    orientation = orientation_method()
    if orientation in {Qt.Orientation.Vertical, Qt.Orientation.Horizontal}:
        return cast(Qt.Orientation, orientation)
    return None


def _dimension(size: object, attribute_name: str) -> int | None:
    """Return one integer size dimension from a Qt size-like object."""

    dimension = getattr(size, attribute_name, None)
    if not callable(dimension):
        return None
    value = dimension()
    return int(value) if isinstance(value, int) else None


def _resize_widget(widget: object, width: int, height: int) -> None:
    """Resize a Qt-like widget when it exposes `resize`."""

    resize = getattr(widget, "resize", None)
    if callable(resize):
        call_resize = cast(Callable[[int, int], object], resize)
        call_resize(width, height)


def _move_widget(widget: object, x: int, y: int) -> None:
    """Move a Qt-like widget when it exposes `move`."""

    move = getattr(widget, "move", None)
    if callable(move):
        call_move = cast(Callable[[int, int], object], move)
        call_move(x, y)


def _call_no_argument_method(obj: object, method_name: str) -> object | None:
    """Call one no-argument method on an object when present."""

    method = getattr(obj, method_name, None)
    if not callable(method):
        return None
    call_method = cast(Callable[[], object], method)
    return call_method()


def _one_argument_callable(target: object) -> Callable[[object], object]:
    """Return a callable narrowed to one positional argument."""

    return cast(Callable[[object], object], target)


__all__ = [
    "configure_qfluent_scroll_surface",
    "disable_qfluent_smooth_scrolling",
    "match_editor_panel_scrollbar_position",
]

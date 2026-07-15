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

"""Define shared shell chrome material, geometry, and theme-aware style helpers."""

from __future__ import annotations

from collections.abc import Callable
from types import MethodType
from weakref import ReferenceType, WeakMethod, ref

from PySide6.QtGui import QColor

from substitute.shared.logging.logger import get_logger, log_warning

try:
    from qfluentwidgets.common.config import qconfig  # type: ignore[import-untyped]
    from qfluentwidgets.common.style_sheet import (  # type: ignore[import-untyped]
        isDarkTheme,
        themeColor,
    )
except ImportError:  # pragma: no cover - lightweight test stubs
    qconfig = None

    def isDarkTheme() -> bool:
        """Return the default theme state for lightweight test stubs."""

        return True

    def themeColor() -> QColor:
        """Return a stable accent color for lightweight test stubs."""

        return QColor("#009FAA")


_shiboken_is_valid: Callable[[object], bool] | None
try:
    from shiboken6 import isValid as _imported_shiboken_is_valid

    _shiboken_is_valid = _imported_shiboken_is_valid
except ImportError:  # pragma: no cover - PySide always supplies this in production
    _shiboken_is_valid = None


_LOGGER = get_logger("presentation.shell.chrome_style")
BODY_MATERIAL_SURFACE_OBJECT_NAME = "SubstituteBodyMaterialSurface"
CUBE_STACK_TOP_INSET = 6
WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT = 4
WORKFLOW_TITLEBAR_HEIGHT = 34
WORKFLOW_TAB_HEIGHT = WORKFLOW_TITLEBAR_HEIGHT - WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT
WORKFLOW_TAB_TOP_ACCENT_HEIGHT = 2.0
WORKFLOW_TAB_CORNER_OVERLAY_WIDTH = 8.0
WORKFLOW_TAB_BODY_TOP_RADIUS = 8.0
WORKFLOW_TAB_BOTTOM_CORNER_RADIUS = 4.0
WORKFLOW_TAB_BOTTOM_CORNER_WIDTH = 8.0
WORKFLOW_TAB_INACTIVE_INSET = 1.0
WORKFLOW_TAB_INACTIVE_RADIUS = 7.0
WORKFLOW_TAB_INACTIVE_TEXT_ALPHA = 201
WORKFLOW_TAB_SELECTED_FONT_WEIGHT = 600
WORKFLOW_TAB_ICON_LEFT_PADDING = 18
WORKFLOW_TAB_TEXT_LEFT_PADDING = 20
WORKFLOW_TAB_TEXT_LEFT_PADDING_WITH_ICON = 44
WORKFLOW_TOOLBAR_VERTICAL_PADDING = 4
WORKFLOW_TOOLBAR_CONTROL_HEIGHT = 36
WORKFLOW_TOOLBAR_HEIGHT = WORKFLOW_TOOLBAR_CONTROL_HEIGHT + (
    WORKFLOW_TOOLBAR_VERTICAL_PADDING * 2
)
APP_ORB_DIAMETER = 46
APP_ORB_LEFT_MARGIN = 8
APP_ORB_TOP = 6
APP_ORB_RESERVED_WIDTH = APP_ORB_LEFT_MARGIN + APP_ORB_DIAMETER + 8
APP_ORB_ICON_SIZE = 28
APP_ORB_TAB_RESERVED_WIDTH = APP_ORB_RESERVED_WIDTH - 14
APP_ORB_TAB_CUTOUT_RADIUS = 25.0
APP_ORB_TAB_CUTOUT_OVERLAP = APP_ORB_RESERVED_WIDTH - APP_ORB_TAB_RESERVED_WIDTH
APP_ORB_TAB_CUTOUT_CENTER_X = (
    APP_ORB_LEFT_MARGIN + APP_ORB_DIAMETER / 2 - APP_ORB_TAB_RESERVED_WIDTH
)
APP_ORB_TAB_CUTOUT_CENTER_Y = (
    APP_ORB_TOP + APP_ORB_DIAMETER / 2 - WORKFLOW_TITLEBAR_MICA_SLIVER_HEIGHT
)
APP_ORB_TAB_CUTOUT_ANIMATION_MS = 160
_ACRYLIC_WASH_ALPHA_MULTIPLIER = 1.5
_ACRYLIC_WASH_ALPHA_CAP = 236
_ACRYLIC_WASH_CURRENT_FACTOR = 0.75
_ACRYLIC_CARD_ALPHA_MULTIPLIER = 1.25


def _is_acrylic_backdrop(backdrop_mode: object | None) -> bool:
    """Return whether the provided backdrop mode represents acrylic."""

    return getattr(backdrop_mode, "value", backdrop_mode) == "acrylic"


def _rgba_string(color: tuple[int, int, int, int]) -> str:
    """Return one CSS rgba string from an RGBA tuple."""

    red, green, blue, alpha = color
    return f"rgba({red}, {green}, {blue}, {alpha})"


def _boost_acrylic_alpha(alpha: int) -> int:
    """Return a stronger acrylic-only alpha without reaching full opacity."""

    boosted = int(round(alpha * _ACRYLIC_WASH_ALPHA_MULTIPLIER))
    return int(
        round(min(_ACRYLIC_WASH_ALPHA_CAP, boosted) * _ACRYLIC_WASH_CURRENT_FACTOR)
    )


def _scale_alpha(alpha: int, factor: float, cap: int = 255) -> int:
    """Return one scaled alpha channel clamped to the requested cap."""

    return max(0, min(cap, int(round(alpha * factor))))


def _accent_color() -> QColor:
    """Return the active accent color as a mutable ``QColor``."""

    return QColor(themeColor())


def body_material_wash_rgba(backdrop_mode: object | None = None) -> str:
    """Return the shared shell body wash for the active theme."""

    return _rgba_string(body_material_wash_color(backdrop_mode))


def body_material_wash_color(
    backdrop_mode: object | None = None,
) -> tuple[int, int, int, int]:
    """Return the shared shell body wash as an RGBA tuple."""

    if isDarkTheme():
        red, green, blue, alpha = (32, 32, 32, 150)
    else:
        red, green, blue, alpha = (251, 251, 251, 188)
    if _is_acrylic_backdrop(backdrop_mode):
        alpha = _boost_acrylic_alpha(alpha)
    return (red, green, blue, alpha)


def resolved_backdrop_mode(widget: object | None) -> object | None:
    """Return the owning top-level backdrop mode for one widget when available."""

    if widget is None:
        return None
    window_getter = getattr(widget, "window", None)
    if not callable(window_getter):
        return None
    try:
        window = window_getter()
    except RuntimeError:
        return None
    return getattr(window, "_backdrop_mode", None)


def winui_card_fill_color(
    backdrop_mode: object | None = None,
) -> tuple[int, int, int, int]:
    """Return the WinUI default card fill as an RGBA tuple."""

    if isDarkTheme():
        red, green, blue, alpha = (255, 255, 255, 13)
    else:
        red, green, blue, alpha = (255, 255, 255, 179)
    if _is_acrylic_backdrop(backdrop_mode):
        alpha = _scale_alpha(alpha, _ACRYLIC_CARD_ALPHA_MULTIPLIER)
    return (red, green, blue, alpha)


def winui_card_border_color_for_theme(is_dark: bool) -> tuple[int, int, int, int]:
    """Return the WinUI default card stroke for one concrete theme state."""

    if is_dark:
        return (0, 0, 0, 25)
    return (0, 0, 0, 15)


def winui_card_border_color() -> tuple[int, int, int, int]:
    """Return the WinUI default card stroke as an RGBA tuple."""

    return winui_card_border_color_for_theme(isDarkTheme())


def winui_accent_button_disabled_fill_color() -> QColor:
    """Return the WinUI-style disabled fill for accent button surfaces."""

    if isDarkTheme():
        return QColor(52, 52, 52)
    return QColor(205, 205, 205)


def winui_accent_button_disabled_foreground_color() -> QColor:
    """Return the WinUI-style disabled foreground for accent button content."""

    if isDarkTheme():
        return QColor(255, 255, 255, 110)
    return QColor(255, 255, 255, 230)


def body_material_wash_style(backdrop_mode: object | None = None) -> str:
    """Return the shared shell body material stylesheet for the active theme."""

    return f"""
QWidget#{BODY_MATERIAL_SURFACE_OBJECT_NAME} {{
    background-color: {body_material_wash_rgba(backdrop_mode)};
    border: none;
}}
"""


def workflow_chrome_wash_rgba(backdrop_mode: object | None = None) -> str:
    """Return the shared workflow toolbar wash for the active theme."""

    return _rgba_string(workflow_chrome_wash_color(backdrop_mode))


def workflow_chrome_wash_color(
    backdrop_mode: object | None = None,
) -> tuple[int, int, int, int]:
    """Return the workflow toolbar wash as an RGBA tuple for painters."""

    if isDarkTheme():
        red, green, blue, alpha = (44, 44, 44, 150)
    else:
        red, green, blue, alpha = (252, 252, 252, 196)
    if _is_acrylic_backdrop(backdrop_mode):
        alpha = _boost_acrylic_alpha(alpha)
    return (red, green, blue, alpha)


def acrylic_titlebar_wash_color() -> QColor:
    """Return the accent-derived acrylic-only titlebar wash color."""

    accent = _accent_color().toHsv()
    hue = accent.hsvHue()
    if hue < 0:
        return QColor(34, 34, 34, 98) if isDarkTheme() else QColor(230, 230, 230, 65)
    saturation_scale = 0.42 if isDarkTheme() else 0.30
    value_scale = 0.50 if isDarkTheme() else 0.76
    alpha = 98 if isDarkTheme() else 65
    return QColor.fromHsv(
        hue,
        max(0, min(255, int(round(accent.hsvSaturation() * saturation_scale)))),
        max(0, min(255, int(round(accent.value() * value_scale)))),
        alpha,
    )


def acrylic_titlebar_wash_rgba() -> str:
    """Return the acrylic-only titlebar wash as a CSS rgba string."""

    color = acrylic_titlebar_wash_color()
    return _rgba_string((color.red(), color.green(), color.blue(), color.alpha()))


def workflow_tab_separator_rgba() -> tuple[int, int, int, int]:
    """Return the workflow tab separator tint for the active theme."""

    if isDarkTheme():
        return (255, 255, 255, 15)
    return (0, 0, 0, 22)


def field_row_divider_rgba_for_theme(is_dark: bool) -> str:
    """Return the editor field-row divider tint from the card stroke token."""

    return _rgba_string(winui_card_border_color_for_theme(is_dark))


def field_row_divider_rgba() -> str:
    """Return the editor field-row divider tint for the active theme."""

    return field_row_divider_rgba_for_theme(isDarkTheme())


def toolbar_separator_rgba() -> str:
    """Return the toolbar separator color for the active theme."""

    if isDarkTheme():
        return "rgba(57, 57, 57, 200)"
    return "rgba(0, 0, 0, 88)"


def splitter_handle_rgba() -> str:
    """Return the shell splitter handle tint for the active theme."""

    if isDarkTheme():
        return "rgba(255, 255, 255, 0.08)"
    return "rgba(0, 0, 0, 0.12)"


def floating_surface_rgba() -> str:
    """Return the opaque WinUI floating shell surface for the active theme."""

    color = floating_surface_color()
    return _rgba_string((color.red(), color.green(), color.blue(), color.alpha()))


def floating_surface_color() -> QColor:
    """Return the opaque WinUI floating shell surface color for painting."""

    if isDarkTheme():
        return QColor(44, 44, 44, 255)
    return QColor(252, 252, 252, 255)


def floating_surface_border_rgba() -> str:
    """Return the floating shell border tint for the active theme."""

    color = floating_surface_border_color()
    return _rgba_string((color.red(), color.green(), color.blue(), color.alpha()))


def floating_surface_border_color() -> QColor:
    """Return the floating shell border tint for direct painting."""

    if isDarkTheme():
        return QColor(255, 255, 255, 25)
    return QColor(0, 0, 0, 30)


def floating_surface_text_color() -> QColor:
    """Return the Fluent foreground used on floating shell surfaces."""

    if isDarkTheme():
        return QColor(255, 255, 255)
    return QColor(0, 0, 0)


def windows_list_item_state_overlay_color(
    *,
    is_dark: bool,
    is_pressed: bool,
    is_hovered: bool,
) -> QColor:
    """Return Windows list-item hover and pressed overlay colors."""

    if is_pressed:
        alpha = 0x33
    elif is_hovered:
        alpha = 0x19
    else:
        alpha = 0x00
    channel = 0xFF if is_dark else 0x00
    return QColor(channel, channel, channel, alpha)


def connect_theme_refresh(
    widget: object,
    refresh: Callable[[], None],
) -> None:
    """Connect one live-widget refresh callback to QFluent theme and accent changes."""

    if qconfig is None:
        return

    widget_ref = _weak_ref_or_none(widget)
    refresh_ref = _weak_method_or_none(refresh)
    disconnected = False

    def _disconnect_theme_signals() -> None:
        """Detach this refresh callback from process-wide QFluent signals."""

        nonlocal disconnected
        if disconnected:
            return
        disconnected = True
        for signal in (qconfig.themeChangedFinished, qconfig.themeColorChanged):
            try:
                signal.disconnect(_refresh)
            except (RuntimeError, TypeError):
                continue

    def _resolve_widget() -> object | None:
        """Return the widget wrapper while it is still available."""

        return widget_ref() if widget_ref is not None else widget

    def _resolve_refresh() -> Callable[[], None] | None:
        """Return the refresh callable while its owning instance is alive."""

        return refresh_ref() if refresh_ref is not None else refresh

    def _refresh(*_args: object) -> None:
        target_widget = _resolve_widget()
        if target_widget is None or not _is_live_qt_object(target_widget):
            _disconnect_theme_signals()
            return
        refresh_callback = _resolve_refresh()
        if refresh_callback is None:
            _disconnect_theme_signals()
            return
        try:
            refresh_callback()
        except RuntimeError as error:
            if _is_deleted_qt_object_error(error):
                log_warning(
                    _LOGGER,
                    "Detached stale theme refresh callback",
                    widget_type=target_widget.__class__.__name__,
                    error=repr(error),
                )
                _disconnect_theme_signals()
                return
            raise

    def _disconnect_on_destroyed(*_args: object) -> None:
        """Detach process-wide theme refresh hooks when the widget is destroyed."""

        _disconnect_theme_signals()

    callbacks = getattr(widget, "_appearance_refresh_callbacks", None)
    if not isinstance(callbacks, list):
        callbacks = []
        setattr(widget, "_appearance_refresh_callbacks", callbacks)
    callbacks.append(_refresh)
    callbacks.append(_disconnect_on_destroyed)
    destroyed_signal = getattr(widget, "destroyed", None)
    if destroyed_signal is not None:
        try:
            destroyed_signal.connect(_disconnect_on_destroyed)
        except (RuntimeError, TypeError):
            pass
    qconfig.themeChangedFinished.connect(_refresh)
    qconfig.themeColorChanged.connect(_refresh)


def _weak_ref_or_none(target: object) -> ReferenceType[object] | None:
    """Return a weak object reference when the target type supports it."""

    try:
        return ref(target)
    except TypeError:
        return None


def _weak_method_or_none(
    callback: Callable[[], None],
) -> WeakMethod[Callable[[], None]] | None:
    """Return a weak bound-method reference for instance-owned callbacks."""

    if not isinstance(callback, MethodType):
        return None
    return WeakMethod(callback)


def _is_live_qt_object(target: object) -> bool:
    """Return whether a PySide wrapper still owns a valid C++ object."""

    if _shiboken_is_valid is None:
        return True
    try:
        return bool(_shiboken_is_valid(target))
    except (RuntimeError, TypeError):
        return False


def _is_deleted_qt_object_error(error: RuntimeError) -> bool:
    """Return whether Qt raised because a Python wrapper outlived its C++ object."""

    message = str(error)
    return "Internal C++ object" in message and "already deleted" in message

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

"""Contract tests for extracted MainWindow menu construction."""

from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


class _Signal:
    """Minimal signal double supporting connect and manual fire."""

    def __init__(self) -> None:
        self.connections: list[object] = []

    def connect(self, callback: object) -> None:
        """Record one connected callback."""

        self.connections.append(callback)

    def fire(self, *args: object) -> None:
        """Invoke all recorded callbacks."""

        for callback in self.connections:
            callback(*args)


class _Widget:
    """Generic widget stub implementing the Qt methods used by the builder."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.init_args = _args
        self.init_kwargs = _kwargs
        self.hidden = False
        self.cursor = None
        self.tooltip = None
        self.parent = None
        self.size_policy = None
        self.layout = None
        self.object_name = None
        self.style = None
        self.geometry = None
        self.fixed_height = None
        self.fixed_width = None
        self.checkable = False
        self.icon_size = None
        self.properties: dict[str, object] = {}
        self.visible_calls: list[bool] = []

    def setToolTip(self, tooltip: str) -> None:
        """Record tooltip text."""

        self.tooltip = tooltip

    def setCursor(self, cursor: object) -> None:
        """Record cursor state."""

        self.cursor = cursor

    def setParent(self, parent: object) -> None:
        """Record parent assignment."""

        self.parent = parent

    def hide(self) -> None:
        """Record hidden state."""

        self.hidden = True

    def show(self) -> None:
        """Record visible state."""

        self.hidden = False

    def setVisible(self, visible: bool) -> None:
        """Record explicit visibility updates."""

        self.hidden = not visible
        self.visible_calls.append(visible)

    def setFixedWidth(self, width: int) -> None:
        """Record fixed-width configuration."""

        self.fixed_width = width

    def setFixedHeight(self, height: int) -> None:
        """Record fixed-height configuration."""

        self.fixed_height = height

    def setObjectName(self, name: str) -> None:
        """Record the assigned object name."""

        self.object_name = name

    def setStyleSheet(self, style: str) -> None:
        """Record style updates."""

        self.style = style

    def setLayoutDirection(self, direction: object) -> None:
        """Record layout direction updates."""

        self.layout_direction = direction

    def setSizePolicy(self, horizontal: object, vertical: object) -> None:
        """Record size-policy selection."""

        self.size_policy = (horizontal, vertical)

    def setGeometry(self, x: int, y: int, width: int, height: int) -> None:
        """Record explicit widget geometry."""

        self.geometry = (x, y, width, height)

    def raise_(self) -> None:
        """Record z-order promotion."""

        self.raised = True

    def setMinimumWidth(self, _width: int) -> None:
        """Accept minimum-width configuration."""

    def setAlignment(self, _alignment: object) -> None:
        """Accept alignment updates."""

    def setText(self, text: str) -> None:
        """Record label text."""

        self.text = text

    def text(self) -> str:
        """Return current text when a widget behaves like a line edit."""

        return str(getattr(self, "_text", ""))

    def blockSignals(self, blocked: bool) -> bool:
        """Accept signal-blocking calls and return the previous state."""

        previous = bool(getattr(self, "_signals_blocked", False))
        self._signals_blocked = blocked
        return previous

    def setPlaceholderText(self, text: str) -> None:
        """Record line-edit placeholder text."""

        self.placeholder_text = text

    def setClearButtonEnabled(self, enabled: bool) -> None:
        """Record whether the clear button is enabled."""

        self.clear_button_enabled = enabled

    def setCheckable(self, checkable: bool) -> None:
        """Record checkable state."""

        self.checkable = checkable

    def setIconSize(self, size: object) -> None:
        """Record icon-size configuration."""

        self.icon_size = size

    def setMenu(self, menu: object) -> None:
        """Record attached menu."""

        self.menu = menu

    def setProperty(self, name: str, value: object) -> None:
        """Record dynamic Qt property values."""

        self.properties[name] = value

    def property(self, name: str) -> object | None:
        """Return one dynamic Qt property value."""

        return self.properties.get(name)

    def setFlyout(self, flyout: object) -> None:
        """Record attached flyout menu."""

        self.flyout = flyout

    def addAction(self, action: object) -> None:
        """Record one added menu action."""

        if not hasattr(self, "actions"):
            self.actions = []
        self.actions.append(action)


class _Layout:
    """Layout stub exposing the methods used by menu construction."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.widgets: list[object] = []
        self.contents_margins: tuple[int, int, int, int] | None = None
        self.direction = None

    def setContentsMargins(self, left: int, top: int, right: int, bottom: int) -> None:
        """Record margin updates."""

        self.contents_margins = (left, top, right, bottom)

    def setSpacing(self, _spacing: int) -> None:
        """Accept spacing updates."""

    def setDirection(self, direction: object) -> None:
        """Record explicit layout direction."""

        self.direction = direction

    def addWidget(self, widget: object) -> None:
        """Append one widget."""

        self.widgets.append(widget)

    def insertSpacing(self, _index: int, _spacing: int) -> None:
        """Accept spacer insertion."""

    def indexOf(self, widget: object) -> int:
        """Return one widget index."""

        return self.widgets.index(widget)

    def insertWidget(self, index: int, widget: object) -> None:
        """Insert one widget."""

        self.widgets.insert(index, widget)


class _Button(_Widget):
    """Button stub with a clicked signal and split-button children."""

    def __init__(self, *_args, **_kwargs) -> None:
        super().__init__(*_args, **_kwargs)
        self.clicked = _Signal()
        self.button = _Widget()
        self.dropButton = _Widget()


class _PendingRestartToolbarButton(_Button):
    """Restart toolbar button stub recording adaptive spacer ownership."""

    def set_centering_spacer(self, spacer: object, *, toolbar: object) -> None:
        """Record the bound Settings-search leading spacer."""

        self.centering_spacer = spacer
        self.centering_toolbar = toolbar

    def set_balance_spacer(
        self,
        spacer: object,
        *,
        expanded_width: int,
        center_widget: object | None = None,
        toolbar: object | None = None,
    ) -> None:
        """Record the bound toolbar balance spacer."""

        self.balance_spacer = spacer
        self.balance_spacer_width = expanded_width
        self.balance_center_widget = center_widget
        self.balance_toolbar = toolbar
        set_fixed_width = getattr(spacer, "setFixedWidth", None)
        center_hidden = bool(getattr(center_widget, "hidden", False))
        if callable(set_fixed_width) and center_hidden:
            set_fixed_width(0)

    def set_alignment_spacer(
        self,
        spacer: object,
        *,
        toolbar: object,
    ) -> None:
        """Record the bound toolbar right-alignment spacer."""

        self.alignment_spacer = spacer
        self.alignment_toolbar = toolbar


class _SearchLineEdit(_Widget):
    """Search line edit stub exposing text changes."""

    def __init__(self, *_args, **_kwargs) -> None:
        """Create an empty search line edit."""

        super().__init__(*_args, **_kwargs)
        self._text = ""
        self.textChanged = _Signal()

    def setText(self, text: str) -> None:
        """Record search text and emit when signals are not blocked."""

        self._text = text
        if not bool(getattr(self, "_signals_blocked", False)):
            self.textChanged.fire(text)


class _Action:
    """Action stub recording the configured icon and text."""

    def __init__(self, icon: object, text: str) -> None:
        self.icon = icon
        self.text = text


def _install_stubs() -> None:
    """Install lightweight PySide and qfluentwidgets stubs for import."""

    for module_name in list(sys.modules):
        if module_name.startswith("qfluentwidgets") or module_name.startswith(
            "PySide6"
        ):
            sys.modules.pop(module_name, None)

    shiboken = types.ModuleType("shiboken6")
    shiboken.isValid = lambda _candidate: True
    sys.modules["shiboken6"] = shiboken

    qtcore = types.ModuleType("PySide6.QtCore")

    class _Rect:
        """Minimal QRect double supporting construction and containment."""

        def __init__(
            self, x: int = 0, y: int = 0, width: int = 0, height: int = 0
        ) -> None:
            self._x = x
            self._y = y
            self._width = width
            self._height = height

        def contains(self, _point: object) -> bool:
            """Return false for stub-only cursor probes."""

            return False

        def x(self) -> int:
            """Return the rectangle x coordinate."""

            return self._x

        def width(self) -> int:
            """Return the rectangle width."""

            return self._width

    qtcore.QEvent = SimpleNamespace(
        Type=SimpleNamespace(
            Enter=10,
            HoverEnter=127,
            HoverMove=129,
            Leave=11,
            HoverLeave=128,
            MouseMove=5,
            MouseButtonPress=2,
            MouseButtonRelease=3,
        )
    )
    qtcore.QRect = _Rect
    qtcore.QSize = lambda width, height: (width, height)
    qtcore.Signal = lambda *_args, **_kwargs: _Signal()

    class _Timer:
        """Timer stub with connectable timeout and start recording."""

        def __init__(self, *_args, **_kwargs) -> None:
            self.timeout = _Signal()
            self.interval = 0
            self.single_shot = False
            self.start_calls = 0

        @staticmethod
        def singleShot(_msec: int, callback: object) -> None:
            """Invoke single-shot callbacks immediately in builder tests."""

            if callable(callback):
                callback()

        def setSingleShot(self, single_shot: bool) -> None:
            """Record single-shot mode."""

            self.single_shot = single_shot

        def setInterval(self, interval: int) -> None:
            """Record timer interval."""

            self.interval = interval

        def start(self) -> None:
            """Record timer starts without firing."""

            self.start_calls += 1

    qtcore.QTimer = _Timer
    qtcore.Qt = SimpleNamespace(
        PointingHandCursor="pointing",
        LayoutDirection=SimpleNamespace(LeftToRight="left-to-right"),
        AlignLeft=1,
        AlignVCenter=2,
        PenStyle=SimpleNamespace(NoPen="no-pen"),
    )
    sys.modules["PySide6.QtCore"] = qtcore

    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QColor = lambda *args, **_kwargs: SimpleNamespace(args=args)
    qtgui.QCursor = SimpleNamespace(pos=lambda: None)

    class _Painter:
        RenderHint = SimpleNamespace(Antialiasing="antialiasing")

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def setRenderHint(self, *_args, **_kwargs) -> None:
            pass

        def setPen(self, *_args, **_kwargs) -> None:
            pass

        def setBrush(self, *_args, **_kwargs) -> None:
            pass

        def drawRoundedRect(self, *_args, **_kwargs) -> None:
            pass

    qtgui.QPainter = _Painter
    sys.modules["PySide6.QtGui"] = qtgui

    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QWidget = _Widget
    qtwidgets.QBoxLayout = SimpleNamespace(
        Direction=SimpleNamespace(LeftToRight="left-to-right")
    )
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QSizePolicy = SimpleNamespace(
        Expanding="expanding", Preferred="preferred", Fixed="fixed"
    )
    qtwidgets.QSizePolicy.Policy = qtwidgets.QSizePolicy
    sys.modules["PySide6.QtWidgets"] = qtwidgets
    sys.modules["PySide6"] = types.ModuleType("PySide6")

    window_frame = types.ModuleType("substitute.presentation.shell.window_frame")
    window_frame.ShellBackdropMode = SimpleNamespace
    sys.modules["substitute.presentation.shell.window_frame"] = window_frame

    qfw = types.ModuleType("qfluentwidgets")

    class _FluentIconBase:
        """Minimal base class for app-owned icon enum imports."""

        def icon(self, *_args, **_kwargs):
            """Return a stable token for tests that request a QIcon."""

            return "app-icon-token"

    class _Icon:
        def icon(self, *_args, **_kwargs):
            return "icon-token"

    class _FluentIcon:
        FOLDER = _Icon()
        SAVE_AS = _Icon()
        IOT = _Icon()
        SAVE = _Icon()
        SETTING = _Icon()
        LAYOUT = _Icon()
        PIN = _Icon()
        PLAY_SOLID = _Icon()
        SYNC = _Icon()
        HISTORY = _Icon()
        CLOSE = _Icon()

    qfw.Action = _Action
    qfw.CheckableMenu = _Widget
    qfw.SearchLineEdit = _SearchLineEdit
    qfw.MenuIndicatorType = SimpleNamespace(CHECK="check")
    qfw.PrimarySplitPushButton = _Button
    qfw.RoundMenu = _Widget
    qfw.SplitToolButton = _Button
    qfw.Theme = SimpleNamespace(AUTO="auto", LIGHT="light", DARK="dark")
    qfw.TransparentDropDownToolButton = _Button
    qfw.TransparentToolButton = _Button
    qfw.FluentIconBase = _FluentIconBase
    qfw.FluentIcon = _FluentIcon
    qfw.isDarkTheme = lambda: True
    qfw.getIconColor = lambda theme="auto": "black"
    sys.modules["qfluentwidgets"] = qfw

    overrides_view = types.ModuleType(
        "substitute.presentation.editor.panel.overrides_controller"
    )
    overrides_view.GlobalOverridesManager = type("GlobalOverridesManager", (), {})
    sys.modules["substitute.presentation.editor.panel.overrides_controller"] = (
        overrides_view
    )

    search_view = types.ModuleType("substitute.presentation.shell.search_view")
    search_view.FloatingSearchBox = _Widget
    sys.modules["substitute.presentation.shell.search_view"] = search_view

    app_orb_cluster = types.ModuleType(
        "substitute.presentation.shell.app_orb_action_cluster"
    )

    class _AppOrbActionCluster(_Widget):
        """Provide the under-orb action cluster shape for builder tests."""

        def __init__(self, *_args, **_kwargs) -> None:
            super().__init__(*_args, **_kwargs)
            self.cube_stack_button = _Button(self)
            self.override_button = _Button(self)

    app_orb_cluster.AppOrbActionCluster = _AppOrbActionCluster
    app_orb_cluster.AppOrbCubeStackButton = _Button
    app_orb_cluster.AppOrbOverrideButton = _Button
    app_orb_cluster.APP_ORB_ACTION_LAYOUT_ANCHOR_OBJECT_NAME = (
        "AppOrbActionLayoutAnchor"
    )
    app_orb_cluster.APP_ORB_ACTION_LAYOUT_ANCHOR_WIDTH = 47
    sys.modules["substitute.presentation.shell.app_orb_action_cluster"] = (
        app_orb_cluster
    )

    pending_restart = types.ModuleType(
        "substitute.presentation.shell.pending_restart_toolbar_button"
    )
    pending_restart.PendingRestartToolbarButton = _PendingRestartToolbarButton
    sys.modules["substitute.presentation.shell.pending_restart_toolbar_button"] = (
        pending_restart
    )


def _preserve_stubbed_modules() -> dict[str, types.ModuleType]:
    """Capture real modules that the menu stubs temporarily replace."""

    return {
        module_name: module
        for module_name, module in sys.modules.items()
        if module_name == "qfluentwidgets"
        or module_name.startswith("qfluentwidgets.")
        or module_name == "PySide6"
        or module_name.startswith("PySide6.")
        or module_name
        in {
            "shiboken6",
            "substitute.presentation.editor.panel.overrides_controller",
            "substitute.presentation.shell.search_view",
            "substitute.presentation.resources.app_icon",
            "substitute.presentation.widgets.menu_buttons",
            "substitute.presentation.shell.settings_toolbar_search",
            "substitute.presentation.shell.app_orb_action_cluster",
            "substitute.presentation.shell.pending_restart_toolbar_button",
            "substitute.presentation.shell.main_window_menu",
        }
    }


def _restore_stubbed_modules(preserved_modules: dict[str, types.ModuleType]) -> None:
    """Remove temporary stubs and restore previously loaded real modules."""

    for module_name in list(sys.modules):
        if module_name == "qfluentwidgets" or module_name.startswith("qfluentwidgets."):
            sys.modules.pop(module_name, None)
        if module_name == "PySide6" or module_name.startswith("PySide6."):
            sys.modules.pop(module_name, None)
        if module_name in {
            "shiboken6",
            "substitute.presentation.editor.panel.overrides_controller",
            "substitute.presentation.shell.search_view",
            "substitute.presentation.resources.app_icon",
            "substitute.presentation.widgets.menu_buttons",
            "substitute.presentation.shell.settings_toolbar_search",
            "substitute.presentation.shell.app_orb_action_cluster",
            "substitute.presentation.shell.pending_restart_toolbar_button",
            "substitute.presentation.shell.main_window_menu",
        }:
            sys.modules.pop(module_name, None)
    sys.modules.update(preserved_modules)


def _import_module():
    """Import the menu builder module under lightweight stubs."""

    preserved_modules = _preserve_stubbed_modules()
    _install_stubs()
    sys.modules.pop("substitute.presentation.resources.app_icon", None)
    sys.modules.pop("substitute.presentation.widgets.menu_buttons", None)
    sys.modules.pop("substitute.presentation.shell.settings_toolbar_search", None)
    sys.modules.pop("substitute.presentation.shell.main_window_menu", None)
    try:
        return importlib.import_module("substitute.presentation.shell.main_window_menu")
    finally:
        _restore_stubbed_modules(preserved_modules)


def _emit_signal(signal: object) -> None:
    """Fire one test signal regardless of whether it exposes emit or fire."""

    emit = getattr(signal, "emit", None)
    if callable(emit):
        emit()
        return
    fire = getattr(signal, "fire", None)
    if callable(fire):
        fire()


def test_build_main_window_menu_returns_wired_generate_and_interrupt_controls() -> None:
    """Menu construction should initialize non-generation shell controls."""

    mod = _import_module()
    widgets = mod.build_main_window_menu(
        SimpleNamespace(),
        workspace_controller=SimpleNamespace(),
    )

    assert widgets.override_managers == {}
    assert widgets.context_search_box.hidden is True
    assert widgets.menu_bar.object_name == "WorkflowChromeToolbar"
    assert mod.workflow_chrome_wash_rgba() in widgets.menu_bar.style
    assert widgets.menu_bar_layout.contents_margins == (8, 4, 8, 4)
    assert widgets.menu_bar.size_policy == ("expanding", "fixed")
    assert widgets.menu_bar.fixed_height == 44
    assert widgets.orb_action_cluster is not None
    assert widgets.menu_bar_layout.direction == "left-to-right"
    assert widgets.menu_bar.layout_direction == "left-to-right"
    assert widgets.orb_action_cluster.geometry == (8, 4, 62, 36)
    assert widgets.orb_action_cluster.raised is True
    assert widgets.menu_bar_layout.indexOf(widgets.orb_action_layout_anchor) == 0
    assert widgets.menu_bar_layout.indexOf(widgets.settings_toolbar_search_box) == 2
    assert len(widgets.menu_bar_layout.widgets) == 6
    search_leading_spacer = widgets.menu_bar_layout.widgets[1]
    search_balance_spacer = widgets.menu_bar_layout.widgets[3]
    restart_toolbar_leading_spacer = widgets.menu_bar_layout.widgets[4]
    pending_restart_button = widgets.menu_bar_layout.widgets[5]
    assert search_leading_spacer.object_name == "SettingsToolbarSearchLeadingSpacer"
    assert search_leading_spacer.size_policy == ("expanding", "preferred")
    assert search_balance_spacer.object_name == "SettingsToolbarSearchBalanceSpacer"
    assert search_balance_spacer.fixed_width == 0
    assert restart_toolbar_leading_spacer.object_name == "RestartToolbarLeadingSpacer"
    assert restart_toolbar_leading_spacer.size_policy == ("expanding", "preferred")
    assert pending_restart_button is widgets.pending_restart_button
    assert pending_restart_button.centering_spacer is search_leading_spacer
    assert pending_restart_button.centering_toolbar is widgets.menu_bar
    assert pending_restart_button.balance_spacer is search_balance_spacer
    assert pending_restart_button.balance_spacer_width == 47
    assert (
        pending_restart_button.balance_center_widget
        is widgets.settings_toolbar_search_box
    )
    assert pending_restart_button.balance_toolbar is widgets.menu_bar
    assert pending_restart_button.alignment_spacer is restart_toolbar_leading_spacer
    assert pending_restart_button.alignment_toolbar is widgets.menu_bar
    assert widgets.orb_action_layout_anchor.object_name == "AppOrbActionLayoutAnchor"
    assert widgets.orb_action_layout_anchor.fixed_width == 47
    assert (
        widgets.settings_toolbar_search_box.object_name
        == "SettingsToolbarSearchLineEdit"
    )
    assert widgets.settings_toolbar_search_box.fixed_width == 420
    assert widgets.settings_toolbar_search_box.fixed_height == 36
    assert widgets.settings_toolbar_search_box.placeholder_text == "Search settings"
    assert widgets.settings_toolbar_search_box.clear_button_enabled is True
    assert widgets.settings_toolbar_search_box.hidden is True
    assert (
        widgets.cube_stack_mode_button is widgets.orb_action_cluster.cube_stack_button
    )
    assert widgets.override_dropdown_btn is widgets.orb_action_cluster.override_button
    assert widgets.override_dropdown_btn.menu is widgets.global_override_menu
    assert (
        widgets.override_dropdown_btn.property("layoutAnchorWidget")
        is widgets.orb_action_layout_anchor
    )
    assert not hasattr(widgets, "load_button")
    assert not hasattr(widgets, "save_button")
    assert not hasattr(widgets, "save_as_action")
    assert not hasattr(widgets, "export_action")
    assert not hasattr(widgets, "generate_button")
    assert not hasattr(widgets, "queue_button")
    assert not hasattr(widgets, "interrupt_button")

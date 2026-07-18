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

"""Import-time stubs shared by canvas widget characterization tests."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import types
from types import SimpleNamespace
from typing import Any


def import_canvas_modules(monkeypatch: Any) -> tuple[Any, Any]:
    """Import split presentation canvas modules with stubs installed."""

    install_canvas_view_stubs(monkeypatch)
    canvas_package = types.ModuleType("substitute.presentation.canvas")
    canvas_package.__path__ = [
        str(
            Path(__file__).resolve().parents[1]
            / "substitute"
            / "presentation"
            / "canvas"
        )
    ]
    monkeypatch.setitem(sys.modules, "substitute.presentation.canvas", canvas_package)
    for module_name in (
        "substitute.presentation.canvas.shared.canvas_grid_layout",
        "substitute.presentation.canvas.input.input_canvas_view",
        "substitute.presentation.canvas.output.output_canvas_view",
    ):
        sys.modules.pop(module_name, None)
    input_mod = importlib.import_module(
        "substitute.presentation.canvas.input.input_canvas_view"
    )
    output_mod = importlib.import_module(
        "substitute.presentation.canvas.output.output_canvas_view"
    )
    return input_mod, output_mod


def install_canvas_view_stubs(monkeypatch: Any) -> None:
    """Install lightweight runtime stubs needed for canvas widget imports."""

    zoom_indicator = types.ModuleType(
        "substitute.presentation.canvas.shared.canvas_zoom_indicator"
    )
    setattr(
        zoom_indicator,
        "CanvasZoomIndicator",
        type(
            "CanvasZoomIndicator",
            (),
            {"__init__": lambda self, _pane: None},
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.canvas.shared.canvas_zoom_indicator",
        zoom_indicator,
    )

    if "PySide6" not in sys.modules:
        pyside = types.ModuleType("PySide6")
        pyside.__spec__ = importlib.machinery.ModuleSpec(
            "PySide6",
            loader=None,
            is_package=True,
        )
        pyside.__path__ = []
        monkeypatch.setitem(sys.modules, "PySide6", pyside)
    support = types.ModuleType("PySide6.support")
    support.__spec__ = importlib.machinery.ModuleSpec(
        "PySide6.support",
        loader=None,
        is_package=True,
    )
    support.__path__ = []
    pyside_root = sys.modules.get("PySide6")
    if pyside_root is not None:
        setattr(pyside_root, "support", support)
    monkeypatch.setitem(sys.modules, "PySide6.support", support)

    qtcore: Any = types.ModuleType("PySide6.QtCore")
    qtcore.QTimer = type(
        "QTimer", (), {"singleShot": staticmethod(lambda _ms, cb: cb())}
    )
    qtcore.Qt = type(
        "Qt",
        (),
        {
            "CustomContextMenu": 0,
            "ClickFocus": 0,
            "FocusPolicy": SimpleNamespace(ClickFocus=0, StrongFocus=1, NoFocus=2),
            "CursorShape": SimpleNamespace(PointingHandCursor=1),
            "AlignmentFlag": SimpleNamespace(AlignLeft=0),
            "MouseButton": SimpleNamespace(LeftButton=1),
            "Key": SimpleNamespace(
                Key_Escape=1,
                Key_Return=2,
                Key_Enter=3,
                Key_Up=4,
                Key_Down=5,
            ),
            "WA_TranslucentBackground": 0,
            "WA_TransparentForMouseEvents": 0,
            "NoPen": 0,
            "LeftButton": 1,
            "RightButton": 2,
            "Window": 1,
            "NonModal": 2,
            "Tool": 3,
            "WA_DeleteOnClose": 4,
            "GlobalColor": SimpleNamespace(transparent=0),
            "PenCapStyle": SimpleNamespace(SquareCap=1),
        },
    )

    class _QEvent:
        """Small QEvent stand-in exposing mouse button event ids."""

        Type = SimpleNamespace(MouseButtonPress=1, MouseButtonRelease=2)

    qtcore.QEvent = _QEvent

    class QPoint:
        """Small QPoint stand-in with Manhattan distance support."""

        def __init__(self, x: int = 0, y: int = 0) -> None:
            """Store integer coordinates."""

            self.x = x
            self.y = y

        def __sub__(self, other: object) -> "QPoint":
            """Return a point delta."""

            other_point = other if isinstance(other, QPoint) else QPoint()
            return QPoint(self.x - other_point.x, self.y - other_point.y)

        def manhattanLength(self) -> int:  # noqa: N802
            """Return Manhattan distance from the origin."""

            return abs(self.x) + abs(self.y)

    qtcore.QPoint = QPoint
    qtcore.QRect = type("QRect", (), {})

    class QSize:
        """Small QSize stand-in."""

        def __init__(self, width: int = 0, height: int = 0) -> None:
            """Store dimensions."""

            self.width = width
            self.height = height

    qtcore.QSize = QSize

    class QRectF:
        """Small QRectF stand-in."""

        def __init__(
            self,
            x: float = 0.0,
            y: float = 0.0,
            w: float = 0.0,
            h: float = 0.0,
        ) -> None:
            """Store rectangle coordinates and dimensions."""

            self.x = x
            self.y = y
            self.w = w
            self.h = h

        def width(self) -> float:
            """Return rectangle width."""

            return self.w

        def height(self) -> float:
            """Return rectangle height."""

            return self.h

    qtcore.QRectF = QRectF

    class QSizeF:
        """Small QSizeF stand-in."""

        def __init__(self, w: float = 0.0, h: float = 0.0) -> None:
            """Store dimensions."""

            self.w = w
            self.h = h

        def width(self) -> float:
            """Return width."""

            return self.w

        def height(self) -> float:
            """Return height."""

            return self.h

    qtcore.QSizeF = QSizeF
    qtcore.Signal = lambda *_a, **_k: SignalStub()
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)

    qtgui: Any = types.ModuleType("PySide6.QtGui")
    qtgui.QImage = type("QImage", (), {})
    qtgui.QColor = type("QColor", (), {})

    class QIcon:
        """Small QIcon stand-in."""

        def __init__(self, payload: object | None = None) -> None:
            """Store icon payload."""

            self.payload = payload

        def isNull(self) -> bool:  # noqa: N802
            """Return whether the icon has no payload."""

            return self.payload is None

    class QPixmap:
        """Small QPixmap stand-in."""

        def __init__(self, size: object | None = None) -> None:
            """Store pixmap size."""

            self.size = size
            self.fill_color: object | None = None

        def fill(self, color: object) -> None:
            """Record fill color."""

            self.fill_color = color

    class QAction:
        """Small QAction stand-in with trigger/toggle state."""

        def __init__(
            self,
            *args: object,
            triggered: Any = None,
            **_kwargs: object,
        ) -> None:
            """Store action text, icon, and callbacks."""

            self.icon_value = args[0] if len(args) > 1 else QIcon()
            self.text = str(args[1] if len(args) > 1 else args[0])
            self.triggered = triggered
            self.toggled = SignalStub()
            self.enabled = True
            self.checkable = False
            self.checked = False

        def setEnabled(self, enabled: bool) -> None:  # noqa: N802
            """Record enabled state."""

            self.enabled = enabled

        def setCheckable(self, checkable: bool) -> None:  # noqa: N802
            """Record checkable state."""

            self.checkable = checkable

        def setChecked(self, checked: bool) -> None:  # noqa: N802
            """Record checked state."""

            self.checked = checked

        def isCheckable(self) -> bool:  # noqa: N802
            """Return checkable state."""

            return self.checkable

        def isChecked(self) -> bool:  # noqa: N802
            """Return checked state."""

            return self.checked

        def isEnabled(self) -> bool:  # noqa: N802
            """Return enabled state."""

            return self.enabled

        def icon(self) -> QIcon:
            """Return an icon object."""

            return (
                self.icon_value
                if isinstance(self.icon_value, QIcon)
                else QIcon(self.icon_value)
            )

        def setIcon(self, icon: object) -> None:  # noqa: N802
            """Record icon payload."""

            self.icon_value = icon

        def trigger(self) -> None:
            """Emit toggle and trigger callbacks."""

            if self.checkable:
                self.checked = not self.checked
                self.toggled.emit(self.checked)
            if self.triggered is not None:
                try:
                    self.triggered(self.checked)
                except TypeError:
                    self.triggered()

    qtgui.QIcon = QIcon
    qtgui.QPixmap = QPixmap
    qtgui.QAction = QAction
    qtgui.QPainter = type(
        "QPainter",
        (),
        {
            "RenderHint": SimpleNamespace(Antialiasing=1),
            "CompositionMode": SimpleNamespace(CompositionMode_Clear=2),
        },
    )

    class QPen:
        """Small QPen stand-in."""

        def __init__(self, color: object) -> None:
            """Store pen color."""

            self.color = color
            self._width = 1
            self._cap_style: object | None = None

        def setWidth(self, width: int) -> None:  # noqa: N802
            """Record pen width."""

            self._width = width

        def width(self) -> int:
            """Return pen width."""

            return self._width

        def setCapStyle(self, cap_style: object) -> None:  # noqa: N802
            """Record cap style."""

            self._cap_style = cap_style

        def capStyle(self) -> object:  # noqa: N802
            """Return cap style."""

            return self._cap_style

    qtgui.QPen = QPen
    qtgui.QKeyEvent = type("QKeyEvent", (), {})
    qtgui.QMouseEvent = type("QMouseEvent", (), {})
    qtgui.QGuiApplication = type(
        "QGuiApplication",
        (),
        {"clipboard": staticmethod(lambda: SimpleNamespace(setImage=lambda *_a: None))},
    )
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    qtwidgets: Any = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QWidget = type("QWidget", (), {})
    qtwidgets.QListWidgetItem = type("QListWidgetItem", (), {})
    qtwidgets.QPushButton = type("QPushButton", (), {})
    qtwidgets.QVBoxLayout = type("QVBoxLayout", (), {})
    qtwidgets.QLabel = type("QLabel", (), {})
    qtwidgets.QStackedLayout = type("QStackedLayout", (), {})
    qtwidgets.QApplication = type(
        "QApplication",
        (),
        {"startDragDistance": staticmethod(lambda: 10)},
    )
    qtwidgets.QStyle = type(
        "QStyle",
        (),
        {"SubElement": SimpleNamespace(SE_PushButtonContents=object())},
    )
    qtwidgets.QStyleOptionButton = type("QStyleOptionButton", (), {})
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)

    install_qpane_stubs(monkeypatch)

    install_qfluent_stubs(monkeypatch, icon_type=QIcon)

    qframe: Any = types.ModuleType("qframelesswindow")
    qframe.AcrylicWindow = type("AcrylicWindow", (), {})
    monkeypatch.setitem(sys.modules, "qframelesswindow", qframe)

    canvas_tabs: Any = types.ModuleType("substitute.presentation.canvas.factory")
    canvas_tabs.CanvasTabManager = type("CanvasTabManager", (), {})
    canvas_tabs.create_canvas_tabs = lambda **_kwargs: SimpleNamespace(
        canvas_map={},
        visibility_changed=SignalStub(),
    )
    canvas_tabs.create_output_floating_chrome_factory = lambda **_kwargs: (
        SimpleNamespace()
    )
    monkeypatch.setitem(
        sys.modules,
        "substitute.presentation.canvas.factory",
        canvas_tabs,
    )


class SignalStub:
    """Small signal double for import-time Qt stubs."""

    def __init__(self) -> None:
        """Initialize emitted calls and connected slots."""

        self.calls: list[tuple[object, ...]] = []
        self.slots: list[Any] = []

    def connect(self, slot: Any) -> None:
        """Record one connected slot."""

        self.slots.append(slot)

    def emit(self, *args: object) -> None:
        """Record emitted arguments and invoke connected slots."""

        self.calls.append(args)
        for slot in self.slots:
            slot(*args)


def install_qfluent_menu_stubs(monkeypatch: Any) -> None:
    """Install qfluent menu modules needed for headless canvas imports."""

    qfw_menu = types.ModuleType("qfluentwidgets.components.widgets.menu")
    setattr(qfw_menu, "Action", type("Action", (), {}))
    setattr(qfw_menu, "RoundMenu", type("RoundMenu", (), {}))
    setattr(
        qfw_menu,
        "MenuAnimationType",
        type("MenuAnimationType", (), {"DROP_DOWN": object()}),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets.components.widgets.menu", qfw_menu)


def install_qfluent_stubs(monkeypatch: Any, *, icon_type: type[Any]) -> None:
    """Install qfluent modules needed for headless canvas imports."""

    qfw = types.ModuleType("qfluentwidgets")
    setattr(qfw, "FluentIconBase", type("FluentIconBase", (), {}))
    setattr(qfw, "Theme", type("Theme", (), {"AUTO": object()}))
    setattr(qfw, "getIconColor", lambda _theme: "black")

    class FluentIconValue:
        """Small FluentIcon enum value stand-in."""

        def __init__(self, name: str) -> None:
            """Store the icon name."""

            self.name = name

        def icon(self) -> Any:
            """Return an icon object compatible with qfluent call sites."""

            return icon_type(self.name)

    setattr(
        qfw, "MenuAnimationType", type("MenuAnimationType", (), {"DROP_DOWN": object()})
    )
    setattr(
        qfw,
        "FluentIcon",
        type(
            "FluentIcon",
            (),
            {"ACCEPT": FluentIconValue("accept"), "COPY": FluentIconValue("copy")},
        ),
    )
    setattr(qfw, "SegmentedItem", type("SegmentedItem", (), {}))
    setattr(qfw, "SegmentedWidget", type("SegmentedWidget", (), {}))
    setattr(qfw, "Pivot", type("Pivot", (), {}))
    setattr(qfw, "PivotItem", type("PivotItem", (), {}))
    monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)

    qfw_style = types.ModuleType("qfluentwidgets.common.style_sheet")
    setattr(qfw_style, "isDarkTheme", lambda: True)
    setattr(
        qfw_style, "themeColor", lambda: types.SimpleNamespace(name=lambda: "#009faa")
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets.common.style_sheet", qfw_style)

    qfw_font = types.ModuleType("qfluentwidgets.common.font")
    setattr(qfw_font, "setFont", lambda *_args, **_kwargs: None)
    monkeypatch.setitem(sys.modules, "qfluentwidgets.common.font", qfw_font)

    install_qfluent_menu_stubs(monkeypatch)

    qfw_material = types.ModuleType("qfluentwidgets.components.material")
    setattr(
        qfw_material,
        "AcrylicFlyout",
        type(
            "AcrylicFlyout",
            (),
            {
                "make": staticmethod(
                    lambda *_args, **_kwargs: types.SimpleNamespace(
                        isVisible=lambda: True,
                        close=lambda: None,
                    )
                )
            },
        ),
    )
    setattr(
        qfw_material,
        "AcrylicFlyoutViewBase",
        type("AcrylicFlyoutViewBase", (), {}),
    )
    monkeypatch.setitem(sys.modules, "qfluentwidgets.components.material", qfw_material)

    qfw_flyout = types.ModuleType("qfluentwidgets.components.widgets.flyout")
    setattr(
        qfw_flyout,
        "FlyoutAnimationType",
        types.SimpleNamespace(DROP_DOWN=1, PULL_UP=2),
    )
    monkeypatch.setitem(
        sys.modules,
        "qfluentwidgets.components.widgets.flyout",
        qfw_flyout,
    )


def install_qpane_stubs(monkeypatch: Any) -> None:
    """Install qpane modules needed for headless canvas imports."""

    qpane_mod = types.ModuleType("qpane")

    class LinkedGroup:
        """Small linked-group stand-in used by canvas import tests."""

        def __init__(self, group_id: object, members: object) -> None:
            """Store linked group payloads."""

            self.group_id = group_id
            self.members = members

    class QPane:
        """Small QPane stand-in exposing control-mode constants."""

        CONTROL_MODE_PANZOOM = "panzoom"
        CONTROL_MODE_CURSOR = "cursor"
        CONTROL_MODE_DRAW_BRUSH = "draw"
        CONTROL_MODE_SMART_SELECT = "smart"

        @staticmethod
        def fitSceneRect(_source_size: object, _target_rect: object) -> None:
            """Fail if batch grid composition tries to fit individual tiles."""

            raise AssertionError("Batch grid composition should not fit tile rects.")

    setattr(qpane_mod, "LinkedGroup", LinkedGroup)
    setattr(qpane_mod, "QPane", QPane)
    setattr(qpane_mod, "QPaneCatalogImageLayerRequest", types.SimpleNamespace)
    setattr(qpane_mod, "QPaneSceneRequest", types.SimpleNamespace)
    monkeypatch.setitem(sys.modules, "qpane", qpane_mod)

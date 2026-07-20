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

"""Characterization tests for search and seed widget behavior."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[1]


def _install_widget_stubs(
    monkeypatch,
    *,
    qfluentwidgets_mode: str = "missing_font",
    include_qt_widget_fallbacks: bool = True,
):
    class _Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def disconnect(self, callback):
            self._callbacks.remove(callback)

        def emit(self, *args, **kwargs):
            for callback in list(self._callbacks):
                relay = getattr(callback, "emit", None)
                if callable(relay):
                    relay(*args, **kwargs)
                    continue
                callback(*args, **kwargs)

    class _Event:
        Hide = 18
        Close = 19
        Destroy = 16

        class Type:
            Hide = 18
            Close = 19
            Destroy = 16

        def __init__(self):
            self._type = 0

        def type(self):
            return self._type

    qtcore = types.ModuleType("PySide6.QtCore")

    class _QSize:
        def __init__(self, width=0, height=0):
            self._width = width
            self._height = height

        def width(self):
            return self._width

        def height(self):
            return self._height

        def __eq__(self, other):
            return (
                hasattr(other, "width")
                and hasattr(other, "height")
                and self.width() == other.width()
                and self.height() == other.height()
            )

    qtcore.QEvent = type(
        "QEvent",
        (),
        {
            "KeyPress": 6,
            "Hide": 18,
            "Close": 19,
            "Destroy": 16,
            "Type": type(
                "Type",
                (),
                {"Hide": 18, "Close": 19, "Destroy": 16},
            ),
        },
    )
    qtcore.Signal = lambda *_a, **_k: _Signal()
    qtcore.QObject = type("QObject", (), {})
    qtcore.QPoint = lambda x=0, y=0: (x, y)
    qtcore.QSize = _QSize
    qtcore.Qt = type(
        "Qt",
        (),
        {
            "Key_Return": 16777220,
            "Key_Enter": 16777221,
            "ShiftModifier": 0x02000000,
            "Key_Up": 16777235,
            "Key_Down": 16777237,
            "AlignLeft": 0x0001,
            "AlignVCenter": 0x0080,
        },
    )
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)

    qtgui = types.ModuleType("PySide6.QtGui")
    qtgui.QKeyEvent = type("QKeyEvent", (), {})
    qtgui.QWheelEvent = type("QWheelEvent", (), {})
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)

    qtwidgets = types.ModuleType("PySide6.QtWidgets")

    class _Widget:
        def __init__(self, *_args, **_kwargs):
            self._width = 0
            self._height = 0
            self._position = (0, 0)
            self._margins = (0, 0, 0, 0)
            self._alignment = None
            self._visible = False
            self._event_filters = []
            self.closedSignal = _Signal()
            self.destroyed = _Signal()

        def eventFilter(self, *_a, **_k):
            return False

        def installEventFilter(self, target):
            self._event_filters.append(target)

        def removeEventFilter(self, target):
            if target in self._event_filters:
                self._event_filters.remove(target)

        def _dispatch_event(self, event_type):
            event = _Event()
            event._type = event_type
            for event_filter in list(self._event_filters):
                handler = getattr(event_filter, "eventFilter", None)
                if callable(handler):
                    handler(self, event)

        def setFixedWidth(self, width):
            self._width = width

        def setFixedHeight(self, height):
            self._height = height

        def resize(self, width, height):
            self._width = width
            self._height = height

        def setContentsMargins(self, left, top, right, bottom):
            self._margins = (left, top, right, bottom)

        def width(self):
            return self._width

        def height(self):
            return self._height

        def move(self, x, y):
            self._position = (x, y)

        def hide(self):
            self._visible = False
            self._dispatch_event(18)
            self.closedSignal.emit()

        def show(self):
            self._visible = True

        def isVisible(self):
            return self._visible

        def raise_(self):
            return None

    class _SizePolicy:
        Fixed = 0
        Policy = type("Policy", (), {"Fixed": 0, "Preferred": 1})

    qtwidgets.QWidget = _Widget
    qtwidgets.QSizePolicy = _SizePolicy
    qtwidgets.QHBoxLayout = type("QHBoxLayout", (), {})
    if include_qt_widget_fallbacks:
        qtwidgets.QLineEdit = type("QLineEdit", (_Widget,), {})
        qtwidgets.QMenu = type("QMenu", (_Widget,), {})
        qtwidgets.QToolButton = type("QToolButton", (_Widget,), {})
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    pyside6 = types.ModuleType("PySide6")
    pyside6.QtCore = qtcore
    pyside6.QtGui = qtgui
    pyside6.QtWidgets = qtwidgets
    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    shiboken6 = types.ModuleType("shiboken6")
    shiboken6.isValid = lambda _obj: True
    monkeypatch.setitem(sys.modules, "shiboken6", shiboken6)

    import builtins

    original_import = builtins.__import__

    if qfluentwidgets_mode != "missing_package":
        qfw = types.ModuleType("qfluentwidgets")

        class _ComboBox(_Widget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._items = []
                self._current_index = 0
                self.currentTextChanged = _Signal()
                self._object_name = ""

            def setSizePolicy(self, *_args, **_kwargs):
                return None

            def setObjectName(self, name):
                self._object_name = name

            def addItems(self, items):
                self._items.extend(items)

            def setCurrentIndex(self, index):
                self._current_index = index

            def setCurrentText(self, text):
                if text in self._items:
                    self._current_index = self._items.index(text)

            def currentText(self):
                if not self._items:
                    return ""
                return self._items[self._current_index]

            def findText(self, text):
                try:
                    return self._items.index(text)
                except ValueError:
                    return -1

        class _SearchLineEdit(_Widget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._text = ""
                self._placeholder = ""
                self._text_margins = (0, 0, 0, 0)
                self.textChanged = _Signal()
                self._event_filter = None

            def setSizePolicy(self, *_args, **_kwargs):
                return None

            def setPlaceholderText(self, text):
                self._placeholder = text

            def setTextMargins(self, left, top, right, bottom):
                self._text_margins = (left, top, right, bottom)

            def setAlignment(self, alignment):
                self._alignment = alignment

            def installEventFilter(self, target):
                self._event_filter = target

            def text(self):
                return self._text

            def setText(self, text):
                self._text = text
                self.textChanged.emit(text)

        class _Action:
            def __init__(self, _icon, _text, _parent=None, *, triggered=None):
                self.triggered = triggered

        class LineEdit(_Widget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._text = ""
                self.textChanged = _Signal()
                self._blocked = False

            def text(self):
                return self._text

            def setText(self, text):
                self._text = text
                if not self._blocked:
                    self.textChanged.emit(text)

            def setMinimumWidth(self, width):
                self._width = width

            def setTextMargins(self, left, top, right, bottom):
                self._margins = (left, top, right, bottom)

            def blockSignals(self, blocked):
                self._blocked = blocked

            def keyPressEvent(self, _event):
                return None

        class RoundMenu(_Widget):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._actions = []
                self.exec_calls = 0

            def addAction(self, action):
                self._actions.append(action)

            def exec(self, *_args, **_kwargs):
                self.exec_calls += 1
                self._visible = True

        qfw.ComboBox = _ComboBox
        qfw.SearchLineEdit = _SearchLineEdit
        qfw.Action = _Action
        qfw.FluentIcon = type("FluentIcon", (), {"PIN": object(), "UNPIN": object()})
        qfw.LineEdit = LineEdit
        qfw.RoundMenu = RoundMenu
        qfw.SplitToolButton = type("SplitToolButton", (), {})
        monkeypatch.setitem(sys.modules, "qfluentwidgets", qfw)

        if qfluentwidgets_mode == "full":
            qfw_common = types.ModuleType("qfluentwidgets.common")
            qfw_font = types.ModuleType("qfluentwidgets.common.font")
            qfw_font.setFont = lambda *_args, **_kwargs: None
            monkeypatch.setitem(sys.modules, "qfluentwidgets.common", qfw_common)
            monkeypatch.setitem(sys.modules, "qfluentwidgets.common.font", qfw_font)
        else:
            monkeypatch.delitem(sys.modules, "qfluentwidgets.common", raising=False)
            monkeypatch.delitem(
                sys.modules, "qfluentwidgets.common.font", raising=False
            )

            def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
                if name == "qfluentwidgets.common.font" or name.startswith(
                    "qfluentwidgets.common.font."
                ):
                    raise ModuleNotFoundError(name)
                return original_import(name, globals, locals, fromlist, level)

            monkeypatch.setattr(builtins, "__import__", _guarded_import)
    else:
        monkeypatch.delitem(sys.modules, "qfluentwidgets", raising=False)
        monkeypatch.delitem(sys.modules, "qfluentwidgets.common", raising=False)
        monkeypatch.delitem(sys.modules, "qfluentwidgets.common.font", raising=False)

        def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "qfluentwidgets" or name.startswith("qfluentwidgets."):
                raise ModuleNotFoundError(name)
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _guarded_import)


def _import_search_box(monkeypatch):
    _install_widget_stubs(monkeypatch, qfluentwidgets_mode="full")
    package_name = "substitute.presentation.widgets"
    package = types.ModuleType(package_name)
    package.__path__ = [str(REPO_ROOT / "substitute" / "presentation" / "widgets")]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, package_name, package)

    module_name = "substitute.presentation.widgets.search_box"
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO_ROOT / "substitute" / "presentation" / "widgets" / "search_box.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    module.set_localized_placeholder = lambda target, text: target.setPlaceholderText(
        str(text)
    )
    sys.modules.pop("substitute.presentation.widgets.menu_buttons", None)
    sys.modules.pop(module_name, None)
    return module


def _import_seed_box(
    monkeypatch,
    *,
    qfluentwidgets_mode: str = "missing_font",
    include_qt_widget_fallbacks: bool = True,
):
    _install_widget_stubs(
        monkeypatch,
        qfluentwidgets_mode=qfluentwidgets_mode,
        include_qt_widget_fallbacks=include_qt_widget_fallbacks,
    )
    package_name = "substitute.presentation.widgets"
    package = types.ModuleType(package_name)
    package.__path__ = [str(REPO_ROOT / "substitute" / "presentation" / "widgets")]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, package_name, package)

    monkeypatch.delitem(
        sys.modules,
        "substitute.presentation.widgets.menu_buttons",
        raising=False,
    )
    module_name = "substitute.presentation.widgets._seed_box_stub_test"
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    spec = importlib.util.spec_from_file_location(
        module_name,
        REPO_ROOT / "substitute" / "presentation" / "widgets" / "seed_box.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    module.set_localized_tooltip = lambda target, text: target.setToolTip(str(text))
    sys.modules.pop("substitute.presentation.widgets.menu_buttons", None)
    sys.modules.pop(module_name, None)
    return module


class _FakeText:
    def __init__(self, text=""):
        self._text = text
        self.blocked = False

    def text(self):
        return self._text

    def setText(self, text):
        self._text = text

    def blockSignals(self, blocked):
        self.blocked = blocked


class _FakeSignal:
    def __init__(self):
        self.calls = []

    def emit(self, *args):
        self.calls.append(args)


def test_context_search_emit_change_parses_full_context_commands(monkeypatch) -> None:
    """Completed @field/@node/@text commands switch context and strip prefixes."""
    module = _import_search_box(monkeypatch)
    emitted = _FakeSignal()

    combo = SimpleNamespace(
        _text="Text",
        setCurrentText=lambda val: setattr(combo, "_text", val),
        currentText=lambda: combo._text,
    )
    search = _FakeText("@field   guidance")
    fake_self = SimpleNamespace(
        comboBox=combo, searchLineEdit=search, contextSearchChanged=emitted
    )

    module.ContextSearchBox._emit_change(fake_self)
    assert combo.currentText() == "Field"
    assert search.text() == "guidance"
    assert emitted.calls == []

    module.ContextSearchBox._emit_change(fake_self)
    assert emitted.calls[-1] == ("Field", "guidance")


def test_context_search_emit_change_suppresses_partial_at_commands(monkeypatch) -> None:
    """Text starting with @ but missing a full command should not emit updates."""
    module = _import_search_box(monkeypatch)
    emitted = _FakeSignal()

    combo = SimpleNamespace(currentText=lambda: "Text", setCurrentText=lambda _v: None)
    search = _FakeText("@fi")
    fake_self = SimpleNamespace(
        comboBox=combo, searchLineEdit=search, contextSearchChanged=emitted
    )

    module.ContextSearchBox._emit_change(fake_self)
    assert emitted.calls == []


def test_context_search_init_keeps_historical_overlay_geometry(monkeypatch) -> None:
    """Search box should overlay context combo and keep text left-aligned."""
    module = _import_search_box(monkeypatch)
    widget = module.ContextSearchBox()

    assert widget.width() == widget.searchLineEdit.width()
    assert widget.comboBox._position == (0, 0)
    assert widget.searchLineEdit._position == (0, 0)
    assert widget.searchLineEdit._text_margins == (widget.comboBox.width() - 4, 0, 0, 0)
    assert widget.searchLineEdit._alignment == (
        module.Qt.AlignLeft | module.Qt.AlignVCenter
    )


def test_context_search_event_filter_handles_shift_enter_with_qt_modifier_objects(
    monkeypatch,
) -> None:
    """Shift+Enter should navigate backward even when modifiers are Qt flag objects."""

    module = _import_search_box(monkeypatch)
    widget = module.ContextSearchBox()

    forward_calls: list[str] = []
    backward_calls: list[str] = []
    widget.cycleSearchMatchRequested.connect(lambda: forward_calls.append("forward"))
    widget.cycleSearchMatchRequestedBackward.connect(
        lambda: backward_calls.append("backward")
    )

    class _KeyboardModifier:
        def __init__(self, value: int) -> None:
            self._value = value

        def __int__(self) -> int:
            return self._value

    class _KeyEvent(module.QKeyEvent):
        def type(self):
            return module._event_key_press_type()

        def key(self):
            return module._qt_key("Key_Return", 16777220)

        def modifiers(self):
            return _KeyboardModifier(module._qt_shift_modifier())

    handled = widget.eventFilter(widget.searchLineEdit, _KeyEvent())

    assert handled is True
    assert forward_calls == []
    assert backward_calls == ["backward"]


def test_seedbox_filter_numeric_and_clamp_behavior(monkeypatch) -> None:
    """SeedBox numeric sanitizer should retain sign and digits, then clamp limits."""
    module = _import_seed_box(monkeypatch)
    fake_self = SimpleNamespace(_minimum=0, _maximum=10, _allow_negative=True)

    assert module.SeedBox._filter_numeric(fake_self, " -12x3 ") == "-123"
    assert module.SeedBox._clamp(fake_self, -9) == 0
    assert module.SeedBox._clamp(fake_self, 22) == 10


def test_seedbox_on_text_changed_emits_only_on_value_change(monkeypatch) -> None:
    """on_text_changed should emit once per effective value transition."""
    module = _import_seed_box(monkeypatch)
    signal = _FakeSignal()
    line_edit = _FakeText("999")
    fake_self = SimpleNamespace(
        _minimum=0,
        _maximum=100,
        _allow_negative=False,
        _last_value=None,
        line_edit=line_edit,
        valueChanged=signal,
    )
    fake_self._filter_numeric = lambda txt: module.SeedBox._filter_numeric(
        fake_self, txt
    )
    fake_self._clamp = lambda val: module.SeedBox._clamp(fake_self, val)

    module.SeedBox._on_text_changed(fake_self, line_edit.text())
    module.SeedBox._on_text_changed(fake_self, line_edit.text())

    assert line_edit.text() == "100"
    assert signal.calls == [(100,)]


def test_seedbox_mode_handlers_update_icon_and_emit_mode(monkeypatch) -> None:
    """Mode setters should apply icon semantics and emit explicit mode changes."""
    module = _import_seed_box(monkeypatch)
    icons = []
    modes = []
    fake_self = SimpleNamespace(
        _mode="fixed",
        _set_mode_icon=lambda icon: icons.append(icon),
        modeChanged=SimpleNamespace(emit=lambda mode: modes.append(mode)),
    )

    module.SeedBox._set_random_mode(fake_self)
    module.SeedBox._set_fixed_mode(fake_self)

    assert icons == [module._RANDOM_SEED_ICON, module._FIXED_SEED_ICON]
    assert modes == ["random", "fixed"]


def test_seedbox_import_keeps_widget_classes_when_font_module_is_missing(
    monkeypatch,
) -> None:
    """Missing qfluentwidgets font helpers should not force the full widget fallback."""

    module = _import_seed_box(monkeypatch, qfluentwidgets_mode="missing_font")

    assert module.LineEdit.__name__ == "LineEdit"
    assert module.SplitToolButton.__name__ == "ToggleSplitToolButton"
    module.setFont(object())


def test_seedbox_import_uses_local_fallbacks_when_qfluentwidgets_is_missing(
    monkeypatch,
) -> None:
    """Missing qfluentwidgets package should still import via local widget fallbacks."""

    module = _import_seed_box(
        monkeypatch,
        qfluentwidgets_mode="missing_package",
        include_qt_widget_fallbacks=False,
    )

    assert module.LineEdit.__name__ == "_FallbackLineEdit"
    assert module.RoundMenu.__name__ == "_FallbackMenu"
    assert module.SplitToolButton.__name__ == "_FallbackSplitToolButton"
    module.setFont(object())


def test_seedbox_split_button_toggle_closes_open_menu(monkeypatch) -> None:
    """SeedBox should wire the shared split-button wrapper so second clicks close the menu."""

    module = _import_seed_box(monkeypatch, qfluentwidgets_mode="missing_font")
    widget = module.SeedBox()

    widget.split_button.dropButton.clicked.emit()
    assert widget.menu.exec_calls == 1
    assert widget.menu.isVisible() is True

    widget.split_button.dropButton.clicked.emit()
    assert widget.menu.exec_calls == 1
    assert widget.menu.isVisible() is False

    widget.split_button.dropButton.clicked.emit()
    assert widget.menu.exec_calls == 2
    assert widget.menu.isVisible() is True


def test_seedbox_clamp_keeps_large_values_when_no_maximum(monkeypatch) -> None:
    """Clamp should not force 32-bit ceilings when no maximum is configured."""
    module = _import_seed_box(monkeypatch)
    fake_self = SimpleNamespace(_minimum=None, _maximum=None)
    huge_value = 18_446_744_073_709_551_615 + 123

    assert module.SeedBox._clamp(fake_self, huge_value) == huge_value


def test_seedbox_keypress_up_down_steps_and_accepts(monkeypatch) -> None:
    """Up/Down key events should step the seed value and accept the event."""
    module = _import_seed_box(monkeypatch)

    class _KeyEvent:
        def __init__(self, key_code: int):
            self._key_code = key_code
            self.accepted = False

        def key(self):
            return self._key_code

        def accept(self):
            self.accepted = True

    calls = []
    fake_self = SimpleNamespace(
        _minimum=0,
        _maximum=20,
        _step=2,
        line_edit=_FakeText("10"),
        setValue=lambda val: calls.append(val),
    )
    fake_self._clamp = lambda val: module.SeedBox._clamp(fake_self, val)

    up_event = _KeyEvent(module.Qt.Key_Up)
    down_event = _KeyEvent(module.Qt.Key_Down)
    module.SeedBox.keyPressEvent(fake_self, up_event)
    module.SeedBox.keyPressEvent(fake_self, down_event)

    assert calls == [12, 8]
    assert up_event.accepted is True
    assert down_event.accepted is True


def test_seedbox_wheel_event_steps_and_clamps(monkeypatch) -> None:
    """Wheel delta should step value and clamp using configured bounds."""
    module = _import_seed_box(monkeypatch)

    class _WheelEvent:
        def __init__(self, delta: int):
            self._delta = delta
            self.accepted = False

        def angleDelta(self):
            return SimpleNamespace(y=lambda: self._delta)

        def accept(self):
            self.accepted = True

    calls = []
    fake_self = SimpleNamespace(
        _minimum=0,
        _maximum=10,
        _step=5,
        line_edit=_FakeText("3"),
        setValue=lambda val: calls.append(val),
    )
    fake_self._clamp = lambda val: module.SeedBox._clamp(fake_self, val)

    up_event = _WheelEvent(120)
    down_event = _WheelEvent(-120)
    module.SeedBox.wheelEvent(fake_self, up_event)
    module.SeedBox.wheelEvent(fake_self, down_event)

    assert calls == [8, 0]
    assert up_event.accepted is True
    assert down_event.accepted is True

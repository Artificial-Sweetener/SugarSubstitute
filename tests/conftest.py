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

"""Shared pytest configuration and safety guards for Substitute tests."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import faulthandler
import os
import sys
import threading
import time
import types
from collections.abc import Generator
from pathlib import Path

import pytest

from substitute.shared.qfluentwidgets_banner import (
    install_qfluentwidgets_banner_filter,
)
from tests.ci_test_policy import (
    SERIAL_TEST_MODULES,
    current_test_platform,
    marker_test_platforms,
    platform_skip_reason,
)

install_qfluentwidgets_banner_filter()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("SUBSTITUTE_DISABLE_APP_USER_MODEL_ID", "1")
os.environ.setdefault("SUBSTITUTE_DISABLE_QPANE_SAM_WARMUP", "1")

_TEST_PROCESS_MEMORY_LIMIT_BYTES = int(
    os.environ.get("SUBSTITUTE_TEST_PROCESS_MEMORY_LIMIT_BYTES", str(8 * 1024**3))
)
_TEST_PROCESS_MEMORY_CHECK_SECONDS = float(
    os.environ.get("SUBSTITUTE_TEST_PROCESS_MEMORY_CHECK_SECONDS", "1.0")
)
_TEST_PROCESS_TEST_TIMEOUT_SECONDS = float(
    os.environ.get("SUBSTITUTE_TEST_PROCESS_TEST_TIMEOUT_SECONDS", "300.0")
)
_memory_watchdog_started = False
_watchdog_lock = threading.Lock()
_active_test_nodeid: str | None = None
_active_test_deadline: float | None = None
_PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _ProcessMemoryCountersEx(ctypes.Structure):
    """Represent the Windows process memory counters returned by psapi."""

    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("PageFaultCount", ctypes.wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start per-process resource guards before test collection."""

    del session
    _start_test_process_memory_watchdog()


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply authoritative serial and platform policy before marker selection."""

    current_platform = current_test_platform()
    for item in items:
        relative_path = item.path.resolve().relative_to(_PROJECT_ROOT).as_posix()
        if relative_path in SERIAL_TEST_MODULES:
            item.add_marker(pytest.mark.serial)

        platform_marker = item.get_closest_marker("platforms")
        if platform_marker is None:
            continue
        try:
            supported_platforms = marker_test_platforms(platform_marker.args)
        except ValueError as error:
            raise pytest.UsageError(f"{item.nodeid}: {error}") from error
        skip_reason = platform_skip_reason(
            supported=supported_platforms,
            current=current_platform,
        )
        if skip_reason is not None:
            item.add_marker(pytest.mark.skip(reason=skip_reason))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(
    item: pytest.Item,
    nextitem: pytest.Item | None,
) -> Generator[None, None, None]:
    """Track each full test lifecycle so hung pytest workers terminate themselves."""

    del nextitem
    if _TEST_PROCESS_TEST_TIMEOUT_SECONDS <= 0:
        yield
        return

    global _active_test_deadline, _active_test_nodeid
    with _watchdog_lock:
        _active_test_nodeid = item.nodeid
        _active_test_deadline = time.monotonic() + _TEST_PROCESS_TEST_TIMEOUT_SECONDS
    try:
        yield
    finally:
        with _watchdog_lock:
            _active_test_nodeid = None
            _active_test_deadline = None


def _start_test_process_memory_watchdog() -> None:
    """Start a daemon guard that terminates runaway pytest workers."""

    global _memory_watchdog_started
    if (
        _memory_watchdog_started
        or sys.platform != "win32"
        or _TEST_PROCESS_MEMORY_LIMIT_BYTES <= 0
    ):
        return

    _memory_watchdog_started = True
    thread = threading.Thread(
        target=_watch_test_process_resources,
        args=(
            _TEST_PROCESS_MEMORY_LIMIT_BYTES,
            _TEST_PROCESS_MEMORY_CHECK_SECONDS,
        ),
        name="substitute-test-memory-watchdog",
        daemon=True,
    )
    thread.start()


def _watch_test_process_resources(limit_bytes: int, interval_seconds: float) -> None:
    """Exit this pytest process before runaway tests exhaust time or RAM."""

    while True:
        _exit_if_active_test_timed_out()
        private_bytes = _current_process_private_bytes()
        if private_bytes is not None and private_bytes > limit_bytes:
            print(
                (
                    "Substitute pytest process exceeded memory limit: "
                    f"{private_bytes / 1024**3:.2f} GiB used, "
                    f"{limit_bytes / 1024**3:.2f} GiB allowed. "
                    "Terminating this test process."
                ),
                file=sys.stderr,
                flush=True,
            )
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
            os._exit(137)
        time.sleep(max(interval_seconds, 0.1))


def _exit_if_active_test_timed_out() -> None:
    """Terminate this process if pytest is stuck inside one test item."""

    with _watchdog_lock:
        nodeid = _active_test_nodeid
        deadline = _active_test_deadline

    if deadline is None or time.monotonic() <= deadline:
        return

    print(
        (
            "Substitute pytest process exceeded per-test timeout: "
            f"{_TEST_PROCESS_TEST_TIMEOUT_SECONDS:.1f} seconds in {nodeid}. "
            "Terminating this test process."
        ),
        file=sys.stderr,
        flush=True,
    )
    faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
    os._exit(124)


def _current_process_private_bytes() -> int | None:
    """Return private bytes for the current Windows process."""

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = (
        ctypes.wintypes.HANDLE,
        ctypes.POINTER(_ProcessMemoryCountersEx),
        ctypes.wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = ctypes.wintypes.BOOL
    counters = _ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(_ProcessMemoryCountersEx)
    process = kernel32.GetCurrentProcess()
    succeeded = psapi.GetProcessMemoryInfo(
        process,
        ctypes.byref(counters),
        counters.cb,
    )
    if not succeeded:
        return None
    return int(counters.PrivateUsage)


def _install_stub_modules():
    """Install lightweight stubs for heavy GUI deps so we can import main.py.

    This avoids requiring PySide6/qfluentwidgets/qframelesswindow during tests.
    """
    # qpane stub
    if "qpane" not in sys.modules:
        m = types.ModuleType("qpane")

        class QPane:  # placeholder
            CONTROL_MODE_PANZOOM = "panzoom"
            CONTROL_MODE_DRAW_BRUSH = "draw-brush"
            CONTROL_MODE_SMART_SELECT = "smart-select"

            def __init__(self, *args, **kwargs):
                pass

            def setControlMode(self, *args, **kwargs):
                pass

        class LinkedGroup:
            def __init__(self, *args, **kwargs):
                pass

        m.QPane = QPane
        m.LinkedGroup = LinkedGroup
        sys.modules["qpane"] = m

    # PySide6 stubs
    if "PySide6" not in sys.modules:
        pyside = types.ModuleType("PySide6")
        sys.modules["PySide6"] = pyside
    qtcore = types.ModuleType("PySide6.QtCore")

    class Qt:
        white = object()

    qtcore.Qt = Qt
    sys.modules["PySide6.QtCore"] = qtcore

    qtgui = types.ModuleType("PySide6.QtGui")

    class QColor:
        def __init__(self, *args, **kwargs):
            pass

    qtgui.QColor = QColor
    sys.modules["PySide6.QtGui"] = qtgui

    qtwidgets = types.ModuleType("PySide6.QtWidgets")

    class QApplication:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 0

        def setQuitOnLastWindowClosed(self, *a, **k):
            pass

        @staticmethod
        def instance():
            return None

        aboutToQuit = types.SimpleNamespace(connect=lambda *a, **k: None)

    class QWidget:
        def __init__(self, *args, **kwargs):
            pass

        def setLayout(self, *args, **kwargs):
            pass

        def setStyleSheet(self, *args, **kwargs):
            pass

    class QHBoxLayout:
        def __init__(self, *a, **k):
            pass

        def setContentsMargins(self, *a, **k):
            pass

        def setSpacing(self, *a, **k):
            pass

        def addWidget(self, *a, **k):
            pass

    class QVBoxLayout(QHBoxLayout):
        pass

    qtwidgets.QApplication = QApplication
    qtwidgets.QWidget = QWidget
    qtwidgets.QHBoxLayout = QHBoxLayout
    qtwidgets.QVBoxLayout = QVBoxLayout
    sys.modules["PySide6.QtWidgets"] = qtwidgets

    # qfluentwidgets stubs
    if "qfluentwidgets" not in sys.modules:
        qfw = types.ModuleType("qfluentwidgets")

        class _Icon:
            def icon(self):
                return object()

        class FluentIcon:
            HOME = _Icon()
            SETTING = _Icon()

        def setTheme(*a, **k):
            pass

        def setThemeColor(*a, **k):
            pass

        class Theme:
            DARK = object()

        qfw.FluentIcon = FluentIcon
        qfw.setTheme = setTheme
        qfw.setThemeColor = setThemeColor
        qfw.Theme = Theme
        sys.modules["qfluentwidgets"] = qfw

    # qframelesswindow stubs
    if "qframelesswindow" not in sys.modules:
        qfw2 = types.ModuleType("qframelesswindow")

        class AcrylicWindow:
            def __init__(self, *a, **k):
                self.windowEffect = types.SimpleNamespace(
                    setMicaEffect=lambda *a, **k: None,
                    setAcrylicEffect=lambda *a, **k: None,
                )
                self.titleBar = types.SimpleNamespace(
                    height=lambda: 0,
                    closeBtn=types.SimpleNamespace(
                        clicked=types.SimpleNamespace(connect=lambda *a, **k: None)
                    ),
                )

            def setTitleBar(self, *a, **k):
                pass

            def screen(self):
                class _Geo:
                    def availableGeometry(self2):
                        class R:
                            def width(self3):
                                return 1920

                            def height(self3):
                                return 1080

                            def left(self3):
                                return 0

                            def top(self3):
                                return 0

                        return R()

                return _Geo()

            def resize(self, *a, **k):
                pass

            def move(self, *a, **k):
                pass

            def setWindowTitle(self, *a, **k):
                pass

            def setWindowIcon(self, *a, **k):
                pass

            def show(self, *a, **k):
                pass

        qfw2.AcrylicWindow = AcrylicWindow
        sys.modules["qframelesswindow"] = qfw2

    titlebar = types.ModuleType("qframelesswindow.titlebar")

    class TitleBar:
        def __init__(self, *a, **k):
            self.minBtn = types.SimpleNamespace(
                setNormalColor=lambda *a, **k: None,
                setHoverColor=lambda *a, **k: None,
                setPressedColor=lambda *a, **k: None,
                setHoverBackgroundColor=lambda *a, **k: None,
                setPressedBackgroundColor=lambda *a, **k: None,
            )
            self.maxBtn = types.SimpleNamespace(
                setNormalColor=lambda *a, **k: None,
                setHoverColor=lambda *a, **k: None,
                setPressedColor=lambda *a, **k: None,
                setHoverBackgroundColor=lambda *a, **k: None,
                setPressedBackgroundColor=lambda *a, **k: None,
            )
            self.closeBtn = types.SimpleNamespace(
                setNormalColor=lambda *a, **k: None,
                clicked=types.SimpleNamespace(connect=lambda *a, **k: None),
            )

            def layout():
                return types.SimpleNamespace(
                    insertWidget=lambda *a, **k: None, setStretch=lambda *a, **k: None
                )

            self.layout = layout
            self.setFixedHeight = lambda *a, **k: None

    titlebar.TitleBar = TitleBar
    sys.modules["qframelesswindow.titlebar"] = titlebar

    # Substitute local UI modules used in main
    # Avoid importing heavy real modules by providing minimal stubs
    if "substitute.presentation.shell.main_window" not in sys.modules:
        smw = types.ModuleType("substitute.presentation.shell.main_window")

        class MainWindow:
            def __init__(self, *a, **k):
                pass

        smw.MainWindow = MainWindow
        sys.modules["substitute.presentation.shell.main_window"] = smw
    if "substitute.presentation.shell.splash_window" not in sys.modules:
        ss = types.ModuleType("substitute.presentation.shell.splash_window")

        class SplashWindow:
            def __init__(self, *a, **k):
                self._logs = []

            def center_on_screen(self):
                pass

            def show(self):
                pass

            def append_log(self, s: str):
                self._logs.append(s)

            def close(self):
                pass

        ss.SplashWindow = SplashWindow
        sys.modules["substitute.presentation.shell.splash_window"] = ss


def import_main_module():
    _install_stub_modules()
    import importlib

    return importlib.import_module("main")


__all__ = [
    "import_main_module",
]


# Ensure repo root is on sys.path for direct package imports in tests
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


@pytest.fixture()
def main_mod():
    return import_main_module()


@pytest.fixture(autouse=True)
def cleanup_qt_widgets_after_test() -> Generator[None, None, None]:
    """Flush leftover real-Qt widget state between tests in long-lived workers."""

    yield
    _cleanup_qt_application_state()


def _cleanup_qt_application_state() -> None:
    """Close top-level Qt widgets and process deferred deletes after each test."""

    qtwidgets = sys.modules.get("PySide6.QtWidgets")
    if qtwidgets is None:
        return
    application_class = getattr(qtwidgets, "QApplication", None)
    instance = getattr(application_class, "instance", None)
    if not callable(instance):
        return
    try:
        application = instance()
    except RuntimeError:
        return
    if application is None:
        return

    top_level_widgets = getattr(application, "topLevelWidgets", None)
    process_events = getattr(application, "processEvents", None)
    if not callable(top_level_widgets) or not callable(process_events):
        return

    for widget in list(top_level_widgets()):
        _close_and_delete_qt_widget(widget)
    _flush_qt_deferred_deletes(application)


def _close_and_delete_qt_widget(widget: object) -> None:
    """Schedule one Qt widget for deletion without failing unrelated tests."""

    close = getattr(widget, "close", None)
    if callable(close):
        try:
            close()
        except RuntimeError:
            return
    delete_later = getattr(widget, "deleteLater", None)
    if callable(delete_later):
        try:
            delete_later()
        except RuntimeError:
            return


def _flush_qt_deferred_deletes(application: object) -> None:
    """Process pending Qt delete events without depending on pytest-qt."""

    qtcore = sys.modules.get("PySide6.QtCore")
    if qtcore is not None:
        core_application = getattr(qtcore, "QCoreApplication", None)
        event_class = getattr(qtcore, "QEvent", None)
        event_type = getattr(event_class, "Type", event_class)
        deferred_delete = getattr(event_type, "DeferredDelete", None)
        send_posted_events = getattr(core_application, "sendPostedEvents", None)
        if callable(send_posted_events) and deferred_delete is not None:
            try:
                send_posted_events(None, deferred_delete)
            except RuntimeError:
                return

    process_events = getattr(application, "processEvents", None)
    if not callable(process_events):
        return
    for _ in range(2):
        try:
            process_events()
        except RuntimeError:
            return

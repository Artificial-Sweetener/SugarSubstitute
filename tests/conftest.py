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
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from PySide6.QtGui import QClipboard

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication

from substitute.shared.qfluentwidgets_banner import (
    install_qfluentwidgets_banner_filter,
)
from tests.ci_test_policy import (
    ISOLATED_TEST_MODULES,
    PLATFORM_TEST_MODULES,
    SERIAL_TEST_MODULES,
    current_test_platform,
    marker_test_platforms,
    parallel_test_worker_count,
    platform_skip_reason,
)
from tests.support.qt.clipboard import preserve_qt_clipboard

install_qfluentwidgets_banner_filter()

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_OPENGL", "software")
os.environ.setdefault("SUBSTITUTE_DISABLE_APP_USER_MODEL_ID", "1")
os.environ.setdefault("SUBSTITUTE_DISABLE_CUTECANVAS_SAM_WARMUP", "1")

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
_TEST_EXECUTION_SEQUENCE = pytest.StashKey[int]()


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


def pytest_xdist_auto_num_workers(config: pytest.Config) -> int:
    """Keep automatic xdist concurrency inside the stable native Qt envelope."""

    del config
    return parallel_test_worker_count(os.cpu_count())


def pytest_ignore_collect(
    collection_path: Path,
    config: pytest.Config,
) -> bool | None:
    """Skip whole test modules before unsupported platform imports execute."""

    del config
    if not PLATFORM_TEST_MODULES:
        return None
    try:
        relative_path = collection_path.resolve().relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        return None
    supported_platforms = PLATFORM_TEST_MODULES.get(relative_path)
    if supported_platforms is None:
        return None
    return current_test_platform() not in supported_platforms


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start per-process resource guards before test collection."""

    session.config.stash[_TEST_EXECUTION_SEQUENCE] = 0
    _install_offscreen_macos_frameless_shim()
    _start_test_process_memory_watchdog()


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Attach worker-local order evidence to every JUnit test case."""

    sequence = item.config.stash.get(_TEST_EXECUTION_SEQUENCE, 0) + 1
    item.config.stash[_TEST_EXECUTION_SEQUENCE] = sequence
    item.user_properties.extend(
        (
            ("execution_worker", _execution_worker_label(item.config)),
            ("execution_sequence", sequence),
        )
    )


def _execution_worker_label(config: pytest.Config) -> str:
    """Return xdist's diagnostic worker label without changing test behavior."""

    worker_input = getattr(config, "workerinput", None)
    if isinstance(worker_input, dict):
        worker_id = worker_input.get("workerid")
        if isinstance(worker_id, str):
            return worker_id
    return "controller"


@pytest.fixture(scope="session", autouse=True)
def qt_application_owner() -> Generator[QApplication, None, None]:
    """Keep one real QApplication alive for the complete pytest worker process."""

    from PySide6.QtWidgets import QApplication

    existing = QApplication.instance()
    application = existing if isinstance(existing, QApplication) else QApplication([])
    application.setQuitOnLastWindowClosed(False)
    yield application


@pytest.fixture
def qt_clipboard_owner() -> Generator[QClipboard, None, None]:
    """Restore the process clipboard after an explicitly marked Qt test module."""

    with preserve_qt_clipboard() as clipboard:
        yield clipboard


def _install_offscreen_macos_frameless_shim() -> None:
    """Disable Cocoa-only window effects under Qt's offscreen test backend."""

    if (
        sys.platform != "darwin"
        or os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
    ):
        return

    from qframelesswindow.mac import MacFramelessWindowBase  # type: ignore[import-untyped]
    from qframelesswindow.mac.window_effect import MacWindowEffect  # type: ignore[import-untyped]

    def ignore_native_window_effect(*_args: object, **_kwargs: object) -> None:
        """Leave native Cocoa effects disabled for an offscreen Qt window."""

    setattr(MacWindowEffect, "setAcrylicEffect", ignore_native_window_effect)
    setattr(MacFramelessWindowBase, "updateFrameless", ignore_native_window_effect)
    setattr(
        MacFramelessWindowBase,
        "_updateSystemTitleBar",
        ignore_native_window_effect,
    )


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply authoritative serial and platform policy before marker selection."""

    current_platform = current_test_platform()
    constrained_modules = ISOLATED_TEST_MODULES | SERIAL_TEST_MODULES
    relative_paths: dict[Path, str] = {}
    for item in items:
        if constrained_modules:
            relative_path = relative_paths.get(item.path)
            if relative_path is None:
                relative_path = (
                    item.path.resolve().relative_to(_PROJECT_ROOT).as_posix()
                )
                relative_paths[item.path] = relative_path
            if relative_path in ISOLATED_TEST_MODULES:
                item.add_marker(pytest.mark.isolated)
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

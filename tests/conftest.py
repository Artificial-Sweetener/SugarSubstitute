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

import os
import sys
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
from tools.ci.pytest_worker_timeout import PytestWorkerTimeoutGuard
from tools.ci.windows_process_memory_guard import (
    start_windows_process_memory_guard,
)

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
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_TEST_EXECUTION_SEQUENCE = pytest.StashKey[int]()
_WORKER_TIMEOUT_GUARD = pytest.StashKey[PytestWorkerTimeoutGuard]()


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
    session.config.stash[_WORKER_TIMEOUT_GUARD] = PytestWorkerTimeoutGuard(
        timeout_seconds=_TEST_PROCESS_TEST_TIMEOUT_SECONDS,
        evidence_directory=_PROJECT_ROOT / "build" / "test-results" / "process-guards",
        worker_id=_execution_worker_label(session.config),
    )
    _install_offscreen_macos_frameless_shim()
    start_windows_process_memory_guard(
        limit_bytes=_TEST_PROCESS_MEMORY_LIMIT_BYTES,
        check_interval_seconds=_TEST_PROCESS_MEMORY_CHECK_SECONDS,
    )


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: int | pytest.ExitCode,
) -> None:
    """Remove active-test evidence only after this pytest process exits cleanly."""

    del exitstatus
    session.config.stash[_WORKER_TIMEOUT_GUARD].close_cleanly()


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
    guard = item.config.stash[_WORKER_TIMEOUT_GUARD]
    with guard.guard_test(item.nodeid):
        yield

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

"""Prove shell cleanup precedes application-global Qt teardown."""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import InfoBar, InfoBarPosition  # type: ignore[import-untyped]
from qfluentwidgets.components.widgets.info_bar import (  # type: ignore[import-untyped]
    InfoBarManager,
)
from shiboken6 import isValid

from substitute.app.bootstrap.shell_resource_qt_binding import (
    bind_shell_resource_lifecycle,
)
from substitute.presentation.shell.shell_info_bar_lifecycle import (
    ShellInfoBarLifecycle,
)
from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)
from tests.support.qt.lifecycle import destroy_qt_object


class _ApplicationSignalOwner(QObject):
    """Expose an isolated Qt application-shutdown signal for lifecycle tests."""

    aboutToQuit = Signal()


def test_application_quit_closes_active_info_bar_before_global_qt_teardown(
    qt_application_owner: QApplication,
) -> None:
    """An active QFluent bar must detach while its global manager remains alive."""

    application_signals = _ApplicationSignalOwner()
    shell = QWidget()
    lifecycle = ShellResourceLifecycle()
    info_bars = ShellInfoBarLifecycle(shell)
    lifecycle.register("fluent_info_bars", info_bars.shutdown)
    binding = bind_shell_resource_lifecycle(
        application=cast(QApplication, application_signals),
        shell=shell,
        lifecycle=lifecycle,
    )
    bar = InfoBar.error(
        title="Disconnected",
        content="",
        duration=-1,
        position=InfoBarPosition.TOP_RIGHT,
        parent=shell,
    )
    shell.show()
    qt_application_owner.processEvents()
    closed_count = 0

    def record_close() -> None:
        """Record the synchronous manager-detachment signal."""

        nonlocal closed_count
        closed_count += 1

    bar.closedSignal.connect(record_close)
    manager = InfoBarManager.make(InfoBarPosition.TOP_RIGHT)

    assert bar in manager.infoBars[shell]

    application_signals.aboutToQuit.emit()

    assert binding.parent() is shell
    assert lifecycle.is_shutdown is True
    assert closed_count == 1
    assert bar not in manager.infoBars[shell]
    assert isValid(manager.aniGroups[shell])

    destroy_qt_object(shell)


def test_shell_destruction_remains_an_idempotent_reload_fallback(
    qt_application_owner: QApplication,
) -> None:
    """Destroying a shell must release resources without retaining its binding."""

    application_signals = _ApplicationSignalOwner()
    shell = QWidget()
    lifecycle = ShellResourceLifecycle()
    shutdown_events: list[str] = []
    lifecycle.register("probe", lambda: shutdown_events.append("shutdown"))
    binding = bind_shell_resource_lifecycle(
        application=cast(QApplication, application_signals),
        shell=shell,
        lifecycle=lifecycle,
    )

    destroy_qt_object(shell)
    application_signals.aboutToQuit.emit()

    assert not isValid(binding)
    assert lifecycle.is_shutdown is True
    assert shutdown_events == ["shutdown"]

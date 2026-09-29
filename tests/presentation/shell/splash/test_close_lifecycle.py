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

"""Keep native window closure and owner dismissal semantically distinct."""

from __future__ import annotations

import pytest

from substitute.app.bootstrap.launch_splash_client import InProcessLaunchSplashClient

from substitute.presentation.shell.splash_window import SplashWindow
from tests.support.qt.lifecycle import destroy_qt_object


@pytest.mark.parametrize("origin", ["window", "titlebar", "owner"])
def test_every_user_close_cancels_once_and_owner_dismissal_never_cancels(
    origin: str,
) -> None:
    """Preserve cancellation for native Close while readiness dismissal stays silent."""

    splash = SplashWindow(backdrop_mode=None, defer_animation_until_first_paint=True)
    cancellations: list[bool] = []
    splash.cancelRequested.connect(lambda: cancellations.append(True))
    try:
        splash.show()
        if origin == "window":
            splash.close()
        elif origin == "titlebar":
            splash.titleBar.closeBtn.click()
        else:
            InProcessLaunchSplashClient(splash).close()
        assert not splash.isVisible()
        assert cancellations == ([] if origin == "owner" else [True])
        splash.close()
        assert cancellations == ([] if origin == "owner" else [True])
    finally:
        destroy_qt_object(splash)


def test_approved_nodepack_work_cannot_be_abandoned_by_closing_splash() -> None:
    """Hide cancellation during install while allowing owner dismissal."""

    splash = SplashWindow(backdrop_mode=None, defer_animation_until_first_paint=True)
    cancellations: list[bool] = []
    splash.cancelRequested.connect(lambda: cancellations.append(True))
    try:
        splash.show()
        splash.set_cancellation_enabled(False)

        assert not splash.titleBar.closeBtn.isVisible()
        assert not splash.close()
        assert splash.isVisible()
        assert cancellations == []

        splash.dismiss()
        assert not splash.isVisible()
        assert cancellations == []
    finally:
        destroy_qt_object(splash)

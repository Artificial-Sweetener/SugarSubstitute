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

"""Keep startup visible while an installed launcher awaits prior ownership."""

from __future__ import annotations

import logging
from collections.abc import MutableMapping

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.splash_session import (
    LauncherSplashSession,
    start_launcher_splash_session,
)


_HANDOFF_WAIT_TIMEOUT_SECONDS = 30.0
_LOGGER = logging.getLogger(__name__)


def wait_for_outgoing_supervisor(
    *,
    layout: InstallLayout,
    locale_override: str | None,
    environment: MutableMapping[str, str],
) -> LauncherSplashSession | None:
    """Show startup, then await only the exact supervisor being replaced."""

    splash_session = start_launcher_splash_session(
        layout=layout,
        locale_override=locale_override,
    )
    if splash_session is None:
        raise RuntimeError("The installed handoff could not present a startup surface.")
    from sugarsubstitute_shared.process_identity import (
        ProcessIdentityError,
        wait_for_process_exit,
    )
    from sugarsubstitute_shared.supervisor_handoff import consume_supervisor_handoff

    try:
        identity = consume_supervisor_handoff(environment)
    except (TypeError, ValueError):
        splash_session.close()
        raise
    if identity is None:
        return splash_session
    _LOGGER.info(
        "Waiting for outgoing application supervisor | owner_pid=%s | "
        "timeout_seconds=%s",
        identity.pid,
        _HANDOFF_WAIT_TIMEOUT_SECONDS,
    )
    try:
        wait_for_process_exit(
            identity,
            timeout_seconds=_HANDOFF_WAIT_TIMEOUT_SECONDS,
        )
    except ProcessIdentityError:
        _LOGGER.warning(
            "Outgoing application supervisor wait did not complete cleanly | "
            "owner_pid=%s",
            identity.pid,
            exc_info=True,
        )
    else:
        _LOGGER.info(
            "Outgoing application supervisor released ownership | owner_pid=%s",
            identity.pid,
        )
    return splash_session


__all__ = ["wait_for_outgoing_supervisor"]

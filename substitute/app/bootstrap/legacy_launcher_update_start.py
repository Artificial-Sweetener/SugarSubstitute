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

"""Start legacy launcher migration through the pre-runtime execution owner."""

from __future__ import annotations

import logging
from pathlib import Path

from substitute.app.bootstrap.standalone_long_lived_execution import (
    StandaloneLongLivedExecutionOwner,
)
from substitute.application.execution import (
    CancellationSource,
    DirectExecutionDispatcher,
    ExecutionContext,
    TaskIdentity,
)
from substitute.infrastructure.execution import LongLivedTaskHandle
from substitute.infrastructure.launcher_update import LegacyLauncherUpdateBridge


_LOGGER = logging.getLogger(__name__)


def start_legacy_launcher_update_bridge(
    *,
    install_root: Path,
) -> LongLivedTaskHandle[None]:
    """Run best-effort migration without occupying the Qt GUI thread."""

    def run_bridge(_cancellation: CancellationSource) -> None:
        try:
            LegacyLauncherUpdateBridge().run(install_root=install_root)
        except Exception:
            _LOGGER.warning(
                "Legacy launcher update bridge failed; it will retry next startup.",
                exc_info=True,
            )

    owner = StandaloneLongLivedExecutionOwner(dispatcher=DirectExecutionDispatcher())
    return owner.start(
        identity=TaskIdentity(
            request_id=1,
            domain="legacy_launcher_update",
        ),
        context=ExecutionContext(
            operation="migrate_legacy_launcher",
            reason="application_startup",
            lane="startup_io",
        ),
        work=run_bridge,
        thread_name="legacy-launcher-update",
    )


__all__ = ["start_legacy_launcher_update_bridge"]

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

"""Own launch election and automatic recovery of verified unavailable owners."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
)
from sugarsubstitute_shared.application_process_scope import ApplicationProcessScope
from launcher.sugarsubstitute_launcher.application_owner_recovery import (
    ApplicationOwnerRecovery,
)

_LOGGER = logging.getLogger(__name__)


class ApplicationElectionRecovery:
    """Keep exact owner proof through automatic recovery and launch re-election."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        process_arguments: Sequence[str],
        locale_override: str | None,
        elect: Callable[
            [InstallLayout, Sequence[str]], ApplicationInstanceBroker | None
        ],
        presentation_layout: InstallLayout | None = None,
        process_scope: ApplicationProcessScope | None = None,
    ) -> None:
        """Bind one launch request and its transient, endpoint-scoped recovery proof."""
        self._layout = layout
        self._arguments = tuple(process_arguments)
        self._locale = locale_override
        self._elect = elect
        self._presentation_layout = presentation_layout
        self._process_scope = process_scope

    def run(self) -> ApplicationInstanceBroker | None:
        """Retire unavailable owners once before presenting an unrecovered failure."""
        recovery = ApplicationOwnerRecovery(
            self._layout, process_scope=self._process_scope
        )
        while True:
            recovery.begin_attempt()
            try:
                return self._elect(self._layout, self._arguments)
            except ApplicationInstanceBrokerError as error:
                _LOGGER.exception(
                    "Active application instance could not present a usable surface",
                    extra={"owner_process_id": error.owner_process_id},
                )
                from launcher.sugarsubstitute_launcher import launcher_ui_supervision

                if recovery.recover(error):
                    continue
                action = launcher_ui_supervision.supervise_instance_recovery_window(
                    layout=self._layout,
                    locale_override=self._locale,
                    reason=error.reason,
                    bundle_layout=self._presentation_layout,
                )
                if action is InstanceRecoveryAction.EXIT:
                    return None

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

"""Own launch election and verified recovery authority across user retries."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import logging
from pathlib import Path
import sys

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.instance_recovery_contract import (
    InstanceRecoveryAction,
)
from sugarsubstitute_shared.application_instance_broker import ApplicationInstanceBroker
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
)

_LOGGER = logging.getLogger(__name__)


class ApplicationElectionRecovery:
    """Keep authenticated owner proof for one interactive launch-recovery sequence."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        process_arguments: Sequence[str],
        locale_override: str | None,
        elect: Callable[
            [InstallLayout, Sequence[str]], ApplicationInstanceBroker | None
        ],
    ) -> None:
        """Bind one launch request and its transient, endpoint-scoped recovery proof."""
        self._layout = layout
        self._arguments = tuple(process_arguments)
        self._locale = locale_override
        self._elect = elect
        self._verified_failure: ApplicationInstanceBrokerError | None = None

    def run(self) -> ApplicationInstanceBroker | None:
        """Elect or offer recovery until this launch succeeds or the user exits."""
        self._verified_failure = None
        while True:
            try:
                return self._elect(self._layout, self._arguments)
            except ApplicationInstanceBrokerError as error:
                _LOGGER.exception(
                    "Active application instance could not present a usable surface",
                    extra={"owner_process_id": error.owner_process_id},
                )
                from launcher.sugarsubstitute_launcher import launcher_ui_supervision

                self._observe_failure(error)
                proof = self._verified_failure
                action = launcher_ui_supervision.supervise_instance_recovery_window(
                    layout=self._layout,
                    locale_override=self._locale,
                    can_end_owner=proof is not None,
                )
                if action is InstanceRecoveryAction.EXIT:
                    return None
                if action is InstanceRecoveryAction.END_AND_RETRY and proof is not None:
                    from launcher.sugarsubstitute_launcher import (
                        application_instance_recovery,
                    )

                    if application_instance_recovery.terminate_verified_instance_owner(
                        proof,
                        expected_executable=Path(sys.executable),
                    ):
                        self._verified_failure = None

    def _observe_failure(self, error: ApplicationInstanceBrokerError) -> None:
        """Retain same-endpoint proof when a subsequent connection cannot authenticate."""
        prior = self._verified_failure
        if error.endpoint is None or (
            prior is not None and prior.endpoint != error.endpoint
        ):
            self._verified_failure = None
        if error.endpoint is not None and error.owner_identity is not None:
            self._verified_failure = error

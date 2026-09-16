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

"""Apply one verified-owner retirement policy to launch and setup admission."""

from __future__ import annotations
import logging
from pathlib import Path
import sys
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInstanceFailureReason,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    ProcessIdentityError,
    wait_for_process_exit,
)
from sugarsubstitute_shared.application_process_scope import (
    ApplicationProcessScope,
    ExactExecutableProcessScope,
)

_LOGGER = logging.getLogger(__name__)


class ApplicationOwnerRecovery:
    """Retain endpoint proof and one retirement attempt per native incarnation."""

    def __init__(
        self,
        layout: InstallLayout,
        *,
        process_scope: ApplicationProcessScope | None = None,
    ) -> None:
        """Scope recovery evidence to one admission operation and installation."""
        self._layout = layout
        self._process_scope = process_scope
        self._verified_failure: ApplicationInstanceBrokerError | None = None
        self._attempted: set[ProcessIdentity] = set()

    def recover(self, error: ApplicationInstanceBrokerError) -> bool:
        """Permit re-election only after verified exit or authorized retirement."""
        self._observe_failure(error)
        proof = self._verified_failure
        identity = (
            proof.owner_identity if proof is not None else self._discover_owner(error)
        )
        if identity is None or identity in self._attempted:
            return False
        if error.reason is not ApplicationInstanceFailureReason.UNAVAILABLE:
            if not self._owner_has_exited(identity):
                return False
        else:
            self._attempted.add(identity)
            if not self._retire_owner(identity):
                return False
        self._attempted.add(identity)
        self._verified_failure = None
        return True

    @staticmethod
    def _owner_has_exited(identity: ProcessIdentity) -> bool:
        """Discard obsolete session failures only after native incarnation exit proof."""
        try:
            wait_for_process_exit(identity, timeout_seconds=0)
        except ProcessIdentityError:
            _LOGGER.debug(
                "Session-inaccessible owner exit was not established | owner_pid=%s",
                identity.pid,
                exc_info=True,
            )
            return False
        _LOGGER.info(
            "Session-inaccessible owner exited; repeating election | owner_pid=%s",
            identity.pid,
        )
        return True

    def _retire_owner(self, identity: ProcessIdentity) -> bool:
        """Delegate exact native retirement without exposing process controls."""
        from launcher.sugarsubstitute_launcher import application_instance_recovery
        from launcher.sugarsubstitute_launcher.application_process_discovery import (
            InstalledInvocationScope,
        )
        from sugarsubstitute_shared.application_instance_election import (
            application_instance_endpoints,
        )

        failure = self._verified_failure
        native_owner = failure.native_owner if failure is not None else None
        scope = self._process_scope
        if (
            scope is None
            and native_owner is not None
            and (
                native_owner.identity == identity
                and native_owner.endpoint
                in application_instance_endpoints(self._layout.root)
            )
        ):
            scope = ExactExecutableProcessScope((native_owner.executable,))

        return application_instance_recovery.terminate_verified_process(
            identity,
            scope=scope
            or (
                InstalledInvocationScope(self._layout)
                if bool(getattr(sys, "frozen", False))
                else ExactExecutableProcessScope((Path(sys.executable),))
            ),
        )

    def _discover_owner(
        self, error: ApplicationInstanceBrokerError
    ) -> ProcessIdentity | None:
        """Inspect earlier installed Windows processes only for this failed endpoint."""
        from launcher.sugarsubstitute_launcher.application_process_discovery import (
            discover_previous_installed_instance,
        )

        return discover_previous_installed_instance(self._layout, error.endpoint)

    def _observe_failure(self, error: ApplicationInstanceBrokerError) -> None:
        """Retain same-endpoint proof when a subsequent connection cannot authenticate."""
        prior = self._verified_failure
        if error.endpoint is None or (
            prior is not None and prior.endpoint != error.endpoint
        ):
            self._verified_failure = None
        if error.endpoint is not None and error.owner_identity is not None:
            self._verified_failure = error

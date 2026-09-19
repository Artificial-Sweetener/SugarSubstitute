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

"""Reserve a setup target using the launcher's verified-owner recovery policy."""

from collections.abc import Callable
import logging
from pathlib import Path

from launcher.sugarsubstitute_launcher.application_owner_recovery import (
    ApplicationOwnerRecovery,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_instance_election import (
    ApplicationInstanceReservation,
    reserve_application_instance,
)
from sugarsubstitute_shared.application_instance_protocol import (
    ApplicationInstanceBrokerError,
    ApplicationInvocation,
)

_LOGGER = logging.getLogger(__name__)


def reserve_selected_installation(
    install_root: Path,
    invocation: ApplicationInvocation,
    on_activity: Callable[[], None],
) -> ApplicationInstanceReservation | None:
    """Retire verified unavailable owners without opening a lease-management surface.

    Report actual election/recovery transitions to the waiting setup worker. A
    disconnected requester cannot start another attempt; ordinary supervisor
    lifetime still owns every successful reservation.
    """
    recovery = ApplicationOwnerRecovery(InstallLayout.from_root(install_root))
    while True:
        on_activity()
        recovery.begin_attempt()
        try:
            return reserve_application_instance(install_root, invocation)
        except ApplicationInstanceBrokerError as error:
            _LOGGER.warning(
                "Selected installation owner could not present a usable surface",
                extra={"owner_process_id": error.owner_process_id},
                exc_info=True,
            )
            on_activity()
            if not recovery.recover(error):
                raise

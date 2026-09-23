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

"""Mirror accepted shell readiness to the installer qualification observer."""

from __future__ import annotations

from collections.abc import Mapping
import logging

from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    publish_application_readiness_receipt,
)
from sugarsubstitute_shared.installer_qualification import InstallerQualificationPlan


_LOGGER = logging.getLogger(__name__)


def publish_qualification_receipt(
    *,
    environment: Mapping[str, str],
    receipt: ApplicationReadinessReceipt,
    attester_pids: tuple[int, ...],
) -> None:
    """Mirror a validated surface without coupling qualification to supervision."""

    try:
        plan = InstallerQualificationPlan.from_environment(environment)
        if plan is None:
            return
        publish_application_readiness_receipt(
            receipt_path=plan.readiness_receipt_path,
            receipt=ApplicationReadinessReceipt(
                pid=receipt.pid,
                token=plan.token,
                surface=receipt.surface,
                parent_pid=receipt.parent_pid,
                milestones=receipt.milestones,
                attester_pids=attester_pids,
            ),
        )
    except (OSError, ValueError) as error:
        _LOGGER.warning(
            "Could not publish installer qualification readiness | "
            "error_type=%s | error=%s",
            type(error).__name__,
            error,
        )


__all__ = ["publish_qualification_receipt"]

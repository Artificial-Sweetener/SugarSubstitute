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

"""Prepare immutable repair artifacts within the parent's native process family."""

from collections.abc import Sequence
import logging
from pathlib import Path

from launcher.sugarsubstitute_launcher.repair_process_channel import (
    RepairProcessChannel,
)

_LOGGER = logging.getLogger(__name__)


def run_repair_preparation_invocation(arguments: Sequence[str]) -> int | None:
    """Accept one private preparation only with a supervisor control capability."""
    prefix = "--repair-preparation-input="
    values = [
        argument.removeprefix(prefix)
        for argument in arguments
        if argument.startswith(prefix)
    ]
    if not values:
        return None
    if len(arguments) != 1 or len(values) != 1 or not values[0]:
        raise ValueError("Repair preparation requires exactly one input path.")
    with RepairProcessChannel.connect() as output:
        try:
            from launcher.sugarsubstitute_launcher.application.repair.preparation_service import (
                RepairPreparationService,
            )
            from launcher.sugarsubstitute_launcher.repair_preparation_invocation import (
                RepairPreparationInvocation,
            )
            from launcher.sugarsubstitute_launcher.repair_preparation_messages import (
                preparation_progress_to_message,
            )

            invocation = RepairPreparationInvocation.load(Path(values[0]))
            preparation = RepairPreparationService(
                progress_observer=lambda progress: output.send(
                    preparation_progress_to_message(progress)
                )
            ).prepare_bound_application_repair(
                layout=invocation.layout,
                release_source=invocation.source.source,
                scope=invocation.scope,
            )
        except Exception as error:
            _LOGGER.exception("Supervised repair preparation failed")
            output.send({"kind": "failed", "details": str(error)[:4096]})
            return 1
        output.send(
            {
                "kind": "succeeded",
                "version": preparation.request.version,
                "preparation_id": preparation.request.preparation_id,
            }
        )
        return 0

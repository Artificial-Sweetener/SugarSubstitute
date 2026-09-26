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

"""Execute prepared repair inside a parent-owned, Qt-free worker process."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from pathlib import Path

from launcher.sugarsubstitute_launcher.repair_execution_progress import (
    repair_progress_to_message,
)

from launcher.sugarsubstitute_launcher.repair_process_channel import (
    RepairProcessChannel,
)

_LOGGER = logging.getLogger(__name__)


def run_repair_execution_invocation(arguments: Sequence[str]) -> int | None:
    """Accept one private request only when an execution-control capability exists."""
    prefix = "--repair-worker-request="
    values = [
        argument.removeprefix(prefix)
        for argument in arguments
        if argument.startswith(prefix)
    ]
    if not values:
        return None
    if len(arguments) != 1 or len(values) != 1 or not values[0]:
        raise ValueError("Repair execution requires exactly one request path.")
    with RepairProcessChannel.connect() as output:
        try:
            from launcher.sugarsubstitute_launcher.repair_helper import (
                run_prepared_repair,
            )

            result = run_prepared_repair(
                Path(values[0]),
                progress_observer=lambda progress: output.send(
                    repair_progress_to_message(progress)
                ),
                output_callback=output.output,
            )
        except Exception as error:
            _LOGGER.exception("Supervised repair execution failed")
            output.send({"kind": "failed", "details": str(error)[:4096]})
            return 1
        output.send(
            {
                "kind": "succeeded",
                "session_recovery": result.session_recovery.to_json(),
            }
        )
        return 0

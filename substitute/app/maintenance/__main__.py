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

"""Run one bounded maintenance command through the installed app runtime."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from substitute.app.maintenance.owned_nodes import OwnedNodeMaintenanceService
from substitute.app.maintenance.full_managed_comfy import (
    FullManagedComfyMaintenanceService,
)
from substitute.app.maintenance.session_recovery import SessionRecoveryService


def main(argv: Sequence[str] | None = None) -> int:
    """Parse and execute one explicit maintenance operation."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=(
            "repair-owned-nodes",
            "validate-owned-nodes",
            "stage-full-managed-comfy",
            "validate-full-managed-comfy",
            "provision-full-managed-comfy",
            "reconcile-session",
        ),
    )
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--install-root", type=Path)
    parser.add_argument("--session-dir", type=Path)
    parser.add_argument("--recovery-root", type=Path)
    parser.add_argument("--result-path", type=Path)
    arguments = parser.parse_args(argv)
    if arguments.operation == "reconcile-session":
        if any(
            value is None
            for value in (
                arguments.session_dir,
                arguments.recovery_root,
                arguments.result_path,
            )
        ):
            parser.error("reconcile-session requires session and recovery paths")
        SessionRecoveryService().reconcile(
            session_dir=arguments.session_dir,
            recovery_root=arguments.recovery_root,
            result_path=arguments.result_path,
        )
        return 0
    if arguments.workspace is None:
        parser.error(f"{arguments.operation} requires --workspace")
    service = OwnedNodeMaintenanceService()
    if arguments.operation == "repair-owned-nodes":
        service.repair(arguments.workspace)
    elif arguments.operation == "validate-owned-nodes":
        service.validate(arguments.workspace)
    elif arguments.operation == "stage-full-managed-comfy":
        if arguments.install_root is None:
            parser.error("stage-full-managed-comfy requires --install-root")
        FullManagedComfyMaintenanceService().stage(
            install_root=arguments.install_root,
            destination=arguments.workspace,
        )
    elif arguments.operation == "provision-full-managed-comfy":
        FullManagedComfyMaintenanceService().provision(arguments.workspace)
    else:
        FullManagedComfyMaintenanceService().validate(arguments.workspace)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True
    )
    raise SystemExit(main())


__all__ = ["main"]

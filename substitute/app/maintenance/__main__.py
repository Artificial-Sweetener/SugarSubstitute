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
from collections.abc import Sequence
from pathlib import Path

from substitute.app.maintenance.owned_nodes import OwnedNodeMaintenanceService
from substitute.app.maintenance.full_managed_comfy import (
    FullManagedComfyMaintenanceService,
)


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
        ),
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--install-root", type=Path)
    arguments = parser.parse_args(argv)
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
    else:
        FullManagedComfyMaintenanceService().validate(arguments.workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main"]

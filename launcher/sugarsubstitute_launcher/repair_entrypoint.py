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

"""Run the installed launcher directly in repair mode."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import sys
from pathlib import Path

_EXECUTE_PREFIX = "--execute-repair-request="


def repair_arguments(arguments: Sequence[str]) -> tuple[str, ...]:
    """Return caller arguments with the authoritative repair flag present once."""

    filtered = tuple(argument for argument in arguments if argument != "--repair")
    return ("--repair", *filtered)


def run_repair(
    launcher_main: Callable[[Sequence[str]], int] | None = None,
    prepared_runner: Callable[[Path], object] | None = None,
) -> int:
    """Enter the normal launcher route with repair selected explicitly."""

    execution_path = _execution_request_path(sys.argv[1:])
    if execution_path is not None:
        if prepared_runner is None:
            from launcher.sugarsubstitute_launcher.repair_helper import (
                run_prepared_repair,
            )

            prepared_runner = run_prepared_repair
        prepared_runner(execution_path)
        return 0
    if launcher_main is None:
        from launcher.sugarsubstitute_launcher.app import main

        launcher_main = main
    return launcher_main(repair_arguments(sys.argv[1:]))


def _execution_request_path(arguments: Sequence[str]) -> Path | None:
    """Extract one internal detached-execution request path."""

    values = tuple(
        argument.removeprefix(_EXECUTE_PREFIX)
        for argument in arguments
        if argument.startswith(_EXECUTE_PREFIX)
    )
    if not values:
        return None
    if len(values) != 1 or not values[0]:
        raise ValueError("Repair helper requires one non-empty request path.")
    if len(arguments) != 1:
        raise ValueError("Repair helper execution does not accept extra arguments.")
    return Path(values[0])


if __name__ == "__main__":
    raise SystemExit(run_repair())


__all__ = ["repair_arguments", "run_repair"]

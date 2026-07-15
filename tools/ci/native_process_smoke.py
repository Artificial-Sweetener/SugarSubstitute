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

"""Prove that a native GUI command reaches a stable event loop."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence


class NativeProcessSmokeError(RuntimeError):
    """Report a native process that exits before the smoke interval."""


def prove_process_stays_alive(
    command: Sequence[str],
    *,
    duration_seconds: float = 5.0,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Start a command, require it to remain alive, and terminate its process group."""

    if not command:
        raise ValueError("A native smoke command is required.")
    process_environment = dict(os.environ)
    if environment is not None:
        process_environment.update(environment)
    creation_flags = (
        subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    )
    process = subprocess.Popen(  # noqa: S603
        list(command),
        env=process_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        start_new_session=sys.platform != "win32",
        creationflags=creation_flags,
    )
    try:
        deadline = time.monotonic() + duration_seconds
        while time.monotonic() < deadline:
            return_code = process.poll()
            if return_code is not None:
                output = process.communicate(timeout=5)[0]
                raise NativeProcessSmokeError(
                    f"Native process exited early with code {return_code}: "
                    f"{' '.join(command)}\n{output}"
                )
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
    finally:
        _terminate_process_group(process)


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    """Terminate the complete smoke process group without leaving GUI children."""

    if process.poll() is not None:
        return
    if sys.platform == "win32":
        process.terminate()
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if sys.platform == "win32":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse a native command and execute its bounded smoke proof."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    environment = dict(item.split("=", maxsplit=1) for item in args.env)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    prove_process_stays_alive(
        command,
        duration_seconds=args.duration,
        environment=environment,
    )
    print(f"NATIVE_SMOKE_OK command={Path(command[0]).name}")
    return 0


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Return validated native-smoke command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(list(argv))
    if not args.command:
        parser.error("a command after -- is required")
    if any("=" not in item for item in args.env):
        parser.error("--env values must use KEY=VALUE")
    return args


if __name__ == "__main__":
    raise SystemExit(main())

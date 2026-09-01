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

"""Qualify real Crashpad capture and the idle handler resource ceiling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil  # type: ignore[import-untyped]


_DUMP_TIMEOUT_SECONDS = 10.0
_HANDLER_TIMEOUT_SECONDS = 10.0
_IDLE_SETTLE_SECONDS = 0.5
_IDLE_SAMPLE_SECONDS = 1.0
_MINIDUMP_MAGIC = b"MDMP"


def main(argv: list[str] | None = None) -> int:
    """Run destructive capture and bounded idle-footprint qualification."""

    arguments = _parse_arguments(argv)
    runtime = arguments.runtime_dir.expanduser().resolve()
    probe = arguments.probe.expanduser().resolve()
    artifact_dir = arguments.artifact_dir.expanduser().resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    handler, client = _runtime_files(runtime)
    _require_file(handler)
    _require_file(client)
    _require_file(probe)
    crash_evidence = _qualify_native_crash(
        probe=probe,
        handler=handler,
        client=client,
        artifact_dir=artifact_dir / "native-crash",
    )
    footprint = _qualify_idle_footprint(
        probe=probe,
        handler=handler,
        client=client,
        artifact_dir=artifact_dir / "idle",
    )
    evidence = {"native_crash": crash_evidence, "idle_handler": footprint}
    (artifact_dir / "evidence.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if footprint["rss_bytes"] > arguments.maximum_handler_rss_mib * 1024 * 1024:
        raise RuntimeError("Crashpad handler exceeded the idle RSS ceiling.")
    if footprint["cpu_seconds"] > arguments.maximum_idle_cpu_seconds:
        raise RuntimeError("Crashpad handler exceeded the idle CPU ceiling.")
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    """Parse explicit runtime, probe, evidence, and resource bounds."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--maximum-handler-rss-mib", type=float, default=32.0)
    parser.add_argument("--maximum-idle-cpu-seconds", type=float, default=0.1)
    return parser.parse_args(argv)


def _qualify_native_crash(
    *,
    probe: Path,
    handler: Path,
    client: Path,
    artifact_dir: Path,
) -> dict[str, int | str]:
    """Trigger one access violation and require a valid minidump."""

    database = artifact_dir / "database"
    metrics = artifact_dir / "metrics"
    database.mkdir(parents=True, exist_ok=True)
    metrics.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(  # noqa: S603
        [str(probe), str(client), str(handler), str(database), str(metrics)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        raise RuntimeError("Native qualification probe did not crash.")
    dump = _wait_for_dump(database)
    with dump.open("rb") as binary:
        if binary.read(len(_MINIDUMP_MAGIC)) != _MINIDUMP_MAGIC:
            raise RuntimeError("Crashpad output is not a valid minidump.")
    return {
        "exit_code": result.returncode,
        "minidump": str(dump.relative_to(artifact_dir)),
        "minidump_bytes": dump.stat().st_size,
    }


def _qualify_idle_footprint(
    *,
    probe: Path,
    handler: Path,
    client: Path,
    artifact_dir: Path,
) -> dict[str, int | float]:
    """Measure the handler after startup settles without application work."""

    database = artifact_dir / "database"
    metrics = artifact_dir / "metrics"
    database.mkdir(parents=True, exist_ok=True)
    metrics.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(  # noqa: S603
        [
            str(probe),
            str(client),
            str(handler),
            str(database),
            str(metrics),
            "--idle",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    probe_process = psutil.Process(process.pid)
    handler_process: psutil.Process | None = None
    try:
        handler_process = _wait_for_handler(probe_process)
        time.sleep(_IDLE_SETTLE_SECONDS)
        before = handler_process.cpu_times()
        time.sleep(_IDLE_SAMPLE_SECONDS)
        after = handler_process.cpu_times()
        cpu_seconds = (after.user + after.system) - (before.user + before.system)
        rss_bytes = handler_process.memory_info().rss
        return {
            "handler_pid": handler_process.pid,
            "rss_bytes": rss_bytes,
            "cpu_seconds": cpu_seconds,
            "sample_seconds": _IDLE_SAMPLE_SECONDS,
        }
    finally:
        _terminate_process(process)
        if handler_process is not None:
            _wait_for_handler_exit(handler_process)


def _wait_for_dump(database: Path) -> Path:
    """Return the single minidump emitted before the bounded deadline."""

    deadline = time.monotonic() + _DUMP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        dumps = tuple((database / "reports").glob("*.dmp"))
        if len(dumps) == 1:
            return dumps[0]
        if len(dumps) > 1:
            raise RuntimeError("Native qualification emitted multiple minidumps.")
        time.sleep(0.05)
    raise RuntimeError("Crashpad did not emit a minidump before the deadline.")


def _wait_for_handler(probe: psutil.Process) -> psutil.Process:
    """Return the Crashpad child process before the bounded deadline."""

    deadline = time.monotonic() + _HANDLER_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        for child in probe.children(recursive=True):
            try:
                if child.name().casefold().startswith("crashpad_handler"):
                    return child
            except psutil.Error:
                continue
        if not probe.is_running():
            raise RuntimeError("Idle qualification probe exited during startup.")
        time.sleep(0.05)
    raise RuntimeError("Crashpad handler did not start before the deadline.")


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Stop the bounded idle probe without leaving a child process behind."""

    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _wait_for_handler_exit(handler: psutil.Process) -> None:
    """Require the out-of-process handler to follow its client lifetime."""

    try:
        handler.wait(timeout=5)
    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
        if handler.is_running():
            handler.kill()
            raise RuntimeError("Crashpad handler outlived its qualification client.")


def _runtime_files(runtime: Path) -> tuple[Path, Path]:
    """Return platform-specific handler and bridge paths."""

    if sys.platform == "win32":
        return (
            runtime / "crashpad_handler.exe",
            runtime / "sugarsubstitute_crashpad_client.dll",
        )
    if sys.platform == "darwin":
        return (
            runtime / "crashpad_handler",
            runtime / "sugarsubstitute_crashpad_client.dylib",
        )
    return (
        runtime / "crashpad_handler",
        runtime / "sugarsubstitute_crashpad_client.so",
    )


def _require_file(path: Path) -> None:
    """Reject missing qualification inputs before process creation."""

    if not path.is_file():
        raise FileNotFoundError(path)


if __name__ == "__main__":
    raise SystemExit(main())

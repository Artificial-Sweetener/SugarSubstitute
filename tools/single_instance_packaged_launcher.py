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

"""Track one packaged invocation separately from its onefile Python runtime.

PyInstaller's Windows onefile parent extracts and waits; its child owns the
broker and kernel process families. Durable startup diagnostics preserve that
child's identity even when a forwarder exits before the observer can sample it.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import time

import psutil  # type: ignore[import-untyped]

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_identity_evidence import (
    LAUNCHER_PROCESS_EVENT,
    LauncherProcessEvidence,
)
from sugarsubstitute_shared.process_identity import (
    ProcessIdentity,
    capture_process_identity,
)


class PackagedLauncherProcess:
    """Keep bootstrap completion and incarnation-checked runtime control distinct."""

    def __init__(
        self,
        process: subprocess.Popen[bytes],
        layout: InstallLayout,
        *,
        output_path: Path | None = None,
    ) -> None:
        """Bind the launched bootstrap before reading any runtime log evidence."""
        self.bootstrap = process
        self.output_path = output_path
        self.bootstrap_identity = capture_process_identity(process.pid)
        self._layout = layout
        self._runtime_evidence: LauncherProcessEvidence | None = None

    @property
    def runtime_evidence(self) -> LauncherProcessEvidence:
        """Resolve exactly one same-image direct child of this bootstrap incarnation."""
        if self._runtime_evidence is not None:
            return self._runtime_evidence
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            completed = self.bootstrap.poll() is not None
            try:
                text = (self._layout.logs_dir / "launcher.log").read_text(
                    encoding="utf-8"
                )
            except FileNotFoundError:
                text = ""
            matches: set[LauncherProcessEvidence] = set()
            for line in text.splitlines():
                if LAUNCHER_PROCESS_EVENT not in line:
                    continue
                payload = line.split(LAUNCHER_PROCESS_EVENT, 1)[1]
                try:
                    evidence = LauncherProcessEvidence.from_json(json.loads(payload))
                except ValueError:
                    continue
                if evidence.parent_identity != self.bootstrap_identity:
                    continue
                validate_onefile_runtime(
                    evidence,
                    bootstrap=self.bootstrap_identity,
                    executable=self._layout.executable_path,
                )
                matches.add(evidence)
            if len(matches) > 1:
                raise AssertionError(
                    f"Multiple runtimes for bootstrap {self.bootstrap_identity}: {matches}"
                )
            if matches:
                self._runtime_evidence = matches.pop()
                return self._runtime_evidence
            if completed:
                # Observe exit before reading: the completed runtime flushed its record.
                raise AssertionError(
                    f"Launcher {self.bootstrap_identity} exited without runtime identity"
                )
            time.sleep(0.05)
        raise TimeoutError(
            f"No runtime identity for bootstrap {self.bootstrap_identity}"
        )

    @property
    def runtime_pid(self) -> int:
        """Return the broker/requester PID, never the extraction bootstrap PID."""
        return self.runtime_evidence.identity.pid

    @property
    def returncode(self) -> int | None:
        """Report the invocation result propagated by PyInstaller's parent."""
        return self.bootstrap.returncode

    def poll(self) -> int | None:
        """Observe completion of the whole invocation, including extraction cleanup."""
        return self.bootstrap.poll()

    def wait(self, timeout: float | None = None) -> int:
        """Wait for the bootstrap to propagate the runtime's exit status."""
        return self.bootstrap.wait(timeout=timeout)

    def kill(self) -> None:
        """Crash the captured broker runtime without touching any reused PID."""
        self._signal_runtime(kill=True)

    def terminate(self) -> None:
        """Terminate the captured runtime while allowing bootstrap cleanup."""
        self._signal_runtime(kill=False)

    def _signal_runtime(self, *, kill: bool) -> None:
        """Require the recorded incarnation and image immediately before signalling."""
        evidence = self.runtime_evidence
        try:
            process = psutil.Process(evidence.identity.pid)
            if float(
                process.create_time()
            ) != evidence.identity.created_at or _path_key(process.exe()) != _path_key(
                evidence.executable
            ):
                raise AssertionError(
                    "Launcher runtime identity changed before termination"
                )
            if kill:
                process.kill()
            else:
                process.terminate()
        except psutil.NoSuchProcess:
            # The outer process may still be deleting its extraction directory.
            return

    def cleanup(self) -> None:
        """Reap owned handles even if bootstrap failed before diagnostic setup."""
        if self.poll() is not None:
            return
        try:
            self.terminate()
        except (AssertionError, TimeoutError, OSError, psutil.Error):
            logging.getLogger(__name__).warning(
                "Runtime cleanup unavailable; terminating owned bootstrap handle",
                exc_info=True,
            )
            try:
                self.bootstrap.terminate()
            except OSError:
                logging.getLogger(__name__).warning(
                    "Owned bootstrap termination failed", exc_info=True
                )
        try:
            self.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            try:
                self.bootstrap.kill()
                self.wait(timeout=5.0)
            except (OSError, subprocess.TimeoutExpired):
                logging.getLogger(__name__).warning(
                    "Owned bootstrap cleanup failed", exc_info=True
                )
        except OSError:
            logging.getLogger(__name__).warning(
                "Owned bootstrap wait failed", exc_info=True
            )


def validate_onefile_runtime(
    evidence: LauncherProcessEvidence,
    *,
    bootstrap: ProcessIdentity,
    executable: Path,
) -> None:
    """Reject unrelated images, stale parents, impossible ancestry, and PID reuse."""
    expected_image = _path_key(str(executable))
    if (
        evidence.parent_identity != bootstrap
        or evidence.identity.pid == bootstrap.pid
        or evidence.identity.created_at < bootstrap.created_at
        or _path_key(evidence.executable) != expected_image
        or _path_key(evidence.parent_executable) != expected_image
    ):
        raise AssertionError(f"Invalid onefile runtime relationship: {evidence}")


def _path_key(value: str) -> str:
    """Compare executable paths under the host's filesystem casing rules."""
    return os.path.normcase(str(Path(value).resolve()))

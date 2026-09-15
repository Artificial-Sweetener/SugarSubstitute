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

"""Qualify packaged Windows installer interruption and visible resumption."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

import psutil  # type: ignore[import-untyped]

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout  # noqa: E402
from tools.ci.candidate_release_source import (  # noqa: E402
    candidate_release_source,
    trust_candidate_source,
)
from tools.ci.current_installer_execution import run_current_installer_ui  # noqa: E402
from tools.ci.external_comfy_readiness_server import (  # noqa: E402
    ExternalComfyReadinessServer,
)
from tools.ci.installer_ui_qualification import (  # noqa: E402
    prepare_qualification_evidence,
    verify_main_shell_evidence,
)
from tools.ci.owned_process_runner import terminate_owned_process_tree  # noqa: E402

_POLL_INTERVAL_SECONDS = 0.05


def main(argv: Sequence[str] | None = None) -> int:
    """Interrupt one packaged install, resume it, and write durable evidence."""

    arguments = _parse_args(sys.argv[1:] if argv is None else argv)
    result = qualify_installer_interruption(
        installer_path=arguments.installer.resolve(),
        release_root=arguments.release_root.resolve(),
        install_root=arguments.install_root.resolve(),
        expected_version=arguments.expected_version,
        timeout_seconds=arguments.timeout_seconds,
    )
    report_path = arguments.artifact_dir.resolve() / "installer-interruption.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(report_path)
    return 0


def qualify_installer_interruption(
    *,
    installer_path: Path,
    release_root: Path,
    install_root: Path,
    expected_version: str,
    timeout_seconds: float,
) -> dict[str, object]:
    """Close during payload installation and prove the same root resumes safely."""

    if os.name != "nt":
        raise RuntimeError("Installer interruption qualification requires Windows.")
    if install_root.exists() and any(install_root.iterdir()):
        raise RuntimeError(f"Qualification root is not empty: {install_root}")
    deadline = time.monotonic() + timeout_seconds
    with ExternalComfyReadinessServer() as external_comfy:
        with candidate_release_source(
            release_root=release_root,
            manifest_url=None,
            certificate_root=install_root.parent / ".interruption-certificate",
        ) as source:
            if source.manifest_url is None:
                raise RuntimeError("Candidate release server omitted its manifest URL.")
            interrupted = _interrupt_initial_install(
                installer_path=installer_path,
                install_root=install_root,
                expected_version=expected_version,
                endpoint_port=external_comfy.port,
                manifest_url=source.manifest_url,
                source=source,
                timeout_seconds=_remaining(deadline, "interrupted install"),
            )
            resumed = prepare_qualification_evidence(
                install_root=install_root,
                expected_version=expected_version,
                endpoint_port=external_comfy.port,
                phase="interruption-resume",
                timeout_seconds=_remaining(deadline, "resume preparation"),
                target_mode="remote",
            )
            trust_candidate_source(resumed.environment, source)
            run_current_installer_ui(
                installer_path=installer_path,
                install_root=install_root,
                manifest_url=source.manifest_url,
                environment=resumed.environment,
                timeout_seconds=_remaining(deadline, "resumed installer"),
            )
            verify_main_shell_evidence(
                install_root=install_root,
                expected_version=expected_version,
                evidence=resumed,
                required_qualification_events=(),
                timeout_seconds=_remaining(deadline, "resumed main shell"),
            )
            external_comfy.require_qualification_probes()
    return {
        "result": "passed",
        "interrupted_install": interrupted,
        "resumed_to_main_shell": True,
        "installed_version": expected_version,
    }


def _interrupt_initial_install(
    *,
    installer_path: Path,
    install_root: Path,
    expected_version: str,
    endpoint_port: int,
    manifest_url: str,
    source: Any,
    timeout_seconds: float,
) -> dict[str, object]:
    """Request a real window close after the production Install action begins."""

    evidence = prepare_qualification_evidence(
        install_root=install_root,
        expected_version=expected_version,
        endpoint_port=endpoint_port,
        phase="interruption",
        timeout_seconds=timeout_seconds,
        target_mode="remote",
    )
    trust_candidate_source(evidence.environment, source)
    environment = dict(evidence.environment)
    environment.pop("QT_QPA_PLATFORM", None)
    output_path = install_root.parent / f".{install_root.name}-interruption-output.log"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)
    with output_path.open("wb") as output:
        process = subprocess.Popen(  # noqa: S603
            [
                str(installer_path),
                f"--install-root={install_root}",
                f"--manifest-url={manifest_url}",
            ],
            cwd=installer_path.parent,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    try:
        deadline = time.monotonic() + timeout_seconds
        _wait_for_event(
            evidence.event_log_path,
            token=evidence.token,
            event="installer.install.clicked",
            process=process,
            deadline=deadline,
        )
        window_pid = _close_setup_window(process.pid, deadline=deadline)
        launcher_log = InstallLayout.from_root(install_root).logs_dir / "launcher.log"
        _wait_for_log_line(
            launcher_log,
            "Installer close deferred to a safe boundary",
            process=process,
            deadline=deadline,
        )
        return_code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        if return_code != 0:
            raise RuntimeError(f"Interrupted installer exited with {return_code}.")
        log_text = launcher_log.read_text(encoding="utf-8", errors="replace")
        if "Installer reached its requested safe close boundary" not in log_text:
            raise RuntimeError("Installer did not report its safe close boundary.")
        events = _events(evidence.event_log_path, token=evidence.token)
        if "installer.onboarding.handoff" in events:
            raise RuntimeError("Close request still launched onboarding.")
        return {
            "close_requested_after_install_action": True,
            "close_deferred_while_worker_active": True,
            "safe_boundary_observed": True,
            "onboarding_handoff_prevented": True,
            "installer_exit_code": return_code,
            "window_process_id": window_pid,
        }
    except Exception:
        if process.poll() is None:
            terminate_owned_process_tree(process.pid)
        raise


def _close_setup_window(owner_pid: int, *, deadline: float) -> int:
    """Close the visible setup window belonging to the owned process tree."""

    from pywinauto import Desktop  # type: ignore[import-untyped]

    while time.monotonic() < deadline:
        process_ids = _process_tree_ids(owner_pid)
        windows = Desktop(backend="uia").windows(
            title="SugarSubstitute Setup",
            visible_only=True,
        )
        for window in windows:
            window_pid = int(window.element_info.process_id)
            if window_pid not in process_ids:
                continue
            window.close()
            return window_pid
        if not psutil.pid_exists(owner_pid):
            raise RuntimeError("Installer exited before its window could be closed.")
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise TimeoutError("Could not find the packaged setup window to close.")


def _process_tree_ids(owner_pid: int) -> frozenset[int]:
    """Return stable current identifiers for one explicitly owned process tree."""

    try:
        root = psutil.Process(owner_pid)
        return frozenset(
            {owner_pid, *(child.pid for child in root.children(recursive=True))}
        )
    except psutil.NoSuchProcess:
        return frozenset()


def _wait_for_event(
    path: Path,
    *,
    token: str,
    event: str,
    process: subprocess.Popen[bytes],
    deadline: float,
) -> None:
    """Wait until the owned qualification journal contains one exact event."""

    while time.monotonic() < deadline:
        if event in _events(path, token=token):
            return
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"Installer exited with {return_code} before event {event!r}."
            )
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Installer did not record {event!r} before the deadline.")


def _events(path: Path, *, token: str) -> tuple[str, ...]:
    """Read valid event names belonging to one qualification identity."""

    if not path.is_file():
        return ()
    events: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("token") == token and isinstance(payload.get("event"), str):
            events.append(payload["event"])
    return tuple(events)


def _wait_for_log_line(
    path: Path,
    expected: str,
    *,
    process: subprocess.Popen[bytes],
    deadline: float,
) -> None:
    """Wait for one durable installer lifecycle diagnostic."""

    while time.monotonic() < deadline:
        if path.is_file() and expected in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            return
        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"Installer exited with {return_code} before logging {expected!r}."
            )
        time.sleep(_POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Installer did not log {expected!r} before the deadline.")


def _remaining(deadline: float, phase: str) -> float:
    """Return a positive remainder from the shared qualification deadline."""

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError(f"Qualification deadline expired before {phase}.")
    return remaining


def _positive_float(value: str) -> float:
    """Parse one positive duration argument."""

    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Duration must be positive.")
    return parsed


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse packaged installer interruption qualification arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=_positive_float, default=3_600.0)
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())

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

"""Require the installed root to acknowledge a candidate's painted app."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Protocol

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from sugarsubstitute_shared.application_readiness import ApplicationReadinessReceipt
from launcher.sugarsubstitute_launcher.process_identity_evidence import (
    LAUNCHER_PROCESS_EVENT,
    LauncherProcessEvidence,
)
from sugarsubstitute_shared.launcher_update.bundle_paths import LauncherBundlePaths
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.windows_long_paths import logical_path, operational_path
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


_ACCEPTANCE = re.compile(
    r"process=(?P<supervisor>\d+) .*?"
    r"application_readiness_supervisor Accepted painted application surface \| "
    r"candidate_pid=(?P<candidate>\d+) \| "
    r"surface_pid=(?P<surface>\d+) \| surface=main_shell \| "
    r"outer_contract=(?P<outer>True|False)"
)


class _LaunchBaseline(Protocol):
    """Expose the log offsets captured immediately before candidate launch."""

    @property
    def progress_baselines(
        self,
    ) -> tuple[tuple[Path, tuple[bool, int]], ...]:
        """Return pre-launch path existence and byte lengths."""


def assert_candidate_root_readiness(
    *,
    install_root: Path,
    candidate_launch: _LaunchBaseline,
    readiness_path: Path,
    event_log_path: Path,
    token: str,
) -> None:
    """Bind the painted process to an attested installed-root acknowledgement."""

    try:
        receipt = ApplicationReadinessReceipt.from_json(
            json.loads(readiness_path.read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise InstallerLifecycleError(
            "Candidate main-shell receipt is unavailable after launch."
        ) from error
    if receipt.token != token:
        raise InstallerLifecycleError(
            "Candidate main-shell receipt is from another launch."
        )
    assert_root_main_shell_acknowledgement(
        install_root=install_root,
        candidate_launch=candidate_launch,
        surface_pid=receipt.pid,
        event_log_path=event_log_path,
        token=token,
        attester_pids=receipt.attester_pids,
    )


def assert_root_main_shell_acknowledgement(
    *,
    install_root: Path,
    candidate_launch: _LaunchBaseline,
    surface_pid: int,
    event_log_path: Path,
    token: str,
    attester_pids: tuple[int, ...],
) -> None:
    """Accept a delegated root or a directly launched, attested installed root."""

    log_path = install_root / "launcher" / "logs" / "launcher.log"
    baseline = next(
        (
            signature[1]
            for path, signature in candidate_launch.progress_baselines
            if path.resolve() == log_path.resolve()
        ),
        None,
    )
    if baseline is None:
        raise InstallerLifecycleError("Launcher log baseline is missing.")
    try:
        raw_log = log_path.read_bytes()
    except OSError as error:
        raise InstallerLifecycleError(
            "Launcher readiness log is unreadable."
        ) from error
    if baseline > len(raw_log):
        raise InstallerLifecycleError("Launcher readiness log was truncated.")
    lines = raw_log[baseline:].decode("utf-8", errors="replace").splitlines()
    records = [
        (index, match)
        for index, line in enumerate(lines)
        if (match := _ACCEPTANCE.search(line)) is not None
        and int(match.group("surface")) == surface_pid
    ]
    observations, inconsistent = _process_observations(lines)
    layout = InstallLayout.from_root(install_root)
    root_executable = layout.executable_path.resolve()
    selected_supervisors = {
        int(record.group("supervisor"))
        for _index, record in records
        if record.group("outer") == "True"
    }
    delegated_root_accepted = any(
        record.group("outer") == "False"
        and (
            (
                not selected_supervisors
                and int(record.group("candidate")) not in attester_pids
            )
            or int(record.group("candidate")) in selected_supervisors
        )
        and _direct_delegation_agrees(
            observations, inconsistent, records, index, record, layout
        )
        for index, record in records
    )
    if delegated_root_accepted:
        return

    startup_images = _attested_startup_images(
        event_log_path=event_log_path,
        token=token,
        attester_pids=attester_pids,
    )
    if _onefile_root_acknowledged(
        layout=layout,
        observations=observations,
        inconsistent=inconsistent,
        records=records,
        attester_pids=attester_pids,
        startup_images=startup_images,
    ):
        return
    direct_root_supervisors = {
        pid
        for pid, images in startup_images.items()
        if images == {root_executable} and pid not in inconsistent
    }
    direct_root_accepted = any(
        record.group("outer") == "True"
        and int(record.group("supervisor")) in direct_root_supervisors
        and _direct_root_identity_agrees(
            observations, int(record.group("supervisor")), index, root_executable
        )
        for index, record in records
    )
    if not direct_root_accepted:
        raise InstallerLifecycleError(
            "Installed launcher root did not accept the candidate main shell."
        )


def _attested_startup_images(
    *,
    event_log_path: Path,
    token: str,
    attester_pids: tuple[int, ...],
) -> dict[int, set[Path]]:
    """Bind launch images to the fresh qualification token and receipt attesters."""

    try:
        events = event_log_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise InstallerLifecycleError(
            "Candidate launcher startup event log is unreadable."
        ) from error
    images: dict[int, set[Path]] = {}
    for line in events:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if (
            event.get("event") != "launcher.startup.resolved"
            or event.get("token") != token
        ):
            continue
        pid = event.get("pid")
        fields = event.get("fields")
        if (
            not isinstance(pid, int)
            or isinstance(pid, bool)
            or pid not in attester_pids
        ):
            continue
        if not isinstance(fields, dict):
            continue
        invocation_path = fields.get("invocation_path")
        if not isinstance(invocation_path, str):
            continue
        invocation = _absolute_image(invocation_path)
        if invocation is not None:
            images.setdefault(pid, set()).add(invocation)
    return images


@dataclass(frozen=True, slots=True)
class _ProcessObservation:
    """Bind one complete process diagnostic to its position in the fresh log."""

    line: int
    evidence: LauncherProcessEvidence


def _onefile_root_acknowledged(
    *,
    layout: InstallLayout,
    observations: list[_ProcessObservation],
    inconsistent: set[int],
    records: list[tuple[int, re.Match[str]]],
    attester_pids: tuple[int, ...],
    startup_images: dict[int, set[Path]],
) -> bool:
    """Join the root's bootstrap child to its attested same-image Python runtime.

    A parent PID alone is insufficient: both runtimes need fresh, unambiguous
    kernel-identity diagnostics before their own acceptance records. The receipt
    must attest the ordered runtime/bootstrap/root chain, and the selected image
    must also be named by this launch's token-bound startup event.
    """
    if len(set(attester_pids)) != len(attester_pids):
        return False
    root_image = layout.executable_path.resolve()
    for root_line, root_record in records:
        if root_record.group("outer") != "False":
            continue
        root_pid = int(root_record.group("supervisor"))
        bootstrap_pid = int(root_record.group("candidate"))
        root = _unique_process(observations, root_pid, root_line)
        if root is None or _absolute_image(root.executable) != root_image:
            continue
        if root_pid in startup_images and startup_images[root_pid] != {root_image}:
            continue
        for selected_line, selected_record in records:
            if selected_record.group("outer") != "True":
                continue
            selected_pid = int(selected_record.group("supervisor"))
            chain = (selected_pid, bootstrap_pid, root_pid)
            if any(pid in inconsistent for pid in (*chain, root.parent_identity.pid)):
                continue
            if not any(
                attester_pids[index : index + 3] == chain
                for index in range(len(attester_pids))
            ):
                continue
            selected = _unique_process(observations, selected_pid, selected_line)
            if selected is None or selected.parent_identity.pid != bootstrap_pid:
                continue
            image = _absolute_image(selected.executable)
            if image is None or _absolute_image(selected.parent_executable) != image:
                continue
            if not _is_generation_launcher_image(layout, image):
                continue
            if startup_images.get(selected_pid) != {image}:
                continue
            if (
                not root.identity.created_at
                <= selected.parent_identity.created_at
                <= selected.identity.created_at
            ):
                continue
            children = {
                observation.evidence.identity.pid
                for observation in observations
                if observation.evidence.parent_identity.pid == bootstrap_pid
            }
            if children != {selected_pid}:
                continue
            return True
    return False


def _direct_delegation_agrees(
    observations: list[_ProcessObservation],
    inconsistent: set[int],
    records: list[tuple[int, re.Match[str]]],
    root_line: int,
    root_record: re.Match[str],
    layout: InstallLayout,
) -> bool:
    """Keep old direct-child proofs but reject contradictory new diagnostics."""
    root_image = layout.executable_path.resolve()
    root_pid = int(root_record.group("supervisor"))
    child_pid = int(root_record.group("candidate"))
    if root_pid in inconsistent or child_pid in inconsistent:
        return False
    if not _direct_root_identity_agrees(observations, root_pid, root_line, root_image):
        return False
    if not any(
        observation.evidence.identity.pid == child_pid for observation in observations
    ):
        # A known bundle bootstrap cannot stand in for a directly launched app.
        return not any(
            observation.evidence.parent_identity.pid == child_pid
            and (image := _absolute_image(observation.evidence.executable)) is not None
            and _absolute_image(observation.evidence.parent_executable) == image
            and _is_generation_launcher_image(layout, image)
            for observation in observations
        )
    root = _unique_process(observations, root_pid, root_line)
    for child_line, child_record in records:
        if (
            child_record.group("outer") != "True"
            or int(child_record.group("supervisor")) != child_pid
        ):
            continue
        child = _unique_process(observations, child_pid, child_line)
        if child is None or child.parent_identity.pid != root_pid:
            continue
        if _absolute_image(child.parent_executable) != root_image:
            continue
        if root is not None and child.parent_identity != root.identity:
            continue
        return True
    return False


def _direct_root_identity_agrees(
    observations: list[_ProcessObservation],
    pid: int,
    acceptance_line: int,
    root_image: Path,
) -> bool:
    """Preserve legacy evidence but never override a contradictory fresh diagnostic."""
    if not any(
        observation.evidence.identity.pid == pid for observation in observations
    ):
        return True
    evidence = _unique_process(observations, pid, acceptance_line)
    return evidence is not None and _absolute_image(evidence.executable) == root_image


def _is_generation_launcher_image(layout: InstallLayout, image: Path) -> bool:
    """Recognize only the authoritative launcher role of an owned generation."""
    target = launcher_bundle_target_for_key(layout.target.key)
    payload = LauncherBundlePaths(layout.root).payload_for_executable(image, target)
    return (
        payload is not None
        and image == (payload / target.executable_relative_path).resolve()
    )


def _absolute_image(value: str) -> Path | None:
    """Normalize absolute image paths without accepting basename-only evidence."""
    path = Path(logical_path(value))
    if not path.is_absolute():
        return None
    return operational_path(path).resolve()


def _process_observations(
    lines: list[str],
) -> tuple[list[_ProcessObservation], set[int]]:
    """Reject malformed or contradictory process incarnations in the fresh log."""
    observations: list[_ProcessObservation] = []
    inconsistent: set[int] = set()
    identities: dict[int, set[tuple[float, Path | None]]] = {}
    pattern = re.compile(
        r"process=(\d+) .*?logging_setup "
        + re.escape(LAUNCHER_PROCESS_EVENT)
        + r"(.*)$"
    )
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match is None:
            continue
        prefix_pid = int(match.group(1))
        try:
            evidence = LauncherProcessEvidence.from_json(json.loads(match.group(2)))
        except (ValueError, TypeError):
            inconsistent.add(prefix_pid)
            continue
        if prefix_pid != evidence.identity.pid:
            inconsistent.update((prefix_pid, evidence.identity.pid))
            continue
        observations.append(_ProcessObservation(index, evidence))
        for identity, executable in (
            (evidence.identity, evidence.executable),
            (evidence.parent_identity, evidence.parent_executable),
        ):
            image = _absolute_image(executable)
            identities.setdefault(identity.pid, set()).add((identity.created_at, image))
            if image is None:
                inconsistent.add(identity.pid)
    inconsistent.update(pid for pid, values in identities.items() if len(values) != 1)
    return observations, inconsistent


def _unique_process(
    observations: list[_ProcessObservation],
    pid: int,
    acceptance_line: int,
) -> LauncherProcessEvidence | None:
    """Require one consistent runtime observation predating its own acceptance."""
    matches = [
        observation
        for observation in observations
        if observation.evidence.identity.pid == pid
    ]
    evidence = {observation.evidence for observation in matches}
    if len(evidence) != 1 or not any(
        observation.line < acceptance_line for observation in matches
    ):
        return None
    return evidence.pop()


__all__ = [
    "assert_candidate_root_readiness",
    "assert_root_main_shell_acknowledgement",
]

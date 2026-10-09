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

"""Verify exact attested root acceptance through onefile launcher bootstraps."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.process_identity_evidence import (
    LAUNCHER_PROCESS_EVENT,
    LauncherProcessEvidence,
)
from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
)
from sugarsubstitute_shared.launcher_update.targets import (
    launcher_bundle_target_for_key,
)
from sugarsubstitute_shared.process_identity import ProcessIdentity
from tools.ci.historical_launcher_chain_evidence import assert_candidate_root_readiness
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


_TOKEN = "current-qualification"


@dataclass(frozen=True)
class _Launch:
    """Expose the exact pre-launch log byte boundary used by qualification."""

    progress_baselines: tuple[tuple[Path, tuple[bool, int]], ...]


@dataclass
class _Evidence:
    """Hold one observed two-hop topology without recreating the acceptance rules."""

    layout: InstallLayout
    selected: LauncherProcessEvidence
    root: LauncherProcessEvidence
    receipt: ApplicationReadinessReceipt
    lines: list[str]
    event: dict[str, object]
    baseline: int = 0
    extra_events: list[dict[str, object]] = field(default_factory=list)

    def assert_accepted(self) -> None:
        """Write independent producer evidence and invoke the public qualification."""
        self.layout.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.layout.logs_dir / "launcher.log"
        log_path.write_text("".join(self.lines), encoding="utf-8")
        event_path = self.layout.root / "qualification.jsonl"
        event_path.write_text(
            "".join(
                json.dumps(event) + "\n" for event in [self.event, *self.extra_events]
            ),
            encoding="utf-8",
        )
        receipt_path = self.layout.root / "readiness.json"
        receipt_path.write_text(json.dumps(self.receipt.to_json()), encoding="utf-8")
        assert_candidate_root_readiness(
            install_root=self.layout.root,
            candidate_launch=_Launch(((log_path, (True, self.baseline)),)),
            readiness_path=receipt_path,
            event_log_path=event_path,
            token=_TOKEN,
        )


def _identity(
    evidence: LauncherProcessEvidence, *, prefix_pid: int | None = None
) -> str:
    """Use the production diagnostic wire shape, with independently named PID."""
    return (
        f"INFO process={evidence.identity.pid if prefix_pid is None else prefix_pid} "
        "launcher.sugarsubstitute_launcher.logging_setup "
        + LAUNCHER_PROCESS_EVENT
        + json.dumps(evidence.to_json())
        + "\n"
    )


def _acceptance(supervisor: int, candidate: int, surface: int, *, outer: bool) -> str:
    """Preserve the producer's acceptance schema and exact surface binding."""
    return (
        f"INFO process={supervisor} launcher.sugarsubstitute_launcher."
        "application_readiness_supervisor Accepted painted application surface | "
        f"candidate_pid={candidate} | surface_pid={surface} | surface=main_shell | outer_contract={outer}\n"
    )


def _evidence(
    root: Path, *, ids: tuple[int, int, int, int, int] = (6500, 1420, 2440, 4896, 7388)
) -> _Evidence:
    """Reproduce the observed upgrade chain with fixture-local executable paths."""
    selected_pid, bootstrap_pid, root_pid, root_parent, surface = ids
    layout = InstallLayout.from_root(root)
    target = launcher_bundle_target_for_key(layout.target.key)
    image = (
        layout.launcher_dir
        / "bundles"
        / ("1" * 32)
        / "payload"
        / target.executable_relative_path
    )
    selected = LauncherProcessEvidence(
        ProcessIdentity(selected_pid, 103.0),
        ProcessIdentity(bootstrap_pid, 102.0),
        str(image),
        str(image),
    )
    installed = LauncherProcessEvidence(
        ProcessIdentity(root_pid, 101.0),
        ProcessIdentity(root_parent, 100.0),
        str(layout.executable_path),
        str(layout.executable_path),
    )
    return _Evidence(
        layout,
        selected,
        installed,
        ApplicationReadinessReceipt(
            surface,
            _TOKEN,
            ApplicationReadinessSurface.MAIN_SHELL,
            6824,
            attester_pids=(selected_pid, bootstrap_pid, root_pid, root_parent),
        ),
        [
            _identity(installed),
            _identity(selected),
            _acceptance(selected_pid, 6824, surface, outer=True),
            _acceptance(root_pid, bootstrap_pid, surface, outer=False),
        ],
        {
            "event": "launcher.startup.resolved",
            "pid": selected_pid,
            "token": _TOKEN,
            "fields": {"invocation_path": str(image)},
        },
    )


@pytest.mark.parametrize(
    "ids", [(6500, 1420, 2440, 4896, 7388), (2072, 9276, 7396, 8424, 9764)]
)
@pytest.mark.parametrize("root_logs_first", [False, True])
def test_historical_onefile_chain_accepts_both_observed_upgrade_topologies(
    tmp_path: Path,
    ids: tuple[int, int, int, int, int],
    root_logs_first: bool,
) -> None:
    """Outer-receipt publication may let the root log acceptance before its child."""
    evidence = _evidence(tmp_path, ids=ids)
    if root_logs_first:
        evidence.lines[2:] = list(reversed(evidence.lines[2:]))
    evidence.assert_accepted()


def test_historical_onefile_chain_allows_identical_repeated_diagnostics(
    tmp_path: Path,
) -> None:
    """Repeated observation of one incarnation is not evidence of another owner."""
    evidence = _evidence(tmp_path)
    evidence.lines.insert(2, evidence.lines[1])
    evidence.assert_accepted()


@pytest.mark.parametrize(
    "fault",
    [
        "selected_acceptance",
        "root_acceptance",
        "selected_identity",
        "root_identity",
        "stale_identity",
        "stale_acceptance",
        "selected_parent",
        "parent_image",
        "selected_image",
        "root_image",
        "selected_role",
        "relative_selected",
        "relative_root",
        "missing_attester",
        "missing_root_attester",
        "reordered_attesters",
        "duplicate_attester",
        "disconnected_attesters",
        "impossible_chronology",
        "runtime_reuse",
        "parent_reuse",
        "extra_runtime",
        "late_selected_identity",
        "late_root_identity",
        "malformed_identity",
        "prefix_mismatch",
        "wrong_event_token",
        "wrong_event_path",
        "wrong_receipt_token",
        "wrong_surface",
        "truncated_log",
        "empty_identity",
        "ambiguous_event_images",
        "event_claims_root",
        "root_candidate_skips_bootstrap",
        "contradictory_root_event",
        "missing_selected_acceptance_and_bootstrap",
    ],
)
def test_historical_onefile_chain_rejects_unproven_ownership(
    fault: str, tmp_path: Path
) -> None:
    """Neither a painted candidate nor a PID-looking relationship proves root acceptance."""
    evidence = _evidence(tmp_path)
    selected = evidence.selected
    root = evidence.root
    if fault in {
        "selected_acceptance",
        "root_acceptance",
        "selected_identity",
        "root_identity",
    }:
        evidence.lines.pop(
            {
                "root_identity": 0,
                "selected_identity": 1,
                "selected_acceptance": 2,
                "root_acceptance": 3,
            }[fault]
        )
    elif fault == "stale_identity":
        evidence.baseline = len("".join(evidence.lines[:2]).encode())
    elif fault == "stale_acceptance":
        evidence.baseline = len("".join(evidence.lines).encode())
    elif fault == "truncated_log":
        evidence.baseline = len("".join(evidence.lines).encode()) + 1
    elif fault == "selected_parent":
        evidence.lines[1] = _identity(
            replace(selected, parent_identity=ProcessIdentity(9999, 102.0))
        )
    elif fault == "parent_image":
        evidence.lines[1] = _identity(
            replace(selected, parent_executable=str(tmp_path / "Other.exe"))
        )
    elif fault in {"selected_image", "selected_role", "relative_selected"}:
        image = {
            "selected_image": str(
                tmp_path / "unowned" / Path(selected.executable).name
            ),
            "selected_role": str(Path(selected.executable).with_name("Repair.exe")),
            "relative_selected": Path(selected.executable).name,
        }[fault]
        evidence.lines[1] = _identity(
            replace(selected, executable=image, parent_executable=image)
        )
        evidence.event["fields"] = {"invocation_path": image}
    elif fault in {"root_image", "relative_root"}:
        image = (
            str(tmp_path / "Other.exe")
            if fault == "root_image"
            else Path(root.executable).name
        )
        evidence.lines[0] = _identity(
            replace(root, executable=image, parent_executable=image)
        )
    elif fault == "missing_attester":
        evidence.receipt = replace(evidence.receipt, attester_pids=(6500, 2440, 4896))
    elif fault == "missing_root_attester":
        evidence.receipt = replace(evidence.receipt, attester_pids=(6500, 1420, 4896))
    elif fault == "reordered_attesters":
        evidence.receipt = replace(
            evidence.receipt, attester_pids=(1420, 6500, 2440, 4896)
        )
    elif fault == "duplicate_attester":
        evidence.receipt = replace(
            evidence.receipt, attester_pids=(6500, 1420, 2440, 4896, 6500)
        )
    elif fault == "disconnected_attesters":
        evidence.receipt = replace(
            evidence.receipt, attester_pids=(6500, 9999, 1420, 2440, 4896)
        )
    elif fault == "impossible_chronology":
        evidence.lines[0] = _identity(
            replace(root, identity=ProcessIdentity(2440, 102.5))
        )
    elif fault == "runtime_reuse":
        evidence.lines.insert(
            2, _identity(replace(selected, identity=ProcessIdentity(6500, 104.0)))
        )
    elif fault == "parent_reuse":
        evidence.lines.insert(
            2, _identity(replace(root, parent_identity=ProcessIdentity(4896, 100.5)))
        )
    elif fault == "extra_runtime":
        evidence.lines.insert(
            2, _identity(replace(selected, identity=ProcessIdentity(6501, 103.5)))
        )
    elif fault == "late_selected_identity":
        evidence.lines.append(evidence.lines.pop(1))
    elif fault == "late_root_identity":
        evidence.lines.append(evidence.lines.pop(0))
    elif fault == "malformed_identity":
        evidence.lines[1] = (
            evidence.lines[1].split(LAUNCHER_PROCESS_EVENT)[0]
            + LAUNCHER_PROCESS_EVENT
            + "{bad-json}\n"
        )
    elif fault == "empty_identity":
        evidence.lines.insert(
            2,
            _identity(selected).split(LAUNCHER_PROCESS_EVENT)[0]
            + LAUNCHER_PROCESS_EVENT
            + "\n",
        )
    elif fault == "ambiguous_event_images":
        evidence.extra_events.append(
            {**evidence.event, "fields": {"invocation_path": root.executable}}
        )
    elif fault == "prefix_mismatch":
        evidence.lines[1] = _identity(selected, prefix_pid=9999)
    elif fault == "event_claims_root":
        evidence.event["fields"] = {"invocation_path": root.executable}
    elif fault == "root_candidate_skips_bootstrap":
        evidence.lines[3] = _acceptance(2440, 6500, 7388, outer=False)
    elif fault == "contradictory_root_event":
        evidence.extra_events.append(
            {
                **evidence.event,
                "pid": 2440,
                "fields": {"invocation_path": str(tmp_path / "Other.exe")},
            }
        )
    elif fault == "missing_selected_acceptance_and_bootstrap":
        evidence.lines.pop(2)
        evidence.receipt = replace(evidence.receipt, attester_pids=(6500, 2440, 4896))
    elif fault == "wrong_event_token":
        evidence.event["token"] = "another-launch"
    elif fault == "wrong_event_path":
        evidence.event["fields"] = {
            "invocation_path": str(tmp_path / "other" / "SugarSubstitute.exe")
        }
    elif fault == "wrong_receipt_token":
        evidence.receipt = replace(evidence.receipt, token="another-launch")
    elif fault == "wrong_surface":
        evidence.receipt = replace(evidence.receipt, pid=12345)
    with pytest.raises(InstallerLifecycleError):
        evidence.assert_accepted()


@pytest.mark.parametrize("with_diagnostics", [False, True])
def test_direct_application_acceptance_keeps_root_only_attestation(
    tmp_path: Path,
    with_diagnostics: bool,
) -> None:
    """A directly launched app has root attesters without a delegated launcher hop."""
    evidence = _evidence(tmp_path)
    evidence.lines = ([_identity(evidence.root)] if with_diagnostics else []) + [
        _acceptance(2440, 6824, 7388, outer=False)
    ]
    evidence.receipt = replace(evidence.receipt, attester_pids=(2440, 4896))
    evidence.assert_accepted()


def test_direct_root_rejects_malformed_only_identity_evidence(tmp_path: Path) -> None:
    """A broken current diagnostic must not masquerade as absent legacy evidence."""
    evidence = _evidence(tmp_path)
    evidence.event = {
        **evidence.event,
        "pid": 2440,
        "fields": {"invocation_path": evidence.root.executable},
    }
    evidence.lines = [
        _identity(evidence.root).split(LAUNCHER_PROCESS_EVENT)[0]
        + LAUNCHER_PROCESS_EVENT
        + "{bad-json}\n",
        _acceptance(2440, 6824, 7388, outer=True),
    ]
    evidence.receipt = replace(evidence.receipt, attester_pids=(2440, 4896))
    with pytest.raises(InstallerLifecycleError):
        evidence.assert_accepted()


def test_onedir_delegation_keeps_direct_parent_identity(tmp_path: Path) -> None:
    """Fresh onedir evidence still proves a real directly supervised launcher."""
    evidence = _evidence(tmp_path)
    child = replace(
        evidence.selected,
        parent_identity=evidence.root.identity,
        parent_executable=evidence.root.executable,
    )
    evidence.lines = [
        _identity(evidence.root),
        _identity(child),
        _acceptance(6500, 6824, 7388, outer=True),
        _acceptance(2440, 6500, 7388, outer=False),
    ]
    evidence.receipt = replace(evidence.receipt, attester_pids=(6500, 2440, 4896))
    evidence.assert_accepted()


def test_direct_root_accepts_consistent_fresh_identity(tmp_path: Path) -> None:
    """A root's own token-bound image and diagnostic agree on direct ownership."""
    evidence = _evidence(tmp_path)
    evidence.event = {
        **evidence.event,
        "pid": 2440,
        "fields": {"invocation_path": evidence.root.executable},
    }
    evidence.lines = [
        _identity(evidence.root),
        _acceptance(2440, 6824, 7388, outer=True),
    ]
    evidence.receipt = replace(evidence.receipt, attester_pids=(2440, 4896))
    evidence.assert_accepted()

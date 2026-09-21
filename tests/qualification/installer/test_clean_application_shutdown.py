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

"""Qualify clean installed-application shutdown evidence."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from sugarsubstitute_shared.application_readiness import (
    ApplicationReadinessReceipt,
    ApplicationReadinessSurface,
)
from sugarsubstitute_shared.crash_reporting import (
    CrashAttribution,
    CrashBoundary,
    CrashIncident,
    CrashIncidentStore,
    CrashKind,
)
from tools.ci import installed_application_shutdown
from tools.ci.installed_application_shutdown import (
    QualificationCandidateProcess,
    assert_no_new_crash_incidents,
    wait_for_clean_qualification_shutdown,
)
from tools.ci.installer_lifecycle_errors import InstallerLifecycleError


def test_clean_shutdown_reaps_the_candidate_before_accepting_process_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A POSIX child zombie must be polled before no-live-process success."""

    polls: list[str] = []

    def poll_candidate() -> int:
        """Record one nonblocking reap of the candidate process."""

        polls.append("poll")
        return 0

    candidate = cast(
        QualificationCandidateProcess,
        SimpleNamespace(pid=123, poll=poll_candidate),
    )
    monkeypatch.setattr(
        installed_application_shutdown,
        "_tracked_processes",
        lambda **_arguments: (),
    )
    monkeypatch.setattr(
        installed_application_shutdown,
        "_installed_process_ids",
        lambda _root: (),
    )

    wait_for_clean_qualification_shutdown(
        install_root=tmp_path / "installed",
        receipt=ApplicationReadinessReceipt(
            pid=456,
            parent_pid=123,
            token="token",
            surface=ApplicationReadinessSurface.MAIN_SHELL,
        ),
        candidate_process=candidate,
        timeout_seconds=1.0,
    )

    assert polls == ["poll"]


def test_clean_shutdown_rejects_a_new_crash_incident(
    tmp_path: Path,
) -> None:
    """A terminated process is not clean when supervision generated an incident."""

    store = CrashIncidentStore(
        tmp_path / "installed" / "appdata" / "diagnostics" / "crashes"
    )
    store.record(
        CrashIncident(
            incident_id="new-run",
            run_id="new-run",
            occurred_at_utc="2026-09-21T00:00:00+00:00",
            kind=CrashKind.ABNORMAL_EXIT,
            boundary=CrashBoundary.SUPERVISOR,
            attribution=CrashAttribution.UNCLEAN_TERMINATION,
            summary="Synthetic qualification incident",
            process_id=42,
        )
    )

    with pytest.raises(InstallerLifecycleError, match="new-run"):
        assert_no_new_crash_incidents(
            install_root=tmp_path / "installed",
            baseline=frozenset(),
        )


def test_clean_shutdown_ignores_retained_run_workspace(tmp_path: Path) -> None:
    """Temporary or legacy run scaffolding must never become a crash."""

    run_directory = (
        tmp_path / "installed" / "appdata" / "diagnostics" / "runs" / "run-only"
    )
    run_directory.mkdir(parents=True)
    (run_directory / "startup-output.log").write_text(
        "retained diagnostic evidence\n",
        encoding="utf-8",
    )
    legacy_directory = (
        tmp_path
        / "installed"
        / "appdata"
        / "diagnostics"
        / "crashes"
        / "legacy-run-only"
    )
    legacy_directory.mkdir(parents=True)
    (legacy_directory / "runtime-context.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    assert_no_new_crash_incidents(
        install_root=tmp_path / "installed",
        baseline=frozenset(),
    )

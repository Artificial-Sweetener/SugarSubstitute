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

"""Verify durable runtime facts survive before an incident can be recorded."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.crash_reporting.run_context import (
    CrashRunRuntimeContext,
    CrashRunRuntimeContextStore,
)


def test_runtime_context_round_trips_without_secret_supervision_state(
    tmp_path: Path,
) -> None:
    """Supervisor fallback should recover complete non-secret runtime facts."""

    store = CrashRunRuntimeContextStore(tmp_path / "runs")
    expected = CrashRunRuntimeContext(
        process_id=42,
        application_version="0.23.5",
        platform="Windows-11",
        python_version="3.12",
        launch_arguments=("main.py", "--token=<redacted>"),
        install_root=str(tmp_path / "install"),
    )

    path = store.save("run-1", expected)

    assert path.is_file()
    assert store.load("run-1") == expected
    assert "supervision" not in path.read_text(encoding="utf-8")


def test_corrupt_runtime_context_is_an_observable_miss(
    tmp_path: Path,
) -> None:
    """Corrupt supplemental facts must not obstruct incident recovery."""

    store = CrashRunRuntimeContextStore(tmp_path / "runs")
    path = store.path("run-2")
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")

    assert store.load("run-2") is None
    assert path.read_text(encoding="utf-8") == "not json"


def test_runtime_context_resolves_exact_process_run(tmp_path: Path) -> None:
    """Qualification should bind startup evidence to its ready process identity."""

    store = CrashRunRuntimeContextStore(tmp_path / "runs")
    first = CrashRunRuntimeContext(
        process_id=41,
        application_version="0.24.0",
        platform="Windows-11",
        python_version="3.12",
        launch_arguments=(),
        install_root=str(tmp_path / "install"),
    )
    second = CrashRunRuntimeContext(
        process_id=42,
        application_version="0.24.1",
        platform="Windows-11",
        python_version="3.12",
        launch_arguments=(),
        install_root=str(tmp_path / "install"),
    )
    store.save("older-run", first)
    store.save("current-run", second)

    assert store.run_ids_for_process(42) == ("current-run",)

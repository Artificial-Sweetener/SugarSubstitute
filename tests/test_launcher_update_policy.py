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

"""Tests for launcher update state and policy decisions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig, UpdateCheckConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_policy import (
    AppPayloadUpdateDecision,
    UpdateCheckDecision,
    compare_release_versions,
    decide_app_payload_update,
    decide_update_check,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState


def test_launcher_update_state_defaults_when_missing(tmp_path: Path) -> None:
    """Missing update state should not block first launcher startup."""

    state = LauncherUpdateState.load(tmp_path / "missing-state.json")

    assert state == LauncherUpdateState()


def test_launcher_update_state_round_trips_json(tmp_path: Path) -> None:
    """Update state should persist installed version and UTC timestamps."""

    path = tmp_path / "state.json"
    state = LauncherUpdateState().with_successful_update(
        version="0.4.0",
        channel="stable",
        completed_at=datetime(2026, 7, 7, 12, 30, tzinfo=UTC),
    )

    state.save(path)
    loaded = LauncherUpdateState.load(path)

    assert loaded == state
    assert path.read_text(encoding="utf-8").splitlines() == [
        "{",
        '  "installed_app_version": "0.4.0",',
        '  "last_manifest_channel": "stable",',
        '  "last_successful_update_utc": "2026-07-07T12:30:00Z",',
        '  "last_update_check_utc": "2026-07-07T12:30:00Z",',
        '  "schema_version": 1',
        "}",
    ]


def test_update_check_policy_respects_cli_and_config_disables(tmp_path: Path) -> None:
    """Launcher update checks should be skippable from CLI or config."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    enabled_config = LauncherConfig.from_layout(layout=layout)
    disabled_config = LauncherConfig.from_layout(
        layout=layout,
        update_check=UpdateCheckConfig(enabled=False),
    )
    now = datetime(2026, 7, 7, tzinfo=UTC)

    assert (
        decide_update_check(
            config=enabled_config,
            state=LauncherUpdateState(),
            now=now,
            no_update_check=True,
        ).decision
        is UpdateCheckDecision.SKIP
    )
    assert (
        decide_update_check(
            config=disabled_config,
            state=LauncherUpdateState(),
            now=now,
            no_update_check=False,
        ).decision
        is UpdateCheckDecision.SKIP
    )


def test_update_check_policy_runs_when_daily_check_is_due(tmp_path: Path) -> None:
    """Daily update checks should run after the configured interval elapses."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    config = LauncherConfig.from_layout(layout=layout)
    now = datetime(2026, 7, 7, 12, tzinfo=UTC)
    recent_state = LauncherUpdateState(
        last_update_check_utc=now - timedelta(hours=12),
    )
    stale_state = LauncherUpdateState(
        last_update_check_utc=now - timedelta(days=1, minutes=1),
    )

    assert (
        decide_update_check(
            config=config,
            state=LauncherUpdateState(),
            now=now,
            no_update_check=False,
        ).reason
        == "never_checked"
    )
    assert (
        decide_update_check(
            config=config,
            state=recent_state,
            now=now,
            no_update_check=False,
        ).decision
        is UpdateCheckDecision.SKIP
    )
    assert (
        decide_update_check(
            config=config,
            state=stale_state,
            now=now,
            no_update_check=False,
        ).decision
        is UpdateCheckDecision.CHECK
    )


def test_app_payload_update_policy_installs_missing_or_newer_versions() -> None:
    """Payload install decisions should depend on installed and manifest versions."""

    assert (
        decide_app_payload_update(
            installed_version=None,
            manifest_version="0.4.0",
        ).decision
        is AppPayloadUpdateDecision.INSTALL
    )
    assert (
        decide_app_payload_update(
            installed_version="0.3.9",
            manifest_version="0.4.0",
        ).decision
        is AppPayloadUpdateDecision.INSTALL
    )
    assert (
        decide_app_payload_update(
            installed_version="0.4.0",
            manifest_version="0.4.0",
        ).decision
        is AppPayloadUpdateDecision.SKIP
    )


def test_compare_release_versions_requires_plain_dotted_numeric_versions() -> None:
    """Release comparison should reject path-like or non-numeric tags."""

    assert compare_release_versions("v0.10.0", "0.9.9") == 1
    assert compare_release_versions("0.4", "0.4.0") == 0
    with pytest.raises(ValueError, match="plain tag"):
        compare_release_versions("0.4/evil", "0.4.0")
    with pytest.raises(ValueError, match="dotted numeric"):
        compare_release_versions("latest", "0.4.0")

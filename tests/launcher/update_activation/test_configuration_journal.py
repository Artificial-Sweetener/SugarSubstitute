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

"""Verify configuration publication compatibility and installation scope."""

import json
from pathlib import Path

import pytest

from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    COMMITTED_PHASE,
    UpdateActivationJournal,
    UpdateRecoveryError,
    load_update_journal,
    update_journal_path,
    write_update_journal_data,
)
from launcher.sugarsubstitute_launcher.update_activation_recovery import (
    recover_interrupted_update,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState


def test_legacy_commit_preserves_existing_configuration(tmp_path: Path) -> None:
    """Complete a version-one decision without changing configuration it did not own."""
    layout = InstallLayout.from_root(tmp_path / "install")
    LauncherConfig.from_layout(layout=layout, channel="preview").save(
        layout.config_path
    )
    previous = layout.config_path.read_bytes()
    payload = UpdateActivationJournal(
        had_app=True,
        had_runtime=True,
        phase=COMMITTED_PHASE,
        successful_state=LauncherUpdateState(installed_app_version="0.4.0"),
    ).to_json()
    payload["schema_version"] = 1
    payload.pop("successful_config")
    write_update_journal_data(update_journal_path(layout), payload)
    assert recover_interrupted_update(layout)
    assert layout.config_path.read_bytes() == previous
    assert LauncherUpdateState.load(layout.state_path).installed_app_version == "0.4.0"


@pytest.mark.parametrize("field", ["install_root", "app_dir", "runtime_python"])
def test_recovery_rejects_configuration_outside_its_installation(
    tmp_path: Path, field: str
) -> None:
    """Retain the journal and prior state when its configuration targets another root."""
    layout = InstallLayout.from_root(tmp_path / "install")
    config = LauncherConfig.from_layout(layout=layout)
    config.save(layout.config_path)
    previous = layout.config_path.read_bytes()
    payload = UpdateActivationJournal(
        had_app=True,
        had_runtime=True,
        phase=COMMITTED_PHASE,
        successful_state=LauncherUpdateState(installed_app_version="0.4.0"),
        successful_config=config,
    ).to_json()
    config_payload = config.to_json()
    config_payload[field] = str(tmp_path / "another-installation")
    payload["successful_config"] = config_payload
    journal_path = update_journal_path(layout)
    write_update_journal_data(journal_path, payload)
    with pytest.raises(UpdateRecoveryError, match="configuration"):
        recover_interrupted_update(layout)
    assert layout.config_path.read_bytes() == previous
    assert not layout.state_path.exists()
    assert json.loads(journal_path.read_text(encoding="utf-8")) == payload


@pytest.mark.parametrize("configuration", [[], "invalid", {"schema_version": 999}])
def test_invalid_configuration_is_rejected_before_publication(
    tmp_path: Path, configuration: object
) -> None:
    """Reject malformed configuration without applying a partial activation decision."""
    layout = InstallLayout.from_root(tmp_path / "install")
    payload = UpdateActivationJournal(
        had_app=False,
        had_runtime=False,
        phase=COMMITTED_PHASE,
        successful_state=LauncherUpdateState(installed_app_version="0.4.0"),
    ).to_json()
    payload["successful_config"] = configuration
    write_update_journal_data(update_journal_path(layout), payload)
    with pytest.raises(UpdateRecoveryError, match="configuration"):
        load_update_journal(layout)


@pytest.mark.parametrize("version", [[], {}, True, "2", 999])
def test_malformed_journal_version_has_a_controlled_recovery_error(
    tmp_path: Path, version: object
) -> None:
    """Keep malformed JSON types on the recoverable journal-error path."""
    layout = InstallLayout.from_root(tmp_path / "install")
    write_update_journal_data(update_journal_path(layout), {"schema_version": version})
    with pytest.raises(UpdateRecoveryError, match="unsupported schema"):
        load_update_journal(layout)

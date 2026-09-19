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

"""Keep unowned legacy backups outside a new activation's rollback authority."""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.installation_recovery import InstallationRecovery
from sugarsubstitute_shared.installation_mutation import InstallationMutationBusyError
from launcher.sugarsubstitute_launcher.update_activation import PendingUpdateActivation
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.payload_models import StagedAppPayload
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    PREPARING_PHASE,
    UpdateActivationJournal,
    UpdateRecoveryError,
    update_journal_path,
    write_update_journal_data,
    load_update_journal,
)
from launcher.sugarsubstitute_launcher.update_activation_recovery import (
    recover_interrupted_update,
)


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("promote", [False, True])
def test_unused_activation_preserves_current_content_and_unrelated_backups(
    tmp_path: Path, commit: bool, promote: bool
) -> None:
    """Never restore or delete another operation's backup merely because it exists."""
    layout = InstallLayout.from_root(tmp_path / "install")
    expected = {
        layout.app_dir / "version.txt": "current-app",
        layout.runtime_dir / "version.txt": "current-runtime",
        layout.root / "app_previous" / "version.txt": "unrelated-old-app",
        layout.root / "runtime_previous" / "version.txt": "unrelated-old-runtime",
    }
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="candidate"),
    )
    owned_directory = activation.staging_directory.parent
    try:
        if promote:
            activation.staging_directory.mkdir(parents=True)
            (activation.staging_directory / "version.txt").write_text("candidate-app")
            activation.promote_app(
                StagedAppPayload(
                    version="candidate", staging_dir=activation.staging_directory
                )
            )
            activation.prepare_runtime()
            (layout.runtime_dir / "version.txt").write_text("candidate-runtime")
        if commit:
            activation.commit()
        else:
            activation.rollback()
    finally:
        activation.rollback()
    if promote and commit:
        expected[layout.app_dir / "version.txt"] = "candidate-app"
        expected[layout.runtime_dir / "version.txt"] = "candidate-runtime"
    assert {path: path.read_text(encoding="utf-8") for path in expected} == expected
    assert not owned_directory.exists()


@pytest.mark.parametrize("schema_version", [1, 2])
def test_legacy_pending_journal_still_restores_its_fixed_backups(
    tmp_path: Path, schema_version: int
) -> None:
    """Honor the existing storage contract only when a legacy journal records it."""
    layout = InstallLayout.from_root(tmp_path / "install")
    for name in ("app", "runtime"):
        active = layout.root / name
        backup = layout.root / (name + "_previous")
        active.mkdir(parents=True)
        backup.mkdir(parents=True)
        (active / "version.txt").write_text("candidate")
        (backup / "version.txt").write_text("original")
    payload = UpdateActivationJournal(
        had_app=True,
        had_runtime=True,
        phase=PREPARING_PHASE,
        successful_state=LauncherUpdateState(installed_app_version="candidate"),
    ).to_json()
    payload["schema_version"] = schema_version
    write_update_journal_data(update_journal_path(layout), payload)
    assert recover_interrupted_update(layout)
    for name in ("app", "runtime"):
        assert (layout.root / name / "version.txt").read_text() == "original"


@pytest.mark.parametrize("identity", [None, "", "../outside", "g" * 32, "/outside"])
def test_transaction_identity_cannot_select_arbitrary_backup_paths(
    tmp_path: Path, identity: object
) -> None:
    """Reject an invalid identity before deriving any activation-owned filesystem path."""
    layout = InstallLayout.from_root(tmp_path / "install")
    payload = UpdateActivationJournal(
        had_app=True,
        had_runtime=True,
        phase=PREPARING_PHASE,
        successful_state=LauncherUpdateState(installed_app_version="candidate"),
    ).to_json()
    payload.update(schema_version=3, transaction_id=identity)
    write_update_journal_data(update_journal_path(layout), payload)
    with pytest.raises(UpdateRecoveryError, match="identity"):
        load_update_journal(layout)


def test_second_activation_cannot_overwrite_pending_intent(tmp_path: Path) -> None:
    """Reject a second logical transaction even on the same reentrant execution thread."""
    layout = InstallLayout.from_root(tmp_path / "install")
    state = LauncherUpdateState(installed_app_version="candidate")
    first = PendingUpdateActivation.begin(layout=layout, successful_state=state)
    journal_path = update_journal_path(layout)
    intent = journal_path.read_bytes()
    try:
        with pytest.raises(InstallationMutationBusyError):
            PendingUpdateActivation.begin(layout=layout, successful_state=state)
        assert journal_path.read_bytes() == intent
    finally:
        first.rollback()


def test_independent_recovery_cannot_roll_back_live_activation(tmp_path: Path) -> None:
    """Preserve a live candidate until its owner makes the activation decision."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.app_dir.mkdir(parents=True)
    marker = layout.app_dir / "version.txt"
    marker.write_text("original", encoding="utf-8")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="candidate"),
    )
    try:
        activation.staging_directory.mkdir()
        (activation.staging_directory / "version.txt").write_text(
            "candidate", encoding="utf-8"
        )
        activation.promote_app(
            StagedAppPayload(
                version="candidate", staging_dir=activation.staging_directory
            )
        )
        intent = update_journal_path(layout).read_bytes()
        with pytest.raises(InstallationMutationBusyError):
            InstallationRecovery(layout).recover()
        assert marker.read_text(encoding="utf-8") == "candidate"
        assert update_journal_path(layout).read_bytes() == intent
        activation.commit()
        assert (
            LauncherUpdateState.load(layout.state_path).installed_app_version
            == "candidate"
        )
        assert marker.read_text(encoding="utf-8") == "candidate"
    finally:
        activation.rollback()


@pytest.mark.parametrize("commit", [False, True])
def test_finished_actor_cannot_change_successor_intent(
    tmp_path: Path, commit: bool
) -> None:
    """Keep late callbacks inert after an activation releases its operation."""
    layout = InstallLayout.from_root(tmp_path / "install")
    state = LauncherUpdateState(installed_app_version="candidate")
    first = PendingUpdateActivation.begin(layout=layout, successful_state=state)
    first.rollback()
    second = PendingUpdateActivation.begin(layout=layout, successful_state=state)
    intent = update_journal_path(layout).read_bytes()
    try:
        if commit:
            first.commit()
        else:
            first.rollback()
        assert update_journal_path(layout).read_bytes() == intent
    finally:
        second.rollback()


@pytest.mark.parametrize("commit", [False, True])
def test_other_thread_cannot_finish_live_activation(
    tmp_path: Path, commit: bool
) -> None:
    """Reject a foreign terminal callback without retiring the legitimate owner."""
    layout = InstallLayout.from_root(tmp_path / "install")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="candidate"),
    )
    intent = update_journal_path(layout).read_bytes()
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            callback = activation.commit if commit else activation.rollback
            with pytest.raises(InstallationMutationBusyError, match="elsewhere"):
                pool.submit(callback).result(timeout=10)
        assert update_journal_path(layout).read_bytes() == intent
        activation.commit()
        assert not update_journal_path(layout).exists()
    finally:
        activation.rollback()


def test_committed_decision_prevents_late_runtime_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Freeze mutation once commitment is durable, even if publication fails."""
    layout = InstallLayout.from_root(tmp_path / "install")
    layout.runtime_dir.mkdir(parents=True)
    marker = layout.runtime_dir / "version.txt"
    marker.write_text("original")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="candidate"),
    )

    def fail_publication(_state: LauncherUpdateState, _path: Path) -> None:
        """Reject state publication after the commit record is persisted."""
        raise OSError("injected publication failure")

    try:
        with monkeypatch.context() as fault:
            fault.setattr(LauncherUpdateState, "save", fail_publication)
            with pytest.raises(OSError, match="publication"):
                activation.commit()
        with pytest.raises(UpdateRecoveryError, match="already committed"):
            activation.prepare_runtime()
        assert marker.read_text() == "original"
    finally:
        activation.rollback()

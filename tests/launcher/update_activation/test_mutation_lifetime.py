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

"""Require payload activation to participate in complete installation ownership."""

from __future__ import annotations
from contextlib import nullcontext
import os
from pathlib import Path
import subprocess
import sys
import pytest
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.startup_plan import (
    LauncherStartupCandidate,
    is_installed_app_launchable,
)
from launcher.sugarsubstitute_launcher.startup_recovery import recover_startup_candidate
from launcher.sugarsubstitute_launcher.update_activation import (
    PendingUpdateActivation,
)
from launcher.sugarsubstitute_launcher.update_activation_recovery import (
    recover_interrupted_update,
)
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    update_journal_path,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from sugarsubstitute_shared.installation_mutation import installation_mutation


def _layout(root: Path) -> InstallLayout:
    """Create portable synthetic startup dependencies without a live application."""
    layout = InstallLayout.from_root(root)
    layout.app_entrypoint.parent.mkdir(parents=True)
    layout.app_entrypoint.write_text("", encoding="utf-8")
    layout.runtime_python.parent.mkdir(parents=True)
    layout.runtime_python.write_bytes(b"old-runtime")
    LauncherConfig.from_layout(layout=layout).save(layout.config_path)
    return layout


def _child(
    module: str, root: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    """Run one bounded hidden native child and capture all diagnostics."""
    return subprocess.run(
        [sys.executable, "-m", module, str(root), *arguments],
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        check=False,
    )


def test_payload_update_cannot_mutate_an_owned_installation(tmp_path: Path) -> None:
    """Preserve runtime and journal state while another installation writer is active."""
    layout = _layout(tmp_path / "install")
    try:
        with installation_mutation(layout.root):
            child = _child(
                "tests.launcher.update_activation.ownership_process", layout.root
            )
            assert child.returncode == 17, child.stderr
            assert layout.runtime_python.read_bytes() == b"old-runtime"
            assert not update_journal_path(layout).exists()
    finally:
        recover_interrupted_update(layout)


@pytest.mark.parametrize("commit", [False, True])
@pytest.mark.parametrize("retained_from_preparation", [False, True])
def test_activation_keeps_ownership_until_terminal_transition(
    tmp_path: Path, commit: bool, retained_from_preparation: bool
) -> None:
    """Retain exclusion across preparation and release it after commit or rollback."""
    layout = _layout(tmp_path / "install")
    preparation = (
        installation_mutation(layout.root)
        if retained_from_preparation
        else nullcontext()
    )
    with preparation as operation:
        activation = PendingUpdateActivation.begin(
            layout=layout,
            operation=operation,
            successful_state=LauncherUpdateState(installed_app_version="2.0.0"),
        )
    try:
        child = _child(
            "tests.shared.installation_mutation.probe_process", layout.root, "claim"
        )
        assert child.returncode == 17, child.stderr
        activation.prepare_runtime()
        layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
        layout.runtime_python.write_bytes(b"new-runtime")
        if commit:
            activation.commit()
        else:
            activation.rollback()
        child = _child(
            "tests.shared.installation_mutation.probe_process", layout.root, "claim"
        )
        assert child.returncode == 0, child.stderr
    finally:
        activation.rollback()


def test_ordinary_startup_recovers_payload_update_without_update_check(
    tmp_path: Path,
) -> None:
    """Restore an interrupted runtime before optional update policy or app assessment."""
    layout = _layout(tmp_path / "install")
    child = _child("tests.launcher.update_activation.ownership_process", layout.root)
    assert child.returncode == 73, child.stderr
    assert not layout.runtime_python.exists()
    try:
        candidate = recover_startup_candidate(LauncherStartupCandidate(layout, True))
        assert is_installed_app_launchable(candidate.layout)
        assert layout.runtime_python.read_bytes() == b"old-runtime"
        assert not update_journal_path(layout).exists()
    finally:
        recover_interrupted_update(layout)


def test_failed_journal_creation_releases_native_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Leave another execution able to recover when activation cannot persist intent."""
    from launcher.sugarsubstitute_launcher import update_activation

    layout = _layout(tmp_path / "install")

    def reject_write(_path: Path, _payload: dict[str, object]) -> None:
        """Reject the filesystem boundary before any activation journal is published."""
        raise OSError("injected journal failure")

    monkeypatch.setattr(update_activation, "write_update_journal_data", reject_write)
    with pytest.raises(OSError, match="injected journal"):
        PendingUpdateActivation.begin(
            layout=layout,
            successful_state=LauncherUpdateState(installed_app_version="2.0.0"),
        )
    assert (
        _child(
            "tests.shared.installation_mutation.probe_process", layout.root, "claim"
        ).returncode
        == 0
    )
    assert layout.runtime_python.read_bytes() == b"old-runtime"


def test_command_failure_rolls_back_and_releases_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retire prepared mutation even when failure precedes candidate supervision."""
    from launcher.sugarsubstitute_launcher import installed_app_handoff
    from launcher.sugarsubstitute_launcher.update_orchestrator import (
        PreLaunchUpdateResult,
    )
    from tests.launcher.application_launch.instance_routing_support import BrokerDouble

    layout = _layout(tmp_path / "install")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="2.0.0"),
    )
    activation.prepare_runtime()
    result = PreLaunchUpdateResult(
        checked_manifest=True,
        installed_update=True,
        pending_activation=activation,
        attempted_version="2.0.0",
    )

    class PreparedOrchestrator:
        """Supply the real prepared transaction at the update-network boundary."""

        def run(self, **_kwargs: object) -> PreLaunchUpdateResult:
            """Transfer the test-owned activation to the production handoff."""
            return result

    def reject_command(**_kwargs: object) -> list[str]:
        """Fail launch assembly before any native application starts."""
        raise ValueError("injected command failure")

    monkeypatch.setattr(
        installed_app_handoff, "LauncherUpdateOrchestrator", PreparedOrchestrator
    )
    monkeypatch.setattr(
        installed_app_handoff, "build_app_launch_command", reject_command
    )
    try:
        with pytest.raises(ValueError, match="injected command"):
            installed_app_handoff.complete_installed_app_handoff(
                layout=layout,
                broker=BrokerDouble(),
                locale_argument="--locale=en",
                no_update_check=False,
                splash_session=None,
                handoff_geometry=None,
            )
        assert layout.runtime_python.read_bytes() == b"old-runtime"
        assert (
            _child(
                "tests.shared.installation_mutation.probe_process", layout.root, "claim"
            ).returncode
            == 0
        )
    finally:
        activation.rollback()


def test_failed_rollback_releases_ownership_for_fresh_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Retain the journal but retire the failed actor so a fresh attempt can recover."""
    layout = _layout(tmp_path / "install")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="2.0.0"),
    )
    activation.prepare_runtime()
    replace = Path.replace

    def reject_restore(source: Path, target: str | Path) -> Path:
        """Deny only the original runtime's restoration at the filesystem boundary."""
        if Path(target).resolve() == layout.runtime_dir.resolve():
            raise PermissionError("injected rollback denial")
        return replace(source, target)

    try:
        with monkeypatch.context() as fault:
            fault.setattr(Path, "replace", reject_restore)
            with pytest.raises(PermissionError, match="injected rollback"):
                activation.rollback()
        assert (
            _child(
                "tests.shared.installation_mutation.probe_process", layout.root, "claim"
            ).returncode
            == 0
        )
        with pytest.raises(RuntimeError, match="already finished"):
            activation.prepare_runtime()
        assert recover_interrupted_update(layout)
        assert layout.runtime_python.read_bytes() == b"old-runtime"
    finally:
        activation.rollback()
        recover_interrupted_update(layout)


def test_commit_bookkeeping_failure_preserves_durable_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Honor the committed candidate when the caller invokes failure cleanup."""
    layout = _layout(tmp_path / "install")
    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=LauncherUpdateState(installed_app_version="2.0.0"),
    )
    activation.prepare_runtime()
    layout.runtime_python.parent.mkdir(parents=True, exist_ok=True)
    layout.runtime_python.write_bytes(b"committed-runtime")

    def reject_state(_state: LauncherUpdateState, _path: Path) -> None:
        """Fail only bookkeeping after the durable commit marker was written."""
        raise OSError("injected bookkeeping failure")

    try:
        with monkeypatch.context() as fault:
            fault.setattr(LauncherUpdateState, "save", reject_state)
            with pytest.raises(OSError, match="injected bookkeeping"):
                activation.commit()
        assert (
            _child(
                "tests.shared.installation_mutation.probe_process", layout.root, "claim"
            ).returncode
            == 17
        )
        activation.rollback()
        assert layout.runtime_python.read_bytes() == b"committed-runtime"
        assert (
            LauncherUpdateState.load(layout.state_path).installed_app_version == "2.0.0"
        )
        assert (
            _child(
                "tests.shared.installation_mutation.probe_process", layout.root, "claim"
            ).returncode
            == 0
        )
    finally:
        activation.rollback()

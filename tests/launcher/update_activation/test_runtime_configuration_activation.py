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

"""Prove application runtime identity follows transactional release selection."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from launcher.sugarsubstitute_launcher.application_release_selection import (
    ApplicationReleaseSelection,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.payload_models import StagedAppPayload
from launcher.sugarsubstitute_launcher.update_activation import (
    PendingUpdateActivation,
)
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    ACTIVATED_PHASE,
    UpdateActivationJournal,
    update_journal_path,
    write_update_journal_data,
)
from launcher.sugarsubstitute_launcher.update_activation_recovery import (
    recover_interrupted_update,
)
from launcher.sugarsubstitute_launcher.update_runtime_configuration import (
    RuntimeConfigurationSnapshot,
    runtime_configuration_path,
    select_candidate_runtime_configuration,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from substitute.domain.onboarding import (
    InstallationConfiguration,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from substitute.infrastructure.onboarding.readiness_checks import (
    FileSystemReadinessChecks,
)


_PREVIOUS_GENERATION = "1" * 32
_CANDIDATE_GENERATION = "2" * 32


def test_023_runtime_record_becomes_ready_for_candidate_generation(
    tmp_path: Path,
) -> None:
    """Replace the split 0.23 runtime identity before candidate readiness starts."""

    layout = _installed_023_layout(tmp_path)
    activation = _prepared_candidate(layout)
    try:
        activation.activate()

        payload = _runtime_payload(layout)
        candidate_layout = layout.for_release_root(
            ApplicationReleaseSelection(layout.root).active_root()
        )
        configuration = RuntimeConfiguration(
            runtime_root=Path(str(payload["runtime_root"])),
            python_executable=Path(str(payload["python_executable"])),
            bootstrap_status=RuntimeBootstrapStatus(str(payload["bootstrap_status"])),
            schema_version=str(payload["schema_version"]),
        )
        assert configuration.runtime_root == candidate_layout.runtime_dir
        assert configuration.python_executable == candidate_layout.runtime_python
        assert FileSystemReadinessChecks().is_runtime_configuration_valid(configuration)
        assert FileSystemReadinessChecks().runtime_python_exists(configuration)
    finally:
        activation.rollback()


def test_generation_rollback_restores_exact_runtime_record(tmp_path: Path) -> None:
    """Restore every original byte when candidate readiness rejects an update."""

    layout = _installed_023_layout(tmp_path)
    path = runtime_configuration_path(layout)
    original = path.read_bytes()
    activation = _prepared_candidate(layout)

    activation.activate()
    assert path.read_bytes() != original
    activation.rollback()

    assert path.read_bytes() == original
    assert (
        ApplicationReleaseSelection(layout.root).load().current == _PREVIOUS_GENERATION
    )


def test_generation_commit_retains_candidate_runtime_record(tmp_path: Path) -> None:
    """Keep the candidate runtime identity after visible readiness is committed."""

    layout = _installed_023_layout(tmp_path)
    activation = _prepared_candidate(layout)
    activation.activate()
    selected = ApplicationReleaseSelection(layout.root).load().current

    activation.commit()

    payload = _runtime_payload(layout)
    selected_layout = layout.for_release_root(
        ApplicationReleaseSelection(layout.root).generation_root(selected)
    )
    assert payload["runtime_root"] == str(selected_layout.runtime_dir)
    assert payload["python_executable"] == str(selected_layout.runtime_python)
    assert payload["bootstrap_status"] == "ready"
    assert not update_journal_path(layout).exists()


def test_interrupted_activation_restores_runtime_record_and_generation(
    tmp_path: Path,
) -> None:
    """Recover both persisted selections after termination before readiness."""

    layout = _installed_023_layout(tmp_path)
    path = runtime_configuration_path(layout)
    original = path.read_bytes()
    snapshot = RuntimeConfigurationSnapshot.capture(layout)
    selection = ApplicationReleaseSelection(layout.root)
    candidate_root = selection.prepare(
        generation=_CANDIDATE_GENERATION, version="0.23.1"
    )
    candidate_layout = layout.for_release_root(candidate_root)
    candidate_layout.app_dir.mkdir()
    candidate_layout.runtime_python.parent.mkdir(parents=True)
    candidate_layout.runtime_python.write_text("python", encoding="utf-8")
    selected = selection.activate(generation=_CANDIDATE_GENERATION)
    journal = UpdateActivationJournal(
        had_app=True,
        had_runtime=True,
        phase=ACTIVATED_PHASE,
        successful_state=_updated_state(),
        transaction_id=_CANDIDATE_GENERATION,
        candidate_generation=_CANDIDATE_GENERATION,
        previous_generation=selected.previous,
        candidate_sha256="a" * 64,
        runtime_configuration_snapshot=snapshot,
    )
    write_update_journal_data(update_journal_path(layout), journal.to_json())
    select_candidate_runtime_configuration(
        layout=layout,
        candidate_layout=candidate_layout,
        snapshot=snapshot,
    )

    assert recover_interrupted_update(layout)

    assert path.read_bytes() == original
    assert selection.load().current == _PREVIOUS_GENERATION
    assert not update_journal_path(layout).exists()


def _installed_023_layout(tmp_path: Path) -> InstallLayout:
    """Create the generation-backed runtime record emitted by a 0.23.0 install."""

    layout = InstallLayout.from_root(tmp_path / "SugarSubstitute")
    selection = ApplicationReleaseSelection(layout.root)
    release_root = selection.prepare(generation=_PREVIOUS_GENERATION, version="0.23.0")
    previous_layout = layout.for_release_root(release_root)
    previous_layout.app_dir.mkdir()
    previous_layout.runtime_python.parent.mkdir(parents=True)
    previous_layout.runtime_python.write_text("python", encoding="utf-8")
    selection.activate(generation=_PREVIOUS_GENERATION)
    selection.accept(generation=_PREVIOUS_GENERATION)
    path = runtime_configuration_path(layout)
    path.parent.mkdir(parents=True)
    path.write_text(
        "{\n"
        f'  "runtime_root": "{_json_path(layout.root / "runtime")}",\n'
        f'  "python_executable": "{_json_path(previous_layout.runtime_python)}",\n'
        '  "bootstrap_status": "ready",\n'
        '  "schema_version": "1",\n'
        '  "preserved_extension": "exact rollback proof"\n'
        "}\n",
        encoding="utf-8",
    )
    installation = InstallationConfiguration.create_default(layout.root)
    stale = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=previous_layout.runtime_python,
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    assert not FileSystemReadinessChecks().is_runtime_configuration_valid(stale)
    return layout


def _prepared_candidate(layout: InstallLayout) -> PendingUpdateActivation:
    """Prepare one paired release while retaining the caller's terminal decision."""

    activation = PendingUpdateActivation.begin(
        layout=layout,
        successful_state=_updated_state(),
        generation_backed=True,
        candidate_sha256="a" * 64,
    )
    activation.staging_directory.mkdir(parents=True)
    (activation.staging_directory / "main.py").write_text("", encoding="utf-8")
    activation.promote_app(
        StagedAppPayload(version="0.23.1", staging_dir=activation.staging_directory)
    )
    activation.prepare_runtime()
    candidate_layout = activation.preparation_layout
    candidate_layout.runtime_python.parent.mkdir(parents=True)
    candidate_layout.runtime_python.write_text("python", encoding="utf-8")
    return activation


def _runtime_payload(layout: InstallLayout) -> dict[str, object]:
    """Load the canonical runtime record as one JSON object."""

    payload = json.loads(runtime_configuration_path(layout).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _updated_state() -> LauncherUpdateState:
    """Return deterministic state committed after candidate readiness."""

    completed_at = datetime(2026, 9, 20, tzinfo=UTC)
    return LauncherUpdateState(
        installed_app_version="0.23.1",
        last_update_check_utc=completed_at,
        last_successful_update_utc=completed_at,
    )


def _json_path(path: Path) -> str:
    """Escape a native path for the hand-authored JSON regression fixture."""

    return str(path).replace("\\", "\\\\")

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

"""Own the persisted application-update journal and its fixed storage paths."""

from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.config import (
    CONFIG_SCHEMA_VERSION,
    LauncherConfig,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.application_release_selection import (
    ApplicationReleaseSelection,
    LEGACY_RELEASE_GENERATION,
)
from launcher.sugarsubstitute_launcher.update_runtime_configuration import (
    RuntimeConfigurationSnapshot,
)

_JOURNAL_SCHEMA_VERSION = 6
_JOURNAL_NAME = "pending-app-update.json"
PREPARING_PHASE = "preparing"
COMMITTED_PHASE = "committed"
ACTIVATED_PHASE = "activated"


class UpdateRecoveryError(RuntimeError):
    """Report pending update state that cannot be recovered safely."""


@dataclass(frozen=True, slots=True)
class UpdateActivationJournal:
    """Describe rollback boundaries and state selected by a committed activation."""

    had_app: bool
    had_runtime: bool
    phase: str
    successful_state: LauncherUpdateState
    successful_config: LauncherConfig | None = None
    transaction_id: str | None = None
    candidate_generation: str | None = None
    previous_generation: str | None = None
    candidate_sha256: str | None = None
    runtime_configuration_snapshot: RuntimeConfigurationSnapshot | None = None

    def to_json(self) -> dict[str, object]:
        """Return the stable persisted journal representation."""

        return {
            "had_app": self.had_app,
            "had_runtime": self.had_runtime,
            "phase": self.phase,
            "schema_version": (
                _JOURNAL_SCHEMA_VERSION
                if self.candidate_generation is not None
                else 3
                if self.transaction_id
                else 2
            ),
            "transaction_id": self.transaction_id,
            "candidate_generation": self.candidate_generation,
            "previous_generation": self.previous_generation,
            "candidate_sha256": self.candidate_sha256,
            "runtime_configuration_snapshot": (
                self.runtime_configuration_snapshot.to_json()
                if self.runtime_configuration_snapshot is not None
                else None
            ),
            "successful_state": self.successful_state.to_json(),
            "successful_config": (
                self.successful_config.to_json() if self.successful_config else None
            ),
        }


def load_update_journal(layout: InstallLayout) -> UpdateActivationJournal | None:
    """Load one valid pending-update journal or fail closed on corruption."""

    path = update_journal_path(layout)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        raise UpdateRecoveryError(
            f"Pending update journal is unreadable: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise UpdateRecoveryError(f"Pending update journal is invalid: {path}")
    schema_version = payload.get("schema_version")
    if type(schema_version) is not int or schema_version not in (
        1,
        2,
        3,
        4,
        5,
        _JOURNAL_SCHEMA_VERSION,
    ):
        raise UpdateRecoveryError(
            f"Pending update journal has an unsupported schema: {path}"
        )
    had_app = payload.get("had_app")
    had_runtime = payload.get("had_runtime")
    phase = payload.get("phase")
    successful_state = payload.get("successful_state")
    if (
        not isinstance(had_app, bool)
        or not isinstance(had_runtime, bool)
        or not isinstance(phase, str)
        or phase not in {PREPARING_PHASE, ACTIVATED_PHASE, COMMITTED_PHASE}
        or not isinstance(successful_state, dict)
    ):
        raise UpdateRecoveryError(f"Pending update journal is invalid: {path}")
    try:
        parsed_state = LauncherUpdateState.from_json(successful_state)
    except (TypeError, ValueError) as error:
        raise UpdateRecoveryError(
            f"Pending update journal contains invalid state: {path}"
        ) from error
    transaction_id = payload.get("transaction_id") if schema_version >= 3 else None
    if schema_version >= 3 and (
        not isinstance(transaction_id, str)
        or len(transaction_id) != 32
        or any(character not in "0123456789abcdef" for character in transaction_id)
    ):
        raise UpdateRecoveryError(
            "Pending activation has an invalid transaction identity."
        )
    candidate_generation = (
        payload.get("candidate_generation") if schema_version >= 4 else None
    )
    if schema_version >= 4 and not _valid_generation(candidate_generation):
        raise UpdateRecoveryError(
            "Pending activation has an invalid candidate generation."
        )
    previous_generation = (
        payload.get("previous_generation") if schema_version >= 4 else None
    )
    if previous_generation is not None and not _valid_generation(
        previous_generation, allow_legacy=True
    ):
        raise UpdateRecoveryError(
            "Pending activation has an invalid previous generation."
        )
    candidate_sha256 = payload.get("candidate_sha256") if schema_version >= 5 else None
    if candidate_sha256 is not None and not _valid_sha256(candidate_sha256):
        raise UpdateRecoveryError("Pending activation has an invalid candidate digest.")
    try:
        runtime_configuration_snapshot = (
            RuntimeConfigurationSnapshot.from_json(
                payload.get("runtime_configuration_snapshot")
            )
            if schema_version >= 6
            else None
        )
    except ValueError as error:
        raise UpdateRecoveryError(
            "Pending activation has an invalid runtime configuration snapshot."
        ) from error
    journal = UpdateActivationJournal(
        had_app=had_app,
        had_runtime=had_runtime,
        phase=phase,
        successful_state=parsed_state,
        successful_config=_load_successful_config(
            payload,
            layout,
            candidate_generation=(
                candidate_generation if isinstance(candidate_generation, str) else None
            ),
        ),
        transaction_id=transaction_id if isinstance(transaction_id, str) else None,
        candidate_generation=(
            candidate_generation if isinstance(candidate_generation, str) else None
        ),
        previous_generation=(
            previous_generation if isinstance(previous_generation, str) else None
        ),
        candidate_sha256=(
            candidate_sha256 if isinstance(candidate_sha256, str) else None
        ),
        runtime_configuration_snapshot=runtime_configuration_snapshot,
    )
    if journal.transaction_id is not None:
        activation_directory(layout, journal)
    return journal


def _load_successful_config(
    payload: dict[str, object],
    layout: InstallLayout,
    *,
    candidate_generation: str | None,
) -> LauncherConfig | None:
    """Accept versioned configuration publication only for this installation."""
    if payload.get("schema_version") == 1:
        return None
    value = payload.get("successful_config")
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != CONFIG_SCHEMA_VERSION
    ):
        raise UpdateRecoveryError("Pending activation contains invalid configuration.")
    try:
        config = LauncherConfig.from_json(value)
        expected_layout = (
            layout.for_release_root(
                ApplicationReleaseSelection(layout.root).generation_root(
                    candidate_generation
                )
            )
            if candidate_generation is not None
            else layout
        )
        if (
            config.install_root.resolve() != layout.root.resolve()
            or config.app_dir.resolve() != expected_layout.app_dir.resolve()
            or config.runtime_python.resolve()
            != expected_layout.runtime_python.resolve()
        ):
            raise ValueError("Configuration targets another installation.")
    except (TypeError, ValueError, OSError) as error:
        raise UpdateRecoveryError(
            "Pending activation configuration does not match its installation."
        ) from error
    return config


def update_journal_path(layout: InstallLayout) -> Path:
    """Return the single durable pending-update journal path."""

    return layout.launcher_dir / _JOURNAL_NAME


def activation_directory(
    layout: InstallLayout, journal: UpdateActivationJournal
) -> Path:
    """Resolve transaction storage without permitting a redirected parent root."""
    if journal.transaction_id is None:
        return layout.root
    directory = layout.root / ".activation" / journal.transaction_id
    if not directory.resolve().is_relative_to(layout.root.resolve()):
        raise UpdateRecoveryError("Activation storage escapes its installation.")
    return directory


def previous_app_dir(layout: InstallLayout, journal: UpdateActivationJournal) -> Path:
    """Return this transaction's application backup, including legacy paths."""
    return activation_directory(layout, journal) / "app_previous"


def previous_runtime_dir(
    layout: InstallLayout, journal: UpdateActivationJournal
) -> Path:
    """Return this transaction's runtime backup, including legacy paths."""
    return activation_directory(layout, journal) / "runtime_previous"


def staged_app_dir(layout: InstallLayout, journal: UpdateActivationJournal) -> Path:
    """Return staging owned by the activation's persisted transaction identity."""
    if journal.candidate_generation is not None:
        return candidate_release_root(layout, journal) / "app"
    return activation_directory(layout, journal) / "app_next"


def candidate_release_root(
    layout: InstallLayout, journal: UpdateActivationJournal
) -> Path:
    """Return preparation storage for a generation-backed activation."""

    if journal.candidate_generation is None:
        raise UpdateRecoveryError("Activation does not own a release generation.")
    return ApplicationReleaseSelection(layout.root).candidate_root(
        journal.candidate_generation
    )


def _valid_generation(value: object, *, allow_legacy: bool = False) -> bool:
    """Return whether one persisted generation identity is path-safe."""

    if allow_legacy and value == LEGACY_RELEASE_GENERATION:
        return True
    return (
        isinstance(value, str)
        and len(value) == 32
        and all(character in "0123456789abcdef" for character in value)
    )


def _valid_sha256(value: object) -> bool:
    """Return whether one persisted artifact digest is canonical SHA256."""

    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def remove_update_journal(layout: InstallLayout) -> None:
    """Remove the pending-update journal after a terminal transition."""

    try:
        update_journal_path(layout).unlink()
    except FileNotFoundError:
        pass


def write_update_journal_data(path: Path, payload: dict[str, object]) -> None:
    """Atomically persist a stable JSON object in launcher-owned state."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(
        f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass

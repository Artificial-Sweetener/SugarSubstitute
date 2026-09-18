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

"""Hold application update ownership from preparation through its terminal decision."""

from __future__ import annotations
from contextlib import ExitStack
import logging
import secrets
from pathlib import Path
from launcher.sugarsubstitute_launcher.payload_models import (
    StagedAppPayload,
    AppPayloadInstallResult,
)
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.config import LauncherConfig
from launcher.sugarsubstitute_launcher.update_activation_publication import (
    publish_committed_activation,
)
from launcher.sugarsubstitute_launcher.update_state import LauncherUpdateState
from launcher.sugarsubstitute_launcher.update_rollback_reporting import (
    discard_update_rollback_report,
)
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    UpdateActivationJournal,
    PREPARING_PHASE,
    COMMITTED_PHASE,
    write_update_journal_data,
    update_journal_path,
    previous_runtime_dir,
    previous_app_dir,
    remove_update_journal,
    activation_directory,
    staged_app_dir,
    load_update_journal,
    UpdateRecoveryError,
)
from launcher.sugarsubstitute_launcher.update_activation_recovery import (
    recover_interrupted_update,
)
from launcher.sugarsubstitute_launcher.update_activation_cleanup import (
    retire_committed_activation,
)
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationOwnership,
    installation_mutation,
)

_LOGGER = logging.getLogger(__name__)


class PendingUpdateActivation:
    """Hold a candidate application until its caller's acceptance decision."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        journal: UpdateActivationJournal,
        ownership: ExitStack,
        operation: InstallationMutationOwnership,
    ) -> None:
        """Store the durable rollback record and state to commit."""

        self._layout = layout
        self._journal = journal
        self._finished = False
        self._ownership = ownership
        self._operation = operation
        self._runtime_prepared = False
        self._app_promoted = False

    @classmethod
    def begin(
        cls,
        *,
        layout: InstallLayout,
        successful_state: LauncherUpdateState,
        successful_config: LauncherConfig | None = None,
        operation: InstallationMutationOwnership | None = None,
    ) -> PendingUpdateActivation:
        """Persist recovery intent before any installed directory is replaced."""

        ownership = ExitStack()
        operation = ownership.enter_context(
            installation_mutation(layout.root, ownership=operation)
        )
        try:
            if update_journal_path(layout).exists():
                raise UpdateRecoveryError(
                    "A pending activation must be recovered before another is created."
                )
            journal = UpdateActivationJournal(
                had_app=layout.app_dir.exists(),
                had_runtime=layout.runtime_dir.exists(),
                phase=PREPARING_PHASE,
                successful_state=successful_state,
                successful_config=successful_config,
                transaction_id=secrets.token_hex(16),
            )
            activation_directory(layout, journal).mkdir(parents=True, exist_ok=False)
            write_update_journal_data(update_journal_path(layout), journal.to_json())
            _LOGGER.info(
                "Prepared application activation",
                extra={"transaction_id": journal.transaction_id},
            )
            return cls(
                layout=layout,
                journal=journal,
                ownership=ownership,
                operation=operation,
            )
        except BaseException:
            ownership.close()
            raise

    @property
    def layout(self) -> InstallLayout:
        """Expose the installation identity owned by this activation."""
        return self._layout

    @property
    def staging_directory(self) -> Path:
        """Expose staging storage belonging exclusively to this activation."""
        return staged_app_dir(self._layout, self._journal)

    def promote_app(self, staged: StagedAppPayload) -> AppPayloadInstallResult:
        """Retire and promote application content under the recorded backup identity."""
        if self._finished or self._app_promoted:
            raise RuntimeError("Application activation cannot promote another payload.")
        self._require_current_ownership()
        if staged.staging_dir.resolve() != self.staging_directory.resolve():
            raise ValueError("Staged payload does not belong to this activation.")
        previous = previous_app_dir(self._layout, self._journal)
        if self._layout.app_dir.exists():
            self._layout.app_dir.replace(previous)
        staged.staging_dir.replace(self._layout.app_dir)
        self._app_promoted = True
        _LOGGER.info(
            "Promoted app payload.",
            extra={
                "version": staged.version,
                "transaction_id": self._journal.transaction_id,
            },
        )
        return AppPayloadInstallResult(
            version=staged.version, app_dir=self._layout.app_dir
        )

    def prepare_runtime(self) -> None:
        """Preserve the prior runtime and create a clean candidate runtime."""

        if self._finished or self._runtime_prepared:
            raise RuntimeError("Update activation is already finished.")
        self._require_current_ownership()
        previous_runtime = previous_runtime_dir(self._layout, self._journal)
        if self._layout.runtime_dir.exists():
            self._layout.runtime_dir.replace(previous_runtime)
        self._layout.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_prepared = True

    def commit(self) -> None:
        """Record the proven version and retire rollback directories."""

        if self._finished:
            return
        self._require_current_ownership(allow_committed=True)
        committed_journal = UpdateActivationJournal(
            had_app=self._journal.had_app,
            had_runtime=self._journal.had_runtime,
            phase=COMMITTED_PHASE,
            successful_state=self._journal.successful_state,
            successful_config=self._journal.successful_config,
            transaction_id=self._journal.transaction_id,
        )
        write_update_journal_data(
            update_journal_path(self._layout),
            committed_journal.to_json(),
        )
        publish_committed_activation(self._layout, committed_journal)
        discard_update_rollback_report(self._layout.root)
        retire_committed_activation(self._layout, self._journal)
        remove_update_journal(self._layout)
        self._finished = True
        self._ownership.close()
        _LOGGER.info(
            "Committed application activation",
            extra={"transaction_id": self._journal.transaction_id},
        )

    def rollback(self) -> None:
        """Recover the durable decision and release this execution even if recovery fails."""

        if self._finished:
            return
        self._operation.validate(self._layout.root.resolve())
        try:
            if load_update_journal(self._layout) is not None:
                self._require_current_ownership(allow_committed=True)
                recover_interrupted_update(self._layout, ownership=self._operation)
        finally:
            self._finished = True
            self._ownership.close()

    def _require_current_ownership(self, *, allow_committed: bool = False) -> None:
        """Reject a retired actor before it can replace another transaction's intent."""
        self._operation.validate(self._layout.root.resolve())
        current = load_update_journal(self._layout)
        if current is None or current.transaction_id != self._journal.transaction_id:
            raise UpdateRecoveryError("Application activation ownership has changed.")
        if current.phase == COMMITTED_PHASE and not allow_committed:
            raise UpdateRecoveryError("Application activation is already committed.")

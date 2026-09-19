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

"""Restore or finalize persisted application updates under mutation ownership."""

from __future__ import annotations
import logging
from pathlib import Path
from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    COMMITTED_PHASE,
    load_update_journal,
    previous_app_dir,
    previous_runtime_dir,
    remove_update_journal,
)
from launcher.sugarsubstitute_launcher.application_release_selection import (
    ApplicationReleaseSelection,
)
from launcher.sugarsubstitute_launcher.update_activation_cleanup import (
    remove_update_directory,
    retire_activation_storage,
    retire_committed_activation,
)
from sugarsubstitute_shared.installation_mutation import (
    InstallationMutationOwnership,
    installation_mutation,
)
from launcher.sugarsubstitute_launcher.update_activation_publication import (
    publish_committed_activation,
)

_LOGGER = logging.getLogger(__name__)


def recover_interrupted_update(
    layout: InstallLayout, *, ownership: InstallationMutationOwnership | None = None
) -> bool:
    """Rollback a journaled update left incomplete by process termination."""

    with installation_mutation(layout.root, ownership=ownership):
        journal = load_update_journal(layout)
        if journal is None:
            return False
        if journal.candidate_generation is not None:
            selection = ApplicationReleaseSelection(layout.root)
            if journal.phase == COMMITTED_PHASE:
                publish_committed_activation(layout, journal)
                selection.accept(generation=journal.candidate_generation)
                selection.prune()
            else:
                selection.recover_failed_activation(
                    generation=journal.candidate_generation
                )
            remove_update_journal(layout)
            _LOGGER.warning(
                "Recovered generation-backed app update.",
                extra={
                    "transaction_id": journal.transaction_id,
                    "phase": journal.phase,
                },
            )
            return True
        if journal.phase == COMMITTED_PHASE:
            publish_committed_activation(layout, journal)
            retire_committed_activation(layout, journal)
            remove_update_journal(layout)
            _LOGGER.warning(
                "Completed an interrupted proven app update.",
                extra={"transaction_id": journal.transaction_id},
            )
            return True
        restore_update_directory(
            active=layout.runtime_dir,
            previous=previous_runtime_dir(layout, journal),
            existed_before=journal.had_runtime,
        )
        restore_update_directory(
            active=layout.app_dir,
            previous=previous_app_dir(layout, journal),
            existed_before=journal.had_app,
        )
        retire_activation_storage(layout, journal)
        remove_update_journal(layout)
        _LOGGER.warning(
            "Recovered an interrupted app update before launch.",
            extra={"transaction_id": journal.transaction_id},
        )
        return True


def restore_update_directory(
    *, active: Path, previous: Path, existed_before: bool
) -> None:
    """Restore one preserved directory or remove a newly introduced directory."""

    if previous.exists():
        remove_update_directory(active)
        previous.replace(active)
        return
    if not existed_before:
        remove_update_directory(active)

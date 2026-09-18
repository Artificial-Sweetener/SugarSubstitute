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

"""Retire obsolete activation storage without changing a proven installation."""

from __future__ import annotations

import logging
from pathlib import Path
import shutil

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from launcher.sugarsubstitute_launcher.update_activation_journal import (
    UpdateActivationJournal,
    activation_directory,
    previous_app_dir,
    previous_runtime_dir,
    staged_app_dir,
)

_LOGGER = logging.getLogger(__name__)


def retire_committed_activation(
    layout: InstallLayout, journal: UpdateActivationJournal
) -> None:
    """Apply the same nonblocking disposal policy after commit and crash recovery."""
    for path in (
        previous_app_dir(layout, journal),
        previous_runtime_dir(layout, journal),
    ):
        _retire_obsolete_directory(path, journal)
    retire_activation_storage(layout, journal)


def retire_activation_storage(
    layout: InstallLayout, journal: UpdateActivationJournal
) -> None:
    """Retain inaccessible staging after the authoritative transition has finished."""
    _retire_obsolete_directory(staged_app_dir(layout, journal), journal)
    if journal.transaction_id is None:
        return
    directory = activation_directory(layout, journal)
    try:
        directory.rmdir()
    except FileNotFoundError:
        pass
    except OSError:
        _LOGGER.warning(
            "Retained activation storage that could not be retired",
            extra={"transaction_id": journal.transaction_id},
            exc_info=True,
        )


def _retire_obsolete_directory(path: Path, journal: UpdateActivationJournal) -> None:
    """Keep a disposable storage failure separate from installation validity."""
    try:
        remove_update_directory(path)
    except OSError:
        _LOGGER.warning(
            "Retained obsolete activation directory | path=%s",
            path,
            extra={"transaction_id": journal.transaction_id},
            exc_info=True,
        )


def remove_update_directory(path: Path) -> None:
    """Remove one owned directory; restoration callers must observe any failure."""
    if path.exists():
        shutil.rmtree(path)

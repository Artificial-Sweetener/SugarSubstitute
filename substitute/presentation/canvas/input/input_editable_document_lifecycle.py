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

"""Persist and restore the authoritative editable Input document."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from cutecanvas import PreparedDocumentRestore

from substitute.application.workspace_state.session_persistence import (
    PreparedSessionPersistence,
)
from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
    log_warning,
)

_LOGGER = get_logger("presentation.canvas.input.input_editable_document_lifecycle")


class EditableInputDocumentPort(Protocol):
    """Describe complete Input document persistence used by the host lifecycle."""

    def has_editable_content(self) -> bool:
        """Return whether the document has content requiring an archive."""

    def restore_editable_document(self, path: Path) -> tuple[UUID, ...]:
        """Restore every editable composition from one archive path."""

    def restore_prepared_editable_document(
        self,
        prepared: PreparedDocumentRestore,
    ) -> tuple[UUID, ...]:
        """Install every composition from one decoded archive."""

    def prepare_editable_document_save(
        self,
        path: Path,
    ) -> PreparedSessionPersistence:
        """Capture editable authority for later background persistence."""


class InputEditableDocumentLifecycle:
    """Align one CuteCanvas document through serial session persistence callbacks."""

    def __init__(
        self,
        *,
        document: EditableInputDocumentPort,
        archive_path: Path,
    ) -> None:
        """Store the document and its application-owned session archive path."""

        self._document = document
        self._archive_path = Path(archive_path)
        self._restore_attempted = False
        self._restored_composition_ids: tuple[UUID, ...] = ()
        self._document_revision = 0
        self._persisted_revision = 0 if self._archive_path.is_file() else -1

    @property
    def archive_path(self) -> Path:
        """Return the complete editable archive path."""

        return self._archive_path

    @property
    def restored_composition_ids(self) -> tuple[UUID, ...]:
        """Return composition identities restored during this process lifetime."""

        return self._restored_composition_ids

    def mark_changed(self) -> None:
        """Advance the authoritative revision after one durable document edit."""

        self._document_revision += 1

    def prepare_session_persistence(self) -> PreparedSessionPersistence:
        """Capture current authority and return background-safe persistence."""

        if self._document.has_editable_content():
            captured_revision = self._document_revision
            prepared = self._document.prepare_editable_document_save(self._archive_path)

            def persist_captured_document() -> None:
                """Write one capture unless an earlier queued save made it current."""

                already_persisted = (
                    self._persisted_revision >= captured_revision
                    and self._archive_path.is_file()
                )
                if already_persisted:
                    self._log_current_archive_skip()
                    return
                prepared.persist()
                self._persisted_revision = max(
                    self._persisted_revision,
                    captured_revision,
                )

            return PreparedSessionPersistence(
                "editable_input_document",
                persist_captured_document,
            )

        def remove_stale_archive() -> None:
            """Remove obsolete persisted authority in the background phase."""
            if not self._remove_stale_archive():
                raise OSError("failed to remove stale editable Input document")

        return PreparedSessionPersistence(
            "editable_input_document",
            remove_stale_archive,
        )

    def restore_before_workspace_assets(
        self,
        prepared: PreparedDocumentRestore | None = None,
    ) -> bool:
        """Restore editable authority once before file-backed fallback hydration."""

        if self._restore_attempted:
            return bool(self._restored_composition_ids)
        self._restore_attempted = True
        if not self._archive_path.is_file():
            log_debug(
                _LOGGER,
                "Editable Input document archive is unavailable",
                archive_path=str(self._archive_path),
            )
            return False
        try:
            composition_ids = (
                self._document.restore_editable_document(self._archive_path)
                if prepared is None
                else self._document.restore_prepared_editable_document(prepared)
            )
        except (TypeError, ValueError) as error:
            self._invalidate_rejected_archive(error)
            return False
        except (OSError, RuntimeError) as error:
            log_exception(
                _LOGGER,
                "Failed to restore editable Input document; file assets remain available",
                archive_path=str(self._archive_path),
                error=error,
            )
            return False
        self._restored_composition_ids = composition_ids
        self._persisted_revision = self._document_revision
        log_info(
            _LOGGER,
            "Restored editable Input document",
            archive_path=str(self._archive_path),
            composition_ids=tuple(str(value) for value in composition_ids),
        )
        return True

    def _log_current_archive_skip(self) -> None:
        """Record that durable editable authority already matches the archive."""

        log_debug(
            _LOGGER,
            "Skipped current editable Input document archive",
            archive_path=str(self._archive_path),
        )

    def _invalidate_rejected_archive(self, error: Exception) -> None:
        """Discard structurally rejected cache state before file-backed rebuild."""

        try:
            self._archive_path.unlink(missing_ok=True)
        except OSError as removal_error:
            log_exception(
                _LOGGER,
                "Failed to invalidate rejected editable Input document cache",
                archive_path=str(self._archive_path),
                error=removal_error,
                rejection_reason=str(error),
            )
            return
        self._persisted_revision = -1
        log_warning(
            _LOGGER,
            "Invalidated rejected editable Input document cache; file assets remain available",
            archive_path=str(self._archive_path),
            error_type=type(error).__name__,
            rejection_reason=str(error),
        )

    def _remove_stale_archive(self) -> bool:
        """Remove prior document state when the current session has no Input content."""

        if not self._archive_path.exists():
            self._persisted_revision = self._document_revision
            return True
        try:
            self._archive_path.unlink()
        except OSError as error:
            log_exception(
                _LOGGER,
                "Failed to remove stale editable Input document",
                archive_path=str(self._archive_path),
                error=error,
            )
            return False
        self._persisted_revision = self._document_revision
        log_debug(
            _LOGGER,
            "Removed stale editable Input document",
            archive_path=str(self._archive_path),
        )
        return True


__all__ = ["InputEditableDocumentLifecycle"]

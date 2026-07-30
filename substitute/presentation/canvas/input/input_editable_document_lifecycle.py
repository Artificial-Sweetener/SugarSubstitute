#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Persist and restore the authoritative editable Input document."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from substitute.shared.logging.logger import (
    get_logger,
    log_debug,
    log_exception,
    log_info,
)

_LOGGER = get_logger("presentation.canvas.input.input_editable_document_lifecycle")


class EditableInputDocumentPort(Protocol):
    """Describe complete Input document persistence used by the host lifecycle."""

    def has_editable_content(self) -> bool:
        """Return whether the document has content requiring an archive."""

    def save_editable_document(self, path: Path) -> tuple[UUID, ...]:
        """Persist every editable composition beneath one archive path."""

    def restore_editable_document(self, path: Path) -> tuple[UUID, ...]:
        """Restore every editable composition from one archive path."""


class InputEditableDocumentLifecycle:
    """Keep one complete CuteCanvas document aligned with session persistence."""

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

    @property
    def archive_path(self) -> Path:
        """Return the complete editable archive path."""

        return self._archive_path

    @property
    def restored_composition_ids(self) -> tuple[UUID, ...]:
        """Return composition identities restored during this process lifetime."""

        return self._restored_composition_ids

    def save_before_session_snapshot(self) -> bool:
        """Persist current editable authority before its referencing session JSON."""

        if not self._document.has_editable_content():
            return self._remove_stale_archive()
        try:
            composition_ids = self._document.save_editable_document(self._archive_path)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            log_exception(
                _LOGGER,
                "Failed to persist editable Input document",
                archive_path=str(self._archive_path),
                error=error,
            )
            return False
        log_debug(
            _LOGGER,
            "Persisted editable Input document",
            archive_path=str(self._archive_path),
            composition_ids=tuple(str(value) for value in composition_ids),
        )
        return True

    def restore_before_workspace_assets(self) -> bool:
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
            composition_ids = self._document.restore_editable_document(
                self._archive_path
            )
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            log_exception(
                _LOGGER,
                "Failed to restore editable Input document; file assets remain available",
                archive_path=str(self._archive_path),
                error=error,
            )
            return False
        self._restored_composition_ids = composition_ids
        log_info(
            _LOGGER,
            "Restored editable Input document",
            archive_path=str(self._archive_path),
            composition_ids=tuple(str(value) for value in composition_ids),
        )
        return True

    def _remove_stale_archive(self) -> bool:
        """Remove prior document state when the current session has no Input content."""

        if not self._archive_path.exists():
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
        log_debug(
            _LOGGER,
            "Removed stale editable Input document",
            archive_path=str(self._archive_path),
        )
        return True


__all__ = ["InputEditableDocumentLifecycle"]

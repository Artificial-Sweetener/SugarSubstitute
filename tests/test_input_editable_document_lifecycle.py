#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Verify complete Input document lifecycle ordering and failure behavior."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from substitute.presentation.canvas.input.input_editable_document_lifecycle import (
    InputEditableDocumentLifecycle,
)


class _Document:
    """Record complete document persistence requests."""

    def __init__(self, *, content: bool = True) -> None:
        """Initialize deterministic editable content and call history."""

        self.content = content
        self.composition_ids = (uuid4(),)
        self.saved: list[Path] = []
        self.restored: list[Path] = []
        self.save_error: Exception | None = None
        self.restore_error: Exception | None = None

    def has_editable_content(self) -> bool:
        """Return the configured content state."""

        return self.content

    def save_editable_document(self, path: Path) -> tuple[UUID, ...]:
        """Record a save or raise its configured failure."""

        self.saved.append(path)
        if self.save_error is not None:
            raise self.save_error
        return self.composition_ids

    def restore_editable_document(self, path: Path) -> tuple[UUID, ...]:
        """Record a restore or raise its configured failure."""

        self.restored.append(path)
        if self.restore_error is not None:
            raise self.restore_error
        return self.composition_ids


def test_lifecycle_persists_before_session_and_restores_only_once(
    tmp_path: Path,
) -> None:
    """Repeated erratic restore requests should install an archive exactly once."""

    archive = tmp_path / "input.ccanvas"
    archive.write_bytes(b"archive")
    document = _Document()
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )

    assert lifecycle.save_before_session_snapshot()
    assert lifecycle.restore_before_workspace_assets()
    assert lifecycle.restore_before_workspace_assets()
    assert document.saved == [archive]
    assert document.restored == [archive]
    assert lifecycle.restored_composition_ids == document.composition_ids


def test_lifecycle_fails_closed_and_removes_stale_empty_state(
    tmp_path: Path,
) -> None:
    """Failed writes block session capture and empty sessions retire prior state."""

    archive = tmp_path / "input.ccanvas"
    archive.write_bytes(b"stale")
    document = _Document()
    document.save_error = OSError("disk full")
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )
    assert lifecycle.save_before_session_snapshot() is False
    assert archive.exists()

    empty_document = _Document(content=False)
    empty_lifecycle = InputEditableDocumentLifecycle(
        document=empty_document,
        archive_path=archive,
    )
    assert empty_lifecycle.save_before_session_snapshot()
    assert not archive.exists()


def test_lifecycle_leaves_file_fallback_available_after_bad_archive(
    tmp_path: Path,
) -> None:
    """Malformed editable state should not prevent legacy asset restoration."""

    archive = tmp_path / "input.ccanvas"
    archive.write_bytes(b"bad")
    document = _Document()
    document.restore_error = ValueError("invalid archive")
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )

    assert lifecycle.restore_before_workspace_assets() is False
    assert lifecycle.restore_before_workspace_assets() is False
    assert document.restored == [archive]
    assert archive.exists()

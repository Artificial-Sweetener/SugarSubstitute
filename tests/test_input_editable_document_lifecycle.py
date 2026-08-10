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

"""Verify complete Input document lifecycle ordering and failure behavior."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from substitute.application.workspace_state import PreparedSessionPersistence
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
        self.prepared: list[Path] = []
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

    def prepare_editable_document_save(
        self,
        path: Path,
    ) -> PreparedSessionPersistence:
        """Capture a deferred save without performing persistence."""
        self.prepared.append(path)

        def persist() -> None:
            """Persist and discard returned composition identities."""
            self.save_editable_document(path)

        return PreparedSessionPersistence(
            "fixture_input_document",
            persist,
        )


def test_lifecycle_skips_current_archive_and_restores_only_once(
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

    prepared = lifecycle.prepare_session_persistence()
    prepared.persist()
    assert lifecycle.restore_before_workspace_assets()
    assert lifecycle.restore_before_workspace_assets()
    assert document.prepared == [archive]
    assert document.saved == []
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
    lifecycle.mark_changed()
    failed_save = lifecycle.prepare_session_persistence()
    try:
        failed_save.persist()
    except OSError as error:
        assert str(error) == "disk full"
    else:
        raise AssertionError("expected the fixture archive write to fail")
    assert archive.exists()

    empty_document = _Document(content=False)
    empty_lifecycle = InputEditableDocumentLifecycle(
        document=empty_document,
        archive_path=archive,
    )
    empty_lifecycle.prepare_session_persistence().persist()
    assert not archive.exists()


def test_lifecycle_prepares_document_without_writing_until_background_phase(
    tmp_path: Path,
) -> None:
    """Separate owner-thread document capture from archive persistence."""

    archive = tmp_path / "input.ccanvas"
    document = _Document()
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )

    prepared = lifecycle.prepare_session_persistence()

    assert document.prepared == [archive]
    assert document.saved == []
    prepared.persist()
    assert document.saved == [archive]


def test_lifecycle_skips_redundant_archive_after_successful_persistence(
    tmp_path: Path,
) -> None:
    """Do not rewrite an unchanged large archive at autosave or shutdown."""

    archive = tmp_path / "input.ccanvas"
    document = _Document()
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )

    lifecycle.mark_changed()
    lifecycle.prepare_session_persistence().persist()
    archive.write_bytes(b"persisted archive")
    lifecycle.prepare_session_persistence().persist()

    assert document.prepared == [archive, archive]
    assert document.saved == [archive]


def test_lifecycle_retry_remains_dirty_after_failed_archive_persistence(
    tmp_path: Path,
) -> None:
    """Retry the same document revision when its first archive write fails."""

    archive = tmp_path / "input.ccanvas"
    document = _Document()
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )
    lifecycle.mark_changed()
    document.save_error = OSError("disk full")

    with_error = lifecycle.prepare_session_persistence()
    try:
        with_error.persist()
    except OSError:
        pass
    else:
        raise AssertionError("expected the fixture archive write to fail")
    document.save_error = None
    lifecycle.prepare_session_persistence().persist()

    assert document.prepared == [archive, archive]
    assert document.saved == [archive, archive]


def test_lifecycle_coalesces_two_prepared_saves_for_one_revision(
    tmp_path: Path,
) -> None:
    """Let the first queued archive make an equivalent second capture redundant."""

    archive = tmp_path / "input.ccanvas"
    document = _Document()
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )
    lifecycle.mark_changed()

    first = lifecycle.prepare_session_persistence()
    second = lifecycle.prepare_session_persistence()
    first.persist()
    archive.write_bytes(b"persisted archive")
    second.persist()

    assert document.prepared == [archive, archive]
    assert document.saved == [archive]


def test_lifecycle_invalidates_bad_archive_before_file_backed_rebuild(
    tmp_path: Path,
) -> None:
    """Malformed cache state should be removed before file asset restoration."""

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
    assert not archive.exists()


def test_lifecycle_preserves_cache_after_transient_restore_failure(
    tmp_path: Path,
) -> None:
    """A runtime failure must not erase structurally valid cache authority."""

    archive = tmp_path / "input.ccanvas"
    archive.write_bytes(b"temporarily unavailable")
    document = _Document()
    document.restore_error = RuntimeError("restore service unavailable")
    lifecycle = InputEditableDocumentLifecycle(
        document=document,
        archive_path=archive,
    )

    assert lifecycle.restore_before_workspace_assets() is False
    assert archive.exists()

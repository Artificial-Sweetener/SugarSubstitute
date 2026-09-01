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

"""Verify explicit-save state transitions."""

from pathlib import Path

from substitute.application.workflows.unsaved_work_service import UnsavedWorkService


def test_dirty_state_survives_rename_and_orders_visible_workflows() -> None:
    """Dirty documents should follow identity changes and visible ordering."""

    service = UnsavedWorkService()
    service.mark_saved("one", Path("one.sugar"))
    service.mark_dirty("one")
    service.mark_dirty("two")
    service.rename("one", "renamed")

    assert service.state_for("renamed").source_path == Path("one.sugar")
    assert service.dirty_workflow_ids(("two", "renamed", "missing")) == (
        "two",
        "renamed",
    )


def test_restore_preserves_dirty_authority_and_source_path() -> None:
    """Recovery restoration should not silently mark unsaved work clean."""

    service = UnsavedWorkService()
    service.restore(
        "restored",
        dirty=True,
        source_path=Path("project.sugar"),
    )

    assert service.state_for("restored").dirty is True
    assert service.state_for("restored").source_path == Path("project.sugar")


def test_remove_forgets_closed_document_state() -> None:
    """Confirmed workflow closure should release its document-state record."""

    service = UnsavedWorkService()
    service.mark_dirty("closed")
    service.remove("closed")

    assert service.state_for("closed").dirty is False

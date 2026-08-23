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

"""Workflow inline-rename and progress-rekeying contracts."""

from __future__ import annotations


from tests.presentation.shell.workflow_surface.workflow_action_fakes import (
    _import_module,
)
from tests.presentation.shell.workflow_surface.workflow_action_support import (
    _build_view,
)


def test_rejected_inline_rename_restores_old_label() -> None:
    """Rejected inline renames should restore the existing workflow label."""

    mod = _import_module()
    view = _build_view()

    mod.WorkflowWorkspaceCoordinator(view).rename_workflow("wf-a", "bad/name")

    assert view.workflow_tabbar.itemMap["wf-a"].text() == "wf-a"


def test_accepted_inline_rename_rekeys_workflow_progress() -> None:
    """Accepted workflow renames should move runtime progress ownership."""

    mod = _import_module()
    view = _build_view()

    mod.WorkflowWorkspaceCoordinator(view).rename_workflow(
        "wf-a",
        "Renamed Workflow",
    )

    assert "progress:rename:wf-a:Renamed Workflow" in view.calls

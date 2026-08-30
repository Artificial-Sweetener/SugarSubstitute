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

"""Mount deterministic saved-segment sources for context-menu tests."""

from __future__ import annotations

from __future__ import annotations
from __future__ import annotations
from typing import Any, cast
from PySide6.QtWidgets import QWidget
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.features import (
    CatalogSnapshotIdentity,
    CatalogSnapshotReadiness,
    CatalogSnapshotStatus,
)
from substitute.presentation.editor.prompt_editor.shell import (
    PromptShellContextMenuOpening,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetMenuModel,
    PromptSegmentPresetSourceSnapshot,
)
from substitute.presentation.widgets.save_preset_dialog import PresetSaveScope
from substitute.domain.user_presets import GLOBAL_PRESET_ASSOCIATION
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.support.execution import immediate_prompt_task_executor_factory
from tests.presentation.editor.prompt_editor.context_menu.mounting import (
    ensure_qapp,
    wait_for_prompt_editor_projection,
)


class _PromptSegmentPresetSource:
    """Provide deterministic saved prompt segment data for context-menu tests."""

    def __init__(
        self,
        model: PromptSegmentPresetMenuModel | None = None,
    ) -> None:
        """Store menu model and saved calls."""

        self.scope = PresetSaveScope(
            title="Global",
            full_label="Global",
            association=GLOBAL_PRESET_ASSOCIATION,
        )
        self.model = model or PromptSegmentPresetMenuModel(
            save_scopes=(self.scope,),
        )
        self.saved: list[tuple[str, str, PresetSaveScope]] = []
        self.list_calls = 0

    def list_prompt_segment_presets(self) -> PromptSegmentPresetSourceSnapshot:
        """Return saved prompt segment insert actions."""

        self.list_calls += 1
        return PromptSegmentPresetSourceSnapshot(
            menu_model=self.model,
            catalog_identity=CatalogSnapshotIdentity(
                catalog_revision=self.list_calls,
                prompt_context_token=("checkpoint", "test"),
            ),
            status=CatalogSnapshotStatus(CatalogSnapshotReadiness.WARM),
        )

    def save_prompt_segment(
        self,
        *,
        label: str,
        text: str,
        scope: PresetSaveScope,
    ) -> None:
        """Record one save request."""

        self.saved.append((label, text, scope))


def create_prompt_editor_with_segments(
    prompt_widgets: list[QWidget],
    source: _PromptSegmentPresetSource,
) -> PromptEditor:
    """Create one prompt editor configured with prompt segment preset support."""

    ensure_qapp()
    host = QWidget()
    host.resize(440, 220)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_segment_preset_source=source,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 320, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.replaceBaselineSourceText("alpha beta gamma")
    wait_for_prompt_editor_projection(editor)
    prompt_widgets.extend([host, editor])
    return editor


def _trigger_save_prompt_segment(
    editor: PromptEditor,
    *,
    source_position: int,
    selected_text: str,
    selection_snapshot: tuple[int, int, str] | None,
) -> None:
    """Trigger the prompt-menu presenter's save-segment callback."""

    cast(Any, editor)._prompt_menu_presenter.prepare_prompt_menu_selection(
        selected_text=selected_text,
        selection_snapshot=selection_snapshot,
        reason="test_trigger_save_prompt_segment",
    )
    request = cast(Any, editor)._prompt_menu_presenter.prepared_prompt_menu_request(
        PromptShellContextMenuOpening(
            source_position=source_position,
            selected_text=selected_text,
            selection_snapshot=selection_snapshot,
        )
    )
    assert request.save_prompt_segment is not None
    request.save_prompt_segment()

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

"""Verify Prompt Editor wildcard Settings behavior."""

from __future__ import annotations
from pathlib import Path
from PySide6.QtWidgets import QWidget
from substitute.application.prompt_editor.features.preferences import (
    PromptEditorPreferenceService,
)
from substitute.application.prompt_wildcards import PromptWildcardPreferenceService
from substitute.infrastructure.persistence import (
    FilePromptEditorPreferenceRepository,
    FilePromptWildcardPreferenceRepository,
)
from substitute.presentation.settings.prompt_editor_page import PromptEditorSettingsPage
from tests.support.qt.lifecycle import ensure_qt_application


def test_prompt_editor_page_updates_wildcard_preference_service(
    tmp_path: Path,
) -> None:
    """Wildcard Settings controls should persist through the wildcard service."""

    app = ensure_qt_application()
    editor_service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path / "editor")
    )
    wildcard_service = PromptWildcardPreferenceService(
        FilePromptWildcardPreferenceRepository(tmp_path / "wildcards")
    )
    page = PromptEditorSettingsPage(
        preference_service=editor_service,
        wildcard_preference_service=wildcard_service,
    )

    page.set_wildcard_resolution_enabled(False)
    app.processEvents()

    preferences = wildcard_service.load_preferences()
    assert preferences.resolve_on_generation is False


def test_prompt_editor_page_invokes_wildcard_management_opener(
    tmp_path: Path,
) -> None:
    """Wildcard Settings management should call the supplied reusable opener."""

    app = ensure_qt_application()
    editor_service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path / "editor")
    )
    calls: list[QWidget | None] = []
    page = PromptEditorSettingsPage(
        preference_service=editor_service,
        open_wildcard_management_modal=lambda parent: calls.append(parent),
    )

    page._open_wildcard_management()
    app.processEvents()

    assert calls == [page]

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

"""Tests for wildcard management modal wrapper and opener."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.prompt_editor import PromptEditorFeature
from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.domain.prompt import PromptWheelAdjustmentMode
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository
from substitute.presentation.managed_text_assets import (
    WildcardManagementModal,
    WildcardManagementOpener,
)
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.prompt_projection_test_helpers import (
    StaticPromptWildcardCatalogGateway,
    ensure_qapp,
)
from tests.execution_test_helpers import immediate_editor_panel_execution_factories

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "wildcard management modal Qt tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def test_wildcard_management_opener_constructs_modal_with_caller_parent(
    tmp_path: Path,
) -> None:
    """The opener should parent the modal mask to the caller's top-level window."""

    app = ensure_qapp()
    parent = QWidget()
    child = QWidget(parent)
    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    opener = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        prompt_wheel_adjustment_mode=lambda: PromptWheelAdjustmentMode.FOCUS_REQUIRED,
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )

    modal = opener.create_modal(child)

    assert app is not None
    assert isinstance(modal, WildcardManagementModal)
    assert modal.parent() is parent
    editor = cast(Any, modal._editor.editor())
    assert (
        editor._autocomplete._result_controller._prompt_autocomplete_gateway.__class__
        is (EmptyPromptAutocompleteGateway)
    )
    assert (
        cast(Any, modal._editor)._wheel_intent_controller._wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )


def test_wildcard_management_modal_uses_wildcard_focused_profile(
    tmp_path: Path,
) -> None:
    """Wildcard modal prompt editor should not expose unrelated prompt-field UI."""

    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    opener = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=StaticPromptWildcardCatalogGateway({}),
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )

    modal = opener.create_modal(None)
    profile = cast(Any, modal._editor.editor())._feature_profile_controller.profile

    assert profile.supports(PromptEditorFeature.WILDCARD_SYNTAX) is True
    assert profile.supports(PromptEditorFeature.WILDCARD_AUTOCOMPLETE) is True
    assert profile.supports(PromptEditorFeature.SEGMENT_REORDER) is False
    assert profile.supports(PromptEditorFeature.LORA_PICKER) is False

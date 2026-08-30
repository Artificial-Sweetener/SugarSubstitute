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

"""Test wildcard management modal construction."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from PySide6.QtWidgets import QWidget

from substitute.domain.prompt.features.models import PromptEditorFeature
from substitute.application.prompt_wildcards import PromptWildcardFileManagementService
from substitute.domain.prompt.preferences.models import PromptWheelAdjustmentMode
from substitute.infrastructure.persistence import FilePromptWildcardFileRepository
from substitute.presentation.managed_text_assets import (
    WildcardManagementModal,
    WildcardManagementOpener,
)
from tests.support.prompt_editor.autocomplete_support import (
    EmptyPromptAutocompleteGateway,
)
from tests.support.prompt_editor.projection_engine_support import (
    ensure_qapp,
)

from tests.presentation.managed_text_assets.wildcards.support import (
    _prompt_runtime_services,
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
        prompt_runtime_services=_prompt_runtime_services(),
        prompt_wheel_adjustment_mode=lambda: PromptWheelAdjustmentMode.FOCUS_REQUIRED,
    )

    modal = opener.create_modal(child)

    assert app is not None
    assert isinstance(modal, WildcardManagementModal)
    assert modal.parent() is parent
    editor = cast(Any, modal._editor.editor())
    assert (
        editor._autocomplete_refresh_controller._lifecycle_requester._result_controller._prompt_autocomplete_gateway.__class__
        is (EmptyPromptAutocompleteGateway)
    )
    assert (
        cast(Any, modal._editor)._wheel_intent_controller._wheel_adjustment_mode
        is PromptWheelAdjustmentMode.FOCUS_REQUIRED
    )


def test_wildcard_management_modal_uses_full_prompt_feature_profile(
    tmp_path: Path,
) -> None:
    """Wildcard modal prompt editor should expose every normal prompt feature."""

    service = PromptWildcardFileManagementService(
        FilePromptWildcardFileRepository(tmp_path / "wildcards")
    )
    opener = WildcardManagementOpener(
        wildcard_file_management_service=service,
        prompt_runtime_services=_prompt_runtime_services(),
    )

    modal = opener.create_modal(None)
    profile = cast(Any, modal._editor.editor())._feature_profile_controller.profile

    assert all(profile.supports(feature) for feature in PromptEditorFeature)

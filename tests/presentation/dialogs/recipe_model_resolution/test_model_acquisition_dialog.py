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

"""Verify the production multi-model acquisition dialog contract."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.recipes import (
    RecipeModelCivitaiState,
    RecipeModelDownloadCandidate,
    RecipeModelResolutionRequired,
    RecipeModelResolutionSummary,
    RecipeModelUnresolvedReference,
)
from substitute.domain.model_metadata import CivitaiDownloadAccess
from substitute.domain.recipes import ParsedSugarScript
from substitute.presentation.dialogs import ModelAcquisitionDialog


def test_dialog_displays_unique_models_and_requires_key_only_for_gated_card(
    qt_application_owner: QApplication,
) -> None:
    """Mixed carts should name the gated card and block until a key is supplied."""

    _ = qt_application_owner
    public = _reference("A", CivitaiDownloadAccess.PUBLIC)
    gated = _reference("B", CivitaiDownloadAccess.API_KEY_REQUIRED)
    dialog = ModelAcquisitionDialog(
        _required(public, gated, public),
        has_api_key=False,
        downloads_enabled=True,
        open_url=lambda _url: True,
    )

    assert len(dialog.cards) == 2
    assert (
        dialog.cards[0].portrait.findChild(QWidget, "ModelAcquisitionAccessBadge")
        is None
    )
    assert (
        dialog.cards[1].portrait.findChild(QWidget, "ModelAcquisitionAccessBadge")
        is not None
    )
    assert dialog._api_key_edit.isVisibleTo(dialog.widget)
    assert not dialog.download_action.isEnabled()

    dialog._api_key_edit.setText("test-key")

    assert dialog.download_action.isEnabled()
    dialog.close()


def test_dialog_does_not_request_key_for_public_models(
    qt_application_owner: QApplication,
) -> None:
    """Public exact matches should remain downloadable without credential copy."""

    _ = qt_application_owner
    dialog = ModelAcquisitionDialog(
        _required(_reference("A", CivitaiDownloadAccess.PUBLIC)),
        has_api_key=False,
        downloads_enabled=True,
        open_url=lambda _url: True,
    )

    assert not dialog._api_key_edit.isVisibleTo(dialog.widget)
    assert dialog.download_action.isEnabled()
    dialog.close()


def test_dialog_disables_aggregate_download_when_any_model_is_unavailable(
    qt_application_owner: QApplication,
) -> None:
    """A partial cart must not begin an acquisition that cannot complete."""

    _ = qt_application_owner
    missing = RecipeModelUnresolvedReference(
        alias="Upscale",
        node_name="model",
        input_key="model_name",
        kind="upscale_models",
        value="missing.pth",
        sha256="C" * 64,
        civitai_state=RecipeModelCivitaiState.NOT_FOUND,
    )
    dialog = ModelAcquisitionDialog(
        _required(_reference("A", CivitaiDownloadAccess.PUBLIC), missing),
        has_api_key=True,
        downloads_enabled=True,
        open_url=lambda _url: True,
    )

    assert len(dialog.cards) == 2
    assert not dialog.download_action.isEnabled()
    dialog.close()


def _reference(
    hash_character: str,
    access: CivitaiDownloadAccess,
) -> RecipeModelUnresolvedReference:
    """Build one exact safe CivitAI candidate."""

    sha256 = hash_character * 64
    return RecipeModelUnresolvedReference(
        alias=f"Cube {hash_character}",
        node_name="model",
        input_key="ckpt_name",
        kind="checkpoints",
        value=f"missing-{hash_character}.safetensors",
        sha256=sha256,
        civitai_state=RecipeModelCivitaiState.FOUND,
        candidate=RecipeModelDownloadCandidate(
            kind="checkpoints",
            sha256=sha256,
            name=f"model-{hash_character}.safetensors",
            download_url=f"https://example.invalid/{hash_character}",
            size_kb=1024.0,
            model_id=1,
            model_version_id=2,
            model_name=f"Model {hash_character}",
            version_name="v1",
            base_model="SDXL",
            creator="Creator",
            file_id=3,
            file_type="Model",
            metadata_format="SafeTensor",
            pickle_scan_result="Success",
            virus_scan_result="Success",
            model_page_url="https://civitai.com/models/1?modelVersionId=2",
            download_access=access,
        ),
    )


def _required(
    *references: RecipeModelUnresolvedReference,
) -> RecipeModelResolutionRequired:
    """Build one blocked resolution request for dialog tests."""

    parsed = ParsedSugarScript(
        buffers=OrderedDict(),
        global_overrides={},
        global_override_selections={},
        field_control_states_by_alias={},
        override_control_states={},
        model_hashes_by_field={},
        prompt_lora_hashes_by_field={},
        project_name=None,
    )
    return RecipeModelResolutionRequired(
        references=tuple(references),
        partial_script=parsed,
        summary=RecipeModelResolutionSummary(unresolved_hashes=len(references)),
    )

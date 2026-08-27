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

"""Test persisted prompt-editor preference JSON contracts."""

from __future__ import annotations

import json
from pathlib import Path

from substitute.application.prompt_editor.features.preferences import (
    PromptEditorPreferenceService,
)
from substitute.domain.prompt.features.models import PromptEditorFeature
from substitute.domain.prompt.preferences.models import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptWheelAdjustmentMode,
)
from substitute.infrastructure.persistence import FilePromptEditorPreferenceRepository


def test_file_prompt_editor_preference_repository_round_trips_normalized_json(
    tmp_path: Path,
) -> None:
    """Save stable JSON containing each normalized feature setting."""

    repository = FilePromptEditorPreferenceRepository(tmp_path)
    service = PromptEditorPreferenceService(repository)

    preferences = service.set_feature_allowed(PromptEditorFeature.LORA_PICKER, False)

    assert preferences.user_allows(PromptEditorFeature.LORA_PICKER) is False
    payload = json.loads((tmp_path / "prompt_editor.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION
    assert payload["wheel_adjustment_mode"] == "hover_dwell"
    assert payload["features"]["autocomplete_ghost_text"] is True
    assert payload["features"]["lora_picker"] is False
    assert set(payload["features"]) == {
        feature.value for feature in PromptEditorFeature
    }


def test_file_prompt_editor_preference_repository_loads_explicit_split_lora_keys(
    tmp_path: Path,
) -> None:
    """Load each independently persisted LoRA preference directly."""

    path = tmp_path / "prompt_editor.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "features": {
                    "lora_syntax": True,
                    "lora_autocomplete": True,
                    "lora_picker": False,
                },
            }
        ),
        encoding="utf-8",
    )
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )

    preferences = service.load_preferences()

    assert preferences.user_allows(PromptEditorFeature.LORA_SYNTAX) is True
    assert preferences.user_allows(PromptEditorFeature.LORA_AUTOCOMPLETE) is True
    assert preferences.user_allows(PromptEditorFeature.LORA_PICKER) is False
    assert preferences.wheel_adjustment_mode is PromptWheelAdjustmentMode.HOVER_DWELL


def test_file_prompt_editor_preference_repository_round_trips_wheel_adjustment_mode(
    tmp_path: Path,
) -> None:
    """Persist and reload the configured wheel adjustment mode."""

    repository = FilePromptEditorPreferenceRepository(tmp_path)
    service = PromptEditorPreferenceService(repository)

    service.set_wheel_adjustment_mode(PromptWheelAdjustmentMode.FOCUS_REQUIRED)

    payload = json.loads((tmp_path / "prompt_editor.json").read_text(encoding="utf-8"))
    preferences = service.load_preferences()
    assert payload["schema_version"] == PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION
    assert payload["wheel_adjustment_mode"] == "focus_required"
    assert preferences.wheel_adjustment_mode is PromptWheelAdjustmentMode.FOCUS_REQUIRED


def test_file_prompt_editor_preference_repository_defaults_invalid_wheel_adjustment_mode(
    tmp_path: Path,
) -> None:
    """Fall back safely when persisted wheel modes are unsupported."""

    path = tmp_path / "prompt_editor.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "2",
                "wheel_adjustment_mode": "future_mode",
                "features": {},
            }
        ),
        encoding="utf-8",
    )
    service = PromptEditorPreferenceService(
        FilePromptEditorPreferenceRepository(tmp_path)
    )

    preferences = service.load_preferences()

    assert preferences.wheel_adjustment_mode is PromptWheelAdjustmentMode.HOVER_DWELL


def test_file_prompt_editor_preference_repository_ignores_unknown_features(
    tmp_path: Path,
) -> None:
    """Discard unknown feature ids when normalizing a persisted document."""

    path = tmp_path / "prompt_editor.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "features": {
                    "emphasis": False,
                    "future_feature": False,
                },
            }
        ),
        encoding="utf-8",
    )
    repository = FilePromptEditorPreferenceRepository(tmp_path)
    service = PromptEditorPreferenceService(repository)

    service.save_preferences(service.load_preferences())

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "future_feature" not in payload["features"]
    assert payload["features"]["emphasis"] is False

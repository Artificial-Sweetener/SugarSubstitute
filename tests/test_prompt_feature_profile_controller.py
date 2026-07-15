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

"""Tests for prompt-editor feature gate controller foundation types."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptSyntaxProfile,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptFeatureActionState,
    PromptFeatureCommandRequest,
    PromptFeatureProfileController,
    PromptFeatureSnapshotIdentity,
    prompt_feature_profile_from_legacy_syntax,
    prompt_feature_profile_identity,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_CONTROLLER_PATH = (
    REPO_ROOT
    / "substitute"
    / "presentation"
    / "editor"
    / "prompt_editor"
    / "features"
    / "feature_profile_controller.py"
)


def test_legacy_syntax_profile_preserves_direct_widget_fallback() -> None:
    """Legacy syntax fallback should match the pre-Phase 8.1 direct widget gates."""

    profile = prompt_feature_profile_from_legacy_syntax(
        PromptSyntaxProfile(enabled_syntaxes=("wildcard",))
    )
    controller = PromptFeatureProfileController(profile)

    assert controller.wildcard_syntax_enabled is True
    assert controller.wildcard_autocomplete_enabled is True
    assert controller.autocomplete_ghost_text_enabled is True
    assert controller.danbooru_url_import_enabled is True
    assert controller.danbooru_wiki_lookup_enabled is True
    assert controller.duplicate_segment_diagnostics_enabled is True
    assert controller.segment_reorder_enabled is True
    assert controller.emphasis_enabled is False
    assert controller.lora_syntax_enabled is False
    assert controller.spellcheck_enabled is False
    assert controller.syntax_profile().enabled_syntaxes == ("wildcard",)


def test_default_legacy_syntax_profile_preserves_rich_direct_widget_support() -> None:
    """Omitted syntax profile should keep the historical direct-widget rich gates."""

    profile = prompt_feature_profile_from_legacy_syntax(None)
    controller = PromptFeatureProfileController(profile)

    assert controller.emphasis_enabled is True
    assert controller.wildcard_syntax_enabled is True
    assert controller.autocomplete_ghost_text_enabled is True
    assert controller.lora_syntax_enabled is True
    assert controller.lora_autocomplete_enabled is True
    assert controller.lora_picker_enabled is True
    assert controller.lora_trigger_words_enabled is True
    assert controller.spellcheck_enabled is False
    assert controller.syntax_profile().enabled_syntaxes == (
        "emphasis",
        "wildcard",
        "lora",
    )


def test_controller_preserves_explicit_profile_decisions() -> None:
    """Explicit profiles should pass through without presentation reinterpretation."""

    profile = PromptEditorFeatureProfile(
        decisions=(
            PromptFeatureDecision(
                feature=PromptEditorFeature.EMPHASIS,
                enabled=False,
                detail="disabled for test",
            ),
            PromptFeatureDecision(
                feature=PromptEditorFeature.LORA_SYNTAX,
                enabled=True,
            ),
        )
    )
    controller = PromptFeatureProfileController(profile)

    assert controller.profile is profile
    assert controller.emphasis_enabled is False
    assert controller.lora_syntax_enabled is True
    assert controller.snapshot.supports(PromptEditorFeature.LORA_SYNTAX)
    assert not controller.snapshot.supports(PromptEditorFeature.EMPHASIS)


def test_snapshot_identity_is_stable_and_source_revision_checked() -> None:
    """Snapshot identity should be hashable and reject invalid source revisions."""

    profile = prompt_feature_profile_from_legacy_syntax(None)
    controller = PromptFeatureProfileController(profile, source_revision=3)

    assert controller.identity.source_revision == 3
    assert controller.identity.feature_profile_id == prompt_feature_profile_identity(
        profile
    )
    assert hash(controller.identity.feature_profile_id) is not None
    assert controller.identity.with_source_revision(4).source_revision == 4
    with pytest.raises(ValueError, match="source_revision"):
        PromptFeatureSnapshotIdentity(source_revision=-1)


def test_action_state_and_command_request_validate_ready_state() -> None:
    """Feature actions should expose readiness and commands without mutation."""

    identity = PromptFeatureSnapshotIdentity(source_revision=1)
    request = PromptFeatureCommandRequest(
        command_name="insert_lora",
        identity=identity,
        payload={"source_range": (0, 0)},
    )
    action = PromptFeatureActionState(
        action_id="lora.insert",
        label="Insert LoRA",
        ready=True,
        command_request=request,
    )

    assert action.command_request is request
    with pytest.raises(ValueError, match="disabled reason"):
        PromptFeatureActionState(
            action_id="bad.ready",
            label="Bad",
            ready=True,
            disabled_reason="not allowed",
        )


def test_feature_profile_controller_is_qt_free() -> None:
    """Feature gate ownership should stay out of widget, shell, and painting layers."""

    source = FEATURE_CONTROLLER_PATH.read_text(encoding="utf-8")
    parsed = ast.parse(source)
    forbidden_roots = (
        "PySide6",
        "qfluentwidgets",
        "substitute.presentation.editor.prompt_editor.shell",
        "substitute.presentation.editor.prompt_editor.overlays",
        "substitute.presentation.editor.prompt_editor.projection.painter",
        "substitute.presentation.editor.prompt_editor.projection.surface",
        "substitute.presentation.editor.prompt_editor.widget",
    )
    violations: list[str] = []
    for node in ast.walk(parsed):
        imported_modules: list[str] = []
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.append(node.module)
        for imported_module in imported_modules:
            if any(
                imported_module == root or imported_module.startswith(f"{root}.")
                for root in forbidden_roots
            ):
                violations.append(f"{getattr(node, 'lineno', 0)}:{imported_module}")
    assert not violations

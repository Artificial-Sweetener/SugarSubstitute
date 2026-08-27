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

"""Keep autocomplete, diagnostics, and related presentation owners separate."""

from __future__ import annotations

from pathlib import Path

from .inventory import (
    PROJECT_ROOT,
    PROMPT_PRESENTATION_ROOT,
)
from .source_shape import protocol_class_count


def test_prompt_editor_private_and_protocol_debt_does_not_grow() -> None:
    """Freeze broad protocols, casts, and private-access exemptions for removal."""

    presentation_sources = tuple(PROMPT_PRESENTATION_ROOT.rglob("*.py"))
    prompt_test_sources = tuple(
        source_path
        for source_path in PROJECT_ROOT.glob("tests/*prompt*.py")
        if source_path != Path(__file__)
    )
    protocol_count = sum(
        protocol_class_count(source_path) for source_path in presentation_sources
    )
    cast_count = sum(
        source_path.read_text(encoding="utf-8").count("cast(")
        for source_path in presentation_sources
    )
    production_private_exemptions = sum(
        source_path.read_text(encoding="utf-8").count("SLF001")
        for source_path in presentation_sources
    )
    test_private_exemptions = sum(
        source_path.read_text(encoding="utf-8").count("SLF001")
        for source_path in prompt_test_sources
    )

    actual = {
        "protocols": protocol_count,
        "casts": cast_count,
        "production_private_exemptions": production_private_exemptions,
        "test_private_exemptions": test_private_exemptions,
    }
    maximums = {
        "protocols": 199,
        "casts": 194,
        "production_private_exemptions": 0,
        "test_private_exemptions": 292,
    }

    assert {
        name: {"actual": actual[name], "maximum": maximum}
        for name, maximum in maximums.items()
        if actual[name] > maximum
    } == {}


def test_autocomplete_presentation_lifecycle_is_the_only_panel_and_preview_owner() -> (
    None
):
    """Keep the Qt coordinator free of session and passive presentation state."""

    controller_path = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    )
    lifecycle_path = (
        PROMPT_PRESENTATION_ROOT
        / "interactions"
        / "autocomplete_presentation_lifecycle.py"
    )
    publication_path = (
        PROMPT_PRESENTATION_ROOT
        / "interactions"
        / "autocomplete_session_publication.py"
    )
    controller_source = controller_path.read_text(encoding="utf-8")
    lifecycle_source = lifecycle_path.read_text(encoding="utf-8")
    publication_source = publication_path.read_text(encoding="utf-8")

    assert "self._presenter" not in controller_source
    assert "self._ghost_text_publisher" not in controller_source
    assert "self._autocomplete_ghost_text_enabled" not in controller_source
    assert "def _present_active_surfaces(" not in controller_source
    assert "def _publish_inline_completion_preview(" not in controller_source
    assert "def _clear_inline_completion_preview(" not in controller_source
    assert "self._sessions" not in controller_source
    assert "self._presentation" not in controller_source
    assert "PromptAutocompletePresentationLifecycle" not in controller_source
    assert "class PromptAutocompletePresentationLifecycle" in lifecycle_source
    assert "application.prompt_editor.autocomplete" not in lifecycle_source
    assert "PromptAutocompleteResultController" not in lifecycle_source
    assert "class PromptAutocompleteSessionPublication" in publication_source
    assert "PromptAutocompletePresentationLifecycle" in publication_source


def test_autocomplete_query_result_lifecycle_is_the_only_query_cache_owner() -> None:
    """Keep query freshness and result work below the Qt interaction coordinator."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    ).read_text(encoding="utf-8")
    lifecycle_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "autocomplete_query_result_lifecycle.py"
    ).read_text(encoding="utf-8")

    forbidden_controller_fragments = (
        "PromptAutocompleteResultController",
        "PromptAutocompleteSceneContextController",
        "PromptAutocompleteScheduledLoraContextController",
        "PromptAutocompleteQueryRefreshController",
        "def refresh_for_query(",
        "def refresh_for_scene_query(",
        "def refresh_for_wildcard_query(",
        "def refresh_for_lora_query(",
        "current_query_identity",
        "refresh_current_query",
    )
    assert not any(
        fragment in controller_source for fragment in forbidden_controller_fragments
    )
    assert "class PromptAutocompleteQueryResultLifecycle" in lifecycle_source
    assert "PySide6" not in lifecycle_source
    assert "PromptAutocompletePresentationLifecycle" not in lifecycle_source
    assert "publication=session_publication" in (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")


def test_autocomplete_acceptance_lifecycle_owns_session_command_transactions() -> None:
    """Keep command acceptance and mandatory session closure outside Qt input routing."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    ).read_text(encoding="utf-8")
    lifecycle_source = (
        PROMPT_PRESENTATION_ROOT
        / "interactions"
        / "autocomplete_acceptance_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert "PromptAutocompleteAcceptanceController" not in controller_source
    assert "self._acceptance_controller" not in controller_source
    assert "class PromptAutocompleteAcceptanceLifecycle" in lifecycle_source
    assert "PromptAutocompleteAcceptanceController" in lifecycle_source
    assert "PromptAutocompleteSessionPublication" in lifecycle_source


def test_autocomplete_input_adapter_stays_at_the_qt_boundary() -> None:
    """Prevent the Qt adapter from reclaiming query, session, or command ownership."""

    adapter_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "autocomplete_controller.py"
    ).read_text(encoding="utf-8")

    assert "class PromptAutocompleteInputAdapter" in adapter_source
    assert "class PromptAutocompleteCoordinator" not in adapter_source
    assert "PromptAutocompleteQueryResultLifecycle" not in adapter_source
    assert "PromptAutocompleteResultController" not in adapter_source
    assert "PromptAutocompleteAcceptanceController" not in adapter_source
    assert "self._sessions" not in adapter_source


def test_autocomplete_test_stack_exposes_real_owners_without_proxy_routing() -> None:
    """Keep test composition explicit instead of recreating autocomplete ownership."""

    helper_source = (
        PROJECT_ROOT / "tests" / "support" / "prompt_editor" / "autocomplete_support.py"
    ).read_text(encoding="utf-8")

    assert "class PromptAutocompleteTestStack" in helper_source
    assert "def build_test_autocomplete_stack(" in helper_source
    assert "PromptAutocompleteInputAdapter" in helper_source
    assert "PromptAutocompleteQueryResultLifecycle" in helper_source
    assert "PromptAutocompleteSessionController" in helper_source
    forbidden_fragments = (
        "PromptAutocompleteLifecycleTestOwner",
        "PromptAutocompleteQueryRefreshTestHarness",
        "build_test_autocomplete_coordinator",
        "def __getattr__(",
        "def refresh_for_query(",
        "def refresh_for_wildcard_query(",
        "def refresh_for_scene_query(",
        "def refresh_for_lora_query(",
        'name == "_sessions"',
    )
    assert not any(fragment in helper_source for fragment in forbidden_fragments)


def test_diagnostics_provider_and_refresh_owners_stay_outside_feature_controller() -> (
    None
):
    """Keep diagnostics lifecycle below its sole presentation/action owner."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_controller.py"
    ).read_text(encoding="utf-8")
    provider_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_provider_lifecycle.py"
    ).read_text(encoding="utf-8")
    refresh_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_refresh_lifecycle.py"
    ).read_text(encoding="utf-8")
    presentation_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_presentation.py"
    ).read_text(encoding="utf-8")
    context_menu_snapshot_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_snapshot_assembly.py"
    ).read_text(encoding="utf-8")
    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")

    assert "class PromptDiagnosticsProviderLifecycle" in provider_source
    assert "class PromptDiagnosticsRefreshLifecycle" in refresh_source
    assert "class PromptDiagnosticsPresentation" in presentation_source
    assert "PromptDiagnosticsProviderLifecycle" in controller_source
    assert "PromptDiagnosticsRefreshLifecycle" in controller_source
    assert "PromptDiagnosticsPresentation" in controller_source
    forbidden_controller_fragments = (
        "def _build_service(",
        "def _scoped_provider(",
        "def _handle_async_outcome(",
        "def _async_identity(",
        "self._request_id",
        "self._stale_guard",
        "self._spellcheck_provider",
        "self._service",
        "self._snapshot",
        "self._published_snapshot",
        "self._visible_diagnostics",
        "self._ignored_diagnostic_ids",
        "def actions_for_diagnostic(",
        "def prepared_menu_actions_for_source_position(",
        "def publish_diagnostics_result(",
        "def publish_empty_diagnostics(",
        "def publish_diagnostics_failure(",
    )
    assert not any(
        fragment in controller_source for fragment in forbidden_controller_fragments
    )
    assert "PySide6" not in provider_source
    assert "PySide6" not in refresh_source
    assert "PySide6" not in presentation_source
    assert "from .diagnostics_controller import" not in context_menu_snapshot_source
    assert "PromptContextMenuDiagnosticsPort" in context_menu_snapshot_source
    assert (
        "diagnostics=self._diagnostics_feature_controller.presentation" in widget_source
    )


def test_weight_interaction_stays_below_general_interaction_routing() -> None:
    """Keep emphasis and exact-weight state out of generic input orchestration."""

    controller_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "controller.py"
    ).read_text(encoding="utf-8")
    weight_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "weight_interaction.py"
    ).read_text(encoding="utf-8")
    keymap_source = (PROMPT_PRESENTATION_ROOT / "interactions" / "keymap.py").read_text(
        encoding="utf-8"
    )
    mouse_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "mouse_selection_controller.py"
    ).read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")
    signal_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "signal_bindings.py"
    ).read_text(encoding="utf-8")

    forbidden_controller_fragments = (
        "PromptEmphasisController",
        "PromptExactWeightController",
        "PromptWeightActionRequest",
        "def modify_emphasis(",
        "def apply_syntax_action(",
        "def apply_overlay_syntax_action(",
        "def apply_token_weight_step_intent(",
        "def apply_token_weight_wheel_step_intent(",
        "def begin_exact_weight_edit(",
        "def start_exact_weight_edit(",
        "def handle_exact_weight_key_press(",
        "def clear_keyboard_emphasis_session(",
        "def clear_mouse_emphasis_session(",
        "def _apply_weight_command_result(",
    )
    assert not any(
        fragment in controller_source for fragment in forbidden_controller_fragments
    )
    assert "class PromptWeightInteraction" in weight_source
    assert "PromptEmphasisController" in weight_source
    assert "PromptExactWeightController" in weight_source
    assert "class PromptKeymapWeightPort" in keymap_source
    assert "self._weights.handle_exact_weight_key_press(event)" in keymap_source
    assert "class PromptMouseSelectionWeightPort" in mouse_source
    assert "self._weights.apply_syntax_action(syntax_action)" in mouse_source
    assert "weight_interaction = PromptWeightInteraction(" in factory_source
    assert "exact_edit_host=weight_interaction" in factory_source
    assert "weight_interaction.modify_emphasis" in signal_source
    assert "weight_interaction.apply_token_weight_step_intent" in signal_source


def test_lora_metadata_refresh_and_presentation_owners_stay_separate() -> None:
    """Keep dispatcher lifecycle and prepared LoRA metadata in direct owners."""

    deleted_controller = (
        PROMPT_PRESENTATION_ROOT / "features" / "lora_metadata_controller.py"
    )
    presentation_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "lora_metadata_presentation.py"
    ).read_text(encoding="utf-8")
    refresh_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "lora_metadata_refresh_lifecycle.py"
    ).read_text(encoding="utf-8")
    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")

    assert not deleted_controller.exists()
    assert "class PromptLoraMetadataPresentation" in presentation_source
    assert "PromptLoraPickerSnapshotController" in presentation_source
    assert "PromptLoraContextActionController" in presentation_source
    assert "QtPromptEditorMainThreadDispatcher" not in presentation_source
    assert "class PromptLoraMetadataRefreshLifecycle" in refresh_source
    assert "self._dirty" in refresh_source
    assert "self._refresh_pending" in refresh_source
    assert "self._catchup_pending" in refresh_source
    assert "PromptLoraPickerSnapshotController" not in refresh_source
    assert "PySide6" not in refresh_source
    assert "self._lora_metadata_presentation" in widget_source
    assert "self._lora_metadata_refresh" in widget_source
    assert "_lora_metadata_feature_controller" not in widget_source
    assert "lora_metadata: PromptLoraMetadataPresentation" in factory_source


def test_wildcard_diagnostics_and_autocomplete_owners_stay_separate() -> None:
    """Keep wildcard diagnostics and asynchronous autocomplete in direct owners."""

    deleted_controller = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_controller.py"
    )
    autocomplete_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_autocomplete.py"
    ).read_text(encoding="utf-8")
    cache_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_autocomplete_cache.py"
    ).read_text(encoding="utf-8")
    diagnostics_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "wildcard_diagnostics.py"
    ).read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")
    diagnostics_lifecycle_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "diagnostics_provider_lifecycle.py"
    ).read_text(encoding="utf-8")

    assert not deleted_controller.exists()
    assert "class PromptWildcardAutocompletePresentation" in autocomplete_source
    assert "PromptWildcardAutocompleteCache" in autocomplete_source
    assert "PromptWildcardDiagnosticProvider" not in autocomplete_source
    assert "actions_for_diagnostic" not in autocomplete_source
    assert "PySide6" not in autocomplete_source
    assert "class PromptWildcardAutocompleteCache" in cache_source
    assert "OrderedDict" in cache_source
    assert "PromptEditorRequestChannel" not in cache_source
    assert "class PromptWildcardDiagnosticsPresentation" in diagnostics_source
    assert "PromptWildcardDiagnosticProvider" in diagnostics_source
    assert "actions_for_diagnostic" in diagnostics_source
    assert "PromptEditorRequestChannel" not in diagnostics_source
    assert "PromptWildcardDiagnosticProviderSource" in diagnostics_lifecycle_source
    assert "PromptWildcardFeatureController" not in diagnostics_lifecycle_source
    assert "wildcard_autocomplete_presentation" in factory_source
    assert "wildcard_diagnostics_presentation" in factory_source


def test_context_menu_preparation_stays_out_of_snapshot_assembly() -> None:
    """Keep explicit feature prewarm work outside passive context-menu reads."""

    preparation_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_preparation.py"
    ).read_text(encoding="utf-8")
    models_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_models.py"
    ).read_text(encoding="utf-8")
    ports_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_ports.py"
    ).read_text(encoding="utf-8")
    snapshot_source = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_snapshot_assembly.py"
    ).read_text(encoding="utf-8")
    presenter_source = (
        PROMPT_PRESENTATION_ROOT / "interactions" / "prompt_menu_presenter.py"
    ).read_text(encoding="utf-8")
    widget_source = (PROMPT_PRESENTATION_ROOT / "widget.py").read_text(encoding="utf-8")
    factory_source = (
        PROMPT_PRESENTATION_ROOT / "composition" / "factory.py"
    ).read_text(encoding="utf-8")
    deleted_action_adapter = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_actions.py"
    )
    deleted_mixed_snapshot_module = (
        PROMPT_PRESENTATION_ROOT / "features" / "context_menu_snapshot.py"
    )

    assert "class PromptContextMenuPreparationLifecycle" in preparation_source
    assert "class PromptContextMenuSnapshotRequest" in models_source
    assert "class PromptContextMenuSnapshot" in models_source
    assert "Protocol" not in models_source
    assert "class PromptContextMenuDiagnosticsPort" in ports_source
    assert "class PromptContextMenuDanbooruPort" in ports_source
    assert "dataclass" not in ports_source
    assert "class PromptContextMenuSnapshotAssembler" in snapshot_source
    assert "class PromptContextMenuDiagnosticsPort" not in snapshot_source
    assert "class PromptContextMenuSnapshotRequest" not in snapshot_source
    assert "prepare_selection" in preparation_source
    assert "prepare_opening" in preparation_source
    assert "PySide6" not in preparation_source
    assert "def prepare_menu_selection(" not in snapshot_source
    assert "def prepare_menu_opening(" not in snapshot_source
    assert not deleted_action_adapter.exists()
    assert not deleted_mixed_snapshot_module.exists()
    assert "class PromptContextMenuSnapshotReader" in presenter_source
    assert "class PromptContextMenuPreparationPort" in presenter_source
    assert "self._preparation.prepare_selection(" in presenter_source
    assert "self._preparation.prepare_opening(" in presenter_source
    assert "self._snapshot_reader.snapshot_for_menu(" in presenter_source
    assert "self._context_menu_snapshot_assembler" in widget_source
    assert "self._context_menu_preparation" in widget_source
    assert "snapshot_reader: PromptContextMenuSnapshotAssembler" in factory_source
    assert "preparation: PromptContextMenuPreparationLifecycle" in factory_source

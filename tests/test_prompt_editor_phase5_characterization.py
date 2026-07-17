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

"""Characterize Phase 5 prompt editor application and lifecycle contracts."""

from __future__ import annotations

from collections.abc import Callable, Iterator
import os
from types import SimpleNamespace
from typing import Any, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QContextMenuEvent, QFocusEvent, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets.components.widgets.menu import RoundMenu  # type: ignore[import-untyped]

from substitute.application.danbooru.models import (
    DanbooruImportedPrompt,
    DanbooruPromptImportResult,
    DanbooruUrlClassification,
    DanbooruUrlKind,
)
from substitute.application.ports import (
    PromptAutocompleteSuggestion,
    PromptWildcardReference,
    PromptWildcardResolution,
)
from substitute.application.prompt_editor import (
    clear_prompt_document_caches,
    clear_prompt_scene_projection_cache,
    clear_prompt_syntax_render_plan_cache,
    effective_prompt_text_at_source_position,
    normalize_literal_parentheses_for_storage,
    parse_prompt_scene_projection_document,
    PromptAutocompleteQuery,
    PromptDocumentService,
    PromptEditorPreferenceService,
    PromptFeatureProfileService,
    PromptLoraCatalogItem,
    PromptScheduledLora,
    PromptSpellcheckSnapshot,
    PromptSyntaxProfileService,
    PromptSyntaxService,
    prompt_syntax_profile_from_feature_profile,
    WorkflowPromptContext,
)
from substitute.application.prompt_editor import (
    prompt_document_cache as document_cache_module,
)
from substitute.application.prompt_editor import (
    prompt_scene_projection_service as scene_module,
)
from substitute.application.prompt_editor import prompt_syntax_service as syntax_module
from substitute.application.prompt_editor.prompt_feature_registry import (
    default_prompt_feature_preferences,
    prompt_feature_definitions,
)
from substitute.domain.prompt import (
    PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptEditorPreferences,
    PromptFeatureDisabledReason,
    PromptWheelAdjustmentMode,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorTaskHandle,
    PromptScheduledLoraContextCoordinator,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptAutocompleteScheduledLoraContextController,
)
from substitute.presentation.editor.prompt_editor.models import (
    PromptEditorInteractionMode,
)
from tests.prompt_projection_test_helpers import (
    ensure_qapp,
    process_events,
    surface_for,
)
from tests.prompt_autocomplete_test_helpers import EmptyPromptAutocompleteGateway
from tests.execution_test_helpers import immediate_prompt_task_executor_factory

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "phase 5 prompt editor characterization tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track widgets created by one Phase 5 characterization test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_phase5_feature_profile_preferences_and_renderer_decisions_match_gates() -> (
    None
):
    """Feature resolution should normalize preferences and drive renderer syntax."""

    repository = _MemoryPreferenceRepository(
        PromptEditorPreferences(
            schema_version="old",
            user_allowed_features={
                PromptEditorFeature.DANBOORU_WIKI_LOOKUP: False,
            },
            wheel_adjustment_mode=cast(Any, "future_mode"),
        )
    )
    preference_service = PromptEditorPreferenceService(repository)
    service = PromptFeatureProfileService(preference_service=preference_service)

    profile = service.build_profile(
        field_style={
            "prompt_features": [
                "wildcard_autocomplete",
                "lora_syntax",
                "future_feature",
            ],
            "prompt_syntaxes": ["emphasis", "wildcard"],
        },
        workflow_context=None,
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )
    preferences = preference_service.load_preferences()

    assert {definition.feature for definition in prompt_feature_definitions()} == set(
        PromptEditorFeature
    )
    assert set(default_prompt_feature_preferences()) == set(PromptEditorFeature)
    assert preferences.schema_version == PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION
    assert preferences.wheel_adjustment_mode is PromptWheelAdjustmentMode.HOVER_DWELL
    assert profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert not profile.supports(PromptEditorFeature.EMPHASIS)
    assert (
        profile.decision_for(PromptEditorFeature.WILDCARD_AUTOCOMPLETE).disabled_reason
        is PromptFeatureDisabledReason.FIELD_DISABLED
    )
    assert profile.decision_for(PromptEditorFeature.WILDCARD_AUTOCOMPLETE).detail == (
        "Requires wildcard_syntax."
    )
    assert service.renderer_syntax_profile(profile) == ("lora",)
    assert prompt_syntax_profile_from_feature_profile(profile).enabled_syntaxes == (
        "lora",
    )


def test_phase5_runtime_lora_profile_uses_prompt_control_graph_and_restored_graph() -> (
    None
):
    """Runtime LoRA actions should require Prompt Control support, including restore data."""

    service = PromptFeatureProfileService(
        preference_service=PromptEditorPreferenceService(
            _MemoryPreferenceRepository(
                PromptEditorPreferences(
                    schema_version=PROMPT_EDITOR_PREFERENCES_SCHEMA_VERSION,
                    user_allowed_features=default_prompt_feature_preferences(),
                )
            )
        )
    )
    missing_runtime_profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
            {
                "prompt": {"class_type": "PrimitiveStringMultiline", "inputs": {}},
                "encode": {
                    "class_type": "CLIPTextEncode",
                    "inputs": {"text": ["prompt", 0]},
                },
            }
        ),
        cube_alias="Cube",
        prompt_node_name="prompt",
        prompt_field_key="text",
    )
    restored_runtime_profile = service.build_profile(
        field_style={"prompt_syntaxes": ["lora"]},
        workflow_context=_workflow_context(
            {},
            original_cube={
                "nodes": {
                    "schedule": {
                        "class_type": (
                            "SimpleSyrup.ScheduleAndEncodePromptsWithPromptControl"
                        ),
                        "inputs": {"positive_prompt": "cat"},
                    }
                }
            },
        ),
        cube_alias="Cube",
        prompt_node_name="schedule",
        prompt_field_key="positive_prompt",
    )

    assert missing_runtime_profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert not missing_runtime_profile.supports(PromptEditorFeature.LORA_PICKER)
    assert (
        missing_runtime_profile.decision_for(
            PromptEditorFeature.LORA_TRIGGER_WORDS
        ).disabled_reason
        is PromptFeatureDisabledReason.MISSING_SERVICE
    )
    assert restored_runtime_profile.supports(PromptEditorFeature.LORA_SYNTAX)
    assert restored_runtime_profile.supports(PromptEditorFeature.LORA_AUTOCOMPLETE)
    assert restored_runtime_profile.supports(PromptEditorFeature.LORA_PICKER)
    assert restored_runtime_profile.supports(PromptEditorFeature.LORA_TRIGGER_WORDS)


def test_phase5_widget_feature_gates_suppress_visible_editor_behaviors(
    widgets: list[QWidget],
) -> None:
    """Widget-visible behavior should respect disabled feature decisions."""

    app = ensure_qapp()
    editor = _show_phase5_editor(
        widgets,
        text="{ani",
        profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.WILDCARD_SYNTAX,)
        ),
        wildcard_gateway=_WildcardCatalogGateway(
            suggestions=(PromptAutocompleteSuggestion(tag="animal"),)
        ),
    )
    interaction = cast(Any, editor)._interaction_controller
    autocomplete = cast(Any, editor)._autocomplete

    _move_cursor(editor, len(editor.toPlainText()))
    cast(Any, editor)._autocomplete_refresh_controller.refresh_from_current_state()
    process_events(app)

    assert autocomplete._sessions.session.mode == "none"

    editor.setPlainText("(cat:1.00), dog")
    process_events(app)
    _select_source_range(editor, 1, 4)
    editor.modify_emphasis(0.1)
    process_events(app)

    assert editor.toPlainText() == "(cat:1.00), dog"

    editor.setPlainText("alpha, beta, gamma")
    _move_cursor(editor, editor.toPlainText().index("beta"))
    QTest.keyPress(editor, Qt.Key.Key_Alt)
    process_events(app)

    assert interaction.interaction_mode is PromptEditorInteractionMode.TEXT_EDITING


def test_phase5_widget_feature_gates_cover_lora_diagnostics_and_danbooru(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LoRA, diagnostic, and Danbooru UI paths should honor feature gates."""

    app = ensure_qapp()
    url = "https://danbooru.donmai.us/posts/12345"
    danbooru_import = _RecordingDanbooruUrlImportService()
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    editor = _show_phase5_editor(
        widgets,
        text="<lora:Mid",
        profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.LORA_SYNTAX,)
        ),
        lora_catalog=_StaticPromptLoraCatalog((_lora_item(),)),
        scheduled_lora_resolver=lambda _prompt_text: (scheduled_lora,),
        danbooru_url_import_service=danbooru_import,
        danbooru_wiki_service=_StubDanbooruWikiService(),
    )
    autocomplete = cast(Any, editor)._autocomplete

    _move_cursor(editor, len(editor.toPlainText()))
    cast(Any, editor)._autocomplete_refresh_controller.refresh_from_current_state()
    process_events(app)

    assert autocomplete._sessions.session.mode == "none"
    assert cast(Any, editor)._danbooru_action_controller.url_import_enabled is False

    editor.setPlainText("alpha")
    _select_source_range(editor, 0, len("alpha"))
    action_texts: list[str] = []

    def fake_exec(self: RoundMenu, *_args: object, **_kwargs: object) -> None:
        """Capture menu actions without opening a popup."""

        action_texts.extend(action.text() for action in self.menuActions())

    monkeypatch.setattr(RoundMenu, "exec", fake_exec)
    cast(Any, editor)._shell_context_menu.show_prompt_context_menu(
        _context_event_for_editor(editor)
    )

    assert "Schedule LoRA" not in action_texts
    assert not any(text.startswith("Trigger words:") for text in action_texts)
    assert "Danbooru wiki lookup" not in action_texts

    editor.setPlainText("")
    _move_cursor(editor, 0)
    QApplication.clipboard().setText(url)
    editor.paste()
    process_events(app)

    assert editor.toPlainText() == url
    assert danbooru_import.classify_calls == []
    assert danbooru_import.import_calls == []

    no_diagnostics_editor = _show_phase5_editor(
        widgets,
        text="alpha",
        profile=PromptEditorFeatureProfile.enabled_profile(()),
        prompt_spellcheck_service=_FakeSpellcheckService(),
    )
    spellcheck_editor = _show_phase5_editor(
        widgets,
        text="alpha",
        profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.SPELLCHECK,)
        ),
        prompt_spellcheck_service=_FakeSpellcheckService(),
    )
    duplicate_editor = _show_phase5_editor(
        widgets,
        text="alpha, alpha",
        profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.DUPLICATE_SEGMENT_DIAGNOSTICS,)
        ),
    )

    assert (
        cast(Any, no_diagnostics_editor)._diagnostics_feature_controller.can_activate()
        is False
    )
    assert (
        cast(Any, spellcheck_editor)._diagnostics_feature_controller.can_activate()
        is True
    )
    assert (
        cast(Any, duplicate_editor)._diagnostics_feature_controller.can_activate()
        is True
    )


def test_phase5_scene_autocomplete_queue_and_effective_prompt_context(
    widgets: list[QWidget],
) -> None:
    """Scene-aware editor behavior should use source-local scene context."""

    app = ensure_qapp()
    text = "quality\n**Ca\nscene text\n**Portrait\nportrait text"
    editor = _show_phase5_editor(widgets, text=text)
    editor.set_scene_autocomplete_titles(("Cafe Interior", "Canal Night", "Portrait"))
    _move_cursor(editor, text.index("Ca") + len("Ca"))
    autocomplete = cast(Any, editor)._autocomplete

    cast(Any, editor)._autocomplete_refresh_controller.refresh_from_current_state()
    process_events(app)

    assert autocomplete._sessions.session.mode == "scene"
    assert [row.tag for row in autocomplete._sessions.session.suggestions] == [
        "Cafe Interior",
        "Canal Night",
    ]

    editor.set_scene_autocomplete_titles(("Canal Night", "Cabin"))
    process_events(app)
    autocomplete.accept_scene_selection()
    process_events(app)

    accepted_text = editor.toPlainText()
    scene_position = accepted_text.index("scene text")
    universal_position = accepted_text.index("quality")
    editor.set_queueable_scene_keys(frozenset({"canal night"}))
    editor.set_source_line_chrome_enabled(True)
    _move_cursor(editor, scene_position)
    process_events(app)

    assert (
        accepted_text == "quality\n**Canal Night\nscene text\n**Portrait\nportrait text"
    )
    assert (
        effective_prompt_text_at_source_position(
            text=accepted_text,
            source_position=scene_position,
        )
        == "quality\n\nscene text"
    )
    assert (
        effective_prompt_text_at_source_position(
            text=accepted_text,
            source_position=universal_position,
        )
        == "quality\n"
    )
    scene_feature = cast(Any, editor)._scene_feature_controller
    assert (
        scene_feature.queueable_scene_key_for_source_position(scene_position)
        == "canal night"
    )
    assert (
        scene_feature.queueable_scene_key_for_source_position(universal_position)
        is None
    )
    assert editor.current_source_line_index() == accepted_text[:scene_position].count(
        "\n"
    )
    assert editor.source_line_rects()


def test_phase5_document_queries_cache_and_normalization_boundaries() -> None:
    """Document query services should expose stable source-backed contracts."""

    clear_prompt_document_caches()
    service = PromptDocumentService()
    source = "alpha, beta,\n\n<LoRA:Midna:0.75>, {animal}, (blue sky:1.20)"

    first_view = service.build_document_view(source)
    second_view = service.build_document_view(source)
    warmed_count = service.prewarm_document_views((source, "gamma"))
    wildcard_query = service.wildcard_autocomplete_query_at_cursor(
        text="{ani",
        cursor_position=len("{ani"),
        has_selection=False,
    )
    scene_query = service.scene_autocomplete_query_at_cursor(
        text="  **Ca  ",
        cursor_position=len("  **Ca"),
        has_selection=False,
    )
    lora_query = service.lora_autocomplete_query_at_cursor(
        text="<LoRA:Mid:0.75>, next",
        cursor_position=len("<LoRA:Mid"),
        has_selection=False,
    )
    invalid_lora_query = service.lora_autocomplete_query_at_cursor(
        text="<lora:Mid:0.75>",
        cursor_position=len("<lora:Mid:0"),
        has_selection=False,
    )
    normalized = normalize_literal_parentheses_for_storage(
        "literal (round text), (blue sky:1.20)"
    )

    assert first_view is second_view
    assert warmed_count == 2
    assert [segment.display_text for segment in first_view.segments] == [
        "alpha",
        "beta",
        "<LoRA:Midna:0.75>",
        "{animal}",
        "(blue sky:1.20)",
    ]
    assert wildcard_query is not None
    assert (
        wildcard_query.prefix,
        wildcard_query.opener_start,
        wildcard_query.content_start,
        wildcard_query.cursor_position,
        wildcard_query.replacement_end,
    ) == ("ani", 0, 1, 4, 4)
    assert scene_query is not None
    assert (
        scene_query.prefix,
        scene_query.marker_start,
        scene_query.title_start,
        scene_query.cursor_position,
        scene_query.replacement_end,
    ) == ("Ca", 2, 4, 6, 6)
    assert lora_query is not None
    assert (
        lora_query.query_text,
        lora_query.token_start,
        lora_query.name_start,
        lora_query.replacement_end,
        lora_query.typed_weight_text,
        lora_query.has_closing_bracket,
    ) == ("Mid", 0, 6, len("<LoRA:Mid:0.75>"), "0.75", True)
    assert invalid_lora_query is None
    assert normalized == "literal (round text:1.10), (blue sky:1.20)"


def test_phase5_document_scene_and_render_plan_caches_evict_oldest_entries() -> None:
    """Prompt document, scene, and render-plan caches should stay bounded LRU caches."""

    clear_prompt_document_caches()
    clear_prompt_scene_projection_cache()
    clear_prompt_syntax_render_plan_cache()
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(_WildcardCatalogGateway())
    syntax_profile = PromptSyntaxProfileService().build_profile(
        {"prompt_syntaxes": ["emphasis"]}
    )

    first_document_view = document_service.build_document_view("document cache 0")
    for index in range(
        cast(int, cast(Any, document_cache_module)._DOCUMENT_VIEW_CACHE_LIMIT)
    ):
        document_service.build_document_view(f"document cache {index + 1}")

    first_scene_document = parse_prompt_scene_projection_document("**scene 0\ntext")
    for index in range(cast(int, cast(Any, scene_module)._SCENE_PARSE_CACHE_LIMIT)):
        parse_prompt_scene_projection_document(f"**scene {index + 1}\ntext")

    first_render_view = document_service.build_document_view("render cache 0")
    first_render_plan = syntax_service.build_render_plan(
        first_render_view,
        syntax_profile,
    )
    for index in range(cast(int, cast(Any, syntax_module)._RENDER_PLAN_CACHE_LIMIT)):
        render_view = document_service.build_document_view(f"render cache {index + 1}")
        syntax_service.build_render_plan(render_view, syntax_profile)

    assert len(cast(Any, document_cache_module)._DOCUMENT_VIEW_CACHE) == cast(
        int, cast(Any, document_cache_module)._DOCUMENT_VIEW_CACHE_LIMIT
    )
    assert all(
        value is not first_document_view
        for value in cast(Any, document_cache_module)._DOCUMENT_VIEW_CACHE.values()
    )
    assert len(cast(Any, scene_module)._SCENE_PARSE_CACHE) == cast(
        int, cast(Any, scene_module)._SCENE_PARSE_CACHE_LIMIT
    )
    assert all(
        value is not first_scene_document
        for value in cast(Any, scene_module)._SCENE_PARSE_CACHE.values()
    )
    assert len(cast(Any, syntax_module)._RENDER_PLAN_CACHE) == cast(
        int, cast(Any, syntax_module)._RENDER_PLAN_CACHE_LIMIT
    )
    assert all(
        value is not first_render_plan
        for value in cast(Any, syntax_module)._RENDER_PLAN_CACHE.values()
    )


def test_phase5_scheduled_lora_context_async_boundaries_and_lru(
    widgets: list[QWidget],
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled-LoRA async context refreshes should coalesce, fail closed, and evict LRU."""

    app = ensure_qapp()
    scheduled_lora = PromptScheduledLora(
        prompt_name="midna",
        backend_value="midna.safetensors",
        display_name="Friendly Midna",
        trained_words=("imp princess",),
        source="cube_field",
    )
    resolver = _TokenScheduledLoraResolver((scheduled_lora,))
    executor = _RecordingScheduledLoraExecutor()
    editor = _show_phase5_editor(
        widgets,
        text="mi",
        profile=PromptEditorFeatureProfile.enabled_profile(
            (PromptEditorFeature.LORA_TRIGGER_WORDS,)
        ),
        scheduled_lora_resolver=resolver,
    )
    autocomplete = cast(Any, editor)._autocomplete
    provider = PromptScheduledLoraContextCoordinator(
        resolver=resolver,
        enabled=True,
        executor=cast(Any, executor),
    )
    autocomplete._scheduled_lora_context = (
        PromptAutocompleteScheduledLoraContextController(
            context_provider=provider,
            current_context=autocomplete,
            enabled=True,
        )
    )

    assert provider.prewarm("secret prompt") is True
    assert provider.prewarm("secret prompt") is False
    assert len(executor.handles) == 1
    cache_key = provider.cache_key_for_prompt("secret prompt")
    assert cache_key in provider.pending_cache_keys()

    executor.handles[0].complete(error=RuntimeError("resolver down"))

    assert cache_key not in provider.pending_cache_keys()
    assert cache_key not in provider.cached_cache_keys()
    assert any(
        record.message.startswith("scheduled_lora_context.refresh.failed")
        for record in caplog.records
    )
    assert "secret prompt" not in caplog.text

    query = PromptAutocompleteQuery(
        prefix="mi",
        word_start=0,
        word_end=2,
        active_tag_end=2,
    )
    refresh_calls: list[PromptAutocompleteQuery] = []
    monkeypatch.setattr(provider, "_cache_limit", 64)
    autocomplete._latest_tag_query = query
    current_key = provider.cache_key_for_prompt("mi")
    current_query_identity = autocomplete._result_controller.safe_tag_query_identity(
        query
    )

    editor.setPlainText("changed")
    process_events(app)
    provider.complete_for_tests(
        cache_key=current_key,
        prompt_text="mi",
        source_text="mi",
        query_identity=current_query_identity,
        scheduled_loras=(scheduled_lora,),
        current_source_text=editor.toPlainText,
        current_query_identity=lambda: current_query_identity,
        refresh_current_query=lambda: refresh_calls.append(query),
    )

    assert refresh_calls == []
    assert provider.cached_scheduled_loras("mi") == (scheduled_lora,)

    editor.setPlainText("mi")
    process_events(app)
    autocomplete._latest_tag_query = query
    provider.complete_for_tests(
        cache_key=current_key,
        prompt_text="mi",
        source_text="mi",
        query_identity=current_query_identity,
        scheduled_loras=(scheduled_lora,),
        current_source_text=editor.toPlainText,
        current_query_identity=lambda: current_query_identity,
        refresh_current_query=lambda: refresh_calls.append(query),
    )

    assert refresh_calls == [query]

    cache_limit = provider.cache_limit
    first_lru_key = provider.cache_key_for_prompt("lru 0")
    provider.complete_for_tests(
        cache_key=first_lru_key,
        prompt_text="lru 0",
        scheduled_loras=(scheduled_lora,),
    )
    for index in range(cache_limit):
        key = provider.cache_key_for_prompt(f"lru {index + 1}")
        provider.complete_for_tests(
            cache_key=key,
            prompt_text=f"lru {index + 1}",
            scheduled_loras=(scheduled_lora,),
        )

    assert len(provider.cached_cache_keys()) == cache_limit
    assert first_lru_key not in provider.cached_cache_keys()


def test_phase5_restore_lifecycle_and_caret_state_remain_source_safe(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restore and lifecycle hooks should clear transient state without source edits."""

    app = ensure_qapp()
    editor = _show_phase5_editor(widgets, text="alpha")
    surface = surface_for(editor)
    QTest.keyClicks(editor, " beta")
    cast(Any, editor)._edit_controller.finish_pending_key_edit_block(reason="phase5")
    process_events(app)
    assert editor.canUndo()

    exact_source = r"literal \(round\), (cat:1.20)"
    editor.replaceBaselineSourceText(exact_source)
    process_events(app)

    assert editor.toPlainText() == exact_source
    assert not editor.canUndo()
    assert not editor.canRedo()

    editor.set_scene_autocomplete_titles(("Cafe",))
    editor.setPlainText("**Ca")
    _move_cursor(editor, len("**Ca"))
    cast(Any, editor)._autocomplete_refresh_controller.refresh_from_current_state()
    process_events(app)
    assert cast(Any, editor)._autocomplete._sessions.session.mode == "scene"

    metadata_catchup_calls = 0
    focus_out_reasons: list[str] = []
    focus_out_controller_calls = 0
    move_calls = 0
    resize_sync_calls = 0

    def record_metadata_catchup() -> None:
        """Record one dirty LoRA metadata catchup request."""

        nonlocal metadata_catchup_calls
        metadata_catchup_calls += 1

    def record_focus_out(reason: str) -> None:
        """Record the key edit block reason used on focus out."""

        focus_out_reasons.append(reason)

    def record_handle_focus_out() -> None:
        """Record the deferred autocomplete focus-out cleanup."""

        nonlocal focus_out_controller_calls
        focus_out_controller_calls += 1

    def record_move() -> None:
        """Record one autocomplete move synchronization."""

        nonlocal move_calls
        move_calls += 1

    def record_resize_sync() -> None:
        """Record one shell geometry sync schedule."""

        nonlocal resize_sync_calls
        resize_sync_calls += 1

    monkeypatch.setattr(
        editor,
        "_schedule_lora_metadata_catchup_if_needed",
        record_metadata_catchup,
    )
    monkeypatch.setattr(
        cast(Any, editor)._edit_controller,
        "finish_pending_key_edit_block",
        lambda *, reason: record_focus_out(reason),
    )
    monkeypatch.setattr(
        cast(Any, editor)._interaction_controller,
        "handle_focus_out",
        record_handle_focus_out,
    )
    monkeypatch.setattr(
        cast(Any, editor)._interaction_controller,
        "handle_move",
        record_move,
    )
    monkeypatch.setattr(
        cast(Any, editor)._qfluent_chrome,
        "_schedule_shell_geometry_sync",
        record_resize_sync,
    )

    editor.hide()
    process_events(app)
    hidden_source = editor.toPlainText()
    editor.show()
    QApplication.sendEvent(
        editor,
        QFocusEvent(QEvent.Type.FocusIn, Qt.FocusReason.OtherFocusReason),
    )
    QApplication.sendEvent(
        editor,
        QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.OtherFocusReason),
    )
    editor.move(editor.pos() + QPoint(4, 3))
    editor.resize(editor.width() + 8, editor.height())
    process_events(app, cycles=10)

    assert hidden_source == "**Ca"
    assert editor.toPlainText() == hidden_source
    assert cast(Any, editor)._autocomplete._sessions.session.mode == "none"
    assert metadata_catchup_calls >= 2
    assert focus_out_reasons == ["editor_focus_out"]
    assert focus_out_controller_calls == 1
    assert move_calls >= 1
    assert resize_sync_calls >= 1
    assert cast(Any, surface)._caret_visual_controller.blink_timer is not None


def _show_phase5_editor(
    widgets: list[QWidget],
    *,
    text: str,
    profile: PromptEditorFeatureProfile | None = None,
    wildcard_gateway: _WildcardCatalogGateway | None = None,
    lora_catalog: _StaticPromptLoraCatalog | None = None,
    scheduled_lora_resolver: Callable[[str], tuple[PromptScheduledLora, ...]]
    | None = None,
    danbooru_url_import_service: object | None = None,
    danbooru_wiki_service: object | None = None,
    prompt_spellcheck_service: object | None = None,
) -> PromptEditor:
    """Create and show one prompt editor for Phase 5 characterization tests."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(460, 240)
    editor = PromptEditor(
        host,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=wildcard_gateway or _WildcardCatalogGateway(),
        danbooru_url_import_service=cast(Any, danbooru_url_import_service),
        danbooru_wiki_service=cast(Any, danbooru_wiki_service),
        prompt_lora_catalog_service=lora_catalog,
        scheduled_lora_resolver=scheduled_lora_resolver,
        prompt_spellcheck_service=cast(Any, prompt_spellcheck_service),
        prompt_feature_profile=profile,
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )
    editor.setGeometry(20, 20, 360, editor.minimumEditorHeight())
    host.show()
    editor.show()
    editor.setFocus()
    editor.replaceBaselineSourceText(text)
    process_events(app, cycles=10)
    widgets.extend([host, editor])
    return editor


def _move_cursor(editor: PromptEditor, position: int) -> None:
    """Move the editor cursor to one source position."""

    cursor = editor.textCursor()
    cursor.setPosition(position, QTextCursor.MoveMode.MoveAnchor)
    editor.setTextCursor(cursor)


def _select_source_range(editor: PromptEditor, start: int, end: int) -> None:
    """Select one source range in the prompt editor."""

    cursor = editor.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def _workflow_context(
    nodes: dict[str, dict[str, Any]],
    *,
    original_cube: dict[str, Any] | None = None,
) -> WorkflowPromptContext:
    """Return a workflow context containing one cube graph."""

    return WorkflowPromptContext(
        cube_states={
            "Cube": SimpleNamespace(
                original_cube=original_cube or {},
                buffer={"nodes": nodes},
            )
        },
        stack_order=("Cube",),
        workflow_overrides={},
        behavior_snapshot=None,
    )


class _MemoryPreferenceRepository:
    """In-memory preference repository used by Phase 5 tests."""

    def __init__(self, preferences: PromptEditorPreferences) -> None:
        """Store the current preference snapshot."""

        self.preferences = preferences

    def load(self) -> PromptEditorPreferences:
        """Return the stored preferences."""

        return self.preferences

    def save(self, preferences: PromptEditorPreferences) -> None:
        """Persist normalized preferences."""

        self.preferences = preferences


class _WildcardCatalogGateway:
    """Return deterministic wildcard metadata and autocomplete rows."""

    def __init__(
        self,
        *,
        suggestions: tuple[PromptAutocompleteSuggestion, ...] = (),
    ) -> None:
        """Store wildcard suggestions returned for any prefix."""

        self._suggestions = suggestions

    def search_wildcards(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Return configured wildcard suggestions within the requested limit."""

        _ = prefix
        return self._suggestions[:limit]

    def resolve_references(
        self,
        references: tuple[PromptWildcardReference, ...],
    ) -> tuple[PromptWildcardResolution, ...]:
        """Resolve wildcard references as existing deterministic entries."""

        return tuple(
            PromptWildcardResolution(
                identifier=reference.identifier,
                wildcard_form=reference.wildcard_form,
                csv_column=reference.csv_column,
                exists=True,
            )
            for reference in references
        )


class _StaticPromptLoraCatalog:
    """Return deterministic LoRA catalog rows for Phase 5 widget tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store LoRA catalog items."""

        self._items = items

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return configured LoRA rows."""

        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured LoRA rows without loading."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return a LoRA row by prompt name."""

        normalized = prompt_name.replace("\\", "/").casefold()
        for item in self._items:
            if item.prompt_name.replace("\\", "/").casefold() == normalized:
                return item
        return None


def _lora_item() -> PromptLoraCatalogItem:
    """Return one deterministic LoRA catalog item."""

    return PromptLoraCatalogItem(
        display_name="Friendly Midna",
        display_subtitle=None,
        prompt_name="Midna",
        backend_value="Midna.safetensors",
        relative_path="Midna.safetensors",
        folder="",
        basename="Midna",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=("imp princess",),
        tags=("character",),
        model_page_url="https://civitai.com/models/1",
        collision_key="midna",
        collision_count=1,
        has_collision=False,
        search_text="friendly midna midna",
    )


class _RecordingDanbooruUrlImportService:
    """Record Danbooru URL import usage for feature-gate tests."""

    def __init__(self) -> None:
        """Initialize empty call records."""

        self.classify_calls: list[str] = []
        self.import_calls: list[str] = []

    def classify_url(self, text: str) -> DanbooruUrlClassification | None:
        """Record classification attempts and return a supported post URL."""

        self.classify_calls.append(text)
        return DanbooruUrlClassification(
            url=text,
            kind=DanbooruUrlKind.POST,
            lookup_value="12345",
        )

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Record import attempts and return deterministic prompt text."""

        self.import_calls.append(text)
        return DanbooruPromptImportResult(
            imported_prompt=DanbooruImportedPrompt(
                display_text="imported tags",
                source_post_id=12345,
                included_tags=("imported_tags",),
                excluded_tags=(),
            )
        )


class _StubDanbooruWikiService:
    """Provide the minimal Danbooru wiki lookup surface."""

    def lookup_selection(self, selection_text: str) -> object:
        """Return an opaque lookup result."""

        return selection_text

    def lookup_title(self, title: str) -> object:
        """Return an opaque lookup result."""

        return title


class _FakeSpellcheckService:
    """Provide enough spellcheck behavior for diagnostics feature gates."""

    @property
    def language_tag(self) -> str:
        """Return a deterministic language tag."""

        return "en_US"

    def snapshot_for_text(self, text: str) -> PromptSpellcheckSnapshot:
        """Return an empty spellcheck snapshot."""

        return PromptSpellcheckSnapshot(
            source_text=text,
            language_tag=self.language_tag,
            issues=(),
        )

    def suggestions_for_word(self, word: str, *, limit: int = 8) -> object:
        """Return no spelling suggestions."""

        _ = (word, limit)
        return ()

    def ignore_word_for_session(self, word: str) -> None:
        """Accept ignored words without side effects."""

        _ = word

    def add_word_to_dictionary(self, word: str) -> bool:
        """Return that dictionary additions are not persisted."""

        _ = word
        return False

    def dictionary_add_supported(self) -> bool:
        """Return that dictionary additions are unsupported."""

        return False


class _TokenScheduledLoraResolver:
    """Resolve scheduled LoRAs with a stable context token."""

    scheduled_lora_context_token = "phase5-token"

    def __init__(self, scheduled_loras: tuple[PromptScheduledLora, ...]) -> None:
        """Store scheduled LoRAs returned by calls."""

        self._scheduled_loras = scheduled_loras
        self.calls: list[str] = []

    def __call__(self, prompt_text: str) -> tuple[PromptScheduledLora, ...]:
        """Record one resolver call."""

        self.calls.append(prompt_text)
        return self._scheduled_loras


class _ScheduledLoraTaskHandle(PromptEditorTaskHandle[tuple[PromptScheduledLora, ...]]):
    """Store one scheduled-LoRA async request for deterministic completion."""

    def __init__(
        self,
        request: PromptAsyncRequest[tuple[PromptScheduledLora, ...]],
    ) -> None:
        """Store request state and completion callbacks."""

        self.request = request
        self.cancel_calls: list[str] = []
        self.callbacks: list[
            Callable[
                [PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]]],
                None,
            ]
        ] = []
        self._outcome: (
            PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]] | None
        ) = None

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self.request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether the fake task has completed."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]] | None:
        """Return the completed outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[
            [PromptAsyncTaskOutcome[tuple[PromptScheduledLora, ...]]],
            None,
        ],
        *,
        reason: str,
    ) -> None:
        """Record one completion callback."""

        _ = reason
        if self._outcome is not None:
            callback(self._outcome)
            return
        self.callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation without preventing explicit test completion."""

        self.cancel_calls.append(reason)

    def run_work(self) -> None:
        """Execute request work and publish one fake task outcome."""

        try:
            result = self.request.work(_Token())
        except BaseException as error:  # noqa: BLE001
            self.complete(error=error)
            return
        self.complete(result=result)

    def complete(
        self,
        *,
        result: tuple[PromptScheduledLora, ...] | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Publish a fake async task outcome to all callbacks."""

        self._outcome = PromptAsyncTaskOutcome(
            identity=self.request.identity,
            context=self.request.context,
            result=result,
            error=error,
        )
        callbacks = tuple(self.callbacks)
        self.callbacks.clear()
        for callback in callbacks:
            callback(self._outcome)


class _Token:
    """Provide a never-cancelled token for scheduled-LoRA characterization work."""

    generation = 0
    is_cancelled = False
    reason: str | None = None


class _RecordingScheduledLoraExecutor:
    """Store scheduled-LoRA async requests for deterministic tests."""

    def __init__(self) -> None:
        """Initialize empty submitted handle storage."""

        self.handles: list[_ScheduledLoraTaskHandle] = []

    def submit(
        self,
        request: PromptAsyncRequest[tuple[PromptScheduledLora, ...]],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[tuple[PromptScheduledLora, ...]]:
        """Record one scheduled-LoRA request and return its handle."""

        _ = cancellation
        handle = _ScheduledLoraTaskHandle(request)
        self.handles.append(handle)
        return handle


def _context_event_for_editor(editor: PromptEditor) -> QContextMenuEvent:
    """Return a context-menu event centered on the editor."""

    local_pos = editor.rect().center()
    return QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        local_pos,
        editor.mapToGlobal(local_pos),
    )

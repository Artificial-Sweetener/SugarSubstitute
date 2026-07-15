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

"""Prompt editor performance scenario runner."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import cast

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptWildcardCatalogGateway,
)
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptLoraCatalogLookup,
    PromptSpellcheckService,
)
from substitute.devtools.prompt_editor_performance.fakes import (
    autocomplete_gateway,
    danbooru_url_import_service,
    danbooru_wiki_service_for_scenario,
    immediate_danbooru_import_dispatcher,
    lora_catalog,
    scheduled_lora_for_context_menu,
    scheduled_lora_resolver_for_scenario,
    segment_preset_source_for_scenario,
    spellcheck_service_for_scenario,
    wildcard_gateway,
)
from substitute.devtools.prompt_editor_performance.instrumentation import (
    InstrumentedMethods,
)
from substitute.devtools.prompt_editor_performance.metrics import (
    Instrumentation,
    ScenarioResult,
    average,
    percentile,
)
from substitute.devtools.prompt_editor_performance.observability import (
    scenario_log_fields,
)
from substitute.devtools.prompt_editor_performance.qt_operations import (
    process_events,
    run_scenario_operations,
    set_cursor_position,
)
from substitute.devtools.prompt_editor_performance.reorder_measurements import (
    reorder_cache_counts,
)
from substitute.devtools.prompt_editor_performance.scenarios import (
    ALL_PROMPT_EDITOR_FEATURES,
    Scenario,
)
from substitute.devtools.prompt_editor_performance.syntax_profile import (
    prompt_syntax_profile,
)
from substitute.app.bootstrap.execution_runtime import ExecutionRuntime
from substitute.app.bootstrap.prompt_editor_execution import (
    create_editor_panel_execution_factories,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.danbooru_paste_import import (
    DanbooruUrlImportDispatcher,
)
from substitute.presentation.editor.prompt_editor.features.diagnostics_controller import (
    PromptDiagnosticsFeatureController,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_controller import (
    PromptSegmentPresetController,
)
from substitute.presentation.editor.prompt_editor.features.prompt_segment_preset_models import (
    PromptSegmentPresetSource,
)

logger = logging.getLogger(__name__)


def run_scenarios(
    app: QApplication,
    scenarios: Sequence[Scenario],
) -> list[ScenarioResult]:
    """Run prompt editor performance scenarios in order."""

    return [run_scenario(app, scenario) for scenario in scenarios]


def run_scenario(app: QApplication, scenario: Scenario) -> ScenarioResult:
    """Run one scenario and return summarized measurements."""

    instrumentation = Instrumentation.create()
    extra_counts: dict[str, int | float] = {}
    timings: list[float] = []
    execution_runtime = ExecutionRuntime()
    editor_execution = create_editor_panel_execution_factories(execution_runtime)

    try:
        with InstrumentedMethods(instrumentation):
            editor = PromptEditor(
                prompt_autocomplete_gateway=cast(
                    PromptAutocompleteGateway,
                    autocomplete_gateway(
                        scenario.autocomplete_gateway,
                        instrumentation.autocomplete_gateway_search,
                    ),
                ),
                prompt_wildcard_catalog_gateway=cast(
                    PromptWildcardCatalogGateway,
                    wildcard_gateway(
                        scenario.wildcard_gateway,
                        instrumentation.wildcard_gateway_search,
                    ),
                ),
                prompt_syntax_profile=prompt_syntax_profile(
                    "emphasis", "wildcard", "lora"
                ),
                prompt_feature_profile=feature_profile_for_scenario(scenario),
                prompt_lora_catalog_service=cast(
                    PromptLoraCatalogLookup,
                    lora_catalog(
                        scenario.lora_catalog,
                        instrumentation.lora_catalog_lookup,
                    ),
                ),
                prompt_spellcheck_service=cast(
                    PromptSpellcheckService | None,
                    spellcheck_service_for_scenario(scenario),
                ),
                scheduled_lora_resolver=scheduled_lora_resolver_for_scenario(scenario),
                danbooru_wiki_service=danbooru_wiki_service_for_scenario(scenario),
                prompt_segment_preset_source=cast(
                    PromptSegmentPresetSource | None,
                    segment_preset_source_for_scenario(scenario),
                ),
                prompt_task_executor_factory=(
                    editor_execution.prompt_task_executor_factory
                ),
                danbooru_lookup_dispatcher_factory=(
                    editor_execution.danbooru_lookup_dispatcher_factory
                ),
            )
            editor.resize(*scenario.editor_size)
            editor.show()
            if scenario.danbooru_import_enabled:
                configure_danbooru_import(editor)
            editor.setPlainText(scenario.initial_text)
            if scenario.selection_range is not None:
                set_selection_range(editor, *scenario.selection_range)
            elif scenario.cursor_position is not None:
                set_cursor_position(editor, scenario.cursor_position)
            editor.setFocus()
            process_events(app)
            prepare_context_menu_scenario(app, editor, scenario)
            instrumentation.reset()

            timings = run_scenario_operations(
                app=app,
                editor=editor,
                scenario=scenario,
                instrumentation=instrumentation,
                extra_counts=extra_counts,
            )
            extra_counts.update(reorder_cache_counts(editor))

            editor.close()
            process_events(app)
    finally:
        execution_runtime.shutdown()

    result = ScenarioResult(
        name=scenario.name,
        characters=len(scenario.initial_text),
        operations=len(timings),
        average_ms=average(timings),
        p95_ms=percentile(timings, 95),
        max_ms=max(timings) if timings else 0.0,
        instrumentation=instrumentation,
        extra_counts=extra_counts,
    )
    logger.info(
        "prompt_editor_performance_scenario_completed",
        extra=scenario_log_fields(scenario, result),
    )
    return result


def configure_danbooru_import(editor: PromptEditor) -> None:
    """Configure deterministic Danbooru URL import for paste measurements."""

    paste_import_controller = getattr(editor, "_danbooru_paste_import_controller")
    paste_import_controller.configure_danbooru_url_import(
        danbooru_url_import_service(),
        enabled=True,
        dispatcher=cast(
            DanbooruUrlImportDispatcher,
            immediate_danbooru_import_dispatcher(),
        ),
    )


def prepare_context_menu_scenario(
    app: QApplication,
    editor: PromptEditor,
    scenario: Scenario,
) -> None:
    """Prepare menu supplier state before measured context-menu opening."""

    if scenario.spellcheck_enabled or scenario.wildcard_gateway == "static":
        diagnostics = cast(
            PromptDiagnosticsFeatureController,
            getattr(editor, "_diagnostics_feature_controller"),
        )
        diagnostics.activate()
        diagnostics.refresh_now()
        process_events(app)
    if scenario.scheduled_lora_context_enabled:
        prime_scheduled_lora_context(editor)
    if scenario.segment_presets_enabled:
        segment_controller = cast(
            PromptSegmentPresetController,
            getattr(editor, "_segment_preset_controller"),
        )
        segment_controller.refresh_menu_model(reason="measure_context_menu_setup")
    process_events(app)


def prime_scheduled_lora_context(editor: PromptEditor) -> None:
    """Populate cached scheduled-LoRA context without resolving during menu open."""

    autocomplete = getattr(editor, "_autocomplete")
    context_controller = getattr(autocomplete, "_scheduled_lora_context", None)
    provider = getattr(context_controller, "_context_provider", None)
    if provider is None:
        return
    prompt_text = editor.toPlainText()
    cache_key = provider.cache_key_for_prompt(prompt_text)
    provider.complete_for_tests(
        cache_key=cache_key,
        prompt_text=prompt_text,
        scheduled_loras=(scheduled_lora_for_context_menu(),),
    )


def feature_profile_for_scenario(
    scenario: Scenario,
) -> PromptEditorFeatureProfile | None:
    """Return a full feature profile when the scenario needs explicit features."""

    if (
        scenario.spellcheck_enabled
        or scenario.wildcard_gateway == "static"
        or scenario.danbooru_wiki_enabled
        or scenario.segment_presets_enabled
        or scenario.scheduled_lora_context_enabled
    ):
        return PromptEditorFeatureProfile.enabled_profile(ALL_PROMPT_EDITOR_FEATURES)
    return None


def set_selection_range(editor: PromptEditor, start: int, end: int) -> None:
    """Select one source range before measuring context-menu opening."""

    cursor = editor.textCursor()
    cursor.setPosition(start, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


__all__ = [
    "configure_danbooru_import",
    "feature_profile_for_scenario",
    "prepare_context_menu_scenario",
    "prime_scheduled_lora_context",
    "run_scenario",
    "run_scenarios",
    "set_selection_range",
]

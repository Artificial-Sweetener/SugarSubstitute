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

"""Warm prompt editor Qt construction costs during launch splash time."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    prompt_syntax_profile_from_feature_profile,
)
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.shared.logging.logger import get_logger, log_exception, log_timing

_LOGGER = get_logger("app.bootstrap.prompt_editor_gui_warmup")
_REPRESENTATIVE_PROMPT_TEXT = (
    "masterpiece, highly detailed, (cinematic lighting:1.2), "
    "__style/portrait__, <lora:example-style:0.8>, [scene:hero], sharp focus"
)


@dataclass(frozen=True, slots=True)
class PromptEditorGuiWarmup:
    """Construct one disposable prompt editor to warm GUI-only startup costs."""

    prompt_autocomplete_gateway: Any
    prompt_wildcard_catalog_gateway: Any
    prompt_lora_catalog_service: Any | None = None
    prompt_scheduled_lora_service: Any | None = None
    prompt_spellcheck_service: Any | None = None
    thumbnail_asset_repository: Any | None = None
    editor_panel_execution_factories: Any | None = None
    editor_factory: Callable[..., Any] | None = None
    budget_seconds: float = 0.20

    def run(self) -> bool:
        """Warm one hidden prompt editor and return whether construction ran."""

        started_at = perf_counter()
        editor: Any | None = None
        try:
            trace_mark("prompt_editor_gui_warmup.start")
            with trace_span("prompt_editor_gui_warmup.factory"):
                factory = self.editor_factory or _prompt_editor_factory()
            feature_profile = PromptEditorFeatureProfile.enabled_profile(
                tuple(PromptEditorFeature)
            )
            with trace_span("prompt_editor_gui_warmup.construct_editor"):
                prompt_task_executor_factory = _execution_factory_attribute(
                    self.editor_panel_execution_factories,
                    "prompt_task_executor_factory",
                )
                danbooru_lookup_dispatcher_factory = _execution_factory_attribute(
                    self.editor_panel_execution_factories,
                    "danbooru_lookup_dispatcher_factory",
                )
                editor = factory(
                    None,
                    prompt_autocomplete_gateway=self.prompt_autocomplete_gateway,
                    prompt_wildcard_catalog_gateway=self.prompt_wildcard_catalog_gateway,
                    prompt_feature_profile=feature_profile,
                    prompt_syntax_profile=prompt_syntax_profile_from_feature_profile(
                        feature_profile
                    ),
                    prompt_lora_catalog_service=self.prompt_lora_catalog_service,
                    prompt_scheduled_lora_service=self.prompt_scheduled_lora_service,
                    prompt_spellcheck_service=self.prompt_spellcheck_service,
                    thumbnail_asset_repository=self.thumbnail_asset_repository,
                    prompt_task_executor_factory=prompt_task_executor_factory,
                    danbooru_lookup_dispatcher_factory=(
                        danbooru_lookup_dispatcher_factory
                    ),
                )
            resize = getattr(editor, "resize", None)
            if callable(resize):
                with trace_span("prompt_editor_gui_warmup.resize"):
                    resize(640, 180)
            ensure_polished = getattr(editor, "ensurePolished", None)
            if callable(ensure_polished):
                with trace_span("prompt_editor_gui_warmup.polish"):
                    ensure_polished()
            set_plain_text = getattr(editor, "setPlainText", None)
            if callable(set_plain_text):
                with trace_span("prompt_editor_gui_warmup.set_text"):
                    set_plain_text(_REPRESENTATIVE_PROMPT_TEXT)
            elapsed_ms = log_timing(
                _LOGGER,
                "Completed prompt editor GUI startup warmup",
                started_at=started_at,
                budget_seconds=f"{self.budget_seconds:.3f}",
            )
            trace_mark(
                "prompt_editor_gui_warmup.end",
                elapsed_ms=elapsed_ms,
                within_budget=elapsed_ms <= self.budget_seconds * 1000.0,
            )
            return elapsed_ms <= self.budget_seconds * 1000.0
        except Exception:
            trace_mark("prompt_editor_gui_warmup.error")
            log_exception(_LOGGER, "Prompt editor GUI startup warmup failed")
            return False
        finally:
            if editor is not None:
                delete_later = getattr(editor, "deleteLater", None)
                if callable(delete_later):
                    with trace_span("prompt_editor_gui_warmup.delete_later"):
                        delete_later()


def warm_prompt_editor_gui_from_window(main_window: Any) -> bool:
    """Warm prompt editor GUI costs from a composed main-window instance."""

    prompt_autocomplete_gateway = getattr(
        main_window, "prompt_autocomplete_gateway", None
    )
    prompt_wildcard_catalog_gateway = getattr(
        main_window,
        "prompt_wildcard_catalog_gateway",
        None,
    )
    if prompt_autocomplete_gateway is None or prompt_wildcard_catalog_gateway is None:
        return False
    return PromptEditorGuiWarmup(
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=prompt_wildcard_catalog_gateway,
        prompt_lora_catalog_service=getattr(
            main_window,
            "prompt_lora_catalog_service",
            None,
        ),
        prompt_scheduled_lora_service=getattr(
            main_window,
            "prompt_scheduled_lora_service",
            None,
        ),
        prompt_spellcheck_service=getattr(
            main_window,
            "prompt_spellcheck_service",
            None,
        ),
        thumbnail_asset_repository=getattr(
            main_window,
            "thumbnail_asset_repository",
            None,
        ),
        editor_panel_execution_factories=getattr(
            main_window,
            "editor_panel_execution_factories",
            None,
        ),
    ).run()


def _execution_factory_attribute(
    editor_panel_execution_factories: Any | None,
    attribute_name: str,
) -> Any | None:
    """Return one editor execution factory from a composed main-window port."""

    if editor_panel_execution_factories is None:
        return None
    return getattr(editor_panel_execution_factories, attribute_name, None)


def _prompt_editor_factory() -> Callable[..., Any]:
    """Import and return the prompt editor class only when warmup runs."""

    from substitute.presentation.editor.prompt_editor import PromptEditor

    return PromptEditor


__all__ = ["PromptEditorGuiWarmup", "warm_prompt_editor_gui_from_window"]

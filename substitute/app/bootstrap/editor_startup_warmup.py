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

"""Warm editor data caches during startup without constructing Qt widgets."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, cast

from substitute.application.execution import (
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
)
from substitute.application.prompt_editor import (
    PromptDocumentService,
    PromptSyntaxService,
    prewarm_prompt_document_views,
    prewarm_prompt_scene_projection_documents,
)
from substitute.application.ports import PromptWildcardCatalogGateway
from substitute.application.prompt_editor.prompt_syntax_profile_service import (
    PromptSyntaxProfileService,
)
from substitute.app.bootstrap.startup_policy import LOCAL_EDITOR_WARMUP_BUDGET_SECONDS
from substitute.app.bootstrap.startup_trace import trace_mark, trace_span
from substitute.shared.logging.logger import (
    get_logger,
    log_exception,
    log_timing,
    log_warning,
)

_LOGGER = get_logger("app.bootstrap.editor_startup_warmup")
DEFAULT_EDITOR_WARMUP_NODE_CLASSES = (
    "CheckpointLoaderSimple",
    "VAELoader",
    "LoraLoader",
    "KSampler",
    "EmptyLatentImage",
    "CLIPTextEncode",
    "CLIPTextEncodeSDXL",
    "PCLazyLoraLoader",
)
_REPRESENTATIVE_PROMPT_TEXTS = (
    (
        "masterpiece, highly detailed, (cinematic lighting:1.2), "
        "__style/portrait__, <lora:example-style:0.8>, [scene:hero], sharp focus"
    ),
)


@dataclass
class _StartupWarmupExecutorHandle:
    """Run one best-effort startup warmup callback through execution."""

    submitter: TaskSubmitter | None = None
    close_submitter: Callable[[], None] | None = None
    task_name_prefix: str = "editor-startup-warmup"

    def __post_init__(self) -> None:
        """Initialize task state for one-shot warmup scheduling."""

        if self.submitter is None:
            raise ValueError("submitter is required for editor startup warmup.")
        self._submitter = self.submitter
        self._scope = TaskScope(
            submitter=self._submitter,
            scope_id=f"editor_startup_warmup_{id(self):x}",
        )
        self._handle: TaskHandle[None] | None = None
        self._shutdown_requested = False

    def start(self) -> None:
        """Start warmup once without blocking shell reveal."""

        trace_mark(
            "editor_startup_warmup.start_requested",
            prefix=self.task_name_prefix,
            already_started=self._handle is not None,
        )
        if self._handle is not None:
            return
        request = TaskRequest(
            identity=TaskIdentity(
                request_id=1,
                domain=self.task_name_prefix.replace("-", "_"),
            ),
            context=ExecutionContext(
                operation=self.task_name_prefix.replace("-", "_"),
                reason="startup_editor_warmup",
                lane="startup",
            ),
            work=lambda _token: self._run_warmup(),
        )
        self._handle = self._scope.submit(request)

    def shutdown(self) -> None:
        """Release executor resources without blocking application shutdown."""

        trace_mark(
            "editor_startup_warmup.shutdown_requested",
            prefix=self.task_name_prefix,
        )
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._scope.close(reason="editor_startup_warmup_shutdown")
        if self.close_submitter is not None:
            self.close_submitter()

    def _run_warmup(self) -> None:
        """Run the concrete warmup implementation."""

        raise NotImplementedError


@dataclass
class LocalEditorStartupWarmupHandle(_StartupWarmupExecutorHandle):
    """Run backend-independent editor cache warmup work off the Qt thread."""

    prompt_autocomplete_gateway: Any | None = None
    prompt_wildcard_catalog_gateway: Any | None = None
    prompt_lora_catalog_service: Any | None = None
    prompt_spellcheck_service: Any | None = None

    def _run_warmup(self) -> None:
        """Warm local editor caches with best-effort logging."""

        started_at = perf_counter()
        try:
            trace_mark("local_editor_warmup.task.start")
            with trace_span("local_editor_warmup.autocomplete"):
                autocomplete_warmed = _warm_prompt_autocomplete(
                    self.prompt_autocomplete_gateway
                )
            with trace_span("local_editor_warmup.wildcard_catalog"):
                wildcard_suggestion_count = _warm_wildcard_catalog(
                    self.prompt_wildcard_catalog_gateway
                )
            with trace_span("local_editor_warmup.lora_catalog"):
                lora_catalog_count = _warm_lora_catalog(
                    self.prompt_lora_catalog_service
                )
            with trace_span("local_editor_warmup.spellcheck"):
                spellcheck_issue_count = _warm_spellcheck(
                    self.prompt_spellcheck_service
                )
            with trace_span("local_editor_warmup.prompt_documents"):
                prompt_document_count = prewarm_prompt_document_views(
                    _REPRESENTATIVE_PROMPT_TEXTS
                )
            with trace_span("local_editor_warmup.prompt_scene_projection"):
                prompt_scene_count = prewarm_prompt_scene_projection_documents(
                    _REPRESENTATIVE_PROMPT_TEXTS
                )
            with trace_span("local_editor_warmup.prompt_render_plans"):
                prompt_render_plan_count = _warm_prompt_render_plans(
                    self.prompt_wildcard_catalog_gateway,
                    self.prompt_lora_catalog_service,
                )
            elapsed_seconds = perf_counter() - started_at
            log_timing(
                _LOGGER,
                "Completed local editor startup warmup",
                started_at=started_at,
                autocomplete_warmed=autocomplete_warmed,
                wildcard_suggestion_count=wildcard_suggestion_count,
                lora_catalog_count=lora_catalog_count,
                spellcheck_issue_count=spellcheck_issue_count,
                prompt_document_count=prompt_document_count,
                prompt_scene_count=prompt_scene_count,
                prompt_render_plan_count=prompt_render_plan_count,
            )
            if elapsed_seconds > LOCAL_EDITOR_WARMUP_BUDGET_SECONDS:
                log_warning(
                    _LOGGER,
                    "Local editor startup warmup exceeded budget",
                    elapsed_ms=f"{elapsed_seconds * 1000.0:.3f}",
                    budget_ms=f"{LOCAL_EDITOR_WARMUP_BUDGET_SECONDS * 1000.0:.3f}",
                )
            trace_mark(
                "local_editor_warmup.task.end",
                autocomplete_warmed=autocomplete_warmed,
                wildcard_suggestion_count=wildcard_suggestion_count,
                lora_catalog_count=lora_catalog_count,
                spellcheck_issue_count=spellcheck_issue_count,
                prompt_document_count=prompt_document_count,
                prompt_scene_count=prompt_scene_count,
                prompt_render_plan_count=prompt_render_plan_count,
            )
        except Exception:
            trace_mark("local_editor_warmup.task.error")
            log_exception(_LOGGER, "Local editor startup warmup failed")


@dataclass
class BackendEditorStartupWarmupHandle(_StartupWarmupExecutorHandle):
    """Run Comfy-dependent editor cache warmup after backend readiness."""

    node_definition_gateway: Any | None = None
    model_choice_resolver: Any | None = None
    node_classes: tuple[str, ...] = DEFAULT_EDITOR_WARMUP_NODE_CLASSES
    task_name_prefix: str = "editor-backend-startup-warmup"

    def _run_warmup(self) -> None:
        """Warm backend node-definition caches with best-effort logging."""

        started_at = perf_counter()
        try:
            trace_mark(
                "backend_editor_warmup.task.start",
                node_classes=self.node_classes,
            )
            scheduled_node_count = 0
            prewarm_node_classes = getattr(
                self.node_definition_gateway,
                "prewarm_node_classes",
                None,
            )
            if callable(prewarm_node_classes):
                with trace_span("backend_editor_warmup.node_definitions"):
                    scheduled_node_count = int(prewarm_node_classes(self.node_classes))
            prewarm = getattr(self.model_choice_resolver, "prewarm", None)
            with trace_span("backend_editor_warmup.model_choice_resolver"):
                warmed_resolution_count = prewarm(()) if callable(prewarm) else 0
            cached_resolution_count = 0
            cached_count = getattr(
                self.model_choice_resolver,
                "cached_resolution_count",
                None,
            )
            if callable(cached_count):
                cached_resolution_count = int(cached_count())
            log_timing(
                _LOGGER,
                "Completed backend editor startup warmup",
                started_at=started_at,
                scheduled_node_definition_count=scheduled_node_count,
                warmed_resolution_count=warmed_resolution_count,
                cached_resolution_count=cached_resolution_count,
            )
            trace_mark(
                "backend_editor_warmup.task.end",
                scheduled_node_definition_count=scheduled_node_count,
                warmed_resolution_count=warmed_resolution_count,
                cached_resolution_count=cached_resolution_count,
            )
        except Exception:
            trace_mark("backend_editor_warmup.task.error")
            log_exception(_LOGGER, "Backend editor startup warmup failed")


def _warm_prompt_autocomplete(prompt_autocomplete_gateway: Any | None) -> bool:
    """Warm prompt autocomplete tags when the gateway exposes a warm hook."""

    warm = getattr(prompt_autocomplete_gateway, "warm", None)
    if callable(warm):
        warm()
        return True
    search = getattr(prompt_autocomplete_gateway, "search", None)
    if callable(search):
        search("", 1)
        return True
    return False


def _warm_wildcard_catalog(prompt_wildcard_catalog_gateway: Any | None) -> int:
    """Warm wildcard catalog scans by running one tiny suggestion query."""

    search_wildcards = getattr(
        prompt_wildcard_catalog_gateway, "search_wildcards", None
    )
    if not callable(search_wildcards):
        return 0
    return len(tuple(search_wildcards("", 1)))


def _warm_lora_catalog(prompt_lora_catalog_service: Any | None) -> int:
    """Warm prompt LoRA catalog records used by syntax and autocomplete."""

    cached_loras = getattr(prompt_lora_catalog_service, "cached_loras", None)
    if callable(cached_loras):
        cached = cached_loras()
        if cached is not None:
            return len(tuple(cached))
    list_loras = getattr(prompt_lora_catalog_service, "list_loras", None)
    if not callable(list_loras):
        return 0
    count = len(tuple(list_loras()))
    return count


def _warm_spellcheck(prompt_spellcheck_service: Any | None) -> int:
    """Warm prompt spellcheck backend with one tiny prompt snapshot."""

    snapshot_for_text = getattr(prompt_spellcheck_service, "snapshot_for_text", None)
    if not callable(snapshot_for_text):
        return 0
    snapshot = snapshot_for_text("warmup prompt")
    return len(getattr(snapshot, "issues", ()) or ())


def _warm_prompt_render_plans(
    prompt_wildcard_catalog_gateway: Any | None,
    prompt_lora_catalog_service: Any | None,
) -> int:
    """Warm pure syntax render plans for representative prompt editor text."""

    resolve_references = getattr(
        prompt_wildcard_catalog_gateway,
        "resolve_references",
        None,
    )
    if not callable(resolve_references):
        return 0
    document_service = PromptDocumentService()
    syntax_service = PromptSyntaxService(
        cast(PromptWildcardCatalogGateway, prompt_wildcard_catalog_gateway),
        prompt_lora_catalog_service=prompt_lora_catalog_service,
    )
    syntax_profile = PromptSyntaxProfileService().default_profile()
    warmed = 0
    for text in _REPRESENTATIVE_PROMPT_TEXTS:
        syntax_service.build_render_plan(
            document_service.build_document_view(text),
            syntax_profile,
        )
        warmed += 1
    return warmed


__all__ = [
    "BackendEditorStartupWarmupHandle",
    "DEFAULT_EDITOR_WARMUP_NODE_CLASSES",
    "LocalEditorStartupWarmupHandle",
]

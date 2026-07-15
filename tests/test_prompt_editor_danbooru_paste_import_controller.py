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

"""Tests for the Danbooru paste/import controller boundary."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

import pytest
from substitute.application.danbooru import (
    DanbooruFailureReason,
    DanbooruImportedPrompt,
    DanbooruPromptImportResult,
    DanbooruUrlClassification,
    DanbooruUrlImportService,
    DanbooruUrlKind,
)
from substitute.application.prompt_editor import PromptSourceNormalizationService
from substitute.presentation.editor.prompt_editor.danbooru_paste_import import (
    PromptDanbooruPasteRequest,
)
from substitute.presentation.editor.prompt_editor.editing_session import (
    PromptSourceEditOrigin,
    PromptCursorState,
    PromptEditingSession,
)
from substitute.presentation.editor.prompt_editor.editing_session.edit_controller import (
    PromptEditController,
    PromptEditControllerResult,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptDanbooruPasteImportController,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptEditCommandRouter,
)


@dataclass(slots=True)
class _StaticDanbooruUrlImportService:
    """Return deterministic Danbooru URL import outcomes for controller tests."""

    classification: DanbooruUrlClassification | None
    result: DanbooruPromptImportResult
    error_factory: Callable[[str], BaseException] | None = None
    classify_calls: list[str] = field(default_factory=list)
    import_calls: list[str] = field(default_factory=list)

    def classify_url(self, text: str) -> DanbooruUrlClassification | None:
        """Return the configured URL classification for one pasted string."""

        self.classify_calls.append(text)
        return self.classification

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Return or raise the configured import outcome."""

        self.import_calls.append(text)
        if self.error_factory is not None:
            raise self.error_factory(text)
        return self.result


@dataclass(slots=True)
class _RecordingDanbooruImportDispatcher:
    """Record Danbooru import requests and optionally complete them inline."""

    complete_immediately: bool = True
    submissions: list[Callable[[], DanbooruPromptImportResult]] = field(
        default_factory=list
    )

    def submit(
        self,
        lookup: Callable[[], DanbooruPromptImportResult],
        *,
        completed: Callable[[DanbooruPromptImportResult], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Record one lookup and optionally run it immediately."""

        self.submissions.append(lookup)
        if not self.complete_immediately:
            return
        try:
            completed(lookup())
        except BaseException as error:  # noqa: BLE001
            failed(error)


@dataclass(slots=True)
class _PayloadProvider:
    """Provide passive undo payloads for controller tests."""

    session: PromptEditingSession[str]

    def undo_restoration_payload(self) -> str:
        """Return the current source text as restoration payload."""

        return self.session.source_text

    def undo_comparison_payload(self) -> str:
        """Return the current source text as comparison payload."""

        return self.session.source_text


@dataclass(slots=True)
class _AvailabilitySink:
    """Record undo/redo availability emissions."""

    undo_values: list[bool] = field(default_factory=list)
    redo_values: list[bool] = field(default_factory=list)

    def emit_undo_available_changed(self, available: bool) -> None:
        """Record one undo availability transition."""

        self.undo_values.append(available)

    def emit_redo_available_changed(self, available: bool) -> None:
        """Record one redo availability transition."""

        self.redo_values.append(available)


@dataclass(slots=True)
class _MutationSink:
    """Record projection mutation results published by the router."""

    results: list[PromptEditControllerResult[str, object]] = field(default_factory=list)

    def apply_edit_controller_result(
        self,
        result: PromptEditControllerResult[str, object],
    ) -> None:
        """Record one router-published mutation result."""

        self.results.append(result)


@dataclass(slots=True)
class _Harness:
    """Bundle one Danbooru paste/import controller test harness."""

    session: PromptEditingSession[str]
    controller: PromptDanbooruPasteImportController[str]
    dispatcher: _RecordingDanbooruImportDispatcher
    router: PromptEditCommandRouter[str]
    exact_source: dict[str, bool]


def test_disabled_service_does_not_schedule_or_mutate_source() -> None:
    """Disabled Danbooru paste/import should fall through to literal paste."""

    service = _service()
    harness = _harness("", service=service, enabled=False)

    assert not harness.controller.try_schedule_clipboard_danbooru_paste(_URL)
    assert harness.session.source_text == ""
    assert service.classify_calls == []
    assert harness.dispatcher.submissions == []


def test_unsupported_url_returns_literal_paste_fallback() -> None:
    """Unsupported pasted URLs should not be consumed by Danbooru scheduling."""

    service = _service(classification=None)
    harness = _harness("", service=service)

    assert not harness.controller.try_schedule_clipboard_danbooru_paste(_URL)
    assert harness.session.source_text == ""
    assert service.classify_calls == [_URL]
    assert service.import_calls == []


def test_scheduled_import_inserts_literal_url_before_async_completion() -> None:
    """Supported URLs should paste immediately and submit import work."""

    service = _service()
    harness = _harness("", service=service, complete_immediately=False)

    assert harness.controller.try_schedule_clipboard_danbooru_paste(_URL)
    assert harness.session.source_text == _URL
    assert service.classify_calls == [_URL]
    assert service.import_calls == []
    assert len(harness.dispatcher.submissions) == 1


def test_successful_replacement_uses_prepared_import_command() -> None:
    """Successful imports should replace the still-matching pasted URL."""

    service = _service()
    harness = _harness("alpha, ", service=service)

    assert harness.controller.try_schedule_clipboard_danbooru_paste(_URL)

    assert harness.session.source_text == "alpha, 1girl, long hair"
    assert service.import_calls == [_URL]
    assert harness.session.can_undo()


def test_failed_import_keeps_literal_pasted_url() -> None:
    """Failed Danbooru import results should leave the literal URL in source."""

    service = _service(
        result=DanbooruPromptImportResult(
            imported_prompt=None,
            failure_reason=DanbooruFailureReason.NOT_FOUND,
        )
    )
    harness = _harness("", service=service)

    assert harness.controller.try_schedule_clipboard_danbooru_paste(_URL)
    assert harness.session.source_text == _URL
    assert service.import_calls == [_URL]


def test_stale_pasted_text_skips_successful_import_replacement() -> None:
    """Later source edits should make completed imports leave user edits intact."""

    service = _service()
    harness = _harness("", service=service, complete_immediately=False)

    assert harness.controller.try_schedule_clipboard_danbooru_paste(_URL)
    harness.router.replace_source_range(
        start=0,
        end=len(_URL),
        replacement_text="edited url",
        origin=PromptSourceEditOrigin.TYPED,
        command_name="test_edit",
    )
    request = PromptDanbooruPasteRequest(
        pasted_text=_URL,
        start=0,
        end=len(_URL),
        pasted_undo_state=harness.router.current_undo_snapshot(),
    )

    harness.controller.apply_import_result(request, _success_result())

    assert harness.session.source_text == "edited url"


def test_async_failure_logging_keeps_prompt_content_out_of_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Async import failures should log safe context without prompt text."""

    pasted_url = "https://danbooru.donmai.us/posts/888"
    service = _service(
        classification=DanbooruUrlClassification(
            url=pasted_url,
            kind=DanbooruUrlKind.POST,
            lookup_value="888",
        ),
        error_factory=lambda text: RuntimeError(text),
    )
    harness = _harness("", service=service)
    caplog.set_level(
        logging.WARNING,
        logger="presentation.editor.prompt_editor.danbooru_paste_import",
    )

    assert harness.controller.try_schedule_clipboard_danbooru_paste(pasted_url)

    assert harness.session.source_text == pasted_url
    assert "Prompt paste Danbooru import failed unexpectedly." in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert f"source_length={len(pasted_url)}" in caplog.text
    assert pasted_url not in caplog.text


def test_exact_source_normalization_tracks_literal_paste_text() -> None:
    """Exact-source mode should change the expected pasted text for replacement."""

    pasted_text = "https://danbooru.donmai.us/posts/(123)"
    service = _service(
        classification=DanbooruUrlClassification(
            url=pasted_text,
            kind=DanbooruUrlKind.POST,
            lookup_value="123",
        ),
    )
    harness = _harness("", service=service, complete_immediately=False)

    assert (
        harness.controller.normalized_paste_text(pasted_text)
        == "https://danbooru.donmai.us/posts/(123:1.10)"
    )

    harness.exact_source["enabled"] = True

    assert harness.controller.normalized_paste_text(pasted_text) == pasted_text


def _harness(
    source_text: str,
    *,
    service: _StaticDanbooruUrlImportService,
    enabled: bool = True,
    complete_immediately: bool = True,
) -> _Harness:
    """Return a controller harness backed by a real editing session and router."""

    session = PromptEditingSession[str](
        source_text=source_text,
        source_revision=0,
        cursor_state=PromptCursorState(
            cursor_position=len(source_text),
            anchor_position=len(source_text),
        ),
        max_undo_states=100,
        max_redo_states=100,
    )
    edit_controller = PromptEditController[str](
        session=session,
        undo_payload_provider=_PayloadProvider(session),
        availability_signal_sink=_AvailabilitySink(),
    )
    normalizer = PromptSourceNormalizationService()
    mutation_sink = _MutationSink()
    exact_source = {"enabled": False}
    router = PromptEditCommandRouter[str](
        edit_controller=edit_controller,
        normalizer=normalizer,
        mutation_sink=mutation_sink,
        source_text_provider=lambda: session.source_text,
        cursor_position_provider=lambda: session.cursor_position,
        anchor_position_provider=lambda: session.anchor_position,
        exact_source_provider=lambda: exact_source["enabled"],
    )
    dispatcher = _RecordingDanbooruImportDispatcher(
        complete_immediately=complete_immediately
    )
    controller = PromptDanbooruPasteImportController[str](
        edit_controller=edit_controller,
        source_replacement_executor=router,
        import_executor=router,
        normalizer=normalizer,
        exact_source_enabled=lambda: exact_source["enabled"],
        dispatcher=dispatcher,
    )
    controller.configure_danbooru_url_import(
        cast(DanbooruUrlImportService, service),
        enabled=enabled,
    )
    return _Harness(
        session=session,
        controller=controller,
        dispatcher=dispatcher,
        router=router,
        exact_source=exact_source,
    )


_DEFAULT_CLASSIFICATION = object()


def _service(
    *,
    classification: DanbooruUrlClassification | None | object = _DEFAULT_CLASSIFICATION,
    result: DanbooruPromptImportResult | None = None,
    error_factory: Callable[[str], BaseException] | None = None,
) -> _StaticDanbooruUrlImportService:
    """Return a deterministic Danbooru URL import service."""

    resolved_classification = (
        _classification()
        if classification is _DEFAULT_CLASSIFICATION
        else cast(DanbooruUrlClassification | None, classification)
    )
    return _StaticDanbooruUrlImportService(
        classification=resolved_classification,
        result=_success_result() if result is None else result,
        error_factory=error_factory,
    )


def _classification() -> DanbooruUrlClassification:
    """Return the default supported URL classification."""

    return DanbooruUrlClassification(
        url=_URL,
        kind=DanbooruUrlKind.POST,
        lookup_value="12345",
    )


def _success_result() -> DanbooruPromptImportResult:
    """Return the default successful prompt import result."""

    return DanbooruPromptImportResult(
        imported_prompt=DanbooruImportedPrompt(
            display_text="1girl, long hair",
            source_post_id=12345,
            included_tags=("1girl", "long_hair"),
            excluded_tags=(),
        )
    )


_URL = "https://danbooru.donmai.us/posts/12345"

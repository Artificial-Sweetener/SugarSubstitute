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

"""Tests for panel-owned LoRA metadata refresh coordination."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

from PySide6.QtWidgets import QApplication

from substitute.application.model_metadata import ModelCatalogItem, ModelCatalogSnapshot
from substitute.application.prompt_editor import PromptLoraCatalogSnapshot
from substitute.presentation.editor.panel.lora_metadata_refresh_controller import (
    EditorPanelLoraMetadataRefreshController,
    EditorPanelLoraMetadataRefreshHost,
    PanelLoraMetadataRefreshController,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
)

TResult = TypeVar("TResult")


class _Dispatcher:
    """Record main-thread publications for deterministic controller tests."""

    def __init__(self) -> None:
        """Initialize the publication queue."""

        self.publications: list[tuple[str, Callable[[], None]]] = []

    def publish(self, callback: Callable[[], None], *, reason: str) -> None:
        """Record the publication callback instead of entering the Qt loop."""

        self.publications.append((reason, callback))

    def run_next(self) -> str:
        """Run and return the next queued publication reason."""

        reason, callback = self.publications.pop(0)
        callback()
        return reason


class _TaskHandle(Generic[TResult]):
    """Expose a controllable prompt-editor task handle for tests."""

    def __init__(self, request: PromptAsyncRequest[TResult]) -> None:
        """Store request identity and initialize callback tracking."""

        self._request = request
        self._callbacks: list[Callable[[PromptAsyncTaskOutcome[TResult]], None]] = []
        self._outcome: PromptAsyncTaskOutcome[TResult] | None = None
        self.cancel_reasons: list[str] = []

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the request identity."""

        return self._request.identity

    @property
    def is_finished(self) -> bool:
        """Return whether a terminal outcome has been supplied."""

        return self._outcome is not None

    @property
    def outcome(self) -> PromptAsyncTaskOutcome[TResult] | None:
        """Return the terminal outcome when available."""

        return self._outcome

    def add_done_callback(
        self,
        callback: Callable[[PromptAsyncTaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Record or immediately publish a completion callback."""

        _ = reason
        if self._outcome is None:
            self._callbacks.append(callback)
            return
        callback(self._outcome)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation requests."""

        self.cancel_reasons.append(reason)

    def complete(self, result: TResult) -> None:
        """Complete the handle successfully."""

        self._finish(
            PromptAsyncTaskOutcome(
                identity=self.identity,
                context=self._request.context,
                result=result,
            )
        )

    def fail(self, error: BaseException) -> None:
        """Complete the handle with an error."""

        self._finish(
            PromptAsyncTaskOutcome(
                identity=self.identity,
                context=self._request.context,
                error=error,
            )
        )

    def _finish(self, outcome: PromptAsyncTaskOutcome[TResult]) -> None:
        """Publish one terminal outcome to registered callbacks."""

        self._outcome = outcome
        callbacks = tuple(self._callbacks)
        self._callbacks.clear()
        for callback in callbacks:
            callback(outcome)


class _Executor:
    """Store submitted prompt async requests without running task code."""

    def __init__(self) -> None:
        """Initialize submitted request tracking."""

        self.submitted: list[
            tuple[
                PromptAsyncRequest[PromptLoraCatalogSnapshot],
                PromptEditorCancellationToken,
                _TaskHandle[PromptLoraCatalogSnapshot],
            ]
        ] = []

    def submit(
        self,
        request: PromptAsyncRequest[PromptLoraCatalogSnapshot],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[PromptLoraCatalogSnapshot]:
        """Record the submitted request and return a controllable handle."""

        handle: _TaskHandle[PromptLoraCatalogSnapshot] = _TaskHandle(request)
        self.submitted.append((request, cancellation, handle))
        return handle


class _CatalogService:
    """Expose the LoRA catalog methods used by the controller."""

    def __init__(self) -> None:
        """Initialize catalog call tracking."""

        self.prepare_calls = 0
        self.prepared_models: list[tuple[tuple[ModelCatalogItem, ...], int]] = []
        self.installed: list[PromptLoraCatalogSnapshot] = []
        self.cache_revision = 0

    def prepare_snapshot_from_models(
        self,
        models: tuple[ModelCatalogItem, ...],
        *,
        model_generation: int,
    ) -> PromptLoraCatalogSnapshot:
        """Return a prepared snapshot from canonical model rows."""

        self.prepare_calls += 1
        self.prepared_models.append((models, model_generation))
        return _prompt_snapshot(model_generation=model_generation)

    def install_snapshot(self, snapshot: PromptLoraCatalogSnapshot) -> None:
        """Record installed snapshots and advance the revision token."""

        self.installed.append(snapshot)
        self.cache_revision += 1


class _Panel:
    """Record dirty marking and visible refresh requests."""

    def __init__(self, refreshed_count: int = 1) -> None:
        """Store fixed refresh result."""

        self.refreshed_count = refreshed_count
        self.dirty_marks = 0
        self.visible_refreshes = 0

    def mark_lora_metadata_dirty(self) -> None:
        """Record dirty marking without doing projection work."""

        self.dirty_marks += 1

    def refresh_visible_lora_metadata(self) -> int:
        """Record visible refresh routing and return the fixed count."""

        self.visible_refreshes += 1
        return self.refreshed_count


class _PromptEditor:
    """Expose the prompt-editor LoRA metadata public API used by panels."""

    def __init__(self, refreshed: bool = False) -> None:
        """Initialize prompt-editor call tracking."""

        self.refreshed = refreshed
        self.mark_calls = 0
        self.refresh_calls = 0

    def mark_lora_metadata_dirty(self) -> None:
        """Record dirty marking."""

        self.mark_calls += 1

    def refresh_lora_metadata_if_visible(self) -> bool:
        """Record visible refresh attempts."""

        self.refresh_calls += 1
        return self.refreshed


class _PanelHost:
    """Return fake prompt editors from the panel host discovery API."""

    def __init__(self, editors: tuple[_PromptEditor, ...]) -> None:
        """Store prompt editors returned by findChildren."""

        self._editors = editors

    def findChildren(self, _widget_type: type[object]) -> list[_PromptEditor]:
        """Return the configured prompt editors."""

        return list(self._editors)


def test_panel_lora_metadata_refresh_controller_marks_dirty_and_coalesces_running_requests() -> (
    None
):
    """Rapid refresh requests should share one active task and queue a follow-up."""

    _ensure_qapp()
    catalog = _CatalogService()
    panel = _Panel(refreshed_count=2)
    dispatcher = _Dispatcher()
    executor = _Executor()
    controller = PanelLoraMetadataRefreshController(
        catalog_service=cast(Any, catalog),
        editor_panels=lambda: (panel,),
        executor=cast(PromptEditorExecutor, executor),
        dispatcher=dispatcher,
    )

    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=1))
    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=1))
    assert len(dispatcher.publications) == 1
    assert dispatcher.run_next() == "lora_metadata_start_refresh"
    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=2))

    assert panel.dirty_marks == 3
    assert len(executor.submitted) == 1
    first_request, first_cancellation, first_handle = executor.submitted[0]
    first_prompt_snapshot = first_request.work(first_cancellation)
    assert catalog.prepared_models == [((_model_item(),), 1)]

    first_handle.complete(first_prompt_snapshot)

    assert catalog.cache_revision == 0
    assert panel.visible_refreshes == 0
    assert len(dispatcher.publications) == 1
    assert dispatcher.run_next() == "lora_metadata_followup_refresh"
    assert len(executor.submitted) == 2
    second_request, second_cancellation, _second_handle = executor.submitted[1]
    _ = second_request.work(second_cancellation)
    assert catalog.prepared_models == [((_model_item(),), 1), ((_model_item(),), 2)]


def test_panel_lora_metadata_refresh_controller_installs_current_generation() -> None:
    """Current canonical generations should install and refresh visible editors."""

    _ensure_qapp()
    catalog = _CatalogService()
    panel = _Panel(refreshed_count=2)
    dispatcher = _Dispatcher()
    executor = _Executor()
    controller = PanelLoraMetadataRefreshController(
        catalog_service=cast(Any, catalog),
        editor_panels=lambda: (panel,),
        executor=cast(PromptEditorExecutor, executor),
        dispatcher=dispatcher,
    )

    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=4))
    dispatcher.run_next()
    request, cancellation, handle = executor.submitted[0]
    handle.complete(request.work(cancellation))

    assert catalog.installed[0].model_generation == 4
    assert catalog.cache_revision == 1
    assert panel.visible_refreshes == 0
    assert dispatcher.run_next() == "lora_metadata_visible_refresh"
    assert panel.visible_refreshes == 1


def test_panel_lora_metadata_refresh_controller_ignores_stale_completion() -> None:
    """Late task completions should not install stale LoRA snapshots."""

    _ensure_qapp()
    catalog = _CatalogService()
    panel = _Panel()
    controller = PanelLoraMetadataRefreshController(
        catalog_service=cast(Any, catalog),
        editor_panels=lambda: (panel,),
        executor=cast(PromptEditorExecutor, _Executor()),
        dispatcher=_Dispatcher(),
    )
    controller._active_request_id = 2

    controller._deliver_completed_refresh(
        PromptAsyncTaskOutcome(
            identity=controller._build_snapshot_request(
                snapshot=_model_snapshot(generation=1),
                request_id=1,
                cancellation_generation=1,
            ).identity,
            context=controller._build_snapshot_request(
                snapshot=_model_snapshot(generation=1),
                request_id=1,
                cancellation_generation=1,
            ).context,
            result=_prompt_snapshot(model_generation=1),
        )
    )

    assert catalog.installed == []
    assert panel.visible_refreshes == 0


def test_panel_lora_metadata_refresh_controller_failure_starts_followup(
    caplog: Any,
) -> None:
    """Task failures should not leak messages and should honor follow-ups."""

    _ensure_qapp()
    catalog = _CatalogService()
    panel = _Panel()
    dispatcher = _Dispatcher()
    executor = _Executor()
    controller = PanelLoraMetadataRefreshController(
        catalog_service=cast(Any, catalog),
        editor_panels=lambda: (panel,),
        executor=cast(PromptEditorExecutor, executor),
        dispatcher=dispatcher,
    )

    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=1))
    dispatcher.run_next()
    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=2))
    _request, _cancellation, handle = executor.submitted[0]
    caplog.set_level(
        logging.WARNING,
        logger="presentation.editor.panel.lora_metadata_refresh_controller",
    )

    handle.fail(RuntimeError("prompt metadata secret"))

    assert catalog.installed == []
    assert dispatcher.run_next() == "lora_metadata_followup_refresh"
    assert len(executor.submitted) == 2
    assert "LoRA prompt snapshot adaptation task failed" in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert "prompt metadata secret" not in caplog.text


def test_panel_lora_metadata_refresh_controller_shutdown_stops_future_work() -> None:
    """Shutdown should stop future requests and cancel active injected work."""

    _ensure_qapp()
    dispatcher = _Dispatcher()
    executor = _Executor()
    controller = PanelLoraMetadataRefreshController(
        catalog_service=cast(Any, _CatalogService()),
        editor_panels=lambda: (),
        executor=cast(PromptEditorExecutor, executor),
        dispatcher=dispatcher,
    )
    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=1))
    dispatcher.run_next()
    _request, cancellation, handle = executor.submitted[0]

    controller.shutdown()
    controller.request_lora_snapshot_adaptation(_model_snapshot(generation=2))

    assert cancellation.is_cancelled is True
    assert handle.cancel_reasons == ["lora_metadata_shutdown"]
    assert len(executor.submitted) == 1


def test_editor_panel_lora_metadata_controller_marks_prompt_editors_dirty() -> None:
    """Panel-local dirty marking should use prompt-editor public APIs."""

    editors = (_PromptEditor(), _PromptEditor())
    host = _PanelHost(editors)
    controller = EditorPanelLoraMetadataRefreshController(
        cast(EditorPanelLoraMetadataRefreshHost, host)
    )

    controller.mark_lora_metadata_dirty()

    assert [editor.mark_calls for editor in editors] == [1, 1]


def test_editor_panel_lora_metadata_controller_counts_visible_refreshes() -> None:
    """Panel-local visible refresh should count editors that perform work."""

    editors = (_PromptEditor(refreshed=True), _PromptEditor(refreshed=False))
    host = _PanelHost(editors)
    controller = EditorPanelLoraMetadataRefreshController(
        cast(EditorPanelLoraMetadataRefreshHost, host)
    )

    refreshed_count = controller.refresh_visible_lora_metadata()

    assert refreshed_count == 1
    assert [editor.refresh_calls for editor in editors] == [1, 1]


def _prompt_snapshot(*, model_generation: int) -> PromptLoraCatalogSnapshot:
    """Return an empty catalog snapshot for controller tests."""

    return PromptLoraCatalogSnapshot(
        items=(),
        prompt_name_items={},
        backend_value_items={},
        backend_prompt_items={},
        collision_items={},
        autocomplete_exact_items={},
        path_suffix_items={},
        model_generation=model_generation,
        revision=0,
    )


def _model_snapshot(*, generation: int, kind: str = "loras") -> ModelCatalogSnapshot:
    """Return a canonical model snapshot for controller tests."""

    return ModelCatalogSnapshot(
        kind=kind,
        items=(_model_item(),),
        generation=generation,
    )


def _model_item() -> ModelCatalogItem:
    """Return one canonical LoRA model item for controller tests."""

    return ModelCatalogItem(
        kind="loras",
        display_name="Midna",
        display_subtitle=None,
        backend_value="midna.safetensors",
        relative_path="midna.safetensors",
        folder="",
        basename="midna",
        extension=".safetensors",
        thumbnail_variants=(),
        base_model=None,
        trained_words=(),
        tags=(),
        model_page_url=None,
        collision_key="midna",
        collision_count=1,
        has_collision=False,
        search_text="midna",
    )


def _ensure_qapp() -> QApplication:
    """Return a Qt application for QObject construction."""

    return cast(QApplication, QApplication.instance() or QApplication([]))

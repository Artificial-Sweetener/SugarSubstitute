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

"""Contract tests for the editor-first prompt autocomplete surface."""

from __future__ import annotations

import os
import logging
import math
from collections.abc import Callable, Iterator
from typing import Any, Generic, TypeVar, cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFontMetricsF, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLineEdit,
    QMenu,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets.components.widgets.line_edit import (  # type: ignore[import-untyped]
    CompleterMenu,
    LineEdit,
)
from shiboken6 import delete, isValid

from substitute.application.danbooru import (
    DanbooruFailureReason,
    DanbooruImportedPrompt,
    DanbooruPromptImportResult,
    DanbooruUrlClassification,
    DanbooruUrlImportService,
    DanbooruUrlKind,
)
from substitute.application.ports import (
    PromptAutocompleteGateway,
    PromptAutocompleteSuggestion,
)
from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
    PromptFeatureDecision,
    PromptLoraAutocompleteCandidate,
    PromptLoraCatalogItem,
    PromptLoraScheduleService,
)
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.widgets.fluent_popup_frame import (
    AttachedFluentPopupFrame,
)
from substitute.presentation.editor.prompt_editor.projection.model import (
    PromptProjectionDocument,
    PromptProjectionTokenKind,
)
from substitute.presentation.editor.prompt_editor.projection.session import (
    PromptProjectionSession,
)
from substitute.presentation.editor.prompt_editor.async_work import (
    PromptAsyncRequest,
    PromptAsyncResultIdentity,
    PromptAsyncTaskOutcome,
    PromptEditorCancellationToken,
    PromptEditorExecutor,
    PromptEditorTaskHandle,
    QtDanbooruUrlImportDispatcher,
)
from substitute.presentation.editor.prompt_editor.autocomplete_preview_state import (
    PromptAutocompletePreviewState,
)
from substitute.presentation.editor.prompt_editor.overlays import (
    PromptAutocompleteLoraWall,
    PromptAutocompleteLoraWallRenderState,
    PromptAutocompletePanel,
    PromptAutocompletePanelRenderState,
    PromptAutocompleteRow,
    PromptAutocompleteRowRenderState,
    PromptLoraWallView,
    SegmentReorderOverlay,
)
from substitute.presentation.editor.prompt_editor import PromptEditor
from tests.prompt_autocomplete_test_helpers import (
    EmptyPromptWildcardCatalogGateway,
    prompt_syntax_profile,
)
from tests.execution_test_helpers import immediate_prompt_task_executor_factory
from tests.prompt_projection_test_helpers import surface_for
from substitute.application.prompt_editor import PromptGapBlankLineDropTarget

TResult = TypeVar("TResult")

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "real prompt autocomplete surface tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _StaticPromptAutocompleteGateway:
    """Return deterministic autocomplete suggestions for one prefix map."""

    def __init__(
        self,
        results_by_prefix: dict[str, tuple[PromptAutocompleteSuggestion, ...]],
    ) -> None:
        """Store deterministic suggestion tuples keyed by typed prefix."""

        self._results_by_prefix = dict(results_by_prefix)
        self.calls: list[tuple[str, int]] = []

    def search(
        self,
        prefix: str,
        limit: int = 10,
    ) -> tuple[PromptAutocompleteSuggestion, ...]:
        """Record one query and return the configured suggestion tuple."""

        self.calls.append((prefix, limit))
        return self._results_by_prefix.get(prefix, ())


class _StaticPromptLoraCatalog:
    """Return deterministic LoRA catalog rows for prompt editor tests."""

    def __init__(self, items: tuple[PromptLoraCatalogItem, ...]) -> None:
        """Store catalog rows."""

        self._items = items
        self.calls = 0

    def list_loras(self) -> tuple[PromptLoraCatalogItem, ...]:
        """Return the configured LoRA rows."""

        self.calls += 1
        return self._items

    def cached_loras(self) -> tuple[PromptLoraCatalogItem, ...] | None:
        """Return configured LoRA rows without simulating backend loading."""

        return self._items

    def find_lora(self, prompt_name: str) -> PromptLoraCatalogItem | None:
        """Return the configured LoRA row matching one prompt name."""

        normalized_prompt_name = prompt_name.replace("\\", "/").casefold()
        for item in self._items:
            if item.prompt_name.replace("\\", "/").casefold() == normalized_prompt_name:
                return item
        return None


class _StaticDanbooruUrlImportService:
    """Return deterministic Danbooru URL import outcomes for paste tests."""

    def __init__(
        self,
        *,
        classification: DanbooruUrlClassification | None,
        result: DanbooruPromptImportResult,
    ) -> None:
        """Store deterministic classification and import outcomes."""

        self._classification = classification
        self._result = result
        self.classify_calls: list[str] = []
        self.import_calls: list[str] = []

    def classify_url(self, text: str) -> DanbooruUrlClassification | None:
        """Return the configured URL classification for the pasted text."""

        self.classify_calls.append(text)
        return self._classification

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Return the configured import result for the pasted text."""

        self.import_calls.append(text)
        return self._result


class _FailingDanbooruUrlImportService(_StaticDanbooruUrlImportService):
    """Raise deterministic import failures for paste logging tests."""

    def __init__(self, *, classification: DanbooruUrlClassification) -> None:
        """Store the classification used before the import failure."""

        super().__init__(
            classification=classification,
            result=DanbooruPromptImportResult(imported_prompt=None),
        )

    def import_prompt_from_url(self, text: str) -> DanbooruPromptImportResult:
        """Raise an error that includes content which logs must not serialize."""

        self.import_calls.append(text)
        raise RuntimeError(text)


class _ImmediateDanbooruImportDispatcher:
    """Run Danbooru paste lookups immediately for deterministic GUI tests."""

    def submit(
        self,
        lookup: Any,
        *,
        completed: Any,
        failed: Any,
    ) -> None:
        """Execute the lookup inline and report through the supplied callbacks."""

        try:
            completed(lookup())
        except BaseException as error:  # noqa: BLE001
            failed(error)


def _configure_danbooru_url_import(
    editor: PromptEditor,
    service: object,
    *,
    dispatcher: Any,
) -> None:
    """Configure Danbooru paste/import through the composed controller."""

    cast(Any, editor)._danbooru_paste_import_controller.configure_danbooru_url_import(
        cast(DanbooruUrlImportService, service),
        enabled=True,
        dispatcher=dispatcher,
    )


class _DanbooruTaskHandle(Generic[TResult]):
    """Expose one controllable async task handle for Danbooru dispatcher tests."""

    def __init__(self, request: PromptAsyncRequest[TResult]) -> None:
        """Store the async request and initialize callback recording."""

        self._request = request
        self._callbacks: list[Callable[[PromptAsyncTaskOutcome[TResult]], None]] = []
        self._outcome: PromptAsyncTaskOutcome[TResult] | None = None
        self.cancel_reasons: list[str] = []

    @property
    def identity(self) -> PromptAsyncResultIdentity:
        """Return the submitted request identity."""

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
        """Record completion callbacks for deterministic delivery."""

        _ = reason
        self._callbacks.append(callback)

    def cancel(self, *, reason: str) -> None:
        """Record cancellation requests."""

        self.cancel_reasons.append(reason)

    def complete(self, result: TResult) -> None:
        """Publish a successful completion."""

        self._finish(
            PromptAsyncTaskOutcome(
                identity=self.identity,
                context=self._request.context,
                result=result,
            )
        )

    def fail(self, error: BaseException) -> None:
        """Publish a failed completion."""

        self._finish(
            PromptAsyncTaskOutcome(
                identity=self.identity,
                context=self._request.context,
                error=error,
            )
        )

    def _finish(self, outcome: PromptAsyncTaskOutcome[TResult]) -> None:
        """Deliver one terminal outcome to all registered callbacks."""

        self._outcome = outcome
        callbacks = tuple(self._callbacks)
        self._callbacks.clear()
        for callback in callbacks:
            callback(outcome)


class _DanbooruExecutor:
    """Record Danbooru async requests without running background work."""

    def __init__(self) -> None:
        """Initialize submitted request tracking."""

        self.handles: list[_DanbooruTaskHandle[DanbooruPromptImportResult]] = []
        self.cancellations: list[PromptEditorCancellationToken] = []

    def submit(
        self,
        request: PromptAsyncRequest[DanbooruPromptImportResult],
        *,
        cancellation: PromptEditorCancellationToken,
    ) -> PromptEditorTaskHandle[DanbooruPromptImportResult]:
        """Record one submitted request and return a controllable handle."""

        handle: _DanbooruTaskHandle[DanbooruPromptImportResult] = _DanbooruTaskHandle(
            request
        )
        self.handles.append(handle)
        self.cancellations.append(cancellation)
        return handle


def ensure_qapp() -> QApplication:
    """Return a running Qt application for autocomplete widget tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def process_events(app: QApplication, cycles: int = 10) -> None:
    """Flush event-loop turns plus frame timers so autocomplete state settles."""

    for _ in range(cycles):
        app.processEvents()
        QTest.qWait(5)


def move_cursor_to_end(box: PromptEditor) -> None:
    """Move the prompt-editor cursor to the document end."""

    cursor = box.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    box.setTextCursor(cursor)


def create_prompt_editor(
    *,
    parent: QWidget | None = None,
    prompt_autocomplete_gateway: PromptAutocompleteGateway,
    danbooru_url_import_service: _StaticDanbooruUrlImportService | None = None,
    prompt_feature_profile: PromptEditorFeatureProfile | None = None,
) -> PromptEditor:
    """Create one prompt editor with the standard Phase 12 test dependencies."""

    return PromptEditor(
        parent,
        prompt_autocomplete_gateway=prompt_autocomplete_gateway,
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        danbooru_url_import_service=cast(
            DanbooruUrlImportService | None,
            danbooru_url_import_service,
        ),
        prompt_feature_profile=prompt_feature_profile,
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard"),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )


def create_lora_prompt_editor(
    *,
    parent: QWidget | None = None,
    loras: tuple[PromptLoraCatalogItem, ...],
) -> PromptEditor:
    """Create one prompt editor with LoRA syntax and catalog autocomplete enabled."""

    return PromptEditor(
        parent,
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        prompt_syntax_profile=prompt_syntax_profile("emphasis", "wildcard", "lora"),
        prompt_lora_catalog_service=_StaticPromptLoraCatalog(loras),
        prompt_task_executor_factory=immediate_prompt_task_executor_factory(),
    )


def _profile_without_ghost_text() -> PromptEditorFeatureProfile:
    """Return a prompt feature profile that disables only autocomplete ghost text."""

    return PromptEditorFeatureProfile(
        decisions=tuple(
            PromptFeatureDecision(
                feature=feature,
                enabled=feature is not PromptEditorFeature.AUTOCOMPLETE_GHOST_TEXT,
            )
            for feature in PromptEditorFeature
        )
    )


def test_danbooru_import_dispatcher_drops_completion_after_parent_deleted() -> None:
    """Danbooru task completion should not publish after Qt teardown."""

    ensure_qapp()
    parent = QWidget()
    executor = _DanbooruExecutor()
    completed: list[DanbooruPromptImportResult] = []
    failed: list[BaseException] = []
    dispatcher = QtDanbooruUrlImportDispatcher(
        parent,
        is_alive=isValid,
        executor=cast(PromptEditorExecutor, executor),
    )
    dispatcher.submit(
        lambda: DanbooruPromptImportResult(imported_prompt=None),
        completed=completed.append,
        failed=failed.append,
    )

    delete(parent)

    executor.handles[0].complete(DanbooruPromptImportResult(imported_prompt=None))

    assert completed == []
    assert failed == []
    assert executor.handles[0].cancel_reasons == ["danbooru_url_import_shutdown"]
    assert executor.cancellations[0].is_cancelled is True


def _sample_suggestions() -> tuple[PromptAutocompleteSuggestion, ...]:
    """Return stable suggestions used across autocomplete surface tests."""

    return (
        PromptAutocompleteSuggestion("1girl", 5_889_398),
        PromptAutocompleteSuggestion("1girls", 3_424),
    )


def _sample_lora(
    *,
    display_name: str = "CivitAI Midna",
    basename: str = "raw_midna",
    prompt_name: str = r"illustrious\characters\raw_midna",
) -> PromptLoraCatalogItem:
    """Return one stable LoRA catalog item for autocomplete tests."""

    return PromptLoraCatalogItem(
        display_name=display_name,
        display_subtitle=None,
        prompt_name=prompt_name,
        backend_value=f"{prompt_name}.safetensors",
        relative_path=f"{prompt_name}.safetensors",
        folder=prompt_name.rsplit("\\", 1)[0] if "\\" in prompt_name else "",
        basename=basename,
        extension=".safetensors",
        thumbnail_variants=(),
        base_model="Illustrious",
        trained_words=(),
        tags=("character",),
        model_page_url=None,
        collision_key=basename.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=" ".join((display_name, basename, prompt_name)).casefold(),
    )


def test_prompt_editor_autocomplete_preview_reflows_downstream_text(
    widgets: list[QWidget],
) -> None:
    """Layout-backed ghost text should wrap following text as real text would."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(230, 220)
    box = create_prompt_editor(
        parent=host,
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
    )
    box.setGeometry(10, 10, 200, 140)
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.extend([host, box])
    process_events(app)

    surface = surface_for(box)
    shell_width = box.width() - round(
        cast(Any, surface)._layout.metrics.wrap_width  # noqa: SLF001
    )
    preview_line_width = math.ceil(
        QFontMetricsF(box.font()).horizontalAdvance("alpha bright ")
    )
    box.setFixedWidth(shell_width + preview_line_width + 2)
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    process_events(app)

    assert _active_projection_line_texts(box) == ("alpha omega",)

    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text="bright ",
        )
    )
    process_events(app)

    configured_width: int | None = None
    for width in range(box.width(), 79, -4):
        box.setFixedWidth(width)
        process_events(app)
        line_texts = _active_projection_line_texts(box)
        if len(line_texts) > 1 and line_texts[-1].endswith("omega"):
            configured_width = width
            break

    assert box.toPlainText() == "alpha omega"
    assert configured_width is not None
    line_texts = _active_projection_line_texts(box)
    assert len(line_texts) > 1
    assert line_texts[-1].endswith("omega")


def test_prompt_editor_autocomplete_preview_does_not_mutate_source_or_undo(
    widgets: list[QWidget],
) -> None:
    """Preview layout changes should not emit textChanged or alter undo state."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    box = create_prompt_editor(
        parent=host,
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
    )
    box.setGeometry(10, 10, 260, 140)
    host.show()
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.extend([host, box])
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    process_events(app)

    changed_count = 0

    def record_text_changed() -> None:
        """Record an unexpected source text change."""

        nonlocal changed_count
        changed_count += 1

    box.textChanged.connect(record_text_changed)
    surface = surface_for(box)
    can_undo_before = surface.can_undo()

    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text="bright ",
        )
    )
    process_events(app)

    assert box.toPlainText() == "alpha omega"
    assert changed_count == 0
    assert surface.can_undo() is can_undo_before


def test_prompt_editor_autocomplete_preview_clears_on_selection(
    widgets: list[QWidget],
) -> None:
    """Selecting real text should remove active non-source-backed preview layout."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
    )
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.append(box)
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    surface = surface_for(box)
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text="bright ",
        )
    )
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(0)
    cursor.setPosition(5, QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    assert _editor_autocomplete_preview_text(box) == ""
    assert surface.active_projection_document().projection_text == "alpha omega"


def test_prompt_editor_autocomplete_preview_clears_on_source_edit(
    widgets: list[QWidget],
) -> None:
    """Typing real source text should remove stale active autocomplete preview."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
    )
    box.show()
    box.setFocus()
    box.setPlainText("alpha omega")
    widgets.append(box)
    process_events(app)

    cursor = box.textCursor()
    cursor.setPosition(len("alpha "))
    box.setTextCursor(cursor)
    process_events(app)

    surface = surface_for(box)
    surface.set_autocomplete_preview_state(
        PromptAutocompletePreviewState(
            source_position=len("alpha "),
            suffix_text="bright ",
        )
    )
    process_events(app)

    assert _editor_autocomplete_preview_text(box) == "bright "
    assert surface.active_projection_document().projection_text == "alpha bright omega"

    QTest.keyClicks(box, "x")
    process_events(app)

    assert box.toPlainText() == "alpha xomega"
    assert surface.active_projection_document().projection_text == "alpha xomega"


def _lora_candidate(
    item: PromptLoraCatalogItem,
    *,
    suffix: str = "itAI Midna",
) -> PromptLoraAutocompleteCandidate:
    """Return one stable LoRA autocomplete candidate."""

    return PromptLoraAutocompleteCandidate(
        item=item,
        score=100,
        display_text=item.display_name or item.basename,
        display_completion_suffix=suffix,
        replacement_text=PromptLoraScheduleService().schedule_text(item),
        match_kind="display_prefix",
    )


def _panel_rows(panel: PromptAutocompletePanel) -> list[PromptAutocompleteRow]:
    """Return the direct child row widgets in render order."""

    return cast(
        list[PromptAutocompleteRow],
        panel.findChildren(
            PromptAutocompleteRow,
            options=Qt.FindChildOption.FindDirectChildrenOnly,
        ),
    )


def _autocomplete_panel(host: QWidget) -> PromptAutocompletePanel:
    """Create an autocomplete panel with the current LoRA wall adapter."""

    panel = PromptAutocompletePanel(host)
    panel.set_lora_wall(
        _autocomplete_lora_wall(
            panel,
            thumbnail_cache=PromptLoraThumbnailCache(),
        )
    )
    return panel


def _autocomplete_lora_wall(
    parent: QWidget,
    *,
    thumbnail_cache: object,
) -> PromptAutocompleteLoraWall:
    """Create the current concrete LoRA wall for autocomplete panel tests."""

    return cast(
        PromptAutocompleteLoraWall,
        PromptLoraWallView(
            parent,
            thumbnail_cache=cast(PromptLoraThumbnailCache, thumbnail_cache),
        ),
    )


def _row_texts(row: PromptAutocompleteRow) -> tuple[str, str]:
    """Return the row-owned rendered tag and popularity strings."""

    return row.rendered_tag_text(), row.rendered_secondary_text()


def _row_render_state_from_suggestions(
    suggestions: tuple[PromptAutocompleteSuggestion, ...],
) -> tuple[PromptAutocompleteRowRenderState, ...]:
    """Return prepared row state matching autocomplete result presentation."""

    return tuple(
        PromptAutocompleteRowRenderState(
            index=index,
            title=suggestion.tag,
            source_label=(
                suggestion.source_label
                if suggestion.source_label is not None
                else (f"{suggestion.popularity:,}" if suggestion.popularity else "")
            ),
            is_selected=index == 0,
            payload=suggestion,
        )
        for index, suggestion in enumerate(suggestions)
    )


def _render_panel_rows(
    panel: PromptAutocompletePanel,
    suggestions: tuple[PromptAutocompleteSuggestion, ...],
) -> None:
    """Render prepared tag autocomplete rows through the panel state boundary."""

    panel.set_render_state(
        PromptAutocompletePanelRenderState(
            rows=_row_render_state_from_suggestions(suggestions),
            visible=True,
        )
    )


def _render_panel_lora_candidates(
    panel: PromptAutocompletePanel,
    candidates: tuple[PromptLoraAutocompleteCandidate, ...],
) -> None:
    """Render prepared LoRA autocomplete candidates through the panel boundary."""

    panel.set_render_state(
        PromptAutocompletePanelRenderState(
            lora_wall=PromptAutocompleteLoraWallRenderState(
                items=tuple(candidate.item for candidate in candidates),
                selected_index=0 if candidates else -1,
                activation_payloads=candidates,
            ),
            visible=True,
        )
    )


def _overlay_chip_widgets(overlay: QWidget) -> list[QWidget]:
    """Return visible reorder chips sorted by their rendered position."""

    chips = list(overlay.findChildren(QWidget, "segmentChip"))
    return sorted(
        chips,
        key=lambda chip: (
            chip.mapToGlobal(chip.rect().topLeft()).y(),
            chip.mapToGlobal(chip.rect().topLeft()).x(),
        ),
    )


def _overlay_preview_segment_indices(overlay: QWidget) -> list[int]:
    """Return visible reorder preview indices in render order."""

    return cast(SegmentReorderOverlay, overlay).preview_chip_indices()


def _overlay_blank_line_target_visuals(overlay: QWidget) -> tuple[object, ...]:
    """Return the current virtual blank-line target visuals for the reorder overlay."""

    visuals = cast(Any, overlay)._drop_target_visuals
    return tuple(
        visual
        for visual in cast(tuple[object, ...], visuals)
        if isinstance(cast(Any, visual).target, PromptGapBlankLineDropTarget)
    )


def _editor_reorder_preview_document(
    box: PromptEditor,
) -> PromptProjectionDocument | None:
    """Return the surface-owned preview document active during reorder mode."""

    return cast(
        PromptProjectionDocument | None,
        getattr(surface_for(box), "_reorder_preview_projection").preview_document,
    )


def _editor_reorder_preview_text(box: PromptEditor) -> str:
    """Return the surface-owned preview text active during reorder mode."""

    preview_document = _editor_reorder_preview_document(box)
    if preview_document is None:
        return ""
    return preview_document.source_text


def _editor_autocomplete_preview_text(box: PromptEditor) -> str:
    """Return the surface-owned autocomplete preview suffix when it is active."""

    preview_state = cast(
        Any,
        getattr(surface_for(box), "_session"),
    ).autocomplete_preview
    if preview_state is None:
        return ""
    return cast(str, preview_state.suffix_text)


def _active_projection_line_texts(box: PromptEditor) -> tuple[str, ...]:
    """Return visual-line text from the active projection layout."""

    surface = surface_for(box)
    layout = getattr(
        surface,
        "_layout",
    )
    snapshot = cast(Any, layout)._snapshot
    return tuple(
        "".join(
            fragment.text for fragment in line.fragments if hasattr(fragment, "text")
        )
        for line in snapshot.lines
    )


def _overlay_chip_by_segment_index(overlay: QWidget, segment_index: int) -> QWidget:
    """Return one rendered reorder chip by its segment index property."""

    for chip in overlay.findChildren(QWidget, "segmentChip"):
        if chip.property("segmentIndex") == segment_index:
            return chip
    raise AssertionError(f"Missing segment chip for index {segment_index}.")


def _overlay_drag_proxy(overlay: QWidget) -> QWidget:
    """Return the floating drag proxy widget used during segment dragging."""

    return cast(SegmentReorderOverlay, overlay).drag_proxy_widget()


def _drag_reorder_chip_to_global(
    chip: QWidget,
    *,
    global_target: QPoint,
) -> None:
    """Drag one reorder hotspot to the supplied global position."""

    start = chip.rect().center()
    target = chip.mapFromGlobal(global_target)
    QTest.mousePress(chip, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(chip, target, 10)
    QTest.mouseRelease(chip, Qt.MouseButton.LeftButton, pos=target, delay=10)


@pytest.fixture()
def widgets() -> Iterator[list[QWidget]]:
    """Track and dispose widgets created during one autocomplete widget test."""

    created: list[QWidget] = []
    yield created
    app = ensure_qapp()
    for widget in reversed(created):
        widget.close()
        widget.deleteLater()
    process_events(app)


def test_prompt_autocomplete_panel_builds_tag_and_popularity_rows(
    widgets: list[QWidget],
) -> None:
    """Panel rows should render only tag text and formatted popularity text."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = _autocomplete_panel(host)
    _render_panel_rows(panel, _sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    rows = _panel_rows(panel)
    assert len(rows) == 2

    first_tag, first_popularity = _row_texts(rows[0])
    second_tag, second_popularity = _row_texts(rows[1])

    assert first_tag == "1girl"
    assert first_popularity == "5,889,398"
    assert second_tag == "1girls"
    assert second_popularity == "3,424"
    assert (
        "General" not in first_tag + first_popularity + second_tag + second_popularity
    )
    assert (
        "danbooru" not in first_tag + first_popularity + second_tag + second_popularity
    )
    assert isinstance(panel, QMenu) is False


def test_prompt_autocomplete_panel_renders_prepared_state_and_activation_intent(
    widgets: list[QWidget],
) -> None:
    """Prepared panel state should render rows and relay activation intent."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    host.show()
    widgets.append(host)
    panel = _autocomplete_panel(host)
    widgets.append(panel)
    activated: list[int] = []
    panel.set_activation_handler(lambda intent: activated.append(intent.index))

    panel.set_render_state(
        PromptAutocompletePanelRenderState(
            rows=(
                PromptAutocompleteRowRenderState(
                    index=0,
                    title="1girl",
                    source_label="5,889,398",
                    is_selected=True,
                ),
                PromptAutocompleteRowRenderState(
                    index=1,
                    title="1girls",
                    source_label="3,424",
                ),
            ),
            visible=True,
            anchor_rect=QRect(20, 20, 1, 18),
        )
    )
    panel.show_overlay(QRect(20, 20, 1, 18))
    process_events(app)

    rows = _panel_rows(panel)
    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert [_row_texts(row) for row in rows] == [
        ("1girl", "5,889,398"),
        ("1girls", "3,424"),
    ]

    QTest.mouseClick(rows[1], Qt.MouseButton.LeftButton, pos=QPoint(4, 4))
    process_events(app)

    assert activated == [1]


def test_prompt_autocomplete_panel_renders_lora_source_label(
    widgets: list[QWidget],
) -> None:
    """LoRA trigger rows should render their source label instead of popularity."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = _autocomplete_panel(host)
    _render_panel_rows(
        panel,
        (
            PromptAutocompleteSuggestion(
                "midna helmet",
                popularity=None,
                source_label="Friendly Midna",
                source_kind="lora_trigger",
            ),
        ),
    )
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    rows = _panel_rows(panel)
    assert len(rows) == 1
    tag_text, source_text = _row_texts(rows[0])
    assert tag_text.startswith("midna hel")
    assert source_text.startswith("Friendly Mid")


def test_prompt_autocomplete_panel_uses_editor_attached_fluent_frame(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should share QFluent frame chrome without becoming a popup."""

    ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    panel = _autocomplete_panel(host)
    widgets.extend([host, panel])

    assert isinstance(panel, AttachedFluentPopupFrame)
    assert panel.parentWidget() is host
    assert not bool(panel.windowFlags() & Qt.WindowType.Popup)


def test_prompt_autocomplete_panel_updates_selected_row(
    widgets: list[QWidget],
) -> None:
    """Panel selection should track the requested row index."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = _autocomplete_panel(host)
    _render_panel_rows(panel, _sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    panel.set_current_index(0)
    assert panel.current_index() == 0

    panel.set_current_index(1)
    process_events(app)

    rows = _panel_rows(panel)
    assert panel.current_index() == 1
    assert bool(rows[0].property("selected")) is False
    assert bool(rows[1].property("selected")) is True


def test_prompt_autocomplete_panel_detaches_stale_rows_during_rapid_refresh(
    widgets: list[QWidget],
) -> None:
    """Rapid tag refreshes should not leave old visible rows stacked in the panel."""

    ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = _autocomplete_panel(host)
    _render_panel_rows(panel, _sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    _render_panel_rows(
        panel,
        (
            PromptAutocompleteSuggestion("solo", 10),
            PromptAutocompleteSuggestion("solo focus", 8),
        ),
    )
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)

    rows = _panel_rows(panel)

    assert [row.rendered_tag_text() for row in rows] == ["solo", "solo focus"]
    assert all(row.isVisible() for row in rows)
    assert len({row.geometry().top() for row in rows}) == len(rows)


def test_prompt_autocomplete_panel_rows_own_text_painting(
    widgets: list[QWidget],
) -> None:
    """Autocomplete rows should not compose child labels over row fills."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = _autocomplete_panel(host)
    _render_panel_rows(panel, _sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    rows = _panel_rows(panel)
    lora_wall = panel.lora_wall()

    assert rows
    assert all(row.findChildren(QWidget) == [] for row in rows)
    assert lora_wall is not None
    assert lora_wall.isHidden()


def test_prompt_autocomplete_panel_matches_qfluent_completer_metrics(
    widgets: list[QWidget],
) -> None:
    """Autocomplete panel metrics should match the live QFluent completer shell."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = _autocomplete_panel(host)
    _render_panel_rows(panel, _sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)

    reference_line_edit = LineEdit(host)
    reference_menu = CompleterMenu(reference_line_edit)
    reference_menu.setItems(["1girl", "1girls"])
    widgets.extend([reference_line_edit, reference_menu])
    process_events(app)

    rows = _panel_rows(panel)
    layout = panel.content_layout()
    assert layout is not None
    margins = layout.contentsMargins()
    reference_margins = reference_menu.view.viewportMargins()

    assert rows[0].height() == reference_menu.itemHeight
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        reference_margins.left(),
        reference_margins.top(),
        reference_margins.right(),
        reference_margins.bottom(),
    )


def test_prompt_autocomplete_panel_click_emits_row_index(
    widgets: list[QWidget],
) -> None:
    """Clicking a rendered row should emit its suggestion index."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(360, 220)
    host.show()
    widgets.append(host)

    panel = _autocomplete_panel(host)
    activated: list[int] = []
    panel.suggestionActivated.connect(activated.append)
    _render_panel_rows(panel, _sample_suggestions())
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    row = _panel_rows(panel)[1]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert activated == [1]


def test_prompt_autocomplete_panel_hosts_lora_wall_without_tag_rows(
    widgets: list[QWidget],
) -> None:
    """LoRA mode should reuse the panel shell with wall content instead of rows."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    host.show()
    widgets.append(host)
    panel = _autocomplete_panel(host)
    item = _sample_lora()

    _render_panel_lora_candidates(panel, (_lora_candidate(item),))
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    wall = panel.lora_wall()
    assert wall is not None
    assert isinstance(wall, PromptLoraWallView)
    assert panel.is_panel_visible() is True
    assert _panel_rows(panel) == []
    assert wall.items()[0].title == "CivitAI Midna"
    assert panel.findChildren(QLineEdit) == []
    assert isinstance(panel, QMenu) is False


def test_prompt_autocomplete_panel_uses_taller_lora_wall_geometry(
    widgets: list[QWidget],
) -> None:
    """LoRA autocomplete should share the taller picker popup height."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 760)
    host.show()
    widgets.append(host)
    panel = _autocomplete_panel(host)

    _render_panel_lora_candidates(panel, (_lora_candidate(_sample_lora()),))
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    assert panel.width() == 560
    assert panel.height() == 630


def test_prompt_autocomplete_panel_lora_wall_click_emits_candidate_index(
    widgets: list[QWidget],
) -> None:
    """Wall activation should flow through the autocomplete panel as an index."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    host.show()
    widgets.append(host)
    panel = _autocomplete_panel(host)
    item = _sample_lora()
    activated: list[int] = []
    panel.loraActivated.connect(activated.append)

    _render_panel_lora_candidates(panel, (_lora_candidate(item),))
    widgets.append(panel)
    process_events(app)
    wall = panel.lora_wall()
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    assert wall.activate_current() is True

    assert activated == [0]


def test_prompt_autocomplete_panel_lora_wall_uses_directional_navigation(
    widgets: list[QWidget],
) -> None:
    """LoRA wall navigation should move up and down by visual rows."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    host.show()
    widgets.append(host)
    panel = _autocomplete_panel(host)
    candidates = tuple(
        _lora_candidate(
            _sample_lora(
                display_name=f"LoRA {index}",
                basename=f"lora_{index}",
                prompt_name=rf"folder\lora_{index}",
            )
        )
        for index in range(20)
    )
    _render_panel_lora_candidates(panel, candidates)
    panel.show_for_editor(host, QRect(24, 24, 1, 18))
    widgets.append(panel)
    process_events(app)

    panel.set_current_index(1)
    panel.move_current_lora_down()
    process_events(app)
    assert panel.current_index() == 5

    down_index = panel.current_index()
    panel.move_current_lora_up()
    process_events(app)
    assert panel.current_index() == 1

    panel.set_current_index(down_index)
    panel.move_current_lora_right()
    process_events(app)
    assert panel.current_index() == down_index + 1


def test_prompt_autocomplete_panel_defers_lora_selection_until_shown(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LoRA selection should use final popup geometry instead of hidden layout."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 760)
    host.show()
    widgets.append(host)
    panel = _autocomplete_panel(host)
    candidates = tuple(
        _lora_candidate(
            _sample_lora(
                display_name=f"LoRA {index}",
                basename=f"lora_{index}",
                prompt_name=rf"folder\lora_{index}",
            )
        )
        for index in range(20)
    )
    selection_viewport_heights: list[int] = []
    original_set_current_index = PromptLoraWallView.set_current_index

    def record_set_current_index(self: PromptLoraWallView, index: int) -> None:
        """Record the viewport height used when selecting a LoRA tile."""

        selection_viewport_heights.append(self.viewport().height())
        original_set_current_index(self, index)

    monkeypatch.setattr(
        PromptLoraWallView,
        "set_current_index",
        record_set_current_index,
    )

    _render_panel_lora_candidates(panel, candidates)

    assert selection_viewport_heights == []

    panel.show_for_editor(host, QRect(24, 700, 1, 18))
    widgets.append(panel)
    process_events(app)
    panel.set_current_index(0)

    assert selection_viewport_heights[-1] >= 100


def test_prompt_lora_wall_skips_unchanged_lora_items(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated LoRA candidates should not rebuild the media wall contents."""

    item = _sample_lora()
    wall = PromptLoraWallView(
        thumbnail_cache=PromptLoraThumbnailCache(),
    )
    widgets.append(wall)
    wall.set_loras((item,))
    rebuilds: list[object] = []

    def record_rebuild(items: object) -> None:
        """Record unexpected media wall rebuild requests."""

        rebuilds.append(items)

    monkeypatch.setattr(wall, "set_picker_items", record_rebuild)

    wall.set_loras((item,))

    assert rebuilds == []


def test_prompt_autocomplete_panel_reuses_lora_wall_for_same_items(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Panel refreshes should not rebuild LoRA wall layout when items are unchanged."""

    host = QWidget()
    widgets.append(host)
    panel = _autocomplete_panel(host)
    widgets.append(panel)
    item = _sample_lora()
    first_candidate = _lora_candidate(item, suffix="itAI Midna")
    next_candidate = _lora_candidate(item, suffix="AI Midna")
    _render_panel_lora_candidates(panel, (first_candidate,))
    wall = panel.lora_wall()
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    set_lora_calls: list[object] = []

    def record_set_loras(items: object) -> None:
        """Record unexpected media wall item replacement requests."""

        set_lora_calls.append(items)

    monkeypatch.setattr(wall, "set_loras", record_set_loras)

    _render_panel_lora_candidates(panel, (next_candidate,))
    assert wall.activate_current() is True

    assert set_lora_calls == []


def test_prompt_editor_projection_owned_preview_tracks_suffix_and_clear_state(
    widgets: list[QWidget],
) -> None:
    """Autocomplete preview should live in the projection session and clear cleanly."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1g": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    assert _editor_autocomplete_preview_text(box) == "irl"

    QTest.keyClick(box, Qt.Key.Key_Escape)
    process_events(app)

    assert _editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_disabled_ghost_text_keeps_autocomplete_panel(
    widgets: list[QWidget],
) -> None:
    """Ghost-text settings should not disable autocomplete suggestions."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1g": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=gateway,
        prompt_feature_profile=_profile_without_ghost_text(),
    )
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    assert panel.is_panel_visible() is True
    assert box.toPlainText() == "1g"
    assert _editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_real_widget_keeps_typing_flow_and_updates_inline_preview(
    widgets: list[QWidget],
) -> None:
    """PromptEditor should keep focus while typing and update the ghost suffix live."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway(
        {
            "1g": suggestions,
            "1gi": suggestions,
        }
    )

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    assert gateway.calls[-1] == ("1g", 10)
    assert box.toPlainText() == "1g"
    assert box.hasFocus() is True
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "irl"
    assert panel.parentWidget() is host
    assert panel.geometry().bottom() > box.geometry().bottom()

    QTest.keyClicks(box, "i")
    process_events(app)

    assert gateway.calls[-1] == ("1gi", 10)
    assert box.toPlainText() == "1gi"
    assert box.hasFocus() is True
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "rl"


def test_prompt_editor_real_widget_cycles_selection_without_mutating_text(
    widgets: list[QWidget],
) -> None:
    """Arrow navigation should change selection and preview without editing text."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1gi": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1gi")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert box.toPlainText() == "1gi"
    assert box.hasFocus() is True
    assert panel.current_index() == 1
    assert _editor_autocomplete_preview_text(box) == "rls"

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert box.toPlainText() == "1gi"
    assert box.hasFocus() is True
    assert panel.current_index() == 0
    assert _editor_autocomplete_preview_text(box) == "rl"


def test_prompt_editor_real_widget_suppresses_autocomplete_after_caret_navigation(
    widgets: list[QWidget],
) -> None:
    """Caret-only navigation should not reopen key-owning autocomplete."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("blue hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"blue": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText("blue")
    cursor = box.textCursor()
    cursor.setPosition(3, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert gateway.calls == []
    assert getattr(box, "_autocomplete_panel") is None

    QTest.qWait(120)
    process_events(app)

    assert gateway.calls == []
    assert getattr(box, "_autocomplete_panel") is None


def test_prompt_editor_real_widget_repeated_arrow_navigation_does_not_query_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Repeated caret moves should stay out of the autocomplete query path."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("blue hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"blue": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText("blue")
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    for _ in range(4):
        QTest.keyClick(box, Qt.Key.Key_Right)
        process_events(app)

    assert gateway.calls == []

    QTest.qWait(120)
    process_events(app)

    assert gateway.calls == []


def test_prompt_editor_real_widget_vertical_boundaries_wrap_horizontal_arrows_escape(
    widgets: list[QWidget],
) -> None:
    """Vertical popup boundaries should wrap while horizontal arrows move the caret."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1gi": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText("1g\nnext")
    cursor = box.textCursor()
    cursor.setPosition(2, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClicks(box, "i")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)
    assert panel.current_index() == 1
    cursor_before_boundary = box.textCursor().position()

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert box.textCursor().position() == cursor_before_boundary

    box.setPlainText("above\n1g")
    cursor = box.textCursor()
    cursor.setPosition(len("above\n1g"), QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClicks(box, "i")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    cursor_before_boundary = box.textCursor().position()

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 1
    assert box.textCursor().position() == cursor_before_boundary

    box.setPlainText("1g\nnext")
    cursor = box.textCursor()
    cursor.setPosition(2, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClicks(box, "i")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    cursor_before_horizontal = box.textCursor().position()

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert panel.is_panel_visible() is False
    assert box.textCursor().position() > cursor_before_horizontal
    assert _editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_real_widget_preserves_acceptance_shortcuts(
    widgets: list[QWidget],
) -> None:
    """Tab and click should accept suggestions with existing semantics."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1g": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    widgets.extend([host, box])

    box.setFocus()
    process_events(app)
    QTest.keyClicks(box, "1g")
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Tab)
    process_events(app)
    assert box.toPlainText() == "1girl, "

    box.setPlainText("")
    box.setFocus()
    process_events(app)
    QTest.keyClicks(box, "1g")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    row = _panel_rows(panel)[1]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == "1girls"
    assert box.hasFocus() is True


def test_prompt_editor_real_widget_enter_inserts_newline_without_accepting_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Enter should keep its text-editing behavior while autocomplete is visible."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1g": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    assert _editor_autocomplete_preview_text(box) == "irl"

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)

    assert box.toPlainText() == "1g\n"
    assert _editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_paste_normalizes_emphasis_weight(
    widgets: list[QWidget],
) -> None:
    """Pasted completed emphasis weights should use canonical two-decimal text."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    QApplication.clipboard().setText("(cat:1)")

    box.paste()
    process_events(app)

    assert box.toPlainText() == "(cat:1.00)"
    assert box.textCursor().selectionStart() == len("(cat:1.00)")


def test_prompt_editor_paste_normalizes_lora_first_weight(
    widgets: list[QWidget],
) -> None:
    """Pasted completed LoRA first weights should use canonical two-decimal text."""

    app = ensure_qapp()
    box = create_lora_prompt_editor(loras=())
    widgets.append(box)
    box.show()
    box.setFocus()
    QApplication.clipboard().setText("<lora:Ranni_illusXLNoobAI_Incrs_v1:1>")

    box.paste()
    process_events(app)

    assert box.toPlainText() == "<lora:Ranni_illusXLNoobAI_Incrs_v1:1.00>"


def test_prompt_editor_paste_normalizes_lora_second_weight(
    widgets: list[QWidget],
) -> None:
    """Pasted completed LoRA second weights should normalize with first weights."""

    app = ensure_qapp()
    box = create_lora_prompt_editor(loras=())
    widgets.append(box)
    box.show()
    box.setFocus()
    QApplication.clipboard().setText("<lora:Name:0.9:1>")

    box.paste()
    process_events(app)

    assert box.toPlainText() == "<lora:Name:0.90:1.00>"


def test_prompt_editor_paste_keeps_cursor_after_normalized_insert(
    widgets: list[QWidget],
) -> None:
    """Cursor placement after paste should account for expanded weight text."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    widgets.append(box)
    box.show()
    box.setPlainText("alpha, ")
    move_cursor_to_end(box)
    box.setFocus()
    QApplication.clipboard().setText("(cat:1)")

    box.paste()
    process_events(app)

    assert box.toPlainText() == "alpha, (cat:1.00)"
    assert box.textCursor().selectionStart() == len("alpha, (cat:1.00)")


def test_prompt_editor_paste_supported_danbooru_url_imports_tags(
    widgets: list[QWidget],
) -> None:
    """Supported Danbooru URLs should be replaced with imported tag text."""

    app = ensure_qapp()
    service = _StaticDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/12345",
            kind=DanbooruUrlKind.POST,
            lookup_value="12345",
        ),
        result=DanbooruPromptImportResult(
            imported_prompt=DanbooruImportedPrompt(
                display_text="1girl, long hair, smile",
                source_post_id=12345,
                included_tags=("1girl", "long_hair", "smile"),
                excluded_tags=("commentary",),
            )
        ),
    )
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    _configure_danbooru_url_import(
        box,
        service,
        dispatcher=_ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://danbooru.donmai.us/posts/12345")

    box.paste()
    process_events(app)

    assert box.toPlainText() == "1girl, long hair, smile"
    assert service.classify_calls == ["https://danbooru.donmai.us/posts/12345"]
    assert service.import_calls == ["https://danbooru.donmai.us/posts/12345"]


def test_prompt_editor_danbooru_url_import_undo_skips_intermediate_url(
    widgets: list[QWidget],
) -> None:
    """Undo after Danbooru expansion should jump back before the paste entirely."""

    app = ensure_qapp()
    service = _StaticDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/12345",
            kind=DanbooruUrlKind.POST,
            lookup_value="12345",
        ),
        result=DanbooruPromptImportResult(
            imported_prompt=DanbooruImportedPrompt(
                display_text="1girl, long hair, smile",
                source_post_id=12345,
                included_tags=("1girl", "long_hair", "smile"),
                excluded_tags=("commentary",),
            )
        ),
    )
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    box.setPlainText("alpha, ")
    move_cursor_to_end(box)
    _configure_danbooru_url_import(
        box,
        service,
        dispatcher=_ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://danbooru.donmai.us/posts/12345")

    box.paste()
    process_events(app)
    assert box.toPlainText() == "alpha, 1girl, long hair, smile"

    box.undo()
    process_events(app)

    assert box.toPlainText() == "alpha, "


def test_prompt_editor_paste_unsupported_danbooru_url_falls_back_to_literal_paste(
    widgets: list[QWidget],
) -> None:
    """Unsupported URLs should use the existing literal paste behavior."""

    app = ensure_qapp()
    service = _StaticDanbooruUrlImportService(
        classification=None,
        result=DanbooruPromptImportResult(imported_prompt=None),
    )
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    _configure_danbooru_url_import(
        box,
        service,
        dispatcher=_ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://example.com/posts/12345")

    box.paste()
    process_events(app)

    assert box.toPlainText() == "https://example.com/posts/12345"
    assert service.classify_calls == ["https://example.com/posts/12345"]
    assert service.import_calls == []


def test_prompt_editor_paste_failed_danbooru_lookup_keeps_literal_url(
    widgets: list[QWidget],
) -> None:
    """Failed Danbooru lookups should leave the pasted URL in place."""

    app = ensure_qapp()
    service = _StaticDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/777",
            kind=DanbooruUrlKind.POST,
            lookup_value="777",
        ),
        result=DanbooruPromptImportResult(
            imported_prompt=None,
            failure_reason=DanbooruFailureReason.NOT_FOUND,
        ),
    )
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    _configure_danbooru_url_import(
        box,
        service,
        dispatcher=_ImmediateDanbooruImportDispatcher(),
    )
    QApplication.clipboard().setText("https://danbooru.donmai.us/posts/777")

    box.paste()
    process_events(app)

    assert box.toPlainText() == "https://danbooru.donmai.us/posts/777"
    assert service.import_calls == ["https://danbooru.donmai.us/posts/777"]


def test_prompt_editor_paste_danbooru_exception_logs_prompt_safe_context(
    widgets: list[QWidget],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Danbooru import exceptions should not serialize pasted URL content."""

    app = ensure_qapp()
    service = _FailingDanbooruUrlImportService(
        classification=DanbooruUrlClassification(
            url="https://danbooru.donmai.us/posts/888",
            kind=DanbooruUrlKind.POST,
            lookup_value="888",
        ),
    )
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({}),
        danbooru_url_import_service=service,
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    _configure_danbooru_url_import(
        box,
        service,
        dispatcher=_ImmediateDanbooruImportDispatcher(),
    )
    caplog.set_level(
        logging.WARNING,
        logger="presentation.editor.prompt_editor.danbooru_paste_import",
    )
    pasted_url = "https://danbooru.donmai.us/posts/888"
    QApplication.clipboard().setText(pasted_url)

    box.paste()
    process_events(app)

    assert box.toPlainText() == pasted_url
    assert service.import_calls == [pasted_url]
    assert "Prompt paste Danbooru import failed unexpectedly." in caplog.text
    assert "error_type=RuntimeError" in caplog.text
    assert f"source_length={len(pasted_url)}" in caplog.text
    assert pasted_url not in caplog.text


def test_prompt_editor_typing_does_not_normalize_incomplete_weight(
    widgets: list[QWidget],
) -> None:
    """Ordinary typing should not fight incomplete weight entry buffers."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    cursor = box.textCursor()

    cursor.insertText("(cat:0.")
    process_events(app)

    assert box.toPlainText() == "(cat:0."


def test_prompt_editor_cursor_insertion_preserves_completed_inline_emphasis_weight(
    widgets: list[QWidget],
) -> None:
    """Cursor insertion should preserve valid authored inline emphasis weights."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    widgets.append(box)
    box.show()
    box.setFocus()
    cursor = box.textCursor()

    cursor.insertText("black underbust (ribbon:1.2)")
    process_events(app)

    assert box.toPlainText() == "black underbust (ribbon:1.2)"
    assert box.textCursor().selectionStart() == len("black underbust (ribbon:1.2)")


def test_prompt_editor_key_typing_preserves_inline_weight_shape(
    widgets: list[QWidget],
) -> None:
    """Key-by-key typing should preserve valid inline emphasis while typing."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    widgets.append(box)
    box.show()
    box.setFocus()

    QTest.keyClicks(box, "black underbust (ribbon:1.2)")
    process_events(app)

    assert box.toPlainText() == "black underbust (ribbon:1.2)"
    assert box.textCursor().selectionStart() == len("black underbust (ribbon:1.2)")


def test_prompt_editor_key_typing_preserves_parenthetical_prompt_words(
    widgets: list[QWidget],
) -> None:
    """Key-by-key typing should preserve authored parenthetical prompt words."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    widgets.append(box)
    box.show()
    box.setFocus()

    QTest.keyClicks(box, "vertin (reverse:1999)")
    process_events(app)

    assert box.toPlainText() == "vertin (reverse:1999)"


def test_prompt_editor_set_plain_text_normalizes_weights(
    widgets: list[QWidget],
) -> None:
    """Programmatic text loading should enter the same canonical source form."""

    app = ensure_qapp()
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    widgets.append(box)
    box.show()

    box.setPlainText("black underbust (ribbon:1.2)")
    process_events(app)

    assert box.toPlainText() == "black underbust (ribbon:1.20)"


def test_prompt_editor_lora_autocomplete_opens_wall_without_search_box(
    widgets: list[QWidget],
) -> None:
    """Typing a LoRA token prefix should open the wall-based autocomplete surface."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    box = create_lora_prompt_editor(loras=(_sample_lora(),))
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "<lora:Civ")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    wall = panel.lora_wall()
    assert panel.is_panel_visible() is True
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    assert wall.items()[0].title == "CivitAI Midna"
    assert panel.findChildren(QLineEdit) == []
    assert _editor_autocomplete_preview_text(box) == "itAI Midna"


def test_prompt_editor_lora_autocomplete_one_row_up_down_stays_open(
    widgets: list[QWidget],
) -> None:
    """Vertical no-op navigation should not dismiss a one-row LoRA wall."""

    app = ensure_qapp()
    loras = tuple(
        _sample_lora(
            display_name=f"LoRA {index}",
            basename=f"lora_{index}",
            prompt_name=rf"folder\lora_{index}",
        )
        for index in range(3)
    )
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    box = create_lora_prompt_editor(loras=loras)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "<lora:LoRA")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    cursor_before_navigation = box.textCursor().position()

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0

    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert box.textCursor().position() == cursor_before_navigation

    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 0
    assert box.textCursor().position() == cursor_before_navigation

    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert panel.is_panel_visible() is True
    assert panel.current_index() == 1
    assert box.textCursor().position() == cursor_before_navigation


def test_prompt_editor_lora_autocomplete_prefix_does_not_scroll_up(
    widgets: list[QWidget],
) -> None:
    """Typing a bottom-of-prompt LoRA prefix should preserve the viewport."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(430, 760)
    layout = QVBoxLayout(host)
    box = create_lora_prompt_editor(loras=(_sample_lora(),))
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText(("one two three four five six seven eight nine ten " * 60).strip())
    process_events(app)
    move_cursor_to_end(box)
    process_events(app)
    scroll_bar = box.verticalScrollBar()
    scroll_bar.setValue(scroll_bar.maximum())
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app)
    previous_value = scroll_bar.value()
    for text in ("<", "l", "o", "r", "a", ":"):
        QTest.keyClicks(box, text)
        process_events(app)
        assert scroll_bar.value() >= previous_value
        previous_value = scroll_bar.value()
    assert box.toPlainText().endswith("\n<lora:")


def test_prompt_editor_enter_at_bottom_keeps_prompt_state_scroll_synced(
    widgets: list[QWidget],
) -> None:
    """Enter at the prompt bottom should not require a second scroll correction."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(430, 760)
    layout = QVBoxLayout(host)
    box = create_lora_prompt_editor(loras=(_sample_lora(),))
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText(
        "\n".join(
            (
                "wide angle, foreground detail, layered composition, long line start",
                "group portrait",
                " 2 figures, conversation, layered background, reflective lighting, "
                "window shadows, table props, repeated descriptive words,",
                "landscape",
                " mountains, river, {seasonal_detail}1, distant village, morning fog, "
                "foreground leaves, repeated descriptive words,",
                "interior",
                " library shelves, window light, {seasonal_detail}1, desk, chair, "
                "maps, notebooks, repeated descriptive words,",
                "street",
                " market stalls, umbrellas, wet pavement, distant signs, layered crowd, "
                "overlapping shapes, repeated descriptive words,",
                "final scene",
                " calm ending line, seated figure, hands folded, warm light, "
                "background texture, repeated descriptive words, final phrase.",
            )
        )
    )
    process_events(app)
    move_cursor_to_end(box)
    process_events(app)
    scroll_bar = box.verticalScrollBar()
    scroll_bar.setValue(scroll_bar.maximum())
    process_events(app)

    QTest.keyClick(box, Qt.Key.Key_Return)
    process_events(app, cycles=50)

    surface = surface_for(box)
    assert cast(Any, surface)._caret_visibility_prompt_state_revision is None
    assert scroll_bar.maximum() - scroll_bar.value() <= box.lineHeight()


def test_prompt_editor_lora_autocomplete_accepts_scheduler_safe_prompt_name(
    widgets: list[QWidget],
) -> None:
    """LoRA autocomplete should insert the raw prompt name, not the display label."""

    app = ensure_qapp()
    lora = _sample_lora()
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    box = create_lora_prompt_editor(loras=(lora,))
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "<lora:Civ")
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Tab)
    process_events(app)

    assert box.toPlainText() == r"<lora:illustrious\characters\raw_midna:1.00>"
    assert box.hasFocus() is True


def test_prompt_editor_lora_autocomplete_click_accepts_selected_lora(
    widgets: list[QWidget],
) -> None:
    """Clicking the LoRA wall should accept through the same coordinator path."""

    app = ensure_qapp()
    lora = _sample_lora()
    host = QWidget()
    host.resize(720, 520)
    layout = QVBoxLayout(host)
    box = create_lora_prompt_editor(loras=(lora,))
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "<lora:Civ")
    process_events(app)
    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    wall = panel.lora_wall()
    assert wall is not None
    wall = cast(PromptLoraWallView, wall)
    assert wall.activate_current() is True
    process_events(app)

    assert box.toPlainText() == r"<lora:illustrious\characters\raw_midna:1.00>"


def test_prompt_editor_real_widget_dismisses_preview_when_context_no_longer_matches(
    widgets: list[QWidget],
) -> None:
    """Escape, backspacing, and moving the caret away should clear autocomplete."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1g": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    QTest.keyClick(box, Qt.Key.Key_Escape)
    process_events(app)

    assert panel.is_panel_visible() is False
    assert _editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_real_widget_uses_comma_delimited_space_tag_matching(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should treat spaces as tag content and commas as delimiters."""

    app = ensure_qapp()
    suggestions = (
        PromptAutocompleteSuggestion("long hair", 500),
        PromptAutocompleteSuggestion("long hairs", 200),
    )
    gateway = _StaticPromptAutocompleteGateway({"long ha": suggestions})

    host = QWidget()
    host.resize(480, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1girl, long ha")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    assert gateway.calls[-1] == ("long ha", 10)
    assert box.toPlainText() == "1girl, long ha"
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "ir"

    row = _panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == "1girl, long hair"


def test_prompt_editor_real_widget_uses_suffix_fallback_without_leading_comma(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should complete the local token when typing inside no-comma prose."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"ha": suggestions})

    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    box.setPlainText("1girl blue  solo")
    cursor = box.textCursor()
    cursor.setPosition(len("1girl blue "))
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "ha")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    assert ("1girl blue ha", 10) in gateway.calls
    assert gateway.calls[-1] == ("ha", 10)
    assert box.toPlainText() == "1girl blue ha solo"
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "ir"

    row = _panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == "1girl blue hair solo"


def test_prompt_editor_real_widget_consumes_matching_right_text_on_accept(
    widgets: list[QWidget],
) -> None:
    """Mid-tag autocomplete should preview and replace without duplicating right text."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"long h": suggestions})

    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    box.setPlainText("long ir")
    cursor = box.textCursor()
    cursor.setPosition(len("long "))
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "h")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    assert gateway.calls[-1] == ("long h", 10)
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "a"

    row = _panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == "long hair"


def test_prompt_editor_real_widget_keeps_unrelated_right_text_on_accept(
    widgets: list[QWidget],
) -> None:
    """Mid-tag autocomplete should leave unrelated text after the caret untouched."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"long h": suggestions})

    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    box.setPlainText("long x")
    cursor = box.textCursor()
    cursor.setPosition(len("long "))
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "h")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    assert gateway.calls[-1] == ("long h", 10)
    assert _editor_autocomplete_preview_text(box) == "air"

    row = _panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == "long hairx"


def test_prompt_editor_real_widget_accepts_underscore_input_as_spaced_completion(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should let underscore input complete to a spaced tag."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"long_ha": suggestions})

    host = QWidget()
    host.resize(480, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1girl, long_ha")
    process_events(app)

    assert gateway.calls[-1] == ("long_ha", 10)
    assert _editor_autocomplete_preview_text(box) == "ir"

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    row = _panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == "1girl, long hair"


def test_prompt_editor_real_widget_hides_noop_autocomplete_suggestion_for_fully_typed_tag(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should hide when the only match is the tag already present in the editor."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("looking_at_viewer", 500),)
    gateway = _StaticPromptAutocompleteGateway({"looking at viewer": suggestions})

    host = QWidget()
    host.resize(520, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "looking at viewer")
    process_events(app)

    panel = cast(PromptAutocompletePanel | None, getattr(box, "_autocomplete_panel"))

    assert gateway.calls[-1] == ("looking at viewer", 10)
    assert panel is None or panel.is_panel_visible() is False
    assert _editor_autocomplete_preview_text(box) == ""


def test_prompt_editor_real_widget_ignores_quoted_and_bracketed_commas_for_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should keep the active segment after quoted or bracketed commas."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"long ha": suggestions})

    host = QWidget()
    host.resize(560, 240)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, '"cat, dog", [bird, fish], long ha')
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    assert gateway.calls[-1] == ("long ha", 10)
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "ir"

    row = _panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == '"cat, dog", [bird, fish], long hair'


def test_prompt_editor_real_widget_ignores_braced_commas_for_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Autocomplete should keep the active segment after commas inside brace groups."""

    app = ensure_qapp()
    suggestions = (PromptAutocompleteSuggestion("long hair", 500),)
    gateway = _StaticPromptAutocompleteGateway({"long ha": suggestions})

    host = QWidget()
    host.resize(560, 240)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "{animal, texture}, long ha")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))

    assert gateway.calls[-1] == ("long ha", 10)
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "ir"

    row = _panel_rows(panel)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=row.rect().center())
    process_events(app)

    assert box.toPlainText() == "{animal, texture}, long hair"


def test_prompt_editor_real_widget_enters_reorder_mode_once_and_closes_without_mutation_on_noop_alt_release(
    widgets: list[QWidget],
) -> None:
    """Holding Alt should create one reorder overlay and close cleanly when nothing moved."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,beta,")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    first_overlay = getattr(box, "_segment_overlay")
    assert first_overlay is not None
    assert _editor_reorder_preview_document(box) is None
    assert first_overlay.isVisible() is True
    assert first_overlay.parentWidget() is box.viewport()
    assert first_overlay.findChild(QWidget, "segmentReorderScrollArea") is None
    assert first_overlay.findChild(QWidget, "segmentReorderFrame") is None

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    assert getattr(box, "_segment_overlay") is first_overlay

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "alpha,beta,"
    assert _editor_reorder_preview_document(box) is None
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_retains_focus_during_alt_reorder_drag(
    widgets: list[QWidget],
) -> None:
    """Alt reorder gestures should keep the host prompt editor focused throughout."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,beta,")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    assert box.hasFocus() is True

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None
    assert box.hasFocus() is True

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    drag_target = first_chip.mapToGlobal(
        QPoint(4, max(4, first_chip.rect().center().y()))
    )
    second_chip_target = second_chip.mapFromGlobal(drag_target)

    QTest.mousePress(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip.rect().center(),
    )
    process_events(app)

    assert box.hasFocus() is True

    QTest.mouseMove(second_chip, second_chip_target, 10)
    process_events(app)

    assert box.hasFocus() is True

    QTest.mouseRelease(
        second_chip,
        Qt.MouseButton.LeftButton,
        pos=second_chip_target,
        delay=10,
    )
    process_events(app)

    assert box.hasFocus() is True

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.hasFocus() is True


def test_prompt_editor_real_widget_commits_alt_left_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-left should commit one leftward chip move for the caret-owned chip."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Left)
    process_events(app)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"
    reorder_session = cast(
        Any, box
    )._interaction_controller._reorder.segment_reorder_session
    latest_snapshot = cast(
        Any, box
    )._interaction_controller._reorder.latest_commit_snapshot
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (1, 0, 2)
    assert latest_snapshot.has_reordered is True
    assert reorder_session.current_ordered_indices == (1, 0, 2)
    assert reorder_session.has_reordered is True
    assert box.hasFocus() is True

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "beta, alpha, gamma"
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 1
    assert getattr(box, "_segment_overlay") is None
    assert box.hasFocus() is True


def test_prompt_editor_real_widget_commits_alt_right_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-right should commit one rightward chip move for the caret-owned chip."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Right)
    process_events(app)

    assert _editor_reorder_preview_text(box) == "alpha, gamma, beta"
    latest_snapshot = cast(
        Any, box
    )._interaction_controller._reorder.latest_commit_snapshot
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (0, 2, 1)
    assert latest_snapshot.has_reordered is True

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "alpha, gamma, beta"
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_commits_alt_up_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-up should move the active chip into the previous visible reorder lane."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 240)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,\n\n\ngamma, beta")
    cursor = box.textCursor()
    cursor.setPosition(10, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert _editor_reorder_preview_text(box) == "alpha,\n\ngamma,\nbeta"
    latest_snapshot = cast(
        Any, box
    )._interaction_controller._reorder.latest_commit_snapshot
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (0, 1, 2)
    assert latest_snapshot.has_reordered is True

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "alpha,\n\ngamma,\nbeta"
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_clamps_alt_up_to_first_slot_on_top_lane(
    widgets: list[QWidget],
) -> None:
    """Alt-up on the top reorder lane should move the active chip to the row start."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "beta, alpha, gamma"
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_commits_alt_down_keyboard_reorder(
    widgets: list[QWidget],
) -> None:
    """Alt-down should move the active chip into the next visible reorder lane."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 240)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,\n\n\ngamma, beta")
    cursor = box.textCursor()
    cursor.setPosition(10, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Up)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert _editor_reorder_preview_text(box) == "alpha,\n\n\nbeta, gamma"
    latest_snapshot = cast(
        Any, box
    )._interaction_controller._reorder.latest_commit_snapshot
    assert latest_snapshot is not None
    assert latest_snapshot.ordered_chip_indices == (0, 2, 1)
    assert latest_snapshot.has_reordered is True

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "alpha,\n\n\nbeta, gamma"
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_clamps_alt_down_to_last_slot_on_bottom_lane(
    widgets: list[QWidget],
) -> None:
    """Alt-down on the bottom reorder lane should move the active chip to the row end."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(8, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)
    QTest.keyClick(box, Qt.Key.Key_Down)
    process_events(app)

    assert _editor_reorder_preview_text(box) == "alpha, gamma, beta"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "alpha, gamma, beta"
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_commits_actual_reorder_on_alt_release(
    widgets: list[QWidget],
) -> None:
    """Dragging chips in reorder mode should commit the new order through the editor path."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,beta,")
    cursor = box.textCursor()
    cursor.setPosition(7, QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None
    assert _editor_reorder_preview_document(box) is None

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    assert first_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert second_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.mapToGlobal(
            QPoint(4, max(4, first_chip.rect().center().y()))
        ),
    )
    process_events(app)

    assert second_chip.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert _editor_reorder_preview_document(box) is not None
    assert _editor_reorder_preview_text(box) == "beta, alpha, "
    ordered_segment_indices = cast(Any, overlay).ordered_chip_indices()
    preview_segment_indices = _overlay_preview_segment_indices(overlay)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert ordered_segment_indices == [1, 0]
    assert preview_segment_indices == [1, 0]
    assert box.toPlainText() == "beta, alpha,"
    assert box.textCursor().selectionStart() == 1
    assert box.textCursor().selectionEnd() == 1
    assert _editor_reorder_preview_document(box) is None
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_accumulates_multiple_reorder_drags_before_alt_release(
    widgets: list[QWidget],
) -> None:
    """Multiple drags in one Alt session should build on the current session order."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha, beta, gamma")
    cursor = box.textCursor()
    cursor.setPosition(0, QTextCursor.MoveMode.MoveAnchor)
    cursor.setPosition(len(box.toPlainText()), QTextCursor.MoveMode.KeepAnchor)
    box.setTextCursor(cursor)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    alpha_chip = _overlay_chip_by_segment_index(overlay, 0)
    beta_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        beta_chip,
        global_target=alpha_chip.mapToGlobal(
            QPoint(4, max(4, alpha_chip.rect().center().y()))
        ),
    )
    process_events(app)

    assert _editor_reorder_preview_text(box) == "beta, alpha, gamma"

    beta_chip = _overlay_chip_by_segment_index(overlay, 1)
    gamma_chip = _overlay_chip_by_segment_index(overlay, 2)
    _drag_reorder_chip_to_global(
        gamma_chip,
        global_target=beta_chip.mapToGlobal(
            QPoint(4, max(4, beta_chip.rect().center().y()))
        ),
    )
    process_events(app)

    assert _editor_reorder_preview_text(box) == "gamma, beta, alpha"

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "gamma, beta, alpha"
    assert _editor_reorder_preview_document(box) is None
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_keeps_emphasis_rendering_during_reorder_drag(
    widgets: list[QWidget],
) -> None:
    """Dragging an emphasized segment should keep rich emphasis formatting in the preview."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("(1girl:0.05), solo")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    emphasized_chip = _overlay_chip_by_segment_index(overlay, 0)
    solo_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        emphasized_chip,
        global_target=overlay.mapToGlobal(
            QPoint(overlay.width() - 8, solo_chip.rect().center().y())
        ),
    )
    process_events(app)

    preview_text = _editor_reorder_preview_text(box)
    preview_projection_document = _editor_reorder_preview_document(box)
    drag_proxy_projection_document = cast(
        Any, _overlay_drag_proxy(overlay)
    ).projection_document()

    assert preview_text == "solo, (1girl:0.05)"
    assert preview_projection_document is not None
    assert drag_proxy_projection_document is not None
    assert preview_projection_document.projection_text.count("\ufffc") == 2
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in preview_projection_document.tokens
    )
    assert any(
        token.kind is PromptProjectionTokenKind.EMPHASIS
        and token.display_text == "1girl"
        and token.value_text == "0.05"
        for token in drag_proxy_projection_document.tokens
    )

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)


def test_prompt_editor_real_widget_reorder_commit_round_trips_through_editor_undo_stack(
    widgets: list[QWidget],
) -> None:
    """Committed segment reorders should behave like one undoable text edit."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,beta,")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.mapToGlobal(
            QPoint(4, max(4, first_chip.rect().center().y()))
        ),
    )
    process_events(app)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "beta, alpha,"

    box.undo()
    process_events(app)

    assert box.toPlainText() == "alpha,beta,"

    box.redo()
    process_events(app)

    assert box.toPlainText() == "beta, alpha,"


def test_prompt_editor_real_widget_reorder_commit_preserves_line_break_slot_formatting(
    widgets: list[QWidget],
) -> None:
    """Dragging through reorder mode should preserve newline separators on commit."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(420, 240)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText("alpha,\nbeta, gamma")
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    first_chip = _overlay_chip_by_segment_index(overlay, 0)
    second_chip = _overlay_chip_by_segment_index(overlay, 1)
    _drag_reorder_chip_to_global(
        second_chip,
        global_target=first_chip.mapToGlobal(
            QPoint(4, max(4, first_chip.rect().center().y()))
        ),
    )
    process_events(app)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert box.toPlainText() == "beta, alpha,\ngamma"
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_can_drop_tag_onto_specific_blank_line(
    widgets: list[QWidget],
) -> None:
    """Dragging into a multiline gap should commit the segment onto the chosen blank line."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 320)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText(
        "1girl, detailed eyes, solo, portrait, looking at viewer,\n\n\n\n\n"
        "soft lighting, pastel colors, clean lineart, highres"
    )
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = cast(QWidget, getattr(box, "_segment_overlay"))
    assert overlay is not None

    soft_lighting_chip = _overlay_chip_by_segment_index(overlay, 5)
    solo_chip = _overlay_chip_by_segment_index(overlay, 2)

    QTest.mousePress(
        solo_chip,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.rect().center(),
    )
    QTest.mouseMove(
        solo_chip,
        solo_chip.mapFromGlobal(
            soft_lighting_chip.mapToGlobal(
                QPoint(4, max(4, soft_lighting_chip.rect().center().y()))
            )
        ),
        10,
    )
    process_events(app)

    blank_line_visuals = _overlay_blank_line_target_visuals(overlay)
    assert len(blank_line_visuals) == 4

    third_blank_line = cast(Any, blank_line_visuals[2])
    third_blank_line_global = overlay.mapToGlobal(
        third_blank_line.hit_rect.center().toPoint()
    )
    QTest.mouseMove(
        solo_chip,
        solo_chip.mapFromGlobal(third_blank_line_global),
        10,
    )
    process_events(app)

    QTest.mouseRelease(
        solo_chip,
        Qt.MouseButton.LeftButton,
        pos=solo_chip.mapFromGlobal(third_blank_line_global),
        delay=10,
    )
    process_events(app)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert (
        box.toPlainText()
        == "1girl, detailed eyes, portrait, looking at viewer,\n\n\nsolo,\n\n"
        "soft lighting, pastel colors, clean lineart, highres"
    )
    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_reorder_preview_still_wraps_in_narrow_card_width(
    widgets: list[QWidget],
) -> None:
    """Reorder preview should stay usable in narrow card widths without a second panel."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(260, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    box.setPlainText(
        "alpha long segment, beta long segment, gamma long segment, delta long segment"
    )
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    overlay = getattr(box, "_segment_overlay")
    assert overlay is not None

    chips = _overlay_chip_widgets(overlay)

    assert overlay.parentWidget() is box.viewport()
    assert overlay.findChild(QWidget, "segmentReorderScrollArea") is None
    assert overlay.findChild(QWidget, "segmentReorderFrame") is None
    assert len({chip.geometry().top() for chip in chips}) > 1
    assert all(chip.cursor().shape() == Qt.CursorShape.OpenHandCursor for chip in chips)

    QTest.keyRelease(box, Qt.Key.Key_Alt)
    process_events(app)

    assert getattr(box, "_segment_overlay") is None


def test_prompt_editor_real_widget_repositions_panel_when_editor_moves(
    widgets: list[QWidget],
) -> None:
    """Moving the editor inside its host should move the autocomplete panel with it."""

    app = ensure_qapp()
    gateway = _StaticPromptAutocompleteGateway({"1g": _sample_suggestions()})

    host = QWidget()
    host.resize(640, 260)
    box = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    box.setGeometry(40, 40, 260, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    initial_geometry = panel.geometry()

    box.move(180, 92)
    process_events(app)

    moved_geometry = panel.geometry()

    assert moved_geometry != initial_geometry
    assert moved_geometry.left() > initial_geometry.left()
    assert moved_geometry.top() > initial_geometry.top()


def test_prompt_editor_real_widget_repositions_panel_when_editor_resizes(
    widgets: list[QWidget],
) -> None:
    """Resizing the editor should recompute panel placement from the wrapped caret."""

    app = ensure_qapp()
    gateway = _StaticPromptAutocompleteGateway({"1g": _sample_suggestions()})

    host = QWidget()
    host.resize(640, 260)
    box = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    box.setGeometry(40, 40, 360, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "alpha alpha alpha alpha alpha, 1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    initial_geometry = panel.geometry()

    box.resize(140, box.height())
    process_events(app)

    resized_geometry = panel.geometry()

    assert resized_geometry != initial_geometry
    assert resized_geometry.top() > initial_geometry.top()


def test_prompt_editor_ignores_programmatic_visible_scrollbar_resets(
    widgets: list[QWidget],
) -> None:
    """QFluent scrollbar mirror resets should not overwrite projection scroll."""

    app = ensure_qapp()
    host = QWidget()
    host.resize(640, 260)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(
        prompt_autocomplete_gateway=_StaticPromptAutocompleteGateway({})
    )
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    box.setPlainText("\n".join(f"line {index}" for index in range(80)))
    process_events(app)

    surface_scroll_bar = box.verticalScrollBar()
    surface_scroll_bar.setValue(surface_scroll_bar.maximum())
    process_events(app)
    bottom_scroll_value = surface_scroll_bar.value()
    scroll_delegate = cast(Any, getattr(box, "scrollDelegate"))
    visible_scroll_bar = scroll_delegate.vScrollBar

    visible_scroll_bar.setValue(0, False)
    process_events(app)

    assert bottom_scroll_value > 0
    assert surface_scroll_bar.value() == bottom_scroll_value


def test_prompt_editor_real_widget_repositions_panel_when_vertical_scrollbar_moves(
    widgets: list[QWidget],
) -> None:
    """Scrolling the editor viewport should reposition the active autocomplete panel."""

    app = ensure_qapp()
    gateway = _StaticPromptAutocompleteGateway({"1g": _sample_suggestions()})

    host = QWidget()
    host.resize(640, 260)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText(("alpha,\n" * 12) + "prefix, ")
    move_cursor_to_end(box)
    box.setFocus()
    process_events(app)
    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    scrollbar = box.verticalScrollBar()
    assert scrollbar.maximum() > 0
    initial_geometry = panel.geometry()

    scrollbar.setValue(0)
    process_events(app)

    scrolled_geometry = panel.geometry()

    assert scrolled_geometry != initial_geometry
    assert scrolled_geometry.top() != initial_geometry.top()


def test_prompt_editor_real_widget_paints_preview_without_changing_projection_layout(
    widgets: list[QWidget],
) -> None:
    """Mid-prompt autocomplete preview should stay outside committed projection."""

    app = ensure_qapp()
    gateway = _StaticPromptAutocompleteGateway({"1g": _sample_suggestions()})

    host = QWidget()
    host.resize(420, 220)
    box = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    box.setGeometry(24, 24, 180, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    box.setPlainText("alpha, , omega")
    cursor = box.textCursor()
    cursor.setPosition(len("alpha, "), QTextCursor.MoveMode.MoveAnchor)
    box.setTextCursor(cursor)
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    surface = surface_for(box)
    assert _editor_autocomplete_preview_text(box) == "irl"
    assert surface.projection_document().source_text == "alpha, 1g, omega"
    assert surface.projection_document().projection_text == "alpha, 1g, omega"
    assert surface.active_projection_document().projection_text == (
        "alpha, 1girl, omega"
    )
    omega_fragment = next(
        fragment
        for fragment in surface._layout._snapshot.text_fragments  # noqa: SLF001
        if fragment.text == "omega"
    )

    assert omega_fragment.run_id.startswith("text:")


def test_prompt_editor_real_widget_clears_stale_preview_before_retargeting(
    widgets: list[QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compatible typing should explicitly clear stale ghost geometry before retargeting."""

    app = ensure_qapp()
    gateway = _StaticPromptAutocompleteGateway(
        {
            "1g": _sample_suggestions(),
            "1gi": _sample_suggestions(),
        }
    )

    host = QWidget()
    host.resize(420, 220)
    box = create_prompt_editor(parent=host, prompt_autocomplete_gateway=gateway)
    box.setGeometry(24, 24, 180, box.minimumEditorHeight())
    host.show()
    host.activateWindow()
    box.show()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    surface = surface_for(box)
    assert _editor_autocomplete_preview_text(box) == "irl"

    preview_updates: list[object | None] = []
    session = surface._session  # noqa: SLF001
    session_type = type(session)
    original_set_preview = PromptProjectionSession.set_autocomplete_preview

    def record_preview(
        target: PromptProjectionSession,
        preview: PromptAutocompletePreviewState | None,
    ) -> None:
        """Record projection preview state transitions during compatible typing."""

        if target is session:
            preview_updates.append(preview)
        original_set_preview(target, preview)

    monkeypatch.setattr(
        session_type,
        "set_autocomplete_preview",
        record_preview,
    )

    QTest.keyClick(box, Qt.Key.Key_I)
    process_events(app)

    assert box.toPlainText() == "1gi"
    assert _editor_autocomplete_preview_text(box) == "rl"
    assert preview_updates[0] is None
    assert isinstance(preview_updates[-1], PromptAutocompletePreviewState)


def test_prompt_editor_real_widget_entering_reorder_mode_dismisses_autocomplete(
    widgets: list[QWidget],
) -> None:
    """Entering segment reorder mode should clear the panel and ghost preview first."""

    app = ensure_qapp()
    gateway = _StaticPromptAutocompleteGateway({"1g": _sample_suggestions()})

    host = QWidget()
    host.resize(520, 240)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "alpha, beta, 1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "irl"

    QTest.keyPress(box, Qt.Key.Key_Alt)
    process_events(app)

    assert panel.is_panel_visible() is False
    assert _editor_autocomplete_preview_text(box) == ""
    reorder_overlay = getattr(box, "_segment_overlay")
    assert reorder_overlay is not None
    assert reorder_overlay.parentWidget() is box.viewport()


def test_prompt_editor_real_widget_hide_event_clears_autocomplete_state(
    widgets: list[QWidget],
) -> None:
    """Hiding the editor should clear both autocomplete surfaces immediately."""

    app = ensure_qapp()
    suggestions = _sample_suggestions()
    gateway = _StaticPromptAutocompleteGateway({"1g": suggestions})

    host = QWidget()
    host.resize(420, 220)
    layout = QVBoxLayout(host)
    box = create_prompt_editor(prompt_autocomplete_gateway=gateway)
    layout.addWidget(box)
    host.show()
    host.activateWindow()
    box.setFocus()
    widgets.extend([host, box])
    process_events(app)

    QTest.keyClicks(box, "1g")
    process_events(app)

    panel = cast(PromptAutocompletePanel, getattr(box, "_autocomplete_panel"))
    assert panel.is_panel_visible() is True
    assert _editor_autocomplete_preview_text(box) == "irl"

    box.hide()
    process_events(app)

    assert panel.is_panel_visible() is False
    assert _editor_autocomplete_preview_text(box) == ""

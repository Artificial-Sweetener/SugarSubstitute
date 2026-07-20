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

"""Render Danbooru wiki definitions inside a native QFluent modal."""

from __future__ import annotations

from sugarsubstitute_shared.localization import ApplicationMessage, ApplicationText
from sugarsubstitute_shared.presentation.localization import (
    app_text,
    render_application_text,
    set_localized_accessible_name,
    set_localized_tooltip,
)

from substitute.presentation.localization import (
    LocalizedBodyLabel,
    LocalizedCaptionLabel,
    LocalizedStrongBodyLabel,
    LocalizedTitleLabel,
)

from collections.abc import Callable
from dataclasses import dataclass
import html
import re
from time import monotonic
from typing import Generic, Protocol, TypeVar, cast
from urllib.parse import quote, unquote

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (  # type: ignore[import-untyped]
    CaptionLabel,
    FluentIcon as FIF,
    MessageBoxBase,
    ToolButton,
)
from sugarsubstitute_shared.presentation.fluent_tooltips import (
    FluentToolTipFilter,
    ToolTipPosition,
    ensure_fluent_tooltip_filter,
)
from qfluentwidgets.common.style_sheet import isDarkTheme  # type: ignore[import-untyped]
from shiboken6 import isValid

from sugarsubstitute_shared.presentation.localization import (
    set_localized_text,
)

from substitute.application.danbooru import (
    DanbooruContentFreshnessState,
    DanbooruFailureReason,
    DanbooruImagePreviewState,
    DanbooruWikiContentLookupResult,
    DanbooruWikiImagePreview,
    DanbooruWikiImageReference,
    DanbooruWikiImageReferenceBlock,
    DanbooruWikiSectionContent,
)
from substitute.application.execution import (
    CancellationToken,
    ExecutionContext,
    TaskHandle,
    TaskIdentity,
    TaskOutcome,
    TaskRequest,
    TaskScope,
    TaskSubmitter,
    TaskTimings,
)
from substitute.presentation.danbooru import (
    DanbooruWikiBlockParser,
    DanbooruWikiContentView,
)
from substitute.presentation.shell.chrome_style import connect_theme_refresh
from substitute.presentation.widgets.civitai_page_action import (
    UrlOpener,
    open_external_url,
)
from substitute.shared.logging.logger import get_logger, log_debug, log_warning

_LOGGER = get_logger("presentation.dialogs.danbooru_wiki_dialog")
_DIALOG_WIDTH_RATIO = 0.85
_DIALOG_HEIGHT_RATIO = 0.85
_DIALOG_MIN_WIDTH = 840
_DIALOG_MIN_HEIGHT = 560
_CONTENT_TOP_MARGIN = 24
_CONTENT_SIDE_MARGIN = 24
_CONTENT_BOTTOM_MARGIN = 18
_CONTENT_SPACING = 14
_WIKI_SCHEME_PREFIX = "danbooru-wiki:"
_FRAGMENT_SCHEME_PREFIX = "danbooru-fragment:"
_URL_ALIAS_PATTERN = re.compile(r"^(?:https?://|www\.)\S+$", re.IGNORECASE)
_PIXIV_ALIAS_PATTERN = re.compile(r"^pixiv\s+#(?P<artwork_id>\d+)$", re.IGNORECASE)
_PIXIV_URL_PATTERN = re.compile(
    r"^(?:https?://)?(?:www\.)?pixiv\.net/\S+$",
    re.IGNORECASE,
)
_FALLBACK_PARENT: QWidget | None = None
_DARK_DIALOG_TOP_FILL = "#2b2b2b"
_DARK_DIALOG_BODY_FILL = "#202020"
_LIGHT_DIALOG_TOP_FILL = "#fbfbfb"
_LIGHT_DIALOG_BODY_FILL = "#f4f4f4"
_HEADER_BUTTON_SIZE = 28
_DIALOG_FALLBACK_TITLE = app_text("Danbooru wiki")
_SURFACE_RADIUS = 18
_HEADER_HORIZONTAL_PADDING = 24
_HEADER_TOP_PADDING = 16
_HEADER_BOTTOM_PADDING = 12
_BODY_HORIZONTAL_PADDING = 24
_BODY_TOP_PADDING = 16
_BODY_BOTTOM_PADDING = 18
TResult = TypeVar("TResult")


class DanbooruWikiLookupDispatcher(Protocol):
    """Schedule Danbooru wiki lookups away from the GUI thread."""

    def submit(
        self,
        lookup: Callable[[], "_DialogLoadResult"],
        *,
        completed: Callable[["_DialogLoadResult"], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Run one Danbooru wiki lookup and deliver the result later."""


class DanbooruWikiLookupService(Protocol):
    """Describe the wiki-service surface consumed by the native dialog."""

    def lookup_selection(self, selection_text: str) -> DanbooruWikiContentLookupResult:
        """Return the wiki result for one selected prompt text."""

    def lookup_title(self, title: str) -> DanbooruWikiContentLookupResult:
        """Return the wiki result for one known Danbooru title."""

    def resolve_sections(
        self,
        sections: tuple[DanbooruWikiSectionContent, ...],
    ) -> tuple[DanbooruWikiSectionContent, ...]:
        """Resolve parsed inline content into metadata-backed chip nodes."""


class DanbooruImagePreviewResolver(Protocol):
    """Resolve cached Danbooru preview images for parsed wiki embed blocks."""

    def resolve_preview_for_reference(
        self,
        *,
        source_kind: str,
        source_id: int,
    ) -> DanbooruWikiImagePreview:
        """Return one preview image or placeholder for a Danbooru wiki embed."""


class DanbooruRecentPostsResolver(Protocol):
    """Return bounded recent visible post ids for one Danbooru wiki tag."""

    def list_recent_visible_post_ids(
        self,
        tag_name: str,
        *,
        desired_count: int = 5,
    ) -> tuple[int, ...]:
        """Return up to ``desired_count`` visible recent post ids for one tag."""


class QtDanbooruWikiLookupDispatcher(QObject):
    """Resolve Danbooru wiki lookups through execution and deliver them to Qt."""

    _finished = Signal(int, object, object)

    def __init__(
        self,
        parent: QObject,
        *,
        submitter: TaskSubmitter | None = None,
        close_submitter: Callable[[], None] | None = None,
    ) -> None:
        """Create a lookup dispatcher for one dialog lifetime."""

        super().__init__(parent)
        self._next_request_id = 0
        active_submitter = submitter or _SynchronousDialogSubmitter()
        self._scope = TaskScope(
            submitter=active_submitter,
            scope_id=f"danbooru_wiki_dialog_lookup_{id(self):x}",
        )
        self._close_submitter = close_submitter
        self._callbacks: dict[
            int,
            tuple[
                Callable[["_DialogLoadResult"], None],
                Callable[[BaseException], None],
            ],
        ] = {}
        self._finished.connect(
            self._deliver_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        parent.destroyed.connect(self._shutdown)

    def submit(
        self,
        lookup: Callable[[], "_DialogLoadResult"],
        *,
        completed: Callable[["_DialogLoadResult"], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Run one wiki lookup without blocking the dialog thread."""

        self._next_request_id += 1
        request_id = self._next_request_id
        self._callbacks[request_id] = (completed, failed)
        request: TaskRequest[_DialogLoadResult] = TaskRequest(
            identity=TaskIdentity(
                request_id=request_id,
                domain="danbooru_wiki_dialog_lookup",
            ),
            context=ExecutionContext(
                operation="danbooru_wiki_dialog_lookup",
                reason="dialog_navigation",
                lane="danbooru_refresh",
            ),
            work=lambda _cancellation: lookup(),
        )
        handle = self._scope.submit(request)
        handle.add_done_callback(
            lambda outcome: self._emit_finished(request_id, outcome),
            reason="danbooru_wiki_dialog_lookup_finished",
        )

    def _emit_finished(
        self,
        request_id: int,
        outcome: TaskOutcome["_DialogLoadResult"],
    ) -> None:
        """Emit one finished lookup through queued Qt signal delivery."""

        result = outcome.result
        error = outcome.error
        self._finished.emit(request_id, result, error)

    @Slot(int, object, object)
    def _deliver_finished(
        self,
        request_id: int,
        result: object,
        error: object,
    ) -> None:
        """Deliver one lookup result on the GUI thread."""

        callbacks = self._callbacks.pop(request_id, None)
        if callbacks is None:
            return
        completed, failed = callbacks
        if isinstance(error, BaseException):
            failed(error)
            return
        completed(cast(_DialogLoadResult, result))

    @Slot()
    def _shutdown(self) -> None:
        """Cancel pending wiki lookups when the dialog is destroyed."""

        self._callbacks.clear()
        self._scope.close(reason="danbooru_wiki_dialog_lookup_shutdown")
        if self._close_submitter is not None:
            self._close_submitter()
            self._close_submitter = None


class _SynchronousDialogSubmitter:
    """Run direct Danbooru dialog construction without runtime ownership."""

    def submit(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> TaskHandle[TResult]:
        """Run one request synchronously and return a settled handle."""

        return _SynchronousDialogTaskHandle(request, cancellation=cancellation)


class _SynchronousDialogTaskHandle(Generic[TResult]):
    """Store one immediately completed dialog lookup result."""

    def __init__(
        self,
        request: TaskRequest[TResult],
        *,
        cancellation: CancellationToken,
    ) -> None:
        """Run one request and capture its outcome."""

        self._identity = request.identity
        queued_at = monotonic()
        started_at = monotonic()
        if cancellation.is_cancelled:
            self._outcome: TaskOutcome[TResult] = TaskOutcome(
                identity=request.identity,
                context=request.context,
                status="cancelled",
                cancellation_reason=cancellation.reason or "cancelled",
                timings=TaskTimings(
                    queued_at=queued_at,
                    started_at=started_at,
                    completed_at=monotonic(),
                ),
            )
            return
        try:
            result = request.work(cancellation)
        except BaseException as error:  # noqa: BLE001
            self._outcome = TaskOutcome(
                identity=request.identity,
                context=request.context,
                status="failed",
                error=error,
                timings=TaskTimings(
                    queued_at=queued_at,
                    started_at=started_at,
                    completed_at=monotonic(),
                ),
            )
        else:
            self._outcome = TaskOutcome(
                identity=request.identity,
                context=request.context,
                status="succeeded",
                result=result,
                timings=TaskTimings(
                    queued_at=queued_at,
                    started_at=started_at,
                    completed_at=monotonic(),
                ),
            )

    @property
    def identity(self) -> TaskIdentity:
        """Return the completed task identity."""

        return self._identity

    @property
    def is_finished(self) -> bool:
        """Return true because the request runs synchronously."""

        return True

    @property
    def outcome(self) -> TaskOutcome[TResult] | None:
        """Return the stored task outcome."""

        return self._outcome

    @property
    def state(self) -> str:
        """Return the stored task status."""

        return self._outcome.status

    def add_done_callback(
        self,
        callback: Callable[[TaskOutcome[TResult]], None],
        *,
        reason: str,
    ) -> None:
        """Run one completion callback immediately."""

        _ = reason
        callback(self._outcome)

    def cancel(self, *, reason: str) -> None:
        """Accept cancellation after synchronous completion."""

        _ = reason


@dataclass(frozen=True, slots=True)
class _WikiHistoryEntry:
    """Track one in-dialog navigation target for back/forward browsing."""

    target: str
    by_title: bool
    display_title: str


@dataclass(frozen=True, slots=True)
class _DialogLoadResult:
    """Carry one loaded wiki page plus parsed native render content."""

    lookup_result: DanbooruWikiContentLookupResult
    sections: tuple[DanbooruWikiSectionContent, ...]
    image_previews_by_post_id: dict[tuple[str, int], DanbooruWikiImagePreview]


class DanbooruWikiDialog(MessageBoxBase):  # type: ignore[misc]
    """Browse Danbooru wiki pages inside a native app-styled modal."""

    def __init__(
        self,
        *,
        wiki_service: DanbooruWikiLookupService,
        image_preview_service: DanbooruImagePreviewResolver | None = None,
        recent_posts_service: DanbooruRecentPostsResolver | None = None,
        selection_text: str,
        open_url: UrlOpener | None = None,
        lookup_dispatcher: DanbooruWikiLookupDispatcher | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Build the native Danbooru wiki browser dialog."""

        self._sizing_parent_window: QWidget | None = None
        super().__init__(_resolve_parent(parent))
        self._wiki_service = wiki_service
        self._image_preview_service = image_preview_service
        self._recent_posts_service = recent_posts_service
        self._open_url = open_url or open_external_url
        self._block_parser = DanbooruWikiBlockParser()
        self._lookup_dispatcher = lookup_dispatcher or QtDanbooruWikiLookupDispatcher(
            self
        )
        self._history: list[_WikiHistoryEntry] = []
        self._history_index = -1
        self._active_canonical_url: str | None = None
        self._active_request_token = 0
        self._current_display_title: ApplicationText = _DIALOG_FALLBACK_TITLE
        self._header_tooltip_filters: list[FluentToolTipFilter] = []

        self.setClosableOnMaskClicked(False)
        self.setModal(True)
        self.widget.setObjectName("DanbooruWikiDialogSurface")
        self.widget.setMinimumWidth(_DIALOG_MIN_WIDTH)
        self.widget.setMinimumHeight(_DIALOG_MIN_HEIGHT)
        self.viewLayout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.setSpacing(0)
        self.hideYesButton()
        self.hideCancelButton()
        self.buttonGroup.hide()
        self.buttonGroup.setFixedHeight(0)

        self._build_header()
        self._build_body()
        self._sync_navigation_buttons()
        self._apply_theme()
        connect_theme_refresh(self, self._apply_theme)
        self._navigate_to(selection_text, by_title=False, push_history=True)

    def showEvent(self, event: QEvent) -> None:
        """Apply responsive sizing from the owning window when the dialog opens."""

        super().showEvent(event)
        self._sync_responsive_parent_window()
        self._apply_responsive_shell_size()

    def hideEvent(self, event: QEvent) -> None:
        """Detach from parent-window resize tracking while the dialog is hidden."""

        self._clear_responsive_parent_window()
        super().hideEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Resize and recenter the dialog when its owning window changes."""

        if watched is self._sizing_parent_window and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Move,
        }:
            self._apply_responsive_shell_size()
        return bool(super().eventFilter(watched, event))

    def _build_header(self) -> None:
        """Create the native header with title, metadata, and navigation actions."""

        self._header = QWidget(self.widget)
        self._header.setObjectName("DanbooruWikiDialogHeader")
        layout = QVBoxLayout(self._header)
        layout.setContentsMargins(
            _HEADER_HORIZONTAL_PADDING,
            _HEADER_TOP_PADDING,
            _HEADER_HORIZONTAL_PADDING,
            _HEADER_BOTTOM_PADDING,
        )
        layout.setSpacing(8)

        top_row = QWidget(self._header)
        top_row.setObjectName("DanbooruWikiDialogTitleRow")
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        self._title_label = LocalizedTitleLabel(app_text("Danbooru wiki"), top_row)
        self._title_label.setObjectName("danbooruWikiTitleLabel")
        self._back_button = self._header_icon_button(
            icon=FIF.LEFT_ARROW,
            tooltip=app_text("Back"),
            accessible_name=app_text("Back"),
            parent=top_row,
        )
        self._back_button.clicked.connect(lambda: self._navigate_history(-1))
        self._forward_button = self._header_icon_button(
            icon=FIF.RIGHT_ARROW,
            tooltip=app_text("Forward"),
            accessible_name=app_text("Forward"),
            parent=top_row,
        )
        self._forward_button.clicked.connect(lambda: self._navigate_history(+1))
        self._copy_button = self._header_icon_button(
            icon=FIF.COPY,
            tooltip=app_text("Copy tag title"),
            accessible_name=app_text("Copy tag title"),
            parent=top_row,
        )
        self._copy_button.clicked.connect(self._copy_current_title)
        self._open_button = self._header_icon_button(
            icon=FIF.LINK,
            tooltip=app_text("Open tag wiki article in browser"),
            accessible_name=app_text("Open tag wiki article in browser"),
            parent=top_row,
        )
        self._open_button.clicked.connect(self._open_current_page)
        self._close_button = self._header_icon_button(
            icon=FIF.CLOSE,
            tooltip=app_text("Close"),
            accessible_name=app_text("Close"),
            parent=top_row,
        )
        self._close_button.clicked.connect(self.reject)
        top_layout.addWidget(self._back_button, 0)
        top_layout.addWidget(self._forward_button, 0)
        top_layout.addWidget(self._title_label, 1)
        top_layout.addSpacing(8)
        top_layout.addWidget(self._copy_button, 0)
        top_layout.addWidget(self._open_button, 0)
        top_layout.addWidget(self._close_button, 0)
        layout.addWidget(top_row)

        meta_row = QWidget(self._header)
        meta_row.setObjectName("DanbooruWikiDialogMetaRow")
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(12)
        self._post_count_label = CaptionLabel("", meta_row)
        self._freshness_label = CaptionLabel("", meta_row)
        self._freshness_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self._freshness_label.setStyleSheet(
            "QLabel { padding: 2px 8px; border-radius: 10px; "
            "background: rgba(127, 127, 127, 0.10); }"
        )
        self._pixiv_prefix_label = LocalizedCaptionLabel(
            app_text("On Pixiv:"), meta_row
        )
        self._pixiv_label = CaptionLabel("", meta_row)
        self._pixiv_label.setWordWrap(True)
        self._pixiv_label.setTextFormat(Qt.TextFormat.RichText)
        self._pixiv_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._pixiv_label.linkActivated.connect(self._open_url)
        meta_layout.addWidget(
            self._post_count_label,
            0,
            Qt.AlignmentFlag.AlignBaseline,
        )
        meta_layout.addWidget(
            self._freshness_label,
            0,
            Qt.AlignmentFlag.AlignBaseline,
        )
        meta_layout.addWidget(
            self._pixiv_prefix_label,
            0,
            Qt.AlignmentFlag.AlignBaseline,
        )
        meta_layout.addWidget(
            self._pixiv_label,
            1,
            Qt.AlignmentFlag.AlignBaseline,
        )
        layout.addWidget(meta_row)
        self.viewLayout.addWidget(self._header)

    def _build_body(self) -> None:
        """Create the browser body plus loading and error states."""

        self._body = QWidget(self.widget)
        self._body.setObjectName("DanbooruWikiDialogBody")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(
            _BODY_HORIZONTAL_PADDING,
            _BODY_TOP_PADDING,
            _BODY_HORIZONTAL_PADDING,
            _BODY_BOTTOM_PADDING,
        )
        body_layout.setSpacing(0)

        self._body_stack = QStackedWidget(self._body)
        self._body_stack.setObjectName("DanbooruWikiDialogBodyStack")
        self._content_view = DanbooruWikiContentView(
            open_url=self._open_url,
            navigate_to_title=lambda title: self._navigate_to(
                title,
                by_title=True,
                push_history=True,
            ),
            navigate_to_fragment=self._navigate_to_fragment,
            parent=self._body_stack,
        )
        self._content_view.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._body_stack.addWidget(self._content_view)

        state_widget = QWidget(self._body_stack)
        state_widget.setObjectName("DanbooruWikiDialogStateWidget")
        state_layout = QVBoxLayout(state_widget)
        state_layout.setContentsMargins(0, 18, 0, 18)
        state_layout.setSpacing(8)
        self._status_title_label = LocalizedStrongBodyLabel("", state_widget)
        self._status_body_label = LocalizedBodyLabel("", state_widget)
        self._status_body_label.setWordWrap(True)
        state_layout.addWidget(self._status_title_label)
        state_layout.addWidget(self._status_body_label)
        state_layout.addStretch(1)
        self._body_stack.addWidget(state_widget)

        body_layout.addWidget(self._body_stack, 1)
        self.viewLayout.addWidget(self._body, 1)

    def _navigate_to(self, target: str, *, by_title: bool, push_history: bool) -> None:
        """Load one selection text or wiki title into the dialog."""

        self._active_request_token += 1
        request_token = self._active_request_token
        display_title = target.strip().replace("_", " ") or _DIALOG_FALLBACK_TITLE
        self._set_title_text(display_title)
        self._show_status(
            title=app_text("Loading definition"),
            body=app_text("Fetching Danbooru wiki content..."),
        )
        self._lookup_dispatcher.submit(
            lambda: self._load_dialog_page(target=target, by_title=by_title),
            completed=lambda result: self._apply_lookup_result(
                request_token=request_token,
                target=target,
                by_title=by_title,
                push_history=push_history,
                result=result,
            ),
            failed=lambda error: self._handle_lookup_failure(
                request_token=request_token,
                target=target,
                error=error,
            ),
        )

    def _load_dialog_page(self, *, target: str, by_title: bool) -> _DialogLoadResult:
        """Load one wiki page plus parsed section/image render data off the UI thread."""

        lookup_result = (
            self._wiki_service.lookup_title(target)
            if by_title
            else self._wiki_service.lookup_selection(target)
        )
        if lookup_result.page is None:
            return _DialogLoadResult(
                lookup_result=lookup_result,
                sections=(),
                image_previews_by_post_id={},
            )
        sections = self._wiki_service.resolve_sections(
            self._block_parser.parse(lookup_result.page.body_dtext)
        )
        image_previews_by_post_id: dict[tuple[str, int], DanbooruWikiImagePreview] = {}
        if self._image_preview_service is not None:
            for reference in _embedded_references(sections):
                image_previews_by_post_id[
                    (reference.source_kind, reference.source_id)
                ] = self._image_preview_service.resolve_preview_for_reference(
                    source_kind=reference.source_kind,
                    source_id=reference.source_id,
                )
        if (
            self._recent_posts_service is not None
            and self._image_preview_service is not None
        ):
            sections = self._append_recent_posts_section(
                page_title=lookup_result.page.title,
                sections=sections,
                image_previews_by_post_id=image_previews_by_post_id,
            )
        return _DialogLoadResult(
            lookup_result=lookup_result,
            sections=sections,
            image_previews_by_post_id=image_previews_by_post_id,
        )

    def _append_recent_posts_section(
        self,
        *,
        page_title: str,
        sections: tuple[DanbooruWikiSectionContent, ...],
        image_previews_by_post_id: dict[tuple[str, int], DanbooruWikiImagePreview],
    ) -> tuple[DanbooruWikiSectionContent, ...]:
        """Append one app-owned recent-post section when visible posts are available."""

        if self._recent_posts_service is None or self._image_preview_service is None:
            return sections
        visible_post_ids = self._recent_posts_service.list_recent_visible_post_ids(
            page_title,
            desired_count=5,
        )
        if not visible_post_ids:
            return sections
        recent_items: list[DanbooruWikiImageReference] = []
        for post_id in visible_post_ids:
            preview = self._image_preview_service.resolve_preview_for_reference(
                source_kind="post",
                source_id=post_id,
            )
            image_previews_by_post_id[("post", post_id)] = preview
            if preview.state is not DanbooruImagePreviewState.READY:
                continue
            recent_items.append(
                DanbooruWikiImageReference(
                    source_kind="post",
                    source_id=post_id,
                )
            )
        if not recent_items:
            return sections
        return sections + (
            DanbooruWikiSectionContent(
                heading=app_text("Posts"),
                blocks=(DanbooruWikiImageReferenceBlock(items=tuple(recent_items)),),
            ),
        )

    def _apply_lookup_result(
        self,
        *,
        request_token: int,
        target: str,
        by_title: bool,
        push_history: bool,
        result: _DialogLoadResult,
    ) -> None:
        """Render one completed wiki lookup when it is still current."""

        if request_token != self._active_request_token:
            return
        lookup_result = result.lookup_result
        display_title = (
            lookup_result.page.display_title
            if lookup_result.page is not None
            else (lookup_result.resolved_title or target).replace("_", " ")
        )
        if push_history:
            self._push_history(
                _WikiHistoryEntry(
                    target=target,
                    by_title=by_title,
                    display_title=display_title,
                )
            )
        if lookup_result.page is None:
            self._active_canonical_url = None
            self._set_title_text(display_title)
            self._update_metadata(
                category_name=None,
                post_count=None,
                aliases=(),
                freshness_state=None,
            )
            self._show_status(
                title=_status_title_for_failure(lookup_result.failure_reason),
                body=_status_body_for_failure(lookup_result),
            )
            self._sync_navigation_buttons()
            return

        page = lookup_result.page
        assert page is not None
        self._active_canonical_url = page.canonical_url
        self._set_title_text(page.display_title)
        self._update_metadata(
            category_name=page.category_name,
            post_count=page.post_count,
            aliases=page.other_names,
            freshness_state=page.freshness_state,
        )
        self._content_view.render_page(
            page=page,
            sections=result.sections,
            image_previews_by_post_id=result.image_previews_by_post_id,
        )
        self._body_stack.setCurrentWidget(self._content_view)
        self._sync_navigation_buttons()
        log_debug(
            _LOGGER,
            "Danbooru wiki dialog rendered page.",
            resolved_title=page.title,
            history_index=self._history_index,
            history_length=len(self._history),
        )

    def _handle_lookup_failure(
        self,
        *,
        request_token: int,
        target: str,
        error: BaseException,
    ) -> None:
        """Show a native error state when lookup execution fails unexpectedly."""

        if request_token != self._active_request_token:
            return
        self._active_canonical_url = None
        self._set_title_text(target.replace("_", " ") or _DIALOG_FALLBACK_TITLE)
        self._update_metadata(
            category_name=None,
            post_count=None,
            aliases=(),
            freshness_state=None,
        )
        self._show_status(
            title=app_text("Lookup failed"),
            body=app_text("Danbooru wiki content could not be loaded unexpectedly."),
        )
        log_warning(
            _LOGGER,
            "Danbooru wiki dialog lookup failed unexpectedly.",
            target=target,
            error=repr(error),
        )

    def _push_history(self, entry: _WikiHistoryEntry) -> None:
        """Append one history entry and discard any stale forward branch."""

        if self._history_index + 1 < len(self._history):
            self._history = self._history[: self._history_index + 1]
        self._history.append(entry)
        self._history_index = len(self._history) - 1
        self._sync_navigation_buttons()

    def _navigate_history(self, delta: int) -> None:
        """Move backward or forward through the wiki history."""

        next_index = self._history_index + delta
        if not 0 <= next_index < len(self._history):
            return
        self._history_index = next_index
        entry = self._history[next_index]
        self._sync_navigation_buttons()
        self._navigate_to(entry.target, by_title=entry.by_title, push_history=False)

    def _sync_navigation_buttons(self) -> None:
        """Refresh navigation and external-open action availability."""

        self._back_button.setEnabled(self._history_index > 0)
        self._forward_button.setEnabled(self._history_index + 1 < len(self._history))
        self._open_button.setEnabled(bool(self._active_canonical_url))
        self._copy_button.setEnabled(bool(self._current_display_title.strip()))

    def _update_metadata(
        self,
        *,
        category_name: str | None,
        post_count: int | None,
        aliases: tuple[str, ...],
        freshness_state: DanbooruContentFreshnessState | None,
    ) -> None:
        """Render the current page metadata in the native header."""

        if post_count is None:
            self._post_count_label.setText("")
        else:
            set_localized_text(
                self._post_count_label,
                "%1 posts",
                f"{post_count:,}",
            )
        self._freshness_label.setVisible(
            freshness_state is DanbooruContentFreshnessState.STALE
        )
        if freshness_state is DanbooruContentFreshnessState.STALE:
            set_localized_text(self._freshness_label, "Cached copy")
        else:
            self._freshness_label.setText("")
        pixiv_links = _pixiv_links_text(aliases)
        self._pixiv_prefix_label.setVisible(bool(pixiv_links))
        self._pixiv_label.setText(pixiv_links)
        self._pixiv_label.setVisible(bool(pixiv_links))

    def _show_status(self, *, title: ApplicationText, body: ApplicationText) -> None:
        """Display one native loading, empty, or error state in the body."""

        self._status_title_label.setText(title)
        self._status_body_label.setText(body)
        self._body_stack.setCurrentIndex(1)

    def _handle_anchor_clicked(self, url: QUrl) -> None:
        """Route internal wiki links locally and external links to the URL opener."""

        url_text = url.toString()
        if url_text.startswith(_WIKI_SCHEME_PREFIX):
            target = unquote(url_text.split(":", 1)[1])
            self._navigate_to(target, by_title=True, push_history=True)
            return
        if url_text.startswith(_FRAGMENT_SCHEME_PREFIX):
            self._navigate_to_fragment(unquote(url_text.split(":", 1)[1]))
            return
        self._open_url(url_text)

    def _open_current_page(self) -> None:
        """Open the current wiki page in the system browser."""

        if self._active_canonical_url:
            self._open_url(self._active_canonical_url)

    def _navigate_to_fragment(self, anchor_id: str) -> None:
        """Scroll the current page to one parsed DText heading anchor."""

        self._content_view.scroll_to_anchor(anchor_id)

    def _copy_current_title(self) -> None:
        """Copy the current visible page title without decorative quotes."""

        QGuiApplication.clipboard().setText(
            render_application_text(self._current_display_title)
        )

    def _set_title_text(self, display_title: ApplicationText) -> None:
        """Store and render the current title using the quoted header presentation."""

        self._current_display_title = (
            display_title if display_title.strip() else _DIALOG_FALLBACK_TITLE
        )
        if self._current_display_title is _DIALOG_FALLBACK_TITLE:
            self._title_label.setText(app_text('"%1"', _DIALOG_FALLBACK_TITLE))
        else:
            self._title_label.setText(f'"{self._current_display_title}"')
        self._sync_navigation_buttons()

    def _header_icon_button(
        self,
        *,
        icon: object,
        tooltip: ApplicationMessage,
        accessible_name: ApplicationMessage,
        parent: QWidget,
    ) -> ToolButton:
        """Create one icon-only header action button."""

        button = ToolButton(icon, parent)
        set_localized_tooltip(button, tooltip.source_text, *tooltip.arguments)
        set_localized_accessible_name(
            button, accessible_name.source_text, *accessible_name.arguments
        )
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(_HEADER_BUTTON_SIZE, _HEADER_BUTTON_SIZE)
        tooltip_filter = ensure_fluent_tooltip_filter(
            button,
            show_delay_ms=1000,
            position=ToolTipPosition.BOTTOM,
        )
        self._header_tooltip_filters.append(tooltip_filter)
        return button

    def _apply_theme(self) -> None:
        """Apply the header/body split-surface styling for the current theme."""

        if _is_dark_theme():
            top_fill = _DARK_DIALOG_TOP_FILL
            body_fill = _DARK_DIALOG_BODY_FILL
        else:
            top_fill = _LIGHT_DIALOG_TOP_FILL
            body_fill = _LIGHT_DIALOG_BODY_FILL
        self.widget.setStyleSheet(
            "QWidget#DanbooruWikiDialogSurface {"
            f"  background: {body_fill};"
            f"  border-radius: {_SURFACE_RADIUS}px;"
            "}"
            "QWidget#DanbooruWikiDialogHeader {"
            f"  background: {top_fill};"
            f"  border-top-left-radius: {_SURFACE_RADIUS}px;"
            f"  border-top-right-radius: {_SURFACE_RADIUS}px;"
            "}"
            "QWidget#DanbooruWikiDialogBody {"
            f"  background: {body_fill};"
            f"  border-bottom-left-radius: {_SURFACE_RADIUS}px;"
            f"  border-bottom-right-radius: {_SURFACE_RADIUS}px;"
            "}"
            "QStackedWidget#DanbooruWikiDialogBodyStack {"
            "  background: transparent;"
            "}"
            "QWidget#DanbooruWikiDialogStateWidget {"
            "  background: transparent;"
            "}"
        )

    def _sync_responsive_parent_window(self) -> None:
        """Track the real top-level owner that controls responsive sizing."""

        resolved_parent_window = _responsive_sizing_parent_window(self.parentWidget())
        if resolved_parent_window is self._sizing_parent_window:
            return
        self._clear_responsive_parent_window()
        if resolved_parent_window is None:
            return
        resolved_parent_window.installEventFilter(self)
        self._sizing_parent_window = resolved_parent_window

    def _clear_responsive_parent_window(self) -> None:
        """Stop listening to the previous responsive sizing parent window."""

        if self._sizing_parent_window is None:
            return
        if isValid(self._sizing_parent_window):
            self._sizing_parent_window.removeEventFilter(self)
        self._sizing_parent_window = None

    def _apply_responsive_shell_size(self) -> None:
        """Resize and recenter the dialog from the current parent-window policy."""

        target_size = _target_dialog_size_for_parent(self._sizing_parent_window)
        self.widget.setMinimumSize(_DIALOG_MIN_WIDTH, _DIALOG_MIN_HEIGHT)
        self.widget.setFixedSize(target_size)


def _pixiv_links_text(aliases: tuple[str, ...]) -> str:
    """Return the dedicated Pixiv link markup for wiki ``other_names`` entries."""

    if not aliases:
        return ""
    return ", ".join(_render_pixiv_alias(alias) for alias in aliases)


def _render_pixiv_alias(alias: str) -> str:
    """Return one wiki ``other_names`` entry as a Pixiv link."""

    label, href = _pixiv_alias_href(alias)
    return _anchor_html(label=label, href=href)


def _pixiv_alias_href(alias: str) -> tuple[str, str]:
    """Return the label and Pixiv target URL for one wiki ``other_names`` entry."""

    stripped = alias.strip()
    pixiv_match = _PIXIV_ALIAS_PATTERN.match(stripped)
    if pixiv_match is not None:
        artwork_id = pixiv_match.group("artwork_id")
        return stripped, f"https://www.pixiv.net/artworks/{artwork_id}"
    if _PIXIV_URL_PATTERN.match(stripped):
        href = stripped if "://" in stripped else f"https://{stripped}"
        return stripped, href
    if _URL_ALIAS_PATTERN.match(stripped):
        href = stripped if "://" in stripped else f"https://{stripped}"
        return stripped, href
    return (
        stripped,
        f"https://www.pixiv.net/en/tags/{quote(stripped, safe='')}/artworks",
    )


def _anchor_html(*, label: str, href: str) -> str:
    """Return one escaped external anchor for dialog metadata."""

    return f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>'


def _status_title_for_failure(
    reason: DanbooruFailureReason | None,
) -> ApplicationText:
    """Return the status title shown for one lookup failure reason."""

    if reason is DanbooruFailureReason.NOT_FOUND:
        return app_text("Definition not found")
    if reason is DanbooruFailureReason.UNAVAILABLE:
        return app_text("Danbooru unavailable")
    if reason is DanbooruFailureReason.INVALID_RESPONSE:
        return app_text("Malformed Danbooru response")
    return app_text("Definition unavailable")


def _status_body_for_failure(
    result: DanbooruWikiContentLookupResult,
) -> ApplicationText:
    """Return the human-readable status body for one lookup failure result."""

    if result.failure_reason is DanbooruFailureReason.NOT_FOUND:
        return app_text(
            'No Danbooru wiki page was found for "%1".',
            result.requested_text.strip(),
        )
    if result.failure_reason is DanbooruFailureReason.UNAVAILABLE:
        return app_text("Danbooru did not respond. Try again in a moment.")
    if result.failure_reason is DanbooruFailureReason.INVALID_RESPONSE:
        return app_text("Danbooru returned content the app could not render safely.")
    return app_text("The requested definition is not available.")


def _embedded_references(
    sections: tuple[DanbooruWikiSectionContent, ...],
) -> tuple[DanbooruWikiImageReference, ...]:
    """Return unique Danbooru image references found in parsed image blocks."""

    references: list[DanbooruWikiImageReference] = []
    for section in sections:
        for block in section.blocks:
            if not isinstance(block, DanbooruWikiImageReferenceBlock):
                continue
            for item in block.items:
                if item not in references:
                    references.append(item)
    return tuple(references)


def _resolve_parent(parent: QWidget | None) -> QWidget:
    """Return a QWidget parent because qfluent mask dialogs require one."""

    if isinstance(parent, QWidget) and isValid(parent):
        top_level_parent = _responsive_sizing_parent_window(parent)
        if top_level_parent is not None:
            return top_level_parent
        return parent
    global _FALLBACK_PARENT
    if _FALLBACK_PARENT is None or not isValid(_FALLBACK_PARENT):
        _FALLBACK_PARENT = QWidget()
        _FALLBACK_PARENT.resize(1200, 800)
    return _FALLBACK_PARENT


def _responsive_sizing_parent_window(parent: QWidget | None) -> QWidget | None:
    """Return the real top-level owner used for responsive dialog sizing."""

    if not isinstance(parent, QWidget) or not isValid(parent):
        return None
    top_level_window = parent.window()
    if not isinstance(top_level_window, QWidget) or not isValid(top_level_window):
        return None
    if _FALLBACK_PARENT is not None and top_level_window is _FALLBACK_PARENT:
        return None
    return top_level_window


def _target_dialog_size_for_parent(parent_window: QWidget | None) -> QSize:
    """Return the responsive dialog size for the supplied top-level parent."""

    if parent_window is None or not isValid(parent_window):
        return QSize(_DIALOG_MIN_WIDTH, _DIALOG_MIN_HEIGHT)
    parent_size = parent_window.size()
    target_width = max(
        _DIALOG_MIN_WIDTH, round(parent_size.width() * _DIALOG_WIDTH_RATIO)
    )
    target_height = max(
        _DIALOG_MIN_HEIGHT,
        round(parent_size.height() * _DIALOG_HEIGHT_RATIO),
    )
    return QSize(target_width, target_height)


def _is_dark_theme() -> bool:
    """Return whether the dialog should render with dark theme styling."""

    return bool(isDarkTheme())


__all__ = ["DanbooruWikiDialog"]

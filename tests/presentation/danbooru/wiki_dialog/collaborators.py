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

"""Provide deterministic collaborators and exact ownership for wiki dialogs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import pytest
from PySide6.QtWidgets import QWidget

from substitute.application.danbooru import (
    DanbooruWikiContentLookupResult,
    DanbooruWikiImagePreview,
    DanbooruWikiSectionContent,
)
from substitute.presentation.dialogs.danbooru_wiki_dialog import (
    DanbooruImagePreviewResolver,
    DanbooruRecentPostsResolver,
    DanbooruWikiDialog,
    DanbooruWikiLookupDispatcher,
    DanbooruWikiLookupService,
    _DialogLoadResult,
)
import substitute.presentation.dialogs.danbooru_wiki_dialog as dialog_module
from tests.support.qt.lifecycle import destroy_qt_object

_WidgetT = TypeVar("_WidgetT", bound=QWidget)


class StubDanbooruWikiService:
    """Return deterministic lookup results and record navigation calls."""

    def __init__(
        self,
        *,
        selection_results: dict[str, DanbooruWikiContentLookupResult],
        title_results: dict[str, DanbooruWikiContentLookupResult] | None = None,
        section_resolver: Callable[
            [tuple[DanbooruWikiSectionContent, ...]],
            tuple[DanbooruWikiSectionContent, ...],
        ]
        | None = None,
    ) -> None:
        """Store results and an optional parsed-section transformation."""

        self._selection_results = dict(selection_results)
        self._title_results = dict(title_results or {})
        self._section_resolver = section_resolver
        self.calls: list[tuple[str, str]] = []

    def lookup_selection(self, selection_text: str) -> DanbooruWikiContentLookupResult:
        """Return the configured selection result and record its request."""

        self.calls.append(("selection", selection_text))
        return self._selection_results[selection_text]

    def lookup_title(self, title: str) -> DanbooruWikiContentLookupResult:
        """Return the configured title result and record its request."""

        self.calls.append(("title", title))
        return self._title_results[title]

    def resolve_sections(
        self,
        sections: tuple[DanbooruWikiSectionContent, ...],
    ) -> tuple[DanbooruWikiSectionContent, ...]:
        """Return unchanged or deterministically transformed parsed sections."""

        if self._section_resolver is None:
            return sections
        return self._section_resolver(sections)


class ImmediateDispatcher:
    """Run dialog lookups immediately through their completion callbacks."""

    def submit(
        self,
        lookup: Callable[[], _DialogLoadResult],
        *,
        completed: Callable[[_DialogLoadResult], None],
        failed: Callable[[BaseException], None],
    ) -> None:
        """Execute one lookup inline and report its outcome."""

        try:
            completed(lookup())
        except BaseException as error:  # noqa: BLE001
            failed(error)


class StubImagePreviewResolver:
    """Return deterministic image previews for parsed embed references."""

    def __init__(
        self,
        previews_by_reference: dict[tuple[str, int], DanbooruWikiImagePreview],
    ) -> None:
        """Store previews keyed by source kind and identifier."""

        self._previews_by_reference = dict(previews_by_reference)

    def resolve_preview_for_reference(
        self,
        *,
        source_kind: str,
        source_id: int,
    ) -> DanbooruWikiImagePreview:
        """Return the configured preview for one reference."""

        return self._previews_by_reference[(source_kind, source_id)]


class StubRecentPostsResolver:
    """Return deterministic recent visible post identifiers by tag."""

    def __init__(self, post_ids_by_tag: dict[str, tuple[int, ...]]) -> None:
        """Store recent post identifiers keyed by canonical tag title."""

        self._post_ids_by_tag = dict(post_ids_by_tag)

    def list_recent_visible_post_ids(
        self,
        tag_name: str,
        *,
        desired_count: int = 5,
    ) -> tuple[int, ...]:
        """Return up to the desired number of configured post identifiers."""

        return self._post_ids_by_tag.get(tag_name, ())[:desired_count]


class DanbooruWikiDialogOwner:
    """Own dialogs and independent parent windows constructed by one test."""

    def __init__(self) -> None:
        """Initialize empty dialog and widget ownership."""

        self._dialogs: list[DanbooruWikiDialog] = []
        self._widgets: list[QWidget] = []

    def own_widget(self, widget: _WidgetT) -> _WidgetT:
        """Retain one independent parent or supporting widget root."""

        self._widgets.append(widget)
        return widget

    def build(
        self,
        *,
        wiki_service: DanbooruWikiLookupService,
        selection_text: str,
        image_preview_service: DanbooruImagePreviewResolver | None = None,
        recent_posts_service: DanbooruRecentPostsResolver | None = None,
        open_url: Callable[[str], bool] | None = None,
        lookup_dispatcher: DanbooruWikiLookupDispatcher | None = None,
        parent: QWidget | None = None,
    ) -> DanbooruWikiDialog:
        """Build and retain one native wiki dialog."""

        dialog = DanbooruWikiDialog(
            wiki_service=wiki_service,
            image_preview_service=image_preview_service,
            recent_posts_service=recent_posts_service,
            selection_text=selection_text,
            open_url=open_url,
            lookup_dispatcher=lookup_dispatcher,
            parent=parent,
        )
        self._dialogs.append(dialog)
        return dialog

    def destroy_all(self) -> None:
        """Destroy dialogs before independent supporting widget roots."""

        for dialog in reversed(self._dialogs):
            destroy_qt_object(dialog)
        self._dialogs.clear()
        for widget in reversed(self._widgets):
            destroy_qt_object(widget)
        self._widgets.clear()


class RecordingClipboard:
    """Retain copied wiki text without touching the process clipboard."""

    def __init__(self) -> None:
        """Initialize empty clipboard text."""

        self.text = ""

    def setText(self, text: str) -> None:  # noqa: N802
        """Record copied text."""

        self.text = text


class _ClipboardApplicationBoundary:
    """Expose one test-local clipboard through the QGuiApplication surface."""

    def __init__(self, clipboard: RecordingClipboard) -> None:
        """Store the clipboard returned to dialog production code."""

        self._clipboard = clipboard

    def clipboard(self) -> RecordingClipboard:
        """Return the test-local clipboard."""

        return self._clipboard


def install_recording_clipboard(
    monkeypatch: pytest.MonkeyPatch,
) -> RecordingClipboard:
    """Replace only the dialog clipboard output with a test-local sink."""

    clipboard = RecordingClipboard()
    monkeypatch.setattr(
        dialog_module,
        "QGuiApplication",
        _ClipboardApplicationBoundary(clipboard),
    )
    return clipboard


__all__ = [
    "DanbooruWikiDialogOwner",
    "ImmediateDispatcher",
    "RecordingClipboard",
    "StubDanbooruWikiService",
    "StubImagePreviewResolver",
    "StubRecentPostsResolver",
    "install_recording_clipboard",
]

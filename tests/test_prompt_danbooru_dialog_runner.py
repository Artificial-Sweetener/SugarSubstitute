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

"""Tests for the prompt-editor Danbooru dialog execution boundary."""

from __future__ import annotations

import os
from collections.abc import Callable
from collections.abc import Iterator
from typing import cast

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruWikiContentService,
)
from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.composition import (
    PromptEditorCompositionContext,
    PromptEditorCompositionFactory,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptDanbooruActionController,
    PromptFeatureProfileController,
)
from substitute.presentation.editor.prompt_editor.interactions import (
    PromptDanbooruDialogHostAdapter,
    PromptDanbooruDialogRunner,
    PromptExternalUrlActionRunner,
)
from substitute.presentation.editor.prompt_editor.projection.surface import (
    PromptProjectionSurface,
)


@pytest.fixture
def prompt_widgets() -> Iterator[list[QWidget]]:
    """Collect Qt widgets created by a test and close them afterward."""

    widgets: list[QWidget] = []
    try:
        yield widgets
    finally:
        for widget in reversed(widgets):
            widget.close()
            widget.deleteLater()
        _ensure_qapp().processEvents()


class _FakeDialog:
    """Capture dialog construction values without showing a modal."""

    def __init__(self, sink: list[dict[str, object]], **kwargs: object) -> None:
        """Store construction keyword arguments for assertions."""

        self._sink = sink
        self._kwargs = kwargs
        self._executed = False
        sink.append(kwargs)

    def exec(self) -> int:
        """Record modal execution and return an accepted result code."""

        self._executed = True
        self._kwargs["executed"] = True
        return 1


def test_runner_executes_dialog_with_prepared_services_and_exact_selection() -> None:
    """Runner should execute the prepared request without mutating selected text."""

    _ensure_qapp()
    parent = QWidget()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record a URL open request and report success."""

        opened_urls.append(url)
        return True

    wiki_service = cast(DanbooruWikiContentService, object())
    image_preview_service = cast(DanbooruImagePreviewService, object())
    recent_posts_service = cast(DanbooruRecentPostsService, object())
    host = PromptDanbooruDialogHostAdapter(
        source_identity_provider=lambda: PromptCommandSourceIdentity(
            source_revision=12,
            source_length=40,
        ),
        dialog_parent_provider=lambda: parent,
        external_url_actions=PromptExternalUrlActionRunner(open_url),
    )
    controller = _controller(
        host=host,
        wiki_service=wiki_service,
        image_preview_service=image_preview_service,
        recent_posts_service=recent_posts_service,
    )
    dialog_calls: list[dict[str, object]] = []
    runner = PromptDanbooruDialogRunner(
        action_controller=controller,
        dialog_factory=lambda **kwargs: _FakeDialog(dialog_calls, **kwargs),
    )

    assert runner.open_wiki_for_selection(" long hair\n")

    assert len(dialog_calls) == 1
    assert dialog_calls[0]["wiki_service"] is wiki_service
    assert dialog_calls[0]["image_preview_service"] is image_preview_service
    assert dialog_calls[0]["recent_posts_service"] is recent_posts_service
    assert dialog_calls[0]["selection_text"] == " long hair\n"
    assert dialog_calls[0]["parent"] is parent
    assert dialog_calls[0]["executed"] is True
    cast(Callable[[str], bool], dialog_calls[0]["open_url"])("https://example.invalid")
    assert opened_urls == ["https://example.invalid"]


def test_runner_suppresses_disabled_lookup_without_constructing_dialog() -> None:
    """Runner should not construct a dialog when feature readiness denies lookup."""

    dialog_calls: list[dict[str, object]] = []
    host = PromptDanbooruDialogHostAdapter(
        source_identity_provider=lambda: None,
        dialog_parent_provider=QWidget,
        external_url_actions=PromptExternalUrlActionRunner(lambda _url: False),
    )
    controller = _controller(
        host=host,
        wiki_service=cast(DanbooruWikiContentService, object()),
        enabled_features=(),
    )
    runner = PromptDanbooruDialogRunner(
        action_controller=controller,
        dialog_factory=lambda **kwargs: _FakeDialog(dialog_calls, **kwargs),
    )

    assert not runner.open_wiki_for_selection("long hair")
    assert dialog_calls == []


def test_dialog_host_adapter_selects_window_parent_and_url_opener(
    prompt_widgets: list[QWidget],
) -> None:
    """Composition host adapter should choose the top-level window parent."""

    app = _ensure_qapp()
    window = QWidget()
    panel = QWidget(window)
    editor = QWidget(panel)
    prompt_widgets.extend([window, panel, editor])
    window.show()
    panel.show()
    editor.show()
    app.processEvents()
    opened_urls: list[str] = []

    def open_url(url: str) -> bool:
        """Record a URL open request and report success."""

        opened_urls.append(url)
        return True

    source_identity = PromptCommandSourceIdentity(source_revision=7, source_length=11)
    adapter = PromptEditorCompositionFactory().build_danbooru_dialog_host_adapter(
        _composition_context(editor),
        source_identity_provider=lambda: source_identity,
        external_url_actions=PromptExternalUrlActionRunner(open_url),
    )

    assert adapter.prompt_command_source_identity() is source_identity
    assert adapter.danbooru_wiki_dialog_parent() is window
    adapter.external_url_opener()("https://example.invalid")
    assert opened_urls == ["https://example.invalid"]


def test_dialog_host_adapter_falls_back_to_parent_then_editor(
    prompt_widgets: list[QWidget],
) -> None:
    """Composition host adapter should keep old parent fallback behavior."""

    _ensure_qapp()
    parent = QWidget()
    editor = QWidget(parent)
    prompt_widgets.extend([parent, editor])
    parent.show()
    editor.show()
    adapter = PromptEditorCompositionFactory().build_danbooru_dialog_host_adapter(
        _composition_context(editor),
        source_identity_provider=lambda: None,
        external_url_actions=PromptExternalUrlActionRunner(lambda _url: False),
    )
    assert adapter.danbooru_wiki_dialog_parent() is parent

    orphan = QWidget()
    prompt_widgets.append(orphan)
    orphan_adapter = (
        PromptEditorCompositionFactory().build_danbooru_dialog_host_adapter(
            _composition_context(orphan),
            source_identity_provider=lambda: None,
            external_url_actions=PromptExternalUrlActionRunner(lambda _url: False),
        )
    )
    assert orphan_adapter.danbooru_wiki_dialog_parent() is orphan


def _controller(
    *,
    host: PromptDanbooruDialogHostAdapter,
    wiki_service: DanbooruWikiContentService | None,
    image_preview_service: DanbooruImagePreviewService | None = None,
    recent_posts_service: DanbooruRecentPostsService | None = None,
    enabled_features: tuple[PromptEditorFeature, ...] = (
        PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
    ),
) -> PromptDanbooruActionController:
    """Build a Danbooru action controller for runner tests."""

    return PromptDanbooruActionController(
        host=host,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(enabled_features)
        ),
        wiki_service=wiki_service,
        image_preview_service=image_preview_service,
        recent_posts_service=recent_posts_service,
        url_import_service=None,
    )


def _composition_context(editor: QWidget) -> PromptEditorCompositionContext:
    """Build a minimal composition context for host-adapter tests."""

    return PromptEditorCompositionContext(
        editor=editor,
        shell_viewport=editor,
        autocomplete_limit=10,
        autocomplete_minimum_prefix_length=2,
        fill_plane_factory=_unused_widget_factory,
        resize_handle_factory=_unused_resize_handle_factory,
    )


def _unused_widget_factory(
    editor: QWidget,
    surface: PromptProjectionSurface,
    parent: QWidget,
    *,
    shell_padding_only: bool,
) -> QWidget:
    """Satisfy the composition context without constructing projection widgets."""

    del editor
    del surface
    del shell_padding_only
    return QWidget(parent)


def _unused_resize_handle_factory(editor: QWidget) -> QWidget:
    """Satisfy the composition context without constructing a resize handle."""

    del editor
    return QWidget()


def _ensure_qapp() -> QApplication:
    """Return the active QApplication, creating one for widget parent tests."""

    app = QApplication.instance()
    if app is None:
        return QApplication([])
    return cast(QApplication, app)

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

"""Tests for Danbooru prompt-editor action controller ownership."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)
from substitute.application.prompt_editor import (
    PromptEditorFeature,
    PromptEditorFeatureProfile,
)
from substitute.presentation.editor.prompt_editor.commands import (
    PromptCommandSourceIdentity,
)
from substitute.presentation.editor.prompt_editor.features import (
    PromptDanbooruActionController,
    PromptDanbooruWikiDialogRequest,
    PromptFeatureProfileController,
)


class _Host:
    """Provide host state needed by the Danbooru action controller."""

    def __init__(self) -> None:
        """Create stable fake host collaborators."""

        self.parent = object()
        self.opened_urls: list[str] = []

    def prompt_command_source_identity(self) -> PromptCommandSourceIdentity:
        """Return a stable fake source identity."""

        return PromptCommandSourceIdentity(source_revision=4, source_length=18)

    def danbooru_wiki_dialog_parent(self) -> object:
        """Return the fake dialog parent."""

        return self.parent

    def external_url_opener(self) -> Callable[[str], bool]:
        """Return the fake external URL opener."""

        return self._open_url

    def _open_url(self, url: str) -> bool:
        """Record a URL open request and report success."""

        self.opened_urls.append(url)
        return True


def test_prepared_wiki_lookup_action_requires_feature_service_and_selection() -> None:
    """Wiki lookup readiness should be prepared before menu reads."""

    host = _Host()
    wiki_service = cast(DanbooruWikiContentService, object())
    controller = _controller(host=host, wiki_service=wiki_service)

    snapshot = controller.prepare_menu_snapshot_for_selection(
        selection_text="long hair",
        selection_range=(0, 9),
        read_only=False,
        reason="test",
    )
    action = controller.prepared_menu_snapshot_for_selection(
        selection_text="long hair",
        selection_range=(0, 9),
        read_only=False,
    ).wiki_lookup_action

    assert action is not None
    assert action.ready is True
    assert action.label == "Danbooru wiki lookup"
    assert action.command_request is not None
    assert action.command_request.command_name == "danbooru_wiki_lookup"
    assert action.command_request.identity.source_revision == 4
    assert action.command_request.payload.selection_text == "long hair"
    assert snapshot.selected_text_identity == ("selected_text", 9, hash("long hair"))
    assert (
        controller.prepare_menu_snapshot_for_selection(
            selection_text="",
            selection_range=None,
            read_only=False,
            reason="test",
        ).wiki_lookup_action
        is None
    )
    assert (
        _controller(host=host, wiki_service=None)
        .prepare_menu_snapshot_for_selection(
            selection_text="long hair",
            selection_range=(0, 9),
            read_only=False,
            reason="test",
        )
        .unavailable_reason
        == "service_unavailable"
    )
    assert (
        _controller(
            host=host,
            wiki_service=wiki_service,
            enabled_features=(),
        )
        .prepare_menu_snapshot_for_selection(
            selection_text="long hair",
            selection_range=(0, 9),
            read_only=False,
            reason="test",
        )
        .unavailable_reason
        == "feature_disabled"
    )


def test_prepared_wiki_lookup_read_only_and_unprepared_states_fail_closed() -> None:
    """Read-only and unprepared menu reads should omit wiki callbacks."""

    host = _Host()
    wiki_service = cast(DanbooruWikiContentService, object())
    controller = _controller(host=host, wiki_service=wiki_service)

    read_only_snapshot = controller.prepare_menu_snapshot_for_selection(
        selection_text="long hair",
        selection_range=(0, 9),
        read_only=True,
        reason="test",
    )
    unprepared_snapshot = controller.prepared_menu_snapshot_for_selection(
        selection_text="long hair",
        selection_range=(0, 9),
        read_only=False,
    )

    assert read_only_snapshot.wiki_lookup_action is None
    assert read_only_snapshot.unavailable_reason == "read_only"
    assert unprepared_snapshot.wiki_lookup_action is None
    assert unprepared_snapshot.identity.stale is True
    assert (
        unprepared_snapshot.unavailable_reason
        == "danbooru_selection_snapshot_unprepared"
    )


def test_wiki_dialog_request_preserves_exact_selection_and_services() -> None:
    """Dialog requests should preserve exact selected text without constructing Qt."""

    host = _Host()
    wiki_service = cast(DanbooruWikiContentService, object())
    image_preview_service = cast(DanbooruImagePreviewService, object())
    recent_posts_service = cast(DanbooruRecentPostsService, object())
    controller = _controller(
        host=host,
        wiki_service=wiki_service,
        image_preview_service=image_preview_service,
        recent_posts_service=recent_posts_service,
    )

    request = controller.wiki_dialog_request("long hair\n")

    assert request is not None
    assert request.wiki_service is wiki_service
    assert request.image_preview_service is image_preview_service
    assert request.recent_posts_service is recent_posts_service
    assert request.selection_text == "long hair\n"
    assert request.parent is host.parent
    request.open_url("https://example.invalid")
    assert host.opened_urls == ["https://example.invalid"]


def test_open_wiki_for_selection_runs_prepared_dialog_request() -> None:
    """Opening a wiki lookup should delegate only a prepared dialog request."""

    host = _Host()
    wiki_service = cast(DanbooruWikiContentService, object())
    controller = _controller(host=host, wiki_service=wiki_service)
    requests: list[PromptDanbooruWikiDialogRequest] = []

    assert controller.open_wiki_for_selection(
        "long hair",
        dialog_runner=requests.append,
    )
    assert requests[0].selection_text == "long hair"
    assert requests[0].wiki_service is wiki_service
    assert not controller.open_wiki_for_selection("", dialog_runner=requests.append)
    assert len(requests) == 1


def test_url_import_state_reflects_feature_gate_and_service() -> None:
    """URL import readiness should describe service and feature-gate availability."""

    host = _Host()
    import_service = cast(DanbooruUrlImportService, object())
    controller = _controller(host=host, url_import_service=import_service)

    ready_state = controller.url_import_state()
    assert ready_state.service_available is True
    assert ready_state.enabled is True
    assert ready_state.ready is True
    assert ready_state.disabled_reason is None
    assert controller.url_import_enabled is True
    assert controller.url_import_service is import_service

    disabled_state = _controller(
        host=host,
        url_import_service=import_service,
        enabled_features=(PromptEditorFeature.DANBOORU_WIKI_LOOKUP,),
    ).url_import_state()
    assert disabled_state.ready is False
    assert disabled_state.disabled_reason == "feature_disabled"

    missing_service_state = _controller(
        host=host,
        url_import_service=None,
    ).url_import_state()
    assert missing_service_state.ready is False
    assert missing_service_state.disabled_reason == "service_unavailable"


def test_snapshot_does_not_echo_selected_text_when_action_unavailable() -> None:
    """Disabled reasons should avoid leaking selected prompt text."""

    host = _Host()
    snapshot = _controller(
        host=host, wiki_service=None
    ).prepare_menu_snapshot_for_selection(
        selection_text="private prompt selection",
        selection_range=(0, 24),
        read_only=False,
        reason="test",
    )

    assert snapshot.wiki_lookup_action is None
    assert snapshot.url_import_state.disabled_reason == "service_unavailable"
    assert "private prompt selection" not in repr(snapshot)


def _controller(
    *,
    host: _Host,
    wiki_service: DanbooruWikiContentService | None = None,
    image_preview_service: DanbooruImagePreviewService | None = None,
    recent_posts_service: DanbooruRecentPostsService | None = None,
    url_import_service: DanbooruUrlImportService | None = None,
    enabled_features: tuple[PromptEditorFeature, ...] = (
        PromptEditorFeature.DANBOORU_WIKI_LOOKUP,
        PromptEditorFeature.DANBOORU_URL_IMPORT,
    ),
) -> PromptDanbooruActionController:
    """Build a Danbooru action controller for tests."""

    return PromptDanbooruActionController(
        host=host,
        feature_profile=PromptFeatureProfileController(
            PromptEditorFeatureProfile.enabled_profile(enabled_features)
        ),
        wiki_service=wiki_service,
        image_preview_service=image_preview_service,
        recent_posts_service=recent_posts_service,
        url_import_service=url_import_service,
    )

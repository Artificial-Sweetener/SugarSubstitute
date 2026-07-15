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

"""Prepare Danbooru prompt-editor actions without constructing Qt widgets."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Protocol

from substitute.application.danbooru import (
    DanbooruImagePreviewService,
    DanbooruRecentPostsService,
    DanbooruUrlImportService,
    DanbooruWikiContentService,
)

from ..commands import PromptFeatureCommandRequest, PromptFeatureSnapshotIdentity
from .feature_profile_controller import (
    PromptFeatureActionState,
    PromptFeatureProfileController,
)

UrlOpener = Callable[[str], bool]


@dataclass(frozen=True, slots=True)
class PromptDanbooruWikiLookupPayload:
    """Carry selected prompt text for one prepared Danbooru wiki lookup."""

    selection_text: str


@dataclass(frozen=True, slots=True)
class PromptDanbooruWikiDialogRequest:
    """Describe a native Danbooru wiki dialog request for a Qt host to run."""

    wiki_service: DanbooruWikiContentService
    image_preview_service: DanbooruImagePreviewService | None
    recent_posts_service: DanbooruRecentPostsService | None
    selection_text: str
    open_url: UrlOpener
    parent: object


@dataclass(frozen=True, slots=True)
class PromptDanbooruUrlImportState:
    """Publish Danbooru URL import readiness for paste handling."""

    service_available: bool
    enabled: bool
    ready: bool
    disabled_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PromptDanbooruActionSnapshot:
    """Publish prepared Danbooru action state for foreground consumers."""

    identity: PromptFeatureSnapshotIdentity
    wiki_lookup_action: PromptFeatureActionState[PromptDanbooruWikiLookupPayload] | None
    url_import_state: PromptDanbooruUrlImportState
    selected_text_identity: Hashable | None = None
    selection_range: tuple[int, int] | None = None
    read_only: bool = False
    unavailable_reason: str | None = None


PromptDanbooruDialogRunner = Callable[[PromptDanbooruWikiDialogRequest], None]


class PromptDanbooruActionHost(Protocol):
    """Expose prompt-editor state needed for Danbooru action requests."""

    def prompt_command_source_identity(self) -> object | None:
        """Return the current source identity when available."""

    def danbooru_wiki_dialog_parent(self) -> object:
        """Return the parent object for native Danbooru wiki dialogs."""

    def external_url_opener(self) -> UrlOpener:
        """Return the URL opener used by Danbooru wiki dialogs."""


class PromptDanbooruActionController:
    """Own Danbooru wiki action readiness and URL-import feature readiness."""

    def __init__(
        self,
        *,
        host: PromptDanbooruActionHost,
        feature_profile: PromptFeatureProfileController,
        wiki_service: DanbooruWikiContentService | None,
        image_preview_service: DanbooruImagePreviewService | None,
        recent_posts_service: DanbooruRecentPostsService | None,
        url_import_service: DanbooruUrlImportService | None,
    ) -> None:
        """Store Danbooru services and publish an initial action snapshot."""

        self._host = host
        self._feature_profile = feature_profile
        self._wiki_service = wiki_service
        self._image_preview_service = image_preview_service
        self._recent_posts_service = recent_posts_service
        self._url_import_service = url_import_service
        self._snapshot = self._build_snapshot(
            selection_text="",
            selection_range=None,
            read_only=False,
            unavailable_reason="danbooru_selection_snapshot_unprepared",
        )
        self._prepared_menu_snapshots: dict[
            tuple[object, ...],
            PromptDanbooruActionSnapshot,
        ] = {}

    @property
    def snapshot(self) -> PromptDanbooruActionSnapshot:
        """Return the most recently prepared Danbooru action snapshot."""

        return self._snapshot

    @property
    def url_import_service(self) -> DanbooruUrlImportService | None:
        """Return the configured Danbooru URL import service."""

        return self._url_import_service

    @property
    def url_import_enabled(self) -> bool:
        """Return whether Danbooru URL paste import is currently enabled."""

        return self.url_import_state().ready

    def url_import_state(self) -> PromptDanbooruUrlImportState:
        """Return prepared Danbooru URL import readiness."""

        service_available = self._url_import_service is not None
        enabled = self._feature_profile.danbooru_url_import_enabled
        disabled_reason = None
        if not enabled:
            disabled_reason = "feature_disabled"
        elif not service_available:
            disabled_reason = "service_unavailable"
        return PromptDanbooruUrlImportState(
            service_available=service_available,
            enabled=enabled,
            ready=service_available and enabled,
            disabled_reason=disabled_reason,
        )

    def prepare_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        reason: str,
    ) -> PromptDanbooruActionSnapshot:
        """Prepare Danbooru menu actions for one captured selection."""

        _ = reason
        snapshot = self._build_snapshot(
            selection_text=selection_text,
            selection_range=selection_range,
            read_only=read_only,
        )
        self._prepared_menu_snapshots[
            self._menu_selection_key(
                selection_text=selection_text,
                selection_range=selection_range,
                read_only=read_only,
            )
        ] = snapshot
        self._snapshot = snapshot
        return self._snapshot

    def prepared_menu_snapshot_for_selection(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptDanbooruActionSnapshot:
        """Return prepared Danbooru selected-text menu state without deriving it."""

        snapshot = self._prepared_menu_snapshots.get(
            self._menu_selection_key(
                selection_text=selection_text,
                selection_range=selection_range,
                read_only=read_only,
            )
        )
        if snapshot is not None:
            return snapshot
        return self._build_snapshot(
            selection_text=selection_text,
            selection_range=selection_range,
            read_only=read_only,
            unavailable_reason="danbooru_selection_snapshot_unprepared",
        )

    def _prepared_wiki_lookup_action(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> PromptFeatureActionState[PromptDanbooruWikiLookupPayload] | None:
        """Return a prepared Danbooru wiki lookup action when available."""

        normalized_selection = selection_text.strip()
        if not normalized_selection:
            return None
        if read_only:
            return None
        if not self._feature_profile.danbooru_wiki_lookup_enabled:
            return None
        if self._wiki_service is None:
            return None
        return PromptFeatureActionState(
            action_id="danbooru.wiki_lookup",
            label="Danbooru wiki lookup",
            ready=True,
            command_request=PromptFeatureCommandRequest(
                command_name="danbooru_wiki_lookup",
                identity=self._snapshot_identity(
                    selection_text=selection_text,
                    selection_range=selection_range,
                    read_only=read_only,
                ),
                payload=PromptDanbooruWikiLookupPayload(
                    selection_text=selection_text,
                ),
            ),
        )

    def wiki_dialog_request(
        self,
        selection_text: str,
    ) -> PromptDanbooruWikiDialogRequest | None:
        """Return a native wiki dialog request for one selected prompt string."""

        action = self._prepared_wiki_lookup_action(
            selection_text=selection_text,
            selection_range=None,
            read_only=False,
        )
        if action is None or action.command_request is None:
            return None
        wiki_service = self._wiki_service
        if wiki_service is None:
            return None
        return PromptDanbooruWikiDialogRequest(
            wiki_service=wiki_service,
            image_preview_service=self._image_preview_service,
            recent_posts_service=self._recent_posts_service,
            selection_text=action.command_request.payload.selection_text,
            open_url=self._host.external_url_opener(),
            parent=self._host.danbooru_wiki_dialog_parent(),
        )

    def open_wiki_for_selection(
        self,
        selection_text: str,
        *,
        dialog_runner: PromptDanbooruDialogRunner,
    ) -> bool:
        """Run a prepared native Danbooru wiki dialog request."""

        request = self.wiki_dialog_request(selection_text)
        if request is None:
            return False
        dialog_runner(request)
        return True

    def _snapshot_identity(
        self,
        *,
        selection_text: str = "",
        selection_range: tuple[int, int] | None = None,
        read_only: bool = False,
        stale: bool = False,
    ) -> PromptFeatureSnapshotIdentity:
        """Return a snapshot identity tied to current source and feature profile."""

        source_identity = self._host.prompt_command_source_identity()
        raw_source_revision = getattr(source_identity, "source_revision", None)
        source_revision = (
            raw_source_revision if isinstance(raw_source_revision, int) else None
        )
        return PromptFeatureSnapshotIdentity(
            source_revision=source_revision,
            feature_profile_id=self._feature_profile.identity.feature_profile_id,
            stale=stale,
            query_identity=(
                "danbooru_menu_selection",
                _selected_text_identity(selection_text),
                selection_range,
                read_only,
                self._wiki_service is not None,
                self._feature_profile.danbooru_wiki_lookup_enabled,
            ),
        )

    def _build_snapshot(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
        unavailable_reason: str | None = None,
    ) -> PromptDanbooruActionSnapshot:
        """Build selected-text Danbooru menu state from current prepared inputs."""

        reason = unavailable_reason or self._wiki_unavailable_reason(
            selection_text=selection_text,
            read_only=read_only,
        )
        stale = unavailable_reason is not None
        return PromptDanbooruActionSnapshot(
            identity=self._snapshot_identity(
                selection_text=selection_text,
                selection_range=selection_range,
                read_only=read_only,
                stale=stale,
            ),
            wiki_lookup_action=(
                None
                if reason is not None
                else self._prepared_wiki_lookup_action(
                    selection_text=selection_text,
                    selection_range=selection_range,
                    read_only=read_only,
                )
            ),
            url_import_state=self.url_import_state(),
            selected_text_identity=_selected_text_identity(selection_text),
            selection_range=selection_range,
            read_only=read_only,
            unavailable_reason=reason,
        )

    def _wiki_unavailable_reason(
        self,
        *,
        selection_text: str,
        read_only: bool,
    ) -> str | None:
        """Return the wiki lookup unavailable reason for selected text."""

        if not selection_text.strip():
            return "empty_selection"
        if read_only:
            return "read_only"
        if not self._feature_profile.danbooru_wiki_lookup_enabled:
            return "feature_disabled"
        if self._wiki_service is None:
            return "service_unavailable"
        return None

    def _menu_selection_key(
        self,
        *,
        selection_text: str,
        selection_range: tuple[int, int] | None,
        read_only: bool,
    ) -> tuple[object, ...]:
        """Return the cache key for one prepared Danbooru menu selection."""

        return (
            self._snapshot_identity(
                selection_text=selection_text,
                selection_range=selection_range,
                read_only=read_only,
            ),
            _selected_text_identity(selection_text),
            selection_range,
            read_only,
        )


def _selected_text_identity(selection_text: str) -> tuple[str, int, int]:
    """Return a prompt-safe identity for selected prompt text."""

    return ("selected_text", len(selection_text), hash(selection_text))


__all__ = [
    "PromptDanbooruActionController",
    "PromptDanbooruActionHost",
    "PromptDanbooruActionSnapshot",
    "PromptDanbooruDialogRunner",
    "PromptDanbooruUrlImportState",
    "PromptDanbooruWikiDialogRequest",
    "PromptDanbooruWikiLookupPayload",
]

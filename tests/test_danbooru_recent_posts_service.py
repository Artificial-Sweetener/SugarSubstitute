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

"""Unit tests for bounded recent Danbooru post retrieval."""

from __future__ import annotations

from pathlib import Path

from substitute.application.danbooru.preferences_service import (
    DanbooruPreferenceService,
)
from substitute.application.danbooru.recent_posts_service import (
    DanbooruRecentPostsService,
)
from substitute.domain.danbooru.models import DanbooruPostRecord
from substitute.domain.danbooru.preferences import DanbooruImageRatingPolicy
from substitute.infrastructure.persistence.danbooru_cache_store import (
    SqliteDanbooruCacheStore,
)


class _StubDanbooruRecentPostsClient:
    """Return deterministic tag-post batches for recent-post service tests."""

    def __init__(
        self,
        *,
        posts_by_request: dict[tuple[str, int | None], tuple[DanbooruPostRecord, ...]],
    ) -> None:
        """Store deterministic post batches and capture each query."""

        self._posts_by_request = dict(posts_by_request)
        self.calls: list[tuple[str, int, int | None]] = []

    def list_posts_by_tag(
        self,
        tag_name: str,
        *,
        limit: int,
        before_post_id: int | None = None,
    ) -> tuple[DanbooruPostRecord, ...]:
        """Return the configured post batch for the requested page."""

        self.calls.append((tag_name, limit, before_post_id))
        return self._posts_by_request.get((tag_name, before_post_id), ())


class _MemoryDanbooruPreferenceRepository:
    """Persist Danbooru preferences in memory for unit tests."""

    def __init__(self) -> None:
        """Initialize with default Danbooru preferences."""

        self.preferences = DanbooruPreferenceService(
            _NullDanbooruPreferenceRepository()
        ).default_preferences()

    def load(self):  # type: ignore[no-untyped-def]
        """Return the current preference snapshot."""

        return self.preferences

    def save(self, preferences):  # type: ignore[no-untyped-def]
        """Persist one preference snapshot in memory."""

        self.preferences = preferences


class _NullDanbooruPreferenceRepository:
    """Return default Danbooru preferences for service bootstrapping."""

    def load(self):  # type: ignore[no-untyped-def]
        """Return the default Danbooru preferences."""

        return DanbooruPreferenceService(self).default_preferences()

    def save(self, preferences):  # type: ignore[no-untyped-def]
        """Ignore persisted writes from default bootstrapping."""


def test_recent_posts_service_scans_forward_until_it_fills_visible_slots(
    tmp_path: Path,
) -> None:
    """Service should fetch forward until it collects five allowed post ids."""

    client = _StubDanbooruRecentPostsClient(
        posts_by_request={
            ("head_tilt", None): (
                _post_record(post_id=10, rating="e"),
                _post_record(post_id=9, rating="q"),
                _post_record(post_id=8, rating="s"),
            ),
            ("head_tilt", 8): (
                _post_record(post_id=7, rating="s"),
                _post_record(post_id=6, rating="s"),
                _post_record(post_id=5, rating="s"),
                _post_record(post_id=4, rating="s"),
            ),
        }
    )
    service = _service(tmp_path, client=client)
    service._preference_service.set_allowed_image_ratings(
        DanbooruImageRatingPolicy.SAFE_ONLY
    )

    result = service.list_recent_visible_post_ids("head_tilt")

    assert result == (8, 7, 6, 5, 4)
    assert client.calls == [
        ("head_tilt", 10, None),
        ("head_tilt", 10, 8),
    ]


def test_recent_posts_service_reuses_cached_candidate_searches(tmp_path: Path) -> None:
    """Repeated lookups should reuse the cached candidate id set."""

    client = _StubDanbooruRecentPostsClient(
        posts_by_request={
            ("head_tilt", None): (
                _post_record(post_id=12, rating="s"),
                _post_record(post_id=11, rating="s"),
                _post_record(post_id=10, rating="s"),
                _post_record(post_id=9, rating="s"),
                _post_record(post_id=8, rating="s"),
            )
        }
    )
    service = _service(tmp_path, client=client)

    first = service.list_recent_visible_post_ids("head_tilt")
    second = service.list_recent_visible_post_ids("head_tilt")

    assert first == (12, 11, 10, 9, 8)
    assert second == first
    assert client.calls == [("head_tilt", 10, None)]


def _service(
    tmp_path: Path,
    *,
    client: _StubDanbooruRecentPostsClient,
) -> DanbooruRecentPostsService:
    """Create one cached recent-post service for tests."""

    preference_service = DanbooruPreferenceService(
        _MemoryDanbooruPreferenceRepository()
    )
    return DanbooruRecentPostsService(
        client=client,
        cache_repository=SqliteDanbooruCacheStore(tmp_path),
        preference_service=preference_service,
    )


def _post_record(*, post_id: int, rating: str) -> DanbooruPostRecord:
    """Return one representative Danbooru post record for recent-post tests."""

    return DanbooruPostRecord(
        post_id=post_id,
        created_at="2026-05-01T10:00:00.000-04:00",
        updated_at="2026-05-13T12:30:00.000-04:00",
        source=f"https://artist.example/post/{post_id}",
        md5=f"{post_id:032d}"[-32:],
        rating=rating,
        tag_string="1girl head_tilt smile",
        tag_string_general="1girl head_tilt smile",
        tag_string_artist="artist_name",
        tag_string_copyright="series_name",
        tag_string_character="heroine",
        tag_string_meta="commentary",
        file_url="https://cdn.donmai.us/original/example.jpg",
        large_file_url="https://cdn.donmai.us/sample/example.jpg",
        preview_file_url="https://cdn.donmai.us/180x180/example.jpg",
    )

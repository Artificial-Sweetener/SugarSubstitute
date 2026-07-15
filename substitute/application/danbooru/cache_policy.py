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

"""Define shared Danbooru cache TTLs and timestamp helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

WIKI_PAGE_CACHE_TTL = timedelta(days=7)
TAG_CACHE_TTL = timedelta(days=3)
POST_CACHE_TTL = timedelta(days=1)
RECENT_POST_SEARCH_CACHE_TTL = timedelta(hours=6)
NEGATIVE_LOOKUP_CACHE_TTL = timedelta(hours=6)
IMAGE_PREVIEW_CACHE_TTL = timedelta(days=30)


def current_utc_timestamp() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def current_utc_timestamp_text() -> str:
    """Return the current UTC timestamp in ISO-8601 text form."""

    return current_utc_timestamp().isoformat()


def expires_at_text(ttl: timedelta, *, now: datetime | None = None) -> str:
    """Return one ISO-8601 expiration timestamp for the supplied TTL."""

    resolved_now = current_utc_timestamp() if now is None else now
    return (resolved_now + ttl).isoformat()


def timestamp_is_expired(
    expires_at: str,
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether one ISO-8601 expiration timestamp has elapsed."""

    resolved_now = current_utc_timestamp() if now is None else now
    try:
        expiration = datetime.fromisoformat(expires_at)
    except ValueError:
        return True
    return expiration <= resolved_now


def fetched_timestamp_is_stale(
    fetched_at: str,
    *,
    ttl: timedelta,
    now: datetime | None = None,
) -> bool:
    """Return whether one fetched-at timestamp is older than the supplied TTL."""

    resolved_now = current_utc_timestamp() if now is None else now
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError:
        return True
    return fetched + ttl <= resolved_now


__all__ = [
    "IMAGE_PREVIEW_CACHE_TTL",
    "NEGATIVE_LOOKUP_CACHE_TTL",
    "POST_CACHE_TTL",
    "RECENT_POST_SEARCH_CACHE_TTL",
    "TAG_CACHE_TTL",
    "WIKI_PAGE_CACHE_TTL",
    "current_utc_timestamp",
    "current_utc_timestamp_text",
    "expires_at_text",
    "fetched_timestamp_is_stale",
    "timestamp_is_expired",
]

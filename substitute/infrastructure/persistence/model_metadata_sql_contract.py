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

"""Define model metadata SQLite schema and scalar encoding contracts."""

from __future__ import annotations

import json
from typing import cast

from substitute.domain.common import JsonObject


def dump_json(value: object) -> str:
    """Return compact deterministic JSON for SQLite JSON columns."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def json_object(value: object) -> JsonObject:
    """Return a JSON object from a SQLite JSON column."""

    parsed = _load_json(value)
    return cast(JsonObject, parsed if isinstance(parsed, dict) else {})


def optional_json_object(value: object) -> JsonObject | None:
    """Return a JSON object or ``None`` from a SQLite JSON column."""

    parsed = _load_json(value)
    return cast(JsonObject | None, parsed if isinstance(parsed, dict) else None)


def json_str_tuple(value: object) -> tuple[str, ...]:
    """Return string entries from a SQLite JSON array column."""

    parsed = _load_json(value)
    if not isinstance(parsed, list):
        return ()
    return tuple(item for item in parsed if isinstance(item, str))


def json_optional_str_int(value: object) -> str | int | None:
    """Return a decoded optional string or integer scalar from JSON text."""

    parsed = _load_json(value)
    if isinstance(parsed, bool):
        return None
    return parsed if isinstance(parsed, str | int) else None


def optional_bool_to_int(value: bool | None) -> int | None:
    """Encode an optional boolean as a SQLite integer."""

    return None if value is None else int(value)


def optional_bool_from_int(value: object) -> bool | None:
    """Decode an optional SQLite integer boolean."""

    return None if value is None else bool(value)


def optional_int(value: object) -> int | None:
    """Return an integer from SQLite when present."""

    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str | bytes | bytearray):
        return int(value)
    raise TypeError(f"Expected integer-compatible SQLite value, got {type(value)!r}.")


def optional_float(value: object) -> float | None:
    """Return a float from SQLite when present."""

    if value is None:
        return None
    if isinstance(value, int | float | str | bytes | bytearray):
        return float(value)
    raise TypeError(f"Expected float-compatible SQLite value, got {type(value)!r}.")


def optional_str(value: object) -> str | None:
    """Return a string from SQLite when present."""

    return value if isinstance(value, str) else None


def _load_json(value: object) -> object:
    """Return JSON-decoded SQLite text, or ``None`` for absent values."""

    return json.loads(value) if isinstance(value, str) else None


SCHEMA_SQL = """
create table if not exists metadata_schema (
  key text primary key,
  value text not null
);

create table if not exists model_metadata_records (
  sha256 text primary key,
  target_id text not null,
  root_id text not null,
  relative_path text not null,
  kind text not null,
  backend_value text not null,
  display_name text not null,
  size_bytes integer not null,
  modified_at text not null,
  provider text not null default 'civitai',
  provider_status text not null,
  thumbnail_status text not null,
  thumbnail_policy text not null,
  thumbnail_policy_version integer not null,
  schema_version integer not null,
  updated_at text not null
);

create table if not exists civitai_model_versions (
  sha256 text primary key references model_metadata_records(sha256) on delete cascade,
  model_id integer,
  model_version_id integer,
  model_name text,
  model_type text,
  version_name text,
  base_model text,
  trained_words_json text not null,
  tags_json text not null,
  description text,
  version_description text,
  creator_username text,
  creator_image text,
  nsfw integer,
  nsfw_level text,
  availability text,
  stats_json text not null,
  model_page_url text,
  source_url text,
  fetched_at text,
  raw_provider_payload_json text not null
);

create table if not exists civitai_files (
  id integer primary key autoincrement,
  sha256 text not null references model_metadata_records(sha256) on delete cascade,
  file_id integer,
  name text not null,
  size_kb real,
  primary_file integer not null,
  hashes_json text not null,
  metadata_json text not null
);

create table if not exists civitai_images (
  id integer primary key autoincrement,
  sha256 text not null references model_metadata_records(sha256) on delete cascade,
  image_id integer,
  url text not null,
  image_type text,
  nsfw integer,
  nsfw_level text,
  width integer,
  height integer,
  meta_json text,
  sort_index integer not null
);

create index if not exists idx_model_metadata_kind
  on model_metadata_records(kind);
create index if not exists idx_model_metadata_relative_path
  on model_metadata_records(relative_path);
create index if not exists idx_model_metadata_kind_relative_path
  on model_metadata_records(kind, relative_path);
create index if not exists idx_civitai_model_base_model
  on civitai_model_versions(base_model);
create index if not exists idx_civitai_files_sha256
  on civitai_files(sha256);
create index if not exists idx_civitai_images_sha256
  on civitai_images(sha256, sort_index);
"""


__all__ = [
    "SCHEMA_SQL",
    "dump_json",
    "json_object",
    "json_optional_str_int",
    "json_str_tuple",
    "optional_bool_from_int",
    "optional_bool_to_int",
    "optional_float",
    "optional_int",
    "optional_json_object",
    "optional_str",
]

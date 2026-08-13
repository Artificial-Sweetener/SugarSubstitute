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

"""Reconstruct normalized CivitAI provider records from SQLite rows."""

from __future__ import annotations

import sqlite3

from substitute.domain.model_metadata import (
    CivitaiFile,
    CivitaiImage,
    CivitaiModelVersion,
)
from substitute.infrastructure.persistence.model_metadata_sql_contract import (
    json_object,
    json_optional_str_int,
    json_str_tuple,
    optional_bool_from_int,
    optional_float,
    optional_int,
    optional_json_object,
    optional_str,
)


def read_provider(
    connection: sqlite3.Connection,
    sha256: str,
) -> CivitaiModelVersion | None:
    """Reconstruct normalized CivitAI metadata for one SHA256 key."""

    row = connection.execute(
        "select * from civitai_model_versions where sha256 = ?",
        (sha256,),
    ).fetchone()
    if row is None:
        return None
    files = tuple(
        CivitaiFile(
            file_id=optional_int(file_row["file_id"]),
            name=str(file_row["name"]),
            size_kb=optional_float(file_row["size_kb"]),
            file_type=None,
            download_url=None,
            pickle_scan_result=None,
            virus_scan_result=None,
            primary=bool(file_row["primary_file"]),
            hashes=json_object(file_row["hashes_json"]),
            metadata=json_object(file_row["metadata_json"]),
        )
        for file_row in connection.execute(
            "select * from civitai_files where sha256 = ? order by id",
            (sha256,),
        ).fetchall()
    )
    images = tuple(
        CivitaiImage(
            image_id=optional_int(image_row["image_id"]),
            url=str(image_row["url"]),
            image_type=optional_str(image_row["image_type"]),
            nsfw=optional_bool_from_int(image_row["nsfw"]),
            nsfw_level=json_optional_str_int(image_row["nsfw_level"]),
            width=optional_int(image_row["width"]),
            height=optional_int(image_row["height"]),
            meta=optional_json_object(image_row["meta_json"]),
        )
        for image_row in connection.execute(
            """
            select *
            from civitai_images
            where sha256 = ?
            order by sort_index
            """,
            (sha256,),
        ).fetchall()
    )
    return CivitaiModelVersion(
        model_id=int(row["model_id"]),
        model_version_id=int(row["model_version_id"]),
        model_name=str(row["model_name"]),
        model_type=optional_str(row["model_type"]),
        version_name=str(row["version_name"]),
        base_model=optional_str(row["base_model"]),
        trained_words=json_str_tuple(row["trained_words_json"]),
        description=optional_str(row["description"]),
        version_description=optional_str(row["version_description"]),
        tags=json_str_tuple(row["tags_json"]),
        creator_username=optional_str(row["creator_username"]),
        creator_image=optional_str(row["creator_image"]),
        nsfw=optional_bool_from_int(row["nsfw"]),
        nsfw_level=json_optional_str_int(row["nsfw_level"]),
        availability=optional_str(row["availability"]),
        files=files,
        images=images,
        stats=json_object(row["stats_json"]),
        model_page_url=str(row["model_page_url"]),
        source_url=str(row["source_url"]),
        fetched_at=str(row["fetched_at"]),
        raw_provider_payload=json_object(row["raw_provider_payload_json"]),
    )


__all__ = ["read_provider"]

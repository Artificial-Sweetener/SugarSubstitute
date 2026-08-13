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

"""Define stable identifiers for governed persistent cache owners."""

CACHE_ID_RESTORE_PROJECTION = "restore-projection"
CACHE_ID_CUBE_ICONS = "cube-icons"
CACHE_ID_CUBE_CLASSIFICATIONS = "cube-classifications"
CACHE_ID_COMFY_I18N = "comfy-i18n"
CACHE_ID_DANBOORU_METADATA = "danbooru-metadata"
CACHE_ID_DANBOORU_IMAGES = "danbooru-images"
CACHE_ID_MODEL_METADATA = "model-metadata"
CACHE_ID_MODEL_THUMBNAILS = "model-thumbnails"
CACHE_ID_MODEL_CATALOG_SNAPSHOTS = "model-catalog-snapshots"

__all__ = [
    "CACHE_ID_COMFY_I18N",
    "CACHE_ID_CUBE_CLASSIFICATIONS",
    "CACHE_ID_CUBE_ICONS",
    "CACHE_ID_DANBOORU_IMAGES",
    "CACHE_ID_DANBOORU_METADATA",
    "CACHE_ID_MODEL_CATALOG_SNAPSHOTS",
    "CACHE_ID_MODEL_METADATA",
    "CACHE_ID_MODEL_THUMBNAILS",
    "CACHE_ID_RESTORE_PROJECTION",
]

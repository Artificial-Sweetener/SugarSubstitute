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

"""Enrich authoritative Ultralytics choices with packaged detector visuals."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath
import re

from substitute.application.model_metadata.model_catalog_service import (
    ModelThumbnailVariant,
)
from substitute.application.model_metadata.rich_choice_models import (
    RichChoiceItem,
    RichChoiceResolution,
)
from substitute.domain.model_metadata import BANNER_THUMBNAIL_ROLE

ULTRALYTICS_MODEL_KIND = "ultralytics"
BUNDLED_ULTRALYTICS_STORAGE_PREFIX = "bundled:ultralytics:"
BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX = "bundled:ultralytics-banner:"
_THUMBNAIL_SIZE = 512
_THUMBNAIL_PAYLOAD_BYTES = _THUMBNAIL_SIZE * _THUMBNAIL_SIZE * 4
_DOWNLOAD_SIZE_SUFFIX = re.compile(r"\s+\([0-9.]+\s*MB\)\s*$", re.IGNORECASE)
_YOLO_TOKEN = re.compile(r"\byolo(?=v?\d)", re.IGNORECASE)

_CURATED_ASSETS = {
    "anzhc face -seg": "face-segmentation",
    "anzhc face seg 640 v2 y8n": "face-segmentation",
    "anzhc face seg 768 v2 y8n": "face-segmentation",
    "anzhc face seg 768ms v2 y8n": "face-segmentation",
    "anzhc face seg 1024 v2 y8n": "face-segmentation",
    "anzhc face seg 640 v3 y11n": "face-segmentation",
    "anzhc face seg 640 v4 y11n": "face-segmentation",
    "anzhcs manface v02 1024 y8n": "male-face-segmentation",
    "anzhcs womanface v05 1024 y8n": "female-face-segmentation",
    "anzhc eyes -seg-hd": "eyes-segmentation",
    "anzhc headhair seg y8n": "hair-segmentation",
    "anzhc headhair seg y8m": "hair-segmentation",
    "anzhc breasts seg v1 1024n": "breast-segmentation",
    "anzhc breasts seg v1 1024s": "breast-segmentation",
    "anzhc breasts seg v1 1024m": "breast-segmentation",
    "bingsu face yolov8n v2": "face-detection",
    "bingsu face yolov8s": "face-detection",
    "bingsu hand yolov8n": "hand-detection",
    "bingsu hand yolov8s": "hand-detection",
    "bingsu person yolov8n-seg": "person-segmentation",
    "bingsu person yolov8s-seg": "person-segmentation",
    "fuyucchi yolov8x6 anime face": "anime-face-detection",
}
_ASSET_NAMES = frozenset(
    {
        "anime-face-detection",
        "anime-face-segmentation",
        "breast-detection",
        "breast-segmentation",
        "eyes-detection",
        "eyes-segmentation",
        "face-detection",
        "face-segmentation",
        "female-face-detection",
        "female-face-segmentation",
        "hair-detection",
        "hair-segmentation",
        "hand-detection",
        "hand-segmentation",
        "male-face-detection",
        "male-face-segmentation",
        "person-segmentation",
    }
)


class BundledUltralyticsThumbnailMode(StrEnum):
    """Identify how one packaged detector visual represents its subject."""

    BOUNDING_BOX = "bounding_box"
    SEGMENTATION = "segmentation"


@dataclass(frozen=True, slots=True)
class BundledUltralyticsThumbnailChoice:
    """Describe one user-selectable packaged detector thumbnail."""

    asset_name: str
    title: str
    mode: BundledUltralyticsThumbnailMode
    thumbnail_variants: tuple[ModelThumbnailVariant, ...]


def bundled_ultralytics_asset_names() -> tuple[str, ...]:
    """Return the complete packaged Ultralytics asset inventory."""

    return tuple(sorted(_ASSET_NAMES))


def bundled_ultralytics_thumbnail_choices() -> tuple[
    BundledUltralyticsThumbnailChoice, ...
]:
    """Return the complete visual library in stable display order."""

    return tuple(
        BundledUltralyticsThumbnailChoice(
            asset_name=asset_name,
            title=_asset_title(asset_name),
            mode=(
                BundledUltralyticsThumbnailMode.SEGMENTATION
                if asset_name.endswith("-segmentation")
                else BundledUltralyticsThumbnailMode.BOUNDING_BOX
            ),
            thumbnail_variants=_thumbnail_variants(asset_name),
        )
        for asset_name in sorted(_ASSET_NAMES, key=_asset_sort_key)
    )


def ultralytics_visual_resolution(
    options: tuple[str, ...],
    *,
    thumbnail_associations: Mapping[str, str] | None = None,
) -> RichChoiceResolution:
    """Return picker rows enriched without changing the selectable values."""

    associations = thumbnail_associations or {}
    items = tuple(_choice_item(option, associations) for option in options)
    enriched_count = sum(bool(item.thumbnail_variants) for item in items)
    return RichChoiceResolution(
        items=items,
        should_use_rich_picker=True,
        matched_kinds=(ULTRALYTICS_MODEL_KIND,),
        option_count=len(items),
        enriched_count=enriched_count,
        ambiguous_count=0,
        unmatched_count=len(items) - enriched_count,
        reason="authoritative Ultralytics field with bundled visual enrichment",
    )


def _choice_item(
    value: str,
    thumbnail_associations: Mapping[str, str],
) -> RichChoiceItem:
    """Build one exact-value picker row with best-effort visual enrichment."""

    title = _friendly_title(value)
    selected_asset = thumbnail_associations.get(value)
    asset_name = (
        selected_asset
        if selected_asset in _ASSET_NAMES
        else _asset_name_for_value(value)
    )
    variants = _thumbnail_variants(asset_name) if asset_name is not None else ()
    search_parts = (value, title, asset_name or "")
    return RichChoiceItem(
        value=value,
        title=title,
        subtitle=None,
        search_text=" ".join(search_parts).replace("\\", "/").casefold(),
        model_kind=ULTRALYTICS_MODEL_KIND,
        catalog_item=None,
        thumbnail_variants=variants,
        is_enriched=bool(variants),
        is_ambiguous=False,
    )


def _asset_name_for_value(value: str) -> str | None:
    """Resolve a curated label or conventional detector filename to one visual."""

    normalized = _normalized_value(value)
    curated = _CURATED_ASSETS.get(normalized)
    if curated is not None:
        return curated

    is_segmentation = _is_segmentation_value(normalized)
    suffix = "segmentation" if is_segmentation else "detection"
    if "anime" in normalized and "face" in normalized:
        subject = "anime-face"
    elif "womanface" in normalized or "female" in normalized:
        subject = "female-face"
    elif "manface" in normalized or "male" in normalized:
        subject = "male-face"
    elif "headhair" in normalized or "head+hair" in normalized or "hair" in normalized:
        subject = "hair"
    elif "eyes" in normalized or "eye" in normalized:
        subject = "eyes"
    elif "breast" in normalized:
        subject = "breast"
    elif "hand" in normalized:
        subject = "hand"
    elif "person" in normalized:
        subject = "person"
    elif "face" in normalized:
        subject = "face"
    else:
        return None

    asset_name = f"{subject}-{suffix}"
    if asset_name in _ASSET_NAMES:
        return asset_name
    if subject == "person":
        return "person-segmentation"
    return None


def _normalized_value(value: str) -> str:
    """Return a stable matching key without a display-only download size."""

    normalized = value.strip().replace("\\", "/").casefold()
    return _DOWNLOAD_SIZE_SUFFIX.sub("", normalized)


def _is_segmentation_value(normalized: str) -> bool:
    """Return whether a choice names or resides in a segmentation model route."""

    return (
        normalized.startswith("segm/")
        or "/segm/" in normalized
        or "segment" in normalized
        or "-seg" in normalized
        or "_seg" in normalized
        or " seg" in normalized
    )


def _friendly_title(value: str) -> str:
    """Return a path-free title while preserving the model author's name."""

    normalized = value.strip().replace("\\", "/")
    basename = PurePosixPath(normalized).name
    for suffix in (".safetensors", ".ckpt", ".pt"):
        if basename.casefold().endswith(suffix):
            basename = basename[: -len(suffix)]
            break
    title = _DOWNLOAD_SIZE_SUFFIX.sub("", basename).strip()
    title = " ".join(title.replace("_", " ").split())
    title = _YOLO_TOKEN.sub("YOLO", title)
    if title and title[0].islower():
        title = title[0].upper() + title[1:]
    return title or value


def _asset_title(asset_name: str) -> str:
    """Return a concise human title for one packaged detector visual."""

    subject = asset_name.rsplit("-", 1)[0]
    words = subject.replace("-", " ").split()
    return " ".join(word.capitalize() for word in words)


def _asset_sort_key(asset_name: str) -> tuple[str, int]:
    """Group matching detection and segmentation visuals together."""

    subject, mode = asset_name.rsplit("-", 1)
    return subject, 0 if mode == "detection" else 1


def _thumbnail_variants(asset_name: str) -> tuple[ModelThumbnailVariant, ...]:
    """Return grid and closed-picker roles for one packaged visual."""

    standard = ModelThumbnailVariant(
        size=_THUMBNAIL_SIZE,
        storage_key=f"{BUNDLED_ULTRALYTICS_STORAGE_PREFIX}{asset_name}",
        width=_THUMBNAIL_SIZE,
        height=_THUMBNAIL_SIZE,
        content_format="bundled-ultralytics-png",
        byte_size=_THUMBNAIL_PAYLOAD_BYTES,
    )
    banner = ModelThumbnailVariant(
        size=_THUMBNAIL_SIZE,
        storage_key=f"{BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX}{asset_name}",
        width=standard.width,
        height=standard.height,
        content_format=standard.content_format,
        byte_size=standard.byte_size,
        role=BANNER_THUMBNAIL_ROLE,
    )
    return standard, banner


__all__ = [
    "BUNDLED_ULTRALYTICS_BANNER_STORAGE_PREFIX",
    "BUNDLED_ULTRALYTICS_STORAGE_PREFIX",
    "BundledUltralyticsThumbnailChoice",
    "BundledUltralyticsThumbnailMode",
    "ULTRALYTICS_MODEL_KIND",
    "bundled_ultralytics_asset_names",
    "bundled_ultralytics_thumbnail_choices",
    "ultralytics_visual_resolution",
]

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

"""Verify deterministic Ultralytics visual enrichment."""

from __future__ import annotations

from substitute.application.model_metadata.ultralytics_visual_catalog import (
    ultralytics_visual_resolution,
)

_SIMPLE_SYRUP_CURATED_CHOICES = (
    "Anzhc Face -seg (6.52MB)",
    "Anzhc Face seg 640 v2 y8n (6.56MB)",
    "Anzhc Face seg 768 v2 y8n (6.58MB)",
    "Anzhc Face seg 768MS v2 y8n (6.60MB)",
    "Anzhc Face seg 1024 v2 y8n (6.63MB)",
    "Anzhc Face seg 640 v3 y11n (5.80MB)",
    "Anzhc Face seg 640 v4 y11n (5.74MB)",
    "Anzhcs ManFace v02 1024 y8n (6.06MB)",
    "Anzhcs WomanFace v05 1024 y8n (6.07MB)",
    "Anzhc Eyes -seg-hd (6.59MB)",
    "Anzhc HeadHair seg y8n (6.50MB)",
    "Anzhc HeadHair seg y8m (52.34MB)",
    "Anzhc Breasts Seg v1 1024n (6.58MB)",
    "Anzhc Breasts Seg v1 1024s (22.86MB)",
    "Anzhc Breasts Seg v1 1024m (52.39MB)",
    "Bingsu Face YOLOv8n v2 (6.23MB)",
    "Bingsu Face YOLOv8s (22.5MB)",
    "Bingsu Hand YOLOv8n (6.23MB)",
    "Bingsu Hand YOLOv8s (22.5MB)",
    "Bingsu Person YOLOv8n-seg (6.78MB)",
    "Bingsu Person YOLOv8s-seg (23.9MB)",
    "Fuyucchi YOLOv8x6 Anime Face (195MB)",
)


def test_every_simplesyrup_curated_choice_has_a_bundled_visual() -> None:
    """Keep explicit coverage aligned with SimpleSyrup's downloadable catalog."""

    resolution = ultralytics_visual_resolution(_SIMPLE_SYRUP_CURATED_CHOICES)

    assert resolution.enriched_count == len(_SIMPLE_SYRUP_CURATED_CHOICES)
    assert resolution.unmatched_count == 0
    assert all(len(item.thumbnail_variants) == 2 for item in resolution.items)
    assert all(
        {variant.role for variant in item.thumbnail_variants} == {"standard", "banner"}
        for item in resolution.items
    )
    assert resolution.items[0].title == "Anzhc Face -seg"


def test_similar_model_variants_deliberately_share_visuals() -> None:
    """Model-size variants should share the visual for their detector purpose."""

    resolution = ultralytics_visual_resolution(
        (
            "Anzhc Face seg 640 v2 y8n (6.56MB)",
            "Anzhc Face seg 1024 v2 y8n (6.63MB)",
            "Bingsu Hand YOLOv8n (6.23MB)",
            "Bingsu Hand YOLOv8s (22.5MB)",
        )
    )

    storage_keys = [item.thumbnail_variants[0].storage_key for item in resolution.items]
    assert storage_keys[0] == storage_keys[1]
    assert storage_keys[2] == storage_keys[3]
    assert storage_keys[0] != storage_keys[2]


def test_installed_bbox_and_segmentation_paths_use_modality_aware_visuals() -> None:
    """Conventional local paths should select bbox or segmentation imagery."""

    resolution = ultralytics_visual_resolution(
        (
            "bbox/face_yolov8n.pt",
            "segm/face_yolov8n-seg.pt",
            "bbox/hand_yolov8s.pt",
            "segm/person_yolov8m-seg.pt",
            "bbox/custom_unknown_detector.pt",
        )
    )

    keys = [
        (item.thumbnail_variants[0].storage_key if item.thumbnail_variants else None)
        for item in resolution.items
    ]
    assert keys == [
        "bundled:ultralytics:face-detection",
        "bundled:ultralytics:face-segmentation",
        "bundled:ultralytics:hand-detection",
        "bundled:ultralytics:person-segmentation",
        None,
    ]
    assert [item.value for item in resolution.items] == [
        "bbox/face_yolov8n.pt",
        "segm/face_yolov8n-seg.pt",
        "bbox/hand_yolov8s.pt",
        "segm/person_yolov8m-seg.pt",
        "bbox/custom_unknown_detector.pt",
    ]
    assert [item.title for item in resolution.items] == [
        "Face YOLOv8n",
        "Face YOLOv8n-seg",
        "Hand YOLOv8s",
        "Person YOLOv8m-seg",
        "Custom unknown detector",
    ]

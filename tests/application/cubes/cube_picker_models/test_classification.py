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

#    SugarSubsti

from .support import (
    CubeSearchTerm,
    classify_cube_document,
)


def test_classify_cube_document_derives_roles_from_current_cube_boundaries() -> None:
    """Picker roles should be derived locally from loaded cube documents."""

    assert (
        classify_cube_document(
            {"implementation": {"inputs": {}, "outputs": {"image": {}}}}
        ).role
        == "start"
    )
    assert (
        classify_cube_document(
            {"implementation": {"inputs": {"image": {}}, "outputs": {"image": {}}}}
        ).role
        == "middle"
    )
    assert (
        classify_cube_document(
            {"implementation": {"inputs": {"image": {}}, "outputs": {}}}
        ).role
        == "end"
    )


def test_classify_cube_document_reads_supported_model_metadata() -> None:
    """Picker classifications should include cube-supported model claims."""

    classification = classify_cube_document(
        {
            "metadata": {"supported_models": [" SDXL 1.0 ", "", "sdxl 1.0"]},
            "implementation": {"inputs": {"image": {}}, "outputs": {"image": {}}},
        }
    )

    assert classification.supported_models == ("SDXL 1.0",)


def test_classify_cube_document_indexes_node_metadata_for_search() -> None:
    """Picker classifications should expose loaded cube node terms for search."""

    classification = classify_cube_document(
        {
            "implementation": {
                "nodes": {
                    "bbox_detector": {
                        "class_type": "UltralyticsDetectorProvider",
                        "inputs": {},
                    }
                },
                "inputs": {"image": {}},
                "outputs": {"image": {}},
                "definitions": {
                    "UltralyticsDetectorProvider": {
                        "display_name": "Ultralytics Detector Provider",
                        "category": "detection",
                    }
                },
                "layout": {
                    "nodes": {
                        "bbox_detector": {
                            "class_type": "UltralyticsDetectorProvider",
                            "title": "bbox detector",
                        }
                    }
                },
            },
            "surface": {
                "controls": [
                    {
                        "control_id": "bbox_detector.model_name",
                        "symbol": "bbox_detector",
                        "input_name": "model_name",
                        "class_type": "UltralyticsDetectorProvider",
                    }
                ]
            },
        }
    )

    assert "UltralyticsDetectorProvider" in classification.search_terms
    assert "Ultralytics Detector Provider" in classification.search_terms
    assert "bbox detector" in classification.search_terms
    assert "bbox_detector.model_name" in classification.search_terms
    assert CubeSearchTerm("UltralyticsDetectorProvider", "node") in (
        classification.search_targets
    )
    assert CubeSearchTerm("Ultralytics Detector Provider", "definition") in (
        classification.search_targets
    )
    assert CubeSearchTerm("bbox_detector.model_name", "control") in (
        classification.search_targets
    )

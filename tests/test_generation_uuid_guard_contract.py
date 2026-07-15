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

from substitute.application.generation import find_unresolved_uuid_class_types


def test_find_unresolved_uuid_class_types_detects_wrapper_nodes():
    workflow = {
        "0": {"class_type": "KSampler", "inputs": {}},
        "1": {
            "class_type": "94f725d5-39bf-4060-be68-f573214a2055",
            "inputs": {},
        },
        "2": {
            "class_type": "94f725d5-39bf-4060-be68-f573214a2055",
            "inputs": {},
        },
    }

    unresolved = find_unresolved_uuid_class_types(workflow)

    assert unresolved == ["94f725d5-39bf-4060-be68-f573214a2055"]


def test_find_unresolved_uuid_class_types_ignores_non_uuid_classes():
    workflow = {
        "0": {"class_type": "KSampler", "inputs": {}},
        "1": {"class_type": "not-a-uuid", "inputs": {}},
    }

    unresolved = find_unresolved_uuid_class_types(workflow)

    assert unresolved == []

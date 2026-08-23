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

"""Tests for backend model-catalog change-event parsing."""

from __future__ import annotations

from substitute.domain.model_metadata import parse_backend_model_catalog_change_event


def test_parse_backend_model_catalog_change_event_accepts_valid_payload() -> None:
    """Accept a supported backend model-catalog change-event payload."""

    event = parse_backend_model_catalog_change_event(_event_payload())

    assert event is not None
    assert event.revision == "rev2"
    assert event.kinds == ("loras",)
    assert event.affected_node_classes == ("LoraLoader",)
    assert event.added[0].source.relative_path == "style.safetensors"
    assert event.enrichable_entries == event.added


def test_parse_backend_model_catalog_change_event_rejects_bad_schema() -> None:
    """Reject unsupported schemas instead of partially parsing them."""

    payload = _event_payload()
    payload["schemaVersion"] = 2

    assert parse_backend_model_catalog_change_event(payload) is None


def _event_payload() -> dict[str, object]:
    """Build one supported backend model-catalog event payload."""

    return {
        "schemaVersion": 1,
        "revision": "rev2",
        "previousRevision": "rev1",
        "generatedAt": "2026-05-26T12:00:01Z",
        "reason": "folder-changed",
        "kinds": ["loras"],
        "affectedNodeClasses": ["LoraLoader"],
        "added": [_entry_payload("style.safetensors")],
        "removed": [],
        "modified": [],
    }


def _entry_payload(value: str) -> dict[str, object]:
    """Build one changed-entry payload."""

    return {
        "kind": "loras",
        "value": value,
        "source": {"rootId": "loras:0", "relativePath": value},
        "file": {"sizeBytes": 123, "modifiedAt": "2026-05-26T12:00:00Z"},
    }

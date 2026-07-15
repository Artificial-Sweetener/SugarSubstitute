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

"""Normalize Comfy queue response entries under one infrastructure owner."""

from __future__ import annotations


def extract_prompt_ids(entries: object) -> tuple[str, ...]:
    """Extract prompt identifiers from supported Comfy queue entry shapes."""

    if not isinstance(entries, list):
        return ()
    prompt_ids: list[str] = []
    for entry in entries:
        prompt_id = _entry_prompt_id(entry)
        if prompt_id is not None:
            prompt_ids.append(prompt_id)
    return tuple(prompt_ids)


def queue_prompt_ids(payload: dict[str, object]) -> set[str]:
    """Return every running or pending prompt identifier in a queue payload."""

    return {
        *extract_prompt_ids(payload.get("queue_running")),
        *extract_prompt_ids(payload.get("queue_pending")),
    }


def _entry_prompt_id(entry: object) -> str | None:
    """Return one prompt id from mapping or tuple-style queue entries."""

    if isinstance(entry, dict):
        prompt_id = entry.get("prompt_id")
        return prompt_id if isinstance(prompt_id, str) else None
    if not isinstance(entry, (list, tuple)):
        return None
    for candidate in entry[:2]:
        if isinstance(candidate, str):
            return candidate
    return None


__all__ = ["extract_prompt_ids", "queue_prompt_ids"]

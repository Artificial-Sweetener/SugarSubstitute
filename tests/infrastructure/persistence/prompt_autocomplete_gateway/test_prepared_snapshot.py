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

"""Contracts for prepared prompt autocomplete gateway snapshots."""

from __future__ import annotations


import pytest

from substitute.infrastructure.persistence.file_prompt_autocomplete_gateway import (
    FilePromptAutocompleteGateway,
)


def test_prepared_gateway_snapshot_never_loads_on_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep exact-tag reads on interactive paths free from asset I/O."""

    gateway = FilePromptAutocompleteGateway()

    def fail_load() -> object:
        raise AssertionError("prepared snapshot attempted asset I/O")

    monkeypatch.setattr(gateway, "_load_rows", fail_load)

    assert gateway.prepared_prompt_tag_snapshot().normalized_tags == frozenset()

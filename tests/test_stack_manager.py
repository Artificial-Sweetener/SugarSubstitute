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

"""Characterization tests for stack manager alias and ordering behavior."""

from substitute.domain.workflow import StackManager


def test_resolve_unique_alias_spans_all_loaded_cube_bases() -> None:
    """Alias uniqueness should be enforced across the whole workflow namespace."""
    manager = StackManager()

    assert manager.resolve_unique_alias("Shared") == "Shared"

    manager.add_cube("cube_a", "Shared", {"nodes": {}})
    assert manager.resolve_unique_alias("Shared") == "Shared 2"

    manager.add_cube("cube_b", "Shared 2", {"nodes": {}})
    assert manager.resolve_unique_alias("Shared") == "Shared 3"


def test_resolve_unique_alias_reuses_suffix_gaps_for_unsuffixed_seed() -> None:
    """Unsuffixed alias requests should fill the first available numeric gap."""
    manager = StackManager()
    manager.add_cube("cube_a", "Shared", {"nodes": {}})
    manager.add_cube("cube_b", "Shared 3", {"nodes": {}})

    assert manager.resolve_unique_alias("Shared") == "Shared 2"


def test_resolve_unique_alias_preserves_requested_numeric_series_on_collision() -> None:
    """Suffixed alias requests should continue that visible numbering series."""
    manager = StackManager()
    manager.add_cube("cube_a", "Shared 2", {"nodes": {}})
    manager.add_cube("cube_b", "Shared 3", {"nodes": {}})

    assert manager.resolve_unique_alias("Shared 2") == "Shared 4"


def test_rename_cube_updates_all_state_collections() -> None:
    """Rename updates aliases, loaded cubes, and stack order together."""
    manager = StackManager()
    manager.add_cube("A", "A", {"a": 1})
    manager.add_cube("B", "B", {"b": 2})

    manager.rename_cube("A", "A-renamed")

    assert "A" not in manager.cube_aliases
    assert "A-renamed" in manager.cube_aliases
    assert "A" not in manager.loaded_cubes
    assert "A-renamed" in manager.loaded_cubes
    assert manager.stack_order == ["A-renamed", "B"]


def test_move_cube_out_of_bounds_is_noop() -> None:
    """Out-of-bounds moves leave stack order unchanged."""
    manager = StackManager()
    manager.add_cube("A", "A", {})
    manager.add_cube("B", "B", {})
    manager.add_cube("C", "C", {})
    original = list(manager.stack_order)

    manager.move_cube(-1, 0)
    manager.move_cube(0, 9)
    manager.move_cube(9, 0)

    assert manager.stack_order == original


def test_to_dict_roundtrip_preserves_state() -> None:
    """Serialize and deserialize stack manager state losslessly."""
    manager = StackManager()
    manager.add_cube("Text to Image", "T2I", {"nodes": {"n1": {}}})
    manager.add_cube("Upscale", "Upscale 2", {"nodes": {"n2": {}}})

    dumped = manager.to_dict()
    restored = StackManager.from_dict(dumped)

    assert restored.get_state() == manager.get_state()

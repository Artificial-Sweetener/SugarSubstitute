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

"""Verify sampler and scheduler linked-choice factory behavior."""

from __future__ import annotations

from __future__ import annotations
from types import SimpleNamespace
import pytest
from substitute.application.overrides import ChoiceLinkTarget
import substitute.presentation.editor.panel.factories.meta_factories as meta_factories

from .link_test_support import (
    _FakeComboBox,
    _FakeNodeDefinitionGateway,
    _Buffers,
    _field_state,
    configure_localized_combo_items,
)


def test_sampler_scheduler_factories_remain_on_shared_combo_box(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sampler and scheduler link widgets should not switch to the specialized subclass."""

    configure_localized_combo_items(monkeypatch)

    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {
                        "required": {
                            "sampler_name": [["euler", "heun"]],
                            "scheduler": [["normal", "karras"]],
                        }
                    }
                }
            }
        }
    )

    sampler_combo = _FakeComboBox()
    scheduler_combo = _FakeComboBox()
    buffers: _Buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {"sampler_name": "euler", "scheduler": "normal"},
                    "sampler_links": [],
                    "scheduler_links": [],
                }
            }
        }
    }

    meta_factories.setup_sampler_link_combobox(
        parent=SimpleNamespace(),
        sampler_link_widgets={("B", "sampler"): sampler_combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="sampler_name",
            link_key="sampler_link",
            literal_options=("euler", "heun"),
        ),
    )
    meta_factories.setup_scheduler_link_combobox(
        parent=SimpleNamespace(),
        scheduler_link_widgets={("B", "sampler"): scheduler_combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="scheduler",
            link_key="scheduler_link",
            literal_options=("normal", "karras"),
        ),
    )

    assert type(sampler_combo) is _FakeComboBox
    assert type(scheduler_combo) is _FakeComboBox


def test_setup_sampler_link_combobox_resets_stale_link_to_first_literal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sampler combobox should fall back to first literal option when link is stale."""

    configure_localized_combo_items(monkeypatch)
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {"required": {"sampler_name": [["euler", "heun"]]}}
                }
            }
        }
    )

    combo = _FakeComboBox()
    buffers: _Buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {"sampler_name": "invalid"},
                    "sampler_links": [
                        {"from_cube": "A", "from_node": "ksampler", "label": "link:A"}
                    ],
                    "sampler_link": {"from_cube": "A", "from_node": "missing"},
                }
            }
        }
    }

    meta_factories.setup_sampler_link_combobox(
        parent=SimpleNamespace(),
        sampler_link_widgets={("B", "sampler"): combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="sampler_name",
            link_key="sampler_link",
            literal_options=("euler", "heun"),
            link_targets=(
                ChoiceLinkTarget(
                    from_cube="A",
                    from_node="ksampler",
                    label="link:A",
                ),
            ),
        ),
    )

    assert combo.items == ["link:A", "euler", "heun"]
    assert combo.current_text == "euler"
    assert buffers["B"]["nodes"]["sampler"]["inputs"]["sampler_name"] == "euler"


def test_setup_scheduler_link_combobox_resets_invalid_literal_to_first_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduler combobox should normalize invalid literal values to first option."""

    configure_localized_combo_items(monkeypatch)
    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    node_definition_gateway = _FakeNodeDefinitionGateway(
        {
            "KSampler": {
                "KSampler": {
                    "input": {"required": {"scheduler": [["normal", "karras"]]}}
                }
            }
        }
    )

    combo = _FakeComboBox()
    buffers: _Buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {"scheduler": "invalid"},
                    "scheduler_links": [],
                }
            }
        }
    }

    meta_factories.setup_scheduler_link_combobox(
        parent=SimpleNamespace(),
        scheduler_link_widgets={("B", "sampler"): combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        node_definition_gateway=node_definition_gateway,
        field_state=_field_state(
            literal_key="scheduler",
            link_key="scheduler_link",
            literal_options=("normal", "karras"),
        ),
    )

    assert combo.current_text == "normal"
    assert buffers["B"]["nodes"]["sampler"]["inputs"]["scheduler"] == "normal"


def test_setup_choice_link_combobox_keeps_existing_items_when_options_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unresolved literal options must not become a link-only complete dropdown."""

    configure_localized_combo_items(monkeypatch)

    monkeypatch.setattr(meta_factories, "isValid", lambda _obj: True)
    combo = _FakeComboBox()
    combo.addItems(["previous"])
    combo.setCurrentText("previous")
    buffers: _Buffers = {
        "B": {
            "nodes": {
                "sampler": {
                    "class_type": "KSampler",
                    "inputs": {},
                    "sampler_link": {"from_cube": "A", "from_node": "ksampler"},
                }
            }
        }
    }

    meta_factories.setup_sampler_link_combobox(
        parent=SimpleNamespace(),
        sampler_link_widgets={("B", "sampler"): combo},
        cube_alias="B",
        node_name="sampler",
        all_buffers=buffers,
        field_state=_field_state(
            literal_key="sampler_name",
            link_key="sampler_link",
            literal_options=(),
            link_targets=(
                ChoiceLinkTarget(
                    from_cube="A",
                    from_node="ksampler",
                    label="link:A",
                ),
            ),
            options_resolved=False,
        ),
    )

    assert combo.items == ["previous"]
    assert combo.current_text == "previous"
    assert combo.enabled is False


def test_sanitize_link_selections_preserve_linked_values_and_reset_invalid_literals() -> (
    None
):
    """Sanitizers should skip linked fields and repair only invalid literal selections."""
    all_buffers: _Buffers = {
        "A": {
            "nodes": {
                "s1": {
                    "inputs": {"sampler_name": "invalid"},
                    "sampler_links": [],
                    "sampler_link": None,
                },
                "s2": {
                    "inputs": {"sampler_name": "invalid"},
                    "sampler_links": [],
                    "sampler_link": {"from_cube": "X", "from_node": "Y"},
                },
                "k1": {
                    "inputs": {"scheduler": "bad"},
                    "scheduler_links": [],
                    "scheduler_link": None,
                },
            }
        }
    }

    meta_factories.sanitize_sampler_link_selection(
        all_buffers,
        {("A", "s1"): ["euler"], ("A", "s2"): ["heun"]},
    )
    meta_factories.sanitize_scheduler_link_selection(
        all_buffers,
        {("A", "k1"): ["normal"]},
    )

    assert all_buffers["A"]["nodes"]["s1"]["inputs"]["sampler_name"] == "euler"
    assert all_buffers["A"]["nodes"]["s2"]["inputs"]["sampler_name"] == "invalid"
    assert all_buffers["A"]["nodes"]["k1"]["inputs"]["scheduler"] == "normal"


def test_sanitize_link_selections_preserve_literals_when_options_are_unavailable() -> (
    None
):
    """Unavailable live choices should not erase restored sampler or scheduler values."""
    all_buffers: _Buffers = {
        "A": {
            "nodes": {
                "sampler": {
                    "inputs": {
                        "sampler_name": "euler_ancestral",
                        "scheduler": "normal",
                    },
                    "sampler_links": [],
                    "sampler_link": None,
                    "scheduler_links": [],
                    "scheduler_link": None,
                },
            },
        },
    }

    meta_factories.sanitize_sampler_link_selection(
        all_buffers,
        {("A", "sampler"): []},
    )
    meta_factories.sanitize_scheduler_link_selection(
        all_buffers,
        {("A", "sampler"): []},
    )

    inputs = all_buffers["A"]["nodes"]["sampler"]["inputs"]
    assert inputs["sampler_name"] == "euler_ancestral"
    assert inputs["scheduler"] == "normal"


def test_update_link_references_on_rename_updates_only_matching_aliases() -> None:
    """Rename propagation should rewrite only links targeting the renamed alias."""
    all_buffers: _Buffers = {
        "A": {
            "nodes": {
                "p": {"prompt_link": {"from_cube": "Old"}},
                "n": {"node_link": {"from_cube": "Old", "from_node": "vectorscopecc"}},
                "s": {"sampler_link": {"from_cube": "Old", "from_node": "K"}},
                "k": {"scheduler_link": {"from_cube": "Old", "from_node": "K"}},
                "x": {"prompt_link": {"from_cube": "Other"}},
            }
        }
    }

    meta_factories.update_prompt_link_references_on_rename(all_buffers, "Old", "New")
    meta_factories.update_sampler_link_references_on_rename(all_buffers, "Old", "New")
    meta_factories.update_scheduler_link_references_on_rename(all_buffers, "Old", "New")

    assert all_buffers["A"]["nodes"]["p"]["prompt_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["n"]["node_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["s"]["sampler_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["k"]["scheduler_link"]["from_cube"] == "New"
    assert all_buffers["A"]["nodes"]["x"]["prompt_link"]["from_cube"] == "Other"

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

"""Characterization tests for MetaRegistry link-widget update behavior."""

from __future__ import annotations

from types import SimpleNamespace

from substitute.domain.links import (
    NodeLinkEndpoint,
    NodeLinkEndpointIndex,
)
from substitute.domain.node_behavior import TitleControl
from substitute.presentation.editor.panel.meta_registry import MetaRegistry
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


class _ParentWidget:
    """Simple parent widget double exposing a layout accessor."""

    def __init__(self, layout_obj) -> None:
        self._layout_obj = layout_obj

    def layout(self):
        """Return assigned layout object."""
        return self._layout_obj


class _Combo:
    """Combo double with parent and parentWidget accessors."""

    def __init__(self, parent_obj, parent_widget_obj, valid: bool = True) -> None:
        self._parent_obj = parent_obj
        self._parent_widget_obj = parent_widget_obj
        self.valid = valid
        self.parents: list[object | None] = []
        self.deleted = False

    def parent(self):
        """Return Qt parent object."""
        return self._parent_obj

    def parentWidget(self):
        """Return parent widget."""
        return self._parent_widget_obj

    def setParent(self, parent) -> None:
        """Record parent changes for deletion assertions."""

        self.parents.append(parent)
        self._parent_obj = parent

    def deleteLater(self) -> None:
        """Record deferred deletion requests."""

        self.deleted = True


def _install_node_link_command_surface(panel: SimpleNamespace) -> None:
    """Attach the typed node-link command methods required by the controller."""

    panel.node_link_selection_calls = []
    panel.node_link_refresh_reasons = []

    def apply_manual_node_link_selection(
        cube_alias: str,
        identity: object,
        from_cube: str | None,
        from_node: str | None,
    ) -> None:
        """Record one manual node-link selection request."""

        panel.node_link_selection_calls.append(
            (cube_alias, identity, from_cube, from_node)
        )

    def refresh_node_behavior_state(*, reason: str) -> None:
        """Record one node-link behavior refresh request."""

        panel.node_link_refresh_reasons.append(reason)

    panel.apply_manual_node_link_selection = apply_manual_node_link_selection
    panel.refresh_node_behavior_state = refresh_node_behavior_state


def test_cleanup_dead_widgets_removes_invalid_or_parentless_combos(
    monkeypatch,
) -> None:
    """Cleanup should keep only combos that are valid and still parented."""
    panel = SimpleNamespace()
    registry = MetaRegistry(panel)
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )

    alive = _Combo(parent_obj=object(), parent_widget_obj=None, valid=True)
    dead_invalid = _Combo(parent_obj=object(), parent_widget_obj=None, valid=False)
    dead_orphan = _Combo(parent_obj=None, parent_widget_obj=None, valid=True)
    widget_map = {("a", 1): alive, ("b", 2): dead_invalid, ("c", 3): dead_orphan}

    registry._cleanup_dead_widgets(widget_map)

    assert widget_map == {("a", 1): alive}


def test_update_link_widgets_skips_when_panel_has_no_stack_context(monkeypatch) -> None:
    """Updater should no-op when cube state or stack order is unavailable."""
    panel = SimpleNamespace(
        _cube_states={},
        _stack_order=[],
        node_definition_gateway=object(),
    )
    registry = MetaRegistry(panel)
    calls = []
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )

    widget_map = {
        ("A", "node"): _Combo(
            parent_obj=object(),
            parent_widget_obj=_ParentWidget("layout"),
            valid=True,
        )
    }
    registry._update_link_widgets(
        widget_map,
        lambda *_args, **_kwargs: calls.append(True),
        add_label=False,
    )

    assert calls == []


def test_update_link_widgets_passes_all_buffers_layout_and_beautifier(
    monkeypatch,
) -> None:
    """Updater should call setup function with key args, buffers, layout, and beautifier."""
    panel = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(buffer={"nodes": {"n1": {"inputs": {}}}}),
            "B": SimpleNamespace(buffer={"nodes": {}}),
        },
        _stack_order=["A", "B"],
        node_definition_gateway=object(),
    )
    registry = MetaRegistry(panel)
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )

    alive_combo = _Combo(
        parent_obj=object(),
        parent_widget_obj=_ParentWidget("layout-object"),
        valid=True,
    )
    dead_combo = _Combo(parent_obj=object(), parent_widget_obj=None, valid=False)
    widget_map = {("A", "n1"): alive_combo, ("B", "n2"): dead_combo}
    captured = []

    def _setup_func(*args, **kwargs):
        captured.append((args, kwargs))

    registry._update_link_widgets(widget_map, _setup_func, add_label=True)

    assert list(widget_map.keys()) == [("A", "n1")]
    assert len(captured) == 1
    call, kwargs = captured[0]
    assert call[0] is panel
    assert call[1] is widget_map
    assert call[2:4] == ("A", "n1")
    assert call[4]["A"] == panel._cube_states["A"].buffer
    assert call[5] == "layout-object"
    assert callable(call[6])
    assert call[6].__name__ == "beautify_label"
    assert kwargs["node_definition_gateway"] is panel.node_definition_gateway


def test_update_link_widgets_for_cube_filters_by_cube_alias(monkeypatch) -> None:
    """Cube-scoped updater should refresh only matching widget-map entries."""

    panel = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(buffer={"nodes": {"n1": {"inputs": {}}}}),
            "B": SimpleNamespace(buffer={"nodes": {"n2": {"inputs": {}}}}),
        },
        _stack_order=["A", "B"],
        node_definition_gateway=object(),
    )
    registry = MetaRegistry(panel)
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )

    widget_map = {
        ("A", "n1"): _Combo(
            parent_obj=object(),
            parent_widget_obj=_ParentWidget("layout-a"),
            valid=True,
        ),
        ("B", "n2"): _Combo(
            parent_obj=object(),
            parent_widget_obj=_ParentWidget("layout-b"),
            valid=True,
        ),
    }
    captured = []

    def _setup_func(*args, **kwargs):
        captured.append((args, kwargs))

    registry._update_link_widgets_for_cube(widget_map, _setup_func, "A")

    assert len(captured) == 1
    call, kwargs = captured[0]
    assert call[2:4] == ("A", "n1")
    assert call[4]["B"] == panel._cube_states["B"].buffer
    assert call[5] == "layout-a"
    assert kwargs["node_definition_gateway"] is panel.node_definition_gateway


def test_prompt_node_link_refresh_passes_width_groups_by_identity(monkeypatch) -> None:
    """Prompt selectors should receive node-link width labels by prompt identity."""

    positive_a = NodeLinkEndpoint(
        cube_alias="SDXL/Text to Image",
        node_name="positive_prompt",
        class_type="PrimitiveStringMultiline",
        family="prompt:positive",
        editable_value_keys=("prompt_template",),
    )
    negative_a = NodeLinkEndpoint(
        cube_alias="SDXL/Text to Image",
        node_name="negative_prompt",
        class_type="PrimitiveStringMultiline",
        family="prompt:negative",
        editable_value_keys=("prompt_template",),
    )
    positive_b = NodeLinkEndpoint(
        cube_alias="SDXL/Automask Detailer",
        node_name="positive_prompt",
        class_type="PrimitiveStringMultiline",
        family="prompt:positive",
        editable_value_keys=("prompt_template",),
    )
    negative_b = NodeLinkEndpoint(
        cube_alias="SDXL/Automask Detailer",
        node_name="negative_prompt",
        class_type="PrimitiveStringMultiline",
        family="prompt:negative",
        editable_value_keys=("prompt_template",),
    )
    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (positive_a, negative_a, positive_b, negative_b)
    )
    panel = SimpleNamespace(
        _cube_states={
            "SDXL/Text to Image": SimpleNamespace(buffer={"nodes": {}}),
            "SDXL/Automask Detailer": SimpleNamespace(buffer={"nodes": {}}),
        },
        _stack_order=["SDXL/Text to Image", "SDXL/Automask Detailer"],
        node_definition_gateway=object(),
        node_link_widgets={
            ("SDXL/Automask Detailer", positive_b.identity): _Combo(
                parent_obj=object(),
                parent_widget_obj=_ParentWidget("positive-layout"),
            ),
            ("SDXL/Automask Detailer", negative_b.identity): _Combo(
                parent_obj=object(),
                parent_widget_obj=_ParentWidget("negative-layout"),
            ),
        },
    )
    _install_node_link_command_surface(panel)
    panel.current_behavior_snapshot = lambda: SimpleNamespace(
        node_link_endpoint_index=endpoint_index,
        resolved_nodes_by_alias={
            "SDXL/Automask Detailer": {
                "positive_prompt": SimpleNamespace(
                    card=SimpleNamespace(
                        title_controls=(TitleControl.NODE_LINK_SELECTOR,)
                    )
                ),
                "negative_prompt": SimpleNamespace(
                    card=SimpleNamespace(
                        title_controls=(TitleControl.NODE_LINK_SELECTOR,)
                    )
                ),
            }
        },
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )
    captured: list[tuple[str, ...]] = []
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.setup_node_link_combobox",
        lambda *_args, **kwargs: captured.append(kwargs["shared_width_labels"]),
    )

    MetaRegistry(panel).update_node_link_widgets()

    assert captured == [
        ("Independent", "🔗 SDXL/Text to Image"),
        ("Independent", "🔗 SDXL/Text to Image"),
    ]


def test_node_link_refresh_passes_width_groups_by_identity(monkeypatch) -> None:
    """Node refresh should share widths only inside each node-link identity."""

    vectorscope_a = NodeLinkEndpoint(
        cube_alias="SDXL/Text to Image",
        node_name="vectorscopecc",
        class_type="VectorscopeCC",
        family="vectorscopecc",
        editable_value_keys=("brightness",),
    )
    vectorscope_b = NodeLinkEndpoint(
        cube_alias="SDXL/Automask Detailer",
        node_name="vectorscopecc",
        class_type="VectorscopeCC",
        family="vectorscopecc",
        editable_value_keys=("brightness",),
    )
    upscale_b = NodeLinkEndpoint(
        cube_alias="SDXL/Automask Detailer",
        node_name="load_model",
        class_type="UpscaleModelLoader",
        family="upscale_model",
        editable_value_keys=("model_name",),
    )
    upscale_c = NodeLinkEndpoint(
        cube_alias="SDXL/Diffusion Upscale",
        node_name="load_model",
        class_type="UpscaleModelLoader",
        family="upscale_model",
        editable_value_keys=("model_name",),
    )
    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (vectorscope_a, vectorscope_b, upscale_b, upscale_c)
    )
    panel = SimpleNamespace(
        _cube_states={
            "SDXL/Text to Image": SimpleNamespace(buffer={"nodes": {}}),
            "SDXL/Automask Detailer": SimpleNamespace(buffer={"nodes": {}}),
            "SDXL/Diffusion Upscale": SimpleNamespace(buffer={"nodes": {}}),
        },
        _stack_order=[
            "SDXL/Text to Image",
            "SDXL/Automask Detailer",
            "SDXL/Diffusion Upscale",
        ],
        node_definition_gateway=object(),
        node_link_widgets={
            ("SDXL/Automask Detailer", vectorscope_b.identity): _Combo(
                parent_obj=object(),
                parent_widget_obj=_ParentWidget("vectorscope-layout"),
            ),
            ("SDXL/Diffusion Upscale", upscale_c.identity): _Combo(
                parent_obj=object(),
                parent_widget_obj=_ParentWidget("upscale-layout"),
            ),
        },
    )
    _install_node_link_command_surface(panel)
    panel.current_behavior_snapshot = lambda: SimpleNamespace(
        node_link_endpoint_index=endpoint_index,
        resolved_nodes_by_alias={
            "SDXL/Automask Detailer": {
                "vectorscopecc": SimpleNamespace(
                    card=SimpleNamespace(
                        title_controls=(TitleControl.NODE_LINK_SELECTOR,)
                    )
                )
            },
            "SDXL/Diffusion Upscale": {
                "load_model": SimpleNamespace(
                    card=SimpleNamespace(
                        title_controls=(TitleControl.NODE_LINK_SELECTOR,)
                    )
                )
            },
        },
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )
    captured: list[tuple[str, ...] | None] = []
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.setup_node_link_combobox",
        lambda *_args, **kwargs: captured.append(kwargs["shared_width_labels"]),
    )

    MetaRegistry(panel).update_node_link_widgets()

    assert captured == [
        ("Independent", "🔗 SDXL/Text to Image"),
        ("Independent", "🔗 SDXL/Automask Detailer"),
    ]


def test_node_link_refresh_creates_missing_eligible_selector_from_title_surface(
    monkeypatch,
) -> None:
    """Node refresh should create an eligible missing selector without rebuilding cards."""

    vectorscope_a = NodeLinkEndpoint(
        cube_alias="SDXL/Text to Image",
        node_name="vectorscopecc",
        class_type="VectorscopeCC",
        family="vectorscopecc",
        editable_value_keys=("brightness",),
    )
    vectorscope_b = NodeLinkEndpoint(
        cube_alias="du2",
        node_name="vectorscopecc",
        class_type="VectorscopeCC",
        family="vectorscopecc",
        editable_value_keys=("brightness",),
    )
    endpoint_index = NodeLinkEndpointIndex.from_endpoints(
        (vectorscope_a, vectorscope_b)
    )
    layout = object()
    panel = SimpleNamespace(
        _cube_states={
            "SDXL/Text to Image": SimpleNamespace(buffer={"nodes": {}}),
            "du2": SimpleNamespace(buffer={"nodes": {}}),
        },
        _stack_order=["SDXL/Text to Image", "du2"],
        node_definition_gateway=object(),
        node_link_widgets={},
        node_link_title_surfaces={
            ("du2", vectorscope_b.identity): SimpleNamespace(
                cube_alias="du2",
                node_name="vectorscopecc",
                identity=vectorscope_b.identity,
                title_layout=layout,
                title_controls=(TitleControl.NODE_LINK_SELECTOR,),
            )
        },
    )
    _install_node_link_command_surface(panel)
    panel.current_behavior_snapshot = lambda: SimpleNamespace(
        node_link_endpoint_index=endpoint_index,
        resolved_nodes_by_alias={
            "du2": {
                "vectorscopecc": SimpleNamespace(
                    card=SimpleNamespace(
                        title_controls=(TitleControl.NODE_LINK_SELECTOR,)
                    )
                )
            }
        },
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )
    captured: list[tuple[NodeLinkEndpoint, object]] = []

    def _setup_node_link(*args, **_kwargs):
        endpoint = args[2]
        title_layout = args[5]
        combo = _Combo(parent_obj=object(), parent_widget_obj=_ParentWidget(layout))
        args[1][(endpoint.cube_alias, endpoint.identity)] = combo
        captured.append((endpoint, title_layout))
        return combo, "SDXL/Text to Image"

    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.setup_node_link_combobox",
        _setup_node_link,
    )

    MetaRegistry(panel).update_node_link_widgets()

    assert captured == [(vectorscope_b, layout)]
    assert ("du2", vectorscope_b.identity) in panel.node_link_widgets


def test_node_link_refresh_skips_endpoint_without_selector_title_control(
    monkeypatch,
) -> None:
    """Node refresh should not treat non-selector endpoints as missing widgets."""

    endpoint = NodeLinkEndpoint(
        cube_alias="A",
        node_name="positive_prompt",
        class_type="CLIPTextEncode",
        family="prompt",
        editable_value_keys=("text",),
    )
    endpoint_index = NodeLinkEndpointIndex.from_endpoints((endpoint,))
    panel = SimpleNamespace(
        _cube_states={"A": SimpleNamespace(buffer={"nodes": {}})},
        _stack_order=["A"],
        node_definition_gateway=object(),
        node_link_widgets={},
        node_link_title_surfaces={
            ("A", endpoint.identity): SimpleNamespace(
                cube_alias="A",
                node_name="positive_prompt",
                identity=endpoint.identity,
                title_layout=object(),
                title_controls=(),
            )
        },
    )
    panel.current_behavior_snapshot = lambda: SimpleNamespace(
        node_link_endpoint_index=endpoint_index,
        resolved_nodes_by_alias={
            "A": {
                "positive_prompt": SimpleNamespace(
                    card=SimpleNamespace(title_controls=())
                )
            }
        },
    )
    calls: list[object] = []
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.setup_node_link_combobox",
        lambda *_args, **_kwargs: calls.append(True),
    )

    MetaRegistry(panel).update_node_link_widgets()

    assert calls == []
    assert panel.node_link_widgets == {}


def test_node_link_alias_rename_migrates_widgets_and_title_surfaces() -> None:
    """Alias rename should keep existing selector widgets attached under the new key."""

    combo = _Combo(parent_obj=object(), parent_widget_obj=_ParentWidget("layout"))
    identity = NodeLinkEndpoint(
        cube_alias="old",
        node_name="vectorscopecc",
        class_type="VectorscopeCC",
        family="vectorscopecc",
        editable_value_keys=("brightness",),
    ).identity
    title_surface = SimpleNamespace(
        cube_alias="old",
        node_name="vectorscopecc",
        identity=identity,
        title_layout="layout",
        title_controls=(TitleControl.NODE_LINK_SELECTOR,),
    )
    panel = SimpleNamespace(
        node_link_widgets={("old", identity): combo},
        node_link_title_surfaces={("old", identity): title_surface},
        node_definition_gateway=object(),
    )

    MetaRegistry(panel).rename_node_link_alias("old", "new")

    assert panel.node_link_widgets == {("new", identity): combo}
    assert ("old", identity) not in panel.node_link_title_surfaces
    migrated_surface = panel.node_link_title_surfaces[("new", identity)]
    assert migrated_surface.cube_alias == "new"
    assert migrated_surface.title_layout == "layout"


def test_sampler_scheduler_refreshes_do_not_receive_shared_width_labels(
    monkeypatch,
) -> None:
    """Choice link refresh paths should remain outside prompt/node width sharing."""

    cube = cube_state(
        nodes={
            "sampler": {
                "class_type": "KSampler",
                "inputs": {"sampler_name": "euler", "scheduler": "normal"},
            }
        }
    )
    behavior_snapshot = build_behavior_snapshot(
        cube_states={"A": cube},
        stack_order=["A"],
        definitions_by_class={
            "KSampler": {
                "input": {
                    "required": {
                        "sampler_name": [["euler", "heun"]],
                        "scheduler": [["normal", "karras"]],
                    }
                }
            }
        },
    )
    panel = SimpleNamespace(
        _cube_states={"A": cube},
        _stack_order=["A"],
        node_definition_gateway=object(),
        current_behavior_snapshot=lambda: behavior_snapshot,
        sampler_link_widgets={
            ("A", "sampler"): _Combo(
                parent_obj=object(),
                parent_widget_obj=_ParentWidget("sampler-layout"),
            )
        },
        scheduler_link_widgets={
            ("A", "sampler"): _Combo(
                parent_obj=object(),
                parent_widget_obj=_ParentWidget("scheduler-layout"),
            )
        },
    )
    registry = MetaRegistry(panel)
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.isValid",
        lambda combo: bool(combo.valid),
    )
    sampler_kwargs: list[dict[str, object]] = []
    scheduler_kwargs: list[dict[str, object]] = []
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.setup_sampler_link_combobox",
        lambda *_args, **kwargs: sampler_kwargs.append(kwargs),
    )
    monkeypatch.setattr(
        "substitute.presentation.editor.panel.meta_registry.setup_scheduler_link_combobox",
        lambda *_args, **kwargs: scheduler_kwargs.append(kwargs),
    )

    registry.update_sampler_link_widgets()
    registry.update_scheduler_link_widgets()

    assert "shared_width_labels" not in sampler_kwargs[0]
    assert "shared_width_labels" not in scheduler_kwargs[0]
    assert sampler_kwargs[0]["field_state"].literal_options == ("euler", "heun")
    assert scheduler_kwargs[0]["field_state"].literal_options == (
        "normal",
        "karras",
    )

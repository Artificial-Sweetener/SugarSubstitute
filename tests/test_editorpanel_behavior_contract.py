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

"""Characterization tests for EditorPanel behavior-critical helpers."""

from __future__ import annotations

import importlib
import logging
from types import SimpleNamespace

from substitute.application.node_behavior import (
    FieldBehavior,
    FieldPresentation,
    PromptRole,
    ResolvedFieldSpec,
)
from substitute.application.prompt_editor import (
    PromptEditorFeatureProfile,
    PromptSyntaxProfile,
)
from substitute.application.editor_search import (
    EditorSearchMode,
    EditorSearchService,
    TextSearchMatch,
)
from substitute.domain.links import PromptEndpoint, PromptEndpointIndex
from substitute.presentation.editor.panel.prompt_profile_policy import (
    PanelPromptFieldProfileDecision,
)
from substitute.presentation.editor.panel.projection_models import ProjectedCubeBuild
from substitute.presentation.editor.panel.projection_session import (
    ActiveProjectionSession,
)
from tests.node_behavior_test_helpers import build_behavior_snapshot, cube_state


def _import_epanel_module():
    """Import the editor panel module."""
    return importlib.import_module("substitute.presentation.editor.panel.view")


class _StrictNodeCardBuilder:
    """NodeCardBuilder double with the production constructor surface."""

    def __init__(
        self,
        *,
        panel,
        services,
        model_choice_snapshot_controller=None,
        thumbnail_asset_repository=None,
        dimension_preset_source=None,
        node_input_preset_source=None,
        prompt_segment_preset_source=None,
    ) -> None:
        """Record constructor inputs and reject unexpected keyword arguments."""

        self.panel = panel
        self.services = services
        self.node_definition_gateway = services.node_definition_gateway
        self.prompt_autocomplete_gateway = services.prompt.autocomplete_gateway
        self.prompt_wildcard_catalog_gateway = services.prompt.wildcard_catalog_gateway
        self.danbooru_url_import_service = services.prompt.danbooru_url_import_service
        self.danbooru_wiki_service = services.prompt.danbooru_wiki_service
        self.danbooru_image_preview_service = (
            services.prompt.danbooru_image_preview_service
        )
        self.danbooru_recent_posts_service = (
            services.prompt.danbooru_recent_posts_service
        )
        self.prompt_lora_catalog_service = services.prompt.lora_catalog_service
        self.model_choice_snapshot_controller = model_choice_snapshot_controller
        self.thumbnail_asset_repository = thumbnail_asset_repository
        self.dimension_preset_source = dimension_preset_source
        self.node_input_preset_source = node_input_preset_source
        self.prompt_segment_preset_source = prompt_segment_preset_source
        self.calls: list[dict[str, object]] = []

    def build_node_card(self, **kwargs):
        """Record one build call and return a sentinel wrapper."""

        self.calls.append(kwargs)
        return "node-card"


class _DimensionPresetSourceDouble:
    """Record prepared dimension preset snapshot refreshes."""

    def __init__(self) -> None:
        """Initialize refresh call tracking."""

        self.prepare_calls: list[str] = []

    def prepare_dimension_preset_menu_model(self, *, reason: str) -> None:
        """Record one explicit preparation reason."""

        self.prepare_calls.append(reason)


class _PresetContextRefreshDouble:
    """Record panel preset-context lifecycle calls."""

    def __init__(self) -> None:
        """Initialize lifecycle observations."""

        self.begin_projection_calls: list[object] = []
        self.refresh_calls: list[str] = []

    def begin_projection(self, **kwargs: object) -> None:
        """Record one full projection boundary."""

        self.begin_projection_calls.append(kwargs)

    def refresh(self, *, reason: str) -> None:
        """Record one downstream preset refresh."""

        self.refresh_calls.append(reason)


class _CardWrapper:
    """Minimal node-card wrapper for visibility assertions."""

    def __init__(self, visible: bool) -> None:
        self.visible = visible
        self.props: dict[str, object] = {}

    def isVisible(self) -> bool:
        """Return current visibility."""
        return self.visible

    def setVisible(self, visible: bool) -> None:
        """Record visibility updates."""
        self.visible = visible

    def setProperty(self, name: str, value: object) -> None:
        """Record one dynamic property update."""

        self.props[name] = value


class _PromptEditorDouble:
    """Prompt editor double with metadata and mutable text."""

    def __init__(self, metadata: dict[str, object], text: str) -> None:
        """Store prompt metadata and initial text."""

        self._metadata = metadata
        self._text = text

    def property(self, name: str) -> object:
        """Return Qt-style widget metadata."""

        return self._metadata if name == "input_metadata" else None

    def toPlainText(self) -> str:
        """Return the current prompt text."""

        return self._text

    def setPlainText(self, text: str) -> None:
        """Replace the current prompt text."""

        self._text = text


class _CubeWidgetDouble:
    """Cube widget double exposing prompt editor children."""

    def __init__(self, children: list[_PromptEditorDouble]) -> None:
        """Store children returned by findChildren."""

        self._children = children

    def findChildren(self, _widget_type: object) -> list[_PromptEditorDouble]:
        """Return prompt editor doubles."""

        return list(self._children)


class _Widget:
    """Generic widget test double with visibility + dynamic properties."""

    def __init__(self, parent=None, props: dict | None = None) -> None:
        self.visible = True
        self._parent = parent
        self._props = dict(props or {})

    def setVisible(self, visible: bool) -> None:
        """Record visibility updates."""
        self.visible = visible

    def property(self, name: str):
        """Qt-style dynamic property getter."""
        return self._props.get(name)

    def setProperty(self, name: str, value) -> None:
        """Qt-style dynamic property setter."""
        self._props[name] = value

    def parentWidget(self):
        """Return the parent widget."""
        return self._parent


class _IssueWidget:
    """Cube-section double that records runtime issue presentation."""

    def __init__(self) -> None:
        """Initialize runtime issue presentation state."""

        self.severity: str | None = None
        self.messages: tuple[str, ...] = ()

    def setIssueSeverity(self, severity: str | None) -> None:  # noqa: N802
        """Record the applied issue severity."""

        self.severity = severity

    def setIssueMessages(self, messages: tuple[str, ...]) -> None:  # noqa: N802
        """Record the applied issue display messages."""

        self.messages = tuple(messages)


class _MaskPickerDouble:
    """Mask picker double with metadata and refresh recording."""

    def __init__(self, metadata: dict[str, object]) -> None:
        """Store picker metadata for editor-panel lookup tests."""

        self._metadata = metadata
        self.mask_paths: list[str] = []
        self.refresh_paths: list[str] = []

    def property(self, name: str) -> object | None:
        """Return Qt-style metadata."""

        if name == "input_metadata":
            return self._metadata
        return None

    def set_mask_path(self, path: str) -> None:
        """Record refreshed mask paths."""

        self.mask_paths.append(path)

    def refresh_mask_path(self, path: str) -> None:
        """Record autosave-driven mask refresh paths."""

        self.refresh_paths.append(path)


class _LayoutItem:
    """Layout item wrapper used by the visibility loop."""

    def __init__(self, widget) -> None:
        self._widget = widget

    def widget(self):
        """Return the contained widget."""
        return self._widget


class _Layout:
    """Simple layout exposing count/itemAt."""

    def __init__(self, widgets: list) -> None:
        self._widgets = widgets

    def count(self) -> int:
        """Return number of widgets."""
        return len(self._widgets)

    def itemAt(self, index: int):
        """Return the layout item."""
        return _LayoutItem(self._widgets[index])


def test_refresh_mask_picker_updates_matching_picker() -> None:
    """Editor panel should refresh the picker matching cube alias and node name."""

    mod = _import_epanel_module()
    matching = _MaskPickerDouble(
        {
            "cube_alias": "Inpaint",
            "node_name": "load_image_as_mask",
            "key": "image",
        }
    )
    other = _MaskPickerDouble(
        {
            "cube_alias": "Other",
            "node_name": "load_image_as_mask",
            "key": "image",
        }
    )
    fake_panel = SimpleNamespace(findChildren=lambda _type: [other, matching])

    mod.EditorPanel.refresh_mask_picker(
        fake_panel,
        "Inpaint",
        "load_image_as_mask",
        "E:/masks/current.png",
    )

    assert other.refresh_paths == []
    assert matching.refresh_paths == ["E:/masks/current.png"]


def test_refresh_mask_picker_logs_when_no_picker_matches(caplog) -> None:
    """Missing mask picker matches should be observable."""

    mod = _import_epanel_module()
    picker = _MaskPickerDouble(
        {
            "node_name": "load_image_as_mask",
            "key": "image",
        }
    )
    fake_panel = SimpleNamespace(findChildren=lambda _type: [picker])

    with caplog.at_level(
        logging.WARNING,
        logger="sugarsubstitute.presentation.editor.panel.view",
    ):
        mod.EditorPanel.refresh_mask_picker(
            fake_panel,
            "Inpaint",
            "load_image_as_mask",
            "E:/masks/current.png",
        )

    assert picker.mask_paths == []
    assert "no matching picker was found" in caplog.text
    assert "cube_alias=Inpaint" in caplog.text
    assert "inspected_count=1" in caplog.text


def test_sync_prompt_editor_values_for_cube_updates_only_target_cube(
    monkeypatch,
) -> None:
    """Cube-scoped prompt sync should not scan or mutate unrelated cube widgets."""

    mod = _import_epanel_module()
    field_state_mod = importlib.import_module(
        "substitute.presentation.editor.panel.field_state_controller"
    )
    monkeypatch.setattr(field_state_mod, "PromptEditor", _PromptEditorDouble)
    target_prompt = _PromptEditorDouble(
        {
            "cube_alias": "A",
            "node_name": "prompt",
            "key": "text",
        },
        "old",
    )
    unrelated_prompt = _PromptEditorDouble(
        {
            "cube_alias": "B",
            "node_name": "prompt",
            "key": "text",
        },
        "unchanged",
    )
    panel = SimpleNamespace(
        _cube_states={
            "A": SimpleNamespace(
                buffer={
                    "nodes": {"prompt": {"inputs": {"text": "new text"}}},
                }
            ),
            "B": SimpleNamespace(
                buffer={
                    "nodes": {"prompt": {"inputs": {"text": "other text"}}},
                }
            ),
        },
        cube_widgets={
            "A": _CubeWidgetDouble([target_prompt]),
            "B": _CubeWidgetDouble([unrelated_prompt]),
        },
        refresh_prompt_scene_diagnostics=lambda: None,
    )

    mod.EditorPanel.sync_prompt_editor_values_for_cube(panel, "A")

    assert target_prompt.toPlainText() == "new text"
    assert unrelated_prompt.toPlainText() == "unchanged"


class _Parent:
    """Parent widget exposing layout()."""

    def __init__(self, layout: _Layout) -> None:
        self._layout = layout

    def layout(self) -> _Layout:
        """Return child layout."""
        return self._layout


class _Signal:
    """Simple signal double supporting connect/disconnect."""

    def __init__(self) -> None:
        self.connected: list = []
        self.disconnected: list = []

    def connect(self, slot) -> None:
        """Record connected slot."""
        self.connected.append(slot)

    def disconnect(self, slot) -> None:
        """Record disconnected slot."""
        self.disconnected.append(slot)


class _LayoutItemForOrder:
    """Layout item used by load/reorder tests."""

    def __init__(self, widget=None, spacer: bool = False) -> None:
        self._widget = widget
        self._spacer = spacer

    def widget(self):
        """Return item widget."""
        return self._widget

    def spacerItem(self):
        """Return spacer marker for spacer items."""
        return object() if self._spacer else None


class _OrderedLayout:
    """Minimal layout that tracks take/add ordering."""

    def __init__(self, items: list[_LayoutItemForOrder]) -> None:
        self._items = list(items)
        self.added: list[tuple[str, object]] = []

    def count(self) -> int:
        """Return current item count."""
        return len(self._items)

    def takeAt(self, index: int) -> _LayoutItemForOrder:
        """Remove and return item at index."""
        return self._items.pop(index)

    def itemAt(self, index: int) -> _LayoutItemForOrder:
        """Return item at index."""
        return self._items[index]

    def addSpacing(self, spacing: int) -> None:
        """Record spacing insertion."""
        self.added.append(("spacing", spacing))

    def addWidget(self, widget) -> None:
        """Record widget insertion."""
        self.added.append(("widget", widget))


class _ClearLayoutItem:
    """Layout item double exposing either a widget or nested layout."""

    def __init__(self, *, widget=None, layout=None) -> None:
        """Store one widget or nested layout payload."""

        self._widget = widget
        self._layout = layout

    def widget(self):
        """Return the contained widget when present."""

        return self._widget

    def layout(self):
        """Return the contained nested layout when present."""

        return self._layout


class _DisposableWidget:
    """Widget double recording deferred deletion requests."""

    def __init__(self) -> None:
        """Initialize the deletion flag."""

        self.deleted = False

    def deleteLater(self) -> None:
        """Record deferred deletion."""

        self.deleted = True


class _ClearLayout:
    """Simple layout double supporting destructive clear operations."""

    def __init__(self, items: list[_ClearLayoutItem]) -> None:
        """Store the ordered layout items."""

        self._items = list(items)

    def count(self) -> int:
        """Return the current item count."""

        return len(self._items)

    def takeAt(self, index: int) -> _ClearLayoutItem:
        """Remove and return one item."""

        return self._items.pop(index)


def test_clear_search_filters_resets_state_and_recomputes_visibility() -> None:
    """Clearing search resets both filters and triggers full recompute."""

    mod = _import_epanel_module()
    calls = {"field": [], "recompute": []}
    fake = SimpleNamespace(
        _current_node_search_text="ksampler",
        _current_search_hidden_keys={"seed"},
        _current_search_matching_nodes={("A", "NodeA")},
        _current_search_result=object(),
        _current_search={"matches": ("match",), "index": 0, "needle": "dog"},
        _text_search_refresh_pending=True,
        input_widgets_by_field_key={},
        set_search_field_match_keys=lambda match_keys, *, active: calls["field"].append(
            (match_keys, active)
        ),
        refresh_node_behavior_state=lambda **kwargs: calls["recompute"].append(kwargs),
    )

    mod.EditorPanel.clear_search_filters(fake)

    assert fake._current_node_search_text is None
    assert fake._current_search_hidden_keys == set()
    assert fake._current_search_matching_nodes is None
    assert fake._current_search_result is None
    assert fake._current_search == {"matches": (), "index": -1, "needle": ""}
    assert fake._text_search_refresh_pending is False
    assert calls["field"] == [(None, False)]
    assert calls["recompute"] == [
        {
            "search_hidden_keys": set(),
            "node_search_text": None,
            "reason": "search_changed",
        }
    ]


def test_set_hidden_field_keys_hides_row_column_and_dividers(monkeypatch) -> None:
    """Hidden key propagation should toggle row, column, and divider visibility."""
    mod = _import_epanel_module()
    import shiboken6

    monkeypatch.setattr(shiboken6, "isValid", lambda _obj: True)

    row_key = ("CubeA", "MaskNode", "seed")
    col_key = ("CubeA", "MaskNode", "seed_col")
    row_divider = _Widget()
    row_widget = _Widget()
    row_container = _Widget()
    horizontal_divider = _Widget()
    col_key_prop = list(col_key)

    vertical_divider = _Widget(props={"vertical_divider_for_field": col_key_prop})
    parent_layout = _Layout([vertical_divider])
    col_parent = _Parent(parent_layout)
    col_widget = _Widget(parent=col_parent, props={"field_key": col_key_prop})
    input_widget = _Widget()

    fake = SimpleNamespace(
        row_widgets={
            row_key: (row_divider, row_widget),
            col_key: (horizontal_divider, _Widget()),
        },
        col_widgets={
            col_key: (row_container, col_widget, input_widget),
        },
    )

    mod.EditorPanel.set_hidden_field_keys(fake, {"seed", "seed_col"})

    assert row_divider.visible is False
    assert row_widget.visible is False
    assert col_widget.visible is False
    assert vertical_divider.visible is False
    assert row_container.visible is False
    assert horizontal_divider.visible is False


def test_refresh_node_behavior_state_reapplies_last_state_on_snapshot_failure(
    monkeypatch,
) -> None:
    """Snapshot failures should fall back to last known card and hidden-field state."""
    mod = _import_epanel_module()
    monkeypatch.setattr(mod, "isValid", lambda _obj: True)

    card = _CardWrapper(visible=True)
    cube_state = SimpleNamespace(buffer={"nodes": {"N1": {"inputs": {}}}}, ui={})
    hidden_calls: list[set[str]] = []
    rebuild_calls: list[bool] = []

    fake = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        card_wrappers={("CubeA", "N1"): card},
        _last_card_decisions={("CubeA", "N1"): (False, True, "previous")},
        _last_hidden_field_keys={"seed"},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _build_behavior_snapshot=lambda **_kwargs: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
        set_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
        _rebuild_all_cube_visibility_menus=lambda: rebuild_calls.append(True),
    )

    mod.EditorPanel.refresh_node_behavior_state(fake)

    assert card.visible is False
    assert hidden_calls == [{"seed"}]
    assert rebuild_calls == []


def test_refresh_node_behavior_state_updates_cards_buffers_and_hidden_fields(
    monkeypatch,
) -> None:
    """Successful snapshot application should update wrappers, hidden fields, and menus."""
    mod = _import_epanel_module()
    monkeypatch.setattr(mod, "isValid", lambda _obj: True)

    card = _CardWrapper(visible=False)
    cube_state = SimpleNamespace(buffer={"nodes": {"N1": {"inputs": {}}}}, ui={})
    hidden_calls: list[set[str]] = []
    rebuild_calls: list[bool] = []
    snapshot_calls: list[dict[str, object]] = []
    snapshot = SimpleNamespace(
        card_decisions_by_alias={
            "CubeA": {
                "N1": SimpleNamespace(
                    visible=True,
                    enabled=False,
                    reason="search_and_policy",
                )
            }
        },
        hidden_field_keys_by_alias={"CubeA": {"seed"}},
        reveal_entries_by_alias={"CubeA": []},
    )

    fake = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        card_wrappers={("CubeA", "N1"): card},
        _last_card_decisions={},
        _last_hidden_field_keys=set(),
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _build_behavior_snapshot=lambda **kwargs: (
            snapshot_calls.append(kwargs),
            snapshot,
        )[1],
        set_hidden_field_keys=lambda keys: hidden_calls.append(set(keys)),
        _rebuild_all_cube_visibility_menus=lambda: rebuild_calls.append(True),
    )

    mod.EditorPanel.refresh_node_behavior_state(
        fake,
        search_hidden_keys={"sampler_name"},
        node_search_text="ksampler",
    )

    assert snapshot_calls == [
        {
            "search_hidden_keys": {"sampler_name"},
            "node_search_text": "ksampler",
        }
    ]
    assert card.visible is True
    assert fake._last_hidden_field_keys == {"seed"}
    assert hidden_calls == [{"seed"}]
    assert fake._last_card_decisions[("CubeA", "N1")] == (
        True,
        False,
        "search_and_policy",
    )
    assert rebuild_calls == [True]


def test_behavior_refresh_transaction_reuses_matching_snapshot(
    caplog,
) -> None:
    """A refresh transaction should reuse one matching behavior snapshot."""

    mod = _import_epanel_module()
    snapshots = [object()]
    build_calls: list[dict[str, object]] = []

    class _NodeBehaviorService:
        def build_snapshot(self, **kwargs: object) -> object:
            build_calls.append(kwargs)
            return snapshots[0]

    cube_state = SimpleNamespace(buffer={"nodes": {}}, ui={})
    fake = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _last_behavior_snapshot=None,
        _behavior_refresh_transaction=None,
        node_behavior_service=_NodeBehaviorService(),
        _workflow_overrides=lambda: {"seed": {"value": 7}},
    )
    caplog.set_level(
        logging.INFO,
        logger="sugarsubstitute.presentation.editor.panel.prompt_context_controller",
    )

    mod.EditorPanel.begin_behavior_refresh_transaction(
        fake,
        reason="full_workflow_projection",
    )
    first_snapshot = mod.EditorPanel._build_behavior_snapshot(fake)
    second_snapshot = mod.EditorPanel._build_behavior_snapshot(fake)
    mod.EditorPanel.end_behavior_refresh_transaction(
        fake,
        reason="full_workflow_projection",
    )

    assert first_snapshot is snapshots[0]
    assert second_snapshot is snapshots[0]
    assert len(build_calls) == 1
    assert "Reused editor behavior snapshot from refresh transaction" in caplog.text
    assert fake._behavior_refresh_transaction is None


def test_behavior_refresh_transaction_builds_fresh_after_link_change() -> None:
    """State-changing behavior refresh reasons should invalidate transactions."""

    mod = _import_epanel_module()
    snapshots = [
        SimpleNamespace(card_decisions_by_alias={}, hidden_field_keys_by_alias={}),
        SimpleNamespace(card_decisions_by_alias={}, hidden_field_keys_by_alias={}),
    ]
    build_calls: list[dict[str, object]] = []
    applied: list[object] = []

    class _NodeBehaviorService:
        def build_snapshot(self, **kwargs: object) -> object:
            build_calls.append(kwargs)
            return snapshots[len(build_calls) - 1]

    cube_state = SimpleNamespace(buffer={"nodes": {}}, ui={})
    fake = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": cube_state},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _last_behavior_snapshot=None,
        _behavior_refresh_transaction=None,
        node_behavior_service=_NodeBehaviorService(),
        _workflow_overrides=lambda: {},
        _build_behavior_snapshot=lambda **kwargs: (
            mod.EditorPanel._build_behavior_snapshot(
                fake,
                **kwargs,
            )
        ),
        set_hidden_field_keys=lambda _keys: None,
        apply_node_card_behavior_decisions=lambda decisions: applied.append(decisions),
        _rebuild_all_cube_visibility_menus=lambda: None,
    )

    mod.EditorPanel.begin_behavior_refresh_transaction(fake, reason="cube_added")
    mod.EditorPanel._build_behavior_snapshot(fake)
    mod.EditorPanel.refresh_node_behavior_state(fake, reason="node_link_changed")

    assert len(build_calls) == 2
    assert fake._last_behavior_snapshot is snapshots[1]
    assert fake._behavior_refresh_transaction is None
    assert applied == [{}]


def test_model_option_refresh_invalidates_behavior_without_projection(
    monkeypatch,
) -> None:
    """Fresh model values should not mark the rendered editor structure stale."""

    mod = _import_epanel_module()
    calls: list[tuple[str, object]] = []
    snapshot = SimpleNamespace(
        card_decisions_by_alias={},
        hidden_field_keys_by_alias={},
    )
    fake = SimpleNamespace(
        _stack_order=["CubeA"],
        _cube_states={"CubeA": SimpleNamespace(buffer={"nodes": {}}, ui={})},
        _current_node_search_text=None,
        _current_search_hidden_keys=None,
        _current_search_matching_nodes=None,
        _build_behavior_snapshot=lambda **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        mod.EditorPanel,
        "invalidate_behavior_refresh_transaction",
        lambda _panel, *, reason: calls.append(("behavior", reason)),
    )
    monkeypatch.setattr(
        mod.EditorPanel,
        "invalidate_projection",
        lambda _panel, *, reason: calls.append(("projection", reason)),
    )
    monkeypatch.setattr(
        mod,
        "behavior_applier_for_panel",
        lambda _panel: SimpleNamespace(
            apply_snapshot=lambda applied: calls.append(("applied", applied)),
            restore_previous_state=lambda: None,
        ),
    )
    monkeypatch.setattr(
        mod,
        "_refresh_prompt_scene_diagnostics_if_available",
        lambda _panel: None,
    )

    mod.EditorPanel.refresh_node_behavior_state(
        fake,
        reason="model_options_changed",
        use_cached_snapshot=False,
    )

    assert calls == [
        ("behavior", "model_options_changed"),
        ("applied", snapshot),
    ]


def test_refresh_prompt_scene_diagnostics_scopes_errors_and_autocomplete() -> None:
    """Scene diagnostics should keep duplicate and authority autocomplete scope local."""

    mod = _import_epanel_module()

    class _PromptEditor:
        def __init__(self, metadata: dict[str, str]) -> None:
            self._metadata = metadata
            self.error_key_calls: list[frozenset[str]] = []
            self.autocomplete_title_calls: list[tuple[str, ...]] = []
            self.queueable_key_calls: list[frozenset[str]] = []

        def property(self, name: str) -> object:
            if name == "input_metadata":
                return self._metadata
            return None

        def set_scene_error_keys(self, keys: frozenset[str]) -> None:
            self.error_key_calls.append(keys)

        def set_scene_autocomplete_titles(self, titles: tuple[str, ...]) -> None:
            self.autocomplete_title_calls.append(titles)

        def set_queueable_scene_keys(self, keys: frozenset[str]) -> None:
            self.queueable_key_calls.append(keys)

    authority_editor = _PromptEditor(
        {
            "cube_alias": "Text",
            "node_name": "positive_prompt",
            "key": "text",
        }
    )
    negative_editor = _PromptEditor(
        {
            "cube_alias": "Text",
            "node_name": "negative_prompt",
            "key": "text",
        }
    )
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="text",
            ),
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.NEGATIVE,
                node_name="negative_prompt",
                field_key="text",
            ),
        )
    )
    fake = SimpleNamespace(
        _last_behavior_snapshot=SimpleNamespace(prompt_endpoint_index=endpoint_index),
        _stack_order=["Text"],
        _cube_states={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "inputs": {
                                "text": "**portrait\none\n**Portrait\nduplicate\n**cafe\ncafe"
                            }
                        },
                        "negative_prompt": {
                            "inputs": {"text": "generic\n**hands\nbad hands"}
                        },
                    }
                }
            )
        },
        _clear_prompt_scene_diagnostics=lambda: None,
        findChildren=lambda _class: [authority_editor, negative_editor],
    )

    mod.EditorPanel.refresh_prompt_scene_diagnostics(fake)

    assert authority_editor.autocomplete_title_calls == [()]
    assert authority_editor.error_key_calls == [frozenset()]
    assert authority_editor.queueable_key_calls == [frozenset({"portrait", "cafe"})]
    assert negative_editor.autocomplete_title_calls == [("portrait", "cafe")]
    assert negative_editor.error_key_calls == [frozenset({"hands"})]
    assert negative_editor.queueable_key_calls == [frozenset({"portrait", "cafe"})]


def test_prompt_scene_queue_request_forwards_only_runnable_scene_keys() -> None:
    """EditorPanel should forward only scene keys from the authority scene list."""

    mod = _import_epanel_module()
    emitted_keys: list[str] = []
    endpoint_index = PromptEndpointIndex.from_endpoints(
        (
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.POSITIVE,
                node_name="positive_prompt",
                field_key="text",
            ),
            PromptEndpoint(
                cube_alias="Text",
                role=PromptRole.NEGATIVE,
                node_name="negative_prompt",
                field_key="text",
            ),
        )
    )
    fake = SimpleNamespace(
        _last_behavior_snapshot=SimpleNamespace(prompt_endpoint_index=endpoint_index),
        _stack_order=["Text"],
        _cube_states={
            "Text": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "inputs": {"text": "**portrait\none\n**cafe\ncafe"}
                        },
                        "negative_prompt": {
                            "inputs": {"text": "generic\n**hands\nbad hands"}
                        },
                    }
                }
            )
        },
        promptSceneQueueRequested=SimpleNamespace(emit=emitted_keys.append),
    )

    mod.EditorPanel._handle_prompt_scene_queue_requested(fake, "portrait")
    mod.EditorPanel._handle_prompt_scene_queue_requested(fake, "hands")

    assert emitted_keys == ["portrait"]


def test_prompt_scene_queue_request_without_analysis_is_suppressed() -> None:
    """EditorPanel should not forward scene queue requests before analysis is ready."""

    mod = _import_epanel_module()
    emitted_keys: list[str] = []
    fake = SimpleNamespace(
        _last_behavior_snapshot=None,
        _stack_order=[],
        _cube_states={},
        promptSceneQueueRequested=SimpleNamespace(emit=emitted_keys.append),
    )

    mod.EditorPanel._handle_prompt_scene_queue_requested(fake, "portrait")

    assert emitted_keys == []


def test_reorder_cube_widgets_applies_stack_order_and_refreshes_links() -> None:
    """Reorder should rebuild layout order and refresh link/visibility state."""
    mod = _import_epanel_module()

    class _Widget:
        def __init__(self) -> None:
            self.parents: list[object | None] = []

        def setParent(self, parent) -> None:
            self.parents.append(parent)

    widget_a = _Widget()
    widget_b = _Widget()
    layout = _OrderedLayout(
        [
            _LayoutItemForOrder(widget=widget_a),
            _LayoutItemForOrder(spacer=True),
            _LayoutItemForOrder(widget=widget_b),
        ]
    )
    registry_calls: list[str] = []
    fake = SimpleNamespace(
        CUBE_SPACING=mod.EditorPanel.CUBE_SPACING,
        _stack_order=["B", "A"],
        _cube_states=None,
        _layout=layout,
        cube_widgets={"A": widget_a, "B": widget_b},
        meta_registry=SimpleNamespace(
            update_node_link_widgets=lambda: registry_calls.append("node"),
            update_sampler_link_widgets=lambda: registry_calls.append("sampler"),
            update_scheduler_link_widgets=lambda: registry_calls.append("scheduler"),
        ),
        sanitize_prompt_link_state=lambda: registry_calls.append("prompt_state"),
        reconcile_prompt_link_state=lambda **_kwargs: None,
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "recompute"
        ),
    )
    fake._ordered_buffers = lambda: mod.EditorPanel._ordered_buffers(fake)
    fake._refresh_sampler_scheduler_link_state = lambda: (
        mod.EditorPanel._refresh_sampler_scheduler_link_state(fake)
    )
    fake._refresh_link_widgets = lambda: mod.EditorPanel._refresh_link_widgets(fake)

    mod.EditorPanel.reorder_cube_widgets(fake)

    assert layout.added == [
        ("spacing", mod.EditorPanel.CUBE_SPACING),
        ("widget", widget_b),
        ("spacing", mod.EditorPanel.CUBE_SPACING),
        ("widget", widget_a),
    ]
    assert registry_calls == [
        "prompt_state",
        "node",
        "sampler",
        "scheduler",
        "recompute",
    ]


def test_remove_cube_clears_alias_state_and_invalidates_projection() -> None:
    """Removing a cube should clear alias-scoped panel state without touching others."""

    coordinator_mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    removed_widgets: list[object] = []
    runtime_issue_clears: list[str] = []
    visibility_refreshes: list[dict[str, object]] = []
    projection_invalidations: list[str] = []
    meta_registry_calls: list[str] = []
    removed_widget = _Widget()
    kept_widget = _Widget()
    fake = SimpleNamespace(
        cube_widgets={"CubeA": removed_widget, "CubeB": kept_widget},
        cube_sections={"CubeA": removed_widget, "CubeB": kept_widget},
        cube_headers={"CubeA": object(), "CubeB": object()},
        card_wrappers={("CubeA", "node"): object(), ("CubeB", "node"): object()},
        input_widgets_by_field_key={
            ("CubeA", "node", "field"): object(),
            ("CubeB", "node", "field"): object(),
        },
        row_widgets={
            ("CubeA", "node", "field"): object(),
            ("CubeB", "node", "field"): object(),
        },
        col_widgets={
            ("CubeA", "node", "field"): object(),
            ("CubeB", "node", "field"): object(),
        },
        _last_card_decisions={"CubeA": object(), "CubeB": object()},
        _last_hidden_field_keys={
            ("CubeA", "node", "field"),
            ("CubeB", "node", "field"),
        },
        meta_registry=SimpleNamespace(
            remove_node_link_cube=lambda alias: meta_registry_calls.append(alias)
        ),
        clear_cube_runtime_issues=runtime_issue_clears.append,
        _remove_cube_widget_from_layout=removed_widgets.append,
        refresh_node_behavior_state=lambda **kwargs: visibility_refreshes.append(
            dict(kwargs)
        ),
    )
    coordinator = coordinator_mod.EditorPanelProjectionCoordinator(fake)
    coordinator.invalidate_projection = lambda *, reason: (
        projection_invalidations.append(reason)
    )

    coordinator.remove_cube("CubeA")

    assert runtime_issue_clears == ["CubeA"]
    assert removed_widgets == [removed_widget]
    assert fake.cube_widgets == {"CubeB": kept_widget}
    assert fake.cube_sections == {"CubeB": kept_widget}
    assert set(fake.card_wrappers) == {("CubeB", "node")}
    assert set(fake.input_widgets_by_field_key) == {("CubeB", "node", "field")}
    assert fake._last_hidden_field_keys == {("CubeB", "node", "field")}
    assert meta_registry_calls == ["CubeA"]
    assert visibility_refreshes == [
        {"reason": "cube_removed", "use_cached_snapshot": False}
    ]
    assert projection_invalidations == ["cube_removed"]


def test_refresh_link_widgets_for_cube_refreshes_stack_scoped_node_widths() -> None:
    """Cube-scoped refresh should still update all node-link selectors."""

    mod = _import_epanel_module()
    registry_calls: list[tuple[str, str | None]] = []
    fake = SimpleNamespace(
        meta_registry=SimpleNamespace(
            update_node_link_widgets=lambda: registry_calls.append(("node_all", None)),
            update_sampler_link_widgets_for_cube=lambda alias: registry_calls.append(
                ("sampler_cube", alias)
            ),
            update_scheduler_link_widgets_for_cube=lambda alias: registry_calls.append(
                ("scheduler_cube", alias)
            ),
        ),
    )

    mod.EditorPanel.refresh_link_widgets_for_cube(fake, "SDXL/Automask Detailer")

    assert registry_calls == [
        ("node_all", None),
        ("sampler_cube", "SDXL/Automask Detailer"),
        ("scheduler_cube", "SDXL/Automask Detailer"),
    ]


def test_visible_projection_commit_rejects_stale_session_without_revealing() -> None:
    """Visible commits must prove session freshness before mutating widgets."""

    visible_commit_mod = importlib.import_module(
        "substitute.presentation.editor.panel.visible_projection_commit"
    )
    reveal_calls: list[object] = []
    complete_marks: list[object] = []
    finish_calls: list[str] = []
    cancel_calls: list[str] = []
    session = ActiveProjectionSession(
        workflow_id="workflow",
        aliases={"CubeA"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )
    projected_build = ProjectedCubeBuild(
        cube_alias="CubeA",
        final_widget=object(),
        build_session=object(),
        started_at=0.0,
        token=object(),
    )
    ports = visible_commit_mod.EditorVisibleProjectionCommitPorts(
        active_workflow_id=lambda: "workflow",
        panel_is_visible=lambda: True,
        is_projection_session_current=lambda _session: False,
        reveal_projected_cube_builds=lambda builds, workflow_id: reveal_calls.append(
            (workflow_id, tuple(builds))
        ),
        mark_build_complete=lambda alias, token: complete_marks.append((alias, token)),
        mark_build_failed=lambda _alias, _token, _error: None,
    )
    pending = visible_commit_mod.PendingVisibleProjectionCommit(
        workflow_id="workflow",
        projection_session=session,
        projected_builds=(projected_build,),
        finish_refresh=lambda: finish_calls.append("finish"),
        cancel_refresh=cancel_calls.append,
        created_at=0.0,
    )

    committed = visible_commit_mod.EditorVisibleProjectionCommitPipeline(
        ports
    ).commit_visible_projection(pending)

    assert committed is False
    assert reveal_calls == []
    assert complete_marks == []
    assert finish_calls == []
    assert cancel_calls == ["visible_projection_session_stale"]


def test_visible_projection_commit_defers_until_panel_is_active(monkeypatch) -> None:
    """Completed projection builds should publish only after the panel is visible."""

    visible_commit_mod = importlib.import_module(
        "substitute.presentation.editor.panel.visible_projection_commit"
    )
    scheduled_retries: list[tuple[str, int]] = []
    monkeypatch.setattr(
        visible_commit_mod.QTimer,
        "singleShot",
        staticmethod(
            lambda delay, _callback: scheduled_retries.append(
                ("visible_commit_retry", delay)
            )
        ),
    )
    visible = False
    reveal_calls: list[tuple[str, tuple[object, ...]]] = []
    complete_marks: list[tuple[str, object]] = []
    finish_calls: list[str] = []
    cancel_calls: list[str] = []
    session = ActiveProjectionSession(
        workflow_id="workflow",
        aliases={"CubeA"},
        token=object(),
        claimed_completions=[],
        projection_completions=[],
    )
    projected_build = ProjectedCubeBuild(
        cube_alias="CubeA",
        final_widget=object(),
        build_session=object(),
        started_at=0.0,
        token=object(),
    )
    ports = visible_commit_mod.EditorVisibleProjectionCommitPorts(
        active_workflow_id=lambda: "workflow",
        panel_is_visible=lambda: visible,
        is_projection_session_current=lambda _session: True,
        reveal_projected_cube_builds=lambda builds, workflow_id: reveal_calls.append(
            (workflow_id, tuple(builds))
        ),
        mark_build_complete=lambda alias, token: complete_marks.append((alias, token)),
        mark_build_failed=lambda _alias, _token, _error: None,
    )
    pipeline = visible_commit_mod.EditorVisibleProjectionCommitPipeline(ports)

    committed_immediately = pipeline.commit_or_defer(
        workflow_id="workflow",
        projection_session=session,
        projected_builds=(projected_build,),
        finish_refresh=lambda: finish_calls.append("finish"),
        cancel_refresh=cancel_calls.append,
    )
    visible = True
    committed_after_activation = pipeline.finalize_pending_visible_projection()

    assert committed_immediately is False
    assert pipeline.has_pending_visible_projection_commit() is False
    assert committed_after_activation is True
    assert scheduled_retries == [("visible_commit_retry", 0)]
    assert reveal_calls == [("workflow", (projected_build,))]
    assert complete_marks == [("CubeA", projected_build.token)]
    assert finish_calls == ["finish"]
    assert cancel_calls == []


def test_hidden_projection_build_cancels_stale_batch_without_stepping(
    monkeypatch,
) -> None:
    """Hidden staged builds should cancel before work when freshness fails."""

    scheduler_mod = importlib.import_module(
        "substitute.presentation.editor.panel.hidden_build_scheduler"
    )
    models_mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_models"
    )
    scheduled_callbacks: list[object] = []
    monkeypatch.setattr(
        scheduler_mod.QTimer,
        "singleShot",
        staticmethod(lambda _delay, callback: scheduled_callbacks.append(callback)),
    )

    class _BuildSession:
        """Build-session double that records unexpected work."""

        def __init__(self) -> None:
            """Initialize the step counter."""

            self.steps = 0

        def step(self) -> bool:
            """Record a build step and report completion."""

            self.steps += 1
            return True

    build_session = _BuildSession()
    projected_build = models_mod.ProjectedCubeBuild(
        cube_alias="CubeA",
        final_widget=object(),
        build_session=build_session,
        started_at=0.0,
        token=object(),
    )
    completion_calls: list[str] = []
    cancel_calls: list[str] = []
    pipeline = scheduler_mod.HiddenBuildScheduler(
        scheduler_mod.HiddenBuildSchedulerPorts(
            reveal_projected_cube_builds=lambda _builds, workflow_id: None,
            mark_build_complete=lambda _alias, _token: None,
            mark_build_failed=lambda _alias, _token, _reason: None,
        )
    )

    pipeline.schedule_projected_cube_builds(
        (projected_build,),
        on_complete=lambda: completion_calls.append("complete"),
        on_cancel=lambda: cancel_calls.append("cancel"),
        workflow_id="workflow",
        is_current=lambda: False,
    )
    scheduled_callbacks[0]()

    assert build_session.steps == 0
    assert completion_calls == []
    assert cancel_calls == ["cancel"]


def test_load_all_cubes_reuses_widgets_removes_closed_and_recomputes_once(
    monkeypatch,
) -> None:
    """load_all_cubes should reuse widgets, remove closed aliases, and recompute once."""
    mod = _import_epanel_module()

    keep_widget = object()
    old_widget = object()
    new_widget = object()
    layout = _OrderedLayout(
        [
            _LayoutItemForOrder(widget=old_widget),
            _LayoutItemForOrder(widget=keep_widget),
        ]
    )
    removed_widgets: list[object] = []
    built_aliases: list[str] = []
    scrollbar_signal = _Signal()
    scrollbar = SimpleNamespace(valueChanged=scrollbar_signal, value=lambda: 17)
    scroll_updates: list[int] = []
    recompute_calls: list[str] = []
    prompt_calls: list[tuple[str, object]] = []
    widget_refresh_calls: list[str] = []

    cube_keep = SimpleNamespace(buffer={"nodes": {}})
    cube_new = SimpleNamespace(buffer={"nodes": {}})
    fake = SimpleNamespace(
        CUBE_SPACING=mod.EditorPanel.CUBE_SPACING,
        cube_widgets={"Keep": keep_widget, "Old": old_widget},
        card_wrappers={("Old", "Node"): object(), ("Keep", "Node"): object()},
        _layout=layout,
        _cube_states=None,
        _stack_order=None,
        node_definition_gateway=object(),
        sanitize_prompt_link_state=lambda: prompt_calls.append(("sanitize", None)),
        reconcile_prompt_link_state=lambda **kwargs: prompt_calls.append(
            ("reconcile", kwargs)
        ),
        sync_prompt_editor_values_from_buffers=lambda: widget_refresh_calls.append(
            "prompt_values"
        ),
        _refresh_link_widgets=lambda: widget_refresh_calls.append("links"),
        _remove_cube_widget_from_layout=lambda widget: removed_widgets.append(widget),
        _build_cube_widget=lambda alias, _state: (
            built_aliases.append(alias),
            new_widget,
        )[1],
        _build_behavior_snapshot=lambda **_kwargs: None,
        hydrate_node_definitions_for_projection=lambda **_kwargs: None,
        cube_sections={"Keep": keep_widget, "Old": old_widget},
        cube_headers={"Old": object()},
        scroll=SimpleNamespace(verticalScrollBar=lambda: scrollbar),
        _on_scroll_updated=lambda value: scroll_updates.append(value),
        refresh_node_behavior_state=lambda **_kwargs: recompute_calls.append(
            "recompute"
        ),
        _preset_context_refresh=_PresetContextRefreshDouble(),
    )
    fake._ordered_buffers = lambda: mod.EditorPanel._ordered_buffers(fake)
    fake._refresh_sampler_scheduler_link_state = lambda: (
        mod.EditorPanel._refresh_sampler_scheduler_link_state(fake)
    )

    mod.EditorPanel.load_all_cubes(
        fake,
        cube_entries=[("Keep", cube_keep), ("New", cube_new)],
        cube_states={"Keep": cube_keep, "New": cube_new},
        stack_order=["Keep", "New"],
    )

    assert removed_widgets == [old_widget]
    assert built_aliases == ["New"]
    assert ("Old", "Node") not in fake.card_wrappers
    assert fake.cube_sections == {"Keep": keep_widget, "New": new_widget}
    assert fake.cube_headers == {}
    assert layout.added == [
        ("spacing", mod.EditorPanel.CUBE_SPACING),
        ("widget", keep_widget),
        ("spacing", mod.EditorPanel.CUBE_SPACING),
        ("widget", new_widget),
    ]
    assert scroll_updates == [17]
    assert len(scrollbar_signal.connected) == 1
    assert widget_refresh_calls == ["prompt_values", "links"]
    assert prompt_calls == [
        (
            "reconcile",
            {
                "previous_cube_states": None,
                "previous_stack_order": None,
                "cube_states": {"Keep": cube_keep, "New": cube_new},
                "stack_order": ["Keep", "New"],
            },
        ),
    ]
    assert recompute_calls == ["recompute"]


def test_runtime_issue_presentation_applies_and_clears_widget_state() -> None:
    """Runtime issue presentation should update cube widgets and stack severity."""

    from substitute.application.workflows import (
        CubeRuntimeIssue,
        CubeRuntimeIssueKind,
        CubeRuntimeIssueSeverity,
        CubeRuntimeIssueSource,
    )

    mod = _import_epanel_module()
    issue_widget = _IssueWidget()
    stack_calls: list[tuple[str, str | None]] = []
    fake = SimpleNamespace(
        _workflow_id="workflow",
        _stack_order=["CubeA"],
        cube_sections={"CubeA": issue_widget},
        mainwindow=SimpleNamespace(
            cube_stacks={
                "workflow": SimpleNamespace(
                    setTabIssueSeverity=lambda alias, severity: stack_calls.append(
                        (alias, severity)
                    )
                )
            }
        ),
    )
    issue = CubeRuntimeIssue(
        workflow_id="workflow",
        cube_alias="CubeA",
        source=CubeRuntimeIssueSource.PROJECTION,
        severity=CubeRuntimeIssueSeverity.ERROR,
        kind=CubeRuntimeIssueKind.MISSING_LIVE_NODE_DEFINITION,
        message="Missing loader",
        operation="projection",
    )

    mod.EditorPanel.set_cube_runtime_issues(fake, "CubeA", (issue,))
    mod.EditorPanel.clear_cube_runtime_issues(fake, "CubeA")

    assert issue_widget.severity is None
    assert issue_widget.messages == ()
    assert stack_calls == [("CubeA", "error"), ("CubeA", None)]


def test_editor_panel_build_node_card_uses_node_card_builder_constructor_surface(
    monkeypatch,
) -> None:
    """EditorPanel should not pass panel-only services into NodeCardBuilder."""

    mod = _import_epanel_module()
    monkeypatch.setattr(mod, "NodeCardBuilder", _StrictNodeCardBuilder)
    fake = SimpleNamespace(
        node_definition_gateway=object(),
        prompt_autocomplete_gateway=object(),
        prompt_wildcard_catalog_gateway=object(),
        danbooru_url_import_service=object(),
        danbooru_wiki_service=object(),
        danbooru_image_preview_service=object(),
        danbooru_recent_posts_service=object(),
        prompt_lora_catalog_service=object(),
        scheduled_lora_provider=object(),
        prompt_scheduled_lora_service=object(),
        model_catalog_service=object(),
        model_choice_snapshot_controller=object(),
        thumbnail_asset_repository=object(),
        model_choice_resolver=object(),
        dimension_preset_source=object(),
        node_input_preset_source=object(),
        prompt_segment_preset_source=object(),
        _preset_context_refresh=_PresetContextRefreshDouble(),
    )
    fake._services = mod.EditorPanelServiceBundle(
        node_definition_gateway=fake.node_definition_gateway,
        node_behavior_service=object(),
        prompt=mod.EditorPanelPromptServiceBundle(
            autocomplete_gateway=fake.prompt_autocomplete_gateway,
            wildcard_catalog_gateway=fake.prompt_wildcard_catalog_gateway,
            scheduled_lora_provider=fake.scheduled_lora_provider,
            scheduled_lora_service=fake.prompt_scheduled_lora_service,
            lora_catalog_service=fake.prompt_lora_catalog_service,
            danbooru_url_import_service=fake.danbooru_url_import_service,
            danbooru_wiki_service=fake.danbooru_wiki_service,
            danbooru_image_preview_service=fake.danbooru_image_preview_service,
            danbooru_recent_posts_service=fake.danbooru_recent_posts_service,
            spellcheck_service=None,
            feature_profile_service=None,
            thumbnail_asset_repository=fake.thumbnail_asset_repository,
        ),
        model=mod.EditorPanelModelServiceBundle(
            catalog_service=fake.model_catalog_service,
            choice_resolver=fake.model_choice_resolver,
            thumbnail_asset_repository=fake.thumbnail_asset_repository,
        ),
        presets=mod.EditorPanelPresetServiceBundle(user_preset_service=None),
    )

    node_card = mod.EditorPanel.build_node_card(
        fake,
        node_name="prompt",
        inputs={},
        node_type="CLIPTextEncode",
        field_specs={},
        cube_state={},
        resolved_behavior=object(),
        display_decision=None,
        alias="Cube",
    )

    assert node_card == "node-card"
    assert isinstance(fake._node_card_builder, _StrictNodeCardBuilder)


def test_editor_panel_prepares_node_card_prompt_inputs(monkeypatch) -> None:
    """EditorPanel should prepare prompt context before invoking NodeCardBuilder."""

    mod = _import_epanel_module()
    monkeypatch.setattr(mod, "NodeCardBuilder", _StrictNodeCardBuilder)
    prompt_feature_profile = PromptEditorFeatureProfile.enabled_profile(())
    prompt_syntax_profile = PromptSyntaxProfile(enabled_syntaxes=())
    prompt_field_profile = PanelPromptFieldProfileDecision(
        feature_profile=prompt_feature_profile,
        syntax_profile=prompt_syntax_profile,
    )
    scheduled_lora_calls: list[tuple[str | None, str, str]] = []
    prompt_profile_calls: list[tuple[str | None, str, str, dict[str, object]]] = []

    def scheduled_lora_resolver(_text: str) -> tuple[object, ...]:
        """Return no scheduled LoRAs for the prepared resolver sentinel."""

        return ()

    def scheduled_lora_resolver_for_prompt(
        alias: str | None,
        node_name: str,
        field_key: str,
    ) -> object:
        """Record scheduled-LoRA resolver preparation."""

        scheduled_lora_calls.append((alias, node_name, field_key))
        return scheduled_lora_resolver

    def prompt_field_profile_for_prompt(
        alias: str | None,
        node_name: str,
        field_key: str,
        field_style: dict[str, object],
    ) -> PanelPromptFieldProfileDecision:
        """Record prompt field-profile preparation."""

        prompt_profile_calls.append((alias, node_name, field_key, dict(field_style)))
        return prompt_field_profile

    fake = SimpleNamespace(
        node_definition_gateway=object(),
        prompt_autocomplete_gateway=object(),
        prompt_wildcard_catalog_gateway=object(),
        danbooru_url_import_service=object(),
        danbooru_wiki_service=object(),
        danbooru_image_preview_service=object(),
        danbooru_recent_posts_service=object(),
        prompt_lora_catalog_service=object(),
        scheduled_lora_provider=object(),
        prompt_scheduled_lora_service=object(),
        model_catalog_service=object(),
        model_choice_snapshot_controller=object(),
        thumbnail_asset_repository=object(),
        model_choice_resolver=object(),
        dimension_preset_source=object(),
        node_input_preset_source=object(),
        prompt_segment_preset_source=object(),
        _preset_context_refresh=_PresetContextRefreshDouble(),
        scheduled_lora_resolver_for_prompt=scheduled_lora_resolver_for_prompt,
        prompt_field_profile_for_prompt=prompt_field_profile_for_prompt,
    )
    fake._services = mod.EditorPanelServiceBundle(
        node_definition_gateway=fake.node_definition_gateway,
        node_behavior_service=object(),
        prompt=mod.EditorPanelPromptServiceBundle(
            autocomplete_gateway=fake.prompt_autocomplete_gateway,
            wildcard_catalog_gateway=fake.prompt_wildcard_catalog_gateway,
            scheduled_lora_provider=fake.scheduled_lora_provider,
            scheduled_lora_service=fake.prompt_scheduled_lora_service,
            lora_catalog_service=fake.prompt_lora_catalog_service,
            danbooru_url_import_service=fake.danbooru_url_import_service,
            danbooru_wiki_service=fake.danbooru_wiki_service,
            danbooru_image_preview_service=fake.danbooru_image_preview_service,
            danbooru_recent_posts_service=fake.danbooru_recent_posts_service,
            spellcheck_service=None,
            feature_profile_service=None,
            thumbnail_asset_repository=fake.thumbnail_asset_repository,
        ),
        model=mod.EditorPanelModelServiceBundle(
            catalog_service=fake.model_catalog_service,
            choice_resolver=fake.model_choice_resolver,
            thumbnail_asset_repository=fake.thumbnail_asset_repository,
        ),
        presets=mod.EditorPanelPresetServiceBundle(user_preset_service=None),
    )
    field_behavior = FieldBehavior(
        field_key="text",
        presentation=FieldPresentation.PROMPT_BOX,
        style={"prompt_syntaxes": ["wildcard"]},
    )
    field_spec = ResolvedFieldSpec(
        cube_alias="Cube",
        node_name="prompt",
        class_type="CLIPTextEncode",
        field_key="text",
        field_type="STRING",
        constraints={},
        meta_info={},
        field_info=None,
        value="prompt text",
        field_behavior=field_behavior,
    )

    node_card = mod.EditorPanel.build_node_card(
        fake,
        node_name="prompt",
        inputs={"text": "prompt text"},
        node_type="CLIPTextEncode",
        field_specs={"text": field_spec},
        cube_state={},
        resolved_behavior=object(),
        display_decision=None,
        alias="Cube",
    )

    assert node_card == "node-card"
    assert scheduled_lora_calls == [("Cube", "prompt", "text")]
    assert prompt_profile_calls == [
        ("Cube", "prompt", "text", {"prompt_syntaxes": ["wildcard"]})
    ]
    prompt_inputs = fake._node_card_builder.calls[0]["prompt_field_inputs"]
    assert prompt_inputs["text"].scheduled_lora_resolver is scheduled_lora_resolver
    assert prompt_inputs["text"].prompt_field_profile is prompt_field_profile
    assert prompt_inputs["text"].prompt_field_profile.feature_profile is (
        prompt_feature_profile
    )
    assert prompt_inputs["text"].prompt_field_profile.syntax_profile is (
        prompt_syntax_profile
    )


def test_sync_prompt_editor_values_from_buffers_restores_reused_prompt_widgets(
    monkeypatch,
) -> None:
    """Prompt editor sync should push reconciled buffer text into reused widgets."""

    mod = _import_epanel_module()
    field_state_mod = importlib.import_module(
        "substitute.presentation.editor.panel.field_state_controller"
    )

    class _PromptEditor:
        def __init__(self, metadata: dict[str, str], text: str) -> None:
            self._metadata = metadata
            self._text = text

        def property(self, name: str):
            if name == "input_metadata":
                return self._metadata
            return None

        def toPlainText(self) -> str:
            return self._text

        def setPlainText(self, text: str) -> None:
            self._text = text

    class _CubeWidget:
        def __init__(self, prompt_editor: _PromptEditor) -> None:
            self._prompt_editor = prompt_editor

        def findChildren(self, cls):
            if cls is _PromptEditor:
                return [self._prompt_editor]
            return []

    monkeypatch.setattr(field_state_mod, "PromptEditor", _PromptEditor)
    prompt_editor = _PromptEditor(
        {
            "cube_alias": "CubeA",
            "node_name": "positive_prompt",
            "key": "prompt_template",
        },
        "stale",
    )
    fake = SimpleNamespace(
        _cube_states={
            "CubeA": SimpleNamespace(
                buffer={
                    "nodes": {
                        "positive_prompt": {
                            "inputs": {"prompt_template": "fresh shared prompt"}
                        }
                    }
                }
            )
        },
        cube_widgets={"CubeA": _CubeWidget(prompt_editor)},
        refresh_prompt_scene_diagnostics=lambda: None,
    )

    mod.EditorPanel.sync_prompt_editor_values_from_buffers(fake)

    assert prompt_editor.toPlainText() == "fresh shared prompt"


def test_rename_cube_updates_maps_cleans_widgets_and_refreshes_links(
    monkeypatch,
) -> None:
    """rename_cube should migrate map keys and clean stale link widgets for old alias."""
    mod = _import_epanel_module()
    coordinator_mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    lifecycle_mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_lifecycle"
    )
    registry_mod = importlib.import_module(
        "substitute.presentation.editor.panel.cube_registry"
    )

    monkeypatch.setattr(mod, "isValid", lambda _obj: True)
    monkeypatch.setattr(
        registry_mod,
        "cube_section_title",
        lambda alias, _cube_state: f"Pretty {alias}",
    )

    link_calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        lifecycle_mod,
        "update_prompt_link_references_on_rename",
        lambda buffers, old, new: link_calls.append(
            (
                "prompt_refs",
                (buffers, old, new),
            )
        ),
    )
    monkeypatch.setattr(
        lifecycle_mod,
        "update_sampler_link_references_on_rename",
        lambda buffers, old, new: link_calls.append(
            (
                "sampler_refs",
                (buffers, old, new),
            )
        ),
    )
    monkeypatch.setattr(
        lifecycle_mod,
        "update_scheduler_link_references_on_rename",
        lambda buffers, old, new: link_calls.append(
            (
                "scheduler_refs",
                (buffers, old, new),
            )
        ),
    )
    monkeypatch.setattr(
        lifecycle_mod,
        "update_node_link_references_on_rename",
        lambda buffers, old, new: link_calls.append(
            (
                "node_refs",
                (buffers, old, new),
            )
        ),
    )

    class _Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:
            self.text = text

    class _Combo:
        def __init__(self) -> None:
            self.parents: list[object | None] = []
            self.deleted = False

        def setParent(self, parent) -> None:
            self.parents.append(parent)

        def deleteLater(self) -> None:
            self.deleted = True

    label = _Label()
    stale_node = _Combo()
    stale_sampler = _Combo()
    stale_scheduler = _Combo()
    card_wrapper = _Widget()
    row_widget = _Widget(
        props={"input_metadata": {"cube_alias": "old", "node_name": "n", "key": "k"}}
    )
    col_widget = _Widget(
        props={"input_metadata": {"cube_alias": "old", "node_name": "n", "key": "k"}}
    )

    cube_old = SimpleNamespace(buffer={"nodes": {}})
    cube_other = SimpleNamespace(buffer={"nodes": {}})
    registry_calls: list[str] = []
    cube_section = object()
    fake = SimpleNamespace(
        cube_headers={"old": label},
        cube_positions={"old": 12},
        cube_widgets={"old": object()},
        cube_sections={"old": cube_section},
        _cube_visibility_btns={"old": object()},
        _cube_visibility_menus={"old": object()},
        _cube_states={"old": cube_old, "other": cube_other},
        _stack_order=["old", "other"],
        node_definition_gateway=object(),
        node_link_widgets={("old", "vectorscopecc"): stale_node},
        node_link_title_surfaces={("old", "vectorscopecc"): object()},
        sampler_link_widgets={("old", "ksampler"): stale_sampler},
        scheduler_link_widgets={("old", "ksampler"): stale_scheduler},
        row_widgets={("old", "n", "k"): (None, row_widget)},
        col_widgets={("old", "n", "k"): (None, col_widget, object())},
        card_wrappers={("old", "n"): card_wrapper},
        meta_registry=SimpleNamespace(
            rename_node_link_alias=lambda old, new: registry_calls.append(
                f"node_rename:{old}->{new}"
            ),
            update_node_link_widgets=lambda: registry_calls.append("node"),
            update_sampler_link_widgets=lambda: registry_calls.append("sampler"),
            update_scheduler_link_widgets=lambda: registry_calls.append("scheduler"),
        ),
        sanitize_prompt_link_state=lambda: registry_calls.append("prompt_state"),
        refresh_node_behavior_state=lambda **_kwargs: registry_calls.append(
            "recompute"
        ),
    )
    fake._ordered_buffers = lambda: mod.EditorPanel._ordered_buffers(fake)
    fake._refresh_sampler_scheduler_link_state = lambda: (
        mod.EditorPanel._refresh_sampler_scheduler_link_state(fake)
    )
    fake._refresh_link_widgets = lambda: mod.EditorPanel._refresh_link_widgets(fake)
    fake._cube_registry_controller = lambda: registry_mod.EditorCubeRegistry(fake)

    coordinator_mod.EditorPanelProjectionCoordinator(fake).rename_cube("old", "new")

    assert label.text == "Pretty new"
    assert "old" not in fake.cube_headers
    assert fake.cube_headers["new"] is label
    assert "old" not in fake.cube_sections
    assert fake.cube_sections["new"] is cube_section
    assert fake._stack_order == ["new", "other"]
    assert "old" not in fake._cube_states
    assert "new" in fake._cube_states
    assert ("new", "n", "k") in fake.row_widgets
    assert ("old", "n", "k") not in fake.row_widgets
    assert row_widget.property("input_metadata")["cube_alias"] == "new"
    assert ("new", "n", "k") in fake.col_widgets
    assert ("old", "n", "k") not in fake.col_widgets
    assert col_widget.property("input_metadata")["cube_alias"] == "new"
    assert ("new", "n") in fake.card_wrappers
    assert ("old", "n") not in fake.card_wrappers
    assert card_wrapper.property("cube_alias") == "new"
    assert ("new", "ksampler") in fake.sampler_link_widgets
    assert ("old", "ksampler") not in fake.sampler_link_widgets
    assert ("new", "ksampler") in fake.scheduler_link_widgets
    assert ("old", "ksampler") not in fake.scheduler_link_widgets
    assert stale_sampler.deleted is False
    assert stale_scheduler.deleted is False
    assert registry_calls == [
        "node_rename:old->new",
        "prompt_state",
        "node",
        "sampler",
        "scheduler",
        "recompute",
    ]
    assert [name for name, _payload in link_calls] == [
        "prompt_refs",
        "node_refs",
        "sampler_refs",
        "scheduler_refs",
    ]


def test_refresh_cube_header_delegates_to_registry_controller() -> None:
    """EditorPanel should expose the header refresh hook used by shell cube actions."""

    mod = _import_epanel_module()

    class _Label:
        def __init__(self) -> None:
            self.text = ""

        def setText(self, text: str) -> None:
            self.text = text

    label = _Label()
    cube_state = SimpleNamespace(buffer={"nodes": {}}, bypassed=True)
    fake = SimpleNamespace(
        cube_headers={"SDXL/Automask Detailer": label},
        cube_positions={},
        cube_widgets={},
        cube_sections={},
        row_widgets={},
        col_widgets={},
        input_widgets_by_field_key={},
        card_wrappers={},
        sampler_link_widgets={},
        scheduler_link_widgets={},
        _cube_visibility_btns={},
        _cube_visibility_menus={},
        _cube_states={"SDXL/Automask Detailer": cube_state},
        _stack_order=["SDXL/Automask Detailer"],
        _node_card_mode_controller=SimpleNamespace(),
    )

    mod.EditorPanel.refresh_cube_header(fake, "SDXL/Automask Detailer")

    assert label.text == "SDXL/Automask Detailer (bypassed)"


def test_clear_layout_resets_reveal_maps_and_deletes_layout_widgets(
    monkeypatch,
) -> None:
    """clear_layout should drop reveal registries and dispose tracked layout items."""

    coordinator_mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_coordinator"
    )
    lifecycle_mod = importlib.import_module(
        "substitute.presentation.editor.panel.projection_lifecycle"
    )
    debug_calls: list[tuple[str, dict[str, object]]] = []
    monkeypatch.setattr(
        lifecycle_mod,
        "log_debug",
        lambda _logger, message, **context: debug_calls.append((message, context)),
    )
    deleted_widget = _DisposableWidget()
    nested_layout = object()
    recursive_calls: list[object] = []
    cleanup_calls: list[str] = []
    fake = SimpleNamespace(
        cube_widgets={"CubeA": object()},
        cube_sections={"CubeA": object()},
        meta_registry=SimpleNamespace(
            cleanup_dead_node_link_widgets=lambda: cleanup_calls.append("node"),
            clear_node_link_title_surfaces=lambda: cleanup_calls.append("surfaces"),
        ),
        node_link_widgets={("CubeA", "identity"): object()},
        node_link_title_surfaces={("CubeA", "identity"): object()},
        row_widgets={"row": object()},
        col_widgets={"col": object()},
        input_widgets_by_field_key={("CubeA", "NodeA", "seed"): object()},
        card_wrappers={("CubeA", "NodeA"): object()},
        _cube_visibility_btns={"CubeA": object()},
        _cube_visibility_menus={"CubeA": object()},
        _layout=_ClearLayout(
            [
                _ClearLayoutItem(widget=deleted_widget),
                _ClearLayoutItem(layout=nested_layout),
            ]
        ),
        cube_headers={"CubeA": object()},
        cube_positions={"CubeA": 12},
        _stack_order=["CubeA"],
        _cube_states={},
        _clear_layout_recursive=lambda layout: recursive_calls.append(layout),
        clear_model_field_load_progress=lambda: cleanup_calls.append("models"),
    )

    coordinator_mod.EditorPanelProjectionCoordinator(fake).clear_layout()

    assert cleanup_calls == ["models", "node", "surfaces"]
    assert fake.cube_widgets == {}
    assert fake.cube_sections == {}
    assert fake.node_link_widgets == {}
    assert fake.node_link_title_surfaces == {}
    assert fake.row_widgets == {}
    assert fake.col_widgets == {}
    assert fake.input_widgets_by_field_key == {}
    assert fake.card_wrappers == {}
    assert fake._cube_visibility_btns == {}
    assert fake._cube_visibility_menus == {}
    assert fake.cube_headers == {}
    assert fake.cube_positions == {}
    assert deleted_widget.deleted is True
    assert recursive_calls == [nested_layout]
    assert debug_calls == [
        (
            "Clearing editor panel layout",
            {
                "card_wrapper_count": 1,
                "cube_position_count": 1,
                "cube_visibility_button_count": 1,
                "cube_visibility_menu_count": 1,
                "cube_widget_count": 1,
                "cube_header_count": 1,
                "node_link_widget_count": 1,
            },
        ),
        (
            "Cleared editor panel layout",
            {
                "card_wrapper_count": 0,
                "cube_position_count": 0,
                "cube_visibility_button_count": 0,
                "cube_visibility_menu_count": 0,
                "cube_widget_count": 0,
                "cube_header_count": 0,
                "node_link_widget_count": 0,
            },
        ),
    ]


def test_card_wrapper_cleanup_ignores_stale_wrapper() -> None:
    """Destroyed stale wrappers must not remove a newer registry owner."""

    mod = _import_epanel_module()
    fake = SimpleNamespace(card_wrappers={})
    wrapper_a = object()
    wrapper_b = object()

    mod.EditorPanel.register_card_wrapper(fake, "Cube", "vae_override", wrapper_a)
    mod.EditorPanel.register_card_wrapper(fake, "Cube", "vae_override", wrapper_b)
    mod.EditorPanel.remove_card_wrapper_if_current(
        fake,
        "Cube",
        "vae_override",
        wrapper_a,
    )

    assert fake.card_wrappers[("Cube", "vae_override")] is wrapper_b

    mod.EditorPanel.remove_card_wrapper_if_current(
        fake,
        "Cube",
        "vae_override",
        wrapper_b,
    )

    assert ("Cube", "vae_override") not in fake.card_wrappers


def test_card_wrapper_cleanup_ignores_unknown_key() -> None:
    """Removing a non-current wrapper should be a no-op for unrelated entries."""

    mod = _import_epanel_module()
    wrapper = object()
    fake = SimpleNamespace(card_wrappers={("Other", "node"): wrapper})

    mod.EditorPanel.remove_card_wrapper_if_current(
        fake,
        "Cube",
        "vae_override",
        object(),
    )

    assert fake.card_wrappers == {("Other", "node"): wrapper}


def test_model_field_load_progress_routes_only_to_model_picker(
    monkeypatch,
    caplog,
) -> None:
    """EditorPanel should dispatch model-load progress through indexed model pickers."""

    caplog.set_level(logging.INFO)
    mod = _import_epanel_module()

    class _ModelPicker:
        def __init__(self) -> None:
            self.calls: list[tuple[float | None, bool]] = []

        def set_model_load_progress(
            self,
            *,
            percent: float | None,
            active: bool,
        ) -> None:
            self.calls.append((percent, active))

    monkeypatch.setattr(mod, "ModelPickerField", _ModelPicker)
    picker = _ModelPicker()
    widget_map = {
        ("Cube", "checkpoint", "ckpt_name"): picker,
        ("Cube", "sampler", "steps"): object(),
    }
    fake = SimpleNamespace(
        _field_registry=SimpleNamespace(widget_map=widget_map),
        input_widgets_by_field_key=widget_map,
    )

    mod.EditorPanel.set_model_field_load_progress(
        fake,
        cube_alias="Cube",
        node_name="checkpoint",
        field_key="ckpt_name",
        percent=37.5,
        active=True,
    )
    mod.EditorPanel.set_model_field_load_progress(
        fake,
        cube_alias="Cube",
        node_name="sampler",
        field_key="steps",
        percent=37.5,
        active=True,
    )
    mod.EditorPanel.set_model_field_load_progress(
        fake,
        cube_alias="Missing",
        node_name="checkpoint",
        field_key="ckpt_name",
        percent=37.5,
        active=True,
    )

    assert picker.calls == [(37.5, True)]
    assert "Applied model-load progress to model picker" in caplog.text
    assert "Model-load progress target widget is not a model picker" in caplog.text
    assert "Model-load progress target widget was not found" in caplog.text


def test_clear_model_field_load_progress_clears_tracked_model_pickers(
    monkeypatch,
) -> None:
    """EditorPanel cleanup should clear every tracked model picker once."""

    mod = _import_epanel_module()

    class _ModelPicker:
        def __init__(self) -> None:
            self.calls: list[tuple[float | None, bool]] = []

        def set_model_load_progress(
            self,
            *,
            percent: float | None,
            active: bool,
        ) -> None:
            self.calls.append((percent, active))

    monkeypatch.setattr(mod, "ModelPickerField", _ModelPicker)
    picker = _ModelPicker()
    widget_map = {
        ("Cube", "checkpoint", "ckpt_name"): picker,
        ("Cube", "checkpoint", "alt"): picker,
        ("Cube", "sampler", "steps"): object(),
    }
    fake = SimpleNamespace(
        _field_registry=SimpleNamespace(widget_map=widget_map),
        input_widgets_by_field_key=widget_map,
    )

    mod.EditorPanel.clear_model_field_load_progress(fake)

    assert picker.calls == [(None, False)]


def test_refresh_model_metadata_for_event_delegates_to_model_pickers(
    monkeypatch,
) -> None:
    """EditorPanel should target model picker refreshes for metadata events."""

    from substitute.application.model_metadata import ModelMetadataRefreshEvent

    mod = _import_epanel_module()

    class _ModelPicker:
        def __init__(self, refreshed: bool) -> None:
            self.refreshed = refreshed
            self.events: list[ModelMetadataRefreshEvent] = []

        def refresh_metadata_for_event(
            self,
            event: ModelMetadataRefreshEvent,
        ) -> bool:
            self.events.append(event)
            return self.refreshed

    monkeypatch.setattr(mod, "ModelPickerField", _ModelPicker)
    event = ModelMetadataRefreshEvent(
        kind="checkpoints",
        value="models/base.safetensors",
        relative_path="models/base.safetensors",
        sha256="ABC123",
        provider_status="found",
    )
    refreshed_picker = _ModelPicker(True)
    deferred_picker = _ModelPicker(False)
    fake = SimpleNamespace(
        _field_registry=SimpleNamespace(
            entries=lambda: (
                SimpleNamespace(widget=refreshed_picker),
                SimpleNamespace(widget=deferred_picker),
            )
        ),
        _preset_context_refresh=_PresetContextRefreshDouble(),
    )

    refreshed_count = mod.EditorPanel.refresh_model_metadata_for_event(fake, event)

    assert refreshed_count == 1
    assert refreshed_picker.events == [event]
    assert deferred_picker.events == [event]


def test_refresh_visible_lora_metadata_counts_dirty_visible_prompt_editors(
    monkeypatch,
) -> None:
    """EditorPanel should count only prompt editors that refresh lazily."""

    mod = _import_epanel_module()
    lora_mod = importlib.import_module(
        "substitute.presentation.editor.panel.lora_metadata_refresh_controller"
    )

    class _PromptEditor:
        def __init__(self, refreshed: bool) -> None:
            self.refreshed = refreshed
            self.calls = 0

        def refresh_lora_metadata_if_visible(self) -> bool:
            self.calls += 1
            return self.refreshed

    monkeypatch.setattr(lora_mod, "PromptEditor", _PromptEditor)
    visible_editor = _PromptEditor(True)
    hidden_editor = _PromptEditor(False)
    fake = SimpleNamespace(
        findChildren=lambda cls: (
            [visible_editor, hidden_editor] if cls is _PromptEditor else []
        )
    )

    refreshed_count = mod.EditorPanel.refresh_visible_lora_metadata(fake)

    assert refreshed_count == 1
    assert visible_editor.calls == 1
    assert hidden_editor.calls == 1


def test_mark_lora_metadata_dirty_marks_prompt_editors(
    monkeypatch,
) -> None:
    """EditorPanel dirty marking should not rebuild prompt projection state."""

    mod = _import_epanel_module()
    lora_mod = importlib.import_module(
        "substitute.presentation.editor.panel.lora_metadata_refresh_controller"
    )

    class _PromptEditor:
        def __init__(self) -> None:
            self.mark_calls = 0

        def mark_lora_metadata_dirty(self) -> None:
            self.mark_calls += 1

    monkeypatch.setattr(lora_mod, "PromptEditor", _PromptEditor)
    first_editor = _PromptEditor()
    second_editor = _PromptEditor()
    fake = SimpleNamespace(
        findChildren=lambda cls: (
            [first_editor, second_editor] if cls is _PromptEditor else []
        )
    )

    mod.EditorPanel.mark_lora_metadata_dirty(fake)

    assert first_editor.mark_calls == 1
    assert second_editor.mark_calls == 1


def test_search_and_select_cycles_matches_and_updates_scroll_targets() -> None:
    """search_and_select should cycle precomputed navigation matches in stable order."""

    mod = _import_epanel_module()
    search_mod = importlib.import_module(
        "substitute.presentation.editor.panel.search_controller"
    )

    class _LineEdit:
        def __init__(self) -> None:
            self.selections: list[tuple[int, int]] = []
            self.deselect_count = 0

        def setSelection(self, start: int, length: int) -> None:
            self.selections.append((start, length))

        def deselect(self) -> None:
            self.deselect_count += 1

    w1 = _LineEdit()
    w2 = _LineEdit()
    matches = (
        TextSearchMatch("CubeA", "NodeA", "field_a", 4, 3),
        TextSearchMatch("CubeA", "NodeA", "field_b", 0, 3),
    )
    cube_scroll_calls: list[tuple[str, bool]] = []
    widget_scroll_calls: list[tuple[object, bool]] = []
    fake = SimpleNamespace(
        input_widgets_by_field_key={
            ("CubeA", "NodeA", "field_a"): w1,
            ("CubeA", "NodeA", "field_b"): w2,
        },
        scroll_to_cube=lambda alias, animated=True: cube_scroll_calls.append(
            (
                alias,
                animated,
            )
        ),
        scroll_to_input_widget=lambda widget, animated=True: widget_scroll_calls.append(
            (widget, animated)
        ),
    )
    controller = search_mod.EditorPanelSearchController(fake)
    controller._navigation = search_mod.PanelSearchNavigationState(
        matches=matches,
        index=-1,
        needle="dog",
    )
    controller._publish_search_state()
    fake._search_controller = controller

    mod.EditorPanel.search_and_select(fake, "dog", direction="next")
    mod.EditorPanel.search_and_select(fake, "dog", direction="next")
    mod.EditorPanel.search_and_select(fake, "", direction="next")

    assert w1.selections[0] == (4, 3)
    assert w2.selections[0] == (0, 3)
    assert fake._current_search == {"matches": (), "index": -1, "needle": ""}
    assert cube_scroll_calls[:2] == [("CubeA", True), ("CubeA", True)]
    assert widget_scroll_calls[0][0] is w1
    assert widget_scroll_calls[1][0] is w2
    assert w1.deselect_count >= 1
    assert w2.deselect_count >= 1


def test_search_and_select_includes_prompt_widgets_and_clears_prompt_selection(
    monkeypatch,
) -> None:
    """Prompt-widget navigation should use cursor selection and clear prompt state."""

    mod = _import_epanel_module()
    search_mod = importlib.import_module(
        "substitute.presentation.editor.panel.search_controller"
    )

    class _PromptCursor:
        def __init__(self) -> None:
            self.selection_start = 0
            self.selection_length = 0
            self.clear_count = 0

        def setPosition(self, pos: int, _mode=None) -> None:
            self.selection_start = pos
            self.selection_length = 0

        def movePosition(self, _direction, _mode=None, length: int = 0) -> None:
            self.selection_length = length

        def clearSelection(self) -> None:
            self.selection_length = 0
            self.clear_count += 1

    class _PromptEditor:
        def __init__(self) -> None:
            self._cursor = _PromptCursor()
            self.applied_selections: list[tuple[int, int]] = []
            self.clear_count = 0

        def textCursor(self) -> _PromptCursor:
            return self._cursor

        def setTextCursor(self, cursor: _PromptCursor) -> None:
            self._cursor = cursor
            self.applied_selections.append(
                (
                    cursor.selection_start,
                    cursor.selection_length,
                )
            )
            self.clear_count = cursor.clear_count

        def clear_search_matches(self) -> None:
            pass

    monkeypatch.setattr(search_mod, "PromptEditor", _PromptEditor)
    monkeypatch.setattr(
        search_mod,
        "QTextCursor",
        SimpleNamespace(
            MoveOperation=SimpleNamespace(Right="right"),
            MoveMode=SimpleNamespace(KeepAnchor="keep"),
        ),
    )

    prompt = _PromptEditor()

    cube_scroll_calls: list[tuple[str, bool]] = []
    widget_scroll_calls: list[tuple[object, bool]] = []
    fake = SimpleNamespace(
        input_widgets_by_field_key={("CubeA", "NodeA", "prompt_template"): prompt},
        scroll_to_cube=lambda alias, animated=True: cube_scroll_calls.append(
            (
                alias,
                animated,
            )
        ),
        scroll_to_input_widget=lambda widget, animated=True: widget_scroll_calls.append(
            (widget, animated)
        ),
    )
    controller = search_mod.EditorPanelSearchController(fake)
    controller._navigation = search_mod.PanelSearchNavigationState(
        matches=(TextSearchMatch("CubeA", "NodeA", "prompt_template", 4, 3),),
        index=-1,
        needle="dog",
    )
    controller._publish_search_state()
    fake._search_controller = controller

    mod.EditorPanel.search_and_select(fake, "dog", direction="next")

    assert fake._current_search["needle"] == "dog"
    assert prompt.applied_selections[-1] == (4, 3)
    assert cube_scroll_calls == [("CubeA", True)]
    assert widget_scroll_calls == [(prompt, True)]

    mod.EditorPanel.search_and_select(fake, "", direction="next")

    assert prompt.clear_count >= 1
    assert fake._current_search == {"matches": (), "index": -1, "needle": ""}


def test_text_search_refresh_recomputes_prompt_highlight_offsets(
    monkeypatch,
) -> None:
    """Refreshing active text search should rebuild prompt ranges after edits."""

    search_mod = importlib.import_module(
        "substitute.presentation.editor.panel.search_controller"
    )

    class _PromptEditor:
        """Prompt editor double that records rendered search ranges."""

        def __init__(self) -> None:
            """Initialize recorded search state."""

            self.search_calls: list[tuple[tuple[tuple[int, int], ...], int | None]] = []
            self.clear_count = 0
            self.cursor_updates = 0

        def clear_search_matches(self) -> None:
            """Record transient search rendering clearing."""

            self.clear_count += 1

        def set_search_matches(
            self,
            matches: tuple[tuple[int, int], ...],
            active_index: int | None,
            *,
            query_identity: object | None = None,
        ) -> None:
            """Record rendered search ranges."""

            self.last_query_identity = query_identity
            self.search_calls.append((matches, active_index))

        def setTextCursor(self, _cursor: object) -> None:
            """Record cursor mutation attempts."""

            self.cursor_updates += 1

    monkeypatch.setattr(search_mod, "PromptEditor", _PromptEditor)
    service = EditorSearchService()
    query = service.build_query(mode=EditorSearchMode.TEXT, raw_text="dog")
    initial_result = service.build_result(
        build_behavior_snapshot(
            cube_states={
                "A": cube_state(
                    nodes={
                        "NodeA": {
                            "class_type": "PromptNode",
                            "inputs": {"prompt_template": "dog alpha"},
                        }
                    }
                )
            },
            stack_order=["A"],
        ),
        query,
    )
    updated_snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "NodeA": {
                        "class_type": "PromptNode",
                        "inputs": {"prompt_template": "xxdog alpha"},
                    }
                }
            )
        },
        stack_order=["A"],
    )
    prompt = _PromptEditor()
    node_behavior_service = SimpleNamespace(
        build_snapshot=lambda **_kwargs: updated_snapshot
    )
    panel = SimpleNamespace(
        input_widgets_by_field_key={("A", "NodeA", "prompt_template"): prompt},
        _stack_order=["A"],
        _cube_states={"A": object()},
        node_behavior_service=node_behavior_service,
        _workflow_overrides=lambda: {},
    )
    controller = search_mod.EditorPanelSearchController(panel)
    controller._current_search_result = initial_result
    controller._navigation = search_mod.PanelSearchNavigationState(
        matches=initial_result.navigation_matches,
        index=0,
        needle="dog",
    )
    controller._publish_search_state()

    controller.refresh_editor_search_result_after_text_change()

    assert prompt.clear_count == 1
    assert prompt.search_calls == [(((2, 3),), 0)]
    assert prompt.cursor_updates == 0
    assert panel._current_search["matches"] == (
        TextSearchMatch("A", "NodeA", "prompt_template", 2, 3),
    )


def test_text_search_refresh_removes_prompt_highlight_when_match_disappears(
    monkeypatch,
) -> None:
    """Refreshing active text search should clear stale prompt ranges."""

    search_mod = importlib.import_module(
        "substitute.presentation.editor.panel.search_controller"
    )

    class _PromptEditor:
        """Prompt editor double that records search rendering state."""

        def __init__(self) -> None:
            """Initialize recorded calls."""

            self.search_calls: list[tuple[tuple[tuple[int, int], ...], int | None]] = []
            self.clear_count = 0

        def clear_search_matches(self) -> None:
            """Record search rendering clearing."""

            self.clear_count += 1

        def set_search_matches(
            self,
            matches: tuple[tuple[int, int], ...],
            active_index: int | None,
            *,
            query_identity: object | None = None,
        ) -> None:
            """Record rendered search ranges."""

            self.last_query_identity = query_identity
            self.search_calls.append((matches, active_index))

    monkeypatch.setattr(search_mod, "PromptEditor", _PromptEditor)
    service = EditorSearchService()
    query = service.build_query(mode=EditorSearchMode.TEXT, raw_text="dog")
    initial_result = service.build_result(
        build_behavior_snapshot(
            cube_states={
                "A": cube_state(
                    nodes={
                        "NodeA": {
                            "class_type": "PromptNode",
                            "inputs": {"prompt_template": "dog alpha"},
                        }
                    }
                )
            },
            stack_order=["A"],
        ),
        query,
    )
    updated_snapshot = build_behavior_snapshot(
        cube_states={
            "A": cube_state(
                nodes={
                    "NodeA": {
                        "class_type": "PromptNode",
                        "inputs": {"prompt_template": "cat alpha"},
                    }
                }
            )
        },
        stack_order=["A"],
    )
    prompt = _PromptEditor()
    node_behavior_service = SimpleNamespace(
        build_snapshot=lambda **_kwargs: updated_snapshot
    )
    panel = SimpleNamespace(
        input_widgets_by_field_key={("A", "NodeA", "prompt_template"): prompt},
        _stack_order=["A"],
        _cube_states={"A": object()},
        node_behavior_service=node_behavior_service,
        _workflow_overrides=lambda: {},
    )
    controller = search_mod.EditorPanelSearchController(panel)
    controller._current_search_result = initial_result
    controller._navigation = search_mod.PanelSearchNavigationState(
        matches=initial_result.navigation_matches,
        index=0,
        needle="dog",
    )
    controller._publish_search_state()

    controller.refresh_editor_search_result_after_text_change()

    assert prompt.clear_count == 1
    assert prompt.search_calls == []
    assert panel._current_search == {"matches": (), "index": -1, "needle": "dog"}

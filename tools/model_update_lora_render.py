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

"""Render a real CivitAI LoRA offer from a production prompt node card."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.localization import (
    ActiveComfyNodeCatalogStore,
    NodePresentationService,
)
from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.application.prompt_editor.lora.catalog_models import (
    PromptLoraCatalogItem,
    PromptLoraThumbnailVariant,
)
from substitute.infrastructure.model_recommendations.thumbnail_fetcher import (
    CivitaiThumbnailFetcher,
)
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.editor.prompt_editor import PromptEditor
from substitute.presentation.editor.prompt_editor.lora_thumbnail_cache import (
    PromptLoraThumbnailCache,
)
from substitute.presentation.editor.prompt_editor.overlays.lora_wall import (
    show_lora_picker_popup,
)
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.model_updates.icon_menu import update_icon_menu
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from substitute.presentation.widgets.media_wall.media_wall_badge import (
    media_wall_badge_rect,
)
from sugarsubstitute_shared.localization import render_source_application_text
from tests.support.execution.runtime_support import (
    immediate_editor_panel_execution_factories,
)
from tools.editor_projection_rig.fake_gateways import (
    EmptyPromptAutocompleteGateway,
    EmptyPromptWildcardCatalogGateway,
    FixtureNodeDefinitionGateway,
)
from tools.editor_projection_rig.fixtures import read_json
from tools.editor_projection_rig.production_trace import (
    _build_trace_shell,
    _workflow_from_fixture,
)
from tools.editor_projection_rig.trace_events import ProjectionTraceRecorder
from tools.install_experience_capture import save_opaque_dark_widget_capture
from tools.model_update_render_surfaces import (
    RealUpdateScenario,
    UpdatePreferenceService,
    _ThumbnailRepository,
    _asset,
    _capture_with_popup,
    _capture_with_popups,
    mount_shell,
    settle,
)


def render_lora_prompt_node_card(
    app: QApplication,
    service: UpdatePreferenceService,
    scenario: RealUpdateScenario,
    fetcher: CivitaiThumbnailFetcher,
    output: Path,
    prefix: str,
) -> SubstituteWindowFrame:
    """Capture an installed real LoRA in the prompt node's shared picker."""

    frame, layout = mount_shell(settings=False, service=service)
    assert layout is not None
    installed = next(
        version
        for version in scenario.versions
        if version.version_id == scenario.proposal.current.version_id
    )
    asset = _asset(installed, fetcher)
    repository = _ThumbnailRepository({asset.storage_key: asset})
    item = PromptLoraCatalogItem(
        display_name=installed.model_name,
        display_subtitle=installed.version_name,
        prompt_name=Path(installed.file_name).stem,
        backend_value=installed.file_name,
        relative_path=installed.file_name,
        folder="LoRAs",
        basename=Path(installed.file_name).stem,
        extension=Path(installed.file_name).suffix,
        thumbnail_variants=(
            PromptLoraThumbnailVariant(
                size=max(asset.width, asset.height),
                storage_key=asset.storage_key,
                width=asset.width,
                height=asset.height,
                content_format=asset.content_format,
                byte_size=len(asset.payload),
            ),
        ),
        base_model=installed.base_model,
        trained_words=(),
        tags=(),
        model_page_url=installed.model_page_url,
        collision_key=installed.file_name.casefold(),
        collision_count=1,
        has_collision=False,
        search_text=installed.model_name.casefold(),
        sha256=installed.sha256,
    )
    bridge = ModelUpdatePickerBridge(frame)
    workflow, definitions = _workflow_from_fixture(
        read_json(
            Path("artifacts/editor_projection_rig/fixtures/workflow_sdxl_baseline.json")
        )
    )
    cube_alias = "Cube 1: SDXL/Text to Image"
    node_name = "positive_prompt"
    cube = workflow.cubes[cube_alias]
    node_payload = cube.buffer["nodes"][node_name]
    gateway = FixtureNodeDefinitionGateway(definitions)
    node_catalog = ActiveComfyNodeCatalogStore()
    panel = EditorPanel(
        node_definition_gateway=gateway,
        prompt_autocomplete_gateway=EmptyPromptAutocompleteGateway(),
        prompt_wildcard_catalog_gateway=EmptyPromptWildcardCatalogGateway(),
        node_behavior_service=NodeBehaviorService(node_definition_gateway=gateway),
        node_presentation_service=NodePresentationService(
            lambda: node_catalog.snapshot("en"),
            application_text_renderer=render_source_application_text,
        ),
        thumbnail_asset_repository=repository,
        model_updates=bridge,
        workflow_id="model-update-lora-node-card-render",
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )
    panel._cube_states = workflow.cubes
    panel._stack_order = list(workflow.stack_order)
    panel.mainwindow = _build_trace_shell(
        workflow_id="model-update-lora-node-card-render",
        workflow=workflow,
        panel=panel,
        recorder=ProjectionTraceRecorder(),
    ).shell
    snapshot = panel._build_behavior_snapshot()
    wrapper = panel.build_node_card(
        node_name,
        node_payload["inputs"],
        node_payload["class_type"],
        snapshot.field_specs_by_alias[cube_alias][node_name],
        cube,
        snapshot.resolved_nodes_by_alias[cube_alias][node_name],
        snapshot.card_decisions_by_alias[cube_alias][node_name],
        alias=cube_alias,
        parent=frame,
    )
    if not isinstance(wrapper, QWidget):
        raise AssertionError("The real SDXL prompt node card did not build.")
    wrapper.setFixedWidth(620)
    layout.addWidget(wrapper)
    layout.addStretch(1)
    wrapper.show()
    setattr(frame, "_qualification_panel", panel)
    editor = wrapper.findChild(PromptEditor)
    if editor is None:
        raise AssertionError("The real prompt node card did not contain its editor.")
    settle(app)
    save_opaque_dark_widget_capture(frame, output / f"{prefix}-prompt-node-card.png")
    bridge.replace((scenario.proposal,))
    popup = show_lora_picker_popup(
        editor,
        (item,),
        thumbnail_cache=PromptLoraThumbnailCache(repository),
        global_position=editor.mapToGlobal(QPoint(180, 45)),
        model_updates=bridge,
    )
    settle(app)
    QTest.qWait(420)
    app.processEvents()
    if popup._view.items()[0].corner_badge_icon is None:
        raise AssertionError("The real prompt LoRA picker omitted its update icon.")
    _capture_with_popup(frame, popup, output / f"{prefix}-prompt-lora-tiles.png")
    icon_menu = update_icon_menu(parent=popup, updates=bridge, sha256=item.sha256)
    if icon_menu is None or len(icon_menu.actions()) != 2:
        raise AssertionError("The prompt LoRA badge omitted its update decisions.")
    badge = media_wall_badge_rect(popup._view._placed_items[0].rect)
    icon_menu.move(popup._view.viewport().mapToGlobal(badge.center()))
    icon_menu.show()
    settle(app)
    _capture_with_popups(
        frame,
        (popup, icon_menu),
        output / f"{prefix}-prompt-lora-update-icon-menu.png",
    )
    icon_menu.close()
    popup.close()
    return frame


__all__ = ["render_lora_prompt_node_card"]

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

"""Render exact update interactions inside production model node cards."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from substitute.application.localization import (
    ActiveComfyNodeCatalogStore,
    NodePresentationService,
)
from substitute.application.model_metadata import (
    ModelChoiceCatalogIndex,
    RichChoiceResolver,
)
from substitute.application.node_behavior.behavior_service import NodeBehaviorService
from substitute.infrastructure.model_recommendations.thumbnail_fetcher import (
    CivitaiThumbnailFetcher,
)
from substitute.presentation.editor.panel.view import EditorPanel
from substitute.presentation.model_updates.picker_bridge import ModelUpdatePickerBridge
from substitute.presentation.model_updates.icon_menu import update_icon_menu
from substitute.presentation.shell.window_frame import SubstituteWindowFrame
from substitute.presentation.widgets.menu_model import MenuModel
from substitute.presentation.widgets.model_metadata_context_menu import (
    ModelMetadataMenuAction,
    model_metadata_menu_entries,
)
from substitute.presentation.widgets.model_picker import ModelPickerField
from substitute.presentation.widgets.qfluent_menu_renderer import QFluentMenuRenderer
from sugarsubstitute_shared.localization import app_text, render_source_application_text
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
    _RenderedModelCatalog,
    _ThumbnailRepository,
    _asset,
    _capture_with_popup,
    _catalog_item,
    mount_shell,
    settle,
)


def render_node_card(
    app: QApplication,
    service: UpdatePreferenceService,
    scenarios: tuple[RealUpdateScenario, ...],
    fetcher: CivitaiThumbnailFetcher,
    output: Path,
    prefix: str,
    *,
    workflow_fixture: str,
    cube_alias: str,
    node_name: str,
    input_name: str,
) -> SubstituteWindowFrame:
    """Capture a real node-card banner, context menu, and picker tiles."""

    frame, layout = mount_shell(settings=False, service=service)
    assert layout is not None
    installed = tuple(
        next(
            version
            for version in scenario.versions
            if version.version_id == scenario.proposal.current.version_id
        )
        for scenario in scenarios
    )
    assets = tuple(_asset(version, fetcher) for version in installed)
    items = tuple(
        _catalog_item(version, asset)
        for version, asset in zip(installed, assets, strict=True)
    )
    bridge = ModelUpdatePickerBridge(frame)
    catalog = _RenderedModelCatalog(items)
    workflow, definitions = _workflow_from_fixture(
        read_json(Path("artifacts/editor_projection_rig/fixtures") / workflow_fixture)
    )
    cube = workflow.cubes[cube_alias]
    node_payload = cube.buffer["nodes"][node_name]
    class_type = node_payload["class_type"]
    choices = [item.backend_value for item in items]
    definitions[class_type]["input"]["required"][input_name][0] = choices
    cube.buffer["definitions"][class_type]["input"]["required"][input_name][0] = choices
    node_payload["inputs"][input_name] = items[0].backend_value
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
        model_catalog_service=catalog,
        model_choice_resolver=RichChoiceResolver(
            catalog_index=ModelChoiceCatalogIndex(model_catalog=catalog)
        ),
        thumbnail_asset_repository=_ThumbnailRepository(
            {asset.storage_key: asset for asset in assets}
        ),
        model_updates=bridge,
        workflow_id="model-update-node-card-render",
        editor_panel_execution_factories=immediate_editor_panel_execution_factories(),
    )
    panel._cube_states = workflow.cubes
    panel._stack_order = list(workflow.stack_order)
    panel.mainwindow = _build_trace_shell(
        workflow_id="model-update-node-card-render",
        workflow=workflow,
        panel=panel,
        recorder=ProjectionTraceRecorder(),
    ).shell
    snapshot = panel._build_behavior_snapshot()
    wrapper = panel.build_node_card(
        node_name,
        node_payload["inputs"],
        class_type,
        snapshot.field_specs_by_alias[cube_alias][node_name],
        cube,
        snapshot.resolved_nodes_by_alias[cube_alias][node_name],
        snapshot.card_decisions_by_alias[cube_alias][node_name],
        alias=cube_alias,
        parent=frame,
    )
    if not isinstance(wrapper, QWidget):
        raise AssertionError(f"The real {node_name} node card did not build.")
    wrapper.setFixedWidth(620)
    layout.addWidget(wrapper)
    layout.addStretch(1)
    wrapper.show()
    setattr(frame, "_qualification_panel", panel)
    fields = wrapper.findChildren(ModelPickerField)
    if not fields:
        raise AssertionError(f"The real {node_name} node card has no model picker.")
    field = fields[0]
    field.setCurrentText(items[0].backend_value)
    settle(app)
    if field._update_button is None or field._update_button.isVisible():
        raise AssertionError("The node card showed an unsolicited update icon.")
    save_opaque_dark_widget_capture(frame, output / f"{prefix}-node-card-no-update.png")
    bridge.replace(tuple(scenario.proposal for scenario in scenarios))
    settle(app)
    if not field._update_button or not field._update_button.isVisible():
        raise AssertionError("Real node card did not display the update button.")
    save_opaque_dark_widget_capture(frame, output / f"{prefix}-node-card-banner.png")

    requested: list[str] = []
    bridge.familyRequested.connect(requested.append)
    QTest.mouseClick(field._update_button, Qt.MouseButton.LeftButton)
    if requested != [scenarios[0].proposal.current.sha256]:
        raise AssertionError("Update click did not request this model's family.")

    target = field._metadata_context_menu_target_for_current_value()
    if target is None:
        raise AssertionError("Selected node-card model has no context-menu target.")
    menu_items = field._metadata_context_menu.menu_items_for_target(target)
    if not any(
        isinstance(item, ModelMetadataMenuAction)
        and item.label == app_text("View model updates")
        for item in menu_items
    ):
        raise AssertionError("Selected node-card model has no update menu action.")
    menu = QFluentMenuRenderer(parent=field).render(
        MenuModel(entries=model_metadata_menu_entries(menu_items))
    )
    menu.move(field.mapToGlobal(QPoint(120, 28)))
    menu.show()
    settle(app)
    _capture_with_popup(frame, menu, output / f"{prefix}-node-card-context-menu.png")
    menu.close()

    icon_menu = update_icon_menu(
        parent=field._update_button,
        updates=bridge,
        sha256=items[0].sha256,
    )
    if icon_menu is None or len(icon_menu.actions()) != 2:
        raise AssertionError("The update icon did not offer both dismissal choices.")
    icon_menu.move(field._update_button.mapToGlobal(QPoint(0, 25)))
    icon_menu.show()
    settle(app)
    _capture_with_popup(
        frame, icon_menu, output / f"{prefix}-node-card-update-icon-menu.png"
    )
    icon_menu.close()

    dismissed: list[str] = []

    def dismiss_for_capture(sha256: str) -> None:
        """Project the controller's badge removal after the icon decision."""

        dismissed.append(sha256)
        bridge.remove(sha256)

    bridge.dismissRequested.connect(dismiss_for_capture)
    icon_menu.actions()[0].trigger()
    settle(app)
    if dismissed != [items[0].sha256] or field._update_button.isVisible():
        raise AssertionError("Dismissing an update left its node-card icon visible.")
    save_opaque_dark_widget_capture(frame, output / f"{prefix}-node-card-dismissed.png")

    bridge.replace(tuple(scenario.proposal for scenario in scenarios))
    disabled: list[str] = []

    def disable_for_capture(sha256: str) -> None:
        """Project the controller's page-wide badge removal after opt-out."""

        disabled.append(sha256)
        bridge.remove_page(scenarios[0].proposal.current.model_id)

    bridge.pageOptOutRequested.connect(disable_for_capture)
    page_menu = update_icon_menu(
        parent=field._update_button,
        updates=bridge,
        sha256=items[0].sha256,
    )
    if page_menu is None:
        raise AssertionError("The update icon lost its model-page opt-out.")
    page_menu.actions()[1].trigger()
    settle(app)
    if disabled != [items[0].sha256] or field._update_button.isVisible():
        raise AssertionError("Model-page opt-out left its node-card icon visible.")
    save_opaque_dark_widget_capture(
        frame, output / f"{prefix}-node-card-page-opted-out.png"
    )

    bridge.replace(tuple(scenario.proposal for scenario in scenarios))

    field.open_picker()
    settle(app)
    QTest.qWait(420)
    app.processEvents()
    if field._popup is None or not field._popup.isVisible():
        raise AssertionError("The node-card model picker did not open.")
    _capture_with_popup(frame, field._popup, output / f"{prefix}-node-card-tiles.png")
    field._popup.hide()
    return frame

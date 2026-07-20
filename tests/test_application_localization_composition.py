#    SugarSubstitute - The desktop native Qt front-end for ComfyUI
#    Copyright (C) 2026  Artificial Sweetener and contributors
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

"""Test application localization composition before theme and widget creation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from substitute.app.bootstrap.localization_composition import (
    build_application_localization_runtime,
    build_comfy_node_localization_runtime,
    build_node_presentation_service,
)
from substitute.domain.localization import (
    NodeCatalogText,
    NodePresentationRequest,
    NodeTextCatalog,
    NodeTextSource,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
    InstallationConfiguration,
    InstallationContext,
    RuntimeBootstrapStatus,
    RuntimeConfiguration,
)
from sugarsubstitute_shared.localization import LocalizationPreferenceStore


def test_application_localization_handoff_override_is_active_but_not_persisted(
    tmp_path: Path,
) -> None:
    """Use a process override for crash-safe handoff without replacing user intent."""

    application = _application()
    context = _context(tmp_path)

    runtime = build_application_localization_runtime(
        application,
        context,
        "zh-Hans",
    )

    assert runtime.initial_snapshot.requested.is_system
    assert runtime.initial_snapshot.effective_language_identifier == "zh-Hans"
    assert QCoreApplication.translate("LanguageSelector", "Language") == "语言"
    assert not (context.user_settings_dir / "localization.json").exists()
    runtime.manager.close()


def test_application_localization_loads_explicit_japanese_preference(
    tmp_path: Path,
) -> None:
    """Initialize the full app translator generation from durable user settings."""

    application = _application()
    context = _context(tmp_path)
    store = LocalizationPreferenceStore(context.user_settings_dir / "localization.json")
    from sugarsubstitute_shared.localization import LanguagePreference

    store.save(LanguagePreference.explicit("ja"))

    runtime = build_application_localization_runtime(application, context, None)

    assert runtime.initial_snapshot.effective_language_identifier == "ja"
    assert QCoreApplication.translate("LanguageSelector", "Language") == "言語"
    assert QCoreApplication.translate("SwitchButton", "On") == "オン"
    runtime.manager.close()


def test_comfy_node_catalog_runtime_publishes_without_render_time_network_lookup(
    tmp_path: Path,
) -> None:
    """Compose server node translations as a cached presentation layer."""

    application = _application()
    context = _context(tmp_path)
    localization = build_application_localization_runtime(
        application,
        context,
        "zh-Hans",
    )
    scheduled: list[object] = []
    comfy = build_comfy_node_localization_runtime(
        application,
        manager=localization.manager,
        endpoint=context.comfy_target.endpoint,
        cache_root=context.cache_dir,
        background_scheduler=lambda callback: scheduled.append(callback),
    )
    comfy.store.publish(
        effective_language_identifier="zh-Hans",
        active_catalog=NodeTextCatalog.create(
            language_identifier="zh-Hans",
            source=NodeTextSource.ACTIVE_COMFY,
            node_definitions={
                "CustomNode": NodeCatalogText("自定义节点", None, {}, {}),
            },
        ),
        english_catalog=None,
    )

    service = build_node_presentation_service(localization.manager, comfy.store)
    presentation = service.present(
        NodePresentationRequest(
            class_type="CustomNode",
            node_name="CustomNode",
        )
    )

    assert presentation.title == "自定义节点"
    assert presentation.title_source is NodeTextSource.ACTIVE_COMFY
    assert len(scheduled) == 1
    localization.manager.close()


def _application() -> QApplication:
    """Return the process application used by bootstrap composition."""

    return cast(QApplication, QApplication.instance() or QApplication([]))


def _context(tmp_path: Path) -> InstallationContext:
    """Build a deterministic installation context for locale persistence."""

    installation = InstallationConfiguration.create_default(tmp_path)
    runtime = RuntimeConfiguration(
        runtime_root=installation.runtime_dir,
        python_executable=installation.runtime_dir / "python.exe",
        bootstrap_status=RuntimeBootstrapStatus.READY,
    )
    target = ComfyTargetConfiguration(
        mode=ComfyTargetMode.REMOTE,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )
    return InstallationContext(
        installation=installation,
        runtime=runtime,
        comfy_target=target,
    )

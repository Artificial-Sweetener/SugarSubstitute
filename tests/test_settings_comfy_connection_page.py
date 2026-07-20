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

"""Widget contract tests for the Settings Comfy Connection page."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from PySide6.QtCore import QEvent, QObject, QTranslator
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from substitute.application.onboarding import (
    ComfyConnectionSaveResult,
    ComfyConnectionSettingsDraft,
    ComfyConnectionSettingsService,
    ComfyConnectionSettingsSnapshot,
)
from substitute.application.restart_requirements import (
    RestartRequirementItem,
    RestartRequirementSnapshot,
    RestartScope,
)
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.app.bootstrap.settings_execution import (
    create_settings_task_runner_factory,
)
from substitute.presentation.shell.shell_resource_lifecycle import (
    ShellResourceLifecycle,
)
from substitute.domain.onboarding import (
    ComfyEndpoint,
    ComfyTargetConfiguration,
    ComfyTargetMode,
)
from substitute.presentation.settings.comfy_connection_page import (
    ComfyConnectionSettingsPage,
)
from substitute.presentation.settings.settings_card import (
    InteractiveSettingsCard,
    SettingsCard,
)
from substitute.presentation.settings.settings_async import (
    SettingsAsyncTaskRunner,
    SettingsAsyncTaskRunnerFactory,
)
from substitute.presentation.settings.settings_card_group import SettingsCardGroup
from tests.execution_test_helpers import ExecutionRuntimeStub

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


class _Service:
    """Record Settings page service calls for widget tests."""

    def __init__(self, target: ComfyTargetConfiguration) -> None:
        """Store the snapshot target returned by the fake service."""

        self.target = target
        self.saved_drafts: list[ComfyConnectionSettingsDraft] = []
        self.test_calls: list[tuple[str, int]] = []
        self.save_succeeds = True
        self.load_delay_seconds = 0.0
        self.save_delay_seconds = 0.0
        self.test_delay_seconds = 0.0
        self.load_finished = False
        self.load_gate: threading.Event | None = None
        self.test_succeeds = True

    def load_snapshot(self) -> ComfyConnectionSettingsSnapshot:
        """Return the current fake snapshot."""

        if self.load_gate is not None:
            self.load_gate.wait(timeout=2.0)
        if self.load_delay_seconds:
            time.sleep(self.load_delay_seconds)
        self.load_finished = True
        return ComfyConnectionSettingsSnapshot(
            target=self.target,
            persisted_exists=True,
            status_message=(
                f"Substitute is configured to use test ComfyUI at "
                f"{self.target.endpoint.host}:{self.target.endpoint.port}."
            ),
            can_test_endpoint=True,
            managed_model_root=(
                str(self.target.workspace_path / "models")
                if self.target.workspace_path is not None
                else "/srv/comfy/models"
            ),
            active_managed_model_root=(
                str(self.target.workspace_path / "models")
                if self.target.workspace_path is not None
                else "/srv/comfy/models"
            ),
            default_managed_model_root=(
                str(self.target.workspace_path / "models")
                if self.target.workspace_path is not None
                else "/srv/comfy/models"
            ),
            model_root_management_available=True,
        )

    def save_draft(
        self,
        draft: ComfyConnectionSettingsDraft,
    ) -> ComfyConnectionSaveResult:
        """Record one save and optionally update the snapshot target."""

        if self.save_delay_seconds:
            time.sleep(self.save_delay_seconds)
        self.saved_drafts.append(draft)
        if not self.save_succeeds:
            return ComfyConnectionSaveResult(
                target=None,
                succeeded=False,
                message="Save failed.",
                restart_required=False,
            )
        self.target = _target_from_draft(draft)
        return ComfyConnectionSaveResult(
            target=self.target,
            succeeded=True,
            message="Saved. Restart Substitute to use the new ComfyUI connection.",
            restart_required=True,
            restart_snapshot=RestartRequirementSnapshot(
                items=(
                    RestartRequirementItem(
                        key="comfy.connection",
                        label="ComfyUI connection",
                        active_value="A",
                        saved_value="B",
                        scope=RestartScope.FULL_APP,
                    ),
                ),
                required_scope=RestartScope.FULL_APP,
            ),
        )

    def test_endpoint(self, host: str, port: int) -> ComfyConnectionSaveResult:
        """Record one endpoint test without changing saved state."""

        if self.test_delay_seconds:
            time.sleep(self.test_delay_seconds)
        self.test_calls.append((host, port))
        if not self.test_succeeds:
            return ComfyConnectionSaveResult(
                target=None,
                succeeded=False,
                message=f"ComfyUI did not respond at {host.strip()}:{port}.",
                restart_required=False,
            )
        return ComfyConnectionSaveResult(
            target=None,
            succeeded=True,
            message=f"ComfyUI responded at {host.strip()}:{port}.",
            restart_required=False,
        )


def _task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for page tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


def _threaded_task_runner_factory() -> SettingsAsyncTaskRunnerFactory:
    """Create a runtime-backed Settings factory for async timing assertions."""

    return create_settings_task_runner_factory(
        ExecutionRuntimeStub(),
        resource_lifecycle=ShellResourceLifecycle(),
    )


def test_comfy_connection_page_builds_expected_form_cards(tmp_path: Path) -> None:
    """The page should expose grouped form cards without interactive row behavior."""

    _app()
    page = _build_page(tmp_path)

    assert page.mode_options() == ("Managed local", "Existing local", "Remote")
    row_titles = tuple(
        row.title_label.text()
        for row in page.findChildren(SettingsCard)
        if not row.isHidden()
    )
    group_titles = tuple(
        group.title_label.text() for group in page.findChildren(SettingsCardGroup)
    )
    assert row_titles == (
        "ComfyUI source",
        "ComfyUI folder",
        "Model folder",
        "Local endpoint",
        "Setup wizard",
        "Connection check",
    )
    assert group_titles == (
        "ComfyUI source",
        "Managed local setup",
        "Connection check",
    )
    assert page.findChildren(InteractiveSettingsCard) == []
    assert page.discard_button.isEnabled() is False
    assert page.save_button.isEnabled() is False
    assert page.setup_action_row.isHidden() is False
    assert page.port_spinbox.property("symbolVisible") is False
    assert page.port_spinbox.minimumWidth() >= page.port_spinbox.sizeHint().width()
    assert page.port_spinbox.minimumWidth() < page.host_edit.minimumWidth()
    assert page.port_spinbox.minimumHeight() == page.host_edit.minimumHeight()
    assert page.port_spinbox.maximumHeight() == page.host_edit.maximumHeight()
    page.close()


def test_comfy_connection_page_does_not_clip_grouped_inputs(tmp_path: Path) -> None:
    """Grouped connection inputs should keep their full Fluent control height."""

    app = _app()
    page = _build_page(tmp_path)
    page.resize(914, 720)
    page.show()
    app.processEvents()

    for control in (
        page.host_edit,
        page.port_spinbox,
        page.managed_folder_edit,
        page.model_folder_edit,
    ):
        group = control.parentWidget()
        assert group is not None
        assert group.height() >= control.minimumHeight()
        assert control.geometry().bottom() <= group.contentsRect().bottom()

    page.set_selected_mode(ComfyTargetMode.ATTACHED_LOCAL)
    app.processEvents()
    group = page.existing_folder_edit.parentWidget()
    assert group is not None
    assert group.height() >= page.existing_folder_edit.minimumHeight()
    assert (
        page.existing_folder_edit.geometry().bottom() <= group.contentsRect().bottom()
    )

    page.close()


def test_comfy_connection_page_switches_mode_specific_folder_rows(
    tmp_path: Path,
) -> None:
    """Target mode changes should expose only the relevant folder row."""

    _app()
    page = _build_page(tmp_path)

    assert page.is_managed_folder_row_visible() is True
    assert page.is_model_folder_row_visible() is True
    assert page.is_existing_folder_row_visible() is False

    page.set_selected_mode(ComfyTargetMode.ATTACHED_LOCAL)
    assert page.is_managed_folder_row_visible() is False
    assert page.is_model_folder_row_visible() is True
    assert page.is_existing_folder_row_visible() is True
    assert page.setup_action_row.isHidden() is False
    assert page.configuration_group.title_label.text() == "Existing local setup"
    assert page.endpoint_row.title_label.text() == "Local endpoint"

    page.set_selected_mode(ComfyTargetMode.REMOTE)
    assert page.is_managed_folder_row_visible() is False
    assert page.is_model_folder_row_visible() is True
    assert page.model_folder_browse_button.isHidden() is True
    assert page.is_existing_folder_row_visible() is False
    assert page.setup_action_row.isHidden() is True
    assert page.configuration_group.title_label.text() == "Remote server"
    assert page.endpoint_row.title_label.text() == "Server endpoint"
    page.close()


def test_comfy_connection_page_marks_dirty_after_edit(tmp_path: Path) -> None:
    """Editing form values should enable save without adding row details."""

    _app()
    page = _build_page(tmp_path)

    assert page.save_button.isEnabled() is False
    page.host_edit.setText("127.0.0.2")

    assert page.save_button.isEnabled() is True
    assert page.discard_button.isEnabled() is True
    page.close()


def test_comfy_connection_page_discard_restores_loaded_draft(
    tmp_path: Path,
) -> None:
    """Discarding changes should restore loaded values and clean action state."""

    _app()
    page = _build_page(tmp_path)
    page.set_selected_mode(ComfyTargetMode.REMOTE)
    page.host_edit.setText("remote-box")
    page.port_spinbox.setValue(8190)

    assert page.save_button.isEnabled() is True
    assert page.discard_button.isEnabled() is True

    page.discard_changes()

    assert page.selected_mode() is ComfyTargetMode.MANAGED_LOCAL
    assert page.host_edit.text() == "127.0.0.1"
    assert page.port_spinbox.value() == 8188
    assert page.save_button.isEnabled() is False
    assert page.discard_button.isEnabled() is False
    page.close()


def test_comfy_connection_page_initial_load_is_async(tmp_path: Path) -> None:
    """Constructing the page should not block on connection snapshot loading."""

    app = _app()
    service = _Service(_managed_target(tmp_path))
    service.load_gate = threading.Event()

    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_threaded_task_runner_factory(),
    )
    try:
        assert service.load_finished is False
        service.load_gate.set()
        _process_events_until(app, lambda: page.host_edit.text() == "127.0.0.1")

        assert service.load_finished is True
        assert page.save_button.isEnabled() is False
    finally:
        service.load_gate.set()
        page.close()


def test_comfy_connection_page_save_submits_current_draft(tmp_path: Path) -> None:
    """Saving should pass the edited draft to the service and reload clean state."""

    _app()
    service = _Service(_managed_target(tmp_path))
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)
    page.set_selected_mode(ComfyTargetMode.REMOTE)
    page.host_edit.setText("remote-box")
    page.port_spinbox.setValue(8190)

    page.save_changes()
    _process_events_until(_app(), lambda: len(service.saved_drafts) == 1)
    _process_events_until(_app(), lambda: page.save_button.isEnabled() is False)

    assert len(service.saved_drafts) == 1
    saved = service.saved_drafts[0]
    assert saved.mode is ComfyTargetMode.REMOTE
    assert saved.host == "remote-box"
    assert saved.port == 8190
    assert page.save_button.isEnabled() is False
    page.close()


def test_comfy_connection_page_save_submits_explicit_model_root(
    tmp_path: Path,
) -> None:
    """Saving should include explicit managed model root edits in the draft."""

    _app()
    service = _Service(_managed_target(tmp_path))
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)
    model_root = tmp_path / "Models"

    page.model_folder_edit.setText(str(model_root))
    page.save_changes()
    _process_events_until(_app(), lambda: len(service.saved_drafts) == 1)

    saved = service.saved_drafts[0]
    assert saved.managed_model_root == str(model_root)
    assert saved.managed_model_root_uses_default is False
    page.close()


def test_comfy_connection_page_default_model_root_follows_managed_folder(
    tmp_path: Path,
) -> None:
    """Default model root should track managed workspace folder edits."""

    _app()
    service = _Service(_managed_target(tmp_path))
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)
    new_workspace = tmp_path / "OtherComfy"

    page.managed_folder_edit.setText(str(new_workspace))
    page.save_changes()
    _process_events_until(_app(), lambda: len(service.saved_drafts) == 1)

    saved = service.saved_drafts[0]
    assert saved.managed_model_root == str(new_workspace / "models")
    assert saved.managed_model_root_uses_default is True
    page.close()


def test_comfy_connection_page_restart_prompt_uses_shared_callback(
    tmp_path: Path,
) -> None:
    """A restart-producing save should open the shared restart requirements UI."""

    _app()
    service = _Service(_managed_target(tmp_path))
    calls: list[str] = []
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
        show_restart_requirements=lambda: calls.append("show"),
    )
    _wait_for_loaded(page)

    page.host_edit.setText("127.0.0.2")
    page.save_changes()
    _process_events_until(_app(), lambda: len(service.saved_drafts) == 1)

    assert calls == ["show"]
    page.close()


def test_comfy_connection_page_failed_save_keeps_draft_editable(
    tmp_path: Path,
) -> None:
    """A failed save should leave the draft editable without row detail text."""

    _app()
    service = _Service(_managed_target(tmp_path))
    service.save_succeeds = False
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)
    page.host_edit.setText("127.0.0.2")

    page.save_changes()
    _process_events_until(_app(), lambda: len(service.saved_drafts) == 1)
    _process_events_until(_app(), lambda: page.save_button.isEnabled())

    assert len(service.saved_drafts) == 1
    assert page.save_button.isEnabled() is True
    page.close()


def test_comfy_connection_page_tests_endpoint_without_saving(tmp_path: Path) -> None:
    """Test connection should call the service test path only."""

    _app()
    service = _Service(_managed_target(tmp_path))
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)
    page.host_edit.setText("127.0.0.9")
    page.port_spinbox.setValue(8199)

    page.test_connection()
    _process_events_until(_app(), lambda: len(service.test_calls) == 1)

    assert service.test_calls == [("127.0.0.9", 8199)]
    assert service.saved_drafts == []
    page.close()


def test_comfy_connection_page_renders_successful_connection_test(
    tmp_path: Path,
) -> None:
    """A successful connection test should render visible success feedback."""

    _app()
    service = _Service(_managed_target(tmp_path))
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)

    page.test_connection()
    _process_events_until(_app(), lambda: len(service.test_calls) == 1)

    assert page.connection_feedback_bar.isHidden() is False
    assert page.connection_feedback_bar.severity() == "success"
    assert page.connection_feedback_bar.title_label.text() == (
        "Connection check succeeded"
    )
    assert "ComfyUI responded" in page.connection_check_row.description_label.text()
    page.close()


def test_comfy_connection_page_renders_failed_connection_test(
    tmp_path: Path,
) -> None:
    """A failed connection test should render visible error feedback."""

    _app()
    service = _Service(_managed_target(tmp_path))
    service.test_succeeds = False
    page = ComfyConnectionSettingsPage(
        service=cast(ComfyConnectionSettingsService, service),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)

    page.test_connection()
    _process_events_until(_app(), lambda: len(service.test_calls) == 1)

    assert page.connection_feedback_bar.isHidden() is False
    assert page.connection_feedback_bar.severity() == "error"
    assert page.connection_feedback_bar.title_label.text() == "Connection check failed"
    assert "did not respond" in page.connection_check_row.description_label.text()
    page.close()


def test_comfy_connection_page_wizard_escape_hatch_routes_to_callback(
    tmp_path: Path,
) -> None:
    """The explicit wizard button should keep reconfigure available."""

    _app()
    calls: list[str] = []
    page = _build_page(tmp_path, open_reconfigure_window=lambda: calls.append("open"))

    page.wizard_button.click()

    assert calls == ["open"]
    page.close()


def test_comfy_connection_page_switches_all_primary_copy_in_place(
    tmp_path: Path,
    request: pytest.FixtureRequest,
) -> None:
    """The production Settings surface must not retain its English scaffold."""

    app = _app()
    resource_root = (
        Path(__file__).resolve().parents[1]
        / "substitute"
        / "presentation"
        / "resources"
        / "i18n"
    )
    chinese = QTranslator()
    japanese = QTranslator()
    assert chinese.load(str(resource_root / "sugarsubstitute_zh_CN.qm"))
    assert japanese.load(str(resource_root / "sugarsubstitute_ja_JP.qm"))
    request.addfinalizer(lambda: app.removeTranslator(chinese))
    request.addfinalizer(lambda: app.removeTranslator(japanese))
    assert app.installTranslator(chinese)
    page = _build_page(tmp_path)
    page.show()
    app.processEvents()

    assert page.source_group.title_label.text() == "ComfyUI 来源"
    assert page.configuration_group.title_label.text() == "受管理的本地设置"
    assert page.source_row.title_label.text() == "ComfyUI 来源"
    assert page.source_row.description_label.text() == (
        "选择 Substitute 用于生成图像的 ComfyUI 实例。"
    )
    assert page.managed_folder_row.title_label.text() == "ComfyUI 文件夹"
    assert page.model_folder_row.title_label.text() == "模型文件夹"
    assert page.endpoint_row.title_label.text() == "本地端点"
    assert page.setup_action_row.title_label.text() == "设置向导"
    assert page.connection_check_group.title_label.text() == "连接检查"
    assert page.refresh_button.text() == "刷新"
    assert page.test_button.text() == "测试连接"

    assert app.removeTranslator(chinese)
    assert app.installTranslator(japanese)
    for widget in (page, *page.findChildren(QObject)):
        app.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

    assert page.source_group.title_label.text() == "ComfyUI ソース"
    assert page.configuration_group.title_label.text() == (
        "管理対象のローカルセットアップ"
    )
    assert page.source_row.description_label.text() == (
        "画像生成に使用する ComfyUI 環境を選択します。"
    )
    assert page.managed_folder_row.title_label.text() == "ComfyUI フォルダー"
    assert page.model_folder_row.title_label.text() == "モデルフォルダー"
    assert page.endpoint_row.title_label.text() == "ローカルエンドポイント"
    assert page.setup_action_row.title_label.text() == "セットアップウィザード"
    assert page.connection_check_group.title_label.text() == "接続確認"
    assert page.refresh_button.text() == "更新"
    assert page.test_button.text() == "接続をテスト"

    assert app.removeTranslator(japanese)
    page.close()


def _app() -> QApplication:
    """Return the active QApplication instance."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast(QApplication, app)


def _build_page(
    tmp_path: Path,
    *,
    open_reconfigure_window: Callable[[], object] | None = None,
) -> ComfyConnectionSettingsPage:
    """Create a Comfy connection page with a managed-local snapshot."""

    callback = (
        open_reconfigure_window
        if callable(open_reconfigure_window)
        else lambda: object()
    )
    page = ComfyConnectionSettingsPage(
        service=cast(
            ComfyConnectionSettingsService,
            _Service(_managed_target(tmp_path)),
        ),
        open_reconfigure_window=callback,
        task_runner_factory=_task_runner_factory,
    )
    _wait_for_loaded(page)
    return page


def _wait_for_loaded(page: ComfyConnectionSettingsPage) -> None:
    """Wait for the page's initial async snapshot to bind."""

    _process_events_until(_app(), lambda: page.host_edit.text() == "127.0.0.1")


def _process_events_until(
    app: QApplication,
    condition: Callable[[], bool],
    *,
    timeout_ms: int = 1000,
) -> None:
    """Process Qt events until a condition passes or a test timeout expires."""

    deadline = time.perf_counter() + (timeout_ms / 1000.0)
    while time.perf_counter() < deadline:
        app.processEvents()
        if condition():
            return
        QTest.qWait(10)
    app.processEvents()
    assert condition()


def _managed_target(tmp_path: Path) -> ComfyTargetConfiguration:
    """Build a managed-local target for page tests."""

    return ComfyTargetConfiguration(
        mode=ComfyTargetMode.MANAGED_LOCAL,
        endpoint=ComfyEndpoint(host="127.0.0.1", port=8188),
        workspace_path=tmp_path / "comfyui",
        install_owned=True,
        launch_owned=True,
    )


def _target_from_draft(
    draft: ComfyConnectionSettingsDraft,
) -> ComfyTargetConfiguration:
    """Build a target from a saved test draft."""

    endpoint = ComfyEndpoint(host=draft.host.strip(), port=draft.port)
    if draft.mode is ComfyTargetMode.MANAGED_LOCAL:
        return ComfyTargetConfiguration(
            mode=draft.mode,
            endpoint=endpoint,
            workspace_path=draft.managed_workspace_path,
            install_owned=True,
            launch_owned=True,
        )
    if draft.mode is ComfyTargetMode.ATTACHED_LOCAL:
        return ComfyTargetConfiguration(
            mode=draft.mode,
            endpoint=endpoint,
            workspace_path=draft.attached_workspace_path,
            install_owned=False,
            launch_owned=True,
        )
    return ComfyTargetConfiguration(
        mode=draft.mode,
        endpoint=endpoint,
        workspace_path=None,
        install_owned=False,
        launch_owned=False,
    )

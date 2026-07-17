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

"""Widget contract tests for the Settings Comfy Environment page."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any, cast

import pytest
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QSizePolicy, QToolButton, QWidget
from qfluentwidgets import (  # type: ignore[import-untyped]
    ListWidget,
    SearchLineEdit,
    TableWidget,
    Theme,
    setTheme,
)
from qfluentwidgets.common.smooth_scroll import (  # type: ignore[import-untyped]
    SmoothMode,
)

from substitute.application.comfy_environment import ComfyEnvironmentService
from tests.execution_testing import ImmediateTaskSubmitter
from substitute.domain.comfy_environment import (
    ComfyEnvironmentAvailability,
    ComfyEnvironmentCapabilities,
    ComfyEnvironmentComponent,
    ComfyEnvironmentJob,
    ComfyEnvironmentJobEvent,
    ComfyEnvironmentJobStatus,
    ComfyEnvironmentOperationPlan,
    ComfyEnvironmentPackage,
    ComfyEnvironmentStatus,
    ComfyHostStatus,
    ComfyMaintenanceExecutionPhase,
    ComfyMaintenancePlan,
    ComfyMaintenancePlanIssue,
    ComfyMaintenancePlanItem,
    ComfyMaintenancePlanRequest,
    ComfyMaintenancePlanSummary,
    ComfyMaintenancePlanTarget,
    ComfyPackageClaimant,
    ComfyPackageManagementTag,
    ComfyPythonStatus,
)
from substitute.presentation.settings.comfy_environment_page import (
    ComfyEnvironmentOperationFailure,
    ComfyEnvironmentPage,
)
from substitute.presentation.settings.comfy_environment_package_list import (
    PackageInventoryList,
)
from substitute.presentation.settings.planned_changes_panel import (
    PlanQueueItemWidget,
)
from substitute.presentation.settings.settings_async import SettingsAsyncTaskRunner
from substitute.presentation.settings.settings_style import settings_card_border_color

if os.environ.get("PYTEST_XDIST_WORKER"):
    pytest.skip(
        "settings Qt contract tests require non-xdist execution on Windows",
        allow_module_level=True,
    )


def _task_runner_factory(
    parent: QObject,
    *,
    owner_id: str,
) -> SettingsAsyncTaskRunner:
    """Create an immediate Settings task runner for environment tests."""

    return SettingsAsyncTaskRunner(
        parent,
        submitter=ImmediateTaskSubmitter(),
        owner_id=owner_id,
    )


class _Backend:
    """Environment backend test double for Settings widgets."""

    def __init__(
        self,
        *,
        planning_supported: bool = True,
        plan_blocked: bool = True,
    ) -> None:
        """Configure environment management capabilities."""

        self._planning_supported = planning_supported
        self._plan_blocked = plan_blocked
        self._maintenance_plan = _maintenance_plan(blocked=plan_blocked)
        self.reorder_requests: list[tuple[int, tuple[str, ...]]] = []

    def get_environment_capabilities(self) -> ComfyEnvironmentCapabilities:
        """Return restart-capable environment management."""

        return ComfyEnvironmentCapabilities(
            schema_version=1,
            supported_features=(
                "restart",
                *(("operation-planning",) if self._planning_supported else ()),
            ),
            restart_supported=True,
            package_mutation_supported=not self._plan_blocked,
            operation_planning_supported=self._planning_supported,
        )

    def get_environment_status(self) -> ComfyEnvironmentStatus:
        """Return one current environment status."""

        return ComfyEnvironmentStatus(
            schema_version=1,
            python=ComfyPythonStatus(
                executable="E:\\ComfyUI\\venv\\Scripts\\python.exe",
                version="3.12.7",
                prefix="E:\\ComfyUI\\venv",
                base_prefix="C:\\Python312",
                is_virtual_environment=True,
            ),
            comfy=ComfyHostStatus(
                root="E:\\ComfyUI",
                process_id=1234,
                restart_supported=True,
            ),
            environment=ComfyEnvironmentAvailability(
                inventory_available=True,
                mutation_available=False,
            ),
        )

    def restart_comfy(self) -> None:
        """Return no restart job because this test does not click restart."""

        return None

    def get_environment_job(self, _job_id: str) -> None:
        """Return no job because this test does not poll restart."""

        return None

    def plan_operation(
        self,
        request: dict[str, object],
    ) -> ComfyEnvironmentOperationPlan | None:
        """Return one operation plan for Settings tests."""

        operation = str(request["operation"])
        if operation == "update-component":
            return _plan("update-component", ("torch", "torchvision", "torchaudio"))
        return _plan(operation, (str(request["packageName"]),))

    def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
        """Return installed packages for the package-first inventory."""

        return (
            _package(
                name="torch",
                version="2.8.0",
                summary="Tensors and dynamic neural networks in Python.",
                summary_source="installed-metadata",
                attribution="supported",
                tags=(_tag("pytorch", "PyTorch"),),
            ),
            _package(
                name="torchvision",
                version="0.23.0",
                summary="Image and video datasets and models for torch.",
                summary_source="installed-metadata",
                attribution="supported",
                tags=(_tag("pytorch", "PyTorch"),),
            ),
            _package(
                name="torchaudio",
                version="2.8.0",
                summary=None,
                summary_source="unavailable",
                attribution="supported",
                tags=(_tag("pytorch", "PyTorch"),),
            ),
            _package(
                name="triton",
                version="3.4.0",
                summary="A language and compiler for custom deep learning operations.",
                summary_source="pypi",
                attribution="supported",
                tags=(_tag("triton", "Triton"),),
            ),
            _package(
                name="sageattention",
                version="2.2.0",
                summary=None,
                summary_source="unavailable",
                attribution="supported",
                tags=(_tag("sageattention", "SageAttention"),),
            ),
            _package(
                name="custom-node-helper",
                version="1.4.0",
                summary="Helper package from installed metadata.",
                summary_source="installed-metadata",
                attribution="custom-node",
                claimants=(
                    _claimant("ComfyUI-VFI", "custom-node-helper>=1.0"),
                    _claimant(
                        "ComfyUI-Manager",
                        "base-helper",
                        required_via="base-helper",
                    ),
                    _claimant(
                        "ComfyUI-EyeCandy",
                        "base-helper",
                        required_via="base-helper",
                    ),
                ),
            ),
            _package(
                name="manual-tool",
                version="0.9.1",
                summary=None,
                summary_source="unavailable",
                attribution="manual-or-unknown",
            ),
        )

    def list_components(self) -> tuple[ComfyEnvironmentComponent, ...]:
        """Return no components because Settings renders packages as primary."""

        return ()

    def get_maintenance_plan(self) -> ComfyMaintenancePlan:
        """Return the current maintenance plan."""

        return self._maintenance_plan

    def add_maintenance_plan_item(
        self,
        request: dict[str, object],
    ) -> ComfyMaintenancePlan:
        """Add one fake item to the maintenance plan."""

        operation = str(request["operation"])
        if operation == "update-runtime":
            self._maintenance_plan = _maintenance_plan(
                items=(
                    _plan_item(
                        item_id="plan-item-1",
                        title="Update PyTorch runtime",
                        operation="update-runtime",
                        affected=("torch", "torchvision", "torchaudio"),
                        target_kind="runtime-family",
                        target_id="pytorch",
                        target_display="PyTorch runtime",
                    ),
                    _plan_item(
                        item_id="plan-item-2",
                        title="Reinstall Triton",
                        operation="reinstall-package",
                        affected=("triton",),
                        install_requirements=("triton-windows",),
                        generated=True,
                        generated_by_item_id="plan-item-1",
                        can_remove=False,
                        can_reorder=False,
                    ),
                    _plan_item(
                        item_id="plan-item-3",
                        title="Reinstall SageAttention",
                        operation="reinstall-package",
                        affected=("sageattention",),
                        generated=True,
                        generated_by_item_id="plan-item-1",
                        can_remove=False,
                        can_reorder=False,
                    ),
                ),
                revision=self._maintenance_plan.revision + 1,
                message="Planned item added with required compatibility follow-ups.",
                blocked=self._plan_blocked,
            )
        else:
            package_name = str(request["packageName"])
            operation_title = (
                "Uninstall" if operation == "uninstall-package" else "Update"
            )
            self._maintenance_plan = _maintenance_plan(
                items=(
                    *self._maintenance_plan.items,
                    _plan_item(
                        item_id=f"plan-item-{len(self._maintenance_plan.items) + 1}",
                        title=f"{operation_title} {package_name}",
                        operation=operation,
                        affected=(package_name,),
                    ),
                ),
                revision=self._maintenance_plan.revision + 1,
                message="Planned item added.",
                blocked=self._plan_blocked,
            )
        return self._maintenance_plan

    def remove_maintenance_plan_item(self, item_id: str) -> ComfyMaintenancePlan:
        """Remove one fake item from the maintenance plan."""

        self._maintenance_plan = _maintenance_plan(
            items=tuple(
                item
                for item in self._maintenance_plan.items
                if item.item_id != item_id and item.generated_by_item_id != item_id
            ),
            revision=self._maintenance_plan.revision + 1,
            message="Planned item removed.",
            blocked=self._plan_blocked,
        )
        return self._maintenance_plan

    def reorder_maintenance_plan_items(
        self,
        *,
        revision: int,
        item_ids: tuple[str, ...],
    ) -> ComfyMaintenancePlan:
        """Record and normalize a fake reorder request."""

        self.reorder_requests.append((revision, item_ids))
        by_id = {item.item_id: item for item in self._maintenance_plan.items}
        ordered = tuple(by_id[item_id] for item_id in item_ids if item_id in by_id)
        if ordered and ordered[0].generated:
            ordered = (
                by_id["plan-item-1"],
                *(item for item in ordered if item.item_id != "plan-item-1"),
            )
        self._maintenance_plan = _maintenance_plan(
            items=ordered,
            revision=self._maintenance_plan.revision + 1,
            message="Order adjusted because compatibility follow-ups must run after their parent.",
            blocked=self._plan_blocked,
        )
        return self._maintenance_plan

    def clear_maintenance_plan(self) -> ComfyMaintenancePlan:
        """Clear the fake maintenance plan."""

        self._maintenance_plan = _maintenance_plan(
            revision=self._maintenance_plan.revision + 1,
            message="Planned changes cleared.",
            blocked=self._plan_blocked,
        )
        return self._maintenance_plan

    def validate_maintenance_plan(self) -> ComfyMaintenancePlan:
        """Return the current fake maintenance plan."""

        return self._maintenance_plan

    def apply_maintenance_plan(self, *, revision: int) -> ComfyEnvironmentJob | None:
        """Return no apply job because fake plans are blocked."""

        _ = revision
        return None


class _CountingBackend(_Backend):
    """Environment backend that counts snapshot capability requests."""

    def __init__(self) -> None:
        """Create a counting backend with default environment data."""

        super().__init__()
        self.capability_requests = 0

    def get_environment_capabilities(self) -> ComfyEnvironmentCapabilities:
        """Count capability requests before returning normal capabilities."""

        self.capability_requests += 1
        return super().get_environment_capabilities()


class _ApplyBackend(_Backend):
    """Backend test double that accepts plan apply."""

    def __init__(self) -> None:
        """Create an applyable backend."""

        super().__init__(plan_blocked=False)
        self.applied_revisions: list[int] = []

    def apply_maintenance_plan(
        self,
        *,
        revision: int,
    ) -> ComfyEnvironmentJob:
        """Return a queued maintenance job."""

        self.applied_revisions.append(revision)
        return ComfyEnvironmentJob(
            job_id="envjob-apply",
            operation="apply-maintenance-plan",
            status=ComfyEnvironmentJobStatus.QUEUED,
            created_at="2026-04-17T00:00:00Z",
            updated_at="2026-04-17T00:00:00Z",
            message="Maintenance plan queued for execution.",
            host_process_id=1234,
            events=(
                ComfyEnvironmentJobEvent(
                    created_at="2026-04-17T00:00:00Z",
                    status=ComfyEnvironmentJobStatus.QUEUED,
                    message="Maintenance plan queued for execution.",
                ),
            ),
        )


class _SearchSortBackend(_Backend):
    """Environment backend test double with targeted sort/search data."""

    def list_packages(self) -> tuple[ComfyEnvironmentPackage, ...]:
        """Return packages that separate name matches from claimant matches."""

        return (
            _package(
                name="beta-package",
                version="1.0.0",
                summary=None,
                summary_source="unavailable",
                attribution="custom-node",
                claimants=(
                    _claimant("HelperNodeA", "beta-package"),
                    _claimant("HelperNodeB", "beta-package"),
                    _claimant("HelperNodeC", "beta-package"),
                ),
            ),
            _package(
                name="alpha-helper",
                version="0.1.0",
                summary=None,
                summary_source="unavailable",
                attribution="manual-or-unknown",
            ),
            _package(
                name="gamma-tool",
                version="2.0.0",
                summary=None,
                summary_source="unavailable",
                attribution="manual-or-unknown",
            ),
        )


def test_comfy_environment_page_renders_environment_status() -> None:
    """Comfy environment settings should render environment status."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)

    assert page.restart_button.isEnabled()
    assert "Python 3.12.7" in page.python_label.text()
    assert page.inventory_label.text() == "7 installed packages"
    assert page.inventory_count_label.isHidden()
    assert "torch" in page.inventory_item_names()
    assert "manual-tool" in page.inventory_item_names()
    assert "Helper package from installed metadata." in (page.detail_text())


def test_environment_page_demotes_setup_wizard_entry_point() -> None:
    """Environment settings should point connection edits to the connection section."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)

    assert page.reconfigure_button.text() == "Open setup wizard"
    assert page.reconfigure_button.text() != "Setup / Connection"


def test_environment_page_refreshes_after_settings_activation() -> None:
    """Environment loading should wait for the active Settings page lifecycle."""

    app = _app()
    backend = _CountingBackend()
    page = ComfyEnvironmentPage(
        ComfyEnvironmentService(backend),
        open_reconfigure_window=lambda: object(),
        task_runner_factory=_task_runner_factory,
    )

    _process_events(app)

    assert backend.capability_requests == 0

    page.set_settings_page_active(True)
    _process_events(app, cycles=20)

    assert backend.capability_requests == 1
    assert "Comfy environment management is available." in page.status_label.text()
    assert "torch" in page.inventory_item_names()
    page.close()
    page.deleteLater()


def test_environment_page_renders_package_inventory_without_synthetic_rows() -> None:
    """Settings page should expose installed packages without fake dependency rows."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)

    item_names = page.inventory_item_names()
    assert item_names == (
        "torch",
        "torchvision",
        "torchaudio",
        "triton",
        "sageattention",
        "custom-node-helper",
        "manual-tool",
    )
    assert "ComfyUI-VFI dependencies" not in item_names
    assert "PyTorch" not in item_names
    assert "more" not in page.inventory_label.text()
    assert "Python packages installed" not in page.inventory_label.text()
    package_selector_layout = page.package_selector.layout()
    assert package_selector_layout is not None
    header_item = package_selector_layout.itemAt(0)
    assert header_item is not None
    assert header_item.widget() is page.inventory_label


def test_environment_page_details_show_claimants_and_summary_source() -> None:
    """Selecting a package should show claimant metadata and summary source."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:custom-node-helper")

    detail_text = page.detail_text()
    assert "custom-node-helper" in detail_text
    assert '"Helper package from installed metadata."' in detail_text
    assert "Required by:\nComfyUI-VFI" in detail_text
    assert "Direct requirement" not in detail_text
    assert "base-helper\n    ComfyUI-EyeCandy\n    ComfyUI-Manager" in detail_text
    assert "    ComfyUI-EyeCandy" in detail_text
    assert "ComfyUI-VFI" in detail_text
    assert "custom-node-helper>=1.0" not in detail_text
    assert "summary: installed metadata" in detail_text
    assert "requirements.txt" not in detail_text
    assert "Core GPU inference runtime" not in detail_text
    assert "Supported actions: none" not in detail_text


def test_environment_page_dependency_names_elide_with_tooltips() -> None:
    """Transitive dependency labels should not clip into malformed names."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:custom-node-helper")
    _process_events(app)

    dependency_label = next(
        label
        for label in page.detail_claimants_label.findChildren(QLabel)
        if label.toolTip() == "base-helper"
    )
    constrained_width = dependency_label.fontMetrics().horizontalAdvance("base")
    dependency_label.setFixedWidth(constrained_width)
    dependency_label.resize(constrained_width, dependency_label.height())
    _process_events(app)

    assert dependency_label.text() == "base-helper"
    rendered_text = QLabel.text(dependency_label)
    assert rendered_text != "base-"
    assert "\u2026" in rendered_text


def test_environment_page_claimants_reappear_after_empty_package_selection() -> None:
    """Claimant details should recover after selecting a package with no claimants."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:manual-tool")
    _process_events(app)
    assert page.detail_claimants_label.height() > 0
    assert "No known extension claimant." in page.detail_text()

    page.select_inventory_item("package:custom-node-helper")
    _process_events(app)

    claimant_labels = page.detail_claimants_label.findChildren(QLabel)
    visible_text = "\n".join(
        label.text() for label in claimant_labels if not label.isHidden()
    )
    assert page.detail_claimants_label.height() > 0
    assert "Required by:" in visible_text
    assert "ComfyUI-VFI" in visible_text
    assert "base-helper" in visible_text


def test_environment_page_details_labels_wrap_inside_inspector() -> None:
    """Long package details should wrap instead of forcing horizontal overflow."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:custom-node-helper")
    _process_events(app)

    labels = (
        page.detail_title_label,
        page.detail_meta_label,
        page.detail_summary_label,
        page.detail_tags_label,
    )
    for label in labels:
        assert label.wordWrap()
        assert label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
        assert label.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Maximum
    assert (
        page.detail_scroll.horizontalScrollBarPolicy()
        == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    scroll_delegate = page.detail_scroll.scrollDelagate
    assert scroll_delegate.useAni is False
    assert scroll_delegate.verticalSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.horizonSmoothScroll.smoothMode is SmoothMode.NO_SMOOTH
    assert scroll_delegate.vScrollBar.duration == 0
    assert scroll_delegate.hScrollBar.duration == 0
    assert page.detail_panel.minimumWidth() == 0
    assert page.detail_panel.width() <= (page.detail_scroll.viewport().width())
    detail_layout = page.detail_panel.layout()
    assert detail_layout is not None
    assert detail_layout.alignment() == Qt.AlignmentFlag.AlignTop
    margins = detail_layout.contentsMargins()
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        12,
        12,
        12,
        12,
    )
    assert detail_layout.count() == 5
    assert page.update_package_button.text() == "Plan update"
    assert page.uninstall_package_button.text() == "Plan uninstall"
    assert page.detail_actions_label.text() == ""
    assert page.detail_actions_label.isHidden()
    assert page.detail_scroll.parentWidget() is (page.detail_container)
    assert page.detail_action_bar.parentWidget() is (page.detail_container)
    action_layout = page.detail_action_bar.layout()
    assert action_layout is not None
    for index in range(action_layout.count()):
        action_item = action_layout.itemAt(index)
        assert action_item is not None
        assert action_item.spacerItem() is None
    assert (
        page.detail_claimants_label.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Ignored
    )
    assert (
        page.detail_claimants_label.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Preferred
    )
    claimant_buttons = page.detail_claimants_label.findChildren(QToolButton)
    claimant_rows = [
        button.parentWidget()
        for button in claimant_buttons
        if button.parentWidget() is not None
    ]
    claimant_child_groups = page.detail_claimants_label.findChildren(
        QWidget,
        "comfyEnvironmentClaimantChildren",
    )
    assert len(claimant_buttons) == 1
    assert len(claimant_rows) == 1
    assert len(claimant_child_groups) == 1
    claimant_row = claimant_rows[0]
    assert claimant_row is not None
    assert claimant_child_groups[0].isHidden()
    assert claimant_buttons[0].text() == "+"
    assert claimant_buttons[0].width() <= 18
    row_labels = claimant_row.findChildren(QLabel)
    dependency_label = next(
        label for label in row_labels if "base-helper" in label.text()
    )
    assert dependency_label.width() > 0
    row_layout = claimant_row.layout()
    assert row_layout is not None
    label_item = row_layout.itemAt(0)
    button_item = row_layout.itemAt(1)
    assert label_item is not None
    assert button_item is not None
    assert label_item.widget() is dependency_label
    assert button_item.widget() is claimant_buttons[0]
    claimant_buttons[0].click()
    _process_events(app)
    assert claimant_buttons[0].text() == "-"
    assert not claimant_child_groups[0].isHidden()
    assert page.detail_claimants_label.height() >= (
        page.detail_claimants_label.sizeHint().height()
    )
    child_layout = claimant_child_groups[0].layout()
    assert child_layout is not None
    assert child_layout.spacing() == 0
    assert claimant_child_groups[0].height() >= (
        claimant_child_groups[0].sizeHint().height()
    )
    child_labels = claimant_child_groups[0].findChildren(QLabel)
    assert len(child_labels) == 2
    for child_label in child_labels:
        assert not child_label.wordWrap()
        assert child_label.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Fixed
    assert child_labels[1].geometry().top() >= child_labels[0].geometry().bottom()
    claimant_buttons[0].click()
    _process_events(app)
    assert claimant_buttons[0].text() == "+"
    assert claimant_child_groups[0].isHidden()
    claimant_labels = page.detail_claimants_label.findChildren(QLabel)
    display_text = "\n".join(QLabel.text(label) for label in claimant_labels)
    assert chr(0x200B) in display_text
    assert chr(0x200B) not in page.detail_claimants_label.text()


def test_environment_page_filter_uses_package_metadata() -> None:
    """Filtering should search package names, claimants, summaries, and tags."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.inventory_filter.setText("ComfyUI-VFI")
    _process_events(app)

    assert page.visible_inventory_item_names() == ("custom-node-helper",)
    assert "ComfyUI-VFI" in page.detail_text()

    page.inventory_filter.setText("requirements.txt")
    _process_events(app)

    assert page.visible_inventory_item_names() == ()


def test_environment_page_search_ranks_name_matches_and_supports_sorting() -> None:
    """Search should favor package names while sort state remains available."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_SearchSortBackend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)

    assert page.visible_inventory_item_names()[0] == "beta-package"
    assert page.detail_title_label.text() == "beta-package  1.0.0"
    raw_title_text = QLabel.text(page.detail_title_label)
    assert '<span style="font-size: 12px; font-weight: 400;">' in raw_title_text
    assert "1.0.0" in raw_title_text.replace(chr(0x200B), "")
    assert "3 extension claimants" in page.detail_meta_label.text()

    page.inventory_filter.setText("helper")
    _process_events(app)

    assert page.visible_inventory_item_names() == (
        "alpha-helper",
        "beta-package",
    )
    assert page.package_list.currentRow() == 0
    assert page.detail_title_label.text() == "alpha-helper  0.1.0"
    assert page.package_list.rowCount() == 2

    page.inventory_filter.clear()
    page._change_inventory_sort(0)
    _process_events(app)

    assert page.visible_inventory_item_names() == (
        "alpha-helper",
        "beta-package",
        "gamma-tool",
    )

    page._change_inventory_sort(2)
    _process_events(app)

    assert page.visible_inventory_item_names()[0] == "beta-package"


def test_environment_package_list_skips_identical_row_rebuilds() -> None:
    """Inventory rendering should not rebuild table rows when row data is unchanged."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_SearchSortBackend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)

    initial_generation = page.package_list.render_generation()
    page._render_filtered_packages()

    assert page.package_list.render_generation() == initial_generation

    page.inventory_filter.setText("helper")
    _process_events(app)
    filtered_generation = page.package_list.render_generation()

    page._render_filtered_packages(select_first=True)

    assert page.package_list.render_generation() == filtered_generation


def test_environment_page_requests_mouse_driven_operation_plan() -> None:
    """Package actions should add visible items to the planned changes queue."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    _process_events(app, cycles=20)

    detail_text = page.detail_text()
    assert "required compatibility follow-ups" in detail_text
    assert page.planned_changes_panel.plan_list.count() == 3
    parent_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(0)
        ),
    )
    triton_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(1)
        ),
    )
    sage_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(2)
        ),
    )
    assert parent_row.title_label.text() == "Update PyTorch runtime"
    assert not hasattr(parent_row, "drag_handle")
    assert triton_row.title_label.text() == "Reinstall Triton"
    assert sage_row.title_label.text() == "Reinstall SageAttention"
    assert parent_row.target_label.text() == "torch, torchvision, torchaudio"
    assert "triton from triton-windows" in triton_row.target_label.text()
    assert sage_row.target_label.text() == ""
    assert sage_row.target_label.isHidden()
    assert triton_row.height() == 40
    assert sage_row.height() == 40
    assert triton_row.move_down_button.isHidden()
    assert triton_row.remove_button.isHidden()
    assert triton_row.badges == ()
    assert sage_row.badges == ()
    assert not hasattr(page.planned_changes_panel, "count_badge")
    assert page.planned_changes_panel.plan_list.item(0).sizeHint().height() == 44
    assert page.planned_changes_panel.plan_list.item(1).sizeHint().height() == 40
    assert page.planned_changes_panel.plan_list.spacing() == 0
    assert page.planned_changes_panel.item_ids() == (
        "plan-item-1",
        "plan-item-2",
        "plan-item-3",
    )
    page.planned_changes_panel.plan_list.setCurrentRow(0)
    _process_events(app)
    assert page.planned_changes_panel.summary_label.text() == (
        "3 changes planned; blocked until issues are resolved."
    )
    assert page.planned_changes_panel.validation_label.text() == ""
    assert not page.planned_changes_panel.summary_label.isHidden()
    assert page.planned_changes_panel.validation_label.isHidden()
    assert page.planned_changes_panel.selected_detail_label.isHidden()
    assert not page.planned_changes_panel.apply_button.isEnabled()


def test_environment_page_adds_uninstall_and_clears_plan() -> None:
    """Package uninstall actions should be queued and clearable."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:manual-tool")
    page.uninstall_package_button.click()
    _process_events(app, cycles=20)

    row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(0)
        ),
    )
    assert row.title_label.text() == "Uninstall manual-tool"
    assert row.target_label.text() == ""
    assert row.target_label.isHidden()
    assert page.planned_changes_panel.selected_detail_label.isHidden()

    page.planned_changes_panel.clear_button.click()
    _process_events(app, cycles=20)

    assert page.planned_changes_panel.plan_list.count() == 0
    assert page.planned_changes_panel.plan_list.isHidden()
    assert not page.planned_changes_panel.empty_label.isHidden()
    assert page.planned_changes_panel.item_ids() == ()
    assert page.planned_changes_panel.empty_label.text() == ("No changes planned.")
    assert page.planned_changes_panel.empty_label.alignment() == (
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    assert (
        page.planned_changes_panel.empty_label.sizePolicy().horizontalPolicy()
        == QSizePolicy.Policy.Expanding
    )
    assert (
        page.planned_changes_panel.empty_label.sizePolicy().verticalPolicy()
        == QSizePolicy.Policy.Fixed
    )
    assert page.planned_changes_panel.summary_label.text() == ""


def test_environment_page_plan_queue_removes_and_reorders_items() -> None:
    """Planned changes should support removal and backend-normalized ordering."""

    app = _app()
    backend = _Backend()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(backend),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    _process_events(app, cycles=20)
    page.select_inventory_item("package:manual-tool")
    page.uninstall_package_button.click()
    _process_events(app, cycles=20)

    parent_row = cast(
        PlanQueueItemWidget,
        page.planned_changes_panel.plan_list.itemWidget(
            page.planned_changes_panel.plan_list.item(0)
        ),
    )
    parent_row.move_down_button.click()
    _process_events(app, cycles=20)

    assert backend.reorder_requests == [
        (2, ("plan-item-4", "plan-item-1", "plan-item-2", "plan-item-3"))
    ]
    assert page.planned_changes_panel.item_ids() == (
        "plan-item-4",
        "plan-item-1",
        "plan-item-2",
        "plan-item-3",
    )

    page.planned_changes_panel.reorder_requested.emit(
        ("plan-item-2", "plan-item-1", "plan-item-3", "plan-item-4")
    )
    _process_events(app, cycles=20)

    assert backend.reorder_requests == [
        (2, ("plan-item-4", "plan-item-1", "plan-item-2", "plan-item-3")),
        (3, ("plan-item-2", "plan-item-1", "plan-item-3", "plan-item-4")),
    ]
    assert page.planned_changes_panel.item_ids()[0] == "plan-item-1"
    assert "Order adjusted" in page.detail_text()

    page.planned_changes_panel.remove_item_requested.emit("plan-item-1")
    _process_events(app, cycles=20)

    assert page.planned_changes_panel.plan_list.count() == 1
    assert not page.planned_changes_panel.plan_list.isHidden()
    assert page.planned_changes_panel.empty_label.isHidden()
    assert page.planned_changes_panel.item_ids() == ("plan-item-4",)


def test_environment_page_apply_button_starts_plan_job_when_applyable() -> None:
    """Apply should request a backend job when the plan is applyable."""

    app = _app()
    backend = _ApplyBackend()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(backend),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    _process_events(app, cycles=20)

    assert page.planned_changes_panel.apply_button.isEnabled()
    expected_revision = cast(Any, page)._maintenance_plan.revision

    page.planned_changes_panel.apply_button.click()
    _process_events(app, cycles=20)

    assert backend.applied_revisions == [expected_revision]
    job_text = page.job_label.text()
    assert job_text.startswith("Maintenance plan queued for execution.") or (
        job_text == "Waiting for Comfy to come back."
    )


def test_environment_page_disables_actions_when_planning_is_unavailable() -> None:
    """Package action buttons should reflect backend planning capability."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(
            _Backend(planning_supported=False)
        ),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)
    page.select_inventory_item("package:torch")

    assert not page.update_package_button.isEnabled()
    assert not page.uninstall_package_button.isEnabled()
    assert "Operation planning is not available" in page.detail_text()


def test_environment_page_uses_package_browser_as_primary_surface() -> None:
    """Package inventory should use a compact selectable package browser."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )

    _process_events(app)

    assert isinstance(page.inventory_filter, SearchLineEdit)
    assert isinstance(page.package_list, PackageInventoryList)
    assert isinstance(page.package_list, TableWidget)
    assert page.package_list.alternatingRowColors()
    assert page.package_list.minimumHeight() <= 140
    assert page.package_list.minimumWidth() >= 380
    assert page.package_list.maximumWidth() >= 440
    assert page.package_list.rowCount() == 7
    assert isinstance(page.planned_changes_panel.plan_list, ListWidget)
    headers = tuple(
        page.package_list.horizontalHeaderItem(column).text()
        for column in range(page.package_list.columnCount())
    )
    assert headers == ("Package", "Version", "Required by")
    assert page.package_list.item(0, 0).text() == "custom-node-helper"
    assert page.package_list.item(0, 1).text() == "1.4.0"
    assert page.package_list.item(0, 2).text() == "3"
    assert page.package_list.columnWidth(2) >= 88
    page._change_inventory_sort(0)
    _process_events(app)
    assert page.package_list.item(0, 0).text() == "custom-node-helper"


def test_environment_page_workbench_layout_does_not_overlap_at_minimum_width() -> None:
    """The package browser, detail inspector, and review shelf should not overlap."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )
    page.resize(1100, 520)
    page.show()

    _process_events(app, cycles=30)

    list_geometry = page.package_list.geometry()
    search_geometry = page.inventory_filter.geometry()
    selector_geometry = page.package_selector.geometry()
    detail_geometry = page.detail_container.geometry()
    plan_geometry = page.planned_changes_panel.geometry()
    assert selector_geometry.right() < detail_geometry.left()
    assert plan_geometry.top() > detail_geometry.bottom()
    assert detail_geometry.left() - selector_geometry.right() >= 8
    assert plan_geometry.top() - detail_geometry.bottom() >= 8
    assert search_geometry.width() <= list_geometry.width()
    assert detail_geometry.height() == selector_geometry.height()
    assert page.detail_action_bar.geometry().top() >= (
        page.detail_scroll.geometry().bottom()
    )
    assert page.restart_button.parentWidget() is not page
    assert "background: transparent" in page.inventory_panel.styleSheet()

    page.close()
    page.deleteLater()
    _process_events(app)


def test_environment_page_adapts_inventory_layout_by_width() -> None:
    """Environment inventory should change layout modes instead of clipping."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )
    page.show()

    page.resize(960, 620)
    _process_events(app, cycles=20)
    assert page.layout_mode() == "wide"
    assert (
        page.package_selector.geometry().right()
        < page.detail_container.geometry().left()
    )
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )

    page.resize(700, 720)
    _process_events(app, cycles=20)
    assert page.layout_mode() == "medium"
    assert (
        page.package_selector.geometry().right()
        < page.detail_container.geometry().left()
    )
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )

    page.resize(500, 860)
    _process_events(app, cycles=20)
    assert page.layout_mode() == "narrow"
    assert (
        page.detail_container.geometry().top()
        > page.package_selector.geometry().bottom()
    )
    assert page.package_selector.geometry().width() >= (
        page.inventory_body.geometry().width() - 4
    )
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )
    assert page.minimumSizeHint().width() <= page.width()

    page.resize(360, 920)
    _process_events(app, cycles=20)
    page._sync_layout_mode(360)
    assert page.layout_mode() == "compact"
    assert page.package_selector.minimumWidth() == 0
    assert page.package_list.minimumWidth() == 0
    assert page.detail_container.minimumWidth() == 0
    assert page.planned_changes_panel.minimumWidth() == 0

    page.close()
    page.deleteLater()
    _process_events(app)


def test_environment_page_keeps_planned_changes_accessible_when_narrow() -> None:
    """Planned changes should remain visible after narrow-mode reflow."""

    app = _app()
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: object(),
    )
    page.resize(500, 860)
    page.show()
    _process_events(app, cycles=20)

    page.select_inventory_item("package:torch")
    page.update_package_button.click()
    _process_events(app, cycles=20)

    assert page.layout_mode() == "narrow"
    assert page.planned_changes_panel.isVisible()
    assert page.planned_changes_panel.plan_list.count() == 3
    assert (
        page.planned_changes_panel.geometry().top()
        > page.detail_container.geometry().bottom()
    )

    page.close()
    page.deleteLater()
    _process_events(app)


def _environment_page(
    *,
    comfy_environment_service: ComfyEnvironmentService,
    open_reconfigure_window: Callable[[], object],
    error_presenter: Any | None = None,
) -> ComfyEnvironmentPage:
    """Create a Comfy environment settings page for widget contract tests."""

    page = ComfyEnvironmentPage(
        comfy_environment_service,
        open_reconfigure_window=open_reconfigure_window,
        error_presenter=error_presenter,
        task_runner_factory=_task_runner_factory,
    )
    page.refresh()
    return page


def _app() -> QApplication:
    """Return the active QApplication instance for widget contract tests."""

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return cast("QApplication", app)


def test_environment_page_stylesheet_refreshes_after_qfluent_theme_switch() -> None:
    """Comfy environment custom panel styles should refresh from QFluent theme changes."""

    app = _app()
    setTheme(Theme.DARK)
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: None,
    )
    try:
        dark_style = page.styleSheet()

        setTheme(Theme.LIGHT)
        app.processEvents()

        assert page.styleSheet() != dark_style
        assert _css_color(settings_card_border_color()) in page.styleSheet()
    finally:
        page.close()
        page.deleteLater()
        app.processEvents()


def _css_color(color: QColor) -> str:
    """Return the stylesheet rgba representation for a QColor-like test value."""

    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def test_environment_page_reports_operation_failures_through_presenter() -> None:
    """Exception-backed environment operations should open the unified error modal."""

    _app()
    presented: list[dict[str, Any]] = []
    page = _environment_page(
        comfy_environment_service=ComfyEnvironmentService(_Backend()),
        open_reconfigure_window=lambda: None,
        error_presenter=type(
            "_Presenter",
            (),
            {"show_exception_report": lambda _self, **kwargs: presented.append(kwargs)},
        )(),
    )
    failure = RuntimeError("plan failed")

    page._show_operation_failure(
        ComfyEnvironmentOperationFailure(
            operation="comfy_environment.plan.apply",
            title="Apply planned changes failed",
            message="Planned changes could not be applied.",
            error=failure,
            package_name="torch",
            values={"revision": 3},
        )
    )

    assert presented[0]["title"] == "Apply planned changes failed"
    assert presented[0]["stage"] == "settings"
    assert presented[0]["error"] is failure
    context = presented[0]["context"]
    assert context.operation == "comfy_environment.plan.apply"
    assert context.package_name == "torch"
    assert context.values["revision"] == 3
    page.close()
    page.deleteLater()


def _package(
    *,
    name: str,
    version: str,
    summary: str | None,
    summary_source: str,
    attribution: str,
    claimants: tuple[ComfyPackageClaimant, ...] = (),
    tags: tuple[ComfyPackageManagementTag, ...] = (),
) -> ComfyEnvironmentPackage:
    """Return one package DTO for Settings tests."""

    return ComfyEnvironmentPackage(
        name=name,
        normalized_name=name.lower(),
        version=version,
        claimants=claimants,
        management_tags=tags,
        attribution=attribution,
        summary=summary,
        summary_source=summary_source,
        installer="pip",
    )


def _claimant(
    name: str,
    requirement: str,
    *,
    required_via: str | None = None,
) -> ComfyPackageClaimant:
    """Return one custom-node claimant for Settings tests."""

    return ComfyPackageClaimant(
        kind="custom-node",
        claimant_id=name,
        display_name=name,
        requirement=requirement,
        source_path=f"E:\\ComfyUI\\custom_nodes\\{name}\\requirements.txt",
        required_via=required_via,
    )


def _tag(tag_id: str, display_name: str) -> ComfyPackageManagementTag:
    """Return one supported management tag for Settings tests."""

    return ComfyPackageManagementTag(
        kind="supported-runtime",
        tag_id=tag_id,
        display_name=display_name,
        supported_actions=("plan-update",),
    )


def _plan(
    operation: str,
    affected_packages: tuple[str, ...],
) -> ComfyEnvironmentOperationPlan:
    """Return one operation plan for Settings tests."""

    return ComfyEnvironmentOperationPlan(
        plan_id="envplan-1",
        operation=operation,
        affected_packages=affected_packages,
        summary=f"Plan {operation}.",
        warnings=("Review before applying.",),
        requires_comfy_stop=True,
        requires_restart=True,
        requires_detached_runner=True,
    )


def _maintenance_plan(
    *,
    items: tuple[ComfyMaintenancePlanItem, ...] = (),
    revision: int = 0,
    message: str | None = None,
    blocked: bool = True,
) -> ComfyMaintenancePlan:
    """Return a maintenance plan for Settings tests."""

    blockers = (
        (
            ComfyMaintenancePlanIssue(
                code="package-mutation-unavailable",
                message="Package execution is not available.",
            ),
        )
        if items and blocked
        else ()
    )
    affected_packages = {
        package for item in items for package in item.affected_packages
    }
    return ComfyMaintenancePlan(
        schema_version=1,
        plan_id="current",
        environment_id="E:\\ComfyUI",
        revision=revision,
        items=items,
        execution_phases=(
            (
                ComfyMaintenanceExecutionPhase(
                    phase_id="phase-1",
                    title="Package maintenance",
                    item_ids=tuple(item.item_id for item in items),
                    requires_comfy_stop=True,
                    requires_comfy_restart=True,
                ),
            )
            if items
            else ()
        ),
        warnings=tuple(warning for item in items for warning in item.warnings),
        blockers=blockers,
        summary=ComfyMaintenancePlanSummary(
            item_count=len(items),
            affected_package_count=len(affected_packages),
            requires_comfy_stop=bool(items),
            requires_comfy_restart=bool(items),
            applyable=bool(items) and not blockers,
        ),
        last_validation_message=message,
    )


def _plan_item(
    *,
    item_id: str,
    title: str,
    operation: str,
    affected: tuple[str, ...],
    target_kind: str = "package",
    target_id: str | None = None,
    target_display: str | None = None,
    install_requirements: tuple[str, ...] | None = None,
    generated: bool = False,
    generated_by_item_id: str | None = None,
    can_remove: bool = True,
    can_reorder: bool = True,
) -> ComfyMaintenancePlanItem:
    """Return a maintenance plan item for Settings tests."""

    target = target_id or affected[0]
    return ComfyMaintenancePlanItem(
        item_id=item_id,
        operation=operation,
        title=title,
        target=ComfyMaintenancePlanTarget(
            kind=target_kind,
            target_id=target,
            display_name=target_display or target,
        ),
        requested=ComfyMaintenancePlanRequest(
            source="backend-policy" if generated else "user",
            package_name=target,
        ),
        generated=generated,
        generated_by_item_id=generated_by_item_id,
        relationship=(
            "required-compatibility-follow-up" if generated else "user-requested"
        ),
        affected_packages=affected,
        install_requirements=install_requirements or affected,
        requires_comfy_stop=True,
        requires_comfy_restart=True,
        locked_relative_order=generated,
        can_remove=can_remove,
        can_reorder=can_reorder,
        warnings=(
            (
                ComfyMaintenancePlanIssue(
                    code="runtime-compatibility",
                    message="Required by PyTorch update.",
                    item_id=item_id,
                ),
            )
            if generated
            else ()
        ),
        blockers=(),
    )


def _user_items(plan: ComfyMaintenancePlan) -> tuple[ComfyMaintenancePlanItem, ...]:
    """Return user-removable items from a fake plan."""

    return tuple(item for item in plan.items if item.can_remove)


def _process_events(app: QApplication, *, cycles: int = 10) -> None:
    """Process deferred Qt events."""

    for _ in range(cycles):
        app.processEvents()
        time.sleep(0.01)

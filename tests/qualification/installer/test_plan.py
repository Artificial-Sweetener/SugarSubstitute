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

"""Qualify installer plan persistence and onboarding action exchange."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast


from sugarsubstitute_shared.installer_qualification import (
    INSTALLER_QUALIFICATION_PLAN_ENV,
    InstallerQualificationPlan,
)
from substitute.presentation.onboarding.installer_qualification import (
    OnboardingQualificationDriver,
)


def test_qualification_plan_round_trips_through_environment(tmp_path: Path) -> None:
    """Installer children should inherit one exact typed qualification plan."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
        force_cpu_mode=True,
    )

    restored = InstallerQualificationPlan.from_environment(
        {INSTALLER_QUALIFICATION_PLAN_ENV: plan.to_json()}
    )

    assert restored == plan


def test_legacy_qualification_plan_defaults_cpu_override_off(tmp_path: Path) -> None:
    """Older serialized plans should remain compatible without forcing CPU."""

    payload = {
        "schema_version": 2,
        "token": "qualification-token",
        "install_root": str((tmp_path / "install").resolve()),
        "endpoint_host": "127.0.0.1",
        "endpoint_port": 8188,
        "event_log_path": str((tmp_path / "events.jsonl").resolve()),
        "timeout_seconds": 45.0,
    }

    restored = InstallerQualificationPlan.from_json(json.dumps(payload))

    assert restored.force_cpu_mode is False


def test_managed_qualification_applies_explicit_cpu_choice(tmp_path: Path) -> None:
    """The production managed page should receive the platform qualification choice."""

    plan = InstallerQualificationPlan(
        token="qualification-token",
        install_root=(tmp_path / "install").resolve(),
        endpoint_host="127.0.0.1",
        endpoint_port=48188,
        event_log_path=(tmp_path / "events.jsonl").resolve(),
        timeout_seconds=45.0,
        target_mode="managed_local",
        managed_workspace_path=(tmp_path / "comfyui").resolve(),
        force_cpu_mode=True,
    )
    values: dict[str, object] = {}
    checkbox = SimpleNamespace(
        setChecked=lambda value: values.__setitem__("force_cpu", value)
    )
    window = SimpleNamespace(
        managed_local_page=SimpleNamespace(
            runtime_summary_panel=SimpleNamespace(force_cpu_checkbox=checkbox)
        )
    )
    widgets = {
        "OnboardingManagedHostEdit": SimpleNamespace(
            setText=lambda value: values.__setitem__("host", value)
        ),
        "OnboardingManagedPortSpinBox": SimpleNamespace(
            setValue=lambda value: values.__setitem__("port", value)
        ),
        "OnboardingManagedWorkspaceEdit": SimpleNamespace(
            setText=lambda value: values.__setitem__("workspace", value)
        ),
    }
    driver = cast(
        OnboardingQualificationDriver,
        SimpleNamespace(
            _plan=plan,
            _window=window,
            _wait_for_page=lambda _page: None,
            _widget=lambda _type, name: widgets[name],
        ),
    )

    OnboardingQualificationDriver._configure_managed_target(driver)

    assert values == {
        "force_cpu": True,
        "host": "127.0.0.1",
        "port": 48188,
        "workspace": str((tmp_path / "comfyui").resolve()),
    }

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

"""Qualify historical onboarding shell handoff and terminal failure evidence."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from launcher.sugarsubstitute_launcher.install_layout import InstallLayout
from tools.ci.drive_windows_installer import (
    WindowsInstallerAutomationError,
    _complete_historical_onboarding,
    _wait_for_historical_main_shell,
)


def test_historical_onboarding_accepts_preset_root_and_reaches_real_main_shell(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A preset install root must begin at target selection and complete onboarding."""

    page_controls = [
        "OnboardingInstallRootEdit",
        "OnboardingTargetCardRadio_managed_local",
        "OnboardingManagedWorkspaceEdit",
        "OnboardingManagedModelRootEdit",
        "OnboardingCivitaiApiKeyEdit",
        "OnboardingProgressStatus",
        "OnboardingCompletionSurface",
    ]
    state = {"page": 1, "main": False, "force_cpu": False}
    handoff_events: list[str] = []
    values: dict[str, object] = {}

    class _Control:
        """Expose the UI Automation patterns used by historical qualification."""

        def __init__(self, suffix: str) -> None:
            self.suffix = suffix
            self.element_info = SimpleNamespace(automation_id=f"qt_{suffix}")
            self.iface_range_value = SimpleNamespace(
                SetValue=lambda value: values.__setitem__(self.suffix, value)
            )

        def is_visible(self) -> bool:
            """Expose only the active page and its controls."""

            if self.suffix == "ForceCpuModeCheckBox":
                return state["page"] == 2
            if self.suffix in page_controls:
                return self.suffix == page_controls[state["page"]]
            return True

        def is_enabled(self) -> bool:
            """Keep deterministic controls actionable."""

            return True

        def window_text(self) -> str:
            """Return terminal primary labels when qualification requires them."""

            if self.suffix == "ForceCpuModeCheckBox":
                return "Force CPU mode"
            if state["page"] == 5:
                return "Review setup"
            if state["page"] == 6:
                return "Open Substitute"
            return "Continue"

        def invoke(self) -> None:
            """Advance the production primary route or reveal the main shell."""

            if self.suffix == "OnboardingTargetCardRadio_managed_local":
                values[self.suffix] = True
            elif self.suffix == "OnboardingPrimaryButton":
                if state["page"] == 6:
                    handoff_events.append("open")
                    state["main"] = True
                else:
                    state["page"] += 1

        def toggle(self) -> None:
            """Toggle only the checkbox through the production UIA pattern."""

            if self.suffix != "ForceCpuModeCheckBox":
                raise AssertionError("Only the checkbox exposes TogglePattern.")
            state["force_cpu"] = not state["force_cpu"]

        def get_toggle_state(self) -> int:
            """Return the production UI Automation toggle state."""

            return int(state["force_cpu"])

        def select(self) -> None:
            """Reject the unsupported SelectionItem route exposed by the wrapper."""

            raise AssertionError("Qt radio choices must use their Invoke action.")

        def set_edit_text(self, value: str) -> None:
            """Record a production line-edit value."""

            values[self.suffix] = value

    controls = [
        *(_Control(control) for control in page_controls),
        _Control("OnboardingPrimaryButton"),
        _Control("OnboardingManagedHostEdit"),
        _Control("OnboardingManagedPortSpinBox"),
        _Control("ForceCpuModeCheckBox"),
    ]
    onboarding = SimpleNamespace(
        element_info=SimpleNamespace(process_id=100),
        is_visible=lambda: True,
        descendants=lambda: controls,
    )
    toolbar = _Control("WorkflowChromeToolbar")
    main_window = SimpleNamespace(
        element_info=SimpleNamespace(process_id=200),
        is_visible=lambda: state["main"],
        descendants=lambda: [toolbar],
    )
    unattributed_window = SimpleNamespace(
        element_info=SimpleNamespace(process_id=None),
        is_visible=lambda: True,
        descendants=lambda: [],
    )
    desktop = SimpleNamespace(
        windows=lambda: [unattributed_window, onboarding, main_window]
    )
    monkeypatch.setattr("tools.ci.drive_windows_installer.time.sleep", lambda _: None)

    main_pid = _complete_historical_onboarding(
        desktop=desktop,
        onboarding_pid=100,
        install_root=tmp_path / "installed",
        managed_workspace_path=tmp_path / "comfyui",
        managed_model_root=tmp_path / "models",
        endpoint_host="127.0.0.1",
        endpoint_port=8188,
        before_open_substitute=lambda: handoff_events.append("candidate"),
        deadline=float("inf"),
    )

    assert main_pid == 200
    assert values["OnboardingTargetCardRadio_managed_local"] is True
    assert values["OnboardingManagedWorkspaceEdit"] == str(
        (tmp_path / "comfyui").resolve()
    )
    assert values["OnboardingManagedModelRootEdit"] == str(
        (tmp_path / "models").resolve()
    )
    assert values["OnboardingManagedPortSpinBox"] == 8188
    assert state["force_cpu"] is True
    assert handoff_events == ["candidate", "open"]


def test_historical_windows_shell_wait_surfaces_terminal_startup_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Windows UI qualification must stop when the launched app reports failure."""

    layout = InstallLayout.from_root(tmp_path / "installed")
    trace_path = layout.appdata_dir / "diagnostics" / "logs" / "startup-trace.jsonl"
    trace_path.parent.mkdir(parents=True)
    trace_path.write_text(
        json.dumps({"event": "startup.managed.failure"}) + "\n",
        encoding="utf-8",
    )
    managed_output = layout.root / "historical-managed-comfy-startup.log"
    managed_output.write_text("managed Comfy exited with code 1\n", encoding="utf-8")
    monkeypatch.setattr("tools.ci.drive_windows_installer.time.sleep", lambda _: None)

    with pytest.raises(
        WindowsInstallerAutomationError,
        match="startup.managed.failure",
    ) as error:
        _wait_for_historical_main_shell(
            desktop=SimpleNamespace(windows=lambda: []),
            excluded_process_id=100,
            install_root=layout.root,
            deadline=float("inf"),
        )

    assert "managed Comfy exited with code 1" in str(error.value)

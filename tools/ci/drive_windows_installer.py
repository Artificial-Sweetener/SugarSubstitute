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

"""Drive a historical Windows setup executable through its native UI."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from collections.abc import Sequence
from typing import Any, Protocol

_UI_PHASE_TIMEOUT_SECONDS = 60.0
_PROVISIONING_TIMEOUT_SECONDS = 1_800.0
_MAIN_SHELL_TIMEOUT_SECONDS = 300.0


class WindowsInstallerAutomationError(RuntimeError):
    """Report a packaged Windows installer that cannot complete its real UI."""


class _InstallerProcess(Protocol):
    """Expose the process operations required by installer automation."""

    pid: int
    returncode: int | None

    def poll(self) -> int | None:
        """Return the exit status when the installer has stopped."""

    def wait(self, timeout: float | None = None) -> int:
        """Wait for the installer to stop and return its exit status."""


class _StartupInfo(ctypes.Structure):
    """Describe a process launched on an isolated Windows desktop."""

    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _ProcessInformation(ctypes.Structure):
    """Receive handles for an isolated Windows process."""

    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _NativeInstallerProcess:
    """Own the native process handle used by isolated-desktop automation."""

    _WAIT_TIMEOUT = 258
    _STILL_ACTIVE = 259

    def __init__(self, *, handle: int, pid: int) -> None:
        """Retain the installer handle and identifier."""

        self._handle = handle
        self.pid = pid
        self.returncode: int | None = None

    def poll(self) -> int | None:
        """Return the installer exit status when available."""

        exit_code = wintypes.DWORD()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        if not kernel32.GetExitCodeProcess(self._handle, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if exit_code.value == self._STILL_ACTIVE:
            return None
        self.returncode = int(exit_code.value)
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        """Wait for the installer to stop within the supplied timeout."""

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        milliseconds = 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1_000))
        result = kernel32.WaitForSingleObject(self._handle, milliseconds)
        if result == self._WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired(
                str(self.pid),
                0.0 if timeout is None else timeout,
            )
        if result != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        return_code = self.poll()
        if return_code is None:
            raise WindowsInstallerAutomationError(
                "Installer remained active after its process handle was signaled."
            )
        return return_code


def drive_windows_installer(
    *,
    installer_path: Path,
    install_root: Path,
    manifest_url: str,
    timeout_seconds: float,
    managed_workspace_path: Path,
    managed_model_root: Path,
    endpoint_host: str,
    endpoint_port: int,
) -> int:
    """Complete installer and onboarding UI through the historical main shell."""

    if os.name != "nt":
        raise WindowsInstallerAutomationError(
            "Historical Windows installer automation requires Windows."
        )
    environment = dict(os.environ)
    environment.pop("QT_QPA_PLATFORM", None)
    process = _launch_on_isolated_desktop(
        command=(
            str(installer_path.resolve()),
            f"--install-root={install_root.resolve()}",
            f"--manifest-url={manifest_url}",
        ),
        working_directory=installer_path.resolve().parent,
        environment=environment,
    )
    from pywinauto import Desktop  # type: ignore[import-untyped]

    desktop = Desktop(backend="uia")
    deadline = time.monotonic() + timeout_seconds
    try:
        setup_window = _wait_for_setup_window(
            desktop=desktop,
            process=process,
            deadline=deadline,
        )
        onboarding_pid = _wait_for_onboarding_window(
            desktop=desktop,
            setup_window=setup_window,
            process=process,
            deadline=deadline,
        )
        main_pid = _complete_historical_onboarding(
            desktop=desktop,
            onboarding_pid=onboarding_pid,
            managed_workspace_path=managed_workspace_path,
            managed_model_root=managed_model_root,
            endpoint_host=endpoint_host,
            endpoint_port=endpoint_port,
            deadline=deadline,
        )
        if process.poll() is None:
            _terminate_process(process.pid)
        return main_pid
    except Exception:
        _terminate_process_tree(process.pid)
        raise


def _wait_for_setup_window(
    *,
    desktop: Any,
    process: _InstallerProcess,
    deadline: float,
) -> Any:
    """Wait for the real setup window or a premature installer exit."""

    while time.monotonic() < deadline:
        windows = [
            window
            for window in desktop.windows()
            if window.window_text() == "SugarSubstitute Setup"
        ]
        if windows:
            return windows[-1]
        return_code = process.poll()
        if return_code is not None:
            raise WindowsInstallerAutomationError(
                "Historical installer exited before showing its setup window: "
                f"{return_code}."
            )
        time.sleep(0.1)
    raise TimeoutError("Historical installer did not show its setup window.")


def _wait_for_onboarding_window(
    *,
    desktop: Any,
    setup_window: Any,
    process: _InstallerProcess,
    deadline: float,
) -> int:
    """Exercise every installer phase until installed onboarding appears."""

    invoked_action: str | None = None
    awaiting_action_transition = False
    while time.monotonic() < deadline:
        for window in desktop.windows():
            automation_id = window.element_info.automation_id or ""
            if automation_id.endswith("OnboardingWindow") and window.is_visible():
                onboarding_pid = int(window.element_info.process_id)
                try:
                    process.wait(timeout=30.0)
                except subprocess.TimeoutExpired:
                    return onboarding_pid
                if process.returncode != 0:
                    raise WindowsInstallerAutomationError(
                        "Historical installer failed after onboarding handoff: "
                        f"{process.returncode}."
                    )
                return onboarding_pid
        try:
            install_button = _control_by_suffix(
                setup_window,
                "LauncherPrimaryButton",
            )
        except WindowsInstallerAutomationError:
            install_button = None
        if install_button is not None:
            action = install_button.window_text()
            if not install_button.is_enabled():
                awaiting_action_transition = False
            if (
                install_button.is_enabled()
                and install_button.is_visible()
                and (not awaiting_action_transition or action != invoked_action)
            ):
                install_button.invoke()
                invoked_action = action
                awaiting_action_transition = True
        return_code = process.poll()
        if return_code is not None and return_code != 0:
            raise WindowsInstallerAutomationError(
                "Historical installer exited before onboarding appeared: "
                f"{return_code}."
            )
        time.sleep(0.2)
    raise TimeoutError("Historical installer did not hand off to onboarding.")


def _control_by_suffix(window: Any, suffix: str) -> Any:
    """Return one descendant identified by its stable Qt automation suffix."""

    controls = [
        control
        for control in window.descendants()
        if (control.element_info.automation_id or "").endswith(suffix)
    ]
    if len(controls) != 1:
        raise WindowsInstallerAutomationError(
            f"Expected one historical installer control {suffix!r}; "
            f"found {len(controls)}."
        )
    return controls[0]


def _complete_historical_onboarding(
    *,
    desktop: Any,
    onboarding_pid: int,
    managed_workspace_path: Path,
    managed_model_root: Path,
    endpoint_host: str,
    endpoint_port: int,
    deadline: float,
) -> int:
    """Drive installed historical onboarding through its Open Substitute action."""

    onboarding = _wait_for_process_window(
        desktop=desktop,
        process_id=onboarding_pid,
        required_control="OnboardingInstallRootEdit",
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _invoke_primary(
        onboarding,
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_visible_control(
        onboarding,
        "OnboardingTargetCardRadio_managed_local",
        _phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _invoke_choice(onboarding, "OnboardingTargetCardRadio_managed_local")
    _invoke_primary(
        onboarding,
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_visible_control(
        onboarding,
        "OnboardingManagedWorkspaceEdit",
        _phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _set_text(onboarding, "OnboardingManagedHostEdit", endpoint_host)
    _set_value(onboarding, "OnboardingManagedPortSpinBox", endpoint_port)
    _set_text(
        onboarding,
        "OnboardingManagedWorkspaceEdit",
        str(managed_workspace_path.resolve()),
    )
    _invoke_primary(
        onboarding,
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_visible_control(
        onboarding,
        "OnboardingManagedModelRootEdit",
        _phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _set_text(
        onboarding,
        "OnboardingManagedModelRootEdit",
        str(managed_model_root.resolve()),
    )
    _invoke_primary(
        onboarding,
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_visible_control(
        onboarding,
        "OnboardingCivitaiApiKeyEdit",
        _phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _invoke_primary(
        onboarding,
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_visible_control(
        onboarding,
        "OnboardingProgressStatus",
        _phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_primary_action(
        onboarding,
        "Review setup",
        _phase_deadline(deadline, _PROVISIONING_TIMEOUT_SECONDS),
    )
    _invoke_primary(
        onboarding,
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_visible_control(
        onboarding,
        "OnboardingCompletionSurface",
        _phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _wait_for_primary_action(
        onboarding,
        "Open Substitute",
        _phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    _invoke_primary(
        onboarding,
        deadline=_phase_deadline(deadline, _UI_PHASE_TIMEOUT_SECONDS),
    )
    return _wait_for_historical_main_shell(
        desktop=desktop,
        excluded_process_id=onboarding_pid,
        deadline=_phase_deadline(deadline, _MAIN_SHELL_TIMEOUT_SECONDS),
    )


def _wait_for_process_window(
    *,
    desktop: Any,
    process_id: int,
    required_control: str,
    deadline: float,
) -> Any:
    """Return one visible process window exposing the required production control."""

    while time.monotonic() < deadline:
        for window in desktop.windows():
            if int(window.element_info.process_id) != process_id:
                continue
            if not window.is_visible():
                continue
            try:
                control = _control_by_suffix(window, required_control)
            except WindowsInstallerAutomationError:
                continue
            if control.is_visible():
                return window
        time.sleep(0.1)
    raise TimeoutError(
        f"Historical onboarding did not expose {required_control}.\n"
        + _desktop_automation_snapshot(desktop)
    )


def _wait_for_visible_control(window: Any, suffix: str, deadline: float) -> Any:
    """Wait for one visible production control identified by automation suffix."""

    while time.monotonic() < deadline:
        try:
            control = _control_by_suffix(window, suffix)
        except WindowsInstallerAutomationError:
            control = None
        if control is not None and control.is_visible():
            return control
        time.sleep(0.1)
    raise TimeoutError(
        f"Historical onboarding did not reveal {suffix}.\n"
        + _window_automation_snapshot(window)
    )


def _invoke_primary(window: Any, *, deadline: float) -> None:
    """Invoke the enabled production onboarding primary action."""

    while time.monotonic() < deadline:
        primary = _control_by_suffix(window, "OnboardingPrimaryButton")
        if primary.is_visible() and primary.is_enabled():
            primary.invoke()
            return
        time.sleep(0.1)
    raise TimeoutError(
        "Historical onboarding primary action did not become enabled.\n"
        + _window_automation_snapshot(window)
    )


def _wait_for_primary_action(window: Any, action: str, deadline: float) -> None:
    """Wait for one terminal onboarding action label."""

    while time.monotonic() < deadline:
        primary = _control_by_suffix(window, "OnboardingPrimaryButton")
        if (
            primary.is_visible()
            and primary.is_enabled()
            and primary.window_text() == action
        ):
            return
        time.sleep(0.2)
    raise TimeoutError(
        f"Historical onboarding did not expose {action!r}.\n"
        + _window_automation_snapshot(window)
    )


def _invoke_choice(window: Any, suffix: str) -> None:
    """Invoke one visible target-choice radio through its UI Automation pattern."""

    control = _control_by_suffix(window, suffix)
    if not control.is_visible() or not control.is_enabled():
        raise WindowsInstallerAutomationError(
            f"Historical onboarding choice is not actionable: {suffix}."
        )
    select = getattr(control, "select", None)
    if callable(select):
        select()
    else:
        control.invoke()


def _set_text(window: Any, suffix: str, value: str) -> None:
    """Set one visible historical line edit through UI Automation."""

    control = _control_by_suffix(window, suffix)
    control.set_edit_text(value)


def _set_value(window: Any, suffix: str, value: int) -> None:
    """Set one visible historical numeric field through UI Automation."""

    control = _control_by_suffix(window, suffix)
    control.set_value(value)


def _wait_for_historical_main_shell(
    *,
    desktop: Any,
    excluded_process_id: int,
    deadline: float,
) -> int:
    """Require splash completion and the historical workflow toolbar."""

    while time.monotonic() < deadline:
        for window in desktop.windows():
            process_id = int(window.element_info.process_id)
            if process_id == excluded_process_id or not window.is_visible():
                continue
            try:
                toolbar = _control_by_suffix(window, "WorkflowChromeToolbar")
            except WindowsInstallerAutomationError:
                continue
            if toolbar.is_visible():
                return process_id
        time.sleep(0.2)
    raise TimeoutError(
        "Historical Open Substitute did not reveal the main shell.\n"
        + _desktop_automation_snapshot(desktop)
    )


def _phase_deadline(overall_deadline: float, timeout_seconds: float) -> float:
    """Bound one UI transition without extending the overall qualification."""

    return min(overall_deadline, time.monotonic() + timeout_seconds)


def _desktop_automation_snapshot(desktop: Any) -> str:
    """Describe visible windows and controls after an automation timeout."""

    snapshots: list[str] = []
    for window in desktop.windows():
        process_id = getattr(window.element_info, "process_id", "unknown")
        snapshots.append(
            f"window pid={process_id} text={window.window_text()!r} "
            f"visible={window.is_visible()}\n{_window_automation_snapshot(window)}"
        )
    return "\n".join(snapshots) or "<no desktop windows>"


def _window_automation_snapshot(window: Any) -> str:
    """Describe a bounded set of UI Automation descendants for diagnostics."""

    controls: list[str] = []
    for control in window.descendants()[:200]:
        automation_id = control.element_info.automation_id or ""
        if not automation_id:
            continue
        controls.append(
            f"{automation_id} text={control.window_text()!r} "
            f"visible={control.is_visible()} enabled={control.is_enabled()}"
        )
    return "\n".join(controls) or "<no identified controls>"


def _launch_on_isolated_desktop(
    *,
    command: Sequence[str],
    working_directory: Path,
    environment: dict[str, str],
) -> _NativeInstallerProcess:
    """Launch the native setup on a non-interactive Windows desktop."""

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.CreateDesktopW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    user32.CreateDesktopW.restype = wintypes.HANDLE
    user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
    user32.SetThreadDesktop.restype = wintypes.BOOL
    kernel32.CreateProcessW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfo),
        ctypes.POINTER(_ProcessInformation),
    ]
    kernel32.CreateProcessW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    desktop_name = f"SugarSubstituteQualification-{os.getpid()}-{time.time_ns()}"
    desktop_handle = user32.CreateDesktopW(
        desktop_name,
        None,
        None,
        0,
        0x10000000,
        None,
    )
    if not desktop_handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if not user32.SetThreadDesktop(desktop_handle):
        raise ctypes.WinError(ctypes.get_last_error())

    startup = _StartupInfo()
    startup.cb = ctypes.sizeof(startup)
    startup.lpDesktop = f"WinSta0\\{desktop_name}"
    process_information = _ProcessInformation()
    command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
    environment_block = ctypes.create_unicode_buffer(
        "\0".join(f"{key}={value}" for key, value in environment.items()) + "\0\0"
    )
    created = kernel32.CreateProcessW(
        str(Path(command[0]).resolve()),
        command_line,
        None,
        None,
        False,
        0x00000400,
        environment_block,
        str(working_directory),
        ctypes.byref(startup),
        ctypes.byref(process_information),
    )
    if not created:
        raise ctypes.WinError(ctypes.get_last_error())
    kernel32.CloseHandle(process_information.hThread)
    return _NativeInstallerProcess(
        handle=int(process_information.hProcess),
        pid=int(process_information.dwProcessId),
    )


def _terminate_process_tree(pid: int) -> None:
    """Terminate only the failed installer process tree."""

    subprocess.run(  # noqa: S603
        ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        check=False,
    )


def _terminate_process(pid: int) -> None:
    """Terminate only a lingering setup parent after handoff proof completes."""

    subprocess.run(  # noqa: S603
        ["taskkill.exe", "/PID", str(pid), "/F"],
        capture_output=True,
        check=False,
    )


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    """Parse historical Windows installer automation arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--manifest-url", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=3_600.0)
    parser.add_argument("--managed-workspace", type=Path, required=True)
    parser.add_argument("--managed-model-root", type=Path, required=True)
    parser.add_argument("--endpoint-host", default="127.0.0.1")
    parser.add_argument("--endpoint-port", type=int, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Drive one Windows setup executable and emit its revealed main-shell PID."""

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    main_shell_pid = drive_windows_installer(
        installer_path=args.installer,
        install_root=args.install_root,
        manifest_url=args.manifest_url,
        timeout_seconds=args.timeout_seconds,
        managed_workspace_path=args.managed_workspace,
        managed_model_root=args.managed_model_root,
        endpoint_host=args.endpoint_host,
        endpoint_port=args.endpoint_port,
    )
    print(json.dumps({"main_shell_pid": main_shell_pid}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

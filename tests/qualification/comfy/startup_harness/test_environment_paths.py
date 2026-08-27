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

"""Test startup-harness environment and installation path routing."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
from tools import startup_harness


def test_app_managed_environment_overrides_can_defer_input_sam() -> None:
    """App-managed diagnostics should opt into no-eager-SAM only when requested."""

    default_overrides = startup_harness.app_managed_environment_overrides(False)
    defer_overrides = startup_harness.app_managed_environment_overrides(True)
    output_overrides = startup_harness.app_managed_environment_overrides(
        False,
        managed_comfy_output_path=Path("managed-comfy.log"),
        managed_comfy_output_timeline_path=Path("managed-comfy-timeline.jsonl"),
    )

    assert default_overrides["SUGAR_SUBSTITUTE_STARTUP_HARNESS"] == "1"
    assert default_overrides["SUBSTITUTE_BACKEND_DIAGNOSTICS"] == "cube-library,startup"
    assert "SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM" not in default_overrides
    assert defer_overrides["SUGAR_SUBSTITUTE_STARTUP_HARNESS_DEFER_INPUT_SAM"] == "1"
    assert (
        output_overrides[startup_harness.APP_MANAGED_COMFY_OUTPUT_LOG_ENV]
        == "managed-comfy.log"
    )
    assert (
        output_overrides[startup_harness.APP_MANAGED_COMFY_OUTPUT_TIMELINE_ENV]
        == "managed-comfy-timeline.jsonl"
    )


def test_direct_comfy_environment_overrides_need_no_desktop_model_root(
    tmp_path: Path,
) -> None:
    """BackEnd prestartup owns model roots without harness environment state."""

    comfy_root = tmp_path / "ComfyUI"
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    overrides = startup_harness.direct_comfy_environment_overrides(paths)

    assert "SUGARSUB_MANAGED_MODEL_ROOT" not in overrides
    assert overrides["PATH"].startswith(str(paths.comfy_python.parent))
    assert overrides["PYTHONIOENCODING"] == "utf-8"
    assert overrides["QT_QPA_PLATFORM"] == "offscreen"
    assert overrides["SUBSTITUTE_BACKEND_DIAGNOSTICS"] == "cube-library,startup"
    assert overrides["SUGAR_SUBSTITUTE_STARTUP_HARNESS"] == "1"
    assert overrides["SUGARCUBES_DIAGNOSTICS"] == "1"


def test_harness_resolves_installed_sugarsubstitute_layout(tmp_path: Path) -> None:
    """App-managed measurements should run against a packaged installation."""

    install_root = tmp_path / "SugarSubstitute"
    installed_python = install_root / "runtime" / ".venv" / "Scripts" / "python.exe"
    installed_main = install_root / "app" / "main.py"
    installed_python.parent.mkdir(parents=True)
    installed_python.write_text("", encoding="utf-8")
    installed_main.parent.mkdir(parents=True)
    installed_main.write_text("", encoding="utf-8")
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=install_root,
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert paths.sugar_substitute_python == installed_python
    assert paths.sugar_substitute_main == installed_main
    assert startup_harness.build_app_managed_command(paths) == (
        str(installed_python),
        str(installed_main),
        f"--install-root={install_root}",
    )


def test_harness_paths_resolve_default_custom_node_roots(tmp_path: Path) -> None:
    """Default custom-node roots should derive from the selected Comfy root."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert (
        paths.substitute_backend_root
        == (tmp_path / "ComfyUI" / "custom_nodes" / "substitute-backend").resolve()
    )
    assert (
        paths.sugarcubes_root
        == (tmp_path / "ComfyUI" / "custom_nodes" / "sugarcubes").resolve()
    )


def test_build_direct_comfy_command_uses_workspace_python(tmp_path: Path) -> None:
    """Direct Comfy command should target the selected workspace and endpoint."""

    comfy_root = tmp_path / "ComfyUI"
    python_path = comfy_root / "venv" / "Scripts" / "python.exe"
    python_path.parent.mkdir(parents=True)
    python_path.write_text("", encoding="utf-8")
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert startup_harness.build_direct_comfy_command(
        paths=paths,
        host="127.0.0.1",
        port=8199,
    ) == (
        str(python_path.resolve()),
        str((comfy_root / "main.py").resolve()),
        "--listen",
        "127.0.0.1",
        "--port",
        "8199",
    )


def test_build_direct_comfy_route_probes_traces_substitute_dependency_route() -> None:
    """Substitute dependency probes should carry a stable backend trace header."""

    probes = startup_harness.build_direct_comfy_route_probes(
        host="127.0.0.1",
        port=8199,
    )
    substitute_probe = next(
        probe for probe in probes if probe.name == "substitute_dependency_readiness"
    )
    repeat_probe = next(
        probe
        for probe in probes
        if probe.name == "substitute_dependency_readiness_repeat"
    )

    assert (
        substitute_probe.headers[startup_harness.SUBSTITUTE_CUBE_TRACE_HEADER]
        == "startup-harness-substitute-deps"
    )
    assert substitute_probe.trace_id == "startup-harness-substitute-deps"
    assert (
        repeat_probe.headers[startup_harness.SUBSTITUTE_CUBE_TRACE_HEADER]
        == "startup-harness-substitute-deps-repeat"
    )
    assert repeat_probe.trace_id == "startup-harness-substitute-deps-repeat"


def test_build_direct_comfy_route_probes_can_probe_sugarcubes_dependencies_first() -> (
    None
):
    """Route order should make first-readiness attribution explicit."""

    probes = startup_harness.build_direct_comfy_route_probes(
        host="127.0.0.1",
        port=8199,
        dependency_route_order="sugarcubes-first",
    )

    assert [probe.name for probe in probes] == [
        "system_stats",
        "substitute_capabilities",
        "sugarcubes_dependency_readiness",
        "sugarcubes_dependency_readiness_repeat",
        "substitute_dependency_readiness",
        "substitute_dependency_readiness_repeat",
    ]


def test_build_sugarcubes_maintenance_command_uses_preflight(
    tmp_path: Path,
) -> None:
    """Maintenance command should run the read-only dependency preflight by default."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    command = startup_harness.build_sugarcubes_maintenance_command(paths)

    assert command[1:] == (
        "-m",
        "sugarcubes.maintenance",
        "cube-deps",
        "preflight",
        "--workspace",
        str((tmp_path / "ComfyUI").resolve()),
    )

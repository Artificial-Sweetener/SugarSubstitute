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

"""Validate native Crashpad build and staging contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.build_crashpad_runtime import (
    CrashpadRuntimeTarget,
    _platform_target,
    _stage_runtime,
    _write_gn_arguments,
)


@pytest.mark.parametrize(
    ("platform_name", "machine", "expected"),
    (
        (
            "win32",
            "AMD64",
            CrashpadRuntimeTarget(
                "windows-x64",
                "x64",
                "crashpad_handler.exe",
                "sugarsubstitute_crashpad_client.dll",
            ),
        ),
        (
            "darwin",
            "arm64",
            CrashpadRuntimeTarget(
                "macos-arm64",
                "arm64",
                "crashpad_handler",
                "sugarsubstitute_crashpad_client.dylib",
            ),
        ),
        (
            "linux",
            "x86_64",
            CrashpadRuntimeTarget(
                "linux-x64",
                "x64",
                "crashpad_handler",
                "sugarsubstitute_crashpad_client.so",
            ),
        ),
    ),
)
def test_platform_target_matches_every_release_host(
    platform_name: str,
    machine: str,
    expected: CrashpadRuntimeTarget,
) -> None:
    """Map every published host to its exact GN and packaging contract."""

    assert _platform_target(platform_name=platform_name, machine=machine) == expected


@pytest.mark.parametrize(
    ("platform_name", "machine"),
    (("win32", "arm64"), ("darwin", "x86_64"), ("linux", "aarch64")),
)
def test_platform_target_rejects_unpublished_architectures(
    platform_name: str,
    machine: str,
) -> None:
    """Fail before compiling or staging an unsupported native runtime."""

    with pytest.raises(RuntimeError, match="Unsupported Crashpad release platform"):
        _platform_target(platform_name=platform_name, machine=machine)


def test_stage_runtime_uses_the_target_contract(tmp_path: Path) -> None:
    """Stage the handler and bridge under the matching release directory."""

    target = _platform_target(platform_name="darwin", machine="arm64")
    output_directory = tmp_path / "native-output"
    output_directory.mkdir()
    (output_directory / target.handler_name).write_bytes(b"handler")
    (output_directory / target.client_name).write_bytes(b"client")

    handler, client = _stage_runtime(
        output_directory=output_directory,
        output_root=tmp_path / "packaging",
        target=target,
    )

    assert handler.read_bytes() == b"handler"
    assert client.read_bytes() == b"client"
    assert handler.parent.name == "macos-arm64"


def test_gn_arguments_use_the_validated_target_cpu(tmp_path: Path) -> None:
    """Keep GN architecture selection coupled to the official target."""

    output_directory = tmp_path / "out"

    _write_gn_arguments(output_directory, target_cpu="arm64")

    assert (output_directory / "args.gn").read_text(encoding="utf-8") == (
        'is_debug = false\ntarget_cpu = "arm64"\n'
    )

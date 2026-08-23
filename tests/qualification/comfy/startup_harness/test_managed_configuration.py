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

"""Test managed Comfy configuration and route setup cleanup."""

from __future__ import annotations

from __future__ import annotations
from pathlib import Path
import pytest
from tools import startup_harness


def test_run_harness_passes_defer_input_sam_to_app_managed_cycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness-level diagnostic flags should reach app-managed cycles."""

    received: list[bool] = []
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    def fake_app_managed_cycle(**kwargs: object) -> startup_harness.CommandRunResult:
        """Record app-managed harness arguments and return a minimal result."""

        received.append(bool(kwargs["defer_input_sam"]))
        return startup_harness.CommandRunResult(
            name="app-managed",
            command=("python", "main.py"),
            cwd=tmp_path,
            exit_code=1,
            termination_kind="killed_after_ready",
            timed_out=False,
            ready=True,
            elapsed_ms=1.0,
            output_path=tmp_path / "app-managed.log",
            route_measurements=(),
            parsed_import_times=(),
        )

    monkeypatch.setattr(startup_harness, "_validate_paths", lambda _paths: None)
    monkeypatch.setattr(
        startup_harness,
        "run_app_managed_cycle",
        fake_app_managed_cycle,
    )

    startup_harness.run_harness(
        paths=paths,
        cycles=1,
        modes=("app-managed",),
        host="127.0.0.1",
        port=8188,
        ready_timeout_seconds=1.0,
        settle_seconds=0.0,
        artifact_root=tmp_path / "artifacts",
        defer_input_sam=True,
        log=lambda _message: None,
    )

    assert received == [True]


def test_temporary_manager_config_restores_original_file(tmp_path: Path) -> None:
    """Temporary Manager config experiments should restore exact file contents."""

    comfy_root = tmp_path / "ComfyUI"
    config_path = comfy_root / "user" / "__manager" / "config.ini"
    original_text = (
        "[default]\nnetwork_mode = public\ndb_mode = remote\nfile_logging = False\n"
    )
    config_path.parent.mkdir(parents=True)
    config_path.write_text(original_text, encoding="utf-8")
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    with startup_harness.temporarily_override_manager_config(
        paths=paths,
        overrides={"network_mode": "offline", "db_mode": "cache"},
        log=lambda _message: None,
    ) as result:
        temporary_text = config_path.read_text(encoding="utf-8")
        assert "network_mode = offline" in temporary_text
        assert "db_mode = cache" in temporary_text
        assert result is not None
        assert result.original_values == {
            "network_mode": "public",
            "db_mode": "remote",
        }
        assert result.restored_values == {
            "network_mode": None,
            "db_mode": None,
        }

    assert config_path.read_text(encoding="utf-8") == original_text
    assert result.restored_values == {
        "network_mode": "public",
        "db_mode": "remote",
    }


def test_run_harness_summarizes_temporary_manager_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Harness summaries should record reversible Manager config experiments."""

    comfy_root = tmp_path / "ComfyUI"
    config_path = comfy_root / "user" / "__manager" / "config.ini"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "[default]\nnetwork_mode = public\ndb_mode = remote\n",
        encoding="utf-8",
    )
    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=comfy_root,
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    def fake_app_managed_cycle(**_kwargs: object) -> startup_harness.CommandRunResult:
        """Return one minimal harness result."""

        return startup_harness.CommandRunResult(
            name="app-managed",
            command=("python", "main.py"),
            cwd=tmp_path,
            exit_code=1,
            termination_kind="killed_after_ready",
            timed_out=False,
            ready=True,
            elapsed_ms=1.0,
            output_path=tmp_path / "app-managed.log",
            route_measurements=(),
            parsed_import_times=(),
        )

    monkeypatch.setattr(startup_harness, "_validate_paths", lambda _paths: None)
    monkeypatch.setattr(
        startup_harness,
        "run_app_managed_cycle",
        fake_app_managed_cycle,
    )

    summary = startup_harness.run_harness(
        paths=paths,
        cycles=1,
        modes=("app-managed",),
        host="127.0.0.1",
        port=8188,
        ready_timeout_seconds=1.0,
        settle_seconds=0.0,
        artifact_root=tmp_path / "artifacts",
        temporary_manager_config={"network_mode": "offline", "db_mode": "cache"},
        log=lambda _message: None,
    )

    payload = summary.to_payload()
    assert payload["temporaryManagerConfig"] == {
        "configPath": str(config_path),
        "originalValues": {"network_mode": "public", "db_mode": "remote"},
        "temporaryValues": {"network_mode": "offline", "db_mode": "cache"},
        "restoredValues": {"network_mode": "public", "db_mode": "remote"},
    }
    assert "network_mode = public" in config_path.read_text(encoding="utf-8")


def test_app_startup_trace_path_uses_install_root_appdata(tmp_path: Path) -> None:
    """App-managed trace capture should read the selected install-root trace."""

    paths = startup_harness.HarnessPaths.from_roots(
        sugar_substitute_root=tmp_path / "SugarSubstitute",
        comfy_root=tmp_path / "ComfyUI",
        substitute_backend_root=None,
        sugarcubes_root=None,
    )

    assert startup_harness.app_startup_trace_path(paths) == (
        (tmp_path / "SugarSubstitute")
        .resolve()
        .joinpath("appdata", "diagnostics", "logs", "startup-trace.jsonl")
    )

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

"""Tests for cube icon cache bootstrap composition helpers."""

from __future__ import annotations

from pathlib import Path

from substitute.app.bootstrap.composition import (
    _cube_cache_target_key,
    _cube_icon_target_key,
    _invalidate_cube_icon_cache,
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


class _Factory:
    """Record icon factory invalidation."""

    def __init__(self) -> None:
        """Initialize invalidation call tracking."""

        self.clear_calls = 0

    def clear_asset_cache(self) -> None:
        """Record process-local cache clearing."""

        self.clear_calls += 1


class _Cache:
    """Record durable cache target invalidation."""

    def __init__(self) -> None:
        """Initialize target deletion call tracking."""

        self.deleted_targets: list[str] = []

    def delete_for_target(self, target_key: str) -> int:
        """Record target-scoped durable row deletion."""

        self.deleted_targets.append(target_key)
        return 0


def test_cube_icon_target_key_is_stable_and_hides_workspace_path(
    tmp_path: Path,
) -> None:
    """Target keys should be stable hashes instead of raw workspace paths."""

    context = _context(tmp_path, port=8188)

    key = _cube_icon_target_key(context)
    repeated = _cube_icon_target_key(context)
    different = _cube_icon_target_key(_context(tmp_path, port=8189))

    assert key == repeated
    assert key != different
    assert str(tmp_path) not in key
    assert _cube_cache_target_key(context) == key


def test_invalidate_cube_icon_cache_clears_memory_and_target_rows() -> None:
    """Cache invalidation should clear memory and only the active target rows."""

    factory = _Factory()
    cache = _Cache()

    _invalidate_cube_icon_cache(
        cube_icon_factory=factory,
        cube_icon_cache=cache,
        target_key="target",
    )

    assert factory.clear_calls == 1
    assert cache.deleted_targets == ["target"]


def _context(tmp_path: Path, *, port: int) -> InstallationContext:
    """Return one installation context for cache composition tests."""

    installation = InstallationConfiguration.create_default(tmp_path)
    return InstallationContext(
        installation=installation,
        runtime=RuntimeConfiguration(
            runtime_root=installation.runtime_dir,
            python_executable=None,
            bootstrap_status=RuntimeBootstrapStatus.READY,
        ),
        comfy_target=ComfyTargetConfiguration(
            mode=ComfyTargetMode.MANAGED_LOCAL,
            endpoint=ComfyEndpoint(host="127.0.0.1", port=port),
            workspace_path=tmp_path / "comfy",
            install_owned=True,
            launch_owned=True,
        ),
    )

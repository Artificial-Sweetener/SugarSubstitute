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

"""Own managed ComfyUI model-root persistence and startup redirection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import textwrap

from substitute.shared.logging.logger import get_logger, log_warning

_LOGGER = get_logger("infrastructure.comfy.managed_model_root")
_CONFIG_DIRECTORY = ".substitute"
_MODEL_ROOT_CONFIG_FILE = "managed_model_root.json"
_EXTRA_MODEL_PATHS_FILE = "extra_model_paths.yaml"
_OWNED_EXTRA_PATHS_SECTION = "substitute_shared_models"
_HOOK_DIRECTORY = "SubstituteManagedModelRoot"
_HOOK_FILE = "prestartup_script.py"
_HOOK_INIT_FILE = "__init__.py"
MANAGED_MODEL_ROOT_ENV = "SUGARSUB_MANAGED_MODEL_ROOT"


class ManagedModelRootSource(str, Enum):
    """Identify where the effective managed model root came from."""

    DEFAULT = "default"
    SUBSTITUTE_MODEL_ROOT = "substitute_model_root"
    LEGACY_EXTRA_PATHS = "legacy_extra_paths"
    MODELS_SYMLINK = "models_symlink"


@dataclass(frozen=True)
class ManagedModelRootConfig:
    """Capture the effective managed ComfyUI model-root state."""

    workspace: Path
    default_model_root: Path
    effective_model_root: Path
    override_model_root: Path | None
    source: ManagedModelRootSource


class ManagedModelRootStore:
    """Read and write Substitute's owned ComfyUI model-root override."""

    def load(self, workspace: Path) -> ManagedModelRootConfig:
        """Return the effective model root for one managed ComfyUI workspace."""

        resolved_workspace = workspace.resolve()
        default_model_root = resolved_workspace / "models"
        override = self._load_owned_model_root(resolved_workspace)
        if override is not None:
            return ManagedModelRootConfig(
                workspace=resolved_workspace,
                default_model_root=default_model_root,
                effective_model_root=override,
                override_model_root=override,
                source=ManagedModelRootSource.SUBSTITUTE_MODEL_ROOT,
            )
        legacy_override = self._load_legacy_extra_paths_override(resolved_workspace)
        if legacy_override is not None:
            return ManagedModelRootConfig(
                workspace=resolved_workspace,
                default_model_root=default_model_root,
                effective_model_root=legacy_override,
                override_model_root=legacy_override,
                source=ManagedModelRootSource.LEGACY_EXTRA_PATHS,
            )
        if default_model_root.is_symlink():
            symlink_target = default_model_root.resolve()
            return ManagedModelRootConfig(
                workspace=resolved_workspace,
                default_model_root=default_model_root,
                effective_model_root=symlink_target,
                override_model_root=None,
                source=ManagedModelRootSource.MODELS_SYMLINK,
            )
        return ManagedModelRootConfig(
            workspace=resolved_workspace,
            default_model_root=default_model_root,
            effective_model_root=default_model_root,
            override_model_root=None,
            source=ManagedModelRootSource.DEFAULT,
        )

    def save(
        self,
        workspace: Path,
        model_root: Path | None,
    ) -> ManagedModelRootConfig:
        """Persist the requested model root and remove the legacy YAML shape."""

        resolved_workspace = workspace.resolve()
        default_model_root = resolved_workspace / "models"
        if model_root is None or _same_path(model_root, default_model_root):
            self._remove_owned_model_root(resolved_workspace)
            self._remove_legacy_extra_paths_section(resolved_workspace)
            return self.load(resolved_workspace)
        resolved_model_root = _resolve_model_root(model_root)
        if resolved_model_root.exists() and not resolved_model_root.is_dir():
            raise ValueError("Managed model root must be a folder.")
        resolved_model_root.mkdir(parents=True, exist_ok=True)
        config_path = _model_root_config_path(resolved_workspace)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "model_root": str(resolved_model_root),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self._remove_legacy_extra_paths_section(resolved_workspace)
        return self.load(resolved_workspace)

    def _load_owned_model_root(self, workspace: Path) -> Path | None:
        """Load Substitute's owned model-root JSON file."""

        config_path = _model_root_config_path(workspace)
        if not config_path.exists():
            return None
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            log_warning(
                _LOGGER,
                "Failed to read managed ComfyUI model-root config.",
                path=config_path,
                error=repr(error),
            )
            return None
        raw_model_root = payload.get("model_root")
        if not isinstance(raw_model_root, str) or not raw_model_root.strip():
            log_warning(
                _LOGGER,
                "Managed ComfyUI model-root config did not contain a model root.",
                path=config_path,
            )
            return None
        return _resolve_model_root(Path(raw_model_root))

    def _load_legacy_extra_paths_override(self, workspace: Path) -> Path | None:
        """Load the old owned YAML base path for one migration cycle."""

        config_path = _extra_model_paths_path(workspace)
        if not config_path.exists():
            return None
        try:
            text = config_path.read_text(encoding="utf-8")
        except OSError as error:
            log_warning(
                _LOGGER,
                "Failed to read legacy managed ComfyUI model path config.",
                path=config_path,
                error=repr(error),
            )
            return None
        raw_base_path = _read_owned_base_path(text)
        if raw_base_path is None:
            return None
        expanded = Path(os.path.expanduser(os.path.expandvars(raw_base_path)))
        if not expanded.is_absolute():
            expanded = config_path.parent / expanded
        return expanded.resolve()

    def _remove_owned_model_root(self, workspace: Path) -> None:
        """Remove Substitute's owned model-root JSON file when present."""

        config_path = _model_root_config_path(workspace)
        if config_path.exists():
            config_path.unlink()
        config_dir = config_path.parent
        if config_dir.exists() and not any(config_dir.iterdir()):
            config_dir.rmdir()

    def _remove_legacy_extra_paths_section(self, workspace: Path) -> None:
        """Remove only Substitute's old top-level YAML section."""

        config_path = _extra_model_paths_path(workspace)
        if not config_path.exists():
            return
        existing_text = config_path.read_text(encoding="utf-8")
        updated_text = _remove_owned_section(existing_text)
        if updated_text.strip():
            config_path.write_text(updated_text, encoding="utf-8")
            return
        config_path.unlink()


def ensure_managed_model_root_startup_hook(workspace: Path) -> Path:
    """Install the prestartup hook that redirects ComfyUI's model root."""

    hook_directory = workspace / "custom_nodes" / _HOOK_DIRECTORY
    hook_path = hook_directory / _HOOK_FILE
    hook_directory.mkdir(parents=True, exist_ok=True)
    (hook_directory / _HOOK_INIT_FILE).write_text(_hook_init_script(), encoding="utf-8")
    hook_path.write_text(_hook_script(), encoding="utf-8")
    return hook_path


def _model_root_config_path(workspace: Path) -> Path:
    """Return Substitute's owned model-root config path."""

    return workspace / _CONFIG_DIRECTORY / _MODEL_ROOT_CONFIG_FILE


def _extra_model_paths_path(workspace: Path) -> Path:
    """Return ComfyUI's extra model paths config path."""

    return workspace / _EXTRA_MODEL_PATHS_FILE


def _resolve_model_root(model_root: Path) -> Path:
    """Return an absolute normalized model root path."""

    expanded = Path(os.path.expanduser(os.path.expandvars(str(model_root))))
    if not expanded.is_absolute():
        raise ValueError("Managed model root must be an absolute path.")
    return expanded.resolve()


def _same_path(left: Path, right: Path) -> bool:
    """Return whether two paths point to the same normalized location."""

    return left.resolve() == right.resolve()


def _read_owned_base_path(text: str) -> str | None:
    """Return the legacy owned section's raw base path, if one is present."""

    lines = text.splitlines()
    section_start = _find_owned_section_start(lines)
    if section_start is None:
        return None
    for line in lines[section_start + 1 :]:
        if _is_top_level_section(line):
            return None
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not stripped.startswith("base_path:"):
            continue
        value = stripped.removeprefix("base_path:").strip()
        return _strip_yaml_scalar_quotes(value) if value else None
    return None


def _strip_yaml_scalar_quotes(value: str) -> str:
    """Strip simple single or double quotes from a YAML scalar value."""

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _remove_owned_section(text: str) -> str:
    """Return text with only the legacy owned top-level section removed."""

    lines = text.splitlines()
    section_start = _find_owned_section_start(lines)
    if section_start is None:
        return text if text.endswith("\n") or not text else f"{text}\n"
    section_end = len(lines)
    for index in range(section_start + 1, len(lines)):
        if _is_top_level_section(lines[index]):
            section_end = index
            break
    kept_lines = [*lines[:section_start], *lines[section_end:]]
    cleaned = "\n".join(kept_lines).strip("\n")
    return f"{cleaned}\n" if cleaned else ""


def _find_owned_section_start(lines: list[str]) -> int | None:
    """Return the first line index for Substitute's legacy YAML section."""

    for index, line in enumerate(lines):
        if line == f"{_OWNED_EXTRA_PATHS_SECTION}:":
            return index
    return None


def _is_top_level_section(line: str) -> bool:
    """Return whether a line begins a top-level YAML mapping section."""

    stripped = line.strip()
    return (
        bool(stripped)
        and not line[0].isspace()
        and not stripped.startswith("#")
        and stripped.endswith(":")
    )


def _hook_script() -> str:
    """Return the standalone ComfyUI prestartup hook source."""

    return textwrap.dedent(
        f'''\
        """Redirect managed ComfyUI's model root before custom nodes import."""

        from __future__ import annotations

        import logging
        import os
        from pathlib import Path

        import folder_paths

        _MODEL_ROOT_ENV = "{MANAGED_MODEL_ROOT_ENV}"


        def _is_relative_to(path: Path, parent: Path) -> bool:
            """Return whether path is contained by parent after normalization."""

            try:
                path.relative_to(parent)
            except ValueError:
                return False
            return True


        def _redirect_registered_model_paths(old_root: Path, new_root: Path) -> None:
            """Rewrite already-initialized Comfy model paths to the new model root."""

            registry = getattr(folder_paths, "folder_names_and_paths", {{}})
            for folder_name, values in list(registry.items()):
                paths, extensions = values
                rewritten_paths = []
                changed = False
                for raw_path in paths:
                    path = Path(str(raw_path)).resolve()
                    if _is_relative_to(path, old_root):
                        rewritten_paths.append(str(new_root / path.relative_to(old_root)))
                        changed = True
                    else:
                        rewritten_paths.append(str(raw_path))
                if changed:
                    registry[folder_name] = (rewritten_paths, extensions)


        def _clear_folder_path_caches() -> None:
            """Clear Comfy filename caches after model paths are rewritten."""

            cache = getattr(folder_paths, "filename_list_cache", None)
            if hasattr(cache, "clear"):
                cache.clear()
            cache_helper = getattr(folder_paths, "cache_helper", None)
            if hasattr(cache_helper, "clear"):
                cache_helper.clear()


        def _apply_managed_model_root() -> None:
            """Apply Substitute's managed model root when this process provides one."""

            raw_model_root = os.environ.get(_MODEL_ROOT_ENV, "").strip()
            if not raw_model_root:
                return
            new_root = Path(raw_model_root).expanduser().resolve()
            if not new_root.is_absolute():
                logging.error("Substitute managed model root is not absolute: %s", raw_model_root)
                return
            new_root.mkdir(parents=True, exist_ok=True)
            old_root = Path(str(folder_paths.models_dir)).resolve()
            if old_root == new_root:
                return
            _redirect_registered_model_paths(old_root, new_root)
            folder_paths.models_dir = str(new_root)
            _clear_folder_path_caches()
            logging.info("Substitute managed ComfyUI model root: %s", new_root)


        _apply_managed_model_root()
        '''
    )


def _hook_init_script() -> str:
    """Return the no-op custom-node module for the prestartup hook directory."""

    return textwrap.dedent(
        '''\
        """Make Substitute's prestartup hook directory import as a no-op custom node."""

        from __future__ import annotations

        NODE_CLASS_MAPPINGS: dict[str, type[object]] = {}
        NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}
        '''
    )


__all__ = [
    "MANAGED_MODEL_ROOT_ENV",
    "ManagedModelRootConfig",
    "ManagedModelRootSource",
    "ManagedModelRootStore",
    "ensure_managed_model_root_startup_hook",
]

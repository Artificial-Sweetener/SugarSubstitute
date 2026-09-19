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

"""Detect shareable model roots in an explicitly selected WebUI folder."""

from __future__ import annotations

from pathlib import Path

from sugarsubstitute_shared.model_discovery import ModelArtifactKind

from substitute.domain.onboarding.webui_model_library import WebUiModelLibrary


class WebUiModelLibraryDetectionError(ValueError):
    """Report that a selected directory is not a supported models folder."""


class WebUiModelLibraryDetector:
    """Map known top-level WebUI directories without inspecting extensions."""

    _CHECKPOINT_NAMES = frozenset({"checkpoints", "stable-diffusion"})
    _DIFFUSION_NAMES = frozenset({"diffusion_models", "unet"})
    _ULTRALYTICS_NAMES = frozenset({"ultralytics", "yolo"})
    _UPSCALER_NAMES = frozenset(
        {
            "upscale_models",
            "esrgan",
            "realesrgan",
            "bsrgan",
            "swinir",
            "scunet",
            "dat",
            "spandrel",
        }
    )

    def detect(self, selected_root: Path) -> WebUiModelLibrary:
        """Resolve supported direct children from one user-selected directory."""

        models_root = self._models_root(selected_root)
        children = self._direct_directories(models_root)
        library = WebUiModelLibrary(
            models_root=models_root,
            checkpoints=self._matching_paths(children, self._CHECKPOINT_NAMES),
            diffusion_models=self._matching_paths(children, self._DIFFUSION_NAMES),
            ultralytics=self._matching_paths(children, self._ULTRALYTICS_NAMES),
            upscale_models=self._matching_paths(children, self._UPSCALER_NAMES),
        )
        if not library.paths_by_kind():
            raise WebUiModelLibraryDetectionError(
                "The selected folder does not contain supported WebUI model directories."
            )
        return library

    def model_family_scan_roots(self, selected_root: Path) -> tuple[Path, ...]:
        """Return only roots capable of containing generation model families."""

        library = self.detect(selected_root)
        return library.checkpoints + library.diffusion_models

    def install_destination(
        self,
        selected_root: Path,
        artifact_kind: ModelArtifactKind,
    ) -> Path:
        """Keep new downloads in the selected library's existing category folder."""

        root = selected_root.expanduser().resolve(strict=False)
        try:
            library = self.detect(root)
        except WebUiModelLibraryDetectionError:
            return root / artifact_kind.value
        candidates = dict(library.paths_by_kind()).get(artifact_kind.value, ())
        return (
            candidates[0] if candidates else library.models_root / artifact_kind.value
        )

    def _models_root(self, selected_root: Path) -> Path:
        """Accept either a models folder or a WebUI root containing one."""

        root = selected_root.expanduser().resolve(strict=False)
        if not root.is_dir():
            raise WebUiModelLibraryDetectionError(
                "The selected WebUI models folder is not accessible."
            )
        direct = self._direct_directories(root)
        if self._contains_supported_name(direct):
            return root
        nested_models = direct.get("models")
        return nested_models if nested_models is not None else root

    @staticmethod
    def _direct_directories(root: Path) -> dict[str, Path]:
        """Return case-insensitive direct directories without descending into them."""

        try:
            entries = tuple(root.iterdir())
        except OSError as error:
            raise WebUiModelLibraryDetectionError(
                "The selected WebUI models folder could not be inspected."
            ) from error
        return {
            entry.name.casefold(): entry.resolve(strict=False)
            for entry in entries
            if entry.is_dir()
        }

    def _contains_supported_name(self, children: dict[str, Path]) -> bool:
        """Return whether direct children contain any supported model category."""

        supported = (
            self._CHECKPOINT_NAMES
            | self._DIFFUSION_NAMES
            | self._ULTRALYTICS_NAMES
            | self._UPSCALER_NAMES
        )
        return not supported.isdisjoint(children)

    @staticmethod
    def _matching_paths(
        children: dict[str, Path],
        names: frozenset[str],
    ) -> tuple[Path, ...]:
        """Return matching paths ordered independently of filesystem enumeration."""

        return tuple(children[name] for name in sorted(names) if name in children)


__all__ = ["WebUiModelLibraryDetectionError", "WebUiModelLibraryDetector"]

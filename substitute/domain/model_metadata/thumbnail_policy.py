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

"""Select thumbnails from normalized CivitAI image metadata."""

from __future__ import annotations

from substitute.domain.model_metadata.models import (
    CivitaiImage,
    CivitaiModelVersion,
    ThumbnailSelection,
)
from substitute.domain.civitai import CivitaiThumbnailSafetyPolicy
from substitute.domain.model_metadata.statuses import ThumbnailSelectionStatus

_SFW_LEVELS = {"", "0", "1", "none", "false", "safe", "sfw"}
_SOFT_LEVELS = {"2", "soft", "racy"}


class CivitaiThumbnailPolicy:
    """Choose the first provider image allowed by the configured safety policy."""

    def __init__(
        self,
        safety_policy: CivitaiThumbnailSafetyPolicy = (
            CivitaiThumbnailSafetyPolicy.SFW_ONLY
        ),
    ) -> None:
        """Store the user-selected thumbnail safety policy."""

        self._safety_policy = safety_policy

    @property
    def selection_policy(self) -> str:
        """Return the stable cache key for this selection policy."""

        return f"civitai-thumbnail:{self._safety_policy.value}:v1"

    def select(self, version: CivitaiModelVersion) -> ThumbnailSelection:
        """Return the first allowed image candidate or a no-thumbnail decision."""

        if self._safety_policy is CivitaiThumbnailSafetyPolicy.DISABLED:
            return ThumbnailSelection(
                status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
                image=None,
                policy=self.selection_policy,
            )
        for image in version.images:
            if self._image_is_allowed(image):
                return ThumbnailSelection(
                    status=ThumbnailSelectionStatus.SELECTED,
                    image=image,
                    policy=self.selection_policy,
                )
        return ThumbnailSelection(
            status=ThumbnailSelectionStatus.NO_SFW_IMAGE,
            image=None,
            policy=self.selection_policy,
        )

    def _image_is_allowed(self, image: CivitaiImage) -> bool:
        """Return whether one CivitAI image is allowed by active policy."""

        if not image.url.strip():
            return False
        if image.image_type is not None and image.image_type.lower() != "image":
            return False
        if self._safety_policy is CivitaiThumbnailSafetyPolicy.ALLOW_ALL:
            return True
        if self._is_sfw_image(image):
            return True
        if self._safety_policy is CivitaiThumbnailSafetyPolicy.ALLOW_SOFT:
            return self._is_soft_image(image)
        return False

    @classmethod
    def _is_sfw_image(cls, image: CivitaiImage) -> bool:
        """Return whether one CivitAI image is safe for default thumbnail use."""

        return image.nsfw is not True and cls._is_sfw_level(image.nsfw_level)

    @staticmethod
    def _is_sfw_level(nsfw_level: str | int | None) -> bool:
        """Return whether a CivitAI NSFW level means safe for default display."""

        if nsfw_level is None:
            return True
        if isinstance(nsfw_level, int):
            return nsfw_level in {0, 1}
        return nsfw_level.strip().lower() in _SFW_LEVELS

    @staticmethod
    def _is_soft_image(image: CivitaiImage) -> bool:
        """Return whether one CivitAI image is soft/racy but not explicit."""

        if image.nsfw is True:
            return False
        nsfw_level = image.nsfw_level
        if isinstance(nsfw_level, int):
            return nsfw_level == 2
        if nsfw_level is None:
            return False
        return nsfw_level.strip().lower() in _SOFT_LEVELS


class FirstSfwThumbnailPolicy(CivitaiThumbnailPolicy):
    """Preserve the previous default thumbnail policy API."""

    selection_policy = "first-sfw-version-image"

    def __init__(self) -> None:
        """Initialize the default SFW-only thumbnail policy."""

        super().__init__(CivitaiThumbnailSafetyPolicy.SFW_ONLY)


__all__ = ["CivitaiThumbnailPolicy", "FirstSfwThumbnailPolicy"]

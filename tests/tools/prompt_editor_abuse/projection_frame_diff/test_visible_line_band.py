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

"""Verify viewport clipping used by prompt backing-store comparisons."""

import numpy as np

from tools.prompt_editor_abuse.projection_frame_diff import (
    has_comparable_text_pixels,
    local_contrast_mask,
    visible_projection_line_band,
)


def test_visible_projection_line_band_keeps_a_fully_visible_line() -> None:
    """Keep the complete integer band for a line inside the viewport."""

    assert visible_projection_line_band(
        viewport_top=3,
        viewport_bottom=277,
        line_top=19.25,
        line_height=16.0,
    ) == (19, 36)


def test_visible_projection_line_band_rejects_edge_antialiasing_sliver() -> None:
    """Ignore a line whose tiny clipped sliver cannot prove missing glyphs."""

    assert (
        visible_projection_line_band(
            viewport_top=3,
            viewport_bottom=277,
            line_top=-11.0,
            line_height=16.0,
        )
        is None
    )


def test_visible_projection_line_band_accepts_half_visible_line() -> None:
    """Retain enough clipped line pixels to compare glyph presence reliably."""

    assert visible_projection_line_band(
        viewport_top=3,
        viewport_bottom=277,
        line_top=-5.0,
        line_height=16.0,
    ) == (3, 11)


def test_visible_projection_line_band_clamps_to_viewport_bottom() -> None:
    """Keep comparisons out of scrollbars and other editor chrome."""

    assert visible_projection_line_band(
        viewport_top=3,
        viewport_bottom=277,
        line_top=269.0,
        line_height=16.0,
    ) == (269, 277)


def test_comparable_text_pixels_reject_translucent_inline_background() -> None:
    """Do not mistake a translucent chip tail for missing text glyphs."""

    alpha = np.full((16, 96), 157, dtype=np.uint8)

    assert has_comparable_text_pixels(alpha) is False


def test_comparable_text_pixels_accept_opaque_glyph_cores() -> None:
    """Compare a tile once it contains enough opaque glyph evidence."""

    alpha = np.zeros((16, 96), dtype=np.uint8)
    alpha[4:8, 10:12] = 220

    assert has_comparable_text_pixels(alpha) is True


def test_local_contrast_mask_rejects_a_blank_tile() -> None:
    """Keep a uniform backing-store tile from masquerading as text."""

    rgb = np.full((16, 96, 3), 255, dtype=np.uint8)

    assert np.count_nonzero(local_contrast_mask(rgb)) == 0


def test_local_contrast_mask_recognizes_style_independent_glyph_edges() -> None:
    """Recognize text edges even when live and reference colors differ."""

    rgb = np.full((16, 96, 3), 255, dtype=np.uint8)
    rgb[4:12, 20:30] = 0

    contrast = local_contrast_mask(rgb)

    assert np.count_nonzero(contrast) > 0
    assert contrast[4, 20]
    assert not contrast[8, 25]

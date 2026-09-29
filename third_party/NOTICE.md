# Third-Party Notices

This repository vendors selected third-party assets for application runtime use.
Each vendored component is recorded in `third_party/manifest.toml`, and the
corresponding license text is stored in `third_party/licenses/`.

## Microsoft Fluent UI System Icons

Selected SVG icons are vendored from Microsoft Fluent UI System Icons under the
MIT License.

## Microsoft Fluent UI Emoji

The game die, infinity, and locked high contrast SVGs are vendored from
Microsoft Fluent UI Emoji under the MIT License.

## Qt Development Logo

The Qt Development logo mark is vendored from the Qt Development Brand Guide for
factual identification of the PySide6 dependency link in the About page. Use is
governed by the Qt Trademark Usage Guidelines.

Qt is a registered trademark of The Qt Company Ltd. and its subsidiaries.

## CivitAI Badge

The CivitAI badge is adapted from CivitAI's official brand package under the
Apache License 2.0. CivitAI's mark identifies the linked model provider and
does not imply endorsement.

## OpenModelDB Favicon

The OpenModelDB favicon is vendored from the OpenModelDB project under the GNU
General Public License v3.0. The mark identifies linked OpenModelDB model
records and acquisition offers and does not imply endorsement.

## Font Awesome Free Brand Icons

The Windows, Apple, and Linux SVG marks used in installation guidance are
adapted from Font Awesome Free 7.3.0 under the Creative Commons Attribution 4.0
International License. Their fill colors are adjusted for visibility on light
and dark GitHub themes. Font Awesome is a product of Fonticons, Inc.

The brand marks remain trademarks of their respective owners. They identify the
platforms they represent and do not imply endorsement.

## 7-Zip

Native 7-Zip command-line binaries are distributed through the `7zip-bin`
package and bundled for responsive standalone-environment extraction. 7-Zip is
Copyright (C) Igor Pavlov and is distributed under its LGPL, BSD, and unRAR
terms. The `7zip-bin` package wrapper is distributed under the MIT License.

## Crashpad

Crashpad is bundled as SugarSubstitute's native out-of-process crash capture
runtime. Crashpad is Copyright The Crashpad Authors and distributed under the
Apache License 2.0. Its linked mini_chromium, zlib, and getopt components retain
their accompanying BSD, zlib, and public-domain notices.

## mpv

mpv and its libmpv client library are bundled as SugarSubstitute's generated-video
decode and playback runtime. mpv is a fork of mplayer2 and MPlayer and is
distributed under the GNU Lesser General Public License version 2.1 or later in
the selected build. The complete upstream copyright inventory and LGPL text
accompany the application. The Windows x64 runtime is a checksum-pinned
Paxton-PKJ build of mpv `v0.41.0`, built without GPL components, Lua, or
JavaScript. Its preparation script records and verifies the archive, every
dynamically linked runtime file, the build configuration, and the builder
revision. The bundle also contains the dynamically linked FFmpeg, libass,
libplacebo, shaderc, FreeType, HarfBuzz, FriBidi, GLib, Graphite2, Brotli, bzip2,
libiconv, libintl, liblzma, PCRE2, libpng, zlib, and MinGW runtime libraries;
their copyright and license obligations remain with their respective projects.

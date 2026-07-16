//    SugarSubstitute - The desktop native Qt front-end for ComfyUI
//    Copyright (C) 2026  Artificial Sweetener and contributors
//
//    This program is free software: you can redistribute it and/or modify
//    it under the terms of the GNU General Public License as published by
//    the Free Software Foundation, either version 3 of the License, or
//    (at your option) any later version.
//
//    This program is distributed in the hope that it will be useful,
//    but WITHOUT ANY WARRANTY; without even the implied warranty of
//    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//    GNU General Public License for more details.
//
//    You should have received a copy of the GNU General Public License
//    along with this program.  If not, see <https://www.gnu.org/licenses/>.

const COMMIT_ANALYZER_PLUGIN = "@semantic-release/commit-analyzer";

/**
 * Select the release-analysis plugin without loading publishing side effects.
 *
 * @param {{plugins?: unknown}} releaseConfig Semantic-release configuration.
 * @returns {Array<unknown>} Analyzer configuration used to calculate a version.
 */
function selectVersionResolutionPlugins(releaseConfig) {
  if (!Array.isArray(releaseConfig.plugins)) {
    throw new Error("Semantic-release configuration has no plugin list.");
  }
  const analyzer = releaseConfig.plugins.find(
    (plugin) => pluginName(plugin) === COMMIT_ANALYZER_PLUGIN,
  );
  if (analyzer === undefined) {
    throw new Error("Semantic-release configuration has no commit analyzer.");
  }
  return [analyzer];
}

/**
 * Return the package name represented by one semantic-release plugin entry.
 *
 * @param {unknown} plugin Semantic-release plugin entry.
 * @returns {string | undefined} Plugin package name when recognized.
 */
function pluginName(plugin) {
  if (typeof plugin === "string") {
    return plugin;
  }
  if (Array.isArray(plugin) && typeof plugin[0] === "string") {
    return plugin[0];
  }
  return undefined;
}

module.exports = { selectVersionResolutionPlugins };

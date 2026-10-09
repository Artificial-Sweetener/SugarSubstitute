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

const CORE_VERSION_PATTERN = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/;

/**
 * Add a legacy-launcher-compatible Canary identifier to the next Stable version.
 *
 * @param {string} nextStableVersion Exact semantic version expected for Stable.
 * @param {string} runNumber Positive GitHub Actions run number.
 * @returns {string} Dotted numeric Canary release version.
 */
function createCanaryVersion(nextStableVersion, runNumber) {
  const normalizedVersion = String(nextStableVersion).trim();
  const normalizedRunNumber = String(runNumber).trim();
  if (!CORE_VERSION_PATTERN.test(normalizedVersion)) {
    throw new Error(`Expected a Stable semantic version: ${nextStableVersion}`);
  }
  if (!/^[1-9]\d*$/.test(normalizedRunNumber)) {
    throw new Error(`Expected a positive Canary run number: ${runNumber}`);
  }
  return `${normalizedVersion}.${normalizedRunNumber}`;
}

/**
 * Return the Stable version implied by a semantic-release change type.
 *
 * @param {string[]} releaseTags Stable tags in vMAJOR.MINOR.PATCH form.
 * @param {"major" | "minor" | "patch"} releaseType Semantic release type.
 * @returns {string} Next Stable version.
 */
function nextStableVersion(releaseTags, releaseType) {
  const versions = releaseTags.map((tag) => {
    const match = /^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.exec(tag);
    if (!match) {
      throw new Error(`Expected a Stable release tag: ${tag}`);
    }
    return [Number(match[1]), Number(match[2]), Number(match[3])];
  });
  if (versions.length === 0) {
    throw new Error("Cannot derive a Canary version without a Stable release tag.");
  }
  versions.sort((left, right) => {
    for (let index = 0; index < left.length; index += 1) {
      if (left[index] !== right[index]) {
        return left[index] - right[index];
      }
    }
    return 0;
  });
  const [major, minor, patch] = versions.at(-1);
  if (releaseType === "major") {
    return `${major + 1}.0.0`;
  }
  if (releaseType === "minor") {
    return `${major}.${minor + 1}.0`;
  }
  if (releaseType === "patch") {
    return `${major}.${minor}.${patch + 1}`;
  }
  throw new Error(`Expected a semantic release type: ${releaseType}`);
}

/**
 * Return the greatest Stable tag by semantic version precedence.
 *
 * @param {string[]} releaseTags Stable tags in vMAJOR.MINOR.PATCH form.
 * @returns {string} Greatest Stable tag.
 */
function latestStableTag(releaseTags) {
  const version = nextStableVersion(releaseTags, "patch")
    .split(".")
    .map(Number);
  version[2] -= 1;
  return `v${version.join(".")}`;
}

module.exports = { createCanaryVersion, latestStableTag, nextStableVersion };

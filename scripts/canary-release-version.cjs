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
 * Add a monotonically increasing Canary identifier to the next Stable version.
 *
 * @param {string} nextStableVersion Exact semantic version expected for Stable.
 * @param {string} runNumber Positive GitHub Actions run number.
 * @returns {string} Canary semantic prerelease version.
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
  return `${normalizedVersion}-canary.${normalizedRunNumber}`;
}

/**
 * Return the patch release following the greatest Stable tag.
 *
 * @param {string[]} releaseTags Stable tags in vMAJOR.MINOR.PATCH form.
 * @returns {string} Next patch version.
 */
function nextPatchVersion(releaseTags) {
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
  return `${major}.${minor}.${patch + 1}`;
}

module.exports = { createCanaryVersion, nextPatchVersion };

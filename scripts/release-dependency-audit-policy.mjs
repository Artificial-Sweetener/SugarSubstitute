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

const dormantNpmAdvisories = new Map([
  ["undici", new Set(["https://github.com/advisories/GHSA-rfgv-xxqx-mfg5"])],
  [
    "brace-expansion",
    new Set([
      "https://github.com/advisories/GHSA-qhr7-859c-m2p7",
      "https://github.com/advisories/GHSA-6j4f-fj2g-mc7p",
    ]),
  ],
]);

/**
 * Scope reviewed advisories to the CLI bundle of the unused npm release plugin.
 * @param {{name: string, nodes?: string[]}} vulnerability
 * @param {{url: string}} finding
 * @returns {boolean}
 */
export function isUnloadedBundledNpmFinding(vulnerability, finding) {
  const nodes = vulnerability.nodes;
  return (
    dormantNpmAdvisories.get(vulnerability.name)?.has(finding.url) === true &&
    Array.isArray(nodes) &&
    nodes.length > 0 &&
    nodes.every(
      (node) => node === `node_modules/npm/node_modules/${vulnerability.name}`,
    )
  );
}

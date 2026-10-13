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

/**
 * Bound the reviewed advisory exceptions to the private release graph.
 * These vulnerable versions remain vulnerable. The exceptions apply only to
 * this private CI release toolchain, never application or newly added tooling.
 * Reviewed 2026-10-08: semantic-release requires braces through micromatch;
 * http-cache-semantics is inside the bundled CLI of its unused npm publisher.
 * Preserve the existing brace-expansion and undici exceptions in that unused
 * CLI bundle. They do not cover the active undici copies used by other tools.
 * The compatible npm bundle still contains these reviewed vulnerable versions.
 * Remove these exceptions when upstream fixes are available; changed versions,
 * paths, release roots, and additional advisories require another review.
 */
const releaseRoots = Object.freeze({
  "@semantic-release/changelog": "6.0.3",
  "@semantic-release/commit-analyzer": "13.0.1",
  "@semantic-release/exec": "7.1.0",
  "@semantic-release/git": "11.0.1",
  "@semantic-release/github": "12.0.9",
  "@semantic-release/release-notes-generator": "14.1.1",
  "semantic-release": "25.0.9",
});

const reviewedNodes = Object.freeze({
  ...Object.fromEntries(Object.entries(releaseRoots).map(([name, version]) =>
    [name, { path: `node_modules/${name}`, version }])),
  "@semantic-release/npm": {
    path: "node_modules/@semantic-release/npm", version: "13.1.5",
  },
  npm: { path: "node_modules/npm", version: "11.21.0" },
  "brace-expansion": {
    path: "node_modules/npm/node_modules/brace-expansion", version: "5.0.9",
  },
  undici: {
    path: "node_modules/npm/node_modules/undici", version: "6.28.0",
    otherInstallations: {
      "node_modules/undici": "6.29.0",
      "node_modules/@semantic-release/github/node_modules/undici": "7.30.0",
    },
  },
  micromatch: { path: "node_modules/micromatch", version: "4.0.8" },
  braces: { path: "node_modules/braces", version: "3.0.3" },
  "http-cache-semantics": {
    path: "node_modules/npm/node_modules/http-cache-semantics", version: "4.2.0",
  },
});

const reviewedAdvisories = Object.freeze({
  braces: ["https://github.com/advisories/GHSA-vfj7-8cjw-p6xm"],
  "http-cache-semantics": ["https://github.com/advisories/GHSA-ch52-4w7c-c8xp"],
  "brace-expansion": [
    "https://github.com/advisories/GHSA-qhr7-859c-m2p7",
    "https://github.com/advisories/GHSA-6j4f-fj2g-mc7p",
  ],
  undici: ["https://github.com/advisories/GHSA-rfgv-xxqx-mfg5"],
});

/** Return whether a value is a JSON object rather than an array or null. */
function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

/** Require complete lock evidence before applying any release exception. */
export function validateReleaseLock(lock) {
  if (!isObject(lock) || lock.lockfileVersion !== 3 ||
      !isObject(lock.packages) || !isObject(lock.packages[""]) ||
      Object.values(lock.packages).some((entry) => !isObject(entry))) {
    throw new Error("npm audit requires a valid version 3 package lock.");
  }
}

/** Match the fixed root inventory; the runner verifies manifest private:true. */
function isReviewedRoot(lock) {
  const root = lock.packages[""];
  const dependencies = root.devDependencies;
  return lock.name === "sugarsubstitute-release" &&
    root.name === "sugarsubstitute-release" && root.private !== false &&
    isObject(dependencies) &&
    Object.keys(dependencies).length === Object.keys(releaseRoots).length &&
    Object.entries(releaseRoots).every(([name, version]) =>
      Object.hasOwn(dependencies, name) && dependencies[name] === version) &&
    [root.dependencies, root.optionalDependencies, root.peerDependencies].every(
      (entries) => entries === undefined ||
        (isObject(entries) && Object.keys(entries).length === 0),
    ) &&
    Object.entries(lock.packages).every(([path, entry]) =>
      path === "" || (entry.dev === true && entry.link !== true)) &&
    Object.keys(reviewedNodes).every((name) => isReviewedNode(name, lock));
}

/** Verify every installed copy while keeping the exception on its one path. */
function isReviewedNode(name, lock) {
  if (!Object.hasOwn(reviewedNodes, name)) return false;
  const reviewed = reviewedNodes[name];
  const paths = Object.keys(lock.packages).filter((path) =>
    path.slice(path.lastIndexOf("node_modules/") + "node_modules/".length) === name,
  );
  const installations = {
    [reviewed.path]: reviewed.version, ...reviewed.otherInstallations,
  };
  return paths.length === Object.keys(installations).length &&
    paths.every((path) => Object.hasOwn(installations, path) &&
      lock.packages[path].version === installations[path] &&
      lock.packages[path].dev === true && lock.packages[path].link !== true);
}

/** Keep both direct and propagated exceptions within exact reviewed nodes. */
export function isReviewedReleaseFinding(finding, lock) {
  if (!isReviewedRoot(lock) || !isReviewedNode(finding.name, lock)) return false;
  return finding.nodes.length === 1 &&
    finding.nodes[0] === reviewedNodes[finding.name].path;
}

/** Accept only reviewed high-severity advisory IDs at the scoped finding. */
export function isReviewedReleaseAdvisory(finding, advisory) {
  return finding.severity === "high" && advisory.severity === "high" &&
    Object.hasOwn(reviewedAdvisories, finding.name) &&
    advisory.name === finding.name && advisory.dependency === finding.name &&
    reviewedAdvisories[finding.name].includes(advisory.url);
}

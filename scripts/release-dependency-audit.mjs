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
 * Validate an npm audit report and return every high or critical finding.
 * @param {unknown} report Untrusted npm audit JSON.
 * @returns {object[]} Release-blocking dependency records.
 */
export function unresolvedReleaseFindings(report) {
  if (!report || report.auditReportVersion !== 2 || report.error ||
      !report.vulnerabilities || typeof report.vulnerabilities !== "object" ||
      Array.isArray(report.vulnerabilities)) {
    throw new Error("npm audit did not produce a valid dependency report.");
  }
  const findings = Object.values(report.vulnerabilities);
  for (const finding of findings) {
    if (!finding || typeof finding.name !== "string" ||
        !["info", "low", "moderate", "high", "critical"].includes(finding.severity) ||
        !Array.isArray(finding.via) || !Array.isArray(finding.nodes)) {
      throw new Error("npm audit contains a malformed dependency finding.");
    }
  }
  return findings.filter((finding) => ["high", "critical"].includes(finding.severity));
}

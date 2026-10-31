"""Map existing JUnit evidence to the US-16 acceptance plan without running tests."""

import argparse
from collections import Counter
from datetime import datetime
import fnmatch
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", type=Path, action="append", required=True,
                        help="Ordered reports; later reports replace the same test result.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/testing/us16/results.json")
    args = parser.parse_args()
    tests, sources = {}, []
    for path in args.junit:
        raw = path.read_bytes()
        sources.append({"file": path.as_posix(), "sha256": hashlib.sha256(raw).hexdigest()})
        for node in ET.fromstring(raw).iter("testcase"):
            key = (node.get("classname"), node.get("name"))
            status = "FAIL" if node.find("failure") is not None or node.find("error") is not None else (
                "BLOCKED" if node.find("skipped") is not None else "PASS")
            tests[key] = {"test": "::".join(key), "status": status,
                          "seconds": float(node.get("time", 0)), "evidence": path.as_posix()}
    git = lambda *parts: subprocess.check_output(["git", *parts], cwd=ROOT, text=True).strip()
    environment = {
        "date": datetime.now(ZoneInfo("Australia/Sydney")).isoformat(),
        "branch": git("branch", "--show-current"), "codeCommit": git("rev-parse", "HEAD"),
        "workingTree": git("status", "--porcelain"), "baseMainCommit": args.base,
        "datasetVersion": "sprint2-synthetic-v2", "platform": platform.platform(),
        "python": platform.python_version(), "mode": "Non-Docker; isolated file-backed SQLite",
        "frontendUrl": "http://127.0.0.1:5173 (DOM origin; no deployed site)",
        "backendMode": "Flask test clients and real loopback HTTP on allocated ports",
        "browser": "Node.js/jsdom automated workflows; supplemental in-app browser at port 5176 for source link only",
    }
    plan = json.loads((ROOT / "docs/testing/us16/plan.json").read_text(encoding="utf-8"))
    results = []
    for case in plan["cases"]:
        selected, missing = {}, []
        for check in case["checks"]:
            # Treat brackets in parameterized test names literally, not as glob classes.
            pattern = check["name"].replace("[", "[[]")
            matches = {key: value for key, value in tests.items()
                       if key[0] == check["class"] and fnmatch.fnmatchcase(key[1], pattern)}
            if not matches:
                missing.append(check)
            selected.update(matches)
        evidence = list(selected.values())
        counts = Counter(row["status"] for row in evidence)
        status = ("FAIL" if counts["FAIL"] else "NOT READY" if missing else
                  "BLOCKED" if counts["BLOCKED"] else "PASS" if evidence else "NOT READY")
        if "manualStatus" in case:
            status = case["manualStatus"]
        actual = case.get("manualActual", f"Executed assertions: {dict(counts)}; unmatched selectors: {len(missing)}.")
        results.append({**case, "environment": environment, "status": status,
                        "actualResult": actual, "evidence": evidence, "missingChecks": missing})
    totals = {key: sum(case["status"] == key for case in results)
              for key in ("PASS", "FAIL", "BLOCKED", "NOT READY", "NOT APPLICABLE")}
    output = {"environment": environment, "sources": sources, "totals": totals,
              "automatedTotals": dict(Counter(value["status"] for value in tests.values())),
              "cases": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(totals))
    return 1 if totals["FAIL"] or totals["NOT READY"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

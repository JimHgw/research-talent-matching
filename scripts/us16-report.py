"""Map current-run JUnit evidence to the US-16 acceptance plan without running tests."""

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


def junit_status(node):
    if node.find("failure") is not None or node.find("error") is not None:
        return "FAIL"
    if node.find("skipped") is not None:
        return "BLOCKED"
    return "PASS"


def load_current_reports(paths):
    """
    Load only reports explicitly supplied as evidence for the current run.

    Historical/reference JUnit files must not be passed here because tests found
    in these reports are eligible to satisfy acceptance checks.
    """
    tests = {}
    sources = []

    for path in paths:
        path = path.resolve()

        if not path.is_file():
            raise FileNotFoundError(f"JUnit report does not exist: {path}")

        raw = path.read_bytes()
        sources.append(
            {
                "file": path.as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "role": "current-run",
            }
        )

        root = ET.fromstring(raw)

        for node in root.iter("testcase"):
            classname = node.get("classname")
            name = node.get("name")

            if not classname or not name:
                continue

            key = (classname, name)

            tests[key] = {
                "test": f"{classname}::{name}",
                "status": junit_status(node),
                "seconds": float(node.get("time", 0)),
                "evidence": path.as_posix(),
            }

    return tests, sources


def load_reference_sources(paths):
    """
    Record historical/reference reports for traceability only.

    These reports are deliberately never loaded into the test-result mapping,
    so historical results cannot satisfy a current US-16 acceptance case.
    """
    sources = []

    for path in paths:
        path = path.resolve()

        if not path.is_file():
            raise FileNotFoundError(f"Reference JUnit report does not exist: {path}")

        raw = path.read_bytes()
        sources.append(
            {
                "file": path.as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "role": "reference-only",
            }
        )

    return sources


def find_matches(tests, check):
    # Treat brackets in parameterized test names literally, not as glob classes.
    pattern = check["name"].replace("[", "[[]")

    return {
        key: value
        for key, value in tests.items()
        if key[0] == check["class"]
        and fnmatch.fnmatchcase(key[1], pattern)
    }


def evaluate_case(case, tests):
    selected = {}
    missing = []

    for check in case["checks"]:
        matches = find_matches(tests, check)

        # Most checks require one matching execution. Parameterised acceptance
        # checks can explicitly require more than one distinct execution.
        minimum_matches = int(check.get("minimumMatches", 1))

        if len(matches) < minimum_matches:
            missing.append(
                {
                    **check,
                    "minimumMatches": minimum_matches,
                    "actualMatches": len(matches),
                    "matchedTests": [
                        "::".join(key)
                        for key in sorted(matches)
                    ],
                }
            )

        selected.update(matches)

    evidence = list(selected.values())
    counts = Counter(row["status"] for row in evidence)

    if counts["FAIL"]:
        automated_status = "FAIL"
    elif missing:
        automated_status = "NOT READY"
    elif counts["BLOCKED"]:
        automated_status = "BLOCKED"
    elif evidence:
        automated_status = "PASS"
    else:
        automated_status = "NOT READY"

    status = automated_status

    # Manual statuses may describe genuinely manual/blocked cases, but must not
    # be able to turn missing or failing automated evidence into a PASS.
    manual_status = case.get("manualStatus")

    if manual_status is not None:
        if manual_status == "PASS" and case["checks"] and automated_status != "PASS":
            status = automated_status
        else:
            status = manual_status

    actual = case.get(
        "manualActual",
        (
            f"Executed assertions: {dict(counts)}; "
            f"incomplete checks: {len(missing)}."
        ),
    )

    return {
        **case,
        "status": status,
        "actualResult": actual,
        "evidence": evidence,
        "missingChecks": missing,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--junit",
        type=Path,
        action="append",
        required=True,
        help=(
            "JUnit reports produced for the CURRENT validation run only. "
            "Historical reports must use --reference-junit."
        ),
    )

    parser.add_argument(
        "--reference-junit",
        type=Path,
        action="append",
        default=[],
        help=(
            "Historical/reference JUnit reports recorded for traceability only. "
            "They cannot satisfy acceptance checks."
        ),
    )

    parser.add_argument("--base", required=True)

    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs/testing/us16/results.json",
    )

    args = parser.parse_args()

    tests, current_sources = load_current_reports(args.junit)
    reference_sources = load_reference_sources(args.reference_junit)

    git = lambda *parts: subprocess.check_output(
        ["git", *parts],
        cwd=ROOT,
        text=True,
    ).strip()

    environment = {
        "date": datetime.now(
            ZoneInfo("Australia/Sydney")
        ).isoformat(),
        "branch": git("branch", "--show-current"),
        "codeCommit": git("rev-parse", "HEAD"),
        "workingTree": git("status", "--porcelain"),
        "baseMainCommit": args.base,
        "datasetVersion": "sprint2-synthetic-v2",
        "platform": platform.platform(),
        "python": platform.python_version(),
        "mode": "Non-Docker; isolated file-backed SQLite",
        "frontendUrl": (
            "http://127.0.0.1:5173 "
            "(DOM origin; no deployed site)"
        ),
        "backendMode": (
            "Flask test clients and real loopback HTTP "
            "on allocated ports"
        ),
        "browser": (
            "Node.js/jsdom automated workflows; "
            "supplemental in-app browser at port 5176 "
            "for source link only"
        ),
    }

    plan_path = ROOT / "docs/testing/us16/plan.json"
    plan = json.loads(
        plan_path.read_text(encoding="utf-8")
    )

    results = []

    for case in plan["cases"]:
        result = evaluate_case(case, tests)
        result["environment"] = environment
        results.append(result)

    totals = {
        key: sum(case["status"] == key for case in results)
        for key in (
            "PASS",
            "FAIL",
            "BLOCKED",
            "NOT READY",
            "NOT APPLICABLE",
        )
    }

    output = {
        "environment": environment,
        "sources": current_sources + reference_sources,
        "totals": totals,
        "automatedTotals": dict(
            Counter(
                value["status"]
                for value in tests.values()
            )
        ),
        "cases": results,
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(output, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(totals))

    return 1 if totals["FAIL"] or totals["NOT READY"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
"""Reproducible, local-only BE-8 HTTP measurements on disposable SQLite files.

Run from the repository root with the project Python. No business DB is opened.
"""

import argparse
from collections import Counter
from contextlib import ExitStack
from hashlib import sha256
import json
import math
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import event
import sqlalchemy

from backend.src.app import create_app
from backend.src.db.models import Opportunity, TalentProfile
from backend.src.features.matching import service, team_service
from backend.src.shared.paths import ROOT
from backend.tests.be8_data import (MANIFEST, NOW, OWNER, TARGET, TEAM,
                                   authenticated_client, seed_dataset)


def fingerprint(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def measure(app, client, path, query, samples, warmups):
    engine = app.extensions["database"].engine
    metrics = {}
    statements = []

    def sql(_, __, statement, parameters, ___, ____):
        if statement.lstrip().upper().startswith(("BEGIN", "PRAGMA")):
            return
        metrics["sql"] += 1
        if not statement.lstrip().upper().startswith("SELECT"):
            raise AssertionError("A list request performed a write: " + statement.split()[0])
        root = re.search(r"\bFROM\s+(\w+)", statement, re.IGNORECASE)
        for table in ("opportunity_requirements", "opportunity_skill_details", "requirement_tags",
                      "privacy_visible_fields", "profile_skill_details", "profile_skills",
                      "profile_interests", "profile_text_details", "profile_personal_interests"):
            if root and root[1] == table:
                metrics["related_sql"] += 1
                break
        statements.append((statement, parameters))

    def loaded(row, _):
        metrics["opportunities_loaded" if isinstance(row, Opportunity) else "profiles_loaded"] += 1

    original = service.enrich_matches

    def scored(pairs):
        metrics["scored"] += len(pairs)
        return original(pairs)

    expected = None

    def request():
        nonlocal expected
        metrics.clear()
        metrics.update(sql=0, related_sql=0, opportunities_loaded=0, profiles_loaded=0, scored=0)
        statements.clear()
        start = time.perf_counter()
        response = client.get(path, query_string={"pageSize": MANIFEST["pageSize"], **query})
        elapsed = (time.perf_counter() - start) * 1000
        assert response.status_code == 200, response.get_json()
        value = response.get_json()
        digest = fingerprint(value)
        if expected is None:
            expected = digest
        assert digest == expected, "Unstable response across repeated requests"
        return elapsed, value

    with ExitStack() as stack:
        stack.enter_context(patch.object(service, "enrich_matches", scored))
        stack.enter_context(patch.object(team_service, "enrich_matches", scored))
        event.listen(engine, "before_cursor_execute", sql)
        event.listen(Opportunity, "load", loaded)
        event.listen(TalentProfile, "load", loaded)
        try:
            for _ in range(warmups):
                request()
            latencies, counts = [], []
            for _ in range(samples):
                elapsed, value = request()
                latencies.append(elapsed)
                counts.append(dict(metrics))
            tracemalloc.start()
            request()
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
        finally:
            event.remove(engine, "before_cursor_execute", sql)
            event.remove(Opportunity, "load", loaded)
            event.remove(TalentProfile, "load", loaded)
    plans = []
    with engine.connect() as connection:
        for statement, params in statements:
            if "FROM opportunities" in statement or "FROM talent_profiles JOIN" in statement:
                plans.append({"sql": statement, "plan": [list(row) for row in
                    connection.exec_driver_sql("EXPLAIN QUERY PLAN " + statement, params)]})
    assert all(count == counts[0] for count in counts), "Non-constant query/candidate counts"
    ordered = sorted(latencies)
    return {"samples": samples, "warmups": warmups, "p50_ms": round(statistics.median(latencies), 3),
            "p95_ms": round(ordered[math.ceil(.95 * len(ordered)) - 1], 3),
            "peak_python_mib": round(peak / 1024 ** 2, 3), "counts": counts[0],
            "eligible_total": value["total"], "response_sha256": expected,
            "latencies_ms": [round(x, 3) for x in latencies], "plans": plans}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--compare", type=Path, help="Fail unless all response fingerprints/totals/scored counts equal this baseline.")
    parser.add_argument("--samples", type=int, default=MANIFEST["samples"])
    args = parser.parse_args()
    if args.samples < 30:
        parser.error("BE-8 requires at least 30 measured requests per group")
    output = {"label": args.label, "fixture_version": MANIFEST["version"], "reference_time": NOW.isoformat(),
              "fixture_sha256": fingerprint(MANIFEST), "environment": {"platform": platform.platform(),
              "python": platform.python_version(), "sqlalchemy": sqlalchemy.__version__, "database": "SQLite",
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()},
              "memory_metric": "Peak Python allocations in one additional warmed HTTP request, via tracemalloc; excludes native ONNX allocations.",
              "groups": []}
    for size in MANIFEST["sizes"]:
        with tempfile.TemporaryDirectory(prefix="be8-", dir=ROOT / ".pytest_cache") as directory:
            app = create_app({"TESTING": True, "DATABASE_URL": f"sqlite:///{Path(directory).as_posix()}/bench.db",
                              "COOKIE_SECURE": False, "SEMANTIC_MATCHING_ENABLED": True})
            database = app.extensions["database"]
            try:
                database.initialise()
                seed_dataset(app, size)
                # Fail explicitly if real application model resources cannot be used.
                app.extensions["semantic_matching"].encode(["BE8 model verification"])
                owner, team = authenticated_client(app, OWNER), authenticated_client(app, TEAM)
                with ExitStack() as stack:
                    for module in ("backend.src.features.opportunities.availability",
                                   "backend.src.features.opportunities.service"):
                        stack.enter_context(patch(module + ".utcnow", lambda: NOW))
                    for name, client, path, filters in (
                        ("opportunities", owner, "/api/v1/opportunities", MANIFEST["opportunityFilters"]),
                        ("recommendations", owner, "/api/v1/me/recommendations", MANIFEST["opportunityFilters"]),
                        ("talents", team, f"/api/v1/opportunities/{TARGET}/talent-matches", MANIFEST["talentFilters"])):
                        for filtered, query in ((False, {}), (True, filters)):
                            result = measure(app, client, path, query, args.samples, MANIFEST["warmups"])
                            output["groups"].append({"size": size, "endpoint": name, "filtered": filtered, **result})
                            print(f"{args.label} n={size} {name} filtered={filtered}: "
                                  f"P50={result['p50_ms']}ms P95={result['p95_ms']}ms "
                                  f"peak={result['peak_python_mib']}MiB {result['counts']}", flush=True)
            finally:
                database.engine.dispose()
    output["model"] = app.extensions["semantic_matching"].config
    if args.compare:
        before = json.loads(args.compare.read_text(encoding="utf-8"))
        assert before["fixture_sha256"] == output["fixture_sha256"] and before["model"] == output["model"]
        assert len(before["groups"]) == len(output["groups"])
        for left, right in zip(before["groups"], output["groups"], strict=True):
            for field in ("size", "endpoint", "filtered", "eligible_total", "response_sha256"):
                assert left[field] == right[field], f"Before/after mismatch in {field}: {left[field]} != {right[field]}"
            assert left["counts"]["scored"] == right["counts"]["scored"]
        output["comparison"] = {"baseline": args.compare.as_posix(), "groups_identical": len(output["groups"]),
                                "checks": ["fixture", "model", "response fingerprint", "total", "scored candidate count"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

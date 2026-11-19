"""Fail release acceptance when mandatory current-run JUnit evidence is absent/skipped."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
GATES = {
    "backend": ("backend-tests-*.xml", 3, [
        "test_request_failure_is_correlated_without_sensitive_diagnostics",
        "test_worker_cli_exposes_claim_reclaim_result_without_lease_secrets",
        "test_release_document_conflict_privacy_fallback_expiry_flow",
        "test_concurrent_profile_saves_have_one_complete_winner",
        "test_killed_process_recovers_after_natural_lease_expiry",
        "test_health_check_does_not_create_sessions_or_expose_database_errors",
        "test_missing_schema_blocks_health_and_native_worker",
    ]),
    "mysql": ("mysql-tests-*.xml", 3, [
        "test_release_database_identity", "test_release_document_conflict_privacy_fallback_expiry_flow",
        "test_concurrent_profile_saves_have_one_complete_winner",
        "test_existing_mysql_text_column_upgrade_preserves_profile_and_is_repeatable",
        "test_killed_process_recovers_after_natural_lease_expiry",
    ]),
    "frontend": ("frontend-integration.xml", 1, [
        "test_us09_real_frontend_workflow", "test_task61_review_states_and_accounts",
        "test_fe3_slow_worker_polling", "test_fe4_editor_recovery_and_sessions",
    ]),
    "actualModel": ("be7-application-model.xml", 1, [
        "test_real_chinese_negation_and_collection_consistency", "test_release_flow_actual_model",
        "test_real_model_query_optimisations_preserve_scores_and_ranks",
    ]),
}


def assess(directory):
    groups, errors = {}, []
    for name, (pattern, required_files, required) in GATES.items():
        files = sorted(directory.glob(pattern))
        cases, properties = [], {}
        if len(files) != required_files:
            errors.append(f"{name}: expected {required_files} report files, found {len(files)}")
        for path in files:
            root = ET.parse(path).getroot()
            cases.extend(root.iter("testcase"))
            properties.update({p.get("name"): p.get("value") for p in root.iter("property")})
        failed = sum(c.find("failure") is not None for c in cases)
        errored = sum(c.find("error") is not None for c in cases)
        skipped = sum(c.find("skipped") is not None for c in cases)
        if not cases or failed or errored:
            errors.append(f"{name}: empty or failing test report")
        for target in required:
            matches = [c for c in cases if c.get("name", "").split("[")[0] == target]
            if not matches or any(any(c.find(tag) is not None for tag in ("skipped", "failure", "error")) for c in matches):
                errors.append(f"{name}: mandatory case absent or not passed: {target}")
        if name == "frontend" and skipped:
            errors.append("frontend: required integration suite has skipped cases")
        if name == "mysql" and (properties.get("BE10.database") != "mysql"
                                or not properties.get("BE10.databaseVersion", "").startswith("8.4.")):
            errors.append("mysql: real MySQL 8.4 identity evidence missing")
        if name == "actualModel":
            config = json.loads((ROOT / "backend/src/features/matching/semantic_config.json").read_text(encoding="utf-8"))
            for key in ("model", "modelVersion", "revision"):
                if properties.get("BE7." + key) != json.dumps(config[key], ensure_ascii=False):
                    errors.append(f"actualModel: current {key} execution evidence missing")
        groups[name] = {"passed": len(cases) - failed - errored - skipped, "failed": failed,
                        "errors": errored, "skipped": skipped,
                        "reports": [p.name for p in files], "properties": properties}
    return {"status": "FAIL" if errors else "PASS", "gates": groups, "errors": errors}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports", type=Path, default=Path("reports"))
    parser.add_argument("--output", type=Path, default=Path("reports/release-acceptance.json"))
    args = parser.parse_args(argv)
    result = assess(args.reports)
    result.update({"commit": os.getenv("CI_COMMIT_SHA") or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "branch": os.getenv("CI_COMMIT_REF_NAME") or subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "recordedAtUtc": datetime.now(timezone.utc).isoformat(),
        "reportRuntime": {"python": platform.python_version(), "platform": platform.system()},
        "pipeline": os.getenv("CI_PIPELINE_URL")})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "errors": result["errors"]}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

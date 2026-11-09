"""Run the 14 opt-in MySQL/Docker checks using disposable test containers."""

import argparse
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from sqlalchemy import create_engine


ROOT = Path(__file__).resolve().parents[1]
MYSQL_TESTS = (
    "test_migration_verifies_values_preserves_login_and_refuses_overwrite",
    "test_failed_migration_rolls_back_every_table",
    "test_invalid_source_does_not_create_sqlite_file",
    "test_mysql_enforces_lengths_and_case_sensitive_ids",
    "test_mysql_cleanup_removes_related_rows_without_rebuilding_tables",
)
ACADEMIC_CASES = (
    "EDUCATION-education-criteria0-MATCHED-100-edu_test",
    "RESEARCH_EXPERIENCE-researchExperience-criteria1-PARTIAL-50-exp_test",
    "RESEARCH_OUTPUT-researchOutputs-criteria2-MATCHED-100-output_test",
    "RESEARCH_OUTPUT-researchOutputs-criteria3-UNKNOWN-0-None",
)
TESTS = (
    *(f"backend/tests/test_mysql.py::{name}" for name in MYSQL_TESTS),
    *(f"backend/tests/test_us18.py::test_academic_evidence_api[{schema}-{case}]"
      for schema in ("upgraded-legacy-schema", "upgraded-startup-schema")
      for case in ACADEMIC_CASES),
    "backend/tests/test_docker_stack.py::test_real_stack_login_profile_and_restart_persistence",
)


def docker_output(docker, *args, timeout=45):
    result = subprocess.run([docker, *args], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Docker command failed.")
    return result.stdout.strip()


def wait_for_mysql(url, timeout=180):
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                with engine.connect() as connection:
                    connection.exec_driver_sql("SELECT 1")
                return
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError("The disposable MySQL server did not become ready.") from None
                time.sleep(2)
    finally:
        engine.dispose()


def verify_report(report, *, include_be8=False):
    cases = ET.parse(report).getroot().findall(".//testcase")
    expected = {node.split("::", 1)[1] for node in TESTS}
    environment_cases = [case for case in cases if "test_sprint3_be8" not in case.get("classname", "")]
    if len(environment_cases) != len(TESTS) or {case.get("name") for case in environment_cases} != expected:
        raise RuntimeError("The report does not contain exactly the 14 requested test cases.")
    be8_cases = [case for case in cases if "test_sprint3_be8" in case.get("classname", "")]
    if (include_be8 and not be8_cases) or (not include_be8 and be8_cases):
        raise RuntimeError("The report does not match the requested BE-8 coverage.")
    if any(case.find(tag) is not None for case in cases for tag in ("skipped", "failure", "error")):
        raise RuntimeError("All requested checks must execute and pass; skips are not accepted.")


def verify_mysql_report(report):
    cases = ET.parse(report).getroot().findall(".//testcase")
    if not cases or any(case.find(tag) is not None for case in cases for tag in ("failure", "error")):
        raise RuntimeError("The selected MySQL tests must execute without failures or errors.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--include-be8", action="store_true", help="Also run BE-8 against the disposable MySQL server with the required real model.")
    selection.add_argument("--mysql-shard", nargs=2, type=int, metavar=("INDEX", "TOTAL"),
                           help="Run a complete CI MySQL shard in its normal collection order.")
    selection.add_argument("--mysql-tests", nargs="+", metavar="NODE",
                           help="Run selected MySQL test nodes in the supplied order.")
    parser.add_argument("--report", type=Path, help="Write JUnit evidence to this path instead of the temporary report directory.")
    args = parser.parse_args()
    if args.mysql_shard and not 1 <= args.mysql_shard[0] <= args.mysql_shard[1]:
        parser.error("--mysql-shard requires 1 <= INDEX <= TOTAL.")
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("Install Docker Desktop and start its Linux engine first.")
    if docker_output(docker, "info", "--format", "{{.OSType}}") != "linux":
        raise RuntimeError("Start Docker Desktop's Linux engine first.")
    docker_output(docker, "compose", "version")
    shell = shutil.which("sh")
    git_bash = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
    if not shell and not (os.name == "nt" and git_bash.is_file()):
        raise RuntimeError("A POSIX shell is required for the startup checks; install Git Bash on Windows.")

    image = subprocess.run([docker, "image", "inspect", "mysql:8.4"], cwd=ROOT,
                           capture_output=True, timeout=45)
    if image.returncode:
        print("Downloading the MySQL 8.4 test image...", flush=True)
        pulled = subprocess.run([docker, "pull", "mysql:8.4"], cwd=ROOT, timeout=900)
        if pulled.returncode:
            raise RuntimeError("Could not download the MySQL 8.4 test image.")

    run_id = secrets.token_hex(6)
    name = f"banana-environment-test-{run_id}"
    password = secrets.token_hex(20)
    report = args.report or ROOT / ".pytest_cache/environment-tests" / f"{run_id}.xml"
    if not report.is_absolute():
        report = ROOT / report
    report.parent.mkdir(parents=True, exist_ok=True)
    container = None
    try:
        print("Creating an isolated MySQL 8.4 test server...", flush=True)
        # Only this new container receives the test database and credentials.
        # No existing container, host directory or named volume is attached.
        container = docker_output(
            docker, "run", "--detach", "--name", name,
            "--label", f"com.h18abanana.environment-test={run_id}",
            "--publish", "127.0.0.1::3306",
            "--env", "MYSQL_DATABASE=banana_environment_test",
            "--env", "MYSQL_USER=banana_test",
            "--env", f"MYSQL_PASSWORD={password}",
            "--env", f"MYSQL_ROOT_PASSWORD={secrets.token_hex(20)}",
            "mysql:8.4", "--character-set-server=utf8mb4", "--collation-server=utf8mb4_0900_bin",
        )
        if not re.fullmatch(r"[0-9a-f]{64}", container):
            raise RuntimeError("Docker returned an unexpected container ID.")
        binding = docker_output(docker, "port", container, "3306/tcp")
        match = re.fullmatch(r"127\.0\.0\.1:(\d+)", binding)
        if not match:
            raise RuntimeError("The test database must be published only on host loopback.")
        url = (f"mysql+pymysql://banana_test:{password}@127.0.0.1:"
               f"{match[1]}/banana_environment_test?charset=utf8mb4")
        wait_for_mysql(url)
        env = {**os.environ, "MYSQL_TEST_DATABASE_URL": url}
        mysql_only = args.mysql_shard is not None or args.mysql_tests is not None
        index, total = args.mysql_shard or (1, 1)
        if args.mysql_shard:
            label = f"CI MySQL shard {index}/{total}"
            tests = ("backend/tests",)
        elif args.mysql_tests:
            label, tests = "selected MySQL tests", args.mysql_tests
        else:
            label = "14 MySQL/Docker checks plus BE-8 MySQL checks" if args.include_be8 else "14 MySQL/Docker checks"
            tests = (*TESTS, "backend/tests/test_sprint3_be8.py", "--require-application-model") if args.include_be8 else TESTS
        flags = ["--run-mysql", f"--shard-index={index}", f"--shard-total={total}"]
        flags += ["-q", "--durations=10"] if args.mysql_shard else ["-v", "--tb=short"]
        if not mysql_only:
            flags.append("--run-docker")
        print(f"Running {label}...", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pytest", *tests, *flags, "-rs", f"--junitxml={report}"],
            cwd=ROOT, env=env,
        )
        print(f"Test report: {report}", flush=True)
        if result.returncode:
            return result.returncode
        if mysql_only:
            verify_mysql_report(report)
            print(f"{label} completed without failures or errors; see the report for optional skips.", flush=True)
        else:
            verify_report(report, include_be8=args.include_be8)
            print(f"All {label} passed with zero skips.", flush=True)
        return 0
    finally:
        if container and re.fullmatch(r"[0-9a-f]{64}", container):
            print("Removing the disposable MySQL test container and its anonymous volume...", flush=True)
            docker_output(docker, "rm", "--force", "--volumes", container)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Environment checks failed: {error}", file=sys.stderr)
        raise SystemExit(1)

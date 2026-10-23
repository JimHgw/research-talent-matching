"""Versioned test state built only in a new, isolated SQLite run directory."""

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import secrets

from backend.src.app import create_app
from backend.src.features.auth.routes import provision_user
from backend.src.features.profile.routes import seed_tags
from backend.src.shared.validation import validator
from backend.tests.conftest import headers, sign_in

DATASET = Path(__file__).parent / "data/sprint2"
FILES = ("manifest.json", "talents.json", "opportunities.json", "expected-results.json")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def load_dataset(directory=DATASET):
    directory = Path(directory)
    data = {name.removesuffix(".json"): json.loads((directory / name).read_text(encoding="utf-8"))
            for name in FILES}
    manifest = data["manifest"]
    version = manifest["datasetVersion"]
    if not isinstance(version, str) or not version.strip():
        raise ValueError("A dataset version is required.")
    if data["expected-results"]["datasetVersion"] != version:
        raise ValueError("Expected labels belong to another dataset version.")
    validator("TagList").validate({"items": manifest["tags"]})
    tags = {tag["id"]: tag["kind"] for tag in manifest["tags"]}
    if len(tags) != len(manifest["tags"]):
        raise ValueError("Duplicate tag ID.")
    accounts = {item["id"]: item for item in manifest["accounts"]}
    records = data["talents"] + data["opportunities"]
    ids = [item["id"] for item in records]
    if len(set(ids)) != len(ids) or len(accounts) != len(manifest["accounts"]):
        raise ValueError("Duplicate dataset identifier.")
    for identifier in [*ids, *accounts]:
        validator("Id").validate(identifier)
        if not identifier.startswith("s2_"):
            raise ValueError("Dataset identifiers must use the s2_ scope.")
    for account in accounts.values():
        if account["role"] not in ("TALENT", "RESEARCH_TEAM") or not account["purpose"]:
            raise ValueError("An account needs a supported role and purpose.")
    talent_ids = {item["id"] for item in data["talents"]}
    if talent_ids != {key for key, account in accounts.items() if account["role"] == "TALENT"}:
        raise ValueError("Every talent account needs exactly one profile.")
    for item in data["talents"]:
        validator("ProfileContent").validate(item["content"])
        state = item["state"]
        validator("PrivacyWrite").validate({"expectedRevision": 0,
            "discoverable": state["discoverable"], "visibleFields": state["visibleFields"]})
        if state["confirmationStatus"] not in ("CONFIRMED", "UNCONFIRMED"):
            raise ValueError("Invalid confirmation state.")
        if state["profileRevision"] != 1 or state["privacyRevision"] != int(
                state["discoverable"] or bool(state["visibleFields"])):
            raise ValueError("Starting revisions must match one initial profile/privacy write.")
        skill_ids = [skill["id"] for skill in item["content"]["skills"]]
        if len(set(skill_ids)) != len(skill_ids):
            raise ValueError("Duplicate skill record ID.")
        if any(tags.get(tag) != "INTEREST" for tag in item["content"]["researchInterests"]):
            raise ValueError("Unknown interest tag.")
    for item in data["opportunities"]:
        validator("OpportunityContent").validate(item["content"])
        if accounts[item["owner"]]["role"] != "RESEARCH_TEAM":
            raise ValueError("Opportunity owner must be a team.")
        state = item["state"]
        if state not in ({"status": "DRAFT", "revision": 1}, {"status": "PUBLISHED", "revision": 2}):
            raise ValueError("Invalid initial opportunity state.")
        if state["status"] == "PUBLISHED" and not item["content"]["requirements"]:
            raise ValueError("A published opportunity requires criteria.")
        for requirement in item["content"]["requirements"]:
            if any(tags.get(tag) != requirement["kind"] for tag in requirement["tagIds"]):
                raise ValueError("Unknown requirement tag or incorrect kind.")
    sources = manifest["sources"]
    if len(sources) != len(ids) or {source["recordId"] for source in sources} != set(ids):
        raise ValueError("Every example needs exactly one source record.")
    for source in sources:
        if source["exampleType"] != ("talent" if source["recordId"] in talent_ids else "opportunity"):
            raise ValueError("Source type does not match the example.")
        if source["sourceCategory"] not in ("public", "owner-provided", "authorised", "synthetic", "de-identified"):
            raise ValueError("Unsupported source category.")
        date.fromisoformat(source["datePrepared"])
        for field in ("sourceReference", "preparationSteps", "deIdentificationSteps", "intendedTestUse"):
            if not source[field]:
                raise ValueError("Source preparation and intended use must be recorded.")
        for field in ("originalContainsPrivateInformation", "originalFileRetained"):
            if type(source[field]) is not bool:
                raise ValueError("Source privacy flags must be explicit booleans.")
        if source["datasetVersion"] != version:
            raise ValueError("Source version mismatch.")
    opportunities = {item["id"]: item for item in data["opportunities"]}
    cases = data["expected-results"]["cases"]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Unique, independent expected labels are required.")
    for case in cases:
        if case["talent"] not in talent_ids or case["opportunity"] not in opportunities:
            raise ValueError("Expected label references a missing record.")
        if case["audience"] not in ("owner", "team", "engine") or not case["labelSource"]:
            raise ValueError("Expected labels require an audience and manual source.")
        if case["httpStatus"] in (200, None):
            if len(case["statuses"]) != len(opportunities[case["opportunity"]]["content"]["requirements"]):
                raise ValueError("One expected status per requirement is required.")
            if any(s not in ("MATCHED", "PARTIAL", "GAP", "UNKNOWN") for s in case["statuses"]):
                raise ValueError("Unsupported expected status.")
            validator("MatchSummary").validate({**case["summary"], "algorithmVersion": manifest["algorithmVersion"]})
    return data


@dataclass
class PreparedRun:
    app: object
    dataset: dict
    clients: dict
    report: dict

    def close(self):
        self.app.extensions["database"].engine.dispose()


def _checked(response, expected=200):
    if response.status_code != expected:
        # Do not copy user-supplied content or credentials into preparation errors.
        raise RuntimeError(f"Preparation request failed: HTTP {response.status_code}, expected {expected}.")
    return response.get_json()


def prepare_run(run_directory, *, dataset_directory=DATASET, password=None):
    """Restore by creating a fresh run; never open or reset an existing database.

    Refusing an existing directory is intentional, including empty directories.
    There is no database URL argument and no use of the ambient DATABASE_URL.
    """
    data = load_dataset(dataset_directory)
    run_directory = Path(run_directory).absolute()
    run_directory.mkdir(parents=True, exist_ok=False)
    app = create_app({"TESTING": True,
        "DATABASE_URL": "sqlite:///" + (run_directory / "test.sqlite3").as_posix(),
        "DOCUMENT_STORAGE_DIR": str(run_directory / "documents"),
        "COOKIE_SECURE": False, "ALLOWED_ORIGINS": ["http://127.0.0.1:5173"],
        "LOGIN_EMAIL_LIMIT": 1000, "LOGIN_IP_LIMIT": 1000, "SMTP_HOST": ""})
    database = app.extensions["database"]
    clients, accounts, talents, opportunities = {}, {}, {}, {}
    try:
        database.initialise()
        password = password or secrets.token_urlsafe(32) + "aA1!"
        with app.app_context():
            seed_tags(data["manifest"]["tags"])
            for account in data["manifest"]["accounts"]:
                identifier = account["id"]
                email = identifier + "@example.test"
                user_id = provision_user(email, password, identifier, account["role"])
                client = app.test_client()
                csrf = sign_in(client, email, password)
                clients[identifier] = (client, csrf)
                accounts[identifier] = {"userId": user_id, "role": account["role"], "purpose": account["purpose"]}
        for record in data["talents"]:
            client, csrf = clients[record["id"]]
            state = record["state"]
            profile = _checked(client.put("/api/v1/me/profile", headers=headers(csrf),
                json={"expectedRevision": 0, "content": record["content"]}))
            if profile["content"] != record["content"]:
                raise RuntimeError("Prepared profile content differs from its definition.")
            if state["confirmationStatus"] == "CONFIRMED":
                profile = _checked(client.post("/api/v1/me/profile/confirmation", headers=headers(csrf),
                    json={"expectedRevision": profile["revision"]}))
            privacy = _checked(client.put("/api/v1/me/privacy", headers=headers(csrf), json={
                "expectedRevision": 0, "discoverable": state["discoverable"], "visibleFields": state["visibleFields"]}))
            observed = {"profileRevision": profile["revision"],
                "confirmationStatus": profile["confirmation"]["status"],
                "privacyRevision": privacy["revision"], "discoverable": privacy["discoverable"],
                "visibleFields": sorted(privacy["visibleFields"])}
            if observed != {**state, "visibleFields": sorted(state["visibleFields"])}:
                raise RuntimeError("Prepared profile state differs from the starting definition.")
            talents[record["id"]] = {"talentId": profile["talentId"], **observed,
                                      "contentSha256": digest(profile["content"])}
        for record in data["opportunities"]:
            client, csrf = clients[record["owner"]]
            opportunity = _checked(client.post("/api/v1/opportunities", headers=headers(csrf),
                                               json=record["content"]), 201)
            if record["state"]["status"] == "PUBLISHED":
                opportunity = _checked(client.post(f"/api/v1/opportunities/{opportunity['id']}/publish",
                    headers=headers(csrf), json={"expectedRevision": opportunity["revision"]}))
            if {key: opportunity[key] for key in ("status", "revision")} != record["state"]:
                raise RuntimeError("Prepared opportunity differs from the starting definition.")
            if opportunity["content"] != record["content"]:
                raise RuntimeError("Prepared opportunity content differs from its definition.")
            opportunities[record["id"]] = {"opportunityId": opportunity["id"],
                "owner": record["owner"], **record["state"], "contentSha256": digest(opportunity["content"])}
        report = {"datasetVersion": data["manifest"]["datasetVersion"], "datasetSha256": digest(data),
            "algorithmVersion": data["manifest"]["algorithmVersion"], "startingStateVerified": True,
            "sourceStatus": data["manifest"]["sourceStatus"],
            "accounts": accounts, "talents": talents, "opportunities": opportunities}
        # An allowlisted report: no provenance details, passwords, source paths or documents.
        (run_directory / "starting-state.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return PreparedRun(app, data, clients, report)
    except BaseException:
        database.engine.dispose()
        # Keep a failed run for diagnosis; never delete its files or reuse its database.
        raise

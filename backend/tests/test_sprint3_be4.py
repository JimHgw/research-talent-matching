"""BE-4: concurrent revision control and transaction atomicity, proven on real connections.

Every race uses two independently signed-in HTTP clients whose requests run on separate
threads, and therefore on separate pooled database connections. Interleaving is fixed by
engine events and ``threading.Event`` barriers, never by sleeping to provoke a race:

1. the *first* writer runs until all of its reads and writes are done and it is about to
   COMMIT, then parks while still holding the writer lock;
2. the *second* writer starts and signals when it issues its writer-lock request (SQLite
   ``BEGIN IMMEDIATE``; MySQL ``SELECT ... FROM database_write_lock ... FOR UPDATE``). On
   MySQL the harness also observes that statement blocked in ``PROCESSLIST``;
3. only then is the first writer released.

So both requests are in flight with the same expected revision before either commits.
A negative control runs the same barriers with the lock removed and shows the invariant
breaks, which proves the barriers really create the overlap the lock must prevent.

Run on MySQL with ``--run-mysql`` and a disposable ``MYSQL_TEST_DATABASE_URL``. Set
``BE4_ROUNDS`` (default 10) and ``BE4_EVIDENCE=<file.json>`` to record per-round results.
"""

from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import time
from threading import Barrier, Event, Thread, current_thread
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text

from backend.src.db.database import WRITE_LOCK, require_write_lock
from backend.src.db.models import Base, Document, DocumentExtraction, PersonalInterestTag
from backend.src.features.documents import routes as document_routes
from backend.src.features.profile import routes as profile_routes
from conftest import headers, sign_in
from test_us01 import sample
from test_us02 import content as opportunity_content

ROUNDS = int(os.getenv("BE4_ROUNDS", "10"))
TIMEOUT = 30
PROFILE = "/api/v1/me/profile"
PRIVACY = "/api/v1/me/privacy"
OPPORTUNITIES = "/api/v1/opportunities"
WRITE = re.compile(r"^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+`?(\w+)`?", re.IGNORECASE)
# Session bookkeeping is not business state; the write mutex row never changes.
UNTRACKED = {"database_write_lock", "auth_sessions", "login_attempts"}
EVIDENCE = {"rounds": [], "faults": [], "controls": []}


@pytest.fixture(scope="module", autouse=True)
def evidence_file():
    yield
    path = os.getenv("BE4_EVIDENCE")
    if path and any(EVIDENCE.values()):
        Path(path).write_text(json.dumps(EVIDENCE, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def database_info(app):
    engine = app.extensions["database"].engine
    if engine.dialect.name == "mysql":
        with engine.connect() as connection:
            version = connection.scalar(text("SELECT VERSION()"))
    else:
        import sqlite3
        version = sqlite3.sqlite_version
    return {"dialect": engine.dialect.name, "serverVersion": version}


def lock_request(statement):
    statement = statement.strip().upper()
    return statement == "BEGIN IMMEDIATE" or ("DATABASE_WRITE_LOCK" in statement and "FOR UPDATE" in statement)


class Race:
    """Run two requests with a fixed interleaving on two connections."""

    def __init__(self, app):
        self.engine = app.extensions["database"].engine
        self.mysql = self.engine.dialect.name == "mysql"

    def observe_second_blocked(self):
        """MySQL only: the second request's lock statement must be running and waiting."""
        if not self.mysql:
            return None
        deadline = time.monotonic() + TIMEOUT
        query = text("SELECT COUNT(*) FROM information_schema.PROCESSLIST WHERE ID <> CONNECTION_ID() "
                     "AND COMMAND = 'Query' AND INFO LIKE :pattern")
        with self.engine.connect() as probe:
            while True:
                waiting = probe.scalar(query, {"pattern": "%database_write_lock%FOR UPDATE%"})
                probe.rollback()
                if waiting:
                    return True
                assert time.monotonic() < deadline, "second writer was never observed waiting for the lock"
                time.sleep(0.002)  # Observation interval only; the interleaving is held by the barrier.

    def run(self, first, second):
        parked, release, requested = Event(), Event(), Event()
        threads, outcome = {}, {}

        def on_commit(connection):
            if current_thread() is threads.get("first") and not parked.is_set():
                parked.set()
                if not release.wait(TIMEOUT):
                    raise RuntimeError("BE-4 harness never released the first writer")

        def on_rollback(connection):
            if current_thread() is threads.get("first"):
                parked.set()  # The first request failed; nothing is held, let assertions report it.

        def on_execute(connection, cursor, statement, parameters, context, executemany):
            if current_thread() is threads.get("second") and lock_request(statement):
                requested.set()

        def call(name, function):
            try:
                outcome[name] = function()
            except BaseException as error:  # Re-raised on the test thread below.
                outcome[name] = error

        listeners = (("commit", on_commit), ("rollback", on_rollback), ("before_cursor_execute", on_execute))
        for name, listener in listeners:
            event.listen(self.engine, name, listener)
        started = time.perf_counter()
        try:
            threads["first"] = Thread(target=call, args=("first", first), name="be4-first", daemon=True)
            threads["second"] = Thread(target=call, args=("second", second), name="be4-second", daemon=True)
            threads["first"].start()
            assert parked.wait(TIMEOUT), "first writer never reached COMMIT"
            threads["second"].start()
            assert requested.wait(TIMEOUT), "second writer never requested the writer lock"
            blocked = self.observe_second_blocked()
            release.set()
            for thread in threads.values():
                thread.join(TIMEOUT)
                assert not thread.is_alive(), f"{thread.name} did not finish"
        finally:
            release.set()
            for name, listener in listeners:
                event.remove(self.engine, name, listener)
        for value in outcome.values():
            if isinstance(value, BaseException):
                raise value
        return outcome["first"], outcome["second"], {
            "secondLockRequestedWhileFirstHeldLock": True,
            "secondObservedBlockedInProcesslist": blocked,
            "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
        }


class Actor:
    """An independent client/session for the same account."""

    def __init__(self, app, email="talent@example.test"):
        self.client = app.test_client()
        self.csrf = sign_in(self.client, email)

    def get(self, url):
        response = self.client.get(url)
        assert response.status_code == 200, response.get_json()
        return response.get_json()

    def put(self, url, payload):
        return self.client.put(url, json=payload, headers=headers(self.csrf))

    def post(self, url, payload):
        return self.client.post(url, json=payload, headers=headers(self.csrf))


@pytest.fixture
def actors(app):
    return Actor(app), Actor(app)


@pytest.fixture
def ready_document(app, actors):
    talent_id = actors[0].get(PROFILE)["talentId"]
    document_id = "doc_be4_" + uuid4().hex[:16]
    with app.extensions["database"].transaction(write=True) as db:
        db.add(Document(id=document_id, talent_id=talent_id, kind="CV", file_name="be4.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        storage_key="be4-" + uuid4().hex, status="READY", size_bytes=1, error=None))
        db.flush()
        db.add(DocumentExtraction(document_id=document_id, result={"suggestedSections": {}}))
    return document_id


def slug(tag):
    return re.sub(r"[^a-z0-9]", "_", tag.lower())


def records(tag):
    key = slug(tag)
    return {
        "education": [{"id": f"edu_{key}", "institution": f"University {tag}", "qualification": "PhD",
                       "discipline": "Computer Science", "startYear": 2024, "endYear": None}],
        "courses": [{"id": f"course_{key}", "name": f"Course {tag}", "code": "COMP3900", "description": ""}],
        "skills": [{"id": f"skill_{key}", "title": f"Skill {tag}", "evidenceText": f"Evidence {tag}"}],
        "customInterestTags": [{"label": f"Topic {tag}", "description": f"Described by {tag}"}],
        "researchInterestText": f"Interest text {tag}",
        "resumeDescription": f"Resume {tag}",
    }


def edited(current, tag, interests):
    """A real change to every profile section, including a brand-new personal tag."""
    content = deepcopy(current["content"])
    content.update(records(tag), displayName=f"Writer {tag}", researchInterests=interests)
    return content


def imported(tag, interests):
    return {**records(tag), "researchInterests": interests}


def other_interests(current):
    return [] if current["content"]["researchInterests"] else ["interest_ml"]


def save(actor, revision, content):
    return lambda: actor.put(PROFILE, {"expectedRevision": revision, "content": content})


def confirm(actor, revision):
    return lambda: actor.post(PROFILE + "/confirmation", {"expectedRevision": revision})


def apply(actor, document_id, revision, sections):
    return lambda: actor.post(f"/api/v1/me/documents/{document_id}/apply",
                              {"expectedProfileRevision": revision, "sections": deepcopy(sections)})


def snapshot(app):
    """Every business row, read on a fresh connection after the request has finished."""
    with app.extensions["database"].engine.connect() as connection:
        return {table.name: sorted(map(repr, connection.execute(select(table)).all()))
                for table in Base.metadata.sorted_tables if table.name not in UNTRACKED}


def personal_labels(app):
    with app.extensions["database"].transaction() as db:
        return list(db.scalars(select(PersonalInterestTag.label)))


def baseline(app, actor):
    """A confirmed profile with stored content, origins, tags and text components."""
    content = sample() | {"courses": [], "researchOutputs": [], "researchInterestText": "Baseline interest",
                          "customInterestTags": [{"label": "Baseline topic", "description": "Baseline"}]}
    response = actor.put(PROFILE, {"expectedRevision": 0, "content": content})
    assert response.status_code == 200, response.get_json()
    response = confirm(actor, response.get_json()["revision"])()
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def conflict(response, current_revision):
    data = response.get_json()
    assert response.status_code == 409, data
    assert data["error"]["code"] == "REVISION_CONFLICT"
    assert data["error"]["currentRevision"] == current_revision
    return data


def ok(response):
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def log(kind, app, name, round_, **values):
    EVIDENCE[kind].append({"test": name, "round": round_, **database_info(app), **values})


# --- Requirement 1/2: lock before reading the compared revision -------------------------

def test_revision_checks_require_the_writer_lock(app):
    database = app.extensions["database"]
    with database.transaction() as db:
        assert db.info[WRITE_LOCK] is False
        with pytest.raises(RuntimeError, match="write=True"):
            require_write_lock(db)
    with database.transaction(write=True) as db:
        assert db.info[WRITE_LOCK] is True
        require_write_lock(db)
        # The connection begins lazily: the lock is taken with the session's first statement.
        db.execute(select(1))
        if database.engine.dialect.name == "sqlite":
            # Holding RESERVED: an independent BEGIN IMMEDIATE must not get the lock.
            import sqlite3
            probe = sqlite3.connect(database.engine.url.database, timeout=0, isolation_level=None)
            try:
                with pytest.raises(sqlite3.OperationalError, match="locked"):
                    probe.execute("BEGIN IMMEDIATE")
            finally:
                probe.close()


ROUTES = ["profile", "confirmation", "privacy", "import", "opportunity", "publish"]


def revision_calls(app, actors, ready_document):
    talent, team = actors[0], Actor(app, "team@example.test")
    profile = ok(save(talent, 0, edited(talent.get(PROFILE), "routes", ["interest_ml"]))())
    created = team.client.post(OPPORTUNITIES, json=opportunity_content(), headers=headers(team.csrf))
    opportunity = created.get_json()
    url = f"{OPPORTUNITIES}/{opportunity['id']}"
    privacy = talent.get(PRIVACY)["revision"]
    return {
        "profile": save(talent, profile["revision"], edited(profile, "guard", [])),
        "confirmation": confirm(talent, profile["revision"]),
        "privacy": lambda: talent.put(PRIVACY, {"expectedRevision": privacy,
                                                "discoverable": True, "visibleFields": ["displayName"]}),
        "import": apply(talent, ready_document, profile["revision"], imported("guard", [])),
        "opportunity": lambda: team.put(url, {"expectedRevision": opportunity["revision"],
                                              "content": opportunity_content() | {"title": "Guard"}}),
        "publish": lambda: team.post(url + "/publish", {"expectedRevision": opportunity["revision"]}),
    }


@pytest.mark.parametrize("route", ROUTES)
def test_writer_lock_is_the_first_statement_of_every_revision_write(app, actors, ready_document, route):
    """Requirement 1: no application read (session, owner, revision) precedes the lock."""
    call = revision_calls(app, actors, ready_document)[route]
    engine = app.extensions["database"].engine
    statements = []

    def on_execute(connection, cursor, statement, parameters, context, executemany):
        if current_thread().name == "MainThread":
            statements.append(statement.strip())
    event.listen(engine, "before_cursor_execute", on_execute)
    try:
        response = call()
    finally:
        event.remove(engine, "before_cursor_execute", on_execute)
    assert response.status_code == 200, response.get_json()
    assert statements and lock_request(statements[0]), statements[:3]
    assert sum(map(lock_request, statements)) == 1  # One write transaction per request.
    EVIDENCE["controls"].append({"test": f"lock_first:{route}", **database_info(app),
                                 "firstStatement": statements[0], "statements": len(statements)})


@pytest.mark.parametrize("route", ROUTES)
def test_every_revision_write_refuses_to_run_without_the_lock(app, actors, ready_document, monkeypatch, route):
    """A future refactor that drops write=True fails loudly instead of losing updates."""
    call = revision_calls(app, actors, ready_document)[route]
    before = snapshot(app)
    database = app.extensions["database"]
    original = type(database).transaction

    def read_only(self, *, write=False):
        return original(self, write=False)
    monkeypatch.setattr(type(database), "transaction", read_only)
    assert call().status_code == 500
    monkeypatch.undo()
    assert snapshot(app) == before


# --- Acceptance: concurrent real changes with the same revision ---------------------------

def test_concurrent_profile_saves_have_one_complete_winner(app, actors):
    race = Race(app)
    for round_ in range(ROUNDS):
        current = actors[0].get(PROFILE)
        revision, interests = current["revision"], other_interests(current)
        first_actor, second_actor = actors if round_ % 2 == 0 else actors[::-1]
        first_tag, second_tag = f"save {round_} first", f"save {round_} second"
        first, second, timing = race.run(save(first_actor, revision, edited(current, first_tag, interests)),
                                         save(second_actor, revision, edited(current, second_tag, interests)))
        winner = ok(first)
        conflict(second, revision + 1)
        assert winner["revision"] == revision + 1
        assert winner["content"]["displayName"] == f"Writer {first_tag}"
        assert winner["confirmation"]["status"] == "UNCONFIRMED"
        assert {item["sourceType"] for item in winner["origins"]} == {"MANUAL"}
        # Only the winner's complete result is stored: content, tags and provenance.
        assert actors[1].get(PROFILE) == winner
        labels = personal_labels(app)
        assert f"Topic {first_tag}" in labels and f"Topic {second_tag}" not in labels
        log("rounds", app, "profile_save_vs_save", round_, statuses=[200, 409],
            revisionBefore=revision, revisionAfter=winner["revision"], **timing)


def test_import_competing_with_manual_save_obeys_the_revision(app, actors, ready_document):
    race = Race(app)
    for round_ in range(ROUNDS):
        current = actors[0].get(PROFILE)
        revision, interests = current["revision"], other_interests(current)
        save_tag, import_tag = f"manual {round_}", f"import {round_}"
        manual = save(actors[0], revision, edited(current, save_tag, interests))
        reviewed = apply(actors[1], ready_document, revision, imported(import_tag, interests))
        import_first = round_ % 2 == 0
        first, second, timing = race.run(*((reviewed, manual) if import_first else (manual, reviewed)))
        winner = ok(first)
        conflict(second, revision + 1)
        assert winner["revision"] == revision + 1  # An import increments exactly once.
        assert winner["confirmation"]["status"] == "UNCONFIRMED"
        assert actors[0].get(PROFILE) == winner
        labels = personal_labels(app)
        won, lost = (import_tag, save_tag) if import_first else (save_tag, import_tag)
        assert f"Topic {won}" in labels and f"Topic {lost}" not in labels
        sources = {item["field"]: item for item in winner["origins"]}
        if import_first:
            assert winner["content"]["education"] == records(import_tag)["education"]
            for field in ("education", "courses", "skills", "researchInterests", "customInterestTags",
                          "researchInterestText", "resumeDescription"):
                assert sources[field] == {"field": field, "sourceType": "USER_REVIEWED_DOCUMENT",
                                          "documentId": ready_document}
        else:
            assert winner["content"]["displayName"] == f"Writer {save_tag}"
            assert {item["sourceType"] for item in winner["origins"]} == {"MANUAL"}
        log("rounds", app, "import_vs_manual_save", round_,
            order="import-first" if import_first else "save-first", statuses=[200, 409],
            revisionBefore=revision, revisionAfter=winner["revision"], **timing)


def test_concurrent_confirmation_and_edit_have_a_valid_serial_outcome(app, actors):
    race = Race(app)
    current = actors[0].get(PROFILE)
    ok(save(actors[0], current["revision"], edited(current, "confirm base", ["interest_ml"]))())
    modes = ("edit-first", "confirm-first", "edit-first/already-confirmed", "confirm-first/already-confirmed")
    for round_ in range(ROUNDS):
        mode = modes[round_ % len(modes)]
        current = actors[0].get(PROFILE)
        if mode.endswith("already-confirmed"):
            current = ok(confirm(actors[0], current["revision"])())
        revision, confirmed_at = current["revision"], current["confirmation"]["confirmedAt"]
        edit = save(actors[0], revision, edited(current, f"confirm {round_}", other_interests(current)))
        confirmation = confirm(actors[1], revision)
        if mode.startswith("edit-first"):
            first, second, timing = race.run(edit, confirmation)
            final = ok(first)
            conflict(second, revision + 1)  # Stale confirmation is rejected.
        else:
            first, second, timing = race.run(confirmation, edit)
            confirmed = ok(first)
            assert confirmed["revision"] == revision
            assert confirmed["confirmation"]["confirmedRevision"] == revision
            if confirmed_at is not None:  # Repeated confirmation keeps the original timestamp.
                assert confirmed["confirmation"]["confirmedAt"] == confirmed_at
            final = ok(second)  # Confirmation does not change the revision, so the edit applies.
        # Either serial order: new content never keeps an older revision's confirmation.
        assert final["revision"] == revision + 1
        assert final["confirmation"] == {"status": "UNCONFIRMED", "confirmedRevision": None, "confirmedAt": None}
        assert actors[1].get(PROFILE) == final
        log("rounds", app, "confirmation_vs_edit", round_, order=mode,
            statuses=[first.status_code, second.status_code], revisionBefore=revision,
            revisionAfter=final["revision"], **timing)


def test_duplicate_concurrent_imports_and_stale_retry_never_replay(app, actors, ready_document):
    race = Race(app)
    for round_ in range(ROUNDS):
        current = actors[0].get(PROFILE)
        revision = current["revision"]
        sections = imported(f"replay {round_}", other_interests(current))
        first, second, timing = race.run(apply(actors[0], ready_document, revision, sections),
                                         apply(actors[1], ready_document, revision, sections))
        winner = ok(first)
        conflict(second, revision + 1)
        after = snapshot(app)
        # The client retries its already successful request with the old revision.
        conflict(apply(actors[0], ready_document, revision, sections)(), revision + 1)
        assert snapshot(app) == after
        assert personal_labels(app).count(f"Topic replay {round_}") == 1
        assert actors[1].get(PROFILE) == winner and winner["revision"] == revision + 1
        log("rounds", app, "duplicate_import_and_stale_retry", round_, statuses=[200, 409, 409],
            revisionBefore=revision, revisionAfter=winner["revision"], **timing)


def test_concurrent_privacy_writes_have_one_winner(app, actors):
    race = Race(app)
    for round_ in range(ROUNDS):
        current = actors[0].get(PRIVACY)
        revision = current["revision"]
        choices = (["displayName", "skills"], ["education"]) if round_ % 2 else (["courses"], ["researchInterests"])

        def write(actor, fields):
            return lambda: actor.put(PRIVACY, {"expectedRevision": revision,
                                               "discoverable": not current["discoverable"], "visibleFields": fields})
        first, second, timing = race.run(write(actors[0], choices[0]), write(actors[1], choices[1]))
        winner = ok(first)
        conflict(second, revision + 1)
        assert winner["revision"] == revision + 1 and winner["visibleFields"] == sorted(choices[0])
        assert actors[1].get(PRIVACY) == winner
        log("rounds", app, "privacy_vs_privacy", round_, statuses=[200, 409],
            revisionBefore=revision, revisionAfter=winner["revision"], **timing)


def test_concurrent_opportunity_writes_have_one_winner(app):
    race = Race(app)
    owners = Actor(app, "team@example.test"), Actor(app, "team@example.test")
    created = owners[0].client.post(OPPORTUNITIES, json=opportunity_content(), headers=headers(owners[0].csrf))
    assert created.status_code == 201, created.get_json()
    url = f"{OPPORTUNITIES}/{created.get_json()['id']}"
    for round_ in range(ROUNDS):
        current = owners[0].get(url)
        revision = current["revision"]

        def write(actor, title):
            return lambda: actor.put(url, {"expectedRevision": revision,
                                           "content": deepcopy(current["content"]) | {"title": title}})
        publish = lambda: owners[1].post(url + "/publish", {"expectedRevision": revision})
        if round_ == 0:  # Draft: publication races an edit of the same revision.
            mode, calls = "publish-vs-save", (publish, write(owners[0], "Lost draft edit"))
        else:
            mode, calls = "save-vs-save", (write(owners[round_ % 2], f"Opportunity {round_} first"),
                                           write(owners[1 - round_ % 2], f"Opportunity {round_} second"))
        first, second, timing = race.run(*calls)
        winner = ok(first)
        conflict(second, revision + 1)
        assert winner["revision"] == revision + 1
        assert owners[1].get(url) == winner
        if round_ == 0:
            assert winner["status"] == "PUBLISHED" and winner["content"]["title"] == current["content"]["title"]
        else:
            assert winner["content"]["title"] == f"Opportunity {round_} first"
        log("rounds", app, "opportunity_writes", round_, order=mode, statuses=[200, 409],
            revisionBefore=revision, revisionAfter=winner["revision"], **timing)


# --- Negative control: the same barriers without the lock break the invariant --------------

def test_negative_control_without_the_writer_lock_violates_the_invariant(app, actors, monkeypatch, caplog):
    database = app.extensions["database"]
    original = type(database).transaction

    @contextmanager
    def unlocked(self, *, write=False):
        # Plain BEGIN / no FOR UPDATE, but claim the lock so the guard does not mask the race.
        with original(self, write=False) as session:
            session.info[WRITE_LOCK] = write
            yield session
    monkeypatch.setattr(type(database), "transaction", unlocked)
    current = actors[0].get(PROFILE)
    revision, interests = current["revision"], other_interests(current)

    def content(name):
        # Keep personal tags unchanged so the profile UPDATE is each request's first write.
        return edited(current, f"control {name}", interests) | {
            "customInterestTags": current["content"]["customInterestTags"]}
    writers, passed = {}, set()
    # Both requests must pass their revision check before either writes the profile row.
    both_checked = Barrier(2, timeout=TIMEOUT)

    def on_execute(connection, cursor, statement, parameters, context, executemany):
        thread = current_thread()
        if thread in writers.values() and thread not in passed and statement.startswith("UPDATE talent_profiles"):
            passed.add(thread)
            both_checked.wait()

    results = {}

    def call(name, function):
        results[name] = function()
    event.listen(database.engine, "before_cursor_execute", on_execute)
    try:
        for name, actor in zip(("a", "b"), actors):
            writers[name] = Thread(target=call, name=f"be4-control-{name}",
                                   args=(name, save(actor, revision, content(name))))
        for thread in writers.values():
            thread.start()
        for thread in writers.values():
            thread.join(TIMEOUT)
            assert not thread.is_alive()
    finally:
        event.remove(database.engine, "before_cursor_execute", on_execute)
        monkeypatch.undo()
    statuses = sorted(response.status_code for response in results.values())
    assert passed == set(writers.values()), "both unprotected writers passed the stale revision check"
    assert statuses != [200, 409], "the unprotected interleaving must not satisfy the revision protocol"
    final = actors[0].get(PROFILE)
    lost_update = statuses == [200, 200] and final["revision"] == revision + 1
    assert lost_update or 500 in statuses
    errors = sorted(re.findall(r"failed \((\w+)\)", caplog.text))
    EVIDENCE["controls"].append({"test": "negative_control_unlocked_save_vs_save", **database_info(app),
                                 "statuses": statuses, "revisionBefore": revision,
                                 "revisionAfter": final["revision"], "lostUpdate": lost_update,
                                 "uncontrolledErrors": errors})


# --- Requirement 4: confirmation, no-op save and import retry are distinct ----------------

def test_repeat_confirmation_noop_save_and_repeat_import_are_distinct(app, actors, ready_document):
    actor = actors[0]
    confirmed = baseline(app, actor)
    revision = confirmed["revision"]
    assert ok(confirm(actor, revision)()) == confirmed  # Same revision and original confirmedAt.
    content = deepcopy(confirmed["content"])
    assert ok(save(actor, revision, content)()) == confirmed  # No-op: revision, confirmation, origins kept.
    sections = imported("repeat", ["interest_ml"])
    first = ok(apply(actor, ready_document, revision, sections)())
    assert first["revision"] == revision + 1 and first["confirmation"]["status"] == "UNCONFIRMED"
    stored = snapshot(app)
    conflict(apply(actor, ready_document, revision, sections)(), revision + 1)  # Retry cannot replay.
    assert snapshot(app) == stored
    # An explicit new import of the same values is a new revision, never a silent no-op;
    # identical labels resolve to the existing personal tag.
    labels = sorted(personal_labels(app))
    second = ok(apply(actor, ready_document, first["revision"], sections)())
    assert second["revision"] == first["revision"] + 1
    assert second["content"] == first["content"] and sorted(personal_labels(app)) == labels


# --- Requirement 3: failure during any child write rolls everything back ------------------

SAVE_TABLES = ("talent_profiles", "personal_interest_tags", "personal_interest_tag_details", "profile_interests",
               "profile_skill_details", "profile_text_details", "profile_personal_interests", "profile_origins",
               "profile_component_origins")
FAULTS = ([("save", table) for table in SAVE_TABLES] + [("save", "after-all-writes")]
          + [("import", table) for table in SAVE_TABLES] + [("import", "after-all-writes")]
          + [("confirmation", "talent_profiles"), ("confirmation", "after-all-writes")])


@pytest.mark.parametrize("operation,target", FAULTS, ids=[f"{a}-{b}" for a, b in FAULTS])
def test_failure_during_a_child_write_rolls_back_everything(app, actors, ready_document, monkeypatch,
                                                            operation, target):
    actor = actors[0]
    confirmed = baseline(app, actor)
    revision = confirmed["revision"]
    if operation == "confirmation":
        current = ok(save(actor, revision, edited(confirmed, "pending", ["interest_ml"]))())
        revision = current["revision"]
        request = confirm(actor, revision)
    elif operation == "save":
        current = confirmed
        request = save(actor, revision, edited(confirmed, "fault", []))
    else:
        current = confirmed
        request = apply(actor, ready_document, revision, imported("fault", []))
    before, labels = snapshot(app), sorted(personal_labels(app))
    engine = app.extensions["database"].engine
    written, fired = [], []

    def on_execute(connection, cursor, statement, parameters, context, executemany):
        match = WRITE.match(statement)
        if match is None or current_thread().name != "MainThread":
            return
        if match[1] == target and not fired:
            fired.append(statement.split()[0].upper())
            raise RuntimeError(f"BE-4 injected failure writing {target}")
        written.append(match[1])

    if target == "after-all-writes":
        # Fail in the final serialisation, after every statement has been flushed.
        for module in (profile_routes, document_routes):
            real = module.serialize_profile

            def failing(db, profile, _real=real):
                if written and not fired:
                    fired.append("after-flush")
                    raise RuntimeError("BE-4 injected failure after all writes")
                return _real(db, profile)
            monkeypatch.setattr(module, "serialize_profile", failing)
    event.listen(engine, "before_cursor_execute", on_execute)
    try:
        response = request()
    finally:
        event.remove(engine, "before_cursor_execute", on_execute)
        monkeypatch.undo()
    assert fired, f"{operation} never wrote {target}; the injection point was not exercised"
    assert response.status_code == 500, response.get_json()
    if target == "after-all-writes" and operation != "confirmation":
        assert set(SAVE_TABLES) <= set(written), set(SAVE_TABLES) - set(written)
    # Revision, confirmation, tags, content and provenance are all unchanged.
    assert snapshot(app) == before
    assert sorted(personal_labels(app)) == labels
    assert actor.get(PROFILE) == current
    # Nothing is left locked or half-written: the identical request now succeeds once.
    retried = ok(request())
    expected = revision if operation == "confirmation" else revision + 1
    assert retried["revision"] == expected
    EVIDENCE["faults"].append({"test": f"{operation}:{target}", **database_info(app), "status": 500,
                               "injectedAt": fired[0], "writesBeforeFailure": len(written),
                               "tablesWrittenBeforeFailure": sorted(set(written)),
                               "rolledBack": True, "retryStatus": 200})

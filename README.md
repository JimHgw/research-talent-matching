# Research Talent and Opportunity Matching

A full-stack platform for explainable, privacy-aware matching between research talent and research opportunities. It combines document ingestion, user-reviewed profiles, requirement-level semantic scoring and research-team discovery in a single workflow.

Developed collaboratively for UNSW COMP3900. **I am Guangwei Hu (Jim), a contributor to core backend engineering, cross-feature integration and delivery.** My work connects private document processing with versioned profile confirmation, testable application services and failure-recovery verification. I also contributed through merge-request review, API integration, Docker deployment and configuration, and team demonstrations.

## Engineering contributions

- **Delivered the core document-to-profile backend:** private PDF/DOCX ingestion, background extraction, reviewed imports and explicit profile confirmation, with ownership and revision checks.
- **Strengthened data integrity and maintainability:** extracted import, save and confirmation services while preserving partial updates, provenance, canonical no-op behaviour and transaction rollback.
- **Hardened extraction and asynchronous processing:** resolved complex document-layout issues and verified worker recovery, competing claims and stale-result rejection using independent processes and fault injection.
- **Established executable API contracts:** added schema and error-semantic regression checks for revision conflicts, processing states and profile operations, with 115 passing cases across four dedicated suites.

## Shared delivery outcomes

- **Co-delivered the integrated matching platform**, contributing through cross-module review, frontend/backend debugging and integration across profile, document, opportunity and matching workflows.
- **Supported consistent API and permission boundaries** through interface work, regression testing and review of the interactions between confirmation, discovery consent and downstream matching.
- **Contributed to deployment and release readiness** through Git-based collaboration, MR review, Docker configuration and deployment, demonstrations and team coordination. I work confidently with Git and understand the project's GitLab CI test, acceptance and build gates.

[Implementation and evidence](docs/portfolio/MY_CONTRIBUTIONS.md) · [Architecture and design](docs/portfolio/ARCHITECTURE.md)

## Application capabilities

| Area | Behaviour |
| --- | --- |
| Document review | Extract suggestions from PDF/DOCX documents, review and edit them, then import selected sections. |
| Confirmed profiles | Versioned education, courses, skills, interests, research experience and outputs, with explicit confirmation. |
| Research opportunities | Publish requirements, search and filter opportunities, and manage deadlines and source links. |
| Explainable matching | Combine structured evidence with local multilingual semantic scoring for individual requirements. |
| Privacy | Keep original documents private and apply discovery consent and field visibility before team matching. |
| Saved work | Save opportunities and shortlist talent with current permission and matching checks. |

The platform combines these capabilities through shared API contracts, revision-aware workflows and permission-aware data access.

## Technology

| Layer | Stack |
| --- | --- |
| Frontend | React 19, Vite, JavaScript/JSX, with TypeScript at selected API and review boundaries |
| Backend | Python, Flask, SQLAlchemy, JSON Schema validation |
| Persistence | MySQL 8.4 in Docker; isolated SQLite fixtures for local regression tests |
| Document processing | pypdf, python-docx, a separate database-backed worker |
| Semantic scoring | Local multilingual MiniLM inference with ONNX Runtime and tokenizers |
| Runtime | Docker Compose, Nginx, Gunicorn |
| Engineering | pytest, Node/jsdom integration tests, Git and GitLab CI |

## Run locally

From the repository root, with Docker Engine and Compose running:

```sh
docker compose up --build --detach --wait --wait-timeout 180 --force-recreate
docker compose ps
```

Open `http://127.0.0.1:5173` with the default port configuration. Compose starts the frontend, backend, MySQL and document worker. The first build downloads dependencies and the pinned local model artifacts.

Default local startup works without creating a root `.env`. Use `.env.example` when customising ports or SMTP. Email registration and email password reset require SMTP configuration. For a local demonstration, provision accounts with hidden password prompts:

```sh
docker compose exec backend python -m flask --app backend.app provision-user --email talent@example.test --display-name "Demo Talent" --role TALENT
docker compose exec backend python -m flask --app backend.app provision-user --email team@example.test --display-name "Demo Team" --role RESEARCH_TEAM
```

[Windows instructions](README_BEFORE_START.md) · [macOS and Linux instructions](docs/docker-integration.md) · [Native development](backend/README.md)

## Verification

The four regression suites added in my Sprint 3 work contain **115 cases** covering API contracts, reviewed imports, profile operations and worker recovery. A focused run against an isolated copy of the 22 November 2026 checkout passed all 115 cases with SQLite. This run covers those suites; Docker, MySQL, real-model and frontend integration acceptance have separate checks.

After installing the development dependencies, run the same focused suites from the repository root:

```sh
python -m pytest backend/tests/test_sprint3_be1.py backend/tests/test_sprint3_be2.py backend/tests/test_sprint3_be3.py backend/tests/test_sprint3_be6.py -q
```

The team's broader acceptance evidence is documented in [BE-10 release verification](docs/testing/be10-release.md). For frontend type checking, tests, formatting and a production build, use:

```sh
python scripts/dev.py frontend check
```

## Design details

- **Extraction, import and confirmation are separate actions.** Machine-generated suggestions require review; importing them leaves the profile unconfirmed.
- **Writes use explicit revisions.** Conflicting updates return `409 / REVISION_CONFLICT` and preserve stored data.
- **Matching uses permitted evidence.** Team discovery requires current confirmation and discovery consent; hidden fields do not become matching inputs.
- **Semantic relevance has a limited meaning.** Similar text can contribute to a score, while structured evidence statuses continue to distinguish confirmed support, gaps and missing evidence.

[Document workflow](docs/us09-documents.md) · [API contracts](docs/api/README.md) · [Requirement scoring](docs/semantic-matching.md)

[Project credits](docs/portfolio/CREDITS.md) · [Source history](docs/portfolio/SOURCE_HISTORY.md)

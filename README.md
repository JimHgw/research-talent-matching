# project

For Sprint 3 architecture and development guidance, see the [Sprint 3 development guide](docs/README_SPRINT_3_DEVELOP_EN.md).

## Install, configure and start

- [Windows Docker run guide](README_BEFORE_START.md)
- [macOS and Linux Docker run guide](docs/docker-integration.md)

The database now uses **MySQL 8.4 + SQLAlchemy**. Start a new environment with `docker compose up --build --detach --wait --wait-timeout 180`.
If you do not need the old data, start the services directly. **To preserve existing SQLite data, follow the [MySQL migration guide](docs/mysql-migration.md) to back up and import it before starting the updated services.**

To run the application on your Windows computer and let people on other networks access it through a temporary URL,
see the [public access guide](docs/public-sharing.md), or start Docker Desktop and run
`powershell -NoProfile -ExecutionPolicy Bypass -File .\share.ps1`.

## Testing and evaluation

Install the development dependencies and activate the project virtual environment.
Run these commands from the repository root. [Development setup](backend/README.md#first-step-after-cloning-install-the-development-environment)

```sh
python -m pytest -q -rs --require-frontend
python scripts/dev.py frontend check
python scripts/evaluate-document-extraction.py
```

- Backend and frontend integration, model checks, and MySQL and Docker acceptance. [BE-10 release acceptance](docs/testing/be10-release.md)
- Synthetic CV and transcript fixtures, field-level metrics and error examples. [Document extraction evaluation](docs/testing/document-extraction-evaluation.md)
- Verified matching results on labelled synthetic profiles. [Matching evaluation](docs/testing/us13-evaluation.md)
- Commands for checking a running Docker installation and testing restart persistence. [Docker verification](docs/docker-integration.md#verify-the-complete-path)

"""Application factory and administrative commands. No data is seeded on startup."""

import json
import os
import secrets
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import click
from argon2 import PasswordHasher
from flask import Flask, g, jsonify
from sqlalchemy import delete, select
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .db.database import Database
from .db.migration import register_migration_command
from .db.release import check_schema, register_release_commands
from .db.models import (AuthSession, LoginAttempt, PasswordResetAttempt, PasswordResetCode,
                        RegistrationAttempt, RegistrationCode, utcnow)
from .features.auth.routes import auth, provision_user
from .features.auth.registration import registration
from .features.auth.mail import send_password_reset_code, send_registration_code
from .features.auth.reset import password_reset
from .features.profile.routes import profiles, seed_tags
from .features.opportunities.routes import opportunities
from .shared.paths import ROOT
from .shared.validation import ApiError
from .features.matching.routes import matching
from .features.matching.semantic_runtime import configure_semantic
from .features.privacy.routes import privacy
from .features.documents.routes import documents
from .features.documents.worker import process_next_document
from .features.collections import collections

from time import sleep



def create_app(config=None):
    app = Flask(__name__)
    cookie_secure = os.getenv("COOKIE_SECURE", "true").lower()
    if cookie_secure not in ("true", "false"):
        raise ValueError("COOKIE_SECURE must be true or false.")
    app.config.from_mapping(
        DATABASE_URL=os.getenv("DATABASE_URL") or URL.create(
            "mysql+pymysql", username=os.getenv("MYSQL_USER", "banana"),
            password=os.getenv("MYSQL_PASSWORD", "banana_local_password"),
            host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "h18abanana"),
        ),
        ALLOWED_ORIGINS=os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(","),
        COOKIE_SECURE=cookie_secure == "true",
        SESSION_TTL=86400, ANONYMOUS_TTL=3600, LOGIN_WINDOW=900,
        LOGIN_EMAIL_LIMIT=10, LOGIN_IP_LIMIT=30, MAX_CONTENT_LENGTH=4 * 1024 * 1024,
        REGISTER_CODE_TTL=600, REGISTER_CODE_ATTEMPTS=5, REGISTER_RESEND_INTERVAL=60,
        REGISTER_WINDOW=3600, REGISTER_EMAIL_LIMIT=5, REGISTER_IP_LIMIT=20,
        RESET_CODE_TTL=600, RESET_CODE_ATTEMPTS=5, RESET_RESEND_INTERVAL=60,
        RESET_WINDOW=3600, RESET_EMAIL_LIMIT=5, RESET_IP_LIMIT=20,
        SMTP_HOST=os.getenv("SMTP_HOST", ""), SMTP_PORT=os.getenv("SMTP_PORT", "587"),
        SMTP_FROM=os.getenv("SMTP_FROM", ""), SMTP_SECURITY=os.getenv("SMTP_SECURITY", "starttls"),
        SMTP_USERNAME=os.getenv("SMTP_USERNAME", ""), SMTP_PASSWORD=os.getenv("SMTP_PASSWORD", ""),
        SMTP_TIMEOUT=os.getenv("SMTP_TIMEOUT", "10"),
        DOCUMENT_STORAGE_DIR=os.getenv("DOCUMENT_STORAGE_DIR", str(ROOT / "data" / "documents"),),
        DOCUMENT_PROCESSING_TIMEOUT=os.getenv("DOCUMENT_PROCESSING_TIMEOUT", "300"),
        DOCUMENT_PROCESSING_MAX_ATTEMPTS=os.getenv("DOCUMENT_PROCESSING_MAX_ATTEMPTS", "3"),
        SEMANTIC_MATCHING_ENABLED=os.getenv("SEMANTIC_MATCHING_ENABLED", "true"),
        SEMANTIC_MATCHING_WEIGHT=os.getenv("SEMANTIC_MATCHING_WEIGHT", "0.3"),
        SEMANTIC_MODEL_DIR=os.getenv("SEMANTIC_MODEL_DIR", str(ROOT / "data/semantic/model")),
    )
    app.config.update(config or {})
    configure_semantic(app)
    for name in ("DOCUMENT_PROCESSING_TIMEOUT", "DOCUMENT_PROCESSING_MAX_ATTEMPTS"):
        try:
            app.config[name] = int(app.config[name])
        except (ValueError, TypeError):
            raise ValueError(f"{name} must be a positive integer.") from None
        if app.config[name] < 1:
            raise ValueError(f"{name} must be a positive integer.")
    origins = {origin.strip() for origin in app.config["ALLOWED_ORIGINS"]}
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path
                or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("ALLOWED_ORIGINS must contain exact HTTP(S) origins without paths.")
    app.config["ALLOWED_ORIGINS"] = origins
    app.extensions["database"] = Database(app.config["DATABASE_URL"])
    register_migration_command(app)
    register_release_commands(app)
    app.extensions["password_hasher"] = PasswordHasher()
    app.extensions["dummy_hash"] = app.extensions["password_hasher"].hash(secrets.token_urlsafe(32))
    app.extensions["registration_mailer"] = send_registration_code
    app.extensions["password_reset_mailer"] = send_password_reset_code
    app.register_blueprint(auth)
    app.register_blueprint(registration)
    app.register_blueprint(password_reset)
    app.register_blueprint(profiles)
    app.register_blueprint(opportunities)
    app.register_blueprint(matching)
    app.register_blueprint(privacy)
    app.register_blueprint(documents)
    app.register_blueprint(collections)

    @app.get("/healthz")
    def health():
        """Read-only container readiness check; never allocate a user session."""
        if not app.extensions["schema_ready"]:
            return jsonify(status="unavailable"), 503
        try:
            with app.extensions["database"].transaction() as db:
                db.execute(select(1))
        except (SQLAlchemyError, ValueError):
            return jsonify(status="unavailable"), 503
        return jsonify(status="ok")

    @app.before_request
    def request_id():
        g.request_id = secrets.token_hex(16)

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Request-Id"] = g.request_id
        return response

    @app.errorhandler(ApiError)
    def api_error(error):
        value = {"code": error.code, "message": error.message, "fieldErrors": error.fields}
        if error.revision is not None:
            value["currentRevision"] = error.revision
        return jsonify(error=value, requestId=g.request_id), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        codes = {400: "BAD_REQUEST", 404: "NOT_FOUND", 405: "BAD_REQUEST",
                 413: "BAD_REQUEST", 415: "UNSUPPORTED_MEDIA_TYPE"}
        response, status = api_error(ApiError(error.code, codes.get(error.code, "BAD_REQUEST"), error.name))
        if error.code == 405:
            # Keep HTTP method discovery while using the contract's existing error codes.
            response.headers["Allow"] = ", ".join(error.valid_methods or [])
        return response, status

    @app.errorhandler(Exception)
    def internal_error(error):
        # Avoid logging SQL parameters, passwords, cookies or submitted profile content.
        app.logger.error("Request %s failed (%s)", g.request_id, type(error).__name__)
        return api_error(ApiError(500, "INTERNAL_ERROR", "The service could not complete this request."))

    @app.cli.command("init-db")
    def init_db():
        """Create missing tables. This does not migrate existing tables."""
        app.extensions["database"].initialise()
        click.echo("Database tables initialised.")

    @app.cli.command("seed-tags")
    @click.option("--file", "filename", type=click.Path(exists=True, dir_okay=False),
                  default=str(ROOT / "docs/api/examples/tags.json"), show_default=True)
    def seed_command(filename):
        """Load the controlled vocabulary explicitly (idempotent for identical data)."""
        try:
            seed_tags(json.loads(Path(filename).read_text(encoding="utf-8"))["items"])
        except (ValueError, KeyError, ApiError) as error:
            raise click.ClickException(str(error)) from None
        click.echo("Tags seeded.")

    @app.cli.command("upgrade-opportunity-search")
    def upgrade_opportunity_search_command():
        """Add nullable US-14 opportunity fields without changing existing records."""
        from .db.opportunity_upgrade import upgrade_opportunity_search
        try:
            changed = upgrade_opportunity_search(app.extensions["database"])
        except ValueError as error:
            raise click.ClickException(str(error)) from None
        click.echo("Opportunity search storage upgraded." if changed else "Opportunity search storage is current.")

    @app.cli.command("upgrade-query-indexes")
    def upgrade_query_indexes_command():
        """Add BE-8 indexes to existing opportunity tables, without changing rows."""
        from .db.query_upgrade import upgrade_query_indexes
        try:
            changed = upgrade_query_indexes(app.extensions["database"])
        except ValueError as error:
            raise click.ClickException(str(error)) from None
        click.echo("Query indexes upgraded." if changed else "Query indexes are current.")

    @app.cli.command("provision-user")
    @click.option("--email", required=True)
    @click.option("--display-name", required=True)
    @click.option("--role", type=click.Choice(["TALENT", "RESEARCH_TEAM"]), required=True)
    def provision_command(email, display_name, role):
        """Create a provisioned account; password input is hidden and never a CLI argument."""
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
        try:
            user_id = provision_user(email, password, display_name, role)
        except (ValueError, ApiError) as error:
            raise click.ClickException(str(error)) from None
        click.echo(f"Created {role} account {user_id}.")

    @app.cli.command("prune-sessions")
    def prune_sessions():
        """Remove expired session/code data and old authentication attempt counters."""
        now = utcnow()
        with app.extensions["database"].transaction(write=True) as db:
            db.execute(delete(AuthSession).where(
                (AuthSession.expires_at <= now) | AuthSession.revoked_at.is_not(None)))
            db.execute(delete(LoginAttempt).where(
                LoginAttempt.attempted_at < now - timedelta(seconds=app.config["LOGIN_WINDOW"])))
            db.execute(delete(RegistrationCode).where(RegistrationCode.expires_at <= now))
            db.execute(delete(RegistrationAttempt).where(
                RegistrationAttempt.attempted_at < now - timedelta(seconds=app.config["REGISTER_WINDOW"])))
            db.execute(delete(PasswordResetCode).where(PasswordResetCode.expires_at <= now))
            db.execute(delete(PasswordResetAttempt).where(
                PasswordResetAttempt.attempted_at < now - timedelta(seconds=app.config["RESET_WINDOW"])))
        click.echo("Expired session data pruned.")

    @app.cli.command("process-documents")
    @click.option(
        "--once",
        is_flag=True,
        help="Attempt one queued document and exit.",
    )
    def process_documents(once):
        # Workers never repair schema while processing; use the release command first.
        try:
            check_schema(app.extensions["database"])
        except (ValueError, SQLAlchemyError):
            raise click.ClickException("Worker schema is incompatible or unavailable; run prepare-db before starting.") from None
        app.logger.setLevel("INFO")
        if once:
            processed = process_next_document()

            if processed:
                click.echo("Document processing attempt finished.")
            else:
                click.echo("No queued document.")

            return

        click.echo("Document worker started. Press Ctrl+C to stop.")

        while True:
            processed = process_next_document()

            if not processed:
                sleep(1)

    # Validate once per application process, including native API startup. Keep
    # administrative commands available when an old/absent schema needs repair.
    app.extensions["schema_ready"] = False
    try:
        check_schema(app.extensions["database"])
    except (SQLAlchemyError, ValueError):
        pass
    else:
        app.extensions["schema_ready"] = True
    return app

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
from sqlalchemy import delete
from werkzeug.exceptions import HTTPException

from .db.database import Database
from .db.models import AuthSession, LoginAttempt, utcnow
from .features.auth.routes import auth, provision_user
from .features.profile.routes import profiles, seed_tags
from .features.opportunities.routes import opportunities
from .shared.paths import ROOT
from .shared.validation import ApiError
from .features.matching.routes import matching


def create_app(config=None):
    app = Flask(__name__)
    cookie_secure = os.getenv("COOKIE_SECURE", "true").lower()
    if cookie_secure not in ("true", "false"):
        raise ValueError("COOKIE_SECURE must be true or false.")
    app.config.from_mapping(
        DATABASE_URL=os.getenv("DATABASE_URL", "sqlite:///data/h18abanana.db"),
        ALLOWED_ORIGINS=os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(","),
        COOKIE_SECURE=cookie_secure == "true",
        SESSION_TTL=86400, ANONYMOUS_TTL=3600, LOGIN_WINDOW=900,
        LOGIN_EMAIL_LIMIT=10, LOGIN_IP_LIMIT=30, MAX_CONTENT_LENGTH=4 * 1024 * 1024,
    )
    app.config.update(config or {})
    origins = {origin.strip() for origin in app.config["ALLOWED_ORIGINS"]}
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path
                or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("ALLOWED_ORIGINS must contain exact HTTP(S) origins without paths.")
    app.config["ALLOWED_ORIGINS"] = origins
    app.extensions["database"] = Database(app.config["DATABASE_URL"])
    app.extensions["password_hasher"] = PasswordHasher()
    app.extensions["dummy_hash"] = app.extensions["password_hasher"].hash(secrets.token_urlsafe(32))
    app.register_blueprint(auth)
    app.register_blueprint(profiles)
    app.register_blueprint(opportunities)
    app.register_blueprint(matching)

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
        """Remove expired/revoked sessions and old login-attempt counters."""
        now = utcnow()
        with app.extensions["database"].transaction(write=True) as db:
            db.execute(delete(AuthSession).where(
                (AuthSession.expires_at <= now) | AuthSession.revoked_at.is_not(None)))
            db.execute(delete(LoginAttempt).where(
                LoginAttempt.attempted_at < now - timedelta(seconds=app.config["LOGIN_WINDOW"])))
        click.echo("Expired session data pruned.")

    return app

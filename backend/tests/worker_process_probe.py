"""Subprocess-only test driver for BE-6; never used by the application."""

from contextlib import redirect_stdout
from io import StringIO
import json
import logging
import os
from queue import Empty, Queue
import signal
import subprocess
import sys
from threading import Thread

import pytest

from backend.src.app import create_app
from backend.src.features.documents import worker
from backend.src.shared.paths import ROOT


TIMEOUT = 30


class Probe:
    """Start an independent interpreter with controlled test communication."""

    def __init__(self, app, directory, action, number):
        self.log_path = directory / f"worker-{number}.log"
        self.log = self.log_path.open("w", encoding="utf-8")
        self.messages = Queue()
        self.worker_pid = None
        self.process = subprocess.Popen(
            [sys.executable, "-B", "-m", "backend.tests.worker_process_probe"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            encoding="utf-8",
            env={
                **os.environ,
                "PYTHONPATH": str(ROOT),
                "PYTHONDONTWRITEBYTECODE": "1",
                "FLASK_SKIP_DOTENV": "1",
            },
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        def read():
            try:
                for line in self.process.stdout:
                    self.messages.put(line)
            finally:
                self.messages.put(None)

        self.reader = Thread(target=read, daemon=True)
        self.reader.start()
        self.send({
            "action": action,
            "config": {
                "TESTING": True,
                "DATABASE_URL": app.config["DATABASE_URL"],
                "DOCUMENT_STORAGE_DIR": app.config["DOCUMENT_STORAGE_DIR"],
                "DOCUMENT_PROCESSING_TIMEOUT": app.config[
                    "DOCUMENT_PROCESSING_TIMEOUT"
                ],
                "DOCUMENT_PROCESSING_MAX_ATTEMPTS": app.config[
                    "DOCUMENT_PROCESSING_MAX_ATTEMPTS"
                ],
                "SEMANTIC_MATCHING_ENABLED": False,
                "COOKIE_SECURE": False,
            },
        })

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def receive(self, expected):
        try:
            line = self.messages.get(timeout=TIMEOUT)
        except Empty:
            pytest.fail(
                f"Worker timed out waiting for {expected}; "
                f"{self.log_path.read_text(encoding='utf-8')}"
            )

        assert line is not None, self.log_path.read_text(encoding="utf-8")
        message = json.loads(line)
        assert message["event"] == expected, message

        if expected == "ready":
            self.worker_pid = message["pid"]
            assert isinstance(self.worker_pid, int) and self.worker_pid > 0
        else:
            assert message["pid"] == self.worker_pid

        return message

    def finish(self):
        message = self.receive("done")
        assert self.process.wait(timeout=TIMEOUT) == 0, (
            self.log_path.read_text(encoding="utf-8")
        )
        return message

    def stop(self):
        if self.process.poll() is None:
            # Windows may use a launcher whose PID differs from the interpreter.
            if self.worker_pid is None:
                self.process.terminate()
            else:
                try:
                    os.kill(self.worker_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def close(self):
        self.stop()
        self.reader.join(timeout=1)
        self.process.stdin.close()
        self.process.stdout.close()
        self.log.close()


def emit(event, **values):
    print(
        json.dumps({"event": event, "pid": os.getpid(), **values}),
        file=sys.__stdout__,
        flush=True,
    )


def command():
    value = sys.stdin.readline()
    if not value:
        raise RuntimeError("Test controller disconnected.")
    return json.loads(value)


def main():
    request = command()
    app = create_app(request["config"])
    app.logger.setLevel(logging.INFO)
    action = request["action"]

    emit("ready")
    if command() != "go":
        raise RuntimeError("Expected the test start barrier.")

    try:
        with app.app_context():
            if action == "claim":
                job = worker.claim_next_document()
                emit(
                    "done",
                    claimed=job is not None,
                    document_id=job["document_id"] if job else None,
                )
                return

            if action == "hold":
                parse = worker.extract_document_text

                def blocked_parse(path, media_type):
                    # PROCESSING has committed before this stop point.
                    emit("parsing")
                    decision = command()

                    if decision == "failure":
                        raise RuntimeError("Synthetic private parser failure.")
                    if decision != "success":
                        raise RuntimeError("Unexpected test release command.")

                    return parse(path, media_type)

                worker.extract_document_text = blocked_parse

            if action not in ("hold", "process", "daemon"):
                raise RuntimeError("Unknown test operation.")

            output = StringIO()
            with redirect_stdout(output):
                app.cli.main(
                    args=["process-documents"] + (
                        [] if action == "daemon" else ["--once"]
                    ),
                    standalone_mode=False,
                )

            emit(
                "done",
                cli_finished=(
                    "Document processing attempt finished." in output.getvalue()
                ),
            )
    finally:
        app.extensions["database"].engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        emit("error", error_type=type(error).__name__)
        raise SystemExit(1)

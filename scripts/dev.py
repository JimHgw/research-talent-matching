"""Development tools for installed Python/Node; no system package installation."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SETUP_HINT = "Run sh setup.sh (macOS/Linux) or setup.ps1 (Windows) from the repository root."


def run(args, *, cwd, env, capture=False):
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, env=env, check=True,
        text=True, encoding="utf-8", errors="replace", capture_output=capture,
    )
    return result.stdout.strip() if capture else None


def setup(root=ROOT):
    if sys.version_info < (3, 12):
        raise RuntimeError("Python 3.12 or newer is required. Set PYTHON to a compatible interpreter.")
    root = Path(root).resolve()
    env = os.environ.copy()
    node = shutil.which(env.get("NODE_BINARY") or "node")
    if not node:
        raise RuntimeError("Install Node.js 22.12+ with npm and add it to PATH, then rerun setup.")
    # Preserve the PATH entry of version-manager symlinks (e.g. nvm/Homebrew).
    node = os.path.abspath(node)
    env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    env["NODE_BINARY"] = node
    version = run([node, "--version"], cwd=root, env=env, capture=True)
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if not match or tuple(map(int, match.groups())) < (22, 12, 0):
        raise RuntimeError("Node.js 22.12 or newer is required.")
    npm = shutil.which("npm", path=env["PATH"])
    if not npm:
        raise RuntimeError("npm is missing. Install Node.js with npm, then rerun setup.")
    frontend_dir = root / "frontend"
    package = json.loads((frontend_dir / "package.json").read_text(encoding="utf-8"))
    manager = package.get("packageManager", "")
    if not re.fullmatch(r"pnpm@\d+\.\d+\.\d+", manager):
        raise RuntimeError("frontend/package.json must pin packageManager to pnpm@X.Y.Z.")

    venv = root / ".venv"
    python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    print("[1/5] Preparing the Python virtual environment...", flush=True)
    if not venv.exists():
        run([sys.executable, "-m", "venv", venv], cwd=root, env=env)
    if not python.is_file():
        raise RuntimeError("The existing .venv is incompatible or broken. Rename it and rerun setup; do not copy virtual environments between operating systems.")
    run([python, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"], cwd=root, env=env)
    print("[2/5] Installing backend dependencies...", flush=True)
    run([python, "-m", "pip", "install", "-r", root / "backend/requirements-dev.txt"], cwd=root, env=env)
    run([python, "-m", "pip", "check"], cwd=root, env=env)

    print("[3/5] Preparing the pinned project-local pnpm...", flush=True)
    tools = venv / "node-tools"
    pnpm = tools / "node_modules/pnpm/bin/pnpm.cjs"
    installed = None
    if pnpm.is_file():
        installed = run([node, pnpm, "--version"], cwd=root, env=env, capture=True)
    if installed != manager.removeprefix("pnpm@"):
        # npm is a script on POSIX; Windows ships its JS entry point.
        npm_command = [npm]
        if sys.platform == "win32":
            npm_cli = Path(npm).parent / "node_modules/npm/bin/npm-cli.js"
            if not npm_cli.is_file():
                raise RuntimeError("Cannot locate npm-cli.js; use the Windows setup.ps1 entry point.")
            npm_command = [node, npm_cli]
        run([*npm_command, "install", "--prefix", tools, "--no-audit", "--no-fund",
             "--ignore-scripts", "--package-lock=false", manager], cwd=root, env=env)
    if run([node, pnpm, "--version"], cwd=root, env=env, capture=True) != manager.removeprefix("pnpm@"):
        raise RuntimeError("The installed pnpm version does not match frontend/package.json.")

    print("[4/5] Installing frontend dependencies from the lockfile...", flush=True)
    env["CI"] = "true"
    run([node, pnpm, "install", "--frozen-lockfile"], cwd=frontend_dir, env=env)
    (venv / "toolchain.json").write_text(
        json.dumps({"node": node, "pnpm": str(pnpm)}, indent=2) + "\n", encoding="utf-8",
    )
    print("[5/5] Verifying backend, frontend and required real HTTP integration...", flush=True)
    run([python, "-m", "pytest", "-q", "--require-frontend"], cwd=root, env=env)
    run([node, pnpm, "test"], cwd=frontend_dir, env=env)
    print("Setup complete. Dependencies are installed and tests passed.", flush=True)
    print("Follow backend/README.md to initialise your database and start both services.")


def frontend(args, root=ROOT):
    root = Path(root).resolve()
    try:
        config = json.loads((root / ".venv/toolchain.json").read_text(encoding="utf-8-sig"))
        node, pnpm = config["node"], config["pnpm"]
        if any(not isinstance(path, str) or not Path(path).is_absolute() or not Path(path).is_file()
               for path in (node, pnpm)):
            raise ValueError("missing executable")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError("The saved toolchain is unavailable. " + SETUP_HINT) from error
    env = os.environ.copy()
    env["PATH"] = str(Path(node).parent) + os.pathsep + env.get("PATH", "")
    run([node, pnpm, *args], cwd=root / "frontend", env=env)


def main():
    try:
        if sys.argv[1:] == ["setup"]:
            setup()
        elif sys.argv[1:2] == ["frontend"]:
            frontend(sys.argv[2:])
        else:
            raise RuntimeError("Usage: python scripts/dev.py setup | frontend [pnpm arguments]")
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return error.returncode if isinstance(error, subprocess.CalledProcessError) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

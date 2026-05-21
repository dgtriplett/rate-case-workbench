"""Databricks Job task: build the React/Vite frontend on Databricks compute.

Reads source from the workspace path, runs `npm install` + `npm run build`,
and writes the resulting `dist/` back into the workspace so the app deploy
picks it up.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

WORKSPACE_FRONTEND = Path(
    os.environ.get(
        "RCW_FRONTEND_SRC",
        "/Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench/frontend",
    )
)
WORK_DIR = Path(os.environ.get("RCW_BUILD_DIR", "/tmp/rcw-frontend-build"))


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> None:
    print(f"$ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=check)


def main() -> None:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR, ignore_errors=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print(f"==> copy source {WORKSPACE_FRONTEND} → {WORK_DIR}", flush=True)
    # Use rsync to handle workspace-file metadata gracefully
    run(["rsync", "-rL", "--no-perms", "--no-owner", "--no-group",
         "--exclude=node_modules", "--exclude=dist", "--exclude=.vite",
         f"{WORKSPACE_FRONTEND}/", f"{WORK_DIR}/"])

    # Install Node via nodeenv (no sudo required, works on serverless compute)
    node_root = Path("/tmp/rcw-node-env")
    node_bin = node_root / "bin"
    npm_bin = node_bin / "npm"
    if not npm_bin.exists():
        print("==> installing node via nodeenv", flush=True)
        run([sys.executable, "-m", "pip", "install", "--quiet", "nodeenv"])
        run([
            sys.executable, "-m", "nodeenv",
            "--node=20.18.1",
            "--prebuilt",
            "--without-ssl",
            str(node_root),
        ])
    env = os.environ.copy()
    env["PATH"] = f"{node_bin}:{env.get('PATH','')}"
    print(f"==> using node from {node_bin}", flush=True)
    subprocess.run([str(node_bin / "node"), "--version"], check=True, env=env)
    subprocess.run([str(npm_bin), "--version"], check=True, env=env)

    print("==> npm install", flush=True)
    subprocess.run([str(npm_bin), "install", "--no-audit", "--no-fund"], cwd=str(WORK_DIR), check=True, env=env)
    print("==> npm run build", flush=True)
    subprocess.run([str(npm_bin), "run", "build"], cwd=str(WORK_DIR), check=True, env=env)

    dist_src = WORK_DIR / "dist"
    dist_dst = WORKSPACE_FRONTEND / "dist"
    if not dist_src.exists():
        raise SystemExit(f"build produced no dist/: {dist_src}")

    print(f"==> sync {dist_src} → {dist_dst}", flush=True)
    dist_dst.mkdir(parents=True, exist_ok=True)
    run(["rsync", "-rL", "--no-perms", "--no-owner", "--no-group", "--delete",
         f"{dist_src}/", f"{dist_dst}/"])

    files = sorted(p.name for p in dist_dst.rglob("*") if p.is_file())
    print(f"==> wrote {len(files)} files; first 10: {files[:10]}", flush=True)


if __name__ == "__main__":
    main()

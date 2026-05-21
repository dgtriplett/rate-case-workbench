#!/bin/bash
set -euo pipefail
# Builds the React/Vite frontend inside Databricks compute.
# Run as a Databricks Job (notebook task) — the workspace mounts source under
# /Workspace and we write dist/ back to the workspace path used by the app.

SRC=/Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench/frontend
DEST=/local_disk0/rcw-frontend

echo "==> Copying source to local_disk0 for fast npm operations"
mkdir -p "$DEST"
cp -R "$SRC"/* "$DEST"/
cd "$DEST"

echo "==> Installing node (using DBR-provided node if available)"
which node && node --version || (
  echo "Installing node 20 from nodesource"
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y nodejs
)

echo "==> npm install"
npm ci --no-audit --no-fund || npm install --no-audit --no-fund

echo "==> npm run build"
npm run build

echo "==> Copying dist back to workspace"
mkdir -p "$SRC/dist"
rsync -a --delete "$DEST/dist/" "$SRC/dist/"

echo "==> Done. Files at $SRC/dist:"
ls -la "$SRC/dist" | head -20

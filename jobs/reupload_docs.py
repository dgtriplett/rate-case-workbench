"""Re-upload all documents from the seed manifest to UC Volume.

Reads ``seed/output/manifest.json`` and pushes each ``doc.content`` to the
corresponding ``doc.volume_path``. Idempotent (overwrite=True).

Used as a one-off when an earlier ``seed/generate.py`` run produced the
manifest but failed mid-upload to UC Volume (e.g. the ``'bytes' has no
attribute 'seekable'`` issue).
"""
from __future__ import annotations

import io
import json
import logging
import os
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")
log = logging.getLogger("reupload")


def main() -> int:
    try:
        root = Path(__file__).resolve().parent.parent
    except NameError:
        root = Path(
            os.environ.get(
                "RCW_PROJECT_ROOT",
                "/Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench",
            )
        )

    manifest_path = root / "seed" / "output" / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"manifest not found at {manifest_path}")
    manifest = json.loads(manifest_path.read_text())

    wc = WorkspaceClient()
    n_ok = n_skip = n_err = 0
    for doc in manifest.get("documents", []):
        vp = doc.get("volume_path")
        content = doc.get("content")
        if not vp or not content:
            n_skip += 1
            continue
        parent = vp.rsplit("/", 1)[0]
        try:
            wc.files.create_directory(parent)
        except Exception:
            pass
        stream = io.BytesIO(content.encode("utf-8"))
        try:
            wc.files.upload(file_path=vp, contents=stream, overwrite=True)
            n_ok += 1
            log.info("uploaded %s (%d bytes)", vp, len(content))
        except Exception as e:
            n_err += 1
            log.warning("FAILED %s: %s", vp, e)
    log.info("done — ok=%d skip=%d err=%d", n_ok, n_skip, n_err)
    return 0


if __name__ == "__main__":
    rc = main()
    if rc:
        raise SystemExit(rc)

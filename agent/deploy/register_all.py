"""Convenience entry point — register all 4 agents in one go."""
from __future__ import annotations

import logging
import sys

from .config import AGENTS
from .register import register_agent

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")


def main() -> int:
    for cfg in AGENTS:
        try:
            uri = register_agent(cfg)
            log.info("OK %s → %s", cfg.name, uri)
        except Exception as e:
            log.exception("Failed to register %s: %s", cfg.name, e)
            return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

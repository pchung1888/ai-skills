"""Locate the canonical harness sources and the per-machine harness state folder.

Sources (the rules): PING_HARNESS_ROOT if set, else the repo's harness/ folder.
State (staging, exports, backups, install-state.json): always ~/.ping-harness,
because install hashes and backups differ per machine and never go into git.
"""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPO_HARNESS = REPO_ROOT / "harness"
STATE_ROOT = Path.home() / ".ping-harness"


def source_root() -> Path:
    override = os.environ.get("PING_HARNESS_ROOT")
    if override:
        return Path(override)
    return REPO_HARNESS

import os
import sys
from pathlib import Path

KILL_AFTER_WRITE_ENV = "KILL_AFTER_WRITE"

def atomic_write(path, content):
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    # Hook for partial-state recovery test (Phase 9)
    if os.environ.get(KILL_AFTER_WRITE_ENV) == "1":
        os.replace(tmp, p)
        sys.exit(99)  # simulate crash before downstream git commit
    os.replace(tmp, p)

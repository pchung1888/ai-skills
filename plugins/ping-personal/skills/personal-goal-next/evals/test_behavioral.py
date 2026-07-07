#!/usr/bin/env python3
"""
Behavioral evals for personal-goal-next -- Phase 4 goal-skill-v2.

Tests:
  A1 -- beacon mutation round-trip (advance phase 1 PASS, assert mutations)
  A2 -- atomic-write crash recovery via KILL_AFTER_WRITE env hook
  A3a -- --abort produces BLOCKED row + Failure Log entry
  A3b -- --tokens absurd value refuses with exit 2
  A3c -- finalize --skip-if-cached skips after PASS cache exists
  A6a -- history fixture (beacon-healthy.md) parses and advances correctly
  A6b -- history fixture (beacon-blocked.md) parses correctly (phase 3 is still Pending)

All tests run in temp dirs; no repo files are mutated.
Exit 0 = all pass; 1 = failures.
"""

import os
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

# Locate skill lib relative to this file
EVALS_DIR = Path(__file__).resolve().parent
SKILL_DIR = EVALS_DIR.parent
LIB_DIR = SKILL_DIR / "lib"
FIXTURES_DIR = EVALS_DIR / "fixtures"

sys.path.insert(0, str(LIB_DIR))
from phase_table import update_row
from log_appender import append_cost_row, append_activity_row, append_failure_row
from checkpoint import update_checkpoint

ADVANCE_PY = str(LIB_DIR / "advance.py")
FINALIZE_PY = str(LIB_DIR / "finalize.py")

BEACON_HEALTHY = FIXTURES_DIR / "beacon-healthy.md"
BEACON_BLOCKED = FIXTURES_DIR / "beacon-blocked.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git_init_commit(dirp: Path, filename: Path) -> None:
    """Init a bare git repo in dirp and commit filename (must already exist)."""
    subprocess.run(["git", "init", "-q", str(dirp)], check=True)
    subprocess.run(["git", "-C", str(dirp), "config", "user.email", "test@test.local"], check=True)
    subprocess.run(["git", "-C", str(dirp), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(dirp), "add", str(filename)], check=True)
    subprocess.run(["git", "-C", str(dirp), "commit", "-q", "-m", "init beacon"], check=True)


def _run_advance(beacon_path: Path, extra_args: list, env=None) -> subprocess.CompletedProcess:
    """Run advance.py against beacon_path.  cwd is set to beacon's parent (git repo root)."""
    cmd = [sys.executable, ADVANCE_PY, "--beacon", str(beacon_path)] + extra_args
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          cwd=str(beacon_path.parent), env=merged)


# ---------------------------------------------------------------------------
# Two-phase beacon template used by A1, A2, A3a
# ---------------------------------------------------------------------------
BEACON_TEMPLATE = """\
---
goal_slug: test-goal
accept_cmd: pwsh -NoProfile -Command "Write-Host 'ALL EVALS PASS'"
accept_match: ALL EVALS PASS
accept_shell: pwsh
---

## Last Known Good Checkpoint

| Field | Value |
|---|---|
| Last completed phase | (none yet) |
| Last successful commit | (none yet) |
| Next action | Dispatch phase 1 |

## Phase Status

| Phase | Source | Title | Status | Commit | Subagent |
|---|---|---|---|---|---|
| 1 | conductor | First phase | ⬜ Pending | -- | -- |
| 2 | conductor | Second phase | ⬜ Pending | -- | -- |

## Subagent Token Cost Log

| # | Phase | Subagent | Task | Tokens | Duration | Outcome | Notes |
|---|---|---|---|---|---|---|---|

## Agent Activity Log

| Timestamp | Phase | Outcome | Commit |
|---|---|---|---|

## Failure Log

| # | Phase | Subagent | What failed | Recovery | Lesson candidate |
|---|---|---|---|---|---|
"""

# ---------------------------------------------------------------------------
# Beacon template WITH max_retries frontmatter (for loop-control tests B1, B2)
# ---------------------------------------------------------------------------
BEACON_TEMPLATE_RETRIES = """\
---
goal_slug: test-goal
accept_cmd: pwsh -NoProfile -Command "Write-Host 'ALL EVALS PASS'"
accept_match: ALL EVALS PASS
accept_shell: pwsh
max_retries: 2
---

## Last Known Good Checkpoint

| Field | Value |
|---|---|
| Last completed phase | (none yet) |
| Last successful commit | (none yet) |
| Next action | Dispatch phase 1 |

## Phase Status

| Phase | Source | Title | Status | Commit | Subagent |
|---|---|---|---|---|---|
| 1 | conductor | First phase | Pending | -- | -- |
| 2 | conductor | Second phase | Pending | -- | -- |

## Subagent Token Cost Log

| # | Phase | Subagent | Task | Tokens | Duration | Outcome | Notes |
|---|---|---|---|---|---|---|---|

## Agent Activity Log

| Timestamp | Phase | Outcome | Commit |
|---|---|---|---|

## Failure Log

| # | Phase | Subagent | What failed | Recovery | Lesson candidate |
|---|---|---|---|---|---|
"""

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

fails = []


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_a1_round_trip():
    """A1: advance phase 1 PASS in a temp git repo; assert all three mutations."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE, encoding="utf-8")
        _git_init_commit(d, beacon)

        # Grab a real commit SHA to pass as --commit
        sha_r = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha = sha_r.stdout.strip()

        r = _run_advance(beacon, [
            "--phase", "1",
            "--outcome", "PASS",
            "--tokens", "5000",
            "--duration", "3",
            "--subagent", "driver",
            "--commit", sha,
        ])
        _assert(r.returncode == 0, f"advance exited {r.returncode}; stderr={r.stderr}")

        after = beacon.read_text(encoding="utf-8")

        # Phase Status row flipped to Done
        found_done = any(
            ln.startswith("| 1 ") and "Done" in ln and sha in ln
            for ln in after.splitlines()
        )
        _assert(found_done, "Phase 1 row not flipped to Done with commit SHA")

        # Cost Log row appended
        _assert("5000" in after, "Cost Log: token count 5000 not found")
        _assert("driver" in after, "Cost Log: subagent 'driver' not found")

        # Activity Log row appended
        _assert("| 1 | PASS |" in after or "1 | PASS |" in after,
                "Activity Log: phase 1 PASS row not found")

        # Checkpoint updated
        _assert("Dispatch phase 2" in after, "Checkpoint: next action not updated to phase 2")

        # git commit was created
        log_r = subprocess.run(
            ["git", "-C", str(d), "log", "--oneline"],
            capture_output=True, text=True, check=True
        )
        _assert(len(log_r.stdout.strip().splitlines()) >= 2,
                "No new git commit found after advance PASS")


def test_a2_crash_recovery():
    """A2: KILL_AFTER_WRITE=1 -> beacon is either fully old or fully new, never partial."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE, encoding="utf-8")
        _git_init_commit(d, beacon)

        sha_r = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha = sha_r.stdout.strip()

        # Capture original content BEFORE running advance
        original = beacon.read_text(encoding="utf-8")

        r = _run_advance(beacon, [
            "--phase", "1",
            "--outcome", "PASS",
            "--tokens", "5000",
            "--duration", "3",
            "--subagent", "driver",
            "--commit", sha,
        ], env={"KILL_AFTER_WRITE": "1"})

        # advance must exit 99 (crash signal)
        _assert(r.returncode == 99, f"KILL_AFTER_WRITE hook did not exit 99; got {r.returncode}")

        # Beacon on disk: must be either original or fully new (Phase 1 -> Done).
        # It must NOT be truncated (zero bytes or partial YAML).
        after = beacon.read_text(encoding="utf-8")
        _assert(len(after) > 100, "Beacon truncated/empty after crash")
        _assert(after.startswith("---"), "Beacon corrupted: no YAML frontmatter start")

        # No half-written .tmp file should remain
        tmp_file = beacon.with_suffix(beacon.suffix + ".tmp")
        _assert(not tmp_file.exists(), ".tmp partial file still present after crash")

        # Git status must be consistent: no staged-but-uncommitted mess
        # (KILL_AFTER_WRITE exits before the git add/commit calls)
        status_r = subprocess.run(
            ["git", "-C", str(d), "status", "--porcelain"],
            capture_output=True, text=True, check=True
        )
        # Porcelain: leading space = unstaged. Leading M = staged. Either is ok.
        # What is NOT ok: two-char " M" or "??" (new untracked) for the .tmp
        _assert(
            ".tmp" not in status_r.stdout,
            f".tmp file appears in git status: {status_r.stdout}"
        )


def test_a3a_abort():
    """A3a: --abort produces BLOCKED row + Failure Log entry."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE, encoding="utf-8")
        _git_init_commit(d, beacon)

        r = _run_advance(beacon, [
            "--phase", "1",
            "--outcome", "PASS",   # outcome required by argparse even for --abort path
            "--tokens", "1000",
            "--duration", "2",
            "--subagent", "driver",
            "--abort", "dependency unavailable",
        ])
        _assert(r.returncode == 0, f"--abort exited {r.returncode}; stderr={r.stderr}")

        after = beacon.read_text(encoding="utf-8")

        # Phase Status: BLOCKED row
        found_blocked = any(
            ln.startswith("| 1 ") and "BLOCKED" in ln
            for ln in after.splitlines()
        )
        _assert(found_blocked, "Phase 1 not BLOCKED after --abort")

        # Failure Log entry present
        _assert("ABORT" in after, "Failure Log: ABORT reason not found in beacon")
        _assert("dependency unavailable" in after,
                "Failure Log: abort reason text not found in beacon")

        # Git commit created
        log_r = subprocess.run(
            ["git", "-C", str(d), "log", "--oneline"],
            capture_output=True, text=True, check=True
        )
        _assert(len(log_r.stdout.strip().splitlines()) >= 2,
                "No git commit created by --abort path")


def test_a3b_absurd_tokens():
    """A3b: --tokens 99999999999 (> TOKEN_REFUSE=10000000) must exit 2."""
    # Use a nonexistent beacon -- advance must refuse BEFORE touching the beacon
    r = subprocess.run(
        [sys.executable, ADVANCE_PY,
         "--beacon", "/nonexistent/dummy.md",
         "--phase", "1",
         "--outcome", "PASS",
         "--tokens", "99999999999",
         "--duration", "1",
         "--subagent", "driver",
         "--commit", "abc"],
        capture_output=True, text=True, encoding="utf-8"
    )
    _assert(r.returncode == 2, f"absurd tokens did not exit 2; got {r.returncode}; stderr={r.stderr}")
    _assert("absurd" in r.stderr.lower() or "exceeds" in r.stderr.lower(),
            f"expected 'absurd'/'exceeds' in stderr; got: {r.stderr}")


def test_a3c_skip_if_cached():
    """A3c: finalize --skip-if-cached skips when cache exists from a prior PASS."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        # Write a beacon with accept_cmd that always passes
        beacon_content = BEACON_TEMPLATE.replace(
            'accept_cmd: pwsh -NoProfile -Command "Write-Host \'ALL EVALS PASS\'"',
            'accept_cmd: pwsh -NoProfile -Command "Write-Host \'ALL EVALS PASS\'"'
        )
        beacon.write_text(beacon_content, encoding="utf-8")
        _git_init_commit(d, beacon)

        # We need a dummy todo file for finalize.py
        todo = d / "todo.md"
        todo.write_text("- **[GOAL test test-goal]** some item\n", encoding="utf-8")

        # First run: no cache -> should run acceptance and PASS
        r1 = subprocess.run(
            [sys.executable, FINALIZE_PY,
             "--beacon", str(beacon),
             "--todo", str(todo),
             "--slug", "test-goal"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(d)
        )
        # finalize may fail if pwsh not available or accept_cmd mismatch is ok for this eval
        # The key test is that --skip-if-cached short-circuits on second run
        # so we manually write the cache file to simulate a prior PASS
        cache_file = Path(str(beacon) + ".accept-cache")
        import hashlib, datetime
        cmd_val = 'pwsh -NoProfile -Command "Write-Host \'ALL EVALS PASS\'"'
        matched_line = "ALL EVALS PASS"
        key = hashlib.sha256((cmd_val + "|" + matched_line).encode("utf-8")).hexdigest()
        ts = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        cache_file.write_text(
            f"key = {key}\nmatched_line = {matched_line}\nts = {ts}\n",
            encoding="utf-8"
        )

        # Second run with --skip-if-cached: must skip and exit 0
        r2 = subprocess.run(
            [sys.executable, FINALIZE_PY,
             "--beacon", str(beacon),
             "--todo", str(todo),
             "--slug", "test-goal",
             "--skip-if-cached"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(d)
        )
        _assert(r2.returncode == 0,
                f"--skip-if-cached did not exit 0; got {r2.returncode}; out={r2.stdout}; err={r2.stderr}")
        _assert("skipping" in r2.stdout.lower() or "previously" in r2.stdout.lower(),
                f"expected skip message; got stdout: {r2.stdout}")


def test_a6a_healthy_fixture():
    """A6a: beacon-healthy.md fixture parses and can have phase 2 advanced."""
    content = BEACON_HEALTHY.read_text(encoding="utf-8")

    # Should parse without error -- just call update_row (no git needed)
    out = update_row(content, 2, "OK Done", "fff001", "driver")
    found = any(
        ln.startswith("| 2 ") and "Done" in ln and "fff001" in ln
        for ln in out.splitlines()
    )
    _assert(found, "beacon-healthy.md: phase 2 row did not flip to Done")

    # Phase 1 (already Done) must still be Done
    found_1 = any(
        ln.startswith("| 1 ") and "Done" in ln
        for ln in out.splitlines()
    )
    _assert(found_1, "beacon-healthy.md: phase 1 Done row was lost after advancing phase 2")


def test_a6b_blocked_fixture():
    """A6b: beacon-blocked.md fixture parses; phase 3 (Pending) can be advanced;
    re-advancing a phase already written as 'OK Done' by advance.py is refused.

    Bug fixed in Phase 5: phase_table.update_row previously only guarded against
    re-advance when status contained the emoji '✅ Done', but advance.py writes
    plain-text 'OK Done' (no emoji).  The guard now matches BOTH forms so that
    any phase advance.py itself wrote is also protected from a duplicate call.
    """
    content = BEACON_BLOCKED.read_text(encoding="utf-8")

    # Phase 3 is Pending -- can be advanced
    out = update_row(content, 3, "OK Done", "abc999", "driver")
    found_3 = any(
        ln.startswith("| 3 ") and "Done" in ln and "abc999" in ln
        for ln in out.splitlines()
    )
    _assert(found_3, "beacon-blocked.md: phase 3 row did not flip to Done")

    # The fixture must contain a Failure Log entry (it was written with one)
    _assert("dep not deployed" in content,
            "beacon-blocked.md: expected Failure Log entry 'dep not deployed' to be present")

    # Phase 1 is 'OK Done' (plain text, written by advance.py) -- re-advancing it
    # MUST now be refused because the guard matches both 'OK Done' and emoji Done.
    try:
        update_row(content, 1, "OK Done", "dup999", "driver")
        _assert(False, "beacon-blocked.md: re-advance of OK Done phase 1 was not rejected")
    except RuntimeError as exc:
        _assert("already done" in str(exc).lower() or "duplicate" in str(exc).lower(),
                f"unexpected error message for dup-advance guard: {exc}")

    # Confirm undeclared phase still raises:
    try:
        update_row(content, 99, "OK Done", "x", "driver")
        _assert(False, "beacon-blocked.md: undeclared phase 99 advance not rejected")
    except RuntimeError:
        pass  # expected


def test_b1_retry_cap():
    """B1: 3rd FAIL with max_retries=2 -> exit 4, BLOCKED row, note contains 'RETRY CAP HIT'."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE_RETRIES, encoding="utf-8")
        _git_init_commit(d, beacon)

        # First FAIL -- should succeed (fail #1 <= max_retries=2)
        r1 = _run_advance(beacon, [
            "--phase", "1", "--outcome", "FAIL",
            "--tokens", "1000", "--duration", "1",
            "--subagent", "driver", "--notes", "first distinct failure note alpha",
        ])
        _assert(r1.returncode == 0,
                f"B1: 1st FAIL should exit 0; got {r1.returncode}; stderr={r1.stderr}")

        # Reset Phase Status row so second advance is not blocked by 'already done'
        # Note: FAIL outcome writes 'ERROR Failed' in the phase row so we must reset it
        # The fixture uses plain 'Pending' -- after first FAIL it will be 'ERROR Failed'.
        # We need to reset to 'Pending' before each subsequent call.  Read and patch.
        txt = beacon.read_text(encoding="utf-8")
        txt = txt.replace("| 1 | conductor | First phase | ERROR Failed |",
                          "| 1 | conductor | First phase | Pending |")
        beacon.write_text(txt, encoding="utf-8")
        subprocess.run(["git", "-C", str(d), "add", str(beacon)], check=True)
        subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", "reset row"], check=True)

        # Second FAIL -- should succeed (fail #2 = max_retries=2, not exceeding yet)
        r2 = _run_advance(beacon, [
            "--phase", "1", "--outcome", "FAIL",
            "--tokens", "1000", "--duration", "1",
            "--subagent", "driver", "--notes", "second distinct failure note beta",
        ])
        _assert(r2.returncode == 0,
                f"B1: 2nd FAIL should exit 0; got {r2.returncode}; stderr={r2.stderr}")

        # Reset again
        txt = beacon.read_text(encoding="utf-8")
        txt = txt.replace("| 1 | conductor | First phase | ERROR Failed |",
                          "| 1 | conductor | First phase | Pending |")
        beacon.write_text(txt, encoding="utf-8")
        subprocess.run(["git", "-C", str(d), "add", str(beacon)], check=True)
        subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", "reset row 2"], check=True)

        # Third FAIL -- fail #3 > max_retries=2, must exit 4 and BLOCKED
        r3 = _run_advance(beacon, [
            "--phase", "1", "--outcome", "FAIL",
            "--tokens", "1000", "--duration", "1",
            "--subagent", "driver", "--notes", "third distinct failure note gamma",
        ])
        _assert(r3.returncode == 4,
                f"B1: 3rd FAIL should exit 4; got {r3.returncode}; stderr={r3.stderr}")

        after = beacon.read_text(encoding="utf-8")
        found_blocked = any(
            ln.startswith("| 1 ") and "BLOCKED" in ln
            for ln in after.splitlines()
        )
        _assert(found_blocked, "B1: phase 1 row not BLOCKED after retry cap hit")
        _assert("RETRY CAP HIT" in after,
                "B1: 'RETRY CAP HIT' prefix not found in beacon after retry cap")


def test_b2_no_progress():
    """B2: 2nd FAIL with near-identical notes -> exit 4, note contains 'NO PROGRESS DETECTED'."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE_RETRIES, encoding="utf-8")
        _git_init_commit(d, beacon)

        note = "import failed because module not found in the path"

        # First FAIL -- should succeed
        r1 = _run_advance(beacon, [
            "--phase", "1", "--outcome", "FAIL",
            "--tokens", "1000", "--duration", "1",
            "--subagent", "driver", "--notes", note,
        ])
        _assert(r1.returncode == 0,
                f"B2: 1st FAIL should exit 0; got {r1.returncode}; stderr={r1.stderr}")

        # Reset Phase Status row
        txt = beacon.read_text(encoding="utf-8")
        txt = txt.replace("| 1 | conductor | First phase | ERROR Failed |",
                          "| 1 | conductor | First phase | Pending |")
        beacon.write_text(txt, encoding="utf-8")
        subprocess.run(["git", "-C", str(d), "add", str(beacon)], check=True)
        subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", "reset row"], check=True)

        # Second FAIL with nearly identical note (>= 0.8 token overlap)
        near_identical = "import failed because module was not found in the path"
        r2 = _run_advance(beacon, [
            "--phase", "1", "--outcome", "FAIL",
            "--tokens", "1000", "--duration", "1",
            "--subagent", "driver", "--notes", near_identical,
        ])
        _assert(r2.returncode == 4,
                f"B2: near-identical 2nd FAIL should exit 4; got {r2.returncode}; stderr={r2.stderr}")

        after = beacon.read_text(encoding="utf-8")
        _assert("NO PROGRESS DETECTED" in after,
                "B2: 'NO PROGRESS DETECTED' prefix not found in beacon")
        found_blocked = any(
            ln.startswith("| 1 ") and "BLOCKED" in ln
            for ln in after.splitlines()
        )
        _assert(found_blocked, "B2: phase 1 row not BLOCKED after no-progress detection")


def test_b3_legacy_no_cap():
    """B3: legacy beacon without max_retries field allows repeated FAILs at exit 0."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        # BEACON_TEMPLATE has no max_retries field -- legacy
        beacon.write_text(BEACON_TEMPLATE, encoding="utf-8")
        _git_init_commit(d, beacon)

        for i in range(3):
            note = f"legacy fail iteration {i} unique text here"
            r = _run_advance(beacon, [
                "--phase", "1", "--outcome", "FAIL",
                "--tokens", "1000", "--duration", "1",
                "--subagent", "driver", "--notes", note,
            ])
            _assert(r.returncode == 0,
                    f"B3: legacy FAIL #{i+1} should exit 0; got {r.returncode}; stderr={r.stderr}")
            # Reset Phase Status row for next iteration
            txt = beacon.read_text(encoding="utf-8")
            txt = txt.replace("| 1 | conductor | First phase | ERROR Failed |",
                              "| 1 | conductor | First phase | Pending |")
            beacon.write_text(txt, encoding="utf-8")
            subprocess.run(["git", "-C", str(d), "add", str(beacon)], check=True)
            subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", f"reset row {i}"], check=True)

        after = beacon.read_text(encoding="utf-8")
        _assert("RETRY CAP HIT" not in after,
                "B3: legacy beacon should not contain 'RETRY CAP HIT'")
        _assert("NO PROGRESS DETECTED" not in after,
                "B3: legacy beacon should not contain 'NO PROGRESS DETECTED'")


# ---------------------------------------------------------------------------
# Beacon template WITH token_budget_total frontmatter (for budget tests C1-C4)
# ---------------------------------------------------------------------------
BEACON_TEMPLATE_BUDGET = """\
---
goal_slug: test-goal
accept_cmd: pwsh -NoProfile -Command "Write-Host 'ALL EVALS PASS'"
accept_match: ALL EVALS PASS
accept_shell: pwsh
max_retries: 2
token_budget_total: 50000
---

## Last Known Good Checkpoint

| Field | Value |
|---|---|
| Last completed phase | (none yet) |
| Last successful commit | (none yet) |
| Next action | Dispatch phase 1 |

## Phase Status

| Phase | Source | Title | Status | Commit | Subagent |
|---|---|---|---|---|---|
| 1 | conductor | First phase | Pending | -- | -- |
| 2 | conductor | Second phase | Pending | -- | -- |

## Subagent Token Cost Log

Rollup: total=0 | phases=0 | median/phase=0

| # | Phase | Subagent type | Task description | Tokens | Duration | Outcome | Notes |
|---|---|---|---|---|---|---|---|

## Agent Activity Log

| Timestamp | Phase | Outcome | Commit |
|---|---|---|---|

## Failure Log

| # | Phase | Subagent | What failed | Recovery | Lesson candidate |
|---|---|---|---|---|---|
"""


def test_c1_budget_exceeded():
    """C1: budget=50000, advance with --tokens 60000 -> exit 5, beacon unchanged."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE_BUDGET, encoding="utf-8")
        _git_init_commit(d, beacon)

        sha_r = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha = sha_r.stdout.strip()

        original = beacon.read_text(encoding="utf-8")

        r = _run_advance(beacon, [
            "--phase", "1",
            "--outcome", "PASS",
            "--tokens", "60000",
            "--duration", "5",
            "--subagent", "driver",
            "--commit", sha,
        ])
        _assert(r.returncode == 5,
                f"C1: budget exceeded should exit 5; got {r.returncode}; stderr={r.stderr}")
        _assert("BUDGET EXCEEDED" in r.stderr,
                f"C1: expected 'BUDGET EXCEEDED' in stderr; got: {r.stderr}")

        # Beacon must be unchanged
        after = beacon.read_text(encoding="utf-8")
        _assert(after == original,
                "C1: beacon was mutated despite budget refusal")

        # No new git commit
        log_r = subprocess.run(
            ["git", "-C", str(d), "log", "--oneline"],
            capture_output=True, text=True, check=True
        )
        _assert(len(log_r.stdout.strip().splitlines()) == 1,
                "C1: a git commit was created despite budget refusal")


def test_c2_budget_override():
    """C2: budget=50000, advance with --tokens 60000 + --override-budget -> exit 0, override row in Activity Log."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE_BUDGET, encoding="utf-8")
        _git_init_commit(d, beacon)

        sha_r = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha = sha_r.stdout.strip()

        r = _run_advance(beacon, [
            "--phase", "1",
            "--outcome", "PASS",
            "--tokens", "60000",
            "--duration", "5",
            "--subagent", "driver",
            "--commit", sha,
            "--override-budget",
        ])
        _assert(r.returncode == 0,
                f"C2: --override-budget should exit 0; got {r.returncode}; stderr={r.stderr}")

        after = beacon.read_text(encoding="utf-8")
        _assert("BUDGET OVERRIDE" in after,
                "C2: 'BUDGET OVERRIDE' note not found in beacon after override")

        # A git commit must exist
        log_r = subprocess.run(
            ["git", "-C", str(d), "log", "--oneline"],
            capture_output=True, text=True, check=True
        )
        _assert(len(log_r.stdout.strip().splitlines()) >= 2,
                "C2: no git commit found after --override-budget advance")


def test_c3_legacy_no_budget():
    """C3: legacy beacon without token_budget_total -> unlimited, exit 0 even with large tokens."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        # BEACON_TEMPLATE has no token_budget_total field
        beacon.write_text(BEACON_TEMPLATE, encoding="utf-8")
        _git_init_commit(d, beacon)

        sha_r = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha = sha_r.stdout.strip()

        r = _run_advance(beacon, [
            "--phase", "1",
            "--outcome", "PASS",
            "--tokens", "999999",
            "--duration", "5",
            "--subagent", "driver",
            "--commit", sha,
        ])
        _assert(r.returncode == 0,
                f"C3: legacy beacon should exit 0 regardless of token count; got {r.returncode}; stderr={r.stderr}")
        _assert("BUDGET EXCEEDED" not in r.stderr,
                "C3: legacy beacon should not produce BUDGET EXCEEDED")


def test_c4_rollup_updates():
    """C4: Rollup line updates with correct total after two advances."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        beacon = d / "test-goal-audit-tracker.md"
        beacon.write_text(BEACON_TEMPLATE_BUDGET, encoding="utf-8")
        _git_init_commit(d, beacon)

        sha_r = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha = sha_r.stdout.strip()

        # First advance: phase 1 PASS with 10000 tokens
        r1 = _run_advance(beacon, [
            "--phase", "1",
            "--outcome", "PASS",
            "--tokens", "10000",
            "--duration", "5",
            "--subagent", "driver",
            "--commit", sha,
        ])
        _assert(r1.returncode == 0,
                f"C4: first advance should exit 0; got {r1.returncode}; stderr={r1.stderr}")

        # Second advance: phase 2 PASS with 20000 tokens
        sha_r2 = subprocess.run(
            ["git", "-C", str(d), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True
        )
        sha2 = sha_r2.stdout.strip()

        r2 = _run_advance(beacon, [
            "--phase", "2",
            "--outcome", "PASS",
            "--tokens", "20000",
            "--duration", "8",
            "--subagent", "driver",
            "--commit", sha2,
        ])
        _assert(r2.returncode == 0,
                f"C4: second advance should exit 0; got {r2.returncode}; stderr={r2.stderr}")

        after = beacon.read_text(encoding="utf-8")
        # Rollup line must show total=30000, phases=2
        _assert("total=30000" in after,
                f"C4: expected 'total=30000' in Rollup line; beacon snippet: {after[after.find('Rollup'):][:100]}")
        _assert("phases=2" in after,
                f"C4: expected 'phases=2' in Rollup line")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    ("A1_round_trip", test_a1_round_trip),
    ("A2_crash_recovery", test_a2_crash_recovery),
    ("A3a_abort", test_a3a_abort),
    ("A3b_absurd_tokens", test_a3b_absurd_tokens),
    ("A3c_skip_if_cached", test_a3c_skip_if_cached),
    ("A6a_healthy_fixture", test_a6a_healthy_fixture),
    ("A6b_blocked_fixture", test_a6b_blocked_fixture),
    ("B1_retry_cap", test_b1_retry_cap),
    ("B2_no_progress", test_b2_no_progress),
    ("B3_legacy_no_cap", test_b3_legacy_no_cap),
    ("C1_budget_exceeded", test_c1_budget_exceeded),
    ("C2_budget_override", test_c2_budget_override),
    ("C3_legacy_no_budget", test_c3_legacy_no_budget),
    ("C4_rollup_updates", test_c4_rollup_updates),
]

pass_count = 0
fail_count = 0
for name, fn in TESTS:
    try:
        fn()
        print(f"PASS {name}")
        pass_count += 1
    except Exception as exc:
        print(f"FAIL {name}: {exc}", file=sys.stderr)
        fail_count += 1

print(f"\nbehavioral_goal_next: {pass_count} passed, {fail_count} failed")
sys.exit(0 if fail_count == 0 else 1)

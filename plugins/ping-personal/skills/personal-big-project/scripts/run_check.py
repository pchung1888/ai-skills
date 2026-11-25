"""Run a task's check commands one by one, so a check is never hand-joined into one shell line, and prove
RED tasks (a test that must fail because the code does not exist yet). generate.py writes the checks JSON
and the task's check command for you; run it by hand only to try a check.

  python run_check.py <checks json>

Checks JSON. Example:
  {"task": "T3", "commands": ["python -m pytest tests/test_a.py -q", "python tools/lint.py"],
   "expect": "pass", "cwd": "D:/work/myrepo", "timeoutSec": 600}
  task: id printed in the last line. commands: non-empty list of command strings, run in order.
  expect: "pass" (default) or "fail" (RED proof). file: optional glob that must match a file (expect "fail"
  only; "**" matches folders). Example: "tests/**/test_invoice.*". cwd: optional folder to run in (default the
  current folder). timeoutSec: per command, default 1800.

Commands run through the shell (shell=True). On Windows that is cmd.exe, so the string must work in cmd; a
command starting with "pwsh " or "powershell " is fine. stdout and stderr are captured as UTF-8 (bad bytes
replaced). For each command it prints "[k/n] exit <code>: <last non-empty output line>"; a timeout prints
"[k/n] exit 124: timeout after N s".

expect pass: every command must exit 0. Last line "<task> CHECK PASS", or "<task> CHECK FAIL (<k> of <n> failed)".
expect fail: the file (when given) must exist and EVERY command must exit non-zero and not time out (the test
  exists and fails because the code is not there yet). Last line "<task> RED PASS", or
  "<task> RED FAIL: <reason>" (file missing, command k already passes, command k timed out).
Exit code is 0 on PASS and 1 on FAIL; a checks JSON that is unreadable or malformed exits 2.
"""
import glob
import json
import os
import signal
import subprocess
import sys

TIMEOUT_EXIT = 124  # the GNU timeout convention


def kill_tree(proc):
    """Kill the shell and everything it started, else a grandchild keeps the output pipe open."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        os.killpg(proc.pid, signal.SIGKILL)


def run_one(command, cwd, timeout):
    """(exit code, last non-empty output line, timed_out) of one shell command."""
    proc = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", start_new_session=os.name != "nt")
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        proc.communicate()
        return TIMEOUT_EXIT, f"timeout after {timeout:g} s", True
    lines = [l.strip() for l in (out or "").splitlines() if l.strip()]
    return proc.returncode, lines[-1] if lines else "(no output)", False


def main(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            spec = json.load(f)
    except (OSError, ValueError) as e:
        print(f"RUN_CHECK FAIL: cannot read {path}: {e}")
        return 2
    cmds = spec.get("commands") if isinstance(spec, dict) else None
    task = str(spec.get("task", "")) if isinstance(spec, dict) else ""
    expect = spec.get("expect", "pass") if isinstance(spec, dict) else None
    timeout = spec.get("timeoutSec", 1800) if isinstance(spec, dict) else None
    if not (task and isinstance(cmds, list) and cmds and all(isinstance(c, str) and c.strip() for c in cmds)
            and expect in ("pass", "fail") and isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0):
        print("RUN_CHECK FAIL: checks JSON needs task, a non-empty commands list of strings, expect pass|fail, timeoutSec > 0")
        return 2
    cwd = spec.get("cwd") or None
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if expect == "fail" and spec.get("file"):
        pattern = os.path.join(cwd, spec["file"]) if cwd and not os.path.isabs(spec["file"]) else spec["file"]
        if not glob.glob(pattern, recursive=True):
            print(f"test file missing: {spec['file']}")
            print(f"{task} RED FAIL: test file missing: {spec['file']}")
            return 1
    results = []
    for k, command in enumerate(cmds, 1):
        code, last, timed_out = run_one(command, cwd, timeout)
        results.append((code, timed_out))
        print(f"[{k}/{len(cmds)}] exit {code}: {last}")
    if expect == "pass":
        failed = sum(code != 0 for code, _ in results)
        print(f"{task} CHECK FAIL ({failed} of {len(cmds)} failed)" if failed else f"{task} CHECK PASS")
        return 1 if failed else 0
    for k, (code, timed_out) in enumerate(results, 1):
        if timed_out or code == 0:
            why = "timed out" if timed_out else "already passes, so it cannot prove the code it targets"
            print(f"{task} RED FAIL: command {k} {why}")
            return 1
    print(f"{task} RED PASS")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__.splitlines()[0])
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))

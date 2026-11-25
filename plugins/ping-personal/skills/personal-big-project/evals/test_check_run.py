"""Self-check for scripts/check_run.py: the good-run fixture passes, and every fail-closed rule and
every parser case (headerless logs, dash or empty time cells, escaped pipes, non-numeric counts) fails by
name. Run: python evals/test_check_run.py   Prints CHECK RUN TEST PASS."""
import contextlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import check_run  # noqa: E402
import statefiles  # noqa: E402

sys.path.insert(0, os.path.join(HERE, "fixtures"))
import materialize  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures")
SECTIONS = "\n## Evidence\nBefore and after.\n\n## Merge danger\nA two-way door.\n"  # what owner-report requires
MASTER = []  # [path of the materialized fixtures]: built once, copied per case
ASK_LINE = ('{"type":"assistant","timestamp":"%s","message":{"content":[{"type":"tool_use","name":"AskUserQuestion"}]}}\n')


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def append(path, text):
    with open(path, "a", encoding="utf-8", newline="") as f:
        f.write(text)


def edit_json(path, change):
    doc = json.loads(read(path))
    change(doc)
    write(path, json.dumps(doc))


def fixtures_copy(tmp, case):
    """A fresh copy of the materialized fixtures: good-run/repo is a git repo whose origin is the bare
    remote.git next to it (a relative url, so a copy points at its own remote)."""
    if not MASTER:
        MASTER.append(materialize.materialize(os.path.join(tmp, "master")))
        # The fixture's STATUS.md predates build_table.py's "Built" stamp; give the master copy one (newest run-log row is 21:10).
        status = os.path.join(MASTER[0], "good-run", "repo", "autopilot", "STATUS.md")
        write(status, read(status).replace(statefiles.TASKS_BEGIN, statefiles.TASKS_BEGIN + "\nBuilt Fri 10-16 21:15 by build_table.py\n", 1))
    copy = os.path.join(tmp, case)
    shutil.copytree(MASTER[0], copy)
    return copy


def git(repo, *args):
    done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                           *args], cwd=repo, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def run_check(state, transcript):
    """(exit code, output lines) of one check_run pass."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = check_run.run(state, transcript)
    return code, buffer.getvalue().splitlines()


def assert_fails(case, name, tmp, mutate):
    """Copy the fixtures, apply `mutate(state, transcript)`, and require FAIL <name>."""
    copy = fixtures_copy(tmp, case)
    state = os.path.join(copy, "good-run", "repo", "autopilot")
    transcript = os.path.join(copy, "transcript.jsonl")
    mutated_transcript = mutate(state, transcript)
    code, lines = run_check(state, mutated_transcript if str(mutated_transcript).endswith(".jsonl") else transcript)
    assert code == 1, f"{case}: expected exit 1, got {code}: {lines}"
    assert any(l.startswith(f"FAIL {name}:") for l in lines), f"{case}: no FAIL {name} in {lines}"
    return lines


def assert_passes(case, tmp, mutate):
    copy = fixtures_copy(tmp, case)
    state = os.path.join(copy, "good-run", "repo", "autopilot")
    transcript = os.path.join(copy, "transcript.jsonl")
    mutate(state, transcript)
    code, lines = run_check(state, transcript)
    assert code == 0, f"{case}: expected pass, got {lines}"


def main():
    tmp = tempfile.mkdtemp()
    try:
        good = fixtures_copy(tmp, "good")
        good_state = os.path.join(good, "good-run", "repo", "autopilot")
        code, lines = run_check(good_state, os.path.join(good, "transcript.jsonl"))
        assert code == 0 and lines[-1] == "RUN CHECK PASS", lines
        for name in ("remote-tags", "remote-branches", "final-commit", "owner-report"):
            assert f"PASS {name}" in lines, (name, lines)

        # Fail closed: each required file missing is named.
        for name in check_run.REQUIRED_FILES:
            lines = assert_fails("missing-" + name.replace(os.sep, "-"), "required-files", tmp,
                                 lambda s, t, n=name: os.remove(os.path.join(s, n)))
            assert any(name in l for l in lines if l.startswith("FAIL required-files")), (name, lines)
        assert_fails("no-transcript", "no-questions", tmp, lambda s, t: (None, os.remove(t))[0])
        code, lines = run_check(good_state, None)
        assert code == 1 and any(l.startswith("FAIL no-questions:") and "required" in l for l in lines), lines

        # inputs.json: caps and unattendedSince are required; a bad cap value is refused.
        assert_fails("no-caps", "inputs", tmp, lambda s, t: edit_json(os.path.join(s, "inputs.json"), lambda d: d.pop("caps")))
        assert_fails("no-since", "inputs", tmp, lambda s, t: edit_json(os.path.join(s, "inputs.json"), lambda d: d.pop("unattendedSince")))
        assert_fails("bad-cap", "inputs", tmp, lambda s, t: edit_json(os.path.join(s, "inputs.json"), lambda d: d["caps"].update(mail="lots")))

        # A time with no zone is UTC: the question at 01:00Z is after 00:30 read as UTC (it would be
        # before it if read as a UTC-4 local time).
        def naive_since(state, transcript):
            edit_json(os.path.join(state, "inputs.json"), lambda d: d.update(unattendedSince="2026-10-17T00:30:00"))
            write(transcript, ASK_LINE % "2026-10-17T01:00:00.000Z")
        assert_fails("naive-utc", "no-questions", tmp, naive_since)

        # A half-written last transcript line is skipped, the earlier question is still found.
        def half_line(state, transcript):
            append(transcript, ASK_LINE % "2026-10-17T03:00:00.000Z" + '{"type":"assistant","timestamp":"2026-10-17T03:')
        assert_fails("half-transcript", "no-questions", tmp, half_line)

        # run-log parser cases.
        assert_fails("log-headerless", "log-times", tmp,
                     lambda s, t: write(os.path.join(s, "log", "run-log.md"), "| evening | T1 | first row has no header | - |\n"))
        assert_fails("log-dash", "log-times", tmp,
                     lambda s, t: append(os.path.join(s, "log", "run-log.md"), "| - | T2 | no time | - |\n"))
        assert_fails("log-empty", "log-times", tmp,
                     lambda s, t: append(os.path.join(s, "log", "run-log.md"), "|  | T2 | empty time | - |\n"))
        assert_passes("log-pipe", tmp,
                      lambda s, t: append(os.path.join(s, "log", "run-log.md"), "| Fri 10-16 21:05 | T2 | a \\| b | - |\n"))
        assert_passes("log-headerless-good", tmp,
                      lambda s, t: write(os.path.join(s, "log", "run-log.md"), "| Fri 10-16 21:05 | T1 | no header | - |\n"))

        # tasks.csv with a BOM still compares ids; a missing row is named.
        assert_passes("csv-bom", tmp, lambda s, t: write(os.path.join(s, "tasks.csv"), "\ufeff" + read(os.path.join(s, "tasks.csv"))))

        # side-effects: non-numeric count, kind with no cap, over cap.
        assert_fails("count-text", "side-effects", tmp,
                     lambda s, t: append(os.path.join(s, "log", "side-effects.md"), "| Sat 10-17 01:00 | mail | many | x |\n"))
        assert_fails("count-empty", "side-effects", tmp,
                     lambda s, t: append(os.path.join(s, "log", "side-effects.md"), "| Sat 10-17 01:00 | mail |  | x |\n"))
        assert_fails("no-cap-kind", "side-effects", tmp,
                     lambda s, t: append(os.path.join(s, "log", "side-effects.md"), "| Sat 10-17 01:00 | push | 1 | x |\n"))
        assert_fails("over-cap", "side-effects", tmp,
                     lambda s, t: append(os.path.join(s, "log", "side-effects.md"), "| Sat 10-17 01:00 | mail | 38 | x |\n"))
        assert_passes("side-effects-headerless", tmp,
                      lambda s, t: write(os.path.join(s, "log", "side-effects.md"), "| Sat 10-17 01:00 | mail | 40 | x |\n"))

        # baselines: an empty file is fine; a malformed line is a named FAIL, not a crash.
        assert_passes("baselines-empty", tmp, lambda s, t: write(os.path.join(s, "baseline-hashes.txt"), ""))
        assert_fails("baselines-malformed", "baselines", tmp,
                     lambda s, t: append(os.path.join(s, "baseline-hashes.txt"), "not-a-hash\n"))
        assert_fails("baselines-not-hex", "baselines", tmp,
                     lambda s, t: write(os.path.join(s, "baseline-hashes.txt"), "zzzz  baseline/expected.txt\n"))
        # sha256sum -b writes "<sha> *<path>"; a run with nothing to baseline writes "none".
        assert_passes("baselines-star", tmp, lambda s, t: write(os.path.join(s, "baseline-hashes.txt"),
                      "498b484532af1715eded0cf3b635f059293c3bcc81664648f06a6339b076f31c *baseline/expected.txt\n"))
        assert_passes("baselines-none", tmp, lambda s, t: write(os.path.join(s, "baseline-hashes.txt"), "none\n"))
        assert_fails("baselines-short-line", "baselines", tmp,
                     lambda s, t: write(os.path.join(s, "baseline-hashes.txt"), "498b484532af1715eded0cf3b635f059293c3bcc81664648f06a6339b076f31c\n"))

        # verdict: exact string, deferred counts equal to run-state.json, a verdict must exist.
        assert_fails("verdict-text", "verdict", tmp,
                     lambda s, t: write(os.path.join(s, "OWNER-REPORT.md"), "Verdict: PASS (2 of 2 tasks; 1 deferred)\n"))
        assert_fails("verdict-other-text", "verdict", tmp,
                     lambda s, t: write(os.path.join(s, "OWNER-REPORT.md"), "Verdict: PASS (9 of 9 tasks; 1 deferred, 1 by agents)\n"))
        assert_fails("verdict-counts", "verdict", tmp,
                     lambda s, t: edit_json(os.path.join(s, "run-state.json"),
                                            lambda d: d["stages"][0]["tasks"]["T1"].update(outcome="deferred", deferredBy="owner")))
        #   M2: a STOPPED verdict passes when its counts match; a wrong prefix or wrong counts fail
        stopped = "STOPPED (weekly-cap; 1 of 3 tasks passed; 1 deferred, 1 by agents)"

        def make_stopped(s, t, text=stopped):
            edit_json(os.path.join(s, "run-state.json"), lambda d: d.update(verdict=text))
            write(os.path.join(s, "OWNER-REPORT.md"), "Verdict: " + text + "\n" + SECTIONS)
            os.makedirs(os.path.join(s, "stages"), exist_ok=True)
            write(os.path.join(s, "stages", "s1-build.json"), json.dumps({"steps": [{"id": "T1"}, {"id": "T2"}, {"id": "T3"}]}))

        assert_passes("verdict-stopped", tmp, make_stopped)
        assert_fails("verdict-stopped-passed", "verdict", tmp,
                     lambda s, t: make_stopped(s, t, stopped.replace("1 of 3", "2 of 3")))
        assert_fails("verdict-stopped-total", "verdict", tmp,
                     lambda s, t: make_stopped(s, t, stopped.replace("of 3", "of 9")))
        assert_fails("verdict-prefix", "verdict", tmp,
                     lambda s, t: make_stopped(s, t, stopped.replace("STOPPED", "DONE")))
        assert_passes("verdict-fail-done-line", tmp, lambda s, t: make_stopped(
            s, t, "FAIL (done command: ALL CHECKS FAIL, 2 of 9; 2 of 3 tasks; 1 deferred, 1 by agents)"))
        assert_fails("verdict-fail-counts", "verdict", tmp, lambda s, t: make_stopped(
            s, t, "FAIL (done command: ALL CHECKS FAIL; 3 of 3 tasks; 1 deferred, 1 by agents)"))
        assert_fails("verdict-pass-counts", "verdict", tmp,
                     lambda s, t: make_stopped(s, t, "PASS (3 of 3 tasks; 1 deferred, 1 by agents)"))
        assert_fails("verdict-none", "verdict", tmp,
                     lambda s, t: edit_json(os.path.join(s, "run-state.json"), lambda d: d.update(verdict=None)))
        assert_fails("run-state-half", "verdict", tmp, lambda s, t: write(os.path.join(s, "run-state.json"), '{"stages": ['))

        # A report with a code in it is refused; progress rows are looked up by task id.
        assert_fails("report-code", "report-plain", tmp,
                     lambda s, t: append(os.path.join(s, "reports", "2026-10-16-2130.md"), "Task T2 passed.\n"))

        def ids_asked(s, t):  # the owner asked for task ids in their reports at start
            append(os.path.join(s, "reports", "2026-10-16-2130.md"), "Task T2 passed.\n")
            edit_json(os.path.join(s, "inputs.json"), lambda d: d.update(report={"ids": True}))
        assert_passes("report-ids-asked", tmp, ids_asked)
        assert_fails("row-missing", "table-rows", tmp,
                     lambda s, t: append(os.path.join(s, "tasks.csv"), "T3,Build,new,,\n"))
        # owner-feedback: one row per owner message after unattendedSince, each with a known class; a dropped
        # row or an unknown class fails, so the coordinator cannot leave out a complaint unseen.
        fb = lambda s: os.path.join(s, "log", "owner-feedback.md")
        assert_fails("feedback-row-dropped", "owner-feedback", tmp,
                     lambda s, t: write(fb(s), "\n".join(read(fb(s)).splitlines()[:3]) + "\n"))
        assert_fails("feedback-bad-class", "owner-feedback", tmp,
                     lambda s, t: write(fb(s), read(fb(s)).replace("| steer |", "| happy |")))
        # Setup talk logged before unattendedSince (rule 12) is not counted against the transcript.
        assert_passes("feedback-setup-before-unattended", tmp, lambda s, t: write(fb(s), read(fb(s)).replace(
            "|---|---|---|---|---|---|\n", "|---|---|---|---|---|---|\n| Fri 10-16 10:00 | setup | big-project | - | - | the goal |\n")))
        # A 15-minute tick is not an owner message, so it needs no row.
        assert_passes("feedback-15-minute-tick", tmp, lambda s, t: append(
            t, '{"type": "user", "timestamp": "2026-10-17T03:20:00.000Z", "message": {"content": "G 15-minute tick (unattended)."}}\n'))
        # owner-score: the closing ask must leave a score row (class score, Like 1-5).
        assert_fails("no-owner-score", "owner-score", tmp,
                     lambda s, t: write(fb(s), read(fb(s)).replace("| score | big-project | - | 4 |", "| answer | big-project | - | - |")))

        # deliverable: GOAL-BRIEF.md must settle the deliverable (first-run test, manifest, folder contract).
        brief = lambda s: os.path.join(s, "GOAL-BRIEF.md")
        assert_fails("no-deliverable", "deliverable", tmp,
                     lambda s, t: write(brief(s), read(brief(s)).split("## Deliverable")[0]))
        assert_fails("empty-deliverable", "deliverable", tmp,
                     lambda s, t: write(brief(s), read(brief(s)).split("## Deliverable")[0] + "## Deliverable\n\n"))
        # audit-first (rule 17): the brief names the old version or "none"; a named one needs audit-old.md.
        old_v1 = lambda s: read(brief(s)).split("## Old version")[0] + "## Old version\n\nweb/page-v1.asp\n"
        assert_fails("no-old-version", "audit-first", tmp,
                     lambda s, t: write(brief(s), read(brief(s)).split("## Old version")[0]))
        assert_fails("old-version-no-audit", "audit-first", tmp, lambda s, t: write(brief(s), old_v1(s)))
        assert_passes("old-version-audited", tmp, lambda s, t: (
            write(brief(s), old_v1(s)), write(os.path.join(s, "audit-old.md"), "# Audit\n\n- finding -> build skill\n")))

        # ui-browser: a UI task's check must launch a real browser (Chromium), never a stub DOM harness.
        png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">II", 800, 600) + b"\x08\x06\x00\x00\x00"

        def proof(s, tid, name, data):  # what the UI check leaves behind: proof/<task id>/<file>
            os.makedirs(os.path.join(s, "proof", tid), exist_ok=True)
            with open(os.path.join(s, "proof", tid, name), "wb") as f:
                f.write(data)

        def trace_zip(members):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                for m in members:
                    z.writestr(m, "{}")
            return buf.getvalue()

        def ui_task(s, script_text, check="node tools/ui_check.js", ui=True, tid="T9", shot=True):
            os.makedirs(os.path.join(s, "stages"), exist_ok=True)
            step = {"id": tid, "agent": "ping-personal:bunny", "text": "build the viewer grid", "check": check, "estimateK": 40}
            if ui is not None:  # None leaves the key out, so only the text detection applies
                step["ui"] = ui
            write(os.path.join(s, "stages", "s3-build.json"), json.dumps({"name": "s3-build", "steps": [step]}))
            os.makedirs(os.path.join(s, "..", "tools"), exist_ok=True)
            write(os.path.join(s, "..", "tools", "ui_check.js"), script_text)
            if shot:
                proof(s, tid, "grid.png", png)
        stub = "const dom = require('./fake-dom'); dom.click('#grid'); console.log('ALL PASS')\n"
        real = "const { chromium } = require('playwright'); chromium.launch().then(b => b.close())\n"
        assert_fails("ui-stub-check", "ui-browser", tmp, lambda s, t: ui_task(s, stub))
        assert_passes("ui-real-browser", tmp, lambda s, t: ui_task(s, real))
        # A list check (several commands) is read command by command, so a script it names is followed too.
        assert_passes("ui-list-check-real", tmp, lambda s, t: ui_task(s, real, check=["python build.py", "node tools/ui_check.js"]))
        assert_fails("ui-list-check-stub", "ui-browser", tmp, lambda s, t: ui_task(s, stub, check=["python build.py", "node tools/ui_check.js"]))
        # A task is a UI task when its text or check names a page, even without "ui": true.
        # Proof the browser ran: each UI task that was not deferred leaves a real screenshot (PNG
        # signature and IHDR header) or a Playwright trace zip (holds a *.trace member) in proof/<task id>/.
        def proof_fails(case, mutate):  # fails on the proof rule, not on some other ui-browser rule
            lines = assert_fails(case, "ui-browser", tmp, mutate)
            assert any("proof/<task id>/" in l for l in lines if l.startswith("FAIL ui-browser")), f"{case}: {lines}"
        proof_fails("ui-no-proof", lambda s, t: ui_task(s, real, shot=False))
        proof_fails("ui-fake-png", lambda s, t: (
            ui_task(s, real, shot=False), proof(s, "T9", "grid.png", b"not really a png")))
        proof_fails("ui-zip-no-trace", lambda s, t: (
            ui_task(s, real, shot=False), proof(s, "T9", "trace.zip", trace_zip(["readme.txt"]))))
        assert_passes("ui-trace-proof", tmp, lambda s, t: (
            ui_task(s, real, shot=False), proof(s, "T9", "trace.zip", trace_zip(["trace.trace", "trace.network"]))))
        assert_passes("ui-deferred-no-proof", tmp, lambda s, t: ui_task(s, real, tid="T2", shot=False))
        proof_fails("ui-proof-id-escapes", lambda s, t: (
            ui_task(s, real, tid="..", shot=False), proof(s, "..", "grid.png", png)))
        assert_fails("ui-by-html-name", "ui-browser", tmp,
                     lambda s, t: ui_task(s, stub, check="node tools/ui_check.js viewer/usage-viewer.html", ui=None))
        # An explicit "ui": false opts out even when the check names a page (review and evidence tasks).
        assert_passes("ui-false-opts-out", tmp,
                      lambda s, t: ui_task(s, stub, check="node tools/ui_check.js viewer/usage-viewer.html", ui=False, shot=False))

        # The task text often lives only in plan.md ("## Task <id>"); a page named there makes it a UI task.
        # This is how the 11-05 grid task escaped: its spec had no text and its check was a stub harness.
        def ui_in_plan(s, t):
            ui_task(s, stub, ui=None)
            write(os.path.join(s, "stages", "s3-build.json"), read(os.path.join(s, "stages", "s3-build.json"))
                  .replace('"text": "build the viewer grid", ', ""))
            write(os.path.join(s, "plan.md"), "# Plan\n\n## Task T9 - grid\n\nMake the cells in viewer/usage-viewer.html editable.\n"
                  "\n## Task T10 - other\n\nNothing to do with pages.\n")
        assert_fails("ui-named-in-plan", "ui-browser", tmp, ui_in_plan)

        # fidelity (rule 17): rebuilding an old page needs the side-by-side page, with no NOT-RUN state in it.
        def rebuild(s, page=None):
            write(brief(s), old_v1(s))
            write(os.path.join(s, "audit-old.md"), "# Audit\n\n- finding\n")
            ui_task(s, real)
            if page is not None:
                os.makedirs(os.path.join(s, "fidelity"), exist_ok=True)
                write(os.path.join(s, "fidelity", "index.html"), page)
        assert_fails("rebuild-no-fidelity-page", "fidelity", tmp, lambda s, t: rebuild(s))
        two = '<div data-state="list" data-differences="0"></div><div data-state="edit" data-differences="{}"></div>'
        assert_fails("rebuild-not-run-state", "fidelity", tmp, lambda s, t: rebuild(s, two.format("0") + " NOT-RUN"))
        # A page that compared nothing is not evidence: every state carries a measured differences count.
        assert_fails("rebuild-page-no-states", "fidelity", tmp, lambda s, t: rebuild(s, "<h1>Old vs new</h1> looks the same"))
        assert_fails("rebuild-state-no-count", "fidelity", tmp,
                     lambda s, t: rebuild(s, two.replace(' data-differences="{}"', "")))
        assert_passes("rebuild-every-state-compared", tmp, lambda s, t: rebuild(s, two.format("3")))

        # not-run-claims (rule 2): one NOT-RUN check keeps "complete" and "best" out of the reports.
        def not_run(s, report_line):
            append(os.path.join(s, "log", "run-log.md"), "| Fri 10-16 21:12 | T2 | look check NOT-RUN for the second page | results/t2.md |\n")
            append(os.path.join(s, "OWNER-REPORT.md"), "\n" + report_line + "\n")
        assert_fails("not-run-but-complete", "not-run-claims", tmp, lambda s, t: not_run(s, "The rebuild is complete."))
        assert_fails("not-run-but-best", "not-run-claims", tmp, lambda s, t: not_run(s, "Best look of all versions."))
        assert_passes("not-run-said-honestly", tmp, lambda s, t: not_run(s, "The rebuild is not complete: one look check did not run."))

        def ships_html(s, t):  # the run commits a page but no task is a UI task
            repo = os.path.dirname(s)
            write(os.path.join(repo, "viewer.html"), "<html></html>\n")
            git(repo, "add", "viewer.html")
            git(repo, "commit", "-q", "-m", "page")
        assert_fails("html-shipped-no-ui-task", "ui-browser", tmp, ships_html)

        def deletes_html(s, t):  # a run that only deleted a page ships no page, so it needs no UI task
            repo = os.path.dirname(s)
            write(os.path.join(repo, "old.html"), "<html></html>\n")
            git(repo, "add", "old.html")
            git(repo, "commit", "-q", "-m", "page")
            edit_json(os.path.join(s, "inputs.json"), lambda d: d.update(baseCommit=git(repo, "rev-parse", "HEAD")))
            git(repo, "rm", "-q", "old.html")
            git(repo, "commit", "-q", "-m", "drop page")
        lines = assert_fails("html-deleted-only", "final-commit", tmp, deletes_html)  # unpushed commits; ui-browser must pass
        assert "PASS ui-browser" in lines, lines

        # --only: the final stage checks the report shape before FINAL; other checks and run-check.txt are left alone
        copy = fixtures_copy(tmp, "only-owner-report")
        state = os.path.join(copy, "good-run", "repo", "autopilot")
        edit_json(os.path.join(state, "run-state.json"), lambda d: d.update(verdict=None))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = check_run.run(state, None, only=["owner-report"])
        assert code == 0 and buffer.getvalue().splitlines() == ["PASS owner-report", "RUN CHECK PASS"], buffer.getvalue()
        assert not os.path.exists(os.path.join(state, "log", "run-check.txt")) or "verdict" in open(
            os.path.join(state, "log", "run-check.txt")).read(), "a partial check never replaces the full result"

        # Hardening (security review of 0.46.1): a git failure fails closed, a baseCommit that git would
        # read as an option is refused and never runs, a missing brief is a FAIL not a crash, and a
        # browser script outside the repo and state folder does not count.
        assert_fails("ui-diff-git-error", "ui-browser", tmp, lambda s, t: edit_json(
            os.path.join(s, "inputs.json"), lambda d: d.update(baseCommit="1" * 40)))
        smuggled = os.path.join(tmp, "smuggled-output.txt")
        assert_fails("ui-diff-option-base", "ui-browser", tmp, lambda s, t: edit_json(
            os.path.join(s, "inputs.json"), lambda d: d.update(baseCommit="--output=" + smuggled)))
        assert not os.path.exists(smuggled), "git ran a baseCommit that starts with '-'"
        assert_fails("no-goal-brief", "deliverable", tmp, lambda s, t: os.remove(os.path.join(s, "GOAL-BRIEF.md")))

        def outside_script(s, t):
            ui_task(s, stub, check="node ../../../outside/real.js")
            os.makedirs(os.path.join(s, "..", "..", "..", "outside"), exist_ok=True)
            write(os.path.join(s, "..", "..", "..", "outside", "real.js"), real)
        assert_fails("ui-script-outside-roots", "ui-browser", tmp, outside_script)

        # A check that crashes is reported as FAIL crash, and run-check.txt is still rewritten.
        real_score = check_run.check_owner_score
        check_run.check_owner_score = lambda state: 1 / 0
        try:
            write(os.path.join(good_state, "log", "run-check.txt"), "RUN CHECK PASS\n")
            code, lines = run_check(good_state, os.path.join(good, "transcript.jsonl"))
        finally:
            check_run.check_owner_score = real_score
        assert code == 1 and any(l.startswith("FAIL crash: ZeroDivisionError") for l in lines), lines
        assert read(os.path.join(good_state, "log", "run-check.txt")).strip().endswith("RUN CHECK FAIL (1)")

        # The task table lives in STATUS.md's Tasks section: a row outside it does not count.
        assert_fails("no-tasks-section", "table-rows", tmp,
                     lambda s, t: write(os.path.join(s, "STATUS.md"), statefiles.task_section(read(os.path.join(s, "STATUS.md")))[0]
                                        + "| 1 | Build | T1 | x |\n| 2 | Build | T2 | x |\n| 3 | Build | T2:fix | x |\n"))

        def repo_of(state):
            return os.path.dirname(state)

        # inputs.json now also needs baseCommit and the two remote lists.
        for key in ("baseCommit", "remoteTagsAtStart", "remoteHeadsAtStart"):
            assert_fails("no-" + key, "inputs", tmp, lambda s, t, k=key: edit_json(os.path.join(s, "inputs.json"), lambda d: d.pop(k)))
        assert_fails("no-start-tags", "remote-tags", tmp,
                     lambda s, t: edit_json(os.path.join(s, "inputs.json"), lambda d: d.pop("remoteTagsAtStart")))

        assert_fails("remote-is-option", "remote-tags", tmp,
                     lambda s, t: edit_json(os.path.join(s, "inputs.json"), lambda d: d.update(remote="--upload-pack=x")))

        # remote-tags: a new tag, or a moved one, on the remote is a FAIL; the unchanged remote passes (good run above).
        assert_fails("tag-added", "remote-tags", tmp,
                     lambda s, t: (git(repo_of(s), "tag", "v2.0"), git(repo_of(s), "push", "origin", "v2.0")))
        assert_fails("tag-moved", "remote-tags", tmp,
                     lambda s, t: (git(repo_of(s), "tag", "-f", "v1.0", "HEAD"), git(repo_of(s), "push", "-f", "origin", "v1.0")))
        # remote-branches: another branch, or a moved main, is a FAIL; only inputs.branch may differ.
        assert_fails("branch-added", "remote-branches", tmp,
                     lambda s, t: git(repo_of(s), "push", "origin", "HEAD:refs/heads/other"))
        assert_fails("main-moved", "remote-branches", tmp,
                     lambda s, t: git(repo_of(s), "push", "-f", "origin", "HEAD:refs/heads/main"))

        def own_branch_moves(s, t):  # the run's own branch gets a new commit and a push: still a pass
            git(repo_of(s), "commit", "--allow-empty", "-m", "more work")
            git(repo_of(s), "push", "origin", "HEAD")
        assert_passes("own-branch-moves", tmp, own_branch_moves)
        # final-commit: an unpushed local commit, or a branch missing on the remote, is a FAIL.
        assert_fails("unpushed", "final-commit", tmp, lambda s, t: git(repo_of(s), "commit", "--allow-empty", "-m", "unpushed"))
        assert_fails("branch-gone", "final-commit", tmp,
                     lambda s, t: git(repo_of(s), "push", "origin", "--delete", "topic/123-fixes"))
        # A git failure is a named FAIL, never a crash: unknown remote, a folder that is not a repo, a subfolder of one.
        for case, change in (("bad-remote", lambda d: d.update(remote="nowhere")),
                             ("not-a-repo", lambda d: d.update(repoPath=tempfile.gettempdir())),
                             ("subfolder", lambda d: d.update(repoPath="."))):
            for name in ("remote-tags", "remote-branches", "final-commit"):
                assert_fails(f"{case}-{name}", name, tmp, lambda s, t, c=change: edit_json(os.path.join(s, "inputs.json"), c))

        # owner-report: both headings, and a door statement inside the Merge danger section.
        def owner(text):
            return lambda s, t: write(os.path.join(s, "OWNER-REPORT.md"), "Verdict: PASS (2 of 2 tasks; 1 deferred, 1 by agents)\n" + text)
        evidence = "\n## Evidence\nBefore and after.\n"
        assert_fails("owner-no-evidence", "owner-report", tmp, owner("\n## Merge danger\nA two-way door.\n"))
        assert_fails("owner-no-danger", "owner-report", tmp, owner(evidence))
        assert_fails("owner-no-door", "owner-report", tmp, owner(evidence + "\n## Merge danger\nLow risk.\n"))
        assert_fails("owner-door-elsewhere", "owner-report", tmp,
                     owner("\n## Evidence\nThis is a one-way door.\n\n## Merge danger\nLow risk.\n"))
        assert_fails("owner-door-after", "owner-report", tmp,
                     owner(evidence + "\n## Merge danger\nLow risk.\n\n## Notes\nA two-way door.\n"))
        assert_passes("owner-one-way", tmp, owner(evidence + "\n## Merge danger\nThe run is a One-Way Door: tag pushed.\n"))
        # baselines: a changed baseline file fails, unless inputs.json baselineChangesApproved lists it.
        def change_baseline(s, approved=None):
            append(os.path.join(os.path.dirname(s), "baseline", "expected.txt"), "changed\n")
            if approved is not None:
                edit_json(os.path.join(s, "inputs.json"), lambda d: d.update(baselineChangesApproved=approved))
        assert_fails("baseline-changed", "baselines", tmp, lambda s, t: change_baseline(s))
        assert_fails("baseline-other-approved", "baselines", tmp, lambda s, t: change_baseline(s, ["baseline/other.txt"]))
        assert_passes("baseline-approved", tmp, lambda s, t: change_baseline(s, ["baseline/expected.txt"]))
        assert_passes("baseline-approved-backslash", tmp, lambda s, t: change_baseline(s, ["baseline\\expected.txt"]))

        # owner-feedback matching: rows are matched to messages by time, one to one, oldest first.
        def local(utc):  # "Day MM-DD HH:MM" in the box's local clock, as log_row.py writes it
            return statefiles.parse_time(utc).astimezone().strftime("%a %m-%d %H:%M")

        def feedback_case(state, transcript, since, messages, rows):
            """messages: UTC ISO times of owner messages; rows: (UTC ISO time, class) of feedback rows."""
            edit_json(os.path.join(state, "inputs.json"), lambda d: d.update(unattendedSince=since))
            write(transcript, "".join(json.dumps({"type": "user", "timestamp": m, "message": {"content": "owner says hi"}}) + "\n"
                                      for m in messages))
            write(fb(state), "| When | Class | Skill | Missed what | Like | Quote |\n|---|---|---|---|---|---|\n" + "".join(
                f"| {local(t)} | {c} | big-project | - | {'4' if c == 'score' else '-'} | q |\n" for t, c in rows))
            return transcript
        score = ("2026-10-17T03:10:00Z", "score")
        T = lambda hhmmss: f"2026-10-17T{hhmmss}Z"  # noqa: E731
        # one message with two rows (a fix and a complaint): extra rows are fine
        assert_passes("feedback-two-rows-one-message", tmp, lambda s, t: feedback_case(
            s, t, T("00:30:00"), [T("01:00:00"), T("03:10:00")], [(T("01:00:00"), "fix"), (T("01:01:00"), "complaint"), score]))
        # the window runs from 1 minute before to 5 minutes after the message
        assert_passes("feedback-row-one-minute-early", tmp, lambda s, t: feedback_case(
            s, t, T("00:30:00"), [T("01:00:30"), T("03:10:00")], [(T("00:59:00"), "fix"), score]))
        assert_passes("feedback-row-five-minutes-late", tmp, lambda s, t: feedback_case(
            s, t, T("00:30:00"), [T("01:00:00"), T("03:10:00")], [(T("01:05:00"), "fix"), score]))
        assert_fails("feedback-row-too-early", "owner-feedback", tmp, lambda s, t: feedback_case(
            s, t, T("00:30:00"), [T("01:00:30"), T("03:10:00")], [(T("00:58:00"), "fix"), score]))
        assert_fails("feedback-row-too-late", "owner-feedback", tmp, lambda s, t: feedback_case(
            s, t, T("00:30:00"), [T("01:00:00"), T("03:10:00")], [(T("01:06:00"), "fix"), score]))
        # two messages, one row: a row serves one message, and the FAIL names the count and the first unmatched time
        lines = assert_fails("feedback-one-row-two-messages", "owner-feedback", tmp, lambda s, t: feedback_case(
            s, t, T("00:30:00"), [T("01:00:00"), T("01:01:00"), T("03:10:00")], [(T("01:00:00"), "fix"), score]))
        text = next(l for l in lines if l.startswith("FAIL owner-feedback:"))
        assert "1 owner message(s)" in text and local(T("01:01:00")) in text, text
        # a message typed after the run closed (run-state.json closed.at) needs no row; before it, it does
        def late_message(s, t, closed_at):
            feedback_case(s, t, T("00:30:00"), [T("01:00:00"), T("03:10:00"), T("05:00:00")], [(T("01:00:00"), "fix"), score])
            edit_json(os.path.join(s, "run-state.json"), lambda d: d.update(closed=closed_at))
            return t
        assert_passes("feedback-after-close", tmp, lambda s, t: late_message(s, t, {"at": T("03:20:00"), "reason": "done"}))
        assert_fails("feedback-before-close", "owner-feedback", tmp, lambda s, t: late_message(s, t, {"at": T("05:30:00"), "reason": "done"}))
        assert_fails("feedback-never-closed", "owner-feedback", tmp, lambda s, t: late_message(s, t, None))
        # a setup row stamped in the unattendedSince minute is not counted, so it cannot stand in for a later message
        assert_fails("feedback-same-minute-setup", "owner-feedback", tmp, lambda s, t: feedback_case(
            s, t, T("01:00:10"), [T("01:00:40"), T("03:10:00")], [(T("01:00:00"), "setup"), score]))

        # table-fresh: the Tasks section must start with a Built stamp no older than one tick (+5 min) before the newest log row.
        def built(s, stamp, every=None):
            path = os.path.join(s, "STATUS.md")
            write(path, re.sub(r"Built Fri 10-16 21:15", stamp, read(path)))
            if every:
                edit_json(os.path.join(s, "inputs.json"), lambda d: d.update(report={"everyMin": every}))
        assert_passes("fresh-edge", tmp, lambda s, t: built(s, "Built Fri 10-16 20:35"))  # 35 min = 30 + 5
        assert_fails("table-stale", "table-fresh", tmp, lambda s, t: built(s, "Built Fri 10-16 20:34"))
        assert_passes("table-stale-slow-tick", tmp, lambda s, t: built(s, "Built Fri 10-16 20:30", every=60))
        assert_fails("table-stale-fast-tick", "table-fresh", tmp, lambda s, t: built(s, "Built Fri 10-16 20:30", every=15))
        assert_fails("table-no-stamp", "table-fresh", tmp, lambda s, t: built(s, "Rebuilt sometime"))
        assert_fails("table-bad-stamp", "table-fresh", tmp, lambda s, t: built(s, "Built yesterday"))

        # reports-saved: a posted report must be on disk, named YYYY-MM-DD-HHMM[-suffix].md.
        reports = lambda s: os.path.join(s, "reports")  # noqa: E731
        assert_fails("reports-none-saved", "reports-saved", tmp, lambda s, t: os.remove(os.path.join(reports(s), "2026-10-16-2130.md")))
        assert_passes("reports-none-posted", tmp, lambda s, t: (
            os.remove(os.path.join(reports(s), "2026-10-16-2130.md")),
            edit_json(os.path.join(s, "run-state.json"), lambda d: d.update(lastReportedLogRows=0))))
        assert_passes("reports-other-note", tmp, lambda s, t: write(os.path.join(reports(s), "notes.md"), "ok\n"))
        assert_fails("reports-only-untimed", "reports-saved", tmp, lambda s, t: (
            os.remove(os.path.join(reports(s), "2026-10-16-2130.md")), write(os.path.join(reports(s), "notes.md"), "ok\n")))
        assert_passes("reports-suffix", tmp, lambda s, t: write(os.path.join(reports(s), "2026-10-17-0830-final.md"), "ok\n"))
        print("CHECK RUN TEST PASS")
    finally:
        materialize.remove_tree(tmp)


if __name__ == "__main__":
    main()

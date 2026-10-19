"""Self-check for scripts/check_run.py: the good-run fixture passes, and every fail-closed rule and
every parser case (headerless logs, dash or empty time cells, escaped pipes, non-numeric counts) fails by
name. Run: python evals/test_check_run.py   Prints CHECK RUN TEST PASS."""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import check_run  # noqa: E402

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
                      lambda s, t: append(os.path.join(s, "log", "run-log.md"), "| Sat 10-17 08:00 | T2 | a \\| b | - |\n"))
        assert_passes("log-headerless-good", tmp,
                      lambda s, t: write(os.path.join(s, "log", "run-log.md"), "| Sat 10-17 08:00 | T1 | no header | - |\n"))

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
        assert_fails("verdict-pass-counts", "verdict", tmp,
                     lambda s, t: make_stopped(s, t, "PASS (3 of 3 tasks; 1 deferred, 1 by agents)"))
        assert_fails("verdict-none", "verdict", tmp,
                     lambda s, t: edit_json(os.path.join(s, "run-state.json"), lambda d: d.update(verdict=None)))
        assert_fails("run-state-half", "verdict", tmp, lambda s, t: write(os.path.join(s, "run-state.json"), '{"stages": ['))

        # A report with a code in it is refused; progress rows are looked up by task id.
        assert_fails("report-code", "report-plain", tmp,
                     lambda s, t: append(os.path.join(s, "reports", "2026-10-16-2130.md"), "Task T2 passed.\n"))
        assert_fails("row-missing", "table-rows", tmp,
                     lambda s, t: append(os.path.join(s, "tasks.csv"), "T3,Build,new,,\n"))

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
        print("CHECK RUN TEST PASS")
    finally:
        materialize.remove_tree(tmp)


if __name__ == "__main__":
    main()

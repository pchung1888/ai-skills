"""Fill the tick prompt and stage workflow templates from <state-dir>/inputs.json, so every run gets
the same shape and nothing is left unfilled. Refuses to write output that still holds a <PLACEHOLDER>.

  python generate.py tick  --state-dir docs/proj-123/autopilot
      -> <state-dir>/tick-prompt.txt (the CronCreate prompt)
  python generate.py stage --state-dir docs/proj-123/autopilot --spec <state-dir>/stages/s4.json
      -> <state-dir>/stages/s4.js (the Workflow script; launch it with scriptPath)

inputs.json (written at start step 1; read by every script). Example:
  {"goal": "PROJ-123 invoice fixes", "repoPath": "D:\\\\work\\\\myrepo", "branch": "topic/123-fixes",
   "stateDir": "docs/proj-123/autopilot", "weeklyCap": 85, "disks": "C:,D:", "minGB": 1,
   "exclusiveResources": "SQL Server, IIS", "domainCritic": "ping-personal:iris",
   "caps": {"mail": 300, "push": 20}, "sessions": ["7d4f0df1-929c-4862-941e-12ecb5445122"],
   "baseCommit": "4b8d3b26c1f0a9e7d5c3b1a2f4e6d8c0a1b2c3d4", "remote": "origin",
   "remoteTagsAtStart": ["4b8d3b26c1f0a9e7d5c3b1a2f4e6d8c0a1b2c3d4 refs/tags/v1.0"],
   "remoteHeadsAtStart": ["4b8d3b26c1f0a9e7d5c3b1a2f4e6d8c0a1b2c3d4 refs/heads/main"],
   "effort": null, "workerModel": "sonnet", "unattendedSince": "2026-10-17T22:30:00Z"}
  Required: goal, repoPath, branch, stateDir, weeklyCap, disks, minGB, exclusiveResources,
  domainCritic, caps, sessions, baseCommit, remoteTagsAtStart, remoteHeadsAtStart.
  baseCommit: the commit HEAD pointed at when the run started (git rev-parse HEAD); "changed by this run" means
         shown by git diff <baseCommit>.
  remote: git remote the run may push to (default "origin"). remoteTagsAtStart / remoteHeadsAtStart: the lines of
         git ls-remote --tags / --heads <remote> at start, each "<sha> <ref>"; check_run.py compares against them.
  caps: side-effect kind -> total allowed; a kind not listed has cap 0.
  sessions: every session id the run has used (start writes the first, resume appends).
  The CURRENT session id comes from CLAUDE_CODE_SESSION_ID and must be in sessions, else this fails.
  Optional: effort ("low" on Fable, null to inherit on Opus), workerModel ("sonnet" or null to inherit),
  unattendedSince (ISO 8601 UTC with Z; a naive time is read as UTC),
  report: the report shape the user chose at start. Example: {"everyMin": 15, "style": "copilot", "taskList": true, "ids": true}
         everyMin: tick and report interval, 10, 15, 20, 30 or 60 (default 30); style: "plain" (default) or
         "copilot" (narrated, for short weekday runs); taskList: add the full task list; ids: allow task ids.

Stage spec (one per stage). A step is a task, or a list of 1-2 tasks run in parallel. Example:
  {"name": "s3-build", "summary": "spikes, then parallel code, then fresh-eyes review",
   "steps": [{"id": "T5", "agent": "ping-personal:vex", "phase": "Spikes", "text": "Probe the API limits"},
             [{"id": "T2", "agent": "ping-personal:bunny", "phase": "Code", "commits": true,
               "resources": ["SQL Server"], "needs": ["T5"]},
              {"id": "T3", "agent": "ping-personal:vex", "phase": "Code", "model": "inherit"}]],
   "review": "T3", "reviewer": "ping-personal:iris"}
  agent: ping-personal:<x> (agents/<x>.md must exist), general-purpose, Explore or Plan.
         codex:codex-rescue is allowed only as inputs.json domainCritic.
  model: "worker" (default, uses workerModel) or "inherit" (the session model).
  needs: task ids that must have passed; ids outside this spec count as already passed (a retry spec).
  commits: true lets the task git commit; the agent's tools line must include Bash.
         Every task agent must have the Write tool (a task always writes its output); ms-mario is a critic seat only.
  resources: exclusive resources the task uses; two tasks of one parallel group may not share one.
  text: task text for the agent. A task without it needs a heading containing "Task <id>" in
        <state-dir>/plan.md (example: "## Task T3 - install"), else this fails naming the task.
  check: REQUIRED. The task's own fast, scoped check command (one test file, one script), never the full done
        command. The verifier runs this command. Example: "python -m pytest tests/test_invoice.py -q".
  estimateK: REQUIRED. Expected context size of the task in thousands of tokens; over 100 is refused.
  passLine: optional exact last line the done-check must print; the task passes only if the verifier
        passed AND its last line, trimmed, equals this.
  reviewer: agent for the fresh-eyes review (default ping-personal:iris).
Per spec (optional):
  stageCheck: {"command": "<full done command>", "passLine": "<exact last line>"}. After every task, one verifier
        runs the full done command once; the result is returned as stageCheck {passed, lastLine}.
  finalReview: true on the last stage. Replaces review/reviewer with two fresh reviewers run one after the other:
        Spec (ping-personal:amanda, git diff <baseCommit>...HEAD against GOAL-BRIEF.md) and Standards
        (ping-personal:ms-mario, repo standards files and CLAUDE.md). Results are never merged.
"""
import argparse
import json
import os
import re

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(SKILL_DIR, "references")
AGENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(SKILL_DIR)), "agents")
PLACEHOLDER = re.compile(r"<[A-Z][A-Z0-9_]*>")
REQUIRED = ["goal", "repoPath", "branch", "stateDir", "weeklyCap", "disks", "minGB",
            "exclusiveResources", "domainCritic", "caps", "sessions", "baseCommit", "remoteTagsAtStart", "remoteHeadsAtStart"]
# One task must fit one fresh context: past about 100K tokens the quality of the agent's work drops.
MAX_ESTIMATE_K = 100
MAX_PARALLEL = 2  # leaves room for the background reporter so the box never runs more than 3 agents
OTHER_AGENTS = ("general-purpose", "Explore", "Plan")  # agents with no file in agents/
CRITIC_ONLY = ("codex:codex-rescue",)  # allowed as domainCritic, never as a task agent or reviewer
READ_ONLY_AGENTS = ("Explore", "Plan")  # cannot run git or write files
REPORT_EVERY = (10, 15, 20, 30, 60)  # minutes that divide the hour, so the tick fires at fixed minutes


def fail(msg):
    raise SystemExit(f"GENERATE FAIL: {msg}")


def load_inputs(state_dir):
    path = os.path.join(state_dir, "inputs.json")
    if not os.path.exists(path):
        fail(f"{path} not found. Write it at start step 1 (shape in this script's docstring).")
    with open(path, encoding="utf-8-sig") as f:
        inputs = json.load(f)
    missing = [k for k in REQUIRED if k not in inputs or inputs[k] is None or inputs[k] == ""]
    if missing:
        fail(f"inputs.json is missing: {', '.join(missing)}")
    if not isinstance(inputs["caps"], dict) or not isinstance(inputs["sessions"], list) or not inputs["sessions"]:
        fail("inputs.json: caps must be an object and sessions a non-empty list")
    for k in ("remoteTagsAtStart", "remoteHeadsAtStart"):
        if not isinstance(inputs[k], list):
            fail(f"inputs.json: {k} must be a list of '<sha> <ref>' lines")
    inputs["sessionId"] = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not inputs["sessionId"]:
        fail("CLAUDE_CODE_SESSION_ID is not set")
    if inputs["sessionId"] not in inputs["sessions"]:
        fail(f"current session {inputs['sessionId']} is not in inputs.json sessions; append it (resume step)")
    check_agent(inputs["domainCritic"], "domainCritic", critic=True)
    report = inputs.get("report") or {}
    if not isinstance(report, dict) or report.get("everyMin", 30) not in REPORT_EVERY \
            or report.get("style", "plain") not in ("plain", "copilot"):
        fail(f"inputs.json report: everyMin one of {REPORT_EVERY}, style 'plain' or 'copilot'")
    inputs["report"] = report
    return inputs


def report_shape(report):
    """One line for the reporter brief naming the shape the user chose at start."""
    words = ["copilot" if report.get("style") == "copilot" else "plain"]
    if report.get("taskList"):
        words.append("with the full task list")
    if report.get("ids"):
        words.append("task ids allowed")
    return ", ".join(words)


def fill(text, values):
    for k, v in values.items():
        text = text.replace(f"<{k}>", str(v))
    return text


def check_filled(text, what):
    left = sorted(set(PLACEHOLDER.findall(text)))
    if left:
        fail(f"{what} still holds {', '.join(left)}")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(path)


def tick(state_dir):
    i = load_inputs(state_dir)
    with open(os.path.join(REFS, "cron-tick.prompt.md"), encoding="utf-8") as f:
        prompt = re.search(r"```text\n(.*?)```", f.read(), re.S).group(1)
    quota_dir = os.path.join(os.path.dirname(SKILL_DIR), "personal-quota").replace("\\", "/")
    every = i["report"].get("everyMin", 30)
    text = fill(prompt, {
        "GOAL": i["goal"], "STATE_DIR": i["stateDir"], "SESSION_ID": i["sessionId"],
        "QUOTA_PS1": f"{quota_dir}/quota.ps1", "SKILL_DIR": SKILL_DIR.replace("\\", "/"),
        "EVERY": every, "REPORT_SHAPE": report_shape(i["report"]),
    })
    check_filled(text, "tick prompt")
    write(os.path.join(state_dir, "tick-prompt.txt"), text)
    print("cron: " + ",".join(str(m) for m in range(7 % every, 60, every)) + " * * * *")


def agent_tools(name):
    """The tools line of agents/<x>.md, or None when the file has no tools line (it inherits every tool)."""
    with open(os.path.join(AGENTS_DIR, name.split(":", 1)[1] + ".md"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("tools:"):
                return line[len("tools:"):]
    return None


def check_agent(name, where, critic=False):
    if name in OTHER_AGENTS or (critic and name in CRITIC_ONLY):
        return
    ok = re.fullmatch(r"ping-personal:[a-z0-9-]+", str(name)) and \
        os.path.exists(os.path.join(AGENTS_DIR, name.split(":", 1)[1] + ".md"))
    if not ok:
        fail(f"{where}: agent '{name}' is not ping-personal:<x> with agents/<x>.md present, "
             f"nor one of {', '.join(OTHER_AGENTS + (CRITIC_ONLY if critic else ()))}")


def has_plan_heading(state_dir, task_id):
    """True when plan.md has a heading line naming the task. Example: "## Task T3 - install"."""
    try:
        with open(os.path.join(state_dir, "plan.md"), encoding="utf-8-sig") as f:
            text = f.read()
    except OSError:
        return False
    return re.search(rf"^#+ .*Task {re.escape(task_id)}\b", text, re.M) is not None


def check_task(t, n, state_dir):
    for k in ("id", "agent", "phase"):
        if not t.get(k):
            fail(f"step {n} has a task without '{k}'")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", str(t["id"])):
        fail(f"task id {t['id']!r}: use 1-16 letters, digits, '-' or '_' (it goes into a shell command). Example: T3")
    check_agent(t["agent"], f"task {t['id']}")
    no_write = t["agent"] in READ_ONLY_AGENTS or \
        (t["agent"] not in OTHER_AGENTS and "Write" not in (agent_tools(t["agent"]) or "Write"))
    if no_write:
        fail(f"task {t['id']}: agent {t['agent']} has no Write tool, so it cannot write its output; "
             "give a critic or review task to ping-personal:rhea or ping-personal:iris")
    if not t.get("text") and not has_plan_heading(state_dir, t["id"]):
        fail(f"task {t['id']} has no 'text' and {state_dir}/plan.md has no heading containing 'Task {t['id']}'")
    if "passLine" in t and not (isinstance(t["passLine"], str) and t["passLine"].strip()):
        fail(f"task {t['id']}: passLine must be a non-empty string")
    if not (isinstance(t.get("check"), str) and t["check"].strip()):
        fail(f"task {t['id']} has no 'check': give its own fast, scoped check command (one test file, one script), "
             "never the full done command")
    est = t.get("estimateK")
    if est is None or isinstance(est, bool) or not isinstance(est, (int, float)) or est <= 0:
        fail(f"task {t['id']} has no 'estimateK': expected context size in thousands of tokens, a number above 0")
    if est > MAX_ESTIMATE_K:
        fail(f"task {t['id']}: estimateK {est:g} is over {MAX_ESTIMATE_K}; "
             "split it: one task must fit one fresh context (about 100K, beyond which quality drops)")
    if t.get("model", "worker") not in ("worker", "inherit"):
        fail(f"task {t['id']}: model must be 'worker' or 'inherit'")
    for k in ("needs", "resources"):
        if not isinstance(t.get(k, []), list):
            fail(f"task {t['id']}: {k} must be a list")
    if t.get("commits"):
        no_bash = t["agent"] in READ_ONLY_AGENTS or \
            (t["agent"] not in OTHER_AGENTS and "Bash" not in (agent_tools(t["agent"]) or "Bash"))
        if no_bash:
            fail(f"task {t['id']}: commits is true but agent {t['agent']} has no Bash tool")


def stage_body(spec, state_dir):
    steps = [s if isinstance(s, list) else [s] for s in spec["steps"]]
    lines, current_phase, ids, step_of = [], None, [], {}
    for n, group in enumerate(steps, 1):
        if not group:
            fail(f"step {n} is an empty group")
        if len(group) > MAX_PARALLEL:
            fail(f"step {n} runs {len(group)} tasks in parallel; the limit is {MAX_PARALLEL}")
        used = {}
        for t in group:
            check_task(t, n, state_dir)
            ids.append(t["id"])
            step_of[t["id"]] = n
            for res in (r.strip().lower() for r in t.get("resources", [])):
                if res in used:
                    fail(f"tasks {used[res]} and {t['id']} in step {n} both use resource '{res}'; "
                         "put them in separate steps")
                used[res] = t["id"]
    if len(ids) != len(set(ids)):
        fail("a task id appears twice in the stage spec")
    for n, group in enumerate(steps, 1):
        if group[0]["phase"] != current_phase:
            current_phase = group[0]["phase"]
            lines.append(f"phase({json.dumps(current_phase)})")
        calls = []
        for t in group:
            needs = [x for x in t.get("needs", []) if x in step_of]  # ids outside this spec already passed
            if any(step_of[x] >= n for x in needs):
                fail(f"task {t['id']} needs a task in the same or a later step")
            model = "WORKER_MODEL" if t.get("model", "worker") == "worker" else "undefined"
            calls.append(f"run({json.dumps(t['id'])}, {json.dumps(t['agent'])}, {json.dumps(t['phase'])}, {model}, "
                         f"{json.dumps(needs)}, {json.dumps(bool(t.get('commits')))}, {json.dumps(t.get('text', ''))}, "
                         f"{json.dumps(t.get('passLine', ''))}, {json.dumps(t['check'])})")
        if len(group) == 1:
            lines.append(f"results[{json.dumps(group[0]['id'])}] = await {calls[0]}")
        else:
            lines.append(f"const g{n} = await parallel([{', '.join('() => ' + c for c in calls)}])")
            lines += [f"results[{json.dumps(t['id'])}] = g{n}[{k}]" for k, t in enumerate(group)]
        lines += ["if (halt.by) return done()", ""]
    sc = spec.get("stageCheck")
    if sc is not None:
        if not (isinstance(sc, dict) and isinstance(sc.get("command"), str) and sc["command"].strip()
                and isinstance(sc.get("passLine", ""), str)):
            fail("stageCheck must be {\"command\": \"<full done command>\", \"passLine\": \"<exact last line>\"}")
        lines += ["phase('Stage check')",
                  f"await stageCheck({json.dumps(sc['command'])}, {json.dumps(sc.get('passLine', ''))})", ""]
    review = spec.get("review")
    final = spec.get("finalReview")
    if final is not None and not isinstance(final, bool):
        fail("finalReview must be true or false")
    if final and (review or spec.get("reviewer")):
        fail("finalReview replaces review and reviewer: give finalReview alone")
    if final:
        lines += ["phase('Review')", "return done(await finalReview())"]
    elif review:
        if review not in ids:
            fail(f"review task {review} is not a step in this stage")
        reviewer = spec.get("reviewer", "ping-personal:iris")
        check_agent(reviewer, "reviewer")
        lines += ["phase('Review')", f"return done(await review({json.dumps(review)}, {json.dumps(reviewer)}))"]
    else:
        lines.append("return done()")
    phases = []
    for g in steps:
        for t in g:
            if t["phase"] not in phases:
                phases.append(t["phase"])
    if sc is not None:
        phases.append("Stage check")
    if review or final:
        phases.append("Review")
    return phases, "\n".join(lines) + "\n"


def stage(state_dir, spec_path):
    i = load_inputs(state_dir)
    with open(spec_path, encoding="utf-8-sig") as f:
        spec = json.load(f)
    for k in ("name", "summary", "steps"):
        if not spec.get(k):
            fail(f"stage spec is missing '{k}'")
    with open(os.path.join(REFS, "stage-workflow.template.js"), encoding="utf-8") as f:
        template = f.read()
    head = template.split("// ---- stage body", 1)[0]
    phases, body = stage_body(spec, state_dir)
    slug = re.sub(r"[^a-z0-9]+", "-", i["goal"].lower()).strip("-")[:24]
    meta = ("export const meta = {\n"
            f"  name: {json.dumps(slug + '-' + spec['name'])},\n"
            f"  description: {json.dumps(spec['summary'])},\n"
            f"  phases: [{', '.join('{ title: ' + json.dumps(p) + ' }' for p in phases)}],\n"
            "}\n")
    head = re.sub(r"export const meta = \{.*?\n\}\n", lambda _: meta, head, count=1, flags=re.S)
    text = fill(head, {
        "GOAL": json.dumps(i["goal"]), "REPO_PATH": json.dumps(i["repoPath"]), "BRANCH": json.dumps(i["branch"]),
        "STATE_DIR": json.dumps(i["stateDir"]), "BASE_COMMIT": json.dumps(i["baseCommit"]), "EXCLUSIVE_RESOURCES": json.dumps(i["exclusiveResources"]),
        "DISKS": json.dumps(i["disks"]), "MIN_GB": json.dumps(i["minGB"]),
        "EFFORT": json.dumps(i["effort"]) if i.get("effort") else "undefined",
        "WORKER_MODEL": json.dumps(i["workerModel"]) if i.get("workerModel") else "undefined",
        "DOMAIN_CRITIC": json.dumps(i["domainCritic"]), "SKILL_DIR": json.dumps(SKILL_DIR.replace("\\", "/")),
    }) + "// ---- stage body (generated from " + os.path.basename(spec_path) + ") ----\n" + body
    # Template comments name placeholders as examples; only code lines must be filled.
    code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("//"))
    check_filled(code, "stage script")
    out = os.path.join(os.path.dirname(os.path.abspath(spec_path)), spec["name"] + ".js")
    write(out, text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=["tick", "stage"])
    ap.add_argument("--state-dir", required=True, help="state folder holding inputs.json. Example: docs/proj-123/autopilot")
    ap.add_argument("--spec", help="stage spec JSON (stage only). Example: docs/proj-123/autopilot/stages/s4.json")
    a = ap.parse_args()
    if a.what == "tick":
        tick(a.state_dir)
    else:
        if not a.spec:
            fail("stage needs --spec <stage spec json>")
        stage(a.state_dir, a.spec)

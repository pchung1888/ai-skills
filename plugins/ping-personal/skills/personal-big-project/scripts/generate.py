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
  projectSteps: steps this run adds to every tick, each with its condition (filled into the tick prompt).
         Example: ["After s1-plan has a RESULT, run personal-critic-judge on plan.md"]
  effort / reviewEffort: worker effort and critic-judge/code-review effort, asked at the door. Example: "low", "medium"
  baselineChangesApproved: baselined files the plan must change, approved by the owner at the door.
         check_run.py accepts their change. Example: ["web/MasterInclude.asp"]
  protectedBranches: branches no agent may push, from pre-flight check 14: the target branch of every open
         review request (pushing to it can merge the request). log_row.py effect --kind push refuses them.
         Example: ["feature/123"]

Stage spec (one per stage). A step is a task, or a list of 1-2 tasks run in parallel. Example:
  {"name": "s3-build", "summary": "spikes, then parallel code, then fresh-eyes review",
   "steps": [{"id": "T5", "agent": "ping-personal:vex", "phase": "Spikes", "text": "Probe the API limits"},
             [{"id": "T2", "agent": "ping-personal:bunny", "phase": "Code", "commits": true,
               "resources": ["SQL Server"], "needs": ["T5"]},
              {"id": "T3", "agent": "ping-personal:vex", "phase": "Code", "model": "inherit"}]],
   "review": "T3", "reviewer": "ping-personal:iris"}
  agent: ping-personal:<x> (agents/<x>.md must exist), general-purpose, Explore or Plan.
         codex:codex-rescue is allowed only as inputs.json domainCritic.
  model: "worker" (default, uses workerModel), "inherit" (the session model) or "advisor" (inputs.json advisorModel,
         for a task or a review step that needs a stronger model). Example inputs.json: "advisorModel": "fable"
  Tool check: a task whose text or plan.md section names "<Tool> tool" (Edit, Bash, Write, WebFetch, WebSearch)
         that its agent lacks is refused, unless the mention is negated ("never use the Bash tool"): agents once
         lost 3-16 calls each on tools their brief named but their type did not have.
  needs: task ids that must have passed; ids outside this spec count as already passed (a retry spec).
  commits: true lets the task git commit; the agent's tools line must include Bash.
         Every task agent must have the Write tool (a task always writes its output); ms-mario is a critic seat only.
  resources: exclusive resources the task uses; two tasks of one parallel group may not share one.
  text: task text for the agent. A task without it needs a heading containing "Task <id>" in
        <state-dir>/plan.md (example: "## Task T3 - install"), else this fails naming the task.
  check: REQUIRED. The task's own fast, scoped check command (one test file, one script), never the full done
        command. The verifier runs this command. Example: "python -m pytest tests/test_invoice.py -q".
        A string that chains commands with " ; ", " && ", " || " or a newline is refused: a hand-joined chain
        hides which part failed and behaves differently in cmd, bash and PowerShell. Give a list instead:
        "check": ["python -m pytest tests/test_a.py -q", "python tools/lint.py"]. For a list, generate.py writes
        <state-dir>/checks/<task id>.json and replaces the check with
        python "<skill>/scripts/run_check.py" "<that json>", and sets passLine to "<id> CHECK PASS".
        Each command runs in order through the shell (cmd.exe on Windows) and all must exit 0.
  expect: optional "pass" (default) or "fail". "fail" marks a RED task: its test must FAIL because the code it
        tests does not exist yet. generate.py then writes the same checks JSON (expect "fail") and sets passLine
        to "<id> RED PASS"; run_check.py prints that only when every command exits non-zero. A passLine in the
        spec of a list-check or RED task is refused (generate.py owns it). A plain string check with expect
        "pass" stays as written.
        Example: {"id": "T3", "expect": "fail", "redFile": "tests/**/test_invoice.*", "check": "python -m pytest tests/test_invoice.py -q"}
  redFile: optional, with expect "fail": a glob (relative to the folder the checks run in) that must match a
        file, so a missing test file cannot pass as RED.
  ui: optional true or false. check_run.py's ui-browser check reads it: true makes the task a UI task, false
        opts it out even when its text or check names a .html/.tsx page (review and evidence tasks). Must be a bool.
        Two tasks with the same check (and passLine), or a check equal to stageCheck.command, are refused:
        such a check stays FAIL until the last task is done. sharedCheck: true on both tasks allows it
        when each task alone makes the check pass.
  estimateK: REQUIRED. Expected context size of the task in thousands of tokens; over 100 is refused.
  passLine: optional exact last line the done-check must print; the task passes only if the verifier
        passed AND its last line, trimmed, equals this.
  kind: "task" (default) or "review". A review step is a read-only agent (ms-mario, a judge seat, Explore,
        codex:codex-rescue) that returns findings inside the stage; run_state.py saves them to reviews/<id>.md
        and counts the open HIGH/CRITICAL ones. It has no check, passLine, needs or commits, needs no Write
        tool, and passes once it answers. Example: {"id": "J1", "agent": "ping-personal:ms-mario",
        "phase": "Judge", "kind": "review", "text": "judge the plan against GOAL-BRIEF.md", "estimateK": 30}
  reviewer: agent for the fresh-eyes review (default ping-personal:iris).
Per spec (optional):
  estimateTokens: whole number above 0, the stage's expected total tokens (all agents). run_state.py reads it
        from the spec file to re-estimate the run after each stage. Only the type is checked here.
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
CHAINED = re.compile(r" ; | && | \|\| |\n")  # a hand-joined chain of commands in one string
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
    protected = inputs.get("protectedBranches", [])
    if not isinstance(protected, list) or not all(isinstance(b, str) and b.strip() for b in protected):
        fail("inputs.json protectedBranches: a list of branch names. Example: [\"feature/123\"]")
    return inputs


def report_shape(report):
    """One line for the reporter brief naming the shape the user chose at start."""
    words = ["copilot" if report.get("style") == "copilot" else "plain"]
    if report.get("taskList"):
        words.append("with the full task list")
    if report.get("ids"):
        words.append("task ids allowed")
    return ", ".join(words)


def project_steps(steps):
    """inputs.json projectSteps as numbered tick-prompt lines; "   none" when there are none."""
    if steps in (None, []):
        return "   none"
    if not isinstance(steps, list) or not all(isinstance(x, str) and x.strip() for x in steps):
        fail("inputs.json projectSteps: a list of plain-words steps, each with its condition. "
             "Example: [\"After s1-plan has a RESULT, run personal-critic-judge on plan.md\"]")
    return "\n".join(f"   {n}. {' '.join(x.split())}" for n, x in enumerate(steps, 1))


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
        "PROJECT_STEPS": project_steps(i.get("projectSteps")),
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


def refuse_chain(command, task_id):
    if CHAINED.search(command):
        fail(f"task {task_id}: the check chains commands with ' ; ', ' && ', ' || ' or a newline; a hand-joined chain "
             "hides which part failed and behaves differently in cmd, bash and PowerShell. "
             "Give 'check' as a list of commands instead.")


def prepare_check(t, state_dir, write_checks):
    """List checks and RED tasks run through run_check.py: write <state-dir>/checks/<id>.json (when
    write_checks) and replace the task's check and passLine. A plain string check with expect pass is left alone."""
    expect = t.get("expect", "pass")
    if expect not in ("pass", "fail"):
        fail(f"task {t['id']}: expect must be 'pass' or 'fail'")
    if "redFile" in t and not (isinstance(t["redFile"], str) and t["redFile"].strip() and expect == "fail"):
        fail(f"task {t['id']}: redFile is a non-empty glob string and needs expect: \"fail\"")
    check = t.get("check")
    if isinstance(check, list):
        if not check or not all(isinstance(c, str) and c.strip() for c in check):
            fail(f"task {t['id']}: a list check holds one or more non-empty command strings")
        commands = [c.strip() for c in check]
    elif isinstance(check, str) and check.strip():
        commands = [check.strip()]
    else:
        return  # the missing-check refusal in check_task names it
    for c in commands:
        refuse_chain(c, t["id"])
    if not isinstance(check, list) and expect == "pass":
        return
    if "passLine" in t:
        fail(f"task {t['id']}: a list check or RED task gets its passLine from generate.py; remove passLine")
    doc = {"task": t["id"], "commands": commands, "expect": expect}
    if t.get("redFile"):
        doc["file"] = t["redFile"].strip()
    path = os.path.abspath(os.path.join(state_dir, "checks", f"{t['id']}.json"))
    if write_checks:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=1)
    t["_commands"] = commands  # keeps the same-check refusal working after the check text becomes a path
    t["check"] = f'python "{SKILL_DIR.replace(chr(92), "/")}/scripts/run_check.py" "{path.replace(chr(92), "/")}"'
    t["passLine"] = f"{t['id']} {'RED' if expect == 'fail' else 'CHECK'} PASS"


TOOL_WORDS = re.compile(r"(?<![\w-])(Edit|Bash|Write|WebFetch|WebSearch) tool\b")
NEGATED = re.compile(r"\b(no|not|never|without|don't|do not)\b[^.;\n]{0,20}$", re.I)


def plan_section(state_dir, task_id):
    """The text under plan.md's 'Task <id>' heading, up to the next heading, or ''."""
    try:
        with open(os.path.join(state_dir, "plan.md"), encoding="utf-8-sig") as f:
            text = f.read()
    except OSError:
        return ""
    m = re.search(rf"^#+ .*Task {re.escape(task_id)}\b.*$", text, re.M)
    if not m:
        return ""
    nxt = re.search(r"^#+ ", text[m.end():], re.M)
    return text[m.end():m.end() + nxt.start()] if nxt else text[m.end():]


def check_tools(t, state_dir):
    """Refuse a brief that tells the agent to use a tool its type lacks."""
    if t["agent"] in OTHER_AGENTS and t["agent"] not in READ_ONLY_AGENTS:
        return
    tools = "Read, Grep, Glob" if t["agent"] in READ_ONLY_AGENTS else (agent_tools(t["agent"]) or "")
    if t["agent"] not in READ_ONLY_AGENTS and agent_tools(t["agent"]) is None:
        return  # no tools line: the agent inherits every tool
    brief = t.get("text", "") + "\n" + plan_section(state_dir, t["id"])
    for m in TOOL_WORDS.finditer(brief):
        if m.group(1) not in tools and not NEGATED.search(brief[max(0, m.start() - 40):m.start()]):
            fail(f"task {t['id']}: its brief names the {m.group(1)} tool, but agent {t['agent']} has no {m.group(1)} "
                 "tool; give the task to an agent that has it, or reword the brief")


def check_task(t, n, state_dir, write_checks=True, advisor=None):
    for k in ("id", "agent", "phase"):
        if not t.get(k):
            fail(f"step {n} has a task without '{k}'")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", str(t["id"])):
        fail(f"task id {t['id']!r}: use 1-16 letters, digits, '-' or '_' (it goes into a shell command). Example: T3")
    kind = t.get("kind", "task")
    if kind not in ("task", "review"):
        fail(f"task {t['id']}: kind must be 'task' or 'review'")
    review = kind == "review"
    check_agent(t["agent"], f"task {t['id']}", critic=review)
    if review and (t.get("commits") or t.get("needs") or "check" in t or "passLine" in t):
        fail(f"review step {t['id']}: a review step only returns findings; it takes no commits, needs, check or "
             "passLine (put it in an earlier step than the tasks that use its findings)")
    no_write = t["agent"] in READ_ONLY_AGENTS or \
        (t["agent"] not in OTHER_AGENTS and "Write" not in (agent_tools(t["agent"]) or "Write"))
    if no_write and not review:
        fail(f"task {t['id']}: agent {t['agent']} has no Write tool, so it cannot write its output; "
             "give it to an agent with Write, or make it a review step (kind: review)")
    if not t.get("text") and not has_plan_heading(state_dir, t["id"]):
        fail(f"task {t['id']} has no 'text' and {state_dir}/plan.md has no heading containing 'Task {t['id']}'")
    if "passLine" in t and not (isinstance(t["passLine"], str) and t["passLine"].strip()):
        fail(f"task {t['id']}: passLine must be a non-empty string")
    if "ui" in t and not isinstance(t["ui"], bool):
        fail(f"task {t['id']}: ui must be true or false")
    if not review:
        prepare_check(t, state_dir, write_checks)
    if not review and not (isinstance(t.get("check"), str) and t["check"].strip()):
        fail(f"task {t['id']} has no 'check': give its own fast, scoped check command (one test file, one script), "
             "never the full done command")
    est = t.get("estimateK")
    if est is None or isinstance(est, bool) or not isinstance(est, (int, float)) or est <= 0:
        fail(f"task {t['id']} has no 'estimateK': expected context size in thousands of tokens, a number above 0")
    if est > MAX_ESTIMATE_K:
        fail(f"task {t['id']}: estimateK {est:g} is over {MAX_ESTIMATE_K}; "
             "split it: one task must fit one fresh context (about 100K, beyond which quality drops)")
    if t.get("model", "worker") not in ("worker", "inherit", "advisor"):
        fail(f"task {t['id']}: model must be 'worker', 'inherit' or 'advisor'")
    if t.get("model") == "advisor" and not advisor:
        fail(f"task {t['id']}: model 'advisor' needs inputs.json advisorModel. Example: \"advisorModel\": \"fable\"")
    check_tools(t, state_dir)
    for k in ("needs", "resources"):
        if not isinstance(t.get(k, []), list):
            fail(f"task {t['id']}: {k} must be a list")
    if t.get("commits"):
        no_bash = t["agent"] in READ_ONLY_AGENTS or \
            (t["agent"] not in OTHER_AGENTS and "Bash" not in (agent_tools(t["agent"]) or "Bash"))
        if no_bash:
            fail(f"task {t['id']}: commits is true but agent {t['agent']} has no Bash tool")


def check_checks(tasks, stage_check):
    """Each task's check must be able to pass from that task's own work. The same check on two tasks, or
    the stage's full done command as a task check, stays FAIL until the last task is done, so the first
    task fails, the stage stops and the retry repeats every task (about 1.2M tokens in one run)."""
    full = (stage_check or {}).get("command", "").strip() if isinstance(stage_check, dict) else ""
    seen = {}
    for t in (t for t in tasks if t.get("kind") != "review"):
        key = (json.dumps([t["_commands"], t.get("expect")]), "") if "_commands" in t             else (t["check"].strip(), str(t.get("passLine", "")).strip())
        if full and key[0] == full:
            fail(f"task {t['id']}: its check is the stage's full done command; give the task its own scoped check")
        if key in seen and not (t.get("sharedCheck") and seen[key].get("sharedCheck")):
            fail(f"tasks {seen[key]['id']} and {t['id']} have the same check; a shared check stays FAIL until both "
                 "are done, so the first one fails. Give each its own scoped check, or set sharedCheck: true on both "
                 "when each one alone makes it pass")
        seen.setdefault(key, t)


def stage_body(spec, state_dir, write_checks=True, advisor=None):
    """(phases, script body) of a stage spec; fails on a bad spec. Task dicts are changed in place (list
    and RED checks become run_check.py commands); write_checks False skips writing the checks JSON files."""
    est = spec.get("estimateTokens")
    if "estimateTokens" in spec and (isinstance(est, bool) or not isinstance(est, int) or est <= 0):
        fail("estimateTokens must be a whole number above 0 (the stage's expected total tokens)")
    steps = [s if isinstance(s, list) else [s] for s in spec["steps"]]
    lines, current_phase, ids, step_of = [], None, [], {}
    for n, group in enumerate(steps, 1):
        if not group:
            fail(f"step {n} is an empty group")
        if len(group) > MAX_PARALLEL:
            fail(f"step {n} runs {len(group)} tasks in parallel; the limit is {MAX_PARALLEL}")
        used = {}
        for t in group:
            check_task(t, n, state_dir, write_checks, advisor)
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
            m = t.get("model", "worker")
            model = "WORKER_MODEL" if m == "worker" else json.dumps(advisor) if m == "advisor" else "undefined"
            needs = [x for x in t.get("needs", []) if x in step_of]  # ids outside this spec already passed
            if any(step_of[x] >= n for x in needs):
                fail(f"task {t['id']} needs a task in the same or a later step")
            if t.get("kind") == "review":  # read-only agent: findings only, no verifier, no commit
                calls.append(f"reviewStep({json.dumps(t['id'])}, {json.dumps(t['agent'])}, {json.dumps(t['phase'])}, "
                             f"{json.dumps(t.get('text', ''))}, {'undefined' if model == 'WORKER_MODEL' else model})")
                continue
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
    check_checks([t for group in steps for t in group], sc)
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
    phases, body = stage_body(spec, state_dir, advisor=i.get("advisorModel"))
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

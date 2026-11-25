"""Turn one stage of a plan file into a stage spec, plan.md sections and tasks.csv rows, so stage specs are
never typed by hand. It validates the spec with generate.py first and writes nothing when that fails.

  python plan_to_stage.py --state-dir docs/proj-123/autopilot --plan docs/proj-123/PLAN.md --stage s2-build
  python plan_to_stage.py ... --spec-only        write only <state-dir>/stages/<stage>.json
  python plan_to_stage.py ... --review T4        add review T4 (reviewer from --reviewer, default ping-personal:iris)

Plan file shape. A stage is a heading "## Stage <name>" followed by a markdown table whose header row names
its columns (any order; the first table under the heading is used). Example:
  ## Stage s2-build

  | id | agent | what | needs | resources | commits | check | passLine | estimateK |
  |---|---|---|---|---|---|---|---|---|
  | S2-1 | bunny | write the parser | - | - | y | `python -m pytest tests/test_a.py -q` | S2-1 PASS | 30 |
  | S2-2 | vex | write its test | S2-1 | SQL Server | n | `python a.py`<br>`python b.py` | | 20 |
  | S2-3 | bunny | wire it up | S2-1..S2-2 | - | y | `python -m pytest tests/test_w.py` | fails before | 25 |
Required columns: id, agent, what, check, estimateK. Optional: needs, resources, commits, passLine, and the extras
expect, ui, phase, redFile, kind, model. Each task also needs a heading "## Task <id>" (any level) in the plan; its text, up to
the next heading of the same or a higher level, is the agent's instructions.
Cell rules:
  agent       "bunny" becomes "ping-personal:bunny"; a value with ":" is kept.
  needs       ids separated by commas or spaces; "-" or empty is none; "S2-1..S2-4" is S2-1, S2-2, S2-3, S2-4.
  resources   comma list; "-" is none.   commits  y, yes or true.   ui  y/yes/true or n/no/false (empty leaves it out).
  check       backticks are removed; several commands separated by "<br>" or " ;; " become a list check.
  passLine    kept only when it contains PASS. "fails before" or "exits 1 before" in that cell, or expect = fail,
              marks a RED task (generate.py then sets "<id> RED PASS").
  redFile     glob of the test file a RED task must have written. Example: tests/**/test_a.*
  kind        "review" makes the row a review step (a read-only seat returning findings): its check, passLine,
              needs and commits cells are ignored. Empty is a normal task.
  model       worker (default), inherit or advisor (inputs.json advisorModel). Example: advisor
Steps: consecutive tasks run as a parallel pair when neither needs the other, they share no resource and neither
commits (at most 2, generate.py's MAX_PARALLEL); otherwise a task runs alone.
Baseline first: while <state-dir>/baseline-hashes.txt does not exist, a stage with a committing task is refused
unless one of its tasks names "log_row.py baseline" in its check or its "## Task <id>" text (SKILL.md rule 3).
Example task text: Run log_row.py baseline --state-dir <state-dir> web/expected.csv (or baseline --none).
Writes <state-dir>/stages/<stage>.json {name, summary, steps[, review, reviewer]}. Unless --spec-only it also
appends "## Task <id> - <what>" sections to <state-dir>/plan.md under "# Stage <stage> (copied from <plan> at
Day MM-DD HH:MM)" and "id,stage,what,estimate,added" rows to <state-dir>/tasks.csv. A task id already in tasks.csv, or
a "Task <id>" heading already in plan.md, is skipped and printed, so a re-run adds nothing twice.
"""
import argparse
import copy
import csv
import json
import os
import re
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import generate  # noqa: E402
import statefiles  # noqa: E402

TRUE = ("y", "yes", "true")
FALSE = ("n", "no", "false")
RED_WORDS = re.compile(r"(fails|exits 1) before", re.I)


def die(msg):
    raise SystemExit(f"PLAN_TO_STAGE FAIL: {msg}")


def parse_table(text, stage):
    """Dicts (column name -> cell) of the first table under '## Stage <stage>'."""
    head = re.search(rf"^## Stage {re.escape(stage)}[ \t]*$", text, re.M)
    if not head:
        die(f"no '## Stage {stage}' heading in the plan")
    rest = text[head.end():]
    nxt = re.search(r"^## Stage ", rest, re.M)
    lines = (rest[:nxt.start()] if nxt else rest).splitlines()
    start = next((i for i, l in enumerate(lines)
                  if l.lstrip().startswith("|") and statefiles.split_row(l)[0].strip().lower() == "id"), None)
    if start is None:
        die(f"stage {stage} has no table whose header row starts with 'id'")
    names = [c.strip().lower() for c in statefiles.split_row(lines[start])]
    for need in ("id", "agent", "what", "check", "estimatek"):
        if need not in names:
            die(f"stage {stage} table has no '{need}' column; header is {names}")
    rows = []
    for line in lines[start + 1:]:
        if not line.lstrip().startswith("|"):
            break
        cells = statefiles.split_row(line)
        if statefiles.is_separator(cells):
            continue
        row = {n: (cells[i] if i < len(cells) else "") for i, n in enumerate(names)}
        if row["id"].strip():
            rows.append(row)
    if not rows:
        die(f"stage {stage} table has no task rows")
    return rows


def parse_needs(cell):
    out = []
    for part in re.split(r"[,\s]+", cell.strip()):
        if part in ("", "-"):
            continue
        m = re.fullmatch(r"(.*?)(\d+)\.\.(.*?)(\d+)", part)
        if m and (m.group(3) in ("", m.group(1))):
            out += [f"{m.group(1)}{k}" for k in range(int(m.group(2)), int(m.group(4)) + 1)]
        else:
            out.append(part)
    return out


def parse_check(cell):
    parts = [p.strip().strip("`").strip() for p in re.split(r"<br\s*/?>| ;; ", cell)]
    parts = [p for p in parts if p]
    return parts if len(parts) > 1 else (parts[0] if parts else "")


def task_spec(row, stage):
    tid = row["id"].strip()
    agent = row["agent"].strip()
    task = {"id": tid, "agent": agent if ":" in agent else "ping-personal:" + agent,
            "phase": row.get("phase", "").strip() or stage, "check": parse_check(row["check"])}
    try:
        k = float(row["estimatek"])
    except ValueError:
        die(f"task {tid}: estimateK '{row['estimatek']}' is not a number")
    task["estimateK"] = int(k) if k == int(k) else k
    model = row.get("model", "").strip().lower()
    if model:
        task["model"] = model  # generate.py refuses a value other than worker, inherit or advisor
    kind = row.get("kind", "").strip().lower()
    if kind not in ("", "task", "review"):
        die(f"task {tid}: kind must be review or empty, got '{kind}'")
    if kind == "review":  # coordinators once wrote review steps into the spec JSON by hand
        task["kind"] = "review"
        del task["check"]
        return task
    pass_line = row.get("passline", "").strip().strip("`").strip()
    expect = row.get("expect", "").strip().lower()
    if expect not in ("", "pass", "fail"):
        die(f"task {tid}: expect must be pass or fail, got '{expect}'")
    if expect == "fail" or (not expect and RED_WORDS.search(pass_line)):
        task["expect"] = "fail"
    elif "PASS" in pass_line:
        task["passLine"] = pass_line
    if row.get("redfile", "").strip():
        task["redFile"] = row["redfile"].strip().strip("`")
    needs = parse_needs(row.get("needs", ""))
    if needs:
        task["needs"] = needs
    resources = [r.strip() for r in row.get("resources", "").split(",") if r.strip() and r.strip() != "-"]
    if resources:
        task["resources"] = resources
    if row.get("commits", "").strip().lower() in TRUE:
        task["commits"] = True
    ui = row.get("ui", "").strip().lower()
    if ui in TRUE + FALSE:
        task["ui"] = ui in TRUE
    elif ui:
        die(f"task {tid}: ui must be y/n/true/false, got '{ui}'")
    return task


def pair_steps(tasks):
    steps, i = [], 0
    while i < len(tasks):
        a = tasks[i]
        b = tasks[i + 1] if i + 1 < len(tasks) else None
        if b and generate.MAX_PARALLEL >= 2 and not (
                {r.lower() for r in a.get("resources", [])} & {r.lower() for r in b.get("resources", [])}
                or a["id"] in b.get("needs", []) or b["id"] in a.get("needs", [])
                or a.get("commits") or b.get("commits")):
            steps.append([a, b])  # ponytail: only ever pairs, MAX_PARALLEL is 2; widen here if generate.py allows more
            i += 2
        else:
            steps.append(a)
            i += 1
    return steps


def task_body(text, tid):
    """The text under the plan's '<#s> Task <id>' heading, up to the next heading of the same or a higher level."""
    m = re.search(rf"^(#+) .*\bTask {re.escape(tid)}(?![\w-]).*$", text, re.M)
    if not m:
        die(f"the plan has no '## Task {tid}' heading")
    level = len(m.group(1))
    after = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", after, re.M)  # ponytail: a '#' line inside a code fence also ends the body
    return (after[:nxt.start()] if nxt else after).strip("\n")


def names(steps):
    return [[t["id"] for t in s] if isinstance(s, list) else s["id"] for s in steps]


def read_or_empty(path):
    return statefiles.read_text(path) if os.path.isfile(path) else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state-dir", required=True, help="run state folder. Example: docs/proj-123/autopilot")
    ap.add_argument("--plan", required=True, help="plan markdown with '## Stage <name>'. Example: docs/proj-123/PLAN.md")
    ap.add_argument("--stage", required=True, help="stage name as in the plan heading. Example: s2-build")
    ap.add_argument("--spec-only", action="store_true", help="write only the stage spec JSON")
    ap.add_argument("--review", help="task id of the fresh-eyes review. Example: S2-4 (default: no review)")
    ap.add_argument("--reviewer", default="ping-personal:iris", help="reviewer agent when --review is given")
    a = ap.parse_args()
    plan_text = statefiles.read_text(a.plan)
    plan_name = os.path.basename(a.plan)
    tasks = [task_spec(row, a.stage) for row in parse_table(plan_text, a.stage)]
    spec = {"name": a.stage, "summary": f"{a.stage} from {plan_name}", "steps": pair_steps(tasks)}
    if a.review:
        spec["review"], spec["reviewer"] = a.review, a.reviewer

    plan_path = os.path.join(a.state_dir, "plan.md")
    csv_path = os.path.join(a.state_dir, "tasks.csv")
    have_plan = read_or_empty(plan_path)
    known = {}  # task id -> the stage that first used it
    if os.path.isfile(csv_path):
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                known.setdefault((r.get("id") or "").strip(), (r.get("stage") or "").strip())
    # One id, one task: the verdict counts tasks by id, so an id reused in a later stage breaks the count.
    # --spec-only (a retry spec of failed tasks) reuses its ids on purpose.
    reused = [f"{t['id']} (used in {known[t['id']]})" for t in tasks
              if not a.spec_only and known.get(t["id"]) not in (None, a.stage)]
    if reused:
        die(f"task ids already used by an earlier stage: {', '.join(reused)}. Give this stage's tasks new ids.")
    now = time.strftime("%a %m-%d %H:%M")
    skipped, new_plan, new_rows = [], [], []
    for t, row in zip(tasks, parse_table(plan_text, a.stage)):
        tid = t["id"]
        if re.search(rf"^#+ .*\bTask {re.escape(tid)}(?![\w-])", have_plan, re.M):
            skipped.append(f"{tid} (already in plan.md)")
        else:
            new_plan.append(f"\n## Task {tid} - {row['what'].strip()}\n\n{task_body(plan_text, tid)}\n")
        if tid in known:
            skipped.append(f"{tid} (already in tasks.csv)")
        else:
            new_rows.append(f"{tid},{a.stage},{row['what'].strip().replace(',', ';')},{t['estimateK']},")
    section = (f"\n\n# Stage {a.stage} (copied from {plan_name} at {now})\n" + "".join(new_plan)) if new_plan else ""

    # Validate before writing anything: generate.py reads task text from plan.md, so check against the text it will hold.
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "plan.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(have_plan + section)
        try:
            with open(os.path.join(a.state_dir, "inputs.json"), encoding="utf-8-sig") as f:
                advisor = json.load(f).get("advisorModel")
        except (OSError, ValueError, AttributeError):
            advisor = None
        generate.stage_body(copy.deepcopy(spec), tmp, write_checks=False, advisor=advisor)

    # Rule 3: the first code stage captures the pre-change baseline. A past plan had no such task and the
    # baseline was only taken at close. --spec-only (a retry spec) is exempt.
    if not a.spec_only and not os.path.isfile(os.path.join(a.state_dir, "baseline-hashes.txt")) \
            and any(t.get("commits") for t in tasks) \
            and not any("log_row.py baseline" in f"{t.get('check', '')} {task_body(plan_text, t['id'])}" for t in tasks):
        die(f"stage {a.stage} commits code but no baseline is captured yet (no baseline-hashes.txt) and no task "
            f"runs 'log_row.py baseline'. Add a first task that runs it (or 'baseline --none').")

    spec_path = os.path.join(a.state_dir, "stages", a.stage + ".json")
    os.makedirs(os.path.dirname(spec_path), exist_ok=True)
    with open(spec_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(spec, f, indent=1)
    print(spec_path)
    if not a.spec_only:
        if section:
            with open(plan_path, "a", encoding="utf-8", newline="\n") as f:
                f.write(section)
        if new_rows:
            head = "" if os.path.isfile(csv_path) else "id,stage,what,estimate,added\n"
            lead = "\n" if os.path.isfile(csv_path) and not read_or_empty(csv_path).endswith("\n") else ""
            with open(csv_path, "a", encoding="utf-8", newline="\n") as f:
                f.write(lead + head + "\n".join(new_rows) + "\n")
    if skipped:
        print("skipped: " + ", ".join(skipped))
    print("steps:", names(spec["steps"]))


if __name__ == "__main__":
    main()

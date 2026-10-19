// Stage workflow template for the Workflow tool: one script per stage, launched in the background.
// scripts/generate.py fills every <PLACEHOLDER> (each value goes in as a JSON string) and appends the
// stage body from the stage spec. Relaunch after a crash or quota stop with the same script and
// resumeFromRunId: finished agents return their cached results.
// Returns { results, stoppedBy, stoppedAt, review, stageCheck } (shape read by scripts/run_state.py).

export const meta = {
  name: '<goal>-<stage>',                   // Example: proj123-s4-install-verify
  description: '<one-line stage summary>',  // Example: install, run the done command, fix rounds, rollback rehearsal
  phases: [{ title: 'Build' }, { title: 'Verify' }, { title: 'Review' }],
}

const GOAL = <GOAL>                           // Example: "PROJ-123 invoice fixes"
const REPO_PATH = <REPO_PATH>                 // Example: "D:\\work\\myrepo"
const BRANCH = <BRANCH>                       // Example: "topic/123-invoice-fixes"
const STATE_DIR = <STATE_DIR>                 // Example: "docs/proj-123/autopilot"
const BASE_COMMIT = <BASE_COMMIT>             // Example: "4b8d3b26c1f0a9e7d5c3b1a2f4e6d8c0a1b2c3d4"
const EXCLUSIVE_RESOURCES = <EXCLUSIVE_RESOURCES> // Example: "SQL Server, IIS, the test browser"
const DISKS = <DISKS>                         // Example: "C:,D:"
const MIN_GB = <MIN_GB>                       // Example: 1

// Shared header every agent receives. Rules live in STATUS.md so the coordinator can add one
// mid-run without relaunching this workflow.
const CTX = `
Goal: ${GOAL}. Repo ${REPO_PATH}, branch ${BRANCH}.
This run started at commit ${BASE_COMMIT}: "changed by this run" means shown by git diff ${BASE_COMMIT}.
The owner is away: never ask questions (no AskUserQuestion). Decide, record in ${STATE_DIR}/STATUS.md, move on.
Plan: ${STATE_DIR}/plan.md. Do your task exactly as written there, including its done-check command.
Read first: the TOP of ${STATE_DIR}/STATUS.md (binding rules override any task text), then your task section.
Exclusive resources (one agent at a time): ${EXCLUSIVE_RESOURCES}. Back up before overwrite.
After your task: (1) append ONE line to ${STATE_DIR}/log/run-log.md:
| <Day MM-DD HH:MM from a real clock command> | <task id> | <what happened, plain words> | <evidence path> |
(2) update the Now block of STATUS.md; (3) tick your rows in file-checklist.md. Read each file right before editing; change only your lines.
Every external side effect (a mail sent, a push, a deploy) gets one row in ${STATE_DIR}/log/side-effects.md: | Day MM-DD HH:MM | kind | count | note |. Write the row BEFORE the action, then check the totals against the caps in STATUS.md.
When you capture a baseline, append "<sha256>  <repo-relative path>" for each file to ${STATE_DIR}/baseline-hashes.txt; never edit a captured file.
Do not git commit unless your task says so. Quote done-check output verbatim; never claim pass without it; never fake, mock or hardcode results.
Stop heavy writes if free disk on ${DISKS} is under ${MIN_GB} GB.
`

// Effort for worker agents: 'low' when the session runs Fable; undefined (inherit) on Opus.
const EFFORT = <EFFORT>      // Example: undefined
// Model for mechanical worker tasks; undefined inherits the session model.
const WORKER_MODEL = <WORKER_MODEL>  // Example: "sonnet"
// Verifier, critic gate seats and reviewer always run at low effort (cost control).
const HELPER_EFFORT = 'low'

const RESULT = { type: 'object', properties: { task: { type: 'string' }, passed: { type: 'boolean' }, doneCheckOutput: { type: 'string' }, summary: { type: 'string' }, problems: { type: 'array', items: { type: 'string' } } }, required: ['task', 'passed', 'doneCheckOutput', 'summary', 'problems'] }
const VERIFY = { type: 'object', properties: { passed: { type: 'boolean' }, lastLine: { type: 'string' } }, required: ['passed', 'lastLine'] }
const AXIS_REVIEW = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string' }, text: { type: 'string' }, closed: { type: 'boolean' } }, required: ['severity', 'text', 'closed'] } } }, required: ['findings'] }
const REVIEW = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string' }, text: { type: 'string' }, closed: { type: 'boolean' } }, required: ['severity', 'text', 'closed'] } } }, required: ['findings'] }
const SEATS = ['ping-personal:ms-mario', 'ping-personal:rhea', <DOMAIN_CRITIC>] // Example: "ping-personal:iris"
const QUORUM = 2 // votes that must agree; fewer means the failing item is deferred, never a stop

const results = {}
const halt = { by: null, at: null }
let stageCheckResult = null

function done(review) {
  return { results, stoppedBy: halt.by, stoppedAt: halt.at, review: review || { findings: [] }, stageCheck: stageCheckResult }
}

// The verifier re-runs the task's own scoped check command itself; a worker's own "passed" is never used.
// A task may name its exact pass line (passLine); then the last printed line must equal it too.
async function verify(task, phase, passLine, check) {
  const v = await agent(CTX + `\nVERIFIER for ${task}. Run exactly this check command yourself and do not trust anyone's claim: ${check}\nReturn passed true only if it succeeded and printed its pass line (plan.md section "Task ${task}" names it); lastLine is the last line it printed.`, { label: `${task}:verify`, phase, agentType: 'ping-personal:rhea', model: 'sonnet', effort: HELPER_EFFORT, schema: VERIFY })
  if (!v) return { passed: false, lastLine: '' }
  return passLine ? { passed: v.passed && String(v.lastLine).trim() === passLine, lastLine: v.lastLine } : v
}

// After every task, one verifier runs the full done command once (tasks only ran their scoped checks).
async function stageCheck(command, passLine) {
  const v = await agent(CTX + `\nVERIFIER for the whole stage. Run exactly this full done command yourself, once, and do not trust anyone's claim: ${command}\nReturn passed true only if it succeeded${passLine ? ' and its last line, trimmed, equals ' + JSON.stringify(passLine) : ''}; lastLine is the last line it printed.`, { label: 'stage:check', phase: 'Stage check', agentType: 'ping-personal:rhea', model: 'sonnet', effort: HELPER_EFFORT, schema: VERIFY })
  const ok = !!v && v.passed && (!passLine || String(v.lastLine).trim() === passLine)
  stageCheckResult = { passed: ok, lastLine: v ? v.lastLine : '' }
}

// Critic vote that replaces asking the owner. Seats run one after another and stop being asked once
// QUORUM seats agree. A seat that returns nothing is asked once more. Without a quorum the failing item is
// deferred (never a stop); only QUORUM real stop votes stop the stage.
async function gate(task, r, phase) {
  const votes = []
  const tally = v => votes.filter(x => x.vote === v).length
  const ask = (a, label) => agent(CTX + `\nCritic gate (majority wins). ${task} failed its done-check twice. Problems: ${r.problems.join('; ')}\nDone-check output: ${r.doneCheckOutput}\nRead the evidence and vote: 'retry' with a concrete root-cause fix, 'defer' the failing item (it is flagged AGENT-DEFERRED for the owner), or 'stop' the stage. If the failing code was changed by this run (git diff ${BASE_COMMIT}), defer is not allowed: vote retry or stop. Whatever you choose must be easy for the owner to reverse; say how.`, { label, phase, agentType: a, effort: HELPER_EFFORT, schema: { type: 'object', properties: { vote: { type: 'string', enum: ['retry', 'defer', 'stop'] }, instruction: { type: 'string' }, howToReverse: { type: 'string' } }, required: ['vote', 'instruction', 'howToReverse'] } })
  for (const a of SEATS) {
    const x = (await ask(a, `${task}:gate:${a}`)) || (await ask(a, `${task}:gate:${a}:retry`))
    if (x) votes.push(x)
    if (Math.max(tally('retry'), tally('defer'), tally('stop')) >= QUORUM) break
  }
  const win = ['retry', 'defer', 'stop'].find(v => tally(v) >= QUORUM)
  if (!win) {
    log(`${task} gate: no quorum (${votes.map(v => v.vote).join(',')}), deferring`)
    return { win: 'defer', noQuorum: true, instructions: 'No critic quorum: defer the failing item and flag it AGENT-DEFERRED. Reverse: undo nothing; the owner decides.' }
  }
  log(`${task} gate: ${win} (${votes.map(v => v.vote).join(',')})`)
  return { win, noQuorum: false, instructions: votes.filter(v => v.vote === win).map(v => `${v.instruction}\nReverse: ${v.howToReverse}`).join('\n---\n') }
}

// Task -> worker -> verifier -> one root-cause fix -> verifier -> critic gate -> apply.
// Every label starts with the task id ("T8", "T8:fix", "T8:verify", "T8:gate:..."), because
// scripts/build_table.py adds an agent's tokens and times to the task named by its label's first word.
async function run(task, agentType, phase, model, needs, commits, text, passLine, check) {
  const entry = (r, v, extra) => ({ task, passed: !!(v && v.passed), deferred: false, deferredBy: null, reason: '', doneCheckOutput: v ? v.lastLine : '', summary: r ? r.summary : '', problems: r ? r.problems : [], ...extra })
  const blocked = needs.filter(n => !(results[n] && results[n].passed))
  if (blocked.length) {
    // Blocked only by deferred tasks: this task is deferred too, so a retry never re-runs it.
    if (blocked.every(n => results[n] && results[n].deferred)) {
      log(`${task} deferred: blocked by ${blocked.join(', ')}`)
      return entry(null, null, { summary: `blocked by ${blocked.join(', ')}`, deferred: true, deferredBy: 'agent', reason: `blocked by ${blocked.join(', ')}` })
    }
    log(`${task} skipped: needs ${blocked.join(', ')}`)
    return entry(null, null, { summary: `skipped: needs ${blocked.join(', ')}`, notRun: true })
  }
  const opts = (label) => ({ label, phase, agentType, model, effort: EFFORT, schema: RESULT })
  const note = (commits ? '\nThis task may git commit its own files (name each path; never git add -A).' : '') + (text ? `\nTask text: ${text}` : '')
  let r = await agent(CTX + `\nYOUR TASK: ${task} (plan.md section "Task ${task}").` + note, opts(task))
  let v = await verify(task, phase, passLine, check)
  if (!v.passed) {
    log(`${task} failed verification, one fix attempt`)
    const f = await agent(CTX + `\nYOUR TASK: finish ${task}. A first attempt failed its done-check. Problems:\n${r ? r.problems.join('\n') : 'worker returned nothing'}\nVerifier last line: ${v.lastLine}\nFind the root cause (superpowers:systematic-debugging), fix it, re-run the done-check.` + note, opts(`${task}:fix`))
    r = f || r
    v = await verify(task, phase, passLine, check)
  }
  if (!v.passed) {
    const g = await gate(task, { problems: r ? r.problems : [], doneCheckOutput: v.lastLine }, phase)
    if (g.win === 'stop') {
      halt.by = 'critic-gate'
      halt.at = task
      return entry(r, v, {})
    }
    const a = await agent(CTX + `\nYOUR TASK: ${task}. Critic gate decided '${g.win}'. Instructions:\n${g.instructions}\nApply it, add a row to "Decisions taken without the owner" in STATUS.md with how to reverse it (mark AGENT-DEFERRED if deferred), re-run the done-check.` + note, opts(`${task}:gate-apply`))
    r = a || r
    if (g.win === 'defer') return entry(r, v, { deferred: true, deferredBy: 'agent', reason: g.noQuorum ? 'no critic quorum' : '' })
    v = await verify(task, phase, passLine, check)
  }
  return entry(r, v, {})
}

// Fresh-eyes reviewer that did not write the assertions; reports what they do NOT cover.
async function review(task, reviewer) {
  return await agent(CTX + `\nFresh-eyes review of the evidence for ${task}. Report what the assertions do NOT cover. Each finding: severity (CRITICAL, HIGH, MEDIUM, LOW), text, closed (true only if the evidence already shows it fixed).`, { label: `${task}:review`, phase: 'Review', agentType: reviewer, model: 'sonnet', effort: HELPER_EFFORT, schema: REVIEW })
}

// Final stage only: two fresh reviewers, one after the other, on two separate axes. The findings of the
// two axes are never merged or ranked together.
async function finalReview() {
  const ask = (label, agentType, what) => agent(CTX + `\n${what}\nEach finding: severity (CRITICAL, HIGH, MEDIUM, LOW), text, closed (true only if the evidence already shows it fixed).`, { label, phase: 'Review', agentType, model: 'sonnet', effort: HELPER_EFFORT, schema: AXIS_REVIEW })
  const spec = await ask('final:spec', 'ping-personal:amanda', `SPEC review, fresh eyes. Compare git diff ${BASE_COMMIT}...HEAD with ${STATE_DIR}/GOAL-BRIEF.md. Report what is missing, what was not asked for, and what is wrong. Ignore code style.`)
  const standards = await ask('final:standards', 'ping-personal:ms-mario', `STANDARDS review, fresh eyes. Read the repo's standards files and the conventions in CLAUDE.md, then check git diff ${BASE_COMMIT}...HEAD against them. Report hard violations as HIGH and judgement calls as MEDIUM or LOW. Ignore whether the goal was met.`)
  return { spec: spec || { findings: [] }, standards: standards || { findings: [] } }
}

// ---- stage body: generated from the stage spec. Shape, for reference:
//   phase("Build")
//   results["T1"] = await run("T1", "ping-personal:bunny", "Build", WORKER_MODEL, [], false, "", "", "python -m pytest tests/test_t1.py -q")
//   if (halt.by) return done()
//   await stageCheck("<full done command>", "<exact last line>")   (only when the spec has stageCheck)
//   return done(await review("T1", "ping-personal:iris"))          (or: return done(await finalReview()))

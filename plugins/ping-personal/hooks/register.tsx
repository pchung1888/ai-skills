import type { Register } from 'claude-code'
import { collect, snapshot, isOld, isSessionFile, withTurn, parseGoal, activity, waitingText, spawnAct, parseCodex, codexDays, cacheSum, memText, foldTasks, addTime, findTime, type Times, type HudState, type Goal, type Codex, type Status, type Task, type Bg } from './hud-data'
import { layout, drawRows, dur, etTime } from './hud-render'
import { chip, shouldToast } from './hud-rules'
import { ACTIONS, resolveCmd, planSlug, GRAY, type Action } from './hud-actions'
import { agentStart, agentTool, agentEnd, agentEndForeground, agentClear, agentGroups, agentCounts, agentHeader, agentLine, asRows, type AgentRow } from './hud-agents'
import { paneLabel, paneWord, orderRows, slugOfPath, type PaneRow, pathOk, pathKey, normPath, slugOf, goalSlug, matchSlug, clean, beacons, pendingTick, mergeToasts, classify, parseGitLog, type Tracked, type Pending } from './hud-goals'

// ping-hud: AbovePrompt band (Model, cwd, Now, Forecast).
export const register: Register = on => {
  // Composes: our rows above whatever the hooks beneath draw, so other mods' band content still shows.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    if (e.props.hasSurvey) return next(e)
    // Other plugins' notes (you-should-know) draw first, so a note never scrolls out of view below the band.
    const below = await next(e), other = hasContent(below)
    const rows = await bandRows($, e)
    if (!rows) return below
    const ui = $.ui.resolve(e), mini = rows[0]?.key === 'mini'
    const ours = drawRows(ui, rows, e.surface === 'desktop', mini ? miniRow($, ui) : await buttonsRow($, ui, e.surface === 'desktop'))
    if (!other) return ours
    const { Box } = ui
    return <Box key="hudwrap" flexDirection="column">{below}{ours}</Box>
  })
  // The band is hidden while a question form is open, so Explain is unreachable then. The question call
  // itself gets an explain option instead, so every surface draws it; picking it sends that label back as the answer.
  on('tool.call', { tool: 'AskUserQuestion' }, async ($, e, next) => next({ ...e, questions: withExplainOption(e.questions) as typeof e.questions }))
    .catch(($, e, next) => next(e)) // a failed rewrite asks the original questions
  // Message times (DEC-18): a dim New York time under each typed prompt and finished reply,
  // and a copy button under the reply, on terminal and Desktop.
  on('ui.render', { component: 'UserMessage' }, async ($, e, next) => timeRow($, e, await next(e), 'user'))
  on('ui.render', { component: 'AssistantMessage' }, async ($, e, next) => timeRow($, e, await next(e), 'assistant'))
  on('prompt.submit', async ($, e, next) => {
    await noteTime($, 'user', e.text)
    return next(e)
  })
  on('turn.start', async ($, e, next) => {
    await turnFlag($, true)
    return next(e)
  })
  on('session.start', async ($, e, next) => {
    await note($, 'hudBg', []) // agents of an earlier process are gone after a (re)start
    await $.command.register({ name: 'personal-hud', description: 'ping-hud band: on, off, compact, mini, goals, agents, or glyphs ascii|unicode', argumentHint: 'on|off|compact|mini|goals|agents|glyphs ascii|unicode' }).catch(() => undefined)
    await cmdNames($)
    await status($)
    await safe($, true)
    await unbindGone($)
    await readStatusLine($)
    try { $.ui.invalidate('ui.render') } catch {}
    return next(e)
  })
  on('command.run', { command: 'personal-hud' }, async ($, e) => hudCommand($, e.args))
  // The session's name (Desktop sidebar or /rename) arrives only on the classic hook inputs.
  on('classic.SessionStart', async ($, e, next) => { await titleNote($, (e as any).session_title); return next(e) }).catch(($, e, next) => next(e))
  on('classic.UserPromptSubmit', async ($, e, next) => { await titleNote($, (e as any).session_title); return next(e) }).catch(($, e, next) => next(e))
  on('ui.render', { component: 'Pane', requestId: 'hud-goals' }, async ($, e) => goalsPane($, e))
  on('ui.render', { component: 'Pane', requestId: 'hud-agents' }, async ($, e) => agentsPane($, e))
  on('session.measure', async ($, e, next) => {
    await safe($, false)
    return next(e)
  })
  on('turn.complete', async ($, e, next) => {
    // A subagent's own turn end: its agent finished. The main turn's turn.complete carries no agentId.
    if (e.agentId) {
      void agentsDo($, (rows, t) => agentEnd(rows, String(e.agentId), t, (e as any).reason))
      await bgDone($, String(e.agentId))
      // Between turns nothing else resets Now, so settle it; mid-turn the main turn owns it.
      if (!((await mine($, 'hud').catch(() => undefined)) as HudState | undefined)?.turnActive) await endTurnNow($)
      return next(e)
    }
    await noteTime($, 'assistant', e.answer)
    void agentsDo($, (rows, t) => agentEndForeground(rows, t))
    await cmdNames($)
    await status($)
    await safe($, false)
    await turnFlag($, false)
    await endTurnNow($)
    await goalTurn($)
    // Store writes do not redraw; the turn's last draw happened before these, so ask for one.
    try { $.ui.invalidate('ui.render') } catch {}
    return next(e)
  })
  on('turn.step', async function* ($, e, next) {
    const r = yield* next(e)
    const prev = await mine($, 'hudStep').catch(() => undefined)
    await note($, 'hudStep', { thinking: e.effort, ...cacheSum(prev, r?.usage) })
    return r
  })
  // Counts background and workflow agents so Now does not say idle while they run.
  // Keyed by the started agent's own id (AgentSpawnResult.agentId); tool_use_id is shared by a workflow run's agents.
  on('agent.spawn', async ($, e, next) => {
    const r = await next(e)
    if ((r as any)?.deny) return r // refused: no agent started, nothing to count or list
    const aid = (r as any)?.agentId, bg = !!(e.background || e.workflow)
    // One id for the band count and the pane row; without the engine's id no tool or end event can reach the row.
    const id = aid ? String(aid) : e.workflow ? `${e.workflow.runId}:${e.workflow.agentIndex}` : `${e.description}:${await $.clock.now()}`
    void agentsDo($, (rows, t) => agentStart(rows, { id, type: e.subagentType, desc: e.description, run: e.workflow?.runId, idx: e.workflow?.agentIndex, bg, tracked: !!aid }, t))
    if (bg) {
      await bgAdd($, id, spawnAct(e), await $.clock.now())
    }
    return r
  })
  // Goal commands (typed or run through a driver) bind the goal they name.
  on('command.run', async ($, e, next) => {
    await goalCommand($, String(e.command), String(e.args ?? ''))
    return next(e)
  }).catch(($, e, next) => next(e))
  on('tool.call', async ($, e, next) => {
    // Now shows the main session's own work; a subagent's call (it carries agentId) must not hide the agent count.
    if (!(e as any).agentId) await setNow($, activity(e))
    else void agentsDo($, (rows, t) => agentTool(rows, String((e as any).agentId), activity(e), t)) // not awaited: the tool never waits on the pane
    const startMs = await $.clock.now()
    const r = await next(e)
    await taskNote($, e, r)
    await goalTool($, e, startMs)
    return r
  }).catch(($, e, next) => next(e)) // the band never blocks a tool
}

// $.store is one file shared by every session on the machine, so per-session keys carry the
// session id ('hudNow:<id>'). hudMode, hudGlyphs and hudStatusLine stay machine-wide.
// 'hudGoal' is no longer written; it stays listed so pruneStore clears keys an older version left behind.
const PER_SESSION = ['hud', 'hudNow', 'hudGoal', 'hudStatus', 'hudStep', 'hudToast', 'hudSeen', 'hudTasks', 'hudBg', 'hudGoals', 'hudGoalRows', 'hudPane', 'hudGoalPending', 'hudGoalToast', 'hudQueue', 'hudTimes', 'hudTitle', 'hudCmds', 'hudAgents']
async function own($: any, key: string): Promise<string> { return `${key}:${await $.session.id()}` }
async function mine($: any, key: string): Promise<any> { return $.store.get(await own($, key)) }

// Label of the option added to the first AskUserQuestion question. The description tells the model what to do.
export const EXPLAIN_FIRST = 'Explain these questions first'
const EXPLAIN_FIRST_HELP = 'Not an answer: explain the questions above, then ask them again.'

// Returns the questions with the explain option appended to the first question. Input is never mutated.
// Skipped when the first question already has 4 options (the tool schema caps a question at 4) or already has the option.
export function withExplainOption(questions: unknown[]): unknown[] {
  const first = questions[0] as { options?: { label?: unknown }[] } | undefined
  const options = Array.isArray(first?.options) ? first.options : []
  if (!first || options.length >= 4 || options.some(o => o?.label === EXPLAIN_FIRST)) return questions
  return [{ ...first, options: [...options, { label: EXPLAIN_FIRST, description: EXPLAIN_FIRST_HELP }] }, ...questions.slice(1)]
}

// Per-session store write that never throws: the band is decoration, the session must go on.
export async function note($: any, key: string, v: unknown) {
  try { await $.store.set(await own($, key), v) } catch {}
}

// hudNow changes what the band shows; between turns nothing else redraws, so ask for one.
export async function setNow($: any, v: string) {
  await note($, 'hudNow', v)
  try { $.ui.invalidate('ui.render') } catch {}
}

// bgAdd/bgDone are read-modify-write on one key; one chain runs them in order so no update is lost.
let bgQueue: Promise<unknown> = Promise.resolve()
function bgSerial(fn: () => Promise<void>): Promise<void> {
  const r = bgQueue.then(fn, fn)
  bgQueue = r.catch(() => undefined)
  return r
}

// Background agents started in this session; the band says 'waiting' instead of 'idle' while any run.
export function bgAdd($: any, id: string, act: string, tMs: number) {
  return bgSerial(async () => { try {
    const bg = ((await mine($, 'hudBg')) as Bg[] | undefined) ?? []
    await note($, 'hudBg', [...bg.filter(b => b.id !== id), { id, act, tMs }])
    $.ui.invalidate('ui.render')
  } catch {} })
}

// Agents pane rows: read-modify-write on the same chain as hudBg, so parallel agents never lose an update.
// The clock is read inside the chain, so a row's times follow the order its events were applied.
// Redraws only while the pane is open; a failed write is reported once per session as a toast.
export function agentsDo($: any, fn: (rows: AgentRow[], nowMs: number) => AgentRow[]) {
  return bgSerial(async () => {
    try {
      await $.store.set(await own($, 'hudAgents'), fn(asRows(await mine($, 'hudAgents')), await $.clock.now()))
      if (agentsOpen) { $.ui.invalidate('ui.render'); agentsTicker($) }
    } catch { if (!agentsWarned) { agentsWarned = true; try { $.ui.toast('ping-hud: Agents pane could not save an update; rows may be out of date') } catch {} } }
  })
}

// While the Agents pane is open and an agent runs, redraw once a second so elapsed times move between events.
let agentsOpen = false, agentsWarned = false, agentsTick: { cancel: () => void } | undefined
export function agentsTicker($: any) {
  if (agentsTick) return
  try {
    agentsTick = $.clock.every(1000, async () => {
      const live = asRows(await mine($, 'hudAgents').catch(() => undefined)).some(x => x.endMs === undefined)
      if (!agentsOpen || !live) { agentsTick?.cancel(); agentsTick = undefined; return }
      try { $.ui.invalidate('ui.render') } catch {}
    })
  } catch { agentsTick = undefined }
}

// Removes a finished agent from this session's background list and asks for a redraw.
export function bgDone($: any, id: string) {
  return bgSerial(async () => { try {
    const bg = ((await mine($, 'hudBg')) as Bg[] | undefined) ?? []
    await note($, 'hudBg', bg.filter(b => b.id !== id))
    $.ui.invalidate('ui.render')
  } catch {} })
}

// End of a turn: 'idle' only when no background agent is still running.
export async function endTurnNow($: any) {
  await setNow($, waitingText((await mine($, 'hudBg').catch(() => undefined)) as Bg[] | undefined) ?? 'idle')
}

// Folds a TodoWrite / TaskCreate / TaskUpdate / TaskList call into this session's task list.
export async function taskNote($: any, e: any, r: any) {
  try {
    const t = foldTasks((await mine($, 'hudTasks')) as Task[] | undefined, e, r)
    if (t) await note($, 'hudTasks', t)
  } catch {}
}

// ---- goal binding: which audit trackers this session tracks (hudGoals), waits for (hudGoalPending) and told the owner about (hudGoalToast) ----

// hudGoals / hudGoalPending / hudGoalToast are read-modify-write; one chain runs every change in order so none is lost.
let goalQueue: Promise<unknown> = Promise.resolve()
function goalSerial(fn: () => Promise<void>): Promise<void> {
  const r = goalQueue.then(async () => { try { await fn() } catch {} })
  goalQueue = r
  return r
}

// Tools that carry shell text in `command`.
const SHELLS = ['Bash', 'PowerShell']
const GOAL_NAMES = ['personal-goal', 'personal-goal-next', 'personal-loop']
const isWin = (root: string) => /^[A-Za-z]:|\\/.test(root)

// Repo root: the nearest folder at or above cwd that holds docs/ (a Bash cd can move cwd below it).
async function docsRoot($: any): Promise<string | null> {
  let dir = String(await $.session.cwd()).replace(/[\\/]+$/, '')
  while (!(await $.fs.exists(`${dir}/docs`))) {
    const up = dir.replace(/[\\/][^\\/]*$/, '')
    if (!up || up === dir) return null
    dir = up
  }
  return dir
}

// docs/<dir>/*-audit-tracker.md one level deep, archived folders skipped; unreadable files are left out.
async function scanTrackers($: any, root: string): Promise<{ path: string; text: string }[]> {
  const out: { path: string; text: string }[] = []
  if (!(await $.fs.exists(`${root}/docs`))) return out
  for (const d of await $.fs.list(`${root}/docs`)) {
    if (d.kind !== 'dir' || /^archived?$/i.test(d.name)) continue
    for (const f of await $.fs.list(`${root}/docs/${d.name}`)) {
      if (f.kind !== 'file' || !f.name.endsWith('-audit-tracker.md')) continue
      try { out.push({ path: `docs/${d.name}/${f.name}`, text: String(await $.fs.read(`${root}/docs/${d.name}/${f.name}`)) }) } catch {}
    }
  }
  return out
}

async function toastIn($: any, key: string, text: string): Promise<boolean> {
  const seen = ((await mine($, 'hudGoalToast')) as string[] | undefined) ?? []
  if (seen.includes(key)) return false
  await note($, 'hudGoalToast', [...seen, key])
  try { $.ui.toast(text) } catch {}
  return true
}

// Bound trackers -> parsed progress for the band; slug and title are cleaned, unreadable or missing files are left out.
export async function readBound($: any, tracked: Tracked[]): Promise<Goal[]> {
  const out: Goal[] = []
  for (const t of tracked) {
    try {
      const slug = slugOfPath(t.path), g = parseGoal(String(await $.fs.read(`${t.root}/${t.path}`)), slug)
      out.push(g ? { ...g, slug: clean(slug), step: clean(g.step) } : { slug: clean(slug), done: 0, total: 0, step: 'unreadable' }) // total 0 = unreadable
    } catch {}
  }
  return out
}

// Re-reads the bound trackers into hudGoalRows, which the band draws; called on bind, unbind and each turn end.
async function refreshRows($: any): Promise<void> {
  await note($, 'hudGoalRows', await readBound($, ((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? []))
}

async function addBound($: any, root: string, path: string): Promise<void> {
  const cur = ((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? [], w = isWin(root), p = normPath(path)
  if (cur.some(t => t.root === root && pathKey(t.path, w) === pathKey(p, w))) return
  await note($, 'hudGoals', [...cur, { root, path: p }])
  await refreshRows($)
  try { $.ui.invalidate('ui.render') } catch {}
}

async function setPending($: any, p: Pending[]): Promise<void> {
  await note($, 'hudGoalPending', p)
  try { $.ui.invalidate('ui.render') } catch {}
}

// One tracker with this goal_slug binds, several toast once, none waits in pending. Returns true when it bound or is ambiguous.
async function bindSlugIn($: any, root: string, slug: string, fresh: boolean): Promise<boolean> {
  const hits = matchSlug(await scanTrackers($, root), slug).filter(p => pathOk(root, p))
  if (hits.length === 1) await addBound($, root, hits[0])
  else if (hits.length > 1) await toastIn($, `ambiguous:${slug}`, `ambiguous goal ${clean(slug)}: pick in Goals`)
  else if (fresh) {
    const cur = ((await mine($, 'hudGoalPending')) as Pending[] | undefined) ?? []
    if (!cur.some(x => x.slug === slug)) await setPending($, [...cur, { slug, turns: 0 }])
  }
  return hits.length > 0
}

export function bindSlug($: any, root: string, slug: string): Promise<void> {
  return goalSerial(async () => { await bindSlugIn($, root, slug, true) })
}

// Slug a goal command or Skill call names: goal / goal-next take the first token, loop only after --resume.
function commandSlug(name: string, args: string): string | null {
  const n = name.replace(/^ping-personal:/, '')
  if (!GOAL_NAMES.includes(n)) return null
  if (n !== 'personal-loop') return slugOf(args)
  const m = /(?:^|\s)--resume\s+(\S+)/.exec(args)
  return m ? slugOf(m[1]) : null
}

async function goalCommand($: any, name: string, args: string): Promise<void> {
  const slug = commandSlug(name, args)
  if (!slug) return
  const root = (await docsRoot($).catch(() => null)) ?? String(await $.session.cwd()).replace(/[\\/]+$/, '')
  await bindSlug($, root, slug)
}

// Path as a root-relative spelling when it sits under root; anything else is returned normalized.
function underRoot(root: string, p: string): string {
  const n = normPath(p), r = normPath(root), w = isWin(root)
  return pathKey(n, w).startsWith(pathKey(r, w) + '/') ? n.slice(r.length + 1) : n
}

async function bindPathIn($: any, root: string, path: string): Promise<boolean> {
  const p = normPath(path)
  if (!pathOk(root, p) || !(await $.fs.exists(`${root}/${p}`))) return false
  await addBound($, root, p)
  return true
}

export function bindPath($: any, root: string, path: string): Promise<void> {
  return goalSerial(async () => { await bindPathIn($, root, path) })
}

// Pending slugs whose tracker now exists bind and leave; with tick the rest age one turn and drop at 3.
async function recheckPending($: any, tick: boolean): Promise<void> {
  const p = ((await mine($, 'hudGoalPending')) as Pending[] | undefined) ?? []
  if (!p.length) return
  const root = await docsRoot($).catch(() => null)
  const found: string[] = []
  for (const x of p) if (root && (await bindSlugIn($, root, x.slug, false))) found.push(x.slug)
  const t = tick ? pendingTick(p, found) : { keep: p.filter(x => !found.includes(x.slug)), dropped: [] as string[] }
  if (t.keep.length !== p.length || tick) await setPending($, t.keep)
  for (const slug of t.dropped) await toastIn($, `pending:${slug}`, `goal ${clean(slug)} not found`)
}

// Tracker paths a Write / Edit file_path or a Bash command names, as root-relative spellings.
function toolTrackerPaths(root: string, e: any): string[] {
  const raw = SHELLS.includes(e.tool)
    ? (String(e.command ?? '').replace(/\\/g, '/').match(/[^\s"'`<>|;&()=]+-audit-tracker\.md/g) ?? [])
    : e.file_path ? [String(e.file_path)] : []
  return [...new Set(raw.map(x => underRoot(root, x)))].filter(x => pathOk(root, x))
}

// A Read of docs/progress/*-progress.md or *-handoff.md while nothing is bound: bind each live 'Goal beacon:' tracker.
// An archived or missing tracker toasts once; a path that breaks the path rule is ignored silently.
async function resumeBind($: any, root: string, readPath: string): Promise<void> {
  if (!/^docs\/progress\/[^/]+-(progress|handoff)\.md$/i.test(underRoot(root, readPath))) return
  if (((await mine($, 'hudGoals')) as Tracked[] | undefined)?.length) return
  const text = String(await $.fs.read(`${root}/${underRoot(root, readPath)}`))
  for (const b of beacons(text)) {
    const n = normPath(b), live = n.split('/').filter(x => !/^archived?$/i.test(x)).join('/')
    if (!pathOk(root, live)) continue
    if (live === n && (await bindPathIn($, root, n))) continue
    await toastIn($, `resume:${pathKey(n, isWin(root))}`, `goal tracker ${clean(n.split('/').pop() ?? '')} moved or missing`)
  }
}

// Newest change per path in ms: the newer of the last git commit and the file mtime (an uncommitted edit counts).
// One git call for all paths; a failed git leaves the mtime alone.
export async function goalLastChange($: any, root: string, paths: string[]): Promise<Record<string, number>> {
  const out: Record<string, number> = {}
  if (!paths.length) return out
  for (const p of paths) out[p] = await $.fs.stat(`${root}/${p}`).then((s: any) => Number(s.mtimeMs) || 0, () => 0)
  try {
    const r = await $.process.run(['git', '--literal-pathspecs', 'log', '--format=%ct', '--name-only', '--', ...paths], { cwd: root, timeoutMs: 5000 })
    if (r.exitCode !== 0) return out
    const g = parseGitLog(String(r.stdout)), w = isWin(root), keys = Object.keys(g)
    // A checkout or pull rewrites files and moves mtime without changing them, so mtime counts only for
    // a file git reports as modified or untracked; an unchanged tracked file takes its commit time.
    const st = await $.process.run(['git', '--literal-pathspecs', 'status', '--porcelain', '--', ...paths], { cwd: root, timeoutMs: 5000 })
    const dirty = st.exitCode === 0 ? String(st.stdout).split(/\r?\n/).filter(Boolean).map(l => pathKey(l.slice(3).replace(/^"|"$/g, ''), w)) : null
    for (const p of paths) {
      const k = keys.find(x => pathKey(x, w) === pathKey(p, w) || pathKey(x, w).endsWith('/' + pathKey(p, w)))
      if (!k) continue
      const changed = !dirty || dirty.some(d => d === pathKey(p, w) || d.endsWith('/' + pathKey(p, w)))
      out[p] = changed ? Math.max(out[p], g[k]) : g[k]
    }
  } catch {}
  return out
}

// Toasts several unbinds as one message; a key already toasted this session stays quiet.
async function toastMany($: any, items: { key: string; text: string }[]): Promise<void> {
  const seen = ((await mine($, 'hudGoalToast')) as string[] | undefined) ?? []
  const fresh = items.filter(x => !seen.includes(x.key))
  if (!fresh.length) return
  await note($, 'hudGoalToast', [...seen, ...fresh.map(x => x.key)])
  for (const m of mergeToasts(fresh.map(x => x.text))) { try { $.ui.toast(m) } catch {} }
}

// Drops bound trackers that were moved, deleted, archived or finalized, and toasts them (merged).
// Git runs once per root, for bound trackers that look finalized (all rows done plus an accept-cache file).
async function unbindIn($: any): Promise<void> {
  const cur = ((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? []
  if (!cur.length) return
  const nowMs = await $.clock.now()
  const gone: Tracked[] = [], texts = new Map<Tracked, { text: string; cacheMs: number }>()
  for (const t of cur) {
    const full = `${t.root}/${t.path}`
    if (normPath(t.path).split('/').some(x => /^archived?$/i.test(x)) || !(await $.fs.exists(full))) { gone.push(t); continue }
    try {
      const text = String(await $.fs.read(full)), g = parseGoal(text, '')
      const cacheMs = g && g.done === g.total ? await $.fs.stat(`${full}.accept-cache`).then((s: any) => Number(s.mtimeMs) || 0, () => 0) : 0
      if (cacheMs) texts.set(t, { text, cacheMs })
    } catch {}
  }
  for (const root of new Set([...texts.keys()].map(t => t.root))) {
    const group = [...texts].filter(([t]) => t.root === root)
    const last = await goalLastChange($, root, group.map(([t]) => t.path))
    for (const [t, x] of group) if (classify(x.text, last[t.path] ?? 0, x.cacheMs, nowMs) === 'finalized') gone.push(t)
  }
  if (!gone.length) return
  await note($, 'hudGoals', cur.filter(t => !gone.includes(t)))
  await refreshRows($)
  try { $.ui.invalidate('ui.render') } catch {}
  await toastMany($, gone.map(t => ({
    key: `gone:${pathKey(t.path, isWin(t.root))}`,
    text: `goal ${clean((t.path.split('/').pop() ?? '').replace(/-audit-tracker\.md$/, ''))} cleared: tracker moved, removed or finalized`,
  })))
}

// Manual unbind from the Goals pane: drops one tracker from this session's bound list.
function unbindPath($: any, root: string, path: string): Promise<void> {
  return goalSerial(async () => {
    const cur = ((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? [], w = isWin(root)
    const next = cur.filter(t => !(t.root === root && pathKey(t.path, w) === pathKey(path, w)))
    if (next.length === cur.length) return
    await note($, 'hudGoals', next)
    await refreshRows($)
    try { $.ui.invalidate('ui.render') } catch {}
  })
}

export function unbindGone($: any): Promise<void> {
  return goalSerial(async () => { await unbindIn($); await refreshRows($) })
}

// True when a tool call's text arguments name a bound tracker path.
async function namesBound($: any, e: any): Promise<boolean> {
  const cur = ((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? []
  if (!cur.length) return false
  const text = Object.values(e).filter(v => typeof v === 'string').join('\n').replace(/\\/g, '/')
  return cur.some(t => { const w = isWin(t.root); return pathKey(text, w).includes(pathKey(t.path, w)) })
}

// After a tool finishes: a goal Skill call binds its slug; a Write / Edit / Bash that touched a tracker binds it;
// a Read of a progress file may resume; a call that names a bound tracker re-checks the bound list.
async function goalTool($: any, e: any, startMs: number): Promise<void> {
  try {
    if (e.tool === 'Skill') return await goalCommand($, String(e.skill ?? ''), String(e.args ?? ''))
    if (!['Read', 'Write', 'Edit', ...SHELLS].includes(e.tool)) return
    await goalSerial(async () => {
      const root = await docsRoot($)
      if (root && e.tool === 'Read' && e.file_path) await resumeBind($, root, String(e.file_path))
      else if (['Write', 'Edit', ...SHELLS].includes(e.tool)) {
        if (root) for (const p of toolTrackerPaths(root, e)) {
          if (SHELLS.includes(e.tool) && !(((await $.fs.stat(`${root}/${p}`).catch(() => undefined))?.mtimeMs ?? 0) > startMs)) continue
          await bindPathIn($, root, p)
        }
        await recheckPending($, false)
      }
      if (await namesBound($, e)) await unbindIn($)
    })
  } catch {}
}

// Main turn end: pending slugs age one turn; bound trackers that are gone or finalized are dropped.
async function goalTurn($: any): Promise<void> {
  await goalSerial(async () => { await recheckPending($, true); await unbindIn($); await refreshRows($) })
}

// Drops other sessions' keys not refreshed for 7 days (by 'hudSeen:<id>'), and pre-session-id bare keys.
export async function pruneStore($: any, nowMs: number) {
  const cur = await $.session.id(), seen: Record<string, unknown> = {}
  for (const k of await $.store.keys()) {
    const m = /^(\w+)(?::(.+))?$/.exec(k)
    if (!m || !PER_SESSION.includes(m[1])) continue
    const sid = m[2]
    if (sid === cur) continue
    if (sid !== undefined && !(sid in seen)) seen[sid] = await $.store.get(`hudSeen:${sid}`)
    const t = sid === undefined ? undefined : seen[sid]
    if (typeof t !== 'number' || isOld(t, nowMs)) await $.store.delete(k)
  }
}

// Stores turnActive on the band state; drives the STALE and idle-age rules.
async function turnFlag($: any, active: boolean) {
  try { const s = withTurn((await mine($, 'hud')) as HudState | undefined, active); if (s) await note($, 'hud', s) } catch {}
}

// A failed read or write must never break the session; the band just keeps its last state.
async function safe($: any, start: boolean) {
  try {
    const now = await $.clock.now()
    if (start) await prune($, now)
    if (start) await pruneStore($, now).catch(() => undefined)
    await refresh($, now)
  } catch {}
}

// $ helpers must live in this file: validate follows $ only into same-file declarations.
async function homeDir($: any): Promise<string | undefined> {
  const home = (await $.env.get('HOME')) || (await $.env.get('USERPROFILE'))
  return home ? home.replace(/[\\/]+$/, '') : undefined
}

async function liveDir($: any): Promise<string | undefined> {
  const home = await homeDir($)
  return home ? `${home}/.claude/live-usage` : undefined
}

// git stdout trimmed; a failed, missing or empty git answers undefined.
async function git($: any, cwd: string, args: string[]): Promise<string | undefined> {
  try {
    const r = await $.process.run(['git', ...args], { cwd, timeoutMs: 5000 })
    return r.exitCode === 0 ? String(r.stdout).trim() || undefined : undefined
  } catch { return undefined }
}

// Current and default branch; no repo, detached HEAD or no git -> '-'.
export async function gitInfo($: any, cwd: string): Promise<{ branch: string; defaultBranch: string }> {
  const b = await git($, cwd, ['rev-parse', '--abbrev-ref', 'HEAD'])
  const d = await git($, cwd, ['symbolic-ref', 'refs/remotes/origin/HEAD'])
  return { branch: b && b !== 'HEAD' ? b : '-', defaultBranch: d ? d.replace(/^(refs\/remotes\/)?origin\//, '') : '-' }
}

// Newest ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl of today, else yesterday -> its last rate_limits.
export async function readCodex($: any, nowMs: number): Promise<Codex | null> {
  const home = await homeDir($)
  if (!home) return null
  for (const day of codexDays(nowMs)) {
    const dir = `${home}/.codex/sessions/${day}`
    if (!(await $.fs.exists(dir))) continue
    const logs = (await $.fs.list(dir)).filter((f: any) => f.kind === 'file' && /^rollout-.*\.jsonl$/.test(f.name))
    if (!logs.length) continue
    logs.sort((a: any, b: any) => b.mtimeMs - a.mtimeMs)
    return parseCodex(String(await $.fs.read(`${dir}/${logs[0].name}`)), nowMs)
  }
  return null
}

// Used/total RAM: /proc/meminfo on Linux, CIM via PowerShell on Windows; anything else -> undefined.
async function readMem($: any): Promise<string | undefined> {
  try {
    if (await $.fs.exists('/proc/meminfo')) {
      const t = String(await $.fs.read('/proc/meminfo'))
      const kb = (k: string) => Number(new RegExp(`^${k}:\\s+(\\d+)`, 'm').exec(t)?.[1])
      return memText(kb('MemTotal'), kb('MemAvailable'))
    }
    const r = await $.process.run(['powershell', '-NoProfile', '-Command',
      '$o = Get-CimInstance Win32_OperatingSystem; "$($o.TotalVisibleMemorySize) $($o.FreePhysicalMemory)"'], { timeoutMs: 10000 })
    const [t, f] = String(r.stdout).trim().split(/\s+/).map(Number)
    return memText(t, f)
  } catch { return undefined }
}

// Status fields for the cwd row and the Codex cells; runs on session start and turn.complete only.
async function status($: any) {
  try {
    const cwd = await $.session.cwd()
    const s: Status = { ...(await gitInfo($, cwd)), mem: await readMem($), codex: await readCodex($, await $.clock.now()).catch(() => null) }
    await note($, 'hudStatus', s)
  } catch {}
}

// Reads usage, folds it into the stored state, writes the snapshot. Returns the new state.
async function refresh($: any, nowMs: number): Promise<HudState> {
  const prev = (await mine($, 'hud')) as HudState | undefined
  const s = collect(prev, await $.session.usage(), await $.session.model(), nowMs)
  await $.store.set(await own($, 'hud'), s)
  await note($, 'hudSeen', nowMs)
  await runsOutToast($, s, nowMs).catch(() => undefined)
  const dir = await liveDir($)
  if (dir) await $.fs.write(`${dir}/${await $.session.id()}.json`, JSON.stringify(snapshot(await $.session.id(), s, nowMs, ((await mine($, 'hudStatus')) as Status | undefined)?.codex), null, 2))
  return s
}

// No $.fs delete exists, so old snapshots are removed with the host's own command; only <uuid>.json names reach it.
async function prune($: any, nowMs: number): Promise<number> {
  const dir = await liveDir($)
  if (!dir || !(await $.fs.exists(dir))) return 0
  const old = (await $.fs.list(dir)).filter((f: any) => f.kind === 'file' && isSessionFile(f.name) && isOld(f.mtimeMs, nowMs))
  for (const f of old) {
    const p = `${dir}/${f.name}`
    await $.process.run(/^[A-Za-z]:/.test(p) ? ['cmd', '/c', 'del', '/q', p.split('/').join('\\')] : ['rm', '-f', p]).catch(() => undefined)
  }
  return old.length
}

// Reads stored state and settings into rows; the layout is cheap, so no row cache.
async function bandRows($: any, e: any) {
  const mode = await $.store.get('hudMode')
  return layout((await mine($, 'hud')) as HudState | undefined, {
    buttons: true, title: (await mine($, 'hudTitle').catch(() => undefined)) || (String(await $.session.id().catch(() => '')).slice(0, 8) || undefined), // DEC-15: no name -> short id
    surface: e.surface, bodyColumns: e.props.bodyColumns, maxRows: e.props.maxRows,
    mode, glyphs: await $.store.get('hudGlyphs'),
    statusLinePresent: await $.store.get('hudStatusLine'), nowMs: await $.clock.now(),
    cwd: await $.session.cwd().catch(() => undefined),
    now: await mine($, 'hudNow'), goals: ((await mine($, 'hudGoalRows')) as Goal[] | undefined) ?? [],
    status: await mine($, 'hudStatus'), step: await mine($, 'hudStep'), tasks: await mine($, 'hudTasks'),
  })
}

// Stores the session name when the classic input carries one; a blank one changes nothing.
async function titleNote($: any, t: unknown) {
  if (typeof t === 'string' && t.trim()) await note($, 'hudTitle', clean(t.trim()))
}

// Command names, read at session.start and turn.complete: the draw hook only reads the stored list,
// since a live $.command.list call inside ui.render can outlast the hook's budget and blank the band.
async function cmdNames($: any) {
  try { await note($, 'hudCmds', ((await $.command.list()) as { name: string }[]).map(c => c.name)) } catch {}
}

// The Buttons row: one Button per action whose command this session lists (Goals always);
// a 'goal' action (Plan) only while a goal with a plain slug is bound.
// Terminal labels are colored Text. Desktop draws a native button, given the plain label only, so a
// colored dot goes before it (DEC-14) and the row gets a one-unit gap between items.
async function buttonsRow($: any, ui: any, desktop = false) {
  const names = ((await mine($, 'hudCmds').catch(() => undefined)) as string[] | undefined) ?? []
  const bound = (((await mine($, 'hudGoals').catch(() => undefined)) as Tracked[] | undefined) ?? []).map(t => t.path)
  const { Box, Text, Button } = ui
  const shown = ACTIONS.filter(a => (!a.cmd || resolveCmd(names, a.cmd, a.plugin)) && (a.needs !== 'goal' || planSlug(bound)))
  if (desktop) return <Box key="buttons" flexDirection="row" columnGap={1}>
    {[...shown.flatMap(a => [
      ...(a.color ? [<Text key={`chip${a.key}`} color={a.color}>{'\u25cf'}</Text>] : []),
      <Button key={`btn${a.key}`} label={a.label} onPress={() => press($, a, names)} />]), <Text key="chiphide" color={GRAY}>{'\u25cf'}</Text>, <Button key="hide" label="Hide" onPress={() => hideBand($)} />]}
  </Box>
  return <Box key="buttons" flexDirection="row">
    {shown.map(a => <Button key={`btn${a.key}`} label={a.label} onPress={() => press($, a, names)}><Text key={`btnt${a.key}`} color={a.color}>{a.label}</Text></Button>)}
    <Button key="hide" onPress={() => hideBand($)}><Text key="hidet" color={GRAY}>Hide</Text></Button>
  </Box>
}

// Hide: the band becomes one row, `ping-hud [ Show ]`. The mode it came from is kept in hudModePrev for Show.
async function hideBand($: any) {
  try {
    const cur = await $.store.get('hudMode')
    await $.store.set('hudModePrev', cur === 'compact' ? 'compact' : 'on')
    await $.store.set('hudMode', 'mini')
    try { $.ui.invalidate('ui.render') } catch {}
  } catch {}
}

// The one-row form of a hidden band. Show restores hudModePrev; a missing or unknown value restores 'on'.
function miniRow($: any, ui: any) {
  const { Box, Text, Button } = ui
  return <Box key="mini" flexDirection="row">
    <Text key="minit" dimColor>ping-hud </Text>
    <Button key="show" onPress={async () => {
      try {
        const prev = await $.store.get('hudModePrev')
        await $.store.set('hudMode', prev === 'compact' ? 'compact' : 'on')
        try { $.ui.invalidate('ui.render') } catch {}
      } catch {}
    }}>[ Show ]</Button>
  </Box>
}

// A press runs the action's command as if typed; the engine queues it until the session is idle.
export async function press($: any, a: Action, names: string[]) {
  try {
    if (!a.cmd) { await (a.key === 'agents' ? openAgents($) : openGoals($)); return }
    const command = resolveCmd(names, a.cmd, a.plugin)
    if (!command) return
    const bound = (((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? []).map(t => t.path)
    if (a.needs === 'goal' && !planSlug(bound)) return
    if (((await mine($, 'hud')) as HudState | undefined)?.turnActive) $.ui.toast(`ping-hud: ${a.label} queued until this turn ends`)
    await $.command.run({ command, args: a.args({ bound, nowMs: await $.clock.now(), root: $.plugin.root }) })
  } catch { try { $.ui.toast(`ping-hud: ${a.label} could not run`) } catch {} }
}

// True when a ui.render tree draws something: an empty Box (the engine's own empty band) is nothing.
export function hasContent(el: any): boolean {
  if (!el) return false
  if (el.type !== 'Box') return true
  const k = el.props?.children
  return Array.isArray(k) ? k.some(hasContent) : hasContent(k)
}

// Records when a prompt or a main-turn answer was sent; read-modify-write, so the band's serial chain runs it.
async function noteTime($: any, kind: 'user' | 'assistant', text: unknown) {
  if (typeof text !== 'string' || !text.trim()) return
  await bgSerial(async () => {
    const prev = (await mine($, 'hudTimes').catch(() => undefined)) as Times | undefined
    await note($, 'hudTimes', addTime(prev, kind, text, await $.clock.now()))
  })
}

// The engine's message row, plus a dim time line (and a copy button on a reply) when its time is known.
async function timeRow($: any, e: any, row: any, kind: 'user' | 'assistant') {
  try {
    if (e.props.isSummary || (await $.store.get('hudMode')) === 'off') return row
    const ms = findTime((await mine($, 'hudTimes')) as Times | undefined, kind, e.props.text)
    if (ms === undefined) return row
    const { Box, Text, Button } = $.ui.resolve(e)
    const time = <Text key="hudtime" dimColor>{etTime(ms)}</Text>
    // Desktop puts the prompt bubble on the right, so its time goes right as well; the terminal prompt is left.
    if (kind === 'user') return <Box key="hudmsg" flexDirection="column">{row}{e.surface === 'desktop' ? <Box key="hudtimeright" alignSelf="flex-end">{time}</Box> : time}</Box>
    const copy = () => $.ui.copy({ text: e.props.text, surface: e.surface }).catch(() => $.ui.toast('ping-hud: copy failed'))
    return <Box key="hudmsg" flexDirection="column">{row}<Box key="hudmeta" flexDirection="row">{time}<Text key="hudgap"> </Text><Button key="hudcopy" label="copy" onPress={copy} /></Box></Box>
  } catch { return row }
}

// A configured statusLine (ccstatusline) already shows cwd and branch, so the terminal band drops the cwd row.
async function readStatusLine($: any) {
  try { await $.store.set('hudStatusLine', !!(await $.settings.read()).statusLine) } catch {}
}

const USAGE = 'Usage: /personal-hud on|off|compact|mini | /personal-hud goals | /personal-hud agents | /personal-hud glyphs ascii|unicode'

// The Goals pane's data, kept in hudPane: one parsed row per tracker (path = '<root>/<rel>'), whether hidden rows
// show, and which row is waiting for its archive confirm.
// confirm holds a row path, or CLEAN while [ clean up ] waits for its confirm.
const CLEAN = '*clean-up*'
type PaneData = { rows: (PaneRow & { root: string; rel: string })[]; show: boolean; confirm?: string }

// Archive from the Goals pane (DEC-20): git mv <dir>/<slug>-audit-tracker.md -> <dir>/archived/, so git keeps tracking it
// even under a git-ignored docs/. Left staged, never committed. A path outside the tracker rule runs nothing.
export async function archiveTracker($: any, root: string, rel: string): Promise<{ ok: boolean; text: string }> {
  const p = normPath(String(rel || ''))
  if (!pathOk(root, p)) return { ok: false, text: `ping-hud: not a goal tracker path: ${p}` }
  // cmd.exe re-parses mkdir's argument, so only plain path characters may reach it (no & | ^ < > % " ! or spaces).
  // The session cwd on Windows uses backslashes; the check and the mkdir path use forward slashes.
  if (!/^[\w.\/:-]+$/.test(`${normPath(root)}/${p}`)) return { ok: false, text: `ping-hud: unsafe characters in path, not archived: ${p}` }
  const i = p.lastIndexOf('/'), dir = p.slice(0, i), dest = `${dir}/archived/${p.slice(i + 1)}`, slug = slugOfPath(p)
  const full = `${normPath(root)}/${dir}/archived`
  // mkdir first: git mv does not create the folder. It may already exist, so its result is ignored.
  await $.process.run(isWin(root) ? ['cmd', '/c', 'mkdir', full.split('/').join('\\')] : ['mkdir', '-p', full], { cwd: root, timeoutMs: 5000 }).catch(() => undefined)
  const r = await $.process.run(['git', 'mv', '--', p, dest], { cwd: root, timeoutMs: 5000 }).catch((e: any) => ({ exitCode: 1, stderr: String(e?.message ?? e) }))
  if (r?.exitCode !== 0) return { ok: false, text: `ping-hud: could not archive ${slug}: ${String(r?.stderr || '').trim().split(/\r?\n/)[0] || 'git mv failed'}` }
  await unbindPath($, root, p)
  return { ok: true, text: `ping-hud: archived ${slug} to ${dest} (staged, not committed)` }
}

// Goals pane open: drop vanished bound trackers, scan every docs/<dir>/*-audit-tracker.md of the pane root and read
// every bound tracker from its own root, one git call per root for last-change times; keep parsed rows, then open.
export async function openGoals($: any): Promise<{ text: string }> {
  try {
    await unbindGone($)
    const root = await docsRoot($).catch(() => null)
    if (!root) return { text: 'ping-hud: no docs/ folder found above the working directory' }
    const nowMs = await $.clock.now(), found = new Map<string, { root: string; path: string; text: string }>()
    const add = (r: string, path: string, text: string) => found.set(pathKey(`${r}/${path}`, isWin(r)), { root: r, path, text })
    for (const f of await scanTrackers($, root)) add(root, f.path, f.text)
    for (const t of ((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? []) {
      if (found.has(pathKey(`${t.root}/${t.path}`, isWin(t.root)))) continue
      try { add(t.root, t.path, String(await $.fs.read(`${t.root}/${t.path}`))) } catch {}
    }
    const rows: PaneData['rows'] = [], all = [...found.values()]
    for (const r of new Set(all.map(x => x.root))) {
      const inRoot = all.filter(x => x.root === r), last = await goalLastChange($, r, inRoot.map(x => x.path))
      for (const f of inRoot) {
        const g = parseGoal(f.text, ''), full = g && g.done === g.total
        const cacheMs = full ? await $.fs.stat(`${r}/${f.path}.accept-cache`).then((s: any) => Number(s.mtimeMs) || 0, () => 0) : 0
        rows.push({ path: `${r}/${f.path}`, root: r, rel: f.path, slug: slugOfPath(f.path), cls: classify(f.text, last[f.path] ?? 0, cacheMs || undefined, nowMs), goal: g, lastChange: last[f.path] ?? 0, bound: false })
      }
    }
    await note($, 'hudPane', { rows, show: false } as PaneData)
    await $.ui.open({ id: 'hud-goals', title: 'Goals' })
    try { $.ui.invalidate('ui.render') } catch {}
    return { text: 'ping-hud: Goals pane opened' }
  } catch { return { text: 'ping-hud: could not read the goal trackers' } }
}

// Pane body: bound rows first, then the rest; [ show ] lists finalized and done trackers inline.
// A row press binds or unbinds that tracker for this session; [ archive ] asks [ confirm ] [ cancel ] before moving it.
async function goalsPane($: any, e: any) {
  const { Box, Text, Button } = $.ui.resolve(e)
  const d = (await mine($, 'hudPane')) as PaneData | undefined
  const setPane = async (v: PaneData) => { await note($, 'hudPane', v); try { $.ui.invalidate('ui.render') } catch {} }
  const archive = async (path: string) => {
    const x = d?.rows.find(r => r.path === path)
    if (!x) return
    const res = await archiveTracker($, x.root, x.rel)
    try { $.ui.toast(res.text) } catch {}
    const cur = ((await mine($, 'hudPane')) as PaneData | undefined) ?? d!
    await setPane({ ...cur, confirm: undefined, rows: res.ok ? cur.rows.filter(r => r.path !== path) : cur.rows })
  }
  // [ clean up ] archives every finalized row (all rows done and accepted) after one confirm; other classes stay.
  const finalized = (d?.rows ?? []).filter(r => r.cls === 'finalized')
  const cleanUp = async () => {
    const gone: string[] = []
    for (const x of finalized) {
      const res = await archiveTracker($, x.root, x.rel)
      if (res.ok) gone.push(x.path); else try { $.ui.toast(res.text) } catch {}
    }
    try { $.ui.toast(`ping-hud: clean up archived ${gone.length} of ${finalized.length} finalized goal(s) (staged, not committed)`) } catch {}
    const cur = ((await mine($, 'hudPane')) as PaneData | undefined) ?? d!
    await setPane({ ...cur, confirm: undefined, rows: cur.rows.filter(r => !gone.includes(r.path)) })
  }
  const tracked = ((await mine($, 'hudGoals')) as Tracked[] | undefined) ?? []
  const at = new Map((d?.rows ?? []).map(r => [r.path, r]))
  const { rows, hidden } = orderRows(d?.rows ?? [], tracked.map(t => `${t.root}/${t.path}`), tracked.some(t => isWin(t.root)) || isWin(d?.rows[0]?.root ?? ''))
  const row = (r: PaneRow) => (
    <Box key={`gr:${r.path}`} flexDirection="row">
      <Button key={`g:${r.path}`} onPress={() => { const x = at.get(r.path)!; return r.bound ? unbindPath($, x.root, x.rel) : bindPath($, x.root, x.rel) }}>
        {paneLabel(r)}{paneWord(r) ? <Text key="w" dimColor>{`  ${paneWord(r)}`}</Text> : null}
      </Button>
      <Text key="sp"> </Text>
      {d?.confirm === r.path
        ? [<Button key={`ac:${r.path}`} onPress={() => archive(r.path)}>[ confirm ]</Button>,
          <Button key={`an:${r.path}`} onPress={() => setPane({ ...d!, confirm: undefined })}>[ cancel ]</Button>]
        : <Button key={`a:${r.path}`} onPress={() => setPane({ ...d!, confirm: r.path })}>[ archive ]</Button>}
    </Box>
  )
  return (
    <Box key="goals" flexDirection="column">
      {rows.map(row)}
      {!rows.length && !hidden.length ? <Text key="none" dimColor>no goal trackers found</Text> : null}
      {hidden.length ? (
        <Box key="hid" flexDirection="row">
          <Text key="hidt">{`hidden: ${hidden.length} finalized or done  `}</Text>
          <Button key="show" onPress={async () => { await note($, 'hudPane', { ...d!, show: !d!.show }); try { $.ui.invalidate('ui.render') } catch {} }}>{d!.show ? '[ hide ]' : '[ show ]'}</Button>
        </Box>
      ) : null}
      {d?.show ? hidden.map(row) : null}
      {d?.confirm === CLEAN
        ? <Box key="cl" flexDirection="row">
            <Text key="clt">{`archive ${finalized.length} finalized: ${finalized.map(r => r.slug).join(', ')}  `}</Text>
            <Button key="cc" onPress={cleanUp}>[ confirm ]</Button>
            <Button key="cn" onPress={() => setPane({ ...d!, confirm: undefined })}>[ cancel ]</Button>
          </Box>
        : <Button key="clean" onPress={async () => { if (finalized.length) return setPane({ ...d!, confirm: CLEAN }); try { $.ui.toast('ping-hud: no finalized goals to clean up') } catch {} }}>[ clean up ]</Button>}
      <Button key="close" onPress={async () => { try { await $.store.delete(await own($, 'hudPane')) } catch {}; await $.ui.close({ id: 'hud-goals' }) }}>[ Close ]</Button>
    </Box>
  )
}

// Agents pane: one row per subagent this session started (who, doing what now, tool count and elapsed time),
// grouped per workflow run. Rows update as the agents work; [ clear done ] drops finished rows.
export async function openAgents($: any): Promise<{ text: string }> {
  try {
    const placed = await $.ui.open({ id: 'hud-agents', title: 'Agents' })
    agentsOpen = true
    agentsTicker($)
    try { $.ui.invalidate('ui.render') } catch {}
    if (placed?.isPlaced === false) return { text: `ping-hud: Agents pane opened but not shown${placed.reason ? `: ${placed.reason}` : ''}` }
    return { text: 'ping-hud: Agents pane opened' }
  } catch { return { text: 'ping-hud: could not open the Agents pane' } }
}

async function agentsPane($: any, e: any) {
  const { Box, Text, Button } = $.ui.resolve(e)
  const rows = asRows(await mine($, 'hudAgents')), nowMs = await $.clock.now()
  const c = agentCounts(rows, nowMs)
  return (
    <Box key="agents" flexDirection="column">
      <Text key="ah">{agentHeader(rows, nowMs)}</Text>
      {!rows.length ? <Text key="anone" dimColor>no agents started in this session yet</Text> : null}
      {agentGroups(rows).map(g => (
        <Box key={`ag:${g.key}`} flexDirection="column">
          <Text key={`agt:${g.key}`} bold>{g.title}</Text>
          {g.rows.map(x => <Text key={`ar:${x.id}`} dimColor={x.endMs !== undefined} color={x.outcome === 'failed' ? 'red' : undefined}>{`  ${agentLine(x, nowMs)}`}</Text>)}
        </Box>
      ))}
      <Box key="ab" flexDirection="row">
        {c.done || c.quiet ? <Button key="aclear" onPress={() => agentsDo($, agentClear)}>[ clear done ]</Button> : null}
        <Button key="aclose" onPress={() => { agentsOpen = false; return $.ui.close({ id: 'hud-agents' }) }}>[ Close ]</Button>
      </Box>
    </Box>
  )
}

// /hud args -> stored mode or glyph set; anything else answers usage and changes nothing.
export async function hudCommand($: any, args: string): Promise<{ text: string }> {
  const [a, b] = String(args || '').trim().toLowerCase().split(/\s+/)
  if (['on', 'off', 'compact', 'mini'].includes(a) && !b) {
    await $.store.set('hudMode', a)
    return { text: `ping-hud: band ${a}` }
  }
  if (a === 'goals' && !b) return openGoals($)
  if (a === 'agents' && !b) return openAgents($)
  if (a === 'glyphs' && (b === 'ascii' || b === 'unicode')) {
    await $.store.set('hudGlyphs', b)
    return { text: b === 'ascii' ? 'ping-hud: glyphs ascii: terminal bars and edge use # . | (Desktop bars are solid boxes and do not change)' : 'ping-hud: glyphs unicode: terminal bars and edge use block characters (Desktop bars are solid boxes and do not change)' }
  }
  return { text: USAGE }
}

// The one RUNS OUT toast: fires on entering RUNS OUT, at most once per 5h window (keyed by resetsAt).
export async function runsOutToast($: any, s: HudState, nowMs: number) {
  if ((await $.store.get('hudMode')) === 'off') return
  const c = chip({ usage: s.usage, measured: s.lastRefreshMs !== undefined, nowMs, turnActive: s.turnActive, lastRefreshMs: s.lastRefreshMs, samples: s.samples })
  const key = s.usage.rateLimits.find(r => r.kind === 'five_hour')?.resetsAt || ''
  const last = ((await mine($, 'hudToast')) as { prev: string | null; key: string | null } | undefined) || { prev: null, key: null }
  const t = shouldToast(key === last.key ? last.prev : null, c.word, key, last.key) // a new window starts a new episode
  await $.store.set(await own($, 'hudToast'), { prev: c.word, key: t.key })
  if (t.fire) $.ui.toast(`ping-hud: 5h limit RUNS OUT in ~${dur(c.t100Min ?? 0)}, resets in ${dur(c.resetMin ?? 0)}`)
}

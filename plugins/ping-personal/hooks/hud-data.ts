// ping-hud data layer: pure state fold + snapshot shape, and the $ calls that feed them.
import { modelName, type Sample } from './hud-rules'

const WIN_MS = 300 * 60000, SPARK = 12, KEEP_MS = 7 * 864e5
const WINDOWS: Record<string, string> = { five_hour: '5h', seven_day: '7d' }

type RL = { kind: string; percentUsed: number; resetsAt?: string }
type U = { context: { tokens?: number; percent?: number }; rateLimits: RL[] }
export type HudState = {
  model: string; ctxPct?: number; ctxTok: number; ctxDeltaTok: number; ctxSpark: number[]
  ctxTurnTok?: number // ctx tokens when the current turn started; the delta is measured from it
  usage: { rateLimits: RL[] }; samples: Sample[]; lastRefreshMs?: number; turnActive: boolean
}

export function collect(prev: HudState | undefined, u: U, modelId: string, nowMs: number): HudState {
  // ctx stays undefined until the engine measures it; a later gap keeps the last reading.
  const ctxPct = u.context.percent ?? prev?.ctxPct, ctxTok = u.context.tokens ?? 0
  const rl = u.rateLimits || []
  const moved = JSON.stringify(rl) !== JSON.stringify(prev?.usage.rateLimits ?? [])
  const five = rl.find(r => r.kind === 'five_hour')
  let samples = prev?.samples ?? []
  if (five) {
    const startMs = five.resetsAt ? Date.parse(five.resetsAt) - WIN_MS : nowMs - WIN_MS
    samples = samples.filter(s => s.tMs >= startMs)
    if (!samples.length || samples[samples.length - 1].pct !== five.percentUsed) samples = [...samples, { tMs: nowMs, pct: five.percentUsed }]
  }
  return {
    model: modelName(modelId), ctxPct, ctxTok, ctxDeltaTok: prev ? ctxTok - (prev.ctxTurnTok ?? prev.ctxTok) : 0, ctxTurnTok: prev?.ctxTurnTok,
    ctxSpark: u.context.percent === undefined ? prev?.ctxSpark ?? [] : [...(prev?.ctxSpark ?? []), u.context.percent].slice(-SPARK),
    usage: { rateLimits: rl }, samples,
    lastRefreshMs: rl.length && (moved || prev?.lastRefreshMs === undefined) ? nowMs : prev?.lastRefreshMs,
    turnActive: prev?.turnActive ?? false,
  }
}

// A background or workflow agent this session started and has not seen finish.
export type Bg = { id: string; act: string; tMs: number }

// Now text while background agents run; none running -> undefined (the caller shows 'idle').
export function waitingText(bg: Bg[] | undefined): string | undefined {
  if (!bg?.length) return undefined
  const newest = bg.reduce((a, b) => (b.tMs > a.tMs ? b : a))
  return `waiting: ${bg.length} agent${bg.length === 1 ? '' : 's'} running, ${newest.act}`
}

// agent.spawn input -> 'Agent (scan repo)' or 'Workflow agent 4 (review)', same cut as activity().
export function spawnAct(e: { description?: string; workflow?: { agentIndex: number } }): string {
  const d = String(e.description ?? ''), a = d.length > 30 ? d.slice(0, 29) + '...' : d
  const tail = a ? ` (${a})` : ''
  return e.workflow ? `Workflow agent ${e.workflow.agentIndex}${tail}` : `Agent${tail}`
}

// Same entry shape quota.ps1 prints, so /personal-quota can read either source.
export function snapshot(sessionId: string, s: HudState, nowMs: number, codex?: Codex | null) {
  const ageSec = s.lastRefreshMs === undefined ? null : Math.round((nowMs - s.lastRefreshMs) / 1000)
  return {
    sessionId, writtenAt: new Date(nowMs).toISOString(), model: s.model, ctxPct: s.ctxPct ?? null,
    claude: s.usage.rateLimits.filter(r => WINDOWS[r.kind]).map(r => ({
      provider: 'claude', window: WINDOWS[r.kind], percentUsed: r.percentUsed, resetsAt: r.resetsAt ?? null, source: 'mod', ageSec,
    })),
    codex: (['fiveH', 'sevenD'] as const).filter(k => codex?.[k]).map(k => ({
      provider: 'codex', window: k === 'fiveH' ? '5h' : '7d', percentUsed: codex![k]!.pct,
      resetsAt: new Date(codex![k]!.resetsAtMs).toISOString(), source: 'codex-log', ageSec: null,
    })),
  }
}

export function isOld(mtimeMs: number, nowMs: number) { return nowMs - mtimeMs > KEEP_MS }

// phase / blocked: the first unfinished row's own Phase number and whether its Status says BLOCKED.
export type Goal = { slug: string; done: number; total: number; step: string; phase?: string; blocked?: boolean }

// Phase Status table of an audit tracker -> progress; anything unexpected -> null.
export function parseGoal(text: string, slug: string): Goal | null {
  const sec = text.split(/^## Phase Status\s*$/m)[1]?.split(/^## /m)[0]
  if (!sec) return null
  const lines = sec.split(/\r?\n/).filter(l => l.trim().startsWith('|'))
  const cells = (l: string) => l.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim())
  const head = lines.length ? cells(lines[0]) : []
  const ti = head.indexOf('Title'), si = head.indexOf('Status')
  if (ti < 0 || si < 0) return null
  const rows = lines.slice(1).map(cells).filter(c => /^\d+$/.test(c[0] ?? ''))
  if (!rows.length) return null
  const done = rows.filter(c => /\bdone\b/i.test(c[si] ?? '')).length
  const next = rows.find(c => !/\bdone\b/i.test(c[si] ?? ''))
  if (!next) return { slug, done, total: rows.length, step: 'done' }
  return { slug, done, total: rows.length, step: next[ti], phase: next[0], blocked: /\bblocked\b/i.test(next[si] ?? '') }
}

export function goalBar(done: number, total: number, bar: string, empty: string): string {
  const n = Math.round((done / total) * 10)
  return `[${bar.repeat(n)}${empty.repeat(10 - n)}]`
}

// Claude's own step list. e = tool.call input, r = its answer (TaskCreate's id is only in the answer).
// TodoWrite replaces the list; TaskCreate / TaskUpdate / TaskList fold into it; other tools -> undefined.
export type Task = { id: string; title: string; status: string }
export function foldTasks(prev: Task[] | undefined, e: any, r: any): Task[] | undefined {
  const list = prev ?? [], res = r?.result, id = String(e?.taskId)
  switch (e?.tool) {
    case 'TodoWrite':
      return Array.isArray(e.todos) ? e.todos.map((t: any, i: number) => ({ id: String(i), title: String(t.content), status: String(t.status) })) : undefined
    case 'TaskCreate':
      return res?.task?.id ? [...list, { id: String(res.task.id), title: String(e.subject), status: 'pending' }] : undefined
    case 'TaskUpdate':
      if (!list.some(t => t.id === id)) return undefined
      if (e.status === 'deleted') return list.filter(t => t.id !== id)
      return list.map(t => (t.id === id ? { ...t, title: e.subject ?? t.title, status: e.status ?? t.status } : t))
    case 'TaskList':
      return Array.isArray(res?.tasks) ? res.tasks.map((t: any) => ({ id: String(t.id), title: String(t.subject), status: String(t.status) })) : undefined
  }
  return undefined
}

// Task list -> done count, total and the step to show (in progress, else next pending); empty -> null.
export function taskBar(tasks?: Task[] | null): { done: number; total: number; current: string } | null {
  if (!tasks?.length) return null
  const cur = tasks.find(t => t.status === 'in_progress') ?? tasks.find(t => t.status !== 'completed')
  return { done: tasks.filter(t => t.status === 'completed').length, total: tasks.length, current: cur ? cur.title : 'all done' }
}

// tool.call input -> 'Running Bash (npm test)'; a workflow script's agent -> 'Workflow agent 4 (review)'.
export function activity(e: any): string {
  if (!e?.tool) return 'idle'
  const raw = e.command ?? e.file_path ?? e.pattern ?? e.description ?? e.url ?? ''
  const first = String(raw).split(/\r?\n/)[0]
  const short = e.command ? first : first.split(/[\\/]+/).filter(Boolean).pop() ?? ''
  const a = short.length > 30 ? short.slice(0, 29) + '...' : short
  const tail = a ? ` (${a})` : ''
  return e.workflow ? `Workflow agent ${e.workflow.agentIndex}${tail}` : `Running ${e.tool}${tail}`
}

export type Win = { pct: number; resetsAtMs: number }
export type Codex = { fiveH?: Win; sevenD?: Win }
export type Status = { branch: string; defaultBranch: string; mem?: string; codex?: Codex | null }
export type Step = { thinking?: string | number; cacheHitPct?: number }

// Codex rollout log -> its last rate_limits reading (primary 300 min = 5h, secondary 10080 min = 7d).
export function parseCodex(text: string, nowMs: number): Codex | null {
  const lines = text.split(/\r?\n/)
  for (let i = lines.length - 1; i >= 0; i--) {
    if (!lines[i].includes('"rate_limits"')) continue
    let rl: any
    try { rl = JSON.parse(lines[i])?.payload?.rate_limits } catch { continue }
    if (!rl) continue
    const out: Codex = {}
    for (const w of [rl.primary, rl.secondary]) {
      if (!w || typeof w.used_percent !== 'number') continue
      const resetsAtMs = Number(w.resets_at) * 1000
      const win = { pct: resetsAtMs <= nowMs ? 0 : w.used_percent, resetsAtMs }
      if (w.window_minutes === 300) out.fiveH = win
      else if (w.window_minutes === 10080) out.sevenD = win
    }
    if (out.fiveH || out.sevenD) return out
  }
  return null
}

// Codex session folders to look in: today, then yesterday (local date, as Codex names them).
export function codexDays(nowMs: number): string[] {
  const p = (n: number) => String(n).padStart(2, '0')
  return [0, 1].map(d => { const t = new Date(nowMs - d * 864e5); return `${t.getFullYear()}/${p(t.getMonth() + 1)}/${p(t.getDate())}` })
}

// Share of the prompt the cache served, from a turn.step usage; undefined when nothing was read.
export function cacheHit(u: any): number | undefined {
  const read = u?.cache_read_input_tokens ?? 0, tot = read + (u?.input_tokens ?? 0)
  return tot ? Math.round((100 * read) / tot) : undefined
}

// Session-cumulative cache hit: adds one turn.step usage to the running sums.
export type CacheSum = { read: number; tot: number; cacheHitPct?: number }
export function cacheSum(prev: CacheSum | undefined, u: any): CacheSum {
  const p = { read: prev?.read ?? 0, tot: prev?.tot ?? 0 }
  if (!u) return { ...p, cacheHitPct: prev?.cacheHitPct }
  const r = u.cache_read_input_tokens ?? 0
  const read = p.read + r, tot = p.tot + r + (u.cache_creation_input_tokens ?? 0) + (u.input_tokens ?? 0)
  return { read, tot, cacheHitPct: tot ? Math.round((100 * read) / tot) : undefined }
}

// Total and free memory in KB -> '39/63G' (used/total).
export function memText(totalKb: number, freeKb: number): string | undefined {
  if (!(totalKb > 0)) return undefined
  const g = (kb: number) => Math.round(kb / 1048576)
  return `${g(totalKb - freeKb)}/${g(totalKb)}G`
}

// Snapshot names are '<session uuid>.json'; nothing else is ever handed to a delete process.
export function isSessionFile(name: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json$/i.test(name)
}

// turn.start -> true and records the ctx base for the delta; turn.complete -> false; no state stays no state.
export function withTurn(s: HudState | undefined, active: boolean): HudState | undefined {
  return s && { ...s, turnActive: active, ...(active ? { ctxTurnTok: s.ctxTok } : {}) }
}

// Message times: the last 200 characters of a prompt or reply and when it was sent. Rows carry no id,
// so a row finds its time by its own tail; a reply's last block ends like the turn's answer.
// ponytail: the same text sent twice shows the newer time on both rows.
export type Stamp = { tail: string; ms: number }
export type Times = { user: Stamp[]; assistant: Stamp[] }
const TAIL = 200, KEEP = 100
const tailOf = (text: string) => text.trim().slice(-TAIL)

export function addTime(prev: Times | undefined, kind: 'user' | 'assistant', text: string, ms: number): Times {
  const p: Times = { user: Array.isArray(prev?.user) ? prev!.user : [], assistant: Array.isArray(prev?.assistant) ? prev!.assistant : [] }
  const tail = tailOf(String(text ?? ''))
  if (!tail) return p
  return { ...p, [kind]: [...p[kind], { tail, ms }].slice(-KEEP) }
}

export function findTime(times: Times | undefined, kind: 'user' | 'assistant', text: string): number | undefined {
  const list = times?.[kind], tail = tailOf(String(text ?? ''))
  if (!Array.isArray(list) || !tail) return undefined
  for (let i = list.length - 1; i >= 0; i--) if (list[i]?.tail === tail && Number.isFinite(list[i].ms)) return list[i].ms
  return undefined
}

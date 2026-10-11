// ping-hud agents rules: the rows of the Agents pane, one per subagent this session started. Pure, no I/O.
// Fed by agent.spawn (start), tool.call carrying agentId (progress) and turn.complete carrying agentId (end).
// Events can arrive in any order and an agent can resume after a turn ends, so every update upserts.

export type Outcome = 'done' | 'stopped' | 'failed'
export type AgentRow = {
  id: string; type: string; desc: string
  run?: string; idx?: number // workflow runId and agent index, when a Workflow started it
  bg: boolean       // background or workflow agent: may keep running after the main turn ends
  tracked: boolean  // false when the spawn returned no agent id, so no tool or end event can reach the row
  startMs: number; lastMs: number; tools: number; last: string
  endMs?: number; outcome?: Outcome
}

// Finished rows beyond this many drop, oldest first; running rows never drop.
export const AGENTS_KEEP = 30
// A running row with no event for this long shows as quiet and can be cleared (a killed agent may never report).
export const STALE_MS = 10 * 60 * 1000

const running = (x: AgentRow) => x.endMs === undefined

function blank(id: string, nowMs: number): AgentRow {
  return { id, type: 'agent', desc: '', bg: true, tracked: true, startMs: nowMs, lastMs: nowMs, tools: 0, last: 'starting' }
}

// Replaces the row with the same id where it stands, or appends a new one, so the pane order stays stable.
function put(rows: AgentRow[], row: AgentRow): AgentRow[] {
  return rows.some(x => x.id === row.id) ? rows.map(x => (x.id === row.id ? row : x)) : [...rows, row]
}

// Drops the oldest finished rows until the list fits AGENTS_KEEP or only running rows are left.
export function trim(rows: AgentRow[]): AgentRow[] {
  let out = rows
  while (out.length > AGENTS_KEEP) {
    const done = out.filter(x => !running(x))
    if (!done.length) break
    const oldest = done.reduce((a, b) => ((a.endMs ?? 0) <= (b.endMs ?? 0) ? a : b))
    out = out.filter(x => x !== oldest)
  }
  return out
}

// agent.spawn: who the agent is. A row an early tool or end event already made keeps its progress.
export function agentStart(rows: AgentRow[], a: { id: string; type?: string; desc?: string; run?: string; idx?: number; bg: boolean; tracked: boolean }, nowMs: number): AgentRow[] {
  const prev = rows.find(x => x.id === a.id) ?? blank(a.id, nowMs)
  const row: AgentRow = { ...prev, type: a.type || 'agent', desc: a.desc || '', bg: a.bg, tracked: a.tracked, startMs: Math.min(prev.startMs, nowMs) }
  if (a.run) { row.run = a.run; row.idx = a.idx }
  return trim(put(rows, row))
}

// tool.call from that agent: one more tool and what it is doing now. A finished agent that calls a tool
// has resumed, so it runs again; an unknown id gets a row of its own.
export function agentTool(rows: AgentRow[], id: string, act: string, nowMs: number): AgentRow[] {
  const prev = rows.find(x => x.id === id) ?? blank(id, nowMs)
  const row: AgentRow = { ...prev, tools: prev.tools + 1, last: act.replace(/^Running /, ''), lastMs: nowMs, endMs: undefined, outcome: undefined }
  return trim(put(rows, row))
}

// turn.complete from that agent: its turn ended. The reason says how: aborted -> stopped, error or refusal -> failed.
export function agentEnd(rows: AgentRow[], id: string, nowMs: number, reason?: string): AgentRow[] {
  const prev = rows.find(x => x.id === id) ?? blank(id, nowMs)
  const outcome: Outcome = reason === 'aborted' ? 'stopped' : reason === 'error' || reason === 'refusal' ? 'failed' : 'done'
  return trim(put(rows, { ...prev, endMs: nowMs, lastMs: nowMs, outcome }))
}

// The main turn ended: a foreground agent cannot outlive it, so any still marked running is closed.
export function agentEndForeground(rows: AgentRow[], nowMs: number): AgentRow[] {
  return rows.map(x => (running(x) && !x.bg ? { ...x, endMs: nowMs, lastMs: nowMs, outcome: 'stopped' as Outcome, last: 'ended with the main turn' } : x))
}

export function isStale(x: AgentRow, nowMs: number): boolean {
  return running(x) && nowMs - x.lastMs > STALE_MS
}

// [ clear done ]: keeps only rows that are running and not quiet.
export function agentClear(rows: AgentRow[], nowMs: number): AgentRow[] {
  return rows.filter(x => running(x) && !isStale(x, nowMs))
}

// Store boundary: anything that is not a list of rows with a string id reads as no rows.
export function asRows(v: unknown): AgentRow[] {
  return Array.isArray(v) ? v.filter((x): x is AgentRow => !!x && typeof x === 'object' && typeof (x as any).id === 'string') : []
}

// Elapsed time as m:ss, or h:mm:ss from one hour.
export function clock(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000)), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = String(s % 60).padStart(2, '0')
  return h ? `${h}:${String(m).padStart(2, '0')}:${ss}` : `${m}:${ss}`
}

const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n - 3) + '...' : s)
const WORD: Record<Outcome, string> = { done: 'finished', stopped: 'interrupted', failed: 'error' }

// One pane line. Progress is a tool count and elapsed time: the engine gives no percent, so none is shown.
export function agentLine(x: AgentRow, nowMs: number): string {
  const who = x.run ? `workflow agent ${x.idx ?? '?'}` : x.type
  const n = `${x.tools} tool${x.tools === 1 ? '' : 's'}`
  const stale = isStale(x, nowMs)
  const state = (running(x) ? (stale ? 'quiet' : 'running') : x.outcome === 'done' || !x.outcome ? 'done' : x.outcome).padEnd(7)
  const doing = !running(x) ? WORD[x.outcome ?? 'done']
    : stale ? `no activity ${clock(nowMs - x.lastMs)}`
    : x.tracked ? cut(x.last, 24) : 'no live updates'
  return `${state}  ${who}  ${cut(x.desc, 30)}  -  ${doing}  -  ${n}  ${clock((x.endMs ?? nowMs) - x.startMs)}`
}

// Groups in start order: one group per workflow run, plain agents in one 'Agents' group.
export function agentGroups(rows: AgentRow[]): { key: string; title: string; rows: AgentRow[] }[] {
  const out: { key: string; title: string; rows: AgentRow[] }[] = []
  for (const x of [...rows].sort((a, b) => a.startMs - b.startMs)) {
    const key = x.run ? `wf:${x.run}` : 'agents'
    let g = out.find(o => o.key === key)
    if (!g) out.push(g = { key, title: x.run ? `Workflow ${x.run}` : 'Agents', rows: [] })
    g.rows.push(x)
  }
  return out
}

// Header counts: running (active), quiet (running but silent past STALE_MS) and finished.
export function agentCounts(rows: AgentRow[], nowMs: number): { running: number; quiet: number; done: number } {
  const quiet = rows.filter(x => isStale(x, nowMs)).length
  const active = rows.filter(x => running(x)).length - quiet
  return { running: active, quiet, done: rows.length - active - quiet }
}

export function agentHeader(rows: AgentRow[], nowMs: number): string {
  const c = agentCounts(rows, nowMs)
  return `${c.running} running, ${c.done} done${c.quiet ? `, ${c.quiet} quiet 10m+` : ''}`
}

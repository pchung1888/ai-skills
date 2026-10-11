import { test, expect } from 'claude-code/testing'
import { agentStart, agentTool, agentEnd, agentEndForeground, agentClear, agentLine, agentGroups, agentCounts, agentHeader, asRows, clock, trim, AGENTS_KEEP, STALE_MS, type AgentRow } from './hud-agents'

const T0 = 1_000_000
const fg = (id: string, extra: object = {}) => ({ id, type: 'general-purpose', desc: 'scan', bg: false, tracked: true, ...extra })

test('agentStart adds a running row; the same id keeps its place and its progress', () => {
  let rows = agentStart([], fg('a1'), T0)
  expect(rows).toEqual([{ id: 'a1', type: 'general-purpose', desc: 'scan', bg: false, tracked: true, startMs: T0, lastMs: T0, tools: 0, last: 'starting' }])
  rows = agentStart(rows, fg('a2'), T0 + 1)
  rows = agentTool(rows, 'a1', 'Running Glob (*.ts)', T0 + 2)
  rows = agentStart(rows, fg('a1', { desc: 'scan again' }), T0 + 3)
  expect(rows.map(r => [r.id, r.desc, r.tools])).toEqual([['a1', 'scan again', 1], ['a2', 'scan', 0]])
})

test('early events: a tool call or end before the spawn row exists is kept, and the spawn fills in who it was', () => {
  let rows = agentTool([], 'a1', 'Running Read (x.ts)', T0)
  rows = agentEnd(rows, 'a1', T0 + 5, 'answer')
  rows = agentStart(rows, fg('a1', { desc: 'late spawn' }), T0 + 6)
  expect(rows.map(r => [r.desc, r.tools, r.outcome, r.startMs])).toEqual([['late spawn', 1, 'done', T0]])
})

test('agentTool counts tools and keeps the latest activity; a finished agent that calls a tool has resumed', () => {
  let rows = agentStart([], fg('a1'), T0)
  rows = agentTool(rows, 'a1', 'Running Glob (*.ts)', T0 + 1)
  rows = agentTool(rows, 'a1', 'Running Read (hud-goals.ts)', T0 + 2)
  expect([rows[0].tools, rows[0].last, rows[0].lastMs]).toEqual([2, 'Read (hud-goals.ts)', T0 + 2])
  rows = agentEnd(rows, 'a1', T0 + 3, 'answer')
  rows = agentTool(rows, 'a1', 'Running Bash (ls)', T0 + 4)
  expect([rows[0].endMs, rows[0].outcome, rows[0].tools]).toEqual([undefined, undefined, 3])
})

test('agentEnd: answer -> done, aborted -> stopped, error or refusal -> failed; a later turn end updates it', () => {
  const at = (reason: string) => agentEnd(agentStart([], fg('a1'), T0), 'a1', T0 + 10, reason)[0].outcome
  expect([at('answer'), at('aborted'), at('error'), at('refusal')]).toEqual(['done', 'stopped', 'failed', 'failed'])
  let rows = agentEnd(agentStart([], fg('a1'), T0), 'a1', T0 + 10, 'answer')
  rows = agentEnd(rows, 'a1', T0 + 99, 'answer')
  expect(rows[0].endMs).toBe(T0 + 99)
})

test('agentEndForeground closes running foreground rows only; background rows keep running', () => {
  let rows = agentStart([], fg('f1'), T0)
  rows = agentStart(rows, fg('b1', { bg: true }), T0)
  rows = agentEndForeground(rows, T0 + 7)
  expect(rows.map(r => [r.id, r.outcome, r.endMs])).toEqual([['f1', 'stopped', T0 + 7], ['b1', undefined, undefined]])
})

test('trim drops the oldest finished rows first and never a running one', () => {
  let rows = agentStart([], fg('long', { bg: true }), T0)
  for (let i = 0; i < AGENTS_KEEP + 5; i++) rows = agentEnd(agentStart(rows, fg(`s${i}`), T0 + i), `s${i}`, T0 + i + 1, 'answer')
  expect(rows.length).toBe(AGENTS_KEEP)
  expect(rows[0].id).toBe('long')
  expect(rows.some(r => r.id === 's0')).toBe(false)
  const allRunning = Array.from({ length: AGENTS_KEEP + 2 }, (_, i) => ({ ...agentStart([], fg(`r${i}`), T0)[0] }))
  expect(trim(allRunning).length).toBe(AGENTS_KEEP + 2)
})

test('quiet rows: running with no event for STALE_MS shows as quiet and [ clear done ] removes it', () => {
  let rows = agentStart([], fg('q1', { bg: true }), T0)
  rows = agentStart(rows, fg('r1', { bg: true }), T0 + STALE_MS)
  rows = agentEnd(agentStart(rows, fg('d1'), T0), 'd1', T0 + 1, 'answer')
  const now = T0 + STALE_MS + 1000
  expect(agentCounts(rows, now)).toEqual({ running: 1, quiet: 1, done: 1 })
  expect(agentHeader(rows, now)).toBe('1 running, 1 done, 1 quiet 10m+')
  expect(agentLine(rows[0], now)).toContain('quiet    general-purpose')
  expect(agentLine(rows[0], now)).toContain('no activity 10:01')
  expect(agentClear(rows, now).map(r => r.id)).toEqual(['r1'])
})

test('clock and agentLine: m:ss / h:mm:ss; tool cut to 24, desc to 30; untracked and workflow rows; no percent', () => {
  expect([clock(0), clock(65_000), clock(3_725_000)]).toEqual(['0:00', '1:05', '1:02:05'])
  const run: AgentRow = { id: 'a1', type: 'general-purpose', desc: 'Test agent A', bg: true, tracked: true, startMs: T0, lastMs: T0, tools: 3, last: 'Glob (*.ts)' }
  expect(agentLine(run, T0 + 24_000)).toBe('running  general-purpose  Test agent A  -  Glob (*.ts)  -  3 tools  0:24')
  expect(agentLine({ ...run, tools: 1, endMs: T0 + 30_000, outcome: 'done' }, T0 + 99_000)).toBe('done     general-purpose  Test agent A  -  finished  -  1 tool  0:30')
  expect(agentLine({ ...run, endMs: T0 + 1, outcome: 'stopped' }, T0)).toContain('stopped  general-purpose  Test agent A  -  interrupted')
  expect(agentLine({ ...run, endMs: T0 + 1, outcome: 'failed' }, T0)).toContain('failed   general-purpose  Test agent A  -  error')
  expect(agentLine({ ...run, last: 'Bash (npm run some-very-long-script --flag)' }, T0)).toContain('-  Bash (npm run some-ve...  -')
  expect(agentLine({ ...run, desc: 'a description that is far longer than thirty' }, T0)).toContain('a description that is far l...')
  expect(agentLine({ ...run, tracked: false }, T0)).toContain('-  no live updates  -')
  expect(agentLine({ ...run, run: 'wf_1', idx: 2 }, T0)).toContain('workflow agent 2')
  expect(agentLine({ ...run, run: 'wf_1' }, T0)).toContain('workflow agent ?')
  expect(agentLine(run, T0)).not.toContain('%')
})

test('agentGroups: plain agents in one group, one group per workflow run, in start order', () => {
  let rows = agentStart([], { id: 'w2', run: 'wf_1', idx: 2, bg: true, tracked: true }, T0 + 2)
  rows = agentStart(rows, fg('a1'), T0)
  rows = agentStart(rows, { id: 'w1', run: 'wf_1', idx: 1, bg: true, tracked: true }, T0 + 1)
  expect(agentGroups(rows).map(x => [x.title, x.rows.map(r => r.id)])).toEqual([['Agents', ['a1']], ['Workflow wf_1', ['w1', 'w2']]])
})

test('asRows: a stored non-list or rows without an id read as no rows', () => {
  expect(asRows(undefined)).toEqual([])
  expect(asRows({ id: 'x' })).toEqual([])
  expect(asRows([null, 3, { nope: 1 }, { id: 'ok' }]).map(r => r.id)).toEqual(['ok'])
})

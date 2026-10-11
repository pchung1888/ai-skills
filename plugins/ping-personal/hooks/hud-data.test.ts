import { test, expect } from 'claude-code/testing'
import { collect, snapshot, isOld, isSessionFile, withTurn, waitingText, spawnAct } from './hud-data'

const now = 1e12
const iso = (ms: number) => new Date(ms).toISOString()
const usage = (pct: number, ctx = 42) => ({
  startedAt: now - 1000,
  context: { window: 200000, tokens: ctx * 2000, percent: ctx },
  rateLimits: [
    { kind: 'five_hour', percentUsed: pct, resetsAt: iso(now + 120 * 60000) },
    { kind: 'seven_day', percentUsed: 3, resetsAt: iso(now + 6 * 864e5) },
  ],
})

test('collect fills model, ctx and usage', () => {
  const s = collect(undefined, usage(20), 'claude-opus-5-5', now)
  expect(s.model).toBe('Opus 5.5')
  expect(s.ctxPct).toBe(42)
  expect(s.ctxDeltaTok).toBe(0)
  expect(s.lastRefreshMs).toBe(now)
  expect(s.samples).toEqual([{ tMs: now, pct: 20 }])
})

test('collect drops samples outside the 5h window and keeps 12 ctx points', () => {
  let s = collect(undefined, usage(10), 'x', now - 400 * 60000)
  for (let i = 0; i < 14; i++) s = collect(s, usage(20 + i, i), 'x', now + i)
  expect(s.samples[0].pct).toBe(20)
  expect(s.ctxSpark.length).toBe(12)
  expect(s.ctxSpark[11]).toBe(13)
  expect(s.ctxDeltaTok).toBe(2000)
})

test('collect keeps lastRefreshMs when rateLimits did not move', () => {
  const a = collect(undefined, usage(20), 'x', now)
  const b = collect(a, usage(20), 'x', now + 60000)
  expect(b.lastRefreshMs).toBe(now)
  expect(b.samples.length).toBe(1)
})

test('empty rateLimits keeps usage empty, no samples', () => {
  const s = collect(undefined, { ...usage(0), rateLimits: [] }, 'x', now)
  expect(s.usage.rateLimits).toEqual([])
  expect(s.samples).toEqual([])
})

test('snapshot has quota output shape', () => {
  const s = collect(undefined, usage(20), 'claude-opus-5-5', now)
  const j = snapshot('sid', s, now + 30000)
  expect(j.sessionId).toBe('sid')
  expect(j.ctxPct).toBe(42)
  expect(j.codex).toEqual([])
  expect(j.claude.length).toBe(2)
  expect(j.claude[0]).toEqual({ provider: 'claude', window: '5h', percentUsed: 20, resetsAt: iso(now + 120 * 60000), source: 'mod', ageSec: 30 })
  expect(j.claude[1].window).toBe('7d')
})

test('isOld is true past 7 days', () => {
  expect(isOld(now - 8 * 864e5, now)).toBe(true)
  expect(isOld(now - 6 * 864e5, now)).toBe(false)
})

test('isSessionFile: only <uuid>.json names may reach a delete', () => {
  expect(isSessionFile('2eeebbb1-96eb-474c-8b2f-d0fc49fbdb85.json')).toBe(true)
  expect(isSessionFile('2EEEBBB1-96EB-474C-8B2F-D0FC49FBDB85.JSON')).toBe(true)
  for (const bad of ['a&calc.json', '..' + String.fromCharCode(92) + 'x.json', 'x.json', '2eeebbb1-96eb-474c-8b2f-d0fc49fbdb85.json&x'])
    expect(isSessionFile(bad)).toBe(false)
})

test('withTurn: turn.start sets turnActive, turn.complete clears it, collect keeps it', () => {
  const s = collect(undefined, usage(20), 'claude-opus-5-5', now)
  expect(s.turnActive).toBe(false)
  const on = withTurn(s, true)!
  expect(on.turnActive).toBe(true)
  expect(collect(on, usage(21), 'claude-opus-5-5', now + 1000).turnActive).toBe(true)
  expect(withTurn(on, false)!.turnActive).toBe(false)
  expect(withTurn(undefined, true)).toBeUndefined()
})

test('collect keeps ctx unmeasured until the engine reports a percent; spark skips it', () => {
  const s = collect(undefined, { context: {}, rateLimits: [] } as any, 'x', now)
  expect(s.ctxPct).toBe(undefined)
  expect(s.ctxSpark).toEqual([])
  const t = collect(s, usage(20, 30), 'x', now + 1)
  expect(t.ctxSpark).toEqual([30])
  expect(collect(t, { context: {}, rateLimits: [] } as any, 'x', now + 2).ctxSpark).toEqual([30])
})

test('ctx delta is measured from the turn.start value, so a second refresh keeps it', () => {
  const a = collect(undefined, usage(20, 10), 'x', now)        // 20000 tokens
  const t = withTurn(a, true)!                                  // turn starts at 20000
  const b = collect(t, usage(20, 15), 'x', now + 1)             // 30000 after session.measure
  const c = collect(b, usage(20, 15), 'x', now + 2)             // turn.complete refresh, same tokens
  expect(b.ctxDeltaTok).toBe(10000)
  expect(c.ctxDeltaTok).toBe(10000)
})

test('second turn.start re-bases ctx delta to the latest reading', () => {
  const a = withTurn(collect(undefined, usage(20, 10), 'x', now), true)!
  const b = withTurn(collect(a, usage(20, 15), 'x', now + 1), true)!  // aborted turn, new turn starts
  expect(collect(b, usage(20, 16), 'x', now + 2).ctxDeltaTok).toBe(2000)
})

test('waitingText: none -> undefined; else count and newest activity', () => {
  expect(waitingText(undefined)).toBe(undefined)
  expect(waitingText([])).toBe(undefined)
  expect(waitingText([{ id: 'a', act: 'Agent (old)', tMs: 1 }, { id: 'b', act: 'Workflow agent 2 (review)', tMs: 2 }]))
    .toBe('waiting: 2 agents running, Workflow agent 2 (review)')
  expect(waitingText([{ id: 'a', act: 'Agent (scan)', tMs: 1 }])).toBe('waiting: 1 agent running, Agent (scan)')
  expect(spawnAct({ description: 'x'.repeat(40) })).toBe(`Agent (${'x'.repeat(29)}...)`)
  expect(spawnAct({ description: 'review', workflow: { agentIndex: 4 } })).toBe('Workflow agent 4 (review)')
})

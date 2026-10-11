import { test, expect } from 'claude-code/testing'
import { verdict, weather, pace, chip, pctTone, shouldToast, modelName } from './hud-rules'

const now = 1e12
const resetsAt = now + 120 * 60000 // 180 min into the 300-min window
const iso = (ms: number) => new Date(ms).toISOString()
const U = (pct: number, rMs = resetsAt) => ({ rateLimits: [{ kind: 'five_hour', percentUsed: pct, resetsAt: iso(rMs) }, { kind: 'seven_day', percentUsed: 3, resetsAt: iso(now + 6 * 864e5) }] })
const S = [{ tMs: now - 180 * 60000, pct: 0 }, { tMs: now, pct: 50 }]

test('verdict boundaries m=t100-reset (test 7)', () => {
  expect(verdict(71, 72)).toBe('RUNS OUT')
  expect(verdict(72, 72)).toBe('RUNS OUT')
  expect(verdict(73, 72)).toBe('TIGHT')
  expect(verdict(101, 72)).toBe('TIGHT')
  expect(verdict(102, 72)).toBe('OK')
})

test('weather word and tone agree (test 11)', () => {
  const cases: [number, string, string][] = [[39, 'Clear', 'default'], [40, 'Cloudy', 'default'], [59, 'Cloudy', 'default'], [60, 'Showers', 'warn'], [79, 'Showers', 'warn'], [80, 'Storm', 'bad']]
  for (const [p, word, tone] of cases) expect(weather(p)).toEqual({ word, tone })
})

test('LEARNING until 2 points consumed, then window average (test 13)', () => {
  expect(pace({ usedPct: 1, resetsAtMs: resetsAt, nowMs: now, samples: [{ tMs: now - 180 * 60000, pct: 0 }, { tMs: now, pct: 1 }] }).state).toBe('LEARNING')
  const p = pace({ usedPct: 2, resetsAtMs: resetsAt, nowMs: now, samples: [{ tMs: now - 180 * 60000, pct: 0 }, { tMs: now, pct: 2 }] })
  expect(p.state).toBe('READY')
  expect(Math.abs(p.pctPerMin - 2 / 180) < 1e-9).toBe(true)
  expect(p.resetMin).toBe(120)
})

test('fresh session: LEARNING from the window percentUsed, not in-session consumption', () => {
  const r84 = now + 84 * 60000
  const c = chip({ usage: U(28, r84), measured: true, lastRefreshMs: now, nowMs: now })
  expect(c.word).toBe('OK')
  expect(Math.abs(c.t100Min! - 72 / (28 / 216)) < 1e-6).toBe(true) // ~555 min, far past the 84 min reset
  expect(chip({ usage: U(1, r84), measured: true, lastRefreshMs: now, nowMs: now }).word).toBe('LEARNING')
})

test('chip states: Loading, NO DATA, STALE, idle age (test 2, Review Focus 2)', () => {
  expect(chip({ usage: { rateLimits: [] }, measured: false, nowMs: now }).word).toBe('...')
  expect(chip({ usage: { rateLimits: [] }, measured: true, nowMs: now }).word).toBe('NO DATA')
  expect(chip({ usage: undefined, measured: true, nowMs: now }).word).toBe('NO DATA')
  // turn completed but newest reading is 10+ min older -> STALE, never OK
  const st = chip({ usage: U(50), measured: true, lastRefreshMs: now - 10 * 60000, lastTurnMs: now, nowMs: now, samples: S })
  expect(st.word).toBe('STALE'); expect(st.tone).toBe('warn')
  // active long turn with old data: no clock rule
  expect(chip({ usage: U(50), measured: true, turnActive: true, lastRefreshMs: now - 30 * 60000, lastTurnMs: now - 31 * 60000, nowMs: now, samples: S }).word).not.toBe('STALE')
  // idle, 12 min old data -> verdict plus age, never bare
  const idle = chip({ usage: U(50), measured: true, lastRefreshMs: now - 12 * 60000, lastTurnMs: now - 12 * 60000, nowMs: now, samples: S })
  expect(idle.word).not.toBe('STALE'); expect(idle.ageMin).toBe(12)
  // fresh data with a verdict
  const fresh = chip({ usage: U(50), measured: true, lastRefreshMs: now, nowMs: now, samples: S })
  expect(fresh.word).toBe('OK'); expect(fresh.ageMin).toBe(undefined)
})

test('past resetsAt treated as reset: LEARNING, never RUNS OUT (Review Focus 1)', () => {
  const c = chip({ usage: U(90, now - 60000), measured: true, lastRefreshMs: now, nowMs: now, samples: S })
  expect(c.word).toBe('LEARNING'); expect(c.usedPct).toBe(0)
})

test('toast dedupe (tests 9, 10)', () => {
  expect(shouldToast('OK', 'RUNS OUT', 'r1', null).fire).toBe(true)
  expect(shouldToast('RUNS OUT', 'RUNS OUT', 'r1', 'r1').fire).toBe(false)
  expect(shouldToast('TIGHT', 'RUNS OUT', 'r1', 'r1').fire).toBe(false)
  expect(shouldToast('TIGHT', 'RUNS OUT', 'r2', 'r1').fire).toBe(true)
  for (const w of ['TIGHT', 'STALE', 'LEARNING', 'NO DATA']) expect(shouldToast('OK', w, 'r1', null).fire).toBe(false)
})

test('pct tones and model names', () => {
  expect(pctTone('cache', 5, 'bad')).toBe('default')
  expect(pctTone('7d', 80, 'ok')).toBe('warn')
  expect(pctTone('7d', 79, 'ok')).toBe('default')
  expect(pctTone('5h', 71, 'bad')).toBe('bad')
  expect(pctTone('ctx', 60, 'ok')).toBe('warn')
  expect(modelName('claude-opus-5-5')).toBe('Opus 5.5')
  expect(modelName('claude-sonnet-5-5')).toBe('Sonnet 5.5')
  expect(modelName('claude-haiku-5-5')).toBe('Haiku 5.5')
  expect(modelName('claude-fable-5-1')).toBe('Fable 5.1')
  expect(modelName('claude-x-9')).toBe('claude-x-9')
})

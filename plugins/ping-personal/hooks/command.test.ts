import { test, expect } from 'claude-code/testing'
import { hudCommand, runsOutToast } from './register'

const NOW = Date.parse('2026-10-08T12:00:00Z')

// Fake $ with a Map store that outlives one "load" (the same object is reused) and a toast log.
function fake(store = new Map<string, unknown>()) {
  const toasts: string[] = []
  return { toasts, store, $: {
    session: { id: async () => 'sid-a' },
    store: { get: async (k: string) => store.get(k), set: async (k: string, v: unknown) => { store.set(k, v) } },
    ui: { toast: (t: string) => { toasts.push(t) } },
  } }
}

// 80% used 228 min into the window: 100% in ~57m, reset in 72m -> RUNS OUT.
function hud(resetMin: number, pct = 80) {
  return { model: 'Opus 5.5', ctxPct: 10, ctxTok: 1, ctxDeltaTok: 0, ctxSpark: [10], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: pct, resetsAt: new Date(NOW + resetMin * 60000).toISOString() }] } } as any
}

test('/personal-hud off|on|compact persists in the store and survives a reload', async () => {
  const f = fake()
  for (const m of ['off', 'compact', 'mini', 'on']) {
    expect((await hudCommand(f.$, ` ${m} `)).text).toContain(m)
    expect(await fake(f.store).$.store.get('hudMode')).toBe(m)
  }
})

test('/personal-hud glyphs ascii|unicode switches the glyph set', async () => {
  const f = fake()
  await hudCommand(f.$, 'glyphs unicode')
  expect(f.store.get('hudGlyphs')).toBe('unicode')
  expect((await hudCommand(f.$, 'GLYPHS ascii')).text).toBe('ping-hud: glyphs ascii: terminal bars and edge use # . | (Desktop bars are solid boxes and do not change)')
  expect(f.store.get('hudGlyphs')).toBe('ascii')
})

test('/personal-hud bad arg -> usage text, no state change', async () => {
  const f = fake(new Map<string, unknown>([['hudMode', 'compact']]))
  for (const a of ['', 'loud', 'glyphs emoji']) expect((await hudCommand(f.$, a)).text).toMatch(/^Usage: \/personal-hud/)
  expect([...f.store.entries()]).toEqual([['hudMode', 'compact']])
})

test('/personal-hud usage names the goals subcommand', async () => {
  expect((await hudCommand(fake().$, 'bogus')).text).toContain('/personal-hud goals')
})

test('RUNS OUT toast: exactly one per 5h window, again for a new window', async () => {
  const f = fake()
  await runsOutToast(f.$, hud(72), NOW)
  await runsOutToast(f.$, hud(72), NOW)
  await runsOutToast(f.$, hud(72, 81), NOW + 60000)
  expect(f.toasts.length).toBe(1)
  expect(f.toasts[0]).toContain('RUNS OUT')
  await runsOutToast(f.$, hud(72, 10), NOW) // back to OK in the same window: no re-fire on re-entry
  await runsOutToast(f.$, hud(72), NOW)
  expect(f.toasts.length).toBe(1)
  await runsOutToast(f.$, hud(73), NOW) // new resetsAt = new window
  expect(f.toasts.length).toBe(2)
})

test('RUNS OUT toast: never while OK, never while /hud off', async () => {
  const ok = fake()
  await runsOutToast(ok.$, hud(72, 10), NOW)
  expect(ok.toasts.length).toBe(0)
  const off = fake(new Map<string, unknown>([['hudMode', 'off']]))
  await runsOutToast(off.$, hud(72), NOW)
  expect(off.toasts.length).toBe(0)
})

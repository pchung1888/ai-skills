import { test, expect } from 'claude-code/testing'
import { layout, rowText, cell, dur, burnSvg, type RenderOpts } from './hud-render'

const B = String.fromCharCode(92) // backslash, kept out of string literals
const NOW = Date.parse('2026-10-08T12:00:00Z')
const min = (m: number) => new Date(NOW + m * 60000).toISOString()
// used% at minute (300 - resetMin) of the window; pace = used / elapsed.
function state(used: number, resetMin: number, ctxPct = 18) {
  return {
    model: 'Opus 5.5', ctxPct, ctxTok: 50000, ctxDeltaTok: 12000, ctxSpark: [5, 10, 18], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: used, resetsAt: min(resetMin) }, { kind: 'seven_day', percentUsed: 1, resetsAt: min(9600) }] },
  }
}
// ascii glyphs keep the expected strings readable; rows() drops the 1-char left edge.
const o = (x: Partial<RenderOpts> = {}): RenderOpts => ({ surface: 'terminal', bodyColumns: 140, glyphs: 'ascii', nowMs: NOW, cwd: ['D:', 'work', 'demo-repo'].join(B), ...x })
const rows = (s: any, x?: Partial<RenderOpts>) => layout(s, o(x))!.map(r => rowText(r).slice(1))

test('cell is a right-aligned 4-char percent', () => {
  expect(cell(5)).toBe('  5%')
  expect(cell(100)).toBe('100%')
  expect(cell(undefined)).toBe('  --')
  expect(dur(44)).toBe('44m')
  expect(dur(72)).toBe('1h12')
  expect(dur(9600, 'reset')).toBe('6d16h')
})

test('OK wide and narrow rows match the presentation mockups', () => {
  const s = state(5, 72) // 5% at minute 228: 100% in ~72h, far past reset
  const w = rows(s)
  expect(w).toHaveLength(4)
  expect(w[0]).toBe('Model    Opus 5.5  | ctx  18% +12k  | 5h   5% reset 1h12  | 7d   1% reset 6d16h')
  expect(w[1]).toBe(`Session  branch -  dir D:${B}...${B}demo-repo  cache  --`)
  expect(w[2]).toBe('Now      idle')
  expect(w[3]).toBe("Forecast  OK  5h won't run out: at this pace 100% in 72h12, after the reset in 1h12") // 5h quota only
  expect(w[3]).not.toContain('18%')
  const n = rows(s, { bodyColumns: 90 })
  expect(n[0]).toBe('Model    Opus 5.5  | ctx  18% +12k  | 5h   5% reset 1h12  | 7d   1% reset 6d16h')
  expect(n[3]).toBe("Forecast  OK  5h won't run out: at this pace 100% in 72h12, after the reset in 1h12")
  expect(n[3]).not.toContain('18%')
  for (const surface of ['terminal', 'desktop']) for (const bodyColumns of [140, 86]) expect(rows(s, { surface, bodyColumns })[0].endsWith(' reset 6d16h')).toBe(true) // 7d reset fits
  for (const r of [...w, ...n]) expect(r.slice(0, 9)).toMatch(/^(Model|Session|Now|Forecast) *$/)
})

test('RUNS OUT and TIGHT sentences name the actionable minutes', () => {
  const r = rows(state(80, 72))[3] // pace 80/228 per min -> 100% in ~57m
  expect(r).toBe('Forecast  RUNS OUT  5h will run out: at this pace 100% in 57m, 15m BEFORE the reset in 1h12 -- wrap up or pause')
  const t = rows(state(70, 72))[3] // pace 70/228 -> 100% in ~98m, 26m to spare
  expect(t).toContain(' TIGHT  5h is close: at this pace 100% in 1h38, only 26m after the reset in 1h12 -- slow down')
  expect(t).not.toContain('ctx')
  // Narrow drops the advice after ' -- '.
  expect(rows(state(80, 72), { bodyColumns: 86 })[3]).toBe('Forecast  RUNS OUT  5h will run out: at this pace 100% in 57m, 15m BEFORE the reset in 1h12')
  expect(rows(state(1, 72))[3].endsWith(' LEARNING  5h under 2% used -- no pace yet')).toBe(true)
  expect(rows(state(1, 72), { bodyColumns: 86 })[3].endsWith(' LEARNING  5h under 2% used')).toBe(true)
  const runs = layout(state(80, 72), o())![3].spans.find(x => x.t === ' RUNS OUT ')!
  expect(runs).toMatchObject({ tone: 'bad', b: true, inv: true, keep: true })
  const ok = layout(state(5, 72), o())![3].spans.find(x => x.t === ' OK ')!
  expect(ok).toMatchObject({ tone: 'ok', inv: false }) // OK is a plain green word, not a badge (decision 29)
})

test('past resetsAt shows 5h as   0%, never RUNS OUT', () => {
  const r = rows(state(99, -1))
  expect(r[0]).toContain('  | 5h   0%')
  expect(r[3]).toContain(' LEARNING ')
})

test('row budget, compact, off and statusLine', () => {
  const s = state(5, 72)
  const keys = (x: Partial<RenderOpts>) => layout(s, o(x))!.map(r => r.key)
  expect(keys({ maxRows: 3 })).toEqual(['model', 'now', 'forecast'])
  expect(keys({ maxRows: 2 })).toEqual(['now', 'forecast'])
  expect(keys({ maxRows: undefined })).toHaveLength(4)
  expect(keys({ mode: 'compact' })).toEqual(['now', 'forecast'])
  expect(keys({ statusLinePresent: true })).toEqual(['model', 'now', 'forecast'])
  expect(keys({ statusLinePresent: true, surface: 'desktop' })).toHaveLength(4)
  expect(layout(s, o({ mode: 'off' }))).toBeNull()
  expect(keys({ mode: 'mini' })).toEqual(['mini']) // Hide state: one row, whatever the width or row budget
})

test('unprotected spans may truncate; chip, 5h and forecast never do', () => {
  const f = layout(state(80, 72), o())!
  expect(f[0].spans.find(x => x.t.includes('5h'))!.keep).toBe(true)
  expect(f[3].spans.slice(0, 3).every(x => x.keep)).toBe(true)
})

test('glyphs: unicode blocks by default on both surfaces, ascii on request', () => {
  for (const surface of ['terminal', 'desktop']) {
    expect(rows(undefined, { surface, glyphs: undefined, tasks: TASKS })[2]).toContain('[\u2588\u2588\u2588\u2591\u2591\u2591\u2591\u2591\u2591\u2591]') // Tasks bar
  }
  expect(rows(state(5, 72), { surface: 'desktop' })[0]).toContain('  ctx  18% +12k  5h') // desktop: spaces, no dividers
})

test('calm palette: edge, labels, model, branch and bar levels', () => {
  const st = { branch: 'topic/mod', defaultBranch: 'main' }
  const r = layout(state(5, 72, 65), o({ status: st }))!
  for (const row of r) expect(row.spans[0]).toEqual({ t: ' ', keep: true }) // OK: blank edge, same width
  expect(r[0].spans[1]).toMatchObject({ t: 'Model    ', d: true })
  expect(r[0].spans[2]).toEqual({ t: 'Opus 5.5', b: true, keep: true })
  expect(r[0].spans.some(x => x.k)).toBe(false) // Model row has no bars
  expect(layout(state(5, 72, 65), o({ surface: 'desktop' }))![0].spans.find(x => x.t === '  65%')!.tone).toBe('warn')
  expect(r[1].spans.find(x => x.t === 'topic/mod')!.tone).toBeUndefined()
  expect(r[1].spans.find(x => x.t === ' from ')).toMatchObject({ d: true })
  expect(layout(state(5, 72, 85), o({ surface: 'desktop' }))![0].spans.find(x => x.t === '  85%')!.tone).toBe('bad')
  expect(layout(state(80, 72), o())![0].spans[0]).toMatchObject({ t: '|', tone: 'bad' })
  expect(layout(undefined, o())![0].spans[0]).toEqual({ t: ' ', keep: true })
})

test('calm palette: all-healthy has no color but the OK word; RUNS OUT has red edge and filled badge', () => {
  const healthy = layout(state(5, 72, 30), o({ surface: 'desktop', status: { branch: 'topic/mod', defaultBranch: 'main' } }))!
  const toned = healthy.flatMap(r => r.spans).filter(x => x.tone === 'ok' || x.tone === 'warn' || x.tone === 'bad')
  expect(toned).toEqual([expect.objectContaining({ t: ' OK ', tone: 'ok' })])
  expect(toned[0].inv).toBeFalsy()
  const hot = layout(state(80, 72), o())!
  expect(hot[0].spans[0]).toMatchObject({ t: '|', tone: 'bad' })
  expect(hot[3].spans.find(x => x.svg)).toMatchObject({ t: ' RUNS OUT ', tone: 'bad', inv: true })
})

test('terminal numbers: green < 50, yellow 50-79, red >= 80; reset times in the time color; desktop numbers plain', () => {
  const tone = (s: any, t: string, x: Partial<RenderOpts> = {}) => layout(s, o(x))![0].spans.find(sp => sp.t === t)?.tone
  expect(tone(state(5, 72, 30), '  30%')).toBe('ok')
  expect(tone(state(5, 72, 65), '  65%')).toBe('warn')
  expect(tone(state(5, 72, 85), '  85%')).toBe('bad')
  expect(tone(state(5, 72, 30), '   5%')).toBe('ok')
  expect(tone(state(5, 72, 30), '1h12')).toBe('time')
  expect(tone(state(5, 72, 30), '  30%', { surface: 'desktop' })).toBeUndefined()
  expect(tone(state(5, 72, 30), '1h12', { surface: 'desktop' })).toBeUndefined()
})

test('Loading: no state shows ... chip and -- cells', () => {
  const r = rows(undefined)
  expect(r[0]).toContain('  | 5h   --')
  expect(r[3].startsWith('Forecast  ... ')).toBe(true)
})

test('burnSvg: scale, tick, clamp arrow, RUNS OUT gap, size cap', () => {
  const s = burnSvg({ usedPct: 5, t100Min: 100, resetMin: 72, tone: 'ok' })
  // S = min(300, max(72,100) * 1.1) = 110; tick x = 320*72/110 = 209.5
  expect(s).toContain('x1="209.5"')
  expect(s).toContain('width="16"')
  expect(s.length).toBeLessThan(131072)
  const far = burnSvg({ usedPct: 5, t100Min: 4000, resetMin: 72, tone: 'ok' })
  expect(far).toContain('<path') // arrowhead at x=320
  expect(far).toContain('320,9')
  const runs = burnSvg({ usedPct: 80, t100Min: 57, resetMin: 72, tone: 'bad' })
  expect(runs).toContain('data-gap="bad"')
  expect(burnSvg({ usedPct: 5, t100Min: 100, resetMin: 72, tone: 'ok' })).not.toContain('data-gap')
})

test('desktop forecast row carries the Svg; terminal does not; desktop narrow drops cwd path', () => {
  const s = state(5, 72)
  expect(layout(s, o({ surface: 'desktop' }))![3].svg).toContain('<svg')
  expect(layout(s, o({ surface: 'desktop', bodyColumns: 86 }))![3].svg).toContain('<svg')
  expect(layout(s, o())![3].svg).toBeUndefined()
  expect(rows(s, { surface: 'desktop', bodyColumns: 86 })[1]).toBe('Session  branch -  cache  --')
})

const TASKS = [{ id: '0', title: 'Write tests', status: 'completed' }, { id: '1', title: 'Implement', status: 'in_progress' }, { id: '2', title: 'Commit', status: 'pending' }]

test('Now row: goal alone shows phase N of M (P%)', () => {
  const r = layout(undefined, o({ now: 'Running Bash (npm test)', goals: [{ slug: 'ping-hud', done: 3, total: 7, step: 'Data layer' }] }))!
  expect(rowText(r[2]).slice(1)).toBe('Now      Running Bash (npm test)  | Goal ping-hud 4/7  Data layer')
  const d = layout(undefined, o({ surface: 'desktop', now: 'Running Bash (npm test)', goals: [{ slug: 'ping-hud', done: 3, total: 7, step: 'Data layer' }] }))!
  expect(rowText(d[2]).slice(1)).toBe('Now      Running Bash (npm test)   Goal ping-hud [####......] phase 4 of 7 (43%): Data layer')
  expect(d[2].spans.find(x => x.k === 'goalfill')).toMatchObject({ tone: 'blue' })
  const g = rows(undefined, { goals: [{ slug: 'big', done: 10, total: 12, step: 'Ship' }] })
  expect(g[2]).toContain('Goal big 11/12  Ship')
  expect(rows(undefined, { goals: [{ slug: 'big', done: 12, total: 12, step: 'done' }] })[2]).toContain('12/12  done')
  // The row's own number wins over done+1; a BLOCKED row says so.
  expect(rows(undefined, { goals: [{ slug: 'v2', done: 4, total: 10, step: 'Share the strip', phase: '3', blocked: true }] })[2])
    .toContain('3/10 BLOCKED  Share the strip')
  // A long step is cut to 40 characters so the row stays on screen.
  const long = rows(undefined, { goals: [{ slug: 'v2', done: 9, total: 11, step: 'Evals, validate, release + Goals clean-up button (DEC-20)' }] })[2]
  expect(long.endsWith('10/11  Evals, validate, release + Goals clea...')).toBe(true)
})

test('band shows first bound goal with +N more', () => {
  const g = [{ slug: 'g1', done: 1, total: 4, step: 'B' }, { slug: 'g2', done: 0, total: 2, step: 'X' }]
  const r = rows(undefined, { goals: g })[2]
  expect(r).toContain('Goal g1 2/4  B')
  expect(r.endsWith('  +1 more')).toBe(true)
  expect(rows(undefined, { goals: [g[0]] })[2]).not.toContain('more')
  const both = rows(undefined, { tasks: TASKS, goals: g }) // Tasks fill Now: Goal and its +N ride the cwd row
  expect(both[1].endsWith('Goal g1 2/4  B  +1 more')).toBe(true)
})

test('nothing bound -> Goal: none; unknown goals -> no goal text', () => {
  expect(rows(undefined, { goals: [] })[2]).toBe('Now      idle  | Goal: none')
  expect(rows(undefined, {})[2]).toBe('Now      idle')
  expect(rows(undefined, { tasks: TASKS, goals: [] })[1].endsWith('  | Goal: none')).toBe(true)
})

test('all-done bound goal shows phase M of M (100%): done', () => {
  expect(rows(undefined, { goals: [{ slug: 'g1', done: 4, total: 4, step: 'done' }] })[2]).toContain('Goal g1 4/4  done')
})

test('garbage goals input never renders NaN or throws; unreadable (total 0) shows dim text', () => {
  const bad: any[] = [null, undefined, { slug: 'x' }, { slug: 'x', done: 'a', total: 3 }, { slug: 'x', done: NaN, total: 3 }]
  expect(rows(undefined, { goals: bad })[2]).toBe('Now      idle  | Goal: none')
  expect(rows(undefined, { goals: 'oops' as any })[2]).toBe('Now      idle')
  const mixed = rows(undefined, { goals: [null as any, { slug: 'g1', done: 1, total: 4, step: 'B' }] })[2]
  expect(mixed).toContain('Goal g1 2/4  B')
  expect(mixed).not.toContain('more')
  const u = layout(undefined, o({ goals: [{ slug: 'bad', done: 0, total: 0, step: 'unreadable' }, { slug: 'g2', done: 0, total: 2, step: 'X' }] }))!
  expect(rowText(u[2])).toContain('Goal bad unreadable  +1 more')
  expect(rowText(u[2])).not.toContain('NaN')
})

test('Tasks on the Now row; with a goal too, Goal moves to the cwd row end (Now row if cwd hidden)', () => {
  const t = rows(undefined, { now: 'Running Bash (npm test)', tasks: TASKS })
  expect(t[2]).toBe('Now      Running Bash (npm test)  | Tasks [###.......] 1/3: Implement')
  expect(t.join('\n')).not.toMatch(/goal/i)
  const goal = [{ slug: 'ping-hud', done: 3, total: 7, step: 'Data layer' }]
  const both = rows(undefined, { tasks: TASKS, goals: goal })
  expect(both[1].endsWith('  | Goal ping-hud 4/7  Data layer')).toBe(true)
  expect(both[2]).toBe('Now      idle  | Tasks [###.......] 1/3: Implement')
  const compact = rows(undefined, { tasks: TASKS, goals: goal, mode: 'compact' })
  expect(compact[0]).toBe('Now      idle  | Tasks [###.......] 1/3: Implement  | Goal ping-hud 4/7  Data layer')
  expect(rows(undefined, { tasks: [] })[2]).toBe('Now      idle')
})

test('no codex text anywhere on the band', () => {
  const st = { branch: 'b', defaultBranch: 'main', codex: { fiveH: { pct: 5, resetsAtMs: NOW + 1e6 } } }
  for (const bodyColumns of [140, 86]) expect(rows(state(5, 72), { bodyColumns, status: st }).join('\n')).not.toMatch(/codex/i)
})

test('ctx unmeasured: -- and no growth; Forecast never mentions ctx', () => {
  const s = { ...state(5, 72), ctxPct: undefined, ctxSpark: [] }
  const r = layout(s, o())!
  expect(rowText(r[0])).toContain('  | ctx   --  | 5h')
  expect(rowText(r[3])).not.toContain('ctx')
})

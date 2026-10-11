import { test, expect } from 'claude-code/testing'
import { parseCodex, codexDays, cacheHit, cacheSum, memText, snapshot, collect } from './hud-data'
import { gitInfo, readCodex } from './register'
import { layout, rowText } from './hud-render'

const NOW = Date.parse('2026-10-08T12:00:00Z')
const sec = (ms: number) => Math.round(ms / 1000)
const rl = (p5: number, r5: number, p7: number, r7: number) => JSON.stringify({ type: 'event_msg', payload: { type: 'token_count', rate_limits: {
  primary: { used_percent: p5, window_minutes: 300, resets_at: sec(r5) },
  secondary: { used_percent: p7, window_minutes: 10080, resets_at: sec(r7) },
} } })
const LOG = [
  '{"type":"session_meta","payload":{}}',
  rl(10, NOW + 3600e3, 2, NOW + 5 * 864e5),
  '{"type":"event_msg","payload":{"type":"token_count","rate_limits":null}}',
  rl(12, NOW + 3600e3, 3, NOW + 5 * 864e5),
  '{"type":"response_item","payload":{}}',
].join('\n')

// Fake $ for process.run: argv joined -> result; anything else rejects like a missing git.
function proc(map: Record<string, { exitCode: number; stdout: string }>) {
  return { process: { run: async (argv: string[]) => {
    const r = map[argv.join(' ')]
    if (!r) throw new Error('cannot start')
    return { ...r, stderr: '' }
  } } }
}

test('gitInfo: branch and default branch from git', async () => {
  const $ = proc({
    'git rev-parse --abbrev-ref HEAD': { exitCode: 0, stdout: 'topic/mod\n' },
    'git symbolic-ref refs/remotes/origin/HEAD': { exitCode: 0, stdout: 'refs/remotes/origin/main\n' },
  })
  expect(await gitInfo($, 'R')).toEqual({ branch: 'topic/mod', defaultBranch: 'main' })
})

test('gitInfo: no repo, detached HEAD or missing git -> "-", no throw', async () => {
  const noRepo = proc({ 'git rev-parse --abbrev-ref HEAD': { exitCode: 128, stdout: '' }, 'git symbolic-ref refs/remotes/origin/HEAD': { exitCode: 128, stdout: '' } })
  expect(await gitInfo(noRepo, 'R')).toEqual({ branch: '-', defaultBranch: '-' })
  const detached = proc({ 'git rev-parse --abbrev-ref HEAD': { exitCode: 0, stdout: 'HEAD\n' } })
  expect(await gitInfo(detached, 'R')).toEqual({ branch: '-', defaultBranch: '-' })
  expect(await gitInfo(proc({}), 'R')).toEqual({ branch: '-', defaultBranch: '-' })
})

test('parseCodex: last rate_limits line wins; primary -> 5h, secondary -> 7d', () => {
  expect(parseCodex(LOG, NOW)).toEqual({
    fiveH: { pct: 12, resetsAtMs: sec(NOW + 3600e3) * 1000 },
    sevenD: { pct: 3, resetsAtMs: sec(NOW + 5 * 864e5) * 1000 },
  })
})

test('parseCodex: past resets_at -> pct 0; no rate_limits -> null', () => {
  const c = parseCodex(rl(40, NOW - 60000, 9, NOW + 864e5), NOW)!
  expect(c.fiveH!.pct).toBe(0)
  expect(c.sevenD!.pct).toBe(9)
  expect(parseCodex('{"type":"session_meta"}\nnot json', NOW)).toBe(null)
})

test('codexDays: today then yesterday, local YYYY/MM/DD', () => {
  const d = codexDays(NOW)
  expect(d).toHaveLength(2)
  expect(d[0]).toMatch(/^2026\/10\/0[78]$/)
  expect(d[1] < d[0]).toBe(true)
})

test('readCodex: newest rollout in today folder, else yesterday; no sessions dir -> null', async () => {
  const [today, yday] = codexDays(NOW)
  const root = 'H/.codex/sessions'
  const files: Record<string, { mtimeMs: number; text: string }> = {
    [`${root}/${today}/rollout-a.jsonl`]: { mtimeMs: 1, text: rl(50, NOW + 3600e3, 5, NOW + 864e5) },
    [`${root}/${today}/rollout-b.jsonl`]: { mtimeMs: 9, text: LOG },
    [`${root}/${today}/notes.txt`]: { mtimeMs: 99, text: '' },
    [`${root}/${yday}/rollout-y.jsonl`]: { mtimeMs: 1, text: rl(77, NOW + 3600e3, 7, NOW + 864e5) },
  }
  const fake = (keep: (p: string) => boolean) => ({
    env: { get: async (n: string) => (n === 'HOME' ? 'H' : undefined) },
    fs: {
      exists: async (p: string) => Object.keys(files).some(f => keep(f) && f.startsWith(p + '/')),
      read: async (p: string) => files[p].text,
      list: async (d: string) => Object.keys(files).filter(f => keep(f) && f.startsWith(d + '/')).map(f => ({ name: f.slice(d.length + 1), kind: 'file', mtimeMs: files[f].mtimeMs })),
    },
  })
  expect((await readCodex(fake(() => true), NOW))!.fiveH!.pct).toBe(12)
  expect((await readCodex(fake(f => !f.includes(`/${today}/`)), NOW))!.fiveH!.pct).toBe(77)
  expect(await readCodex(fake(() => false), NOW)).toBe(null)
})

test('cacheHit = cache_read / (cache_read + input); memText in GB', () => {
  expect(cacheHit({ input_tokens: 20, cache_read_input_tokens: 980, output_tokens: 5, cache_creation_input_tokens: 0 })).toBe(98)
  expect(cacheHit({ input_tokens: 0, cache_read_input_tokens: 0 })).toBe(undefined)
  expect(cacheHit(null)).toBe(undefined)
  const a = cacheSum(undefined, { input_tokens: 0, cache_read_input_tokens: 0, cache_creation_input_tokens: 1000 })
  expect(a.cacheHitPct).toBe(0)
  const b = cacheSum(a, { input_tokens: 10, cache_read_input_tokens: 2990, cache_creation_input_tokens: 0 })
  expect(b.cacheHitPct).toBe(75)
  expect(cacheSum(b, null)).toEqual(b)
  expect(memText(63 * 1048576, 24 * 1048576)).toBe('39/63G')
  expect(memText(0, 0)).toBe(undefined)
})

test('snapshot carries codex windows', () => {
  const s = collect(undefined, { context: { percent: 1, tokens: 1 }, rateLimits: [] }, 'x', NOW)
  const j = snapshot('sid', s, NOW, parseCodex(LOG, NOW))
  expect(j.codex).toEqual([
    { provider: 'codex', window: '5h', percentUsed: 12, resetsAt: new Date(sec(NOW + 3600e3) * 1000).toISOString(), source: 'codex-log', ageSec: null },
    { provider: 'codex', window: '7d', percentUsed: 3, resetsAt: new Date(sec(NOW + 5 * 864e5) * 1000).toISOString(), source: 'codex-log', ageSec: null },
  ])
})

test('render: cwd status fields wide and narrow; Codex never on the band (decision 27)', () => {
  const status = { branch: 'topic/mod', defaultBranch: 'main', mem: '39/63G', codex: parseCodex(LOG, NOW) }
  const step = { thinking: 'medium', cacheHitPct: 98 }
  const base = { surface: 'terminal', nowMs: NOW, cwd: 'D:/work/demo-repo', status, step }
  const w = layout(undefined, { ...base, bodyColumns: 140 })!.map(r => rowText(r).slice(1))
  expect(w.join('\n')).not.toContain('codex')
  expect(w[0]).toContain('-- think medium  | ctx') // thinking sits beside the model name
  expect(w[1]).toBe('Session  branch topic/mod from main  dir D:/.../demo-repo  cache 98%  mem 39/63G')
  const n = layout(undefined, { ...base, bodyColumns: 90 })!.map(r => rowText(r).slice(1))
  expect(n[1]).toBe('Session  branch topic/mod from main  cache 98%')
  const none = layout(undefined, { ...base, status: { branch: '-', defaultBranch: '-' }, step: undefined, bodyColumns: 140 })!.map(r => rowText(r).slice(1))
  const t = layout(undefined, { ...base, bodyColumns: 70 })!.map(r => rowText(r).slice(1))
  expect(t[0]).toContain('think medium') // kept on a narrow band too
  expect(none[1]).toBe('Session  branch -  dir D:/.../demo-repo  cache  --')
})

import { test, expect } from 'claude-code/testing'
import { classify, pathOk, pathKey, slugOk, slugOf, clean, goalSlug, matchSlug, scanList, parseGitLog, beacons, pendingTick, mergeToasts, paneLabel, paneWord } from './hud-goals'

const DAY = 864e5
const NOW = Date.parse('2026-10-08T12:00:00Z')
// Column words copied from a real audit tracker's Phase Status table.
const row = (n: number, title: string, status: string) => `| ${n} | ASK:x | ${title} | ${status} | -- | -- |`
const tracker = (rows: string[], slug = 'g') => [
  '---', `goal_slug: ${slug}`, '---', '# t', '', '## Phase Status', '',
  '| Phase | Source | Title | Status | Commit | Subagent |', '|---|---|---|---|---|---|', ...rows, '', '## Cost Log',
].join('\n')
const done2 = tracker([row(0, 'A', 'OK Done'), row(1, 'B', 'OK Done')])
const half = tracker([row(0, 'A', 'OK Done'), row(1, 'B', 'Pending')])

test('classify: unreadable, finalized, all-done, idle 14d+, active', () => {
  expect(classify('no table', NOW, undefined, NOW)).toBe('unreadable')
  expect(classify(tracker([]), NOW, undefined, NOW)).toBe('unreadable')
  expect(classify(done2, NOW - DAY, NOW, NOW)).toBe('finalized')
  expect(classify(done2, NOW - DAY, undefined, NOW)).toBe('all-done')
  expect(classify(half, NOW - 14 * DAY, undefined, NOW)).toBe('idle')
  expect(classify(half, NOW - 13 * DAY, undefined, NOW)).toBe('active')
})

test('classify: re-opened goal with an old accept-cache is active, not finalized', () => {
  const reopened = tracker([row(0, 'A', 'OK Done'), row(1, 'B', 'OK Done'), row(2, 'C', 'Pending')])
  expect(classify(reopened, NOW - DAY, NOW - 2 * DAY, NOW)).toBe('active')
  expect(classify(done2, NOW - DAY, NOW - 2 * DAY, NOW)).toBe('all-done') // cache older than last change
})

test('pathOk: relative tracker paths only; no .., archived, absolute or wrong basename', () => {
  const B = String.fromCharCode(92)
  expect(pathOk('D:/r', 'docs/mod/ping-hud-v2-audit-tracker.md')).toBe(true)
  expect(pathOk('D:/r', ['docs', 'mod', 'x-audit-tracker.md'].join(B))).toBe(true)
  expect(pathOk('D:/r', 'D:/r/docs/mod/x-audit-tracker.md')).toBe(false)
  expect(pathOk('D:/r', '/docs/x-audit-tracker.md')).toBe(false)
  expect(pathOk('D:/r', '../docs/x-audit-tracker.md')).toBe(false)
  expect(pathOk('D:/r', 'docs/a/../x-audit-tracker.md')).toBe(false)
  expect(pathOk('D:/r', 'docs/archived/x-audit-tracker.md')).toBe(false)
  expect(pathOk('D:/r', 'docs/Archive/x-audit-tracker.md')).toBe(false)
  expect(pathOk('D:/r', 'docs/mod/plan.md')).toBe(false)
  expect(pathOk('', 'docs/mod/x-audit-tracker.md')).toBe(false)
})

test('pathKey folds case on win32 only', () => {
  expect(pathKey('Docs/Mod/X-audit-tracker.md', true)).toBe(pathKey('docs/mod/x-audit-tracker.md', true))
  expect(pathKey('Docs/Mod/X-audit-tracker.md', false)).not.toBe(pathKey('docs/mod/x-audit-tracker.md', false))
})

test('slugOf: first non-flag token, validated', () => {
  expect(slugOf('ping-hud-v2')).toBe('ping-hud-v2')
  expect(slugOf('--resume ping-hud extra')).toBe('ping-hud')
  expect(slugOf('  --plan  ')).toBe(null)
  expect(slugOf('Bad')).toBe(null)
  expect(slugOf('a;rm')).toBe(null)
  expect(slugOk('-x')).toBe(false)
  expect(slugOk('a'.repeat(64))).toBe(true)
  expect(slugOk('a'.repeat(65))).toBe(false)
})

test('clean strips control characters and ESC sequences and cuts to 60', () => {
  expect(clean('\x1b[31mred\x1b[0m\tx\x07\x7f')).toBe('redx')
  expect(clean('\x1b]0;title\x07ok')).toBe('ok')
  expect(clean('y'.repeat(100))).toHaveLength(60)
})

test('goalSlug reads CRLF frontmatter with trailing spaces', () => {
  expect(goalSlug('---\r\ngoal_slug: ping-hud   \r\nbranch: x\r\n---\r\n# t')).toBe('ping-hud')
  expect(goalSlug('# no frontmatter\ngoal_slug: nope')).toBe(null)
})

test('matchSlug: duplicate slug returns every tracker; none returns empty', () => {
  const es = [{ path: 'docs/a/a-audit-tracker.md', text: tracker([], 'dup') }, { path: 'docs/b/b-audit-tracker.md', text: tracker([], 'dup') }, { path: 'docs/c/c-audit-tracker.md', text: tracker([], 'other') }]
  expect(matchSlug(es, 'dup')).toEqual(['docs/a/a-audit-tracker.md', 'docs/b/b-audit-tracker.md'])
  expect(matchSlug(es, 'missing')).toEqual([])
})

test('scanList: bound rows first whatever class, then active/idle/unreadable, finalized and done hidden', () => {
  const e = (path: string, text: string, lastChange: number, cacheMs?: number) => ({ path, text, lastChange, cacheMs })
  const es = [
    e('docs/f/f-audit-tracker.md', done2, NOW - DAY, NOW),          // finalized
    e('docs/d/d-audit-tracker.md', done2, NOW - DAY),               // all-done
    e('docs/i/i-audit-tracker.md', half, NOW - 20 * DAY),           // idle
    e('docs/a/a-audit-tracker.md', half, NOW - DAY),                // active
    e('docs/u/u-audit-tracker.md', 'junk', NOW),                    // unreadable
  ]
  const r = scanList(es, ['docs/F/f-audit-tracker.md'], NOW, true)
  expect(r.rows.map(x => [x.slug, x.cls, x.bound])).toEqual([
    ['f', 'finalized', true], ['u', 'unreadable', false], ['a', 'active', false], ['i', 'idle', false],
  ])
  expect(r.hidden.map(x => x.slug)).toEqual(['d'])
})

test('parseGitLog: newest commit time per path, in ms', () => {
  const out = ['1700000200', '', 'docs/a/a-audit-tracker.md', '1700000100', '', 'docs/a/a-audit-tracker.md', 'docs/b/b-audit-tracker.md'].join('\n')
  expect(parseGitLog(out)).toEqual({ 'docs/a/a-audit-tracker.md': 1700000200000, 'docs/b/b-audit-tracker.md': 1700000100000 })
  expect(parseGitLog('')).toEqual({})
})

test('beacons: every Goal beacon path in a text, also mid-line, backticks dropped', () => {
  const t = ['# Progress', 'Goal beacon: docs/a/x-audit-tracker.md', 'see Goal beacon: `docs/b/y-audit-tracker.md` and Goal beacon: docs/c/z-audit-tracker.md', 'no beacon here'].join('\n')
  expect(beacons(t)).toEqual(['docs/a/x-audit-tracker.md', 'docs/b/y-audit-tracker.md', 'docs/c/z-audit-tracker.md'])
  expect(beacons('nothing')).toEqual([])
})

test('pendingTick: counts a turn, drops at 3, removes found slugs without a drop', () => {
  let p = [{ slug: 'a', turns: 0 }, { slug: 'b', turns: 0 }]
  let r = pendingTick(p, ['b'])
  expect(r).toEqual({ keep: [{ slug: 'a', turns: 1 }], dropped: [] })
  r = pendingTick(r.keep, [])
  expect(r.keep).toEqual([{ slug: 'a', turns: 2 }])
  r = pendingTick(r.keep, [])
  expect(r).toEqual({ keep: [], dropped: ['a'] })
})

test('mergeToasts keeps a single message as is; 2+ become one count message', () => {
  expect(mergeToasts(['goal a cleared'])).toEqual(['goal a cleared'])
  expect(mergeToasts([])).toEqual([])
  expect(mergeToasts(['x', 'y'])).toEqual(['2 goals cleared: tracker moved, removed or finalized'])
  expect(mergeToasts(['x', 'y', 'z'])).toEqual(['3 goals cleared: tracker moved, removed or finalized'])
})

test('paneLabel and paneWord: [x]/[ ] mark, done/total percent, UTC date, cleaned slug, dim words', () => {
  const r = { path: 'docs/a/x-audit-tracker.md', slug: '\x1b[31mg1\x1b[0m', cls: 'idle' as const, goal: { slug: '', done: 1, total: 4, step: 'B' }, lastChange: Date.parse('2026-09-18T23:59:00Z'), bound: true }
  expect(paneLabel(r)).toBe('[x] g1 1/4 25% 2026-09-18')
  expect(paneWord(r)).toBe('idle 14d+')
  const u = { ...r, goal: null, cls: 'unreadable' as const, bound: false }
  expect(paneLabel(u)).toBe('[ ] g1 -- 2026-09-18')
  expect(paneWord(u)).toBe('unreadable')
  expect(paneWord({ ...r, cls: 'active' })).toBe('')
})

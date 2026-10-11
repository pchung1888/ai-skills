// ping-hud goal rules: which audit trackers a session tracks and what state each is in.
// Pure: no $ here; register.tsx does every read, git call and store write.
import { parseGoal, type Goal } from './hud-data'

export type Tracked = { root: string; path: string }
export type GoalClass = 'unreadable' | 'finalized' | 'all-done' | 'idle' | 'active'
export type Entry = { path: string; text: string; lastChange: number; cacheMs?: number }
export type PaneRow = { path: string; slug: string; cls: GoalClass; goal: Goal | null; lastChange: number; bound: boolean }

const IDLE_MS = 14 * 864e5

// First match wins: unreadable, finalized, all-done, idle 14d+, active.
// cacheMs = mtime of '<tracker>.accept-cache'; it counts only when newer than the tracker's last change.
export function classify(text: string, lastChange: number, cacheMs: number | undefined, nowMs: number): GoalClass {
  const g = parseGoal(text, '')
  if (!g) return 'unreadable'
  if (g.done === g.total) return cacheMs !== undefined && cacheMs > lastChange ? 'finalized' : 'all-done'
  return nowMs - lastChange >= IDLE_MS ? 'idle' : 'active'
}

// Backslashes become slashes and a leading './' is dropped, so one tracker has one spelling.
export function normPath(p: string): string { return p.replace(/\\/g, '/').replace(/^(\.\/)+/, '') }

// Comparison key: case-insensitive on win32 (NTFS), exact elsewhere.
export function pathKey(p: string, win32: boolean): string { const n = normPath(p); return win32 ? n.toLowerCase() : n }

// Accepts only a relative '<...>/<name>-audit-tracker.md' under root with no '..' or archived/archive segment.
export function pathOk(root: string, path: string): boolean {
  if (!root || !path) return false
  const p = normPath(path)
  if (/^([A-Za-z]:|\/)/.test(p)) return false
  const segs = p.split('/')
  if (segs.some(s => s === '' || s === '..' || /^archived?$/i.test(s))) return false
  return segs[segs.length - 1].endsWith('-audit-tracker.md')
}

const SLUG = /^[a-z0-9][a-z0-9-]{0,63}$/
export function slugOk(s: string): boolean { return SLUG.test(s) }

// Goal commands put the slug first, after any '--flag'; an invalid slug is ignored, never echoed.
export function slugOf(args: string): string | null {
  const t = String(args || '').trim().split(/\s+/).find(x => x && !x.startsWith('--'))
  return t && slugOk(t) ? t : null
}

// File text shown on the band or in a toast: no ESC sequences, no control characters, 60 chars max.
export function clean(text: string): string {
  return String(text)
    .replace(/\x1b(?:\[[0-9;?]*[ -\/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|.)/g, '')
    .replace(/[\x00-\x1f\x7f]/g, '')
    .slice(0, 60)
}

// 'goal_slug: <slug>' from the leading '---' frontmatter block; none -> null.
export function goalSlug(text: string): string | null {
  const fm = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text)
  const m = fm && /^goal_slug:[ \t]*(\S+)[ \t]*\r?$/m.exec(fm[1])
  return m ? m[1] : null
}

export function matchSlug(entries: { path: string; text: string }[], slug: string): string[] {
  return entries.filter(e => goalSlug(e.text) === slug).map(e => e.path)
}

// Goals pane order: bound trackers first (bind order, any class), then active / idle / unreadable by last change;
// finalized and all-done go to 'hidden' unless bound. Row paths are compared as given (pathKey).
export function orderRows(all: PaneRow[], bound: string[], win32: boolean): { rows: PaneRow[]; hidden: PaneRow[] } {
  const keys = bound.map(b => pathKey(b, win32))
  const marked = all.map(x => ({ ...x, bound: keys.includes(pathKey(x.path, win32)) }))
  const rank: Record<GoalClass, number> = { unreadable: 0, active: 1, idle: 2, 'all-done': 3, finalized: 3 }
  const mine = marked.filter(x => x.bound).sort((a, b) => keys.indexOf(pathKey(a.path, win32)) - keys.indexOf(pathKey(b.path, win32)))
  const rest = marked.filter(x => !x.bound).sort((a, b) => rank[a.cls] - rank[b.cls] || b.lastChange - a.lastChange)
  return { rows: [...mine, ...rest.filter(x => rank[x.cls] < 3)], hidden: rest.filter(x => rank[x.cls] === 3) }
}

// Scanned trackers -> pane rows. Slug = file name without '-audit-tracker.md'.
export function scanList(entries: Entry[], bound: string[], nowMs: number, win32: boolean): { rows: PaneRow[]; hidden: PaneRow[] } {
  return orderRows(entries.map(x => ({
    path: normPath(x.path), slug: slugOfPath(x.path), cls: classify(x.text, x.lastChange, x.cacheMs, nowMs),
    goal: parseGoal(x.text, ''), lastChange: x.lastChange, bound: false,
  })), bound, win32)
}

export function slugOfPath(p: string): string { return normPath(p).split('/').pop()!.replace(/-audit-tracker\.md$/, '') }

// Goals pane row text: '[x]' bound or '[ ]', slug, done/total, percent, last change date (UTC).
export function paneLabel(r: PaneRow): string {
  const g = r.goal, p = g ? `${g.done}/${g.total} ${Math.round((100 * g.done) / g.total)}%` : '--'
  return `${r.bound ? '[x]' : '[ ]'} ${clean(r.slug)} ${p} ${new Date(r.lastChange).toISOString().slice(0, 10)}`
}

// Dim word after a pane row: only idle and unreadable trackers carry one.
export function paneWord(r: PaneRow): string { return r.cls === 'idle' ? 'idle 14d+' : r.cls === 'unreadable' ? 'unreadable' : '' }

// 'git log --format=%ct --name-only' output -> newest commit ms per path (git lists newest first).
export function parseGitLog(stdout: string): Record<string, number> {
  const out: Record<string, number> = {}
  let t = 0
  for (const line of String(stdout).split(/\r?\n/)) {
    const s = line.trim()
    if (/^\d+$/.test(s)) t = Number(s) * 1000
    else if (s && !(s in out)) out[s] = t
  }
  return out
}

// Every 'Goal beacon: <path>' in a text, also mid-line; wrapping backticks are dropped.
export function beacons(text: string): string[] {
  return [...String(text).matchAll(/Goal beacon:[ \t]*`?([^\s`]+)/g)].map(m => m[1])
}

export type Pending = { slug: string; turns: number }
const PENDING_TURNS = 3

// One turn passes: slugs now found leave quietly, the rest count a turn and drop at 3.
export function pendingTick(p: Pending[], found: string[]): { keep: Pending[]; dropped: string[] } {
  const rest = p.filter(x => !found.includes(x.slug)).map(x => ({ slug: x.slug, turns: x.turns + 1 }))
  return { keep: rest.filter(x => x.turns < PENDING_TURNS), dropped: rest.filter(x => x.turns >= PENDING_TURNS).map(x => x.slug) }
}

// Two or more unbind messages from one check become a single count message.
export function mergeToasts(msgs: string[]): string[] {
  return msgs.length < 2 ? msgs : [`${msgs.length} goals cleared: tracker moved, removed or finalized`]
}

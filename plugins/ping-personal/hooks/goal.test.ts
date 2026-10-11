import { test, expect } from 'claude-code/testing'
import { parseGoal, goalBar, activity, foldTasks, taskBar } from './hud-data'
import { readBound } from './register'

// Column words copied from docs/mod/ping-hud-audit-tracker.md.
const row = (n: number, title: string, status: string) => `| ${n} | ASK:x | ${title} | ${status} | -- | -- |`
const tracker = (rows: string[]) => [
  '# t', '', '## Phase Status', '', 'Source column legal values:', '',
  '| Phase | Source | Title | Status | Commit | Subagent |', '|---|---|---|---|---|---|', ...rows, '', '## Cost Log',
].join('\n')
const seven = tracker([
  row(0, 'Build-start checks', 'OK Done'), row(1, 'Mod skeleton', 'OK Done'), row(2, 'Pure rule functions (TDD)', 'OK Done'),
  row(3, 'Data layer + snapshot', 'Pending'), row(4, 'Terminal render', 'Pending'), row(5, 'Desktop render', 'Pending'), row(6, 'Now row', 'Pending'),
])

test('7-row table, 3 done -> 3/7, step is first not-done title, bar 4 of 10', () => {
  expect(parseGoal(seven, 'ping-hud')).toEqual({ slug: 'ping-hud', done: 3, total: 7, step: 'Data layer + snapshot', phase: '3', blocked: false })
  expect(goalBar(3, 7, '#', '-')).toBe('[####------]')
})

test('0-based, out of order: phase is the first unfinished row own number, BLOCKED kept', () => {
  const t = tracker([row(0, 'A', 'OK Done'), row(1, 'B', 'OK Done'), row(2, 'C', 'BLOCKED Blocked'), row(3, 'D', 'OK Done'), row(4, 'E', 'Pending')])
  expect(parseGoal(t, 'g')).toEqual({ slug: 'g', done: 3, total: 5, step: 'C', phase: '2', blocked: true })
})

test('malformed table -> null, no throw', () => {
  expect(parseGoal('no table here', 's')).toBe(null)
  expect(parseGoal('## Phase Status\n| a | b |\n|---|---|\n| 1 | 2 |', 's')).toBe(null)
  expect(parseGoal(tracker([]), 's')).toBe(null)
})

test('readBound: bound order wins (not newest mtime); missing files are skipped, unreadable ones are marked; text is cleaned', async () => {
  const files: Record<string, string> = {
    'R/docs/old/old-audit-tracker.md': tracker([row(0, 'Old', 'Pending')]),
    'R/docs/mod/ping-hud-audit-tracker.md': seven,
    'R/docs/x/bad-audit-tracker.md': 'no table',
    'R/docs/y/red-audit-tracker.md': tracker([row(0, '[31mRed[0m title', 'Pending')]),
  }
  const fake = { fs: { read: async (p: string) => { if (!(p in files)) throw new Error('ENOENT'); return files[p] } } }
  const at = (path: string) => ({ root: 'R', path })
  expect(await readBound(fake, [at('docs/mod/ping-hud-audit-tracker.md'), at('docs/old/old-audit-tracker.md')])).toEqual([
    { slug: 'ping-hud', done: 3, total: 7, step: 'Data layer + snapshot', phase: '3', blocked: false }, { slug: 'old', done: 0, total: 1, step: 'Old', phase: '0', blocked: false }])
  expect(await readBound(fake, [at('docs/x/bad-audit-tracker.md'), at('docs/gone/z-audit-tracker.md'), at('docs/y/red-audit-tracker.md')]))
    .toEqual([{ slug: 'bad', done: 0, total: 0, step: 'unreadable' }, { slug: 'red', done: 0, total: 1, step: 'Red title', phase: '0', blocked: false }])
  expect(await readBound(fake, [])).toEqual([])
})

test('activity: tool name + short arg, workflow agent, idle', () => {
  expect(activity({ tool: 'Bash', command: 'npm test' })).toBe('Running Bash (npm test)')
  expect(activity({ tool: 'Read', file_path: 'D:/a/b/hud-data.ts' })).toBe('Running Read (hud-data.ts)')
  expect(activity(undefined)).toBe('idle')
  expect(activity({ tool: 'Agent', description: 'review', workflow: { runId: 'wf_1', agentIndex: 4 } })).toBe('Workflow agent 4 (review)')
  expect(activity({ tool: 'Bash', command: 'x'.repeat(80) }).length).toBeLessThan(50)
})

test('foldTasks: TodoWrite replaces, TaskCreate/Update/List fold, other tools leave it alone', () => {
  const todo = foldTasks(undefined, { tool: 'TodoWrite', todos: [
    { content: 'Write tests', status: 'completed', activeForm: 'Writing tests' },
    { content: 'Implement', status: 'in_progress', activeForm: 'Implementing' },
    { content: 'Commit', status: 'pending', activeForm: 'Committing' }] }, {})
  expect(taskBar(todo)).toEqual({ done: 1, total: 3, current: 'Implement' })
  expect(foldTasks(todo, { tool: 'Bash', command: 'ls' }, {})).toBeUndefined()
  let t = foldTasks(undefined, { tool: 'TaskCreate', subject: 'A', description: 'a' }, { result: { task: { id: '1', subject: 'A' } } })
  t = foldTasks(t, { tool: 'TaskCreate', subject: 'B', description: 'b' }, { result: { task: { id: '2', subject: 'B' } } })
  expect(taskBar(t)).toEqual({ done: 0, total: 2, current: 'A' })
  t = foldTasks(t, { tool: 'TaskUpdate', taskId: '1', status: 'completed' }, {})
  expect(taskBar(t)).toEqual({ done: 1, total: 2, current: 'B' })
  t = foldTasks(t, { tool: 'TaskUpdate', taskId: '2', status: 'deleted' }, {})
  expect(taskBar(t)).toEqual({ done: 1, total: 1, current: 'all done' })
  expect(foldTasks(t, { tool: 'TaskUpdate', taskId: '9', status: 'completed' }, {})).toBeUndefined()
  const l = foldTasks(undefined, { tool: 'TaskList' }, { result: { tasks: [{ id: '5', subject: 'X', status: 'in_progress', blockedBy: [] }] } })
  expect(taskBar(l)).toEqual({ done: 0, total: 1, current: 'X' })
  expect(taskBar([])).toBe(null)
  expect(taskBar(undefined)).toBe(null)
})

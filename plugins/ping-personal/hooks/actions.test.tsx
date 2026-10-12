import { test, expect, mock } from 'claude-code/testing'
import { ACTIONS, HTSW_ACTIONS, resolveCmd, stamp, workDir, planSlug, GREEN, BLUE, YELLOW, ORANGE, PURPLE, CYAN, GRAY, PINK } from './hud-actions'
import { layout } from './hud-render'

const NOW = Date.parse('2026-10-09T16:00:00Z')
const props = { hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 95, scroll: { offset: 0, bodyRows: 12 }, view: {} }
const ALL = ['ping-personal:personal-handoff', 'ping-personal:personal-htsw', 'compact']

// Buttons world: the listed commands are `names`; runs, toasts and pane opens are recorded.
function bw(on: any, names: string[], store: Record<string, unknown> = {}, sid = 'sid-a') {
  mock.store(on, { [`hudCmds:${sid}`]: names, ...store }) // as session.start stores it
  mock.clock(on, { now: NOW })
  on('session.cwd', () => ({ value: 'D:/x' }))
  on('session.id', () => ({ value: sid }))
  const w = { runs: [] as { command: string; args: string }[], toasts: [] as string[] }
  on('command.list', () => ({ value: names.map(name => ({ name, description: '' })) }))
  on('command.run', (_$: any, e: any) => { w.runs.push({ command: e.command, args: e.args }); return { text: '' } })
  on('ui.toast', (_$: any, e: any) => { w.toasts.push(e.text); return { value: undefined } })
  on('ui.render', { component: 'AbovePrompt' }, ($: any, e: any) => { const { Box } = $.ui.resolve(e); return <Box key="engine" /> }) // the engine's empty band
  return w
}

test('ACTIONS: commands and args per button', () => {
  const by = Object.fromEntries(ACTIONS.map(a => [a.key, a]))
  expect(by.handoff.cmd).toBe('personal-handoff')
  const c = (bound: string[]) => ({ bound, nowMs: NOW, root: 'R' })
  expect(by.handoff.args(c(['docs/a/g1-audit-tracker.md']))).toBe('--unattended docs/a/g1-audit-tracker.md')
  expect(ACTIONS.map(a => a.label)).toEqual(['Handoff', 'Plan', 'Next', 'Agents', 'Goals']) // the Action row (Hide is added when drawn)
  expect(by.next.cmd).toBe('personal-next') // DEC-10: press only, the skill asks with clickable choices
  expect(by.next.args(c([]))).toBe('now')
  expect(by.plan.color).toBe(PURPLE)
  expect(by.goals.cmd).toBe(null)
  expect(by.agents.cmd).toBe(null) // opens the Agents pane, runs no command
  expect(by.handoff.color).toBe(GREEN)
})

test('HTSW_ACTIONS: the pane button, the four levels and Motion run no command; each names its mode (DEC-7, DEC-8)', () => {
  expect(HTSW_ACTIONS.map(a => a.label)).toEqual(['Pane', 'Simple', 'Explain', 'Kid', 'Deep HTML', 'Motion'])
  expect(HTSW_ACTIONS.map(a => a.mode)).toEqual(['pane', 'simple', 'explain', 'kid', 'deep', 'motion'])
  expect(HTSW_ACTIONS.every(a => a.cmd === null)).toBe(true)
  expect(HTSW_ACTIONS.map(a => a.color)).toEqual([CYAN, YELLOW, BLUE, ORANGE, PURPLE, PINK])
})

test('resolveCmd: exact name, else plugin-prefixed, else undefined', () => {
  expect(resolveCmd(['personal-htsw'], 'personal-htsw')).toBe('personal-htsw')
  expect(resolveCmd(['ping-personal:personal-htsw'], 'personal-htsw')).toBe('ping-personal:personal-htsw')
  expect(resolveCmd(['ping-personal:personal-htsw-x'], 'personal-htsw')).toBe(undefined)
  expect(resolveCmd(['evil:personal-htsw'], 'personal-htsw')).toBe(undefined) // another plugin cannot take a button
  expect(resolveCmd(['evil:personal-htsw', 'personal-htsw', 'ping-personal:personal-htsw'], 'personal-htsw')).toBe('ping-personal:personal-htsw')
})

test('Handoff args drop a bound path that could add arguments', () => {
  const h = ACTIONS.find(a => a.key === 'handoff')!
  expect(h.args({ bound: ['docs/a/g1-audit-tracker.md', 'docs/x y/--force-audit-tracker.md', '--commit', 'docs/b/g2-audit-tracker.md'], nowMs: NOW, root: 'R' }))
    .toBe('--unattended docs/a/g1-audit-tracker.md docs/b/g2-audit-tracker.md')
})

test('Deep HTML pages: ET stamp, next to the bound goal, else docs/explain', () => {
  expect(stamp(Date.parse('2026-10-08T18:41:00Z'))).toBe('2026-10-08-1441') // EDT
  expect(stamp(Date.parse('2026-12-08T04:05:00Z'))).toBe('2026-12-07-2305') // EST, day before in New York
  expect(workDir([])).toBe('docs/explain')
  expect(workDir(['docs/mod/ping-hud-v2-audit-tracker.md'])).toBe('docs/mod') // the page goes next to the goal's tracker
  expect(workDir(['docs/x y/g-audit-tracker.md'])).toBe('docs/explain') // not a plain path
})

test('Plan uses the first bound slug, validated, and links the arc skin', () => {
  const p = ACTIONS.find(a => a.key === 'plan')!
  expect(p.cmd).toBe('html-plan')
  const a = p.args({ bound: ['docs/mod/ping-hud-v2-audit-tracker.md', 'docs/b/g2-audit-tracker.md'], nowMs: NOW, root: 'C:/p/ping-personal' })
  expect(a.startsWith('ping-hud-v2 ')).toBe(true)
  expect(a).toContain('docs/mod/ping-hud-v2-audit-tracker.md')
  expect(a).toContain('C:/p/ping-personal/assets/html-plan-arc.css')
  expect(a).not.toContain('g2')
  expect(planSlug(['docs/x y/a b-audit-tracker.md'])).toBe(undefined) // not a plain path: no Plan
  expect(planSlug(['docs/a/-x-audit-tracker.md'])).toBe(undefined)
  expect(planSlug([])).toBe(undefined)
})

test('resolveCmd: another plugin only when the action names it', () => {
  expect(resolveCmd(['html-plan:html-plan'], 'html-plan', 'html-plan')).toBe('html-plan:html-plan')
  expect(resolveCmd(['html-plan:html-plan'], 'html-plan')).toBe(undefined)
})

const PLAN = ['ping-personal:personal-htsw', 'html-plan:html-plan']
test('Plan hidden without a bound goal', async ($, on) => {
  bw(on, PLAN)
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props })
  expect(await ui.find({ key: 'btnplan' })).toBeUndefined()
  expect(await ui.find({ key: 'btndeep' })).toBeDefined()
  await ui.unmount()
})

test('Plan hidden when html-plan is not installed', async ($, on) => {
  bw(on, ['ping-personal:personal-htsw'], { 'hudGoals:sid-a': [{ root: 'D:/x', path: 'docs/a/g1-audit-tracker.md' }] })
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props })
  expect(await ui.find({ key: 'btnplan' })).toBeUndefined()
  await ui.unmount()
})

test('Plan press runs html-plan with the first bound slug', async ($, on) => {
  const w = bw(on, PLAN, { 'hudGoals:sid-a': [{ root: 'D:/x', path: 'docs/a/g1-audit-tracker.md' }] })
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'desktop', component: 'AbovePrompt', props })
  await ui.press({ key: 'btnplan' })
  expect(w.runs[0]?.command).toBe('html-plan:html-plan')
  expect(w.runs[0]?.args.startsWith('g1 ')).toBe(true)
  await ui.unmount()
})

test('Button rows: Action and HTSW, each labeled; colored labels on both surfaces; an unlisted command is hidden', async ($, on) => {
  bw(on, ['ping-personal:personal-htsw'])
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props })
    for (const k of ['btnpane', 'btnsimple', 'btnexplain', 'btnkid', 'btndeep', 'btnmotion', 'btngoals', 'btnagents', 'hide']) expect(await ui.find({ key: k })).toBeDefined()
    expect(await ui.find({ key: 'btnhandoff' })).toBeUndefined() // personal-handoff not listed
    const b = await ui.find({ key: 'btnexplain' }) as any
    if (surface === 'terminal') expect(JSON.stringify(b)).toContain(BLUE) // the label's Text child carries the color
    else expect(JSON.stringify(b)).not.toContain(BLUE) // desktop: native button, plain label
    expect((await ui.find({ key: 'btnexplain' }))?.props?.variant).toBeUndefined()
    const action = await ui.find({ key: 'buttons' }) as any, htsw = await ui.find({ key: 'htsw' }) as any
    expect(JSON.stringify(action)).toContain('Action')
    expect(JSON.stringify(htsw)).toContain('HTSW')
    expect(JSON.stringify(action)).toContain('btngoals')
    expect(JSON.stringify(action)).not.toContain('btnsimple') // the levels live in the HTSW row only
    expect(JSON.stringify(htsw)).toContain('btnsimple')
    if (surface === 'desktop') {
      expect(action.props.columnGap).toBe(1) // DEC-14 follow-up: Desktop buttons were packed edge to edge
      expect(JSON.stringify(htsw)).toContain(BLUE) // the colored chip before Explain
      expect(JSON.stringify(action)).toContain('\u25cf')
      expect(JSON.stringify(action)).toContain(CYAN) // Goals chip
      expect(JSON.stringify(action)).toContain(GRAY) // Hide chip
    } else expect(action.props.columnGap).toBeUndefined() // terminal keeps its [ a ][ b ] look
    await ui.unmount()
  }
})

test('press: Handoff runs its command with bound tracker paths; an HTSW level runs no command', async ($, on) => {
  const w = bw(on, ALL, { 'hudGoals:sid-a': [{ root: 'D:/x', path: 'docs/a/g1-audit-tracker.md' }] })
  on('ui.open', () => ({ value: { isPlaced: true } }))
  on('model.complete', () => ({ value: { isAnswered: true, text: 'answer', usage: { input_tokens: 1, output_tokens: 1 } } }))
  on('fs.read', () => ({ value: '## Explaining sentences\nrules' }))
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'desktop', component: 'AbovePrompt', props })
  await ui.press({ key: 'btnexplain' })
  await ui.press({ key: 'btnhandoff' })
  expect(w.runs).toEqual([{ command: 'ping-personal:personal-handoff', args: '--unattended docs/a/g1-audit-tracker.md' }])
  expect(w.toasts).toEqual([])
  await ui.unmount()
})

test('press during a turn toasts that it is queued and still hands the run to the engine', async ($, on) => {
  const w = bw(on, ALL, { 'hud:sid-a': { model: 'm', ctxSpark: [], samples: [], turnActive: true, usage: { rateLimits: [] } } })
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props })
  await ui.press({ key: 'btnhandoff' })
  expect(w.toasts.some(t => t.includes('Handoff queued'))).toBe(true)
  expect(w.runs).toContainEqual({ command: 'ping-personal:personal-handoff', args: '--unattended' })
  await ui.unmount()
})

const SID = '437b481d-d2fd-4db7-8b22-08eabdb3ae01'
test('Session row: no session name -> first 8 characters of the session id (DEC-15)', async ($, on) => {
  bw(on, ALL, {}, SID)
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'desktop', component: 'AbovePrompt', props })
  expect(await ui.find({ type: 'Text', text: '437b481d' })).toBeDefined()
  await ui.unmount()
})

test('Session row: a known session name wins over the short id', async ($, on) => {
  bw(on, ALL, { [`hudTitle:${SID}`]: 'plugin-desktop-fix-1' }, SID)
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'desktop', component: 'AbovePrompt', props })
  expect(await ui.find({ type: 'Text', text: 'plugin-desktop-fix-1' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: '437b481d' })).toBeUndefined()
  await ui.unmount()
})

test('row drop order with the button rows: cwd, Model, Forecast, HTSW, then Action; Now always stays', () => {
  const keys = (maxRows: number, mode?: 'compact') => layout(undefined, { surface: 'desktop', nowMs: NOW, buttons: true, maxRows, mode })!.map(r => r.key)
  expect(keys(6)).toEqual(['model', 'cwd', 'now', 'forecast', 'buttons', 'htsw'])
  expect(keys(5)).toEqual(['model', 'now', 'forecast', 'buttons', 'htsw'])
  expect(keys(4)).toEqual(['now', 'forecast', 'buttons', 'htsw'])
  expect(keys(3)).toEqual(['now', 'buttons', 'htsw'])
  expect(keys(2)).toEqual(['now', 'buttons'])
  expect(keys(1)).toEqual(['now'])
  expect(keys(12, 'compact')).toEqual(['now', 'forecast', 'buttons', 'htsw'])
})

test('Session row: name first, labels grey and values white; reset label grey, its time white', () => {
  const s = { model: 'Opus', ctxPct: 10, ctxTok: 1, ctxDeltaTok: 0, ctxSpark: [10], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: 11, resetsAt: new Date(NOW + 20 * 60000).toISOString() }] } } as any
  const r = layout(s, { surface: 'desktop', nowMs: NOW, bodyColumns: 95, title: 'plugin-desktop-fix-1', status: { branch: 'topic/mod', defaultBranch: 'main' }, step: { thinking: 'medium', cacheHitPct: 54 } as any })!
  const cwd = r.find(x => x.key === 'cwd')!.spans, model = r.find(x => x.key === 'model')!.spans
  expect(cwd.find(x => x.t === 'plugin-desktop-fix-1')).toMatchObject({ b: true })
  expect(model.find(x => x.t === ' think ')).toMatchObject({ d: true })
  expect(model.find(x => x.t === 'medium')?.d).toBeFalsy()
  expect(cwd.find(x => x.t.includes('think'))).toBeUndefined()
  expect(model.find(x => x.t === ' reset ')).toMatchObject({ d: true })
  expect(model.find(x => x.t === '20m')?.d).toBeFalsy()
  expect(model.find(x => x.t === '  5h')).toMatchObject({ d: true })
})

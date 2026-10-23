import { test, expect, mock } from 'claude-code/testing'
import { note, pruneStore, setNow, bgAdd, bgDone, endTurnNow, goalLastChange, openGoals, hasContent, archiveTracker, withExplainOption, EXPLAIN_FIRST, register } from './register'

const NOW = Date.parse('2026-10-08T12:00:00Z')
const props = (bodyColumns: number) => ({ hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns, scroll: { offset: 0, bodyRows: 12 }, view: {} })
function world(on: any, store: Record<string, unknown> = {}, engine = true) {
  mock.store(on, store)
  mock.clock(on, { now: NOW })
  on('session.cwd', () => ({ value: 'D:/work/demo-repo' }))
  on('session.id', () => ({ value: 'sid-a' }))
  if (engine) on('ui.render', { component: 'AbovePrompt' }, ($, e) => { const { Box } = $.ui.resolve(e); return <Box key="engine" /> }) // stands for the engine's own (empty) band
}

test('Loading band: four labeled rows on terminal and desktop at 140 and 90 cols', async ($, on) => {
  world(on)
  for (const surface of ['terminal', 'desktop'] as const) {
    for (const cols of [140, 90]) {
      const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(cols) })
      for (const k of ['model', 'cwd', 'now', 'forecast']) expect(await ui.find({ key: k })).toBeDefined()
      expect((await ui.find({ type: 'Text', text: /^Forecast/ }))?.text).toBe('Forecast ')
      expect(await ui.find({ type: 'Text', text: ' ... ' })).toBeDefined()
      await ui.unmount()
    }
  }
})

test('past resetsAt renders 5h as   0% (both surfaces, 140 and 90 cols)', async ($, on) => {
  world(on, { 'hud:sid-a': {
    model: 'Opus 5.5', ctxPct: 18, ctxTok: 1000, ctxDeltaTok: 0, ctxSpark: [18], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: 71, resetsAt: new Date(NOW - 60000).toISOString() }] },
  } })
  for (const surface of ['terminal', 'desktop'] as const) {
    for (const cols of [140, 90]) {
      const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(cols) })
      expect(await ui.find({ type: 'Text', text: '   0%' })).toBeDefined()
      await ui.unmount()
    }
  }
})

test('RUNS OUT chip is bold, inverse and error-colored', async ($, on) => {
  const resetsAt = new Date(NOW + 72 * 60000).toISOString() // 80% used 228 min into the window: 100% in ~57m, reset in 72m
  world(on, { 'hud:sid-a': {
    model: 'Opus 5.5', ctxPct: 61, ctxTok: 1000, ctxDeltaTok: 31000, ctxSpark: [10, 61], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: 80, resetsAt }] },
  } })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(140) })
    const c = await ui.find({ type: 'Text', text: ' RUNS OUT ' })
    expect(c?.props).toMatchObject({ bold: true, inverse: true, color: 'error' })
    await ui.unmount()
  }
})

test('calm mount: healthy has no red/amber/green but the OK word and no edge; RUNS OUT red edge + filled badge', async ($, on) => {
  world(on, { 'hudStatus:sid-a': { branch: 'topic/mod', defaultBranch: 'main' }, 'hud:sid-a': {
    model: 'Opus 5.5', ctxPct: 20, ctxTok: 1000, ctxDeltaTok: 0, ctxSpark: [20], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: 5, resetsAt: new Date(NOW + 72 * 60000).toISOString() }] },
  } })
  const loud = ['success', 'warning', 'error']
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(140) })
    const nodes = [...await ui.findAll({ type: 'Text' }), ...await ui.findAll({ type: 'Box' })]
    const hits = nodes.filter((x: any) => loud.includes(x.props?.color) || loud.includes(x.props?.backgroundColor))
    if (surface === 'desktop') expect(hits.map((x: any) => x.text)).toEqual([' OK '])
    else { // terminal numbers are colored by level (ccstatusline style): healthy = green, never amber or red
      expect(hits.map((x: any) => x.text)).toEqual(['  20%', '   5%', ' OK '])
      expect(hits.every((x: any) => x.props.color === 'success')).toBe(true)
    }
    expect(hits.find((x: any) => x.text === ' OK ').props.inverse).toBeFalsy()
    expect(await ui.find({ type: 'Text', text: String.fromCharCode(0x258c) })).toBeUndefined()
    await ui.unmount()
  }
})

test('calm mount: RUNS OUT has a red left edge and a red filled badge', async ($, on) => {
  hot(on)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(140) })
    const t = await ui.findAll({ type: 'Text' })
    expect(t[0]).toMatchObject({ text: String.fromCharCode(0x258c), props: { color: 'error' } })
    expect((await ui.find({ type: 'Text', text: ' RUNS OUT ' }))?.props).toMatchObject({ color: 'error', inverse: true })
    await ui.unmount()
  }
})

test('mode off renders nothing of ours; compact keeps Now and Forecast', async ($, on) => {
  world(on, { hudMode: 'off' })
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: props(140) }).catch(() => undefined)
  expect(ui ? await ui.find({ key: 'forecast' }) : undefined).toBeUndefined()
})

test('Hide shrinks the band to one row [ Show ]; Show restores the mode Hide came from', async ($, on) => {
  hot(on, { hudMode: 'compact' })
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: props(140) })
  expect(await ui.find({ key: 'forecast' })).toBeDefined()
  await ui.press({ key: 'hide' })
  await ui.unmount()
  const m = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: props(140) })
  expect(await m.find({ key: 'forecast' })).toBeUndefined() // one row only
  expect(await m.find({ type: 'Button', text: '[ Show ]' })).toBeDefined()
  await m.press({ key: 'show' })
  await m.unmount()
  const back = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: props(140) })
  expect(await back.find({ key: 'forecast' })).toBeDefined() // compact again: Now and Forecast
  await back.unmount()
})

test('Svg burn timeline: exactly one on desktop (140 and 86 cols), none on terminal', async ($, on) => {
  world(on, { 'hud:sid-a': {
    model: 'Opus 5.5', ctxPct: 18, ctxTok: 1000, ctxDeltaTok: 0, ctxSpark: [18], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: 80, resetsAt: new Date(NOW + 72 * 60000).toISOString() }] },
  } })
  for (const [surface, cols, n] of [['desktop', 140, 1], ['desktop', 86, 1], ['terminal', 140, 0]] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(cols) })
    expect(await ui.findAll({ type: 'Svg' })).toHaveLength(n)
    await ui.unmount()
  }
})

// 80% used 228 min into the window -> RUNS OUT; ctx 65 -> yellow ctx percent.
function hot(on: any, extra: Record<string, unknown> = {}, engine = true) {
  world(on, { ...extra, 'hudStatus:sid-a': { branch: 'topic/mod', defaultBranch: 'main' }, 'hud:sid-a': {
    model: 'Opus 5.5', ctxPct: 65, ctxTok: 1000, ctxDeltaTok: 0, ctxSpark: [65], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: 80, resetsAt: new Date(NOW + 72 * 60000).toISOString() }] },
  } }, engine)
}
// Model row nodes: the group label (e.g. '  5h' or '  | 5h') is followed by its percent number.
async function barOf(ui: any, label: string) {
  const t = await ui.findAll({ type: 'Text' })
  const i = t.findIndex((x: any) => x.text === label || x.text === label.replace(/^  /, '  | '))
  return { all: t, num: t[i + 1] }
}

test('band composes with the hooks beneath: their note first, band rows kept, at maxRows 12 and 4', async ($, on) => {
  hot(on, {}, false)
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => { const { Text } = $.ui.resolve(e); return <Text key="other">other mod note</Text> })
  for (const surface of ['terminal', 'desktop'] as const) {
    for (const maxRows of [12, 4]) {
      const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: { ...props(140), maxRows } })
      const t = (await ui.findAll({ type: 'Text' })).map((x: any) => x.text)
      expect(t.indexOf('other mod note')).toBeGreaterThan(-1)
      expect(t.indexOf('other mod note')).toBeLessThan(t.indexOf(' RUNS OUT ')) // the note is drawn before the band
      // Desktop's engine hands back a non-empty band even with no note, so a note never forces compact.
      expect(await ui.find({ key: maxRows === 12 ? 'model' : 'now' })).toBeDefined()
      expect(await ui.find({ key: 'forecast' })).toBeDefined()
      await ui.unmount()
    }
  }
})

test('hasContent: an empty Box is nothing, a Text or a Box holding one is something', async () => {

  expect(hasContent(null)).toBe(false)
  expect(hasContent({ type: 'Box', props: {} })).toBe(false)
  expect(hasContent({ type: 'Box', props: { children: [null, { type: 'Box', props: {} }] } })).toBe(false)
  expect(hasContent({ type: 'Text', props: { children: 'x' } })).toBe(true)
  expect(hasContent({ type: 'Box', props: { children: { type: 'Text', props: {} } } })).toBe(true)
})

test('max color mount: Model row numbers carry the warning colors on both surfaces, no bars', async ($, on) => {
  hot(on)
  for (const surface of ['terminal', 'desktop'] as const) {
    for (const cols of [140, 90]) {
      const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(cols) })
      const five = await barOf(ui, '  5h')
      expect(five.num).toMatchObject({ text: '  80%', props: { color: 'error' } })
      expect((await barOf(ui, '  ctx')).num).toMatchObject({ text: '  65%', props: { color: 'warning' } })
      expect((await ui.findAll({ type: 'Box' })).some((x: any) => /^(ctx|5h|7d)(fill|empty)/.test(String(x.key)))).toBe(false)
      const [edge, lab, model] = five.all
      expect(edge.props).toMatchObject({ color: 'error' }) // RUNS OUT: red left edge
      expect(lab).toMatchObject({ text: 'Model    ', props: { dimColor: true } })
      expect(lab.props.color).toBeUndefined()
      expect(model.props).toMatchObject({ bold: true })
      expect(model.props.color).toBeUndefined()
      expect((await ui.find({ type: 'Text', text: 'topic/mod' }))?.props.color).toBeUndefined()
      expect(await ui.findAll({ type: 'Svg' })).toHaveLength(surface === 'desktop' ? 1 : 0)
      await ui.unmount()
    }
  }
})

test('glyphs ascii: terminal bars drawn with # and .', async ($, on) => {
  hot(on, { hudGlyphs: 'ascii', 'hudTasks:sid-a': [{ id: '1', title: 'Done', status: 'completed' }, { id: '2', title: 'Next', status: 'in_progress' }] })
  for (const surface of ['terminal'] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(140) })
    const t = await ui.findAll({ type: 'Text' }), i = t.findIndex((x: any) => x.text === '  | Tasks ')
    expect(t[i + 2].text + t[i + 3].text).toBe('#####.....')
    await ui.unmount()
  }
})

test('desktop 86 cols: 7d reset shown, solid Box bars (no light shade), one ctx percent', async ($, on) => {
  world(on, { 'hud:sid-a': {
    model: 'Opus 5.5', ctxPct: 65, ctxTok: 1000, ctxDeltaTok: 0, ctxSpark: [65], samples: [], turnActive: false, lastRefreshMs: NOW,
    usage: { rateLimits: [{ kind: 'five_hour', percentUsed: 20, resetsAt: new Date(NOW + 88 * 60000).toISOString() },
      { kind: 'seven_day', percentUsed: 3, resetsAt: new Date(NOW + (6 * 1440 + 13 * 60) * 60000).toISOString() }] },
  } })
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'desktop', component: 'AbovePrompt', props: props(86) })
  const texts = (await ui.findAll({ type: 'Text' })).map((t: any) => String(t.text))
  const all = texts.join('')
  expect(all).toContain(' 6d13h')
  expect(all).toContain(' 1h28')
  expect(texts.some(t => t.includes(String.fromCharCode(0x2591)))).toBe(false)
  expect(all.split('65%').length - 1).toBe(1)
  expect(await ui.findAll({ type: 'Svg' })).toHaveLength(1)
  await ui.unmount()
})

test('per-session state: the band reads only its own session key', async ($, on) => {
  const mk = (model: string) => ({ model, ctxPct: 10, ctxTok: 1, ctxDeltaTok: 0, ctxSpark: [10], samples: [], turnActive: false, usage: { rateLimits: [] } })
  world(on, { 'hud:sid-a': mk('Opus A'), 'hud:sid-b': mk('Sonnet B') })
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: props(140) })
  expect(await ui.find({ type: 'Text', text: 'Opus A' })).toBeDefined()
  expect(await ui.find({ type: 'Text', text: 'Sonnet B' })).toBeUndefined()
  await ui.unmount()
})

// used% with 72 min to reset (minute 228 of the window): 5 OK, 70 TIGHT, 80 RUNS OUT, 1 LEARNING.
const hudAt = (used: number) => ({
  model: 'Opus 5.5', ctxPct: 18, ctxTok: 1000, ctxDeltaTok: 0, ctxSpark: [18], samples: [], turnActive: false, lastRefreshMs: NOW,
  usage: { rateLimits: [{ kind: 'five_hour', percentUsed: used, resetsAt: new Date(NOW + 72 * 60000).toISOString() }] },
})
const SENTENCE: Array<[number, RegExp, string]> = [
  [5, /^ 5h won't run out: at this pace 100% in \S+, after the reset in 1h12$/, ''],
  [70, /^ 5h is close: at this pace 100% in 1h38, only 26m after the reset in 1h12/, ' -- slow down'],
  [80, /^ 5h will run out: at this pace 100% in 57m, 15m BEFORE the reset in 1h12/, ' -- wrap up or pause'],
  [1, /^ 5h under 2% used/, ' -- no pace yet'],
]

for (const [used, re, advice] of SENTENCE) {
  for (const withTasks of [true, false]) {
    test(`readability mount ${used}% tasks=${withTasks}: sentence, Tasks bar, goal phase, no codex (both surfaces, 140 and 86)`, async ($, on) => {
      const store: Record<string, unknown> = {
        'hud:sid-a': hudAt(used), 'hudGoalRows:sid-a': [{ slug: 'big', done: 10, total: 12, step: 'Ship' }],
        'hudStatus:sid-a': { branch: 'b', defaultBranch: 'main', codex: { fiveH: { pct: 9, resetsAtMs: NOW + 1e6 } } },
      }
      if (withTasks) store['hudTasks:sid-a'] = [{ id: '1', title: 'Implement', status: 'in_progress' }, { id: '2', title: 'Commit', status: 'pending' }]
      world(on, store)
      for (const surface of ['terminal', 'desktop'] as const) {
        for (const cols of [140, 86]) {
          const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(cols) })
          const all = (await ui.findAll({ type: 'Text' })).map((t: any) => String(t.text))
          const s = all.find(t => re.test(t))
          expect(s).toBeDefined()
          expect(s!.endsWith(advice)).toBe(cols === 140 || advice === '')
          if (cols === 86 && advice) expect(s).not.toContain(' -- ')
          expect(all.includes(surface === 'terminal' ? '  | Tasks ' : '   Tasks ')).toBe(withTasks)
          if (withTasks) expect(all).toContain(' 0/2: ')
          if (surface === 'terminal') { expect(all).toContain('11/12'); expect(all).toContain('  Ship') }
          else expect(all).toContain(' phase 11 of 12 (83%): Ship')
          expect(all.join('')).not.toMatch(/codex/i)
          await ui.unmount()
        }
      }
    })
  }
}

// Fake $ over one shared store map, as two sessions on one machine see it.
function fakeStore(map: Record<string, unknown>, sid: string) {
  return {
    session: { id: async () => sid },
    store: {
      get: async (k: string) => map[k], set: async (k: string, v: unknown) => { map[k] = v },
      delete: async (k: string) => { delete map[k] }, keys: async () => Object.keys(map),
    },
  }
}

test('per-session state: two sessions writing never overwrite each other', async () => {
  const map: Record<string, unknown> = { hudMode: 'compact' }
  await note(fakeStore(map, 'sid-a'), 'hudNow', 'Running Bash')
  await note(fakeStore(map, 'sid-b'), 'hudNow', 'idle')
  expect(map['hudNow:sid-a']).toBe('Running Bash')
  expect(map['hudNow:sid-b']).toBe('idle')
  expect(map.hudMode).toBe('compact')
})

test('pruneStore drops other sessions unseen for 7 days and legacy keys; keeps machine-wide keys', async () => {
  const day = 864e5
  const map: Record<string, unknown> = {
    hudMode: 'on', hudGlyphs: 'ascii', hudStatusLine: true, hud: {}, hudNow: 'x',
    'hudSeen:old': NOW - 8 * day, 'hud:old': {}, 'hudNow:old': 'x', 'hudToast:old': {}, 'hudBg:old': [],
    'hudSeen:new': NOW - day, 'hud:new': {}, 'hudNow:orphan': 'x', 'hud:sid-a': {},
  }
  await pruneStore(fakeStore(map, 'sid-a'), NOW)
  expect(Object.keys(map).sort()).toEqual(['hud:new', 'hud:sid-a', 'hudGlyphs', 'hudMode', 'hudSeen:new', 'hudStatusLine'])
})

test('goal on the Now row with mode on, glyphs ascii, no tasks; title follows the colon (desktop 86, terminal 86 and 140)', async ($, on) => {
  hot(on, { 'hudGoalRows:sid-a': [{ slug: 'ping-hud', done: 10, total: 12, step: 'Visual review' }], 'hudNow:sid-a': 'idle', hudMode: 'on', hudGlyphs: 'ascii' }) // store as /hud compact, glyphs ascii, on leave it
  for (const [surface, cols] of [['desktop', 86], ['terminal', 86], ['terminal', 140]] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AbovePrompt', props: props(cols) })
    const all = (await ui.findAll({ type: 'Text' })).map((t: any) => String(t.text))
    expect(all.join('')).toContain('Goal ping-hud')
    if (surface === 'terminal') { expect(all).toContain('11/12'); expect(all).toContain('  Visual review') }
    else expect(all).toContain(' phase 11 of 12 (83%): Visual review') // title one space after the colon, same Text

    await ui.unmount()
  }
})

// fakeStore plus a counter of $.ui.invalidate('ui.render') calls.
function drawn(map: Record<string, unknown>, sid = 'sid-a') {
  const calls: string[] = []
  return { calls, $: { ...fakeStore(map, sid), ui: { invalidate: (k: string) => { calls.push(k) } } } }
}

test('setNow writes this session hudNow and asks for a redraw', async () => {
  const map: Record<string, unknown> = {}, d = drawn(map)
  await setNow(d.$, 'Running Bash (npm test)')
  expect(map['hudNow:sid-a']).toBe('Running Bash (npm test)')
  expect(d.calls).toEqual(['ui.render'])
})

test('turn end writes idle only when no background agent runs', async () => {
  const map: Record<string, unknown> = {}, d = drawn(map)
  await bgAdd(d.$, 'tu1', 'Agent (scan)', 5)
  await endTurnNow(d.$)
  expect(map['hudNow:sid-a']).toBe('waiting: 1 agent running, Agent (scan)')
  await bgDone(d.$, 'tu1')
  await endTurnNow(d.$)
  expect(map['hudNow:sid-a']).toBe('idle')
  expect(d.calls.length).toBeGreaterThanOrEqual(4) // each hudBg and hudNow write redraws
})

// Store over the caller's map (mock.store keeps a private copy a test cannot read back).
function memStore(on: any, map: Record<string, unknown>) {
  on('store.get', (_$: any, e: any) => ({ value: map[e.key] }))
  on('store.set', (_$: any, e: any) => { map[e.key] = e.value; return { value: undefined } })
  on('store.delete', (_$: any, e: any) => { delete map[e.key]; return { value: undefined } })
  on('store.keys', () => ({ value: Object.keys(map) }))
}

// One full agent.spawn payload, reused by every spawn test.
const spawnInput = { prompt: 'p', description: 'scan', subagentType: 'general-purpose', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'claude-opus-5-5', fork: false }

test('foreground spawn adds nothing; background spawn adds its agent id', async ($, on) => {
  const map: Record<string, unknown> = {}
  memStore(on, map)
  mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  // Engine bottom: answers like a started agent, so the hook really runs.
  on('agent.spawn', () => ({ agentId: 'a1', model: 'm' }) as any)
  await expect($.agent.spawn({ ...spawnInput, tool_use_id: 'fg', background: false } as any)).resolves.toBeDefined()
  expect(map['hudBg:sid-a']).toBeUndefined()
  await $.agent.spawn({ ...spawnInput, tool_use_id: 'bg', background: true } as any)
  expect((map['hudBg:sid-a'] as any[]).map(b => b.id)).toEqual(['a1'])
})

test('two workflow agents sharing one tool_use_id count as two', async ($, on) => {
  const map: Record<string, unknown> = {}
  memStore(on, map)
  mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  let n = 0
  on('agent.spawn', () => ({ agentId: `w${++n}`, model: 'm' }) as any)
  const wf = (i: number) => ({ ...spawnInput, tool_use_id: 'wf-call', background: true, workflow: { runId: 'r1', agentIndex: i } })
  await $.agent.spawn(wf(1) as any)
  await $.agent.spawn(wf(2) as any)
  expect((map['hudBg:sid-a'] as any[]).length).toBe(2)
})

// A valid main-turn turn.complete payload; a subagent's adds agentId.
const done = { answer: 'a', durationMs: 1, isAborted: false, turnId: 't1', reason: 'end_turn' }

test('a subagent turn.complete drops its hudBg entry and leaves the main turn state alone', async ($, on) => {
  const map: Record<string, unknown> = { 'hudBg:sid-a': [{ id: 'a1', act: 'Agent (scan)', tMs: 1 }], 'hudNow:sid-a': 'Running Bash', 'hud:sid-a': { turnActive: true } }
  memStore(on, map)
  mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ ...done, agentId: 'a1' } as any)
  expect(map['hudBg:sid-a']).toEqual([])
  expect(map['hudNow:sid-a']).toBe('Running Bash')
  expect((map['hud:sid-a'] as any).turnActive).toBe(true)
})

test('session.start clears hudBg and live bypass left by a previous process', async ($, on) => {
  const map: Record<string, unknown> = { 'hudBg:sid-a': [{ id: 'a1', act: 'Agent (scan)', tMs: 1 }], 'hudBypass:sid-a': true }
  memStore(on, map)
  mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  on('session.start', () => ({ cwd: 'D:/x' }) as any)
  await $.session.start({ cwd: 'D:/x' } as any)
  expect(map['hudBg:sid-a']).toEqual([])
  expect(map['hudBypass:sid-a']).toBe(false) // a restart never keeps bypass on
})

test('a subagent turn.complete between turns settles Now to idle; the last of two leaves waiting', async ($, on) => {
  const map: Record<string, unknown> = { 'hudBg:sid-a': [{ id: 'a1', act: 'Agent (one)', tMs: 1 }, { id: 'a2', act: 'Agent (two)', tMs: 2 }], 'hudNow:sid-a': 'waiting: 2 agents running, Agent (two)', 'hud:sid-a': { turnActive: false } }
  memStore(on, map)
  mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ ...done, agentId: 'a2' } as any)
  expect(map['hudNow:sid-a']).toBe('waiting: 1 agent running, Agent (one)')
  await $.turn.complete({ ...done, agentId: 'a1' } as any)
  expect(map['hudNow:sid-a']).toBe('idle')
})

test('concurrent bgAdd calls both land', async () => {
  const map: Record<string, unknown> = {}, d = drawn(map)
  await Promise.all([bgAdd(d.$, 'x', 'Agent (x)', 1), bgAdd(d.$, 'y', 'Agent (y)', 2)])
  expect((map['hudBg:sid-a'] as any[]).map(b => b.id).sort()).toEqual(['x', 'y'])
})

// ---- goal binding: a fake repo under ROOT, answered through the fs / process / ui hooks ----
const ROOT = 'D:/work/demo-repo'
type FakeFile = { text: string; mtimeMs: number }
const trackerText = (slug: string, rows = ['| 0 | ASK:x | A | Pending | -- | -- |']) => [
  '---', `goal_slug: ${slug}`, '---', '# t', '', '## Phase Status', '',
  '| Phase | Source | Title | Status | Commit | Subagent |', '|---|---|---|---|---|---|', ...rows, '', '## Cost Log',
].join('\n')
const file = (text: string, mtimeMs = NOW - 1000): FakeFile => ({ text, mtimeMs })
const T = (p: string) => `${ROOT}/${p}`

// goal world: store over `map`, fs over `files` (mutable), git answers `gitOut`, toasts and redraws recorded.
function goalWorld(on: any, files: Record<string, FakeFile>, map: Record<string, unknown> = {}, gitOut: { value: string | Error } = { value: '' }) {
  memStore(on, map)
  mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  on('session.cwd', () => ({ value: ROOT }))
  const w = { map, files, toasts: [] as string[], inval: 0, gitRuns: [] as any[], statusRuns: [] as any[], status: '', goalLists: 0, fsCalls: 0, failList: false, procRuns: [] as string[][], mvFail: false }
  const np = (p: string) => p.replace(/\\/g, '/')
  const kids = (p: string) => [...new Set(Object.keys(files).filter(k => k.startsWith(p + '/')).map(k => k.slice(p.length + 1).split('/')[0]))]
  on('fs.exists', (_$: any, e0: any) => { w.fsCalls++; const e = { ...e0, path: np(e0.path) }; return { value: e.path in files || kids(e.path).length > 0 } })
  on('fs.read', (_$: any, e0: any) => { const e = { ...e0, path: np(e0.path) }; if (!(e.path in files)) throw new Error('ENOENT'); return { value: files[e.path].text } })
  on('fs.stat', (_$: any, e0: any) => { const e = { ...e0, path: np(e0.path) };
    if (e.path in files) return { value: { kind: 'file', size: 1, mtimeMs: files[e.path].mtimeMs, isLink: false } }
    if (kids(e.path).length) return { value: { kind: 'dir', size: 0, mtimeMs: 0, isLink: false } }
    throw new Error('ENOENT')
  })
  on('fs.list', (_$: any, e0: any) => { w.fsCalls++; if (w.failList) { w.failList = false; throw new Error('disk') } const e = { ...e0, path: np(e0.path) };
    if (/\/docs$/.test(e.path)) w.goalLists++
    return { value: kids(e.path).map(n => { const f = files[`${e.path}/${n}`]; return { name: n, kind: f ? 'file' : 'dir', size: f ? 1 : 0, mtimeMs: f ? f.mtimeMs : 0 } }) }
  })
  on('process.run', (_$: any, e: any) => {
    const r = { exitCode: 1, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false }
    w.procRuns.push(e.argv)
    if (e.argv[0] === 'git' && e.argv[1] === 'mv') return { value: { ...r, exitCode: w.mvFail ? 128 : 0, stderr: w.mvFail ? 'fatal: not under version control, source=x\n' : '' } }
    if (e.argv[1] !== '--literal-pathspecs') return { value: r }
    // git status answers which trackers have uncommitted edits (w.status, porcelain lines; '' = none).
    if (e.argv[2] === 'status') { w.statusRuns.push(e); return { value: { ...r, exitCode: 0, stdout: w.status } } }
    w.gitRuns.push(e)
    if (gitOut.value instanceof Error) throw gitOut.value
    return { value: { ...r, exitCode: 0, stdout: gitOut.value } }
  })
  on('ui.toast', (_$: any, e: any) => { w.toasts.push(e.text); return { value: undefined } })
  on('ui.invalidate', (_$: any, e: any, next: any) => { w.inval++; return next(e) }) // passes on, so a mounted drawing redraws
  on('command.run', () => ({ text: '' }))
  on('ui.render', { component: 'AbovePrompt' }, ($: any, e: any) => { const { Box } = $.ui.resolve(e); return <Box key="engine" /> }) // the engine's empty band
  return w
}
const GOAL = 'ping-personal:personal-goal'
const g1 = () => ({ [T('docs/a/g1-audit-tracker.md')]: file(trackerText('g1')), [T('docs/b/other-audit-tracker.md')]: file(trackerText('other')) })

test('bind: one tracker with goal_slug binds it', async ($, on) => {
  const w = goalWorld(on, g1())
  await $.command.run({ command: GOAL, args: 'g1' })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
  expect(w.inval).toBe(1) // one redraw for the one store change that shows on the band
})

test('bind: goal and goal-next match prefixed and bare names', async ($, on) => {
  const w = goalWorld(on, g1())
  for (const command of ['ping-personal:personal-goal-next', 'personal-goal', 'personal-goal-next']) {
    delete w.map['hudGoals:sid-a']
    await $.command.run({ command, args: 'g1 phase done' })
    expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
  }
})

test('bind: no tracker adds to pending', async ($, on) => {
  const w = goalWorld(on, g1())
  await $.command.run({ command: GOAL, args: 'g9' })
  expect(w.map['hudGoalPending:sid-a']).toEqual([{ slug: 'g9', turns: 0 }])
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
})

test('bind: two trackers with one slug bind none and toast once', async ($, on) => {
  const w = goalWorld(on, { ...g1(), [T('docs/c/dup-audit-tracker.md')]: file(trackerText('dup')), [T('docs/d/dup2-audit-tracker.md')]: file(trackerText('dup')) })
  await $.command.run({ command: GOAL, args: 'dup' })
  await $.command.run({ command: GOAL, args: 'dup' })
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
  expect(w.toasts).toEqual(['ambiguous goal dup: pick in Goals'])
})

test('bind: archived trackers are not scanned for a slug', async ($, on) => {
  const w = goalWorld(on, { [T('docs/archived/g1-audit-tracker.md')]: file(trackerText('g1')) })
  await $.command.run({ command: GOAL, args: 'g1' })
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
  expect(w.map['hudGoalPending:sid-a']).toEqual([{ slug: 'g1', turns: 0 }])
})

test('bind: /personal-loop --resume <slug> binds like goal-next; other loop forms bind nothing', async ($, on) => {
  const w = goalWorld(on, g1())
  await $.command.run({ command: 'ping-personal:personal-loop', args: '--campaign g1' })
  await $.command.run({ command: 'ping-personal:personal-loop', args: 'fix the thing' })
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
  expect(w.map['hudGoalPending:sid-a']).toBeUndefined()
  await $.command.run({ command: 'ping-personal:personal-loop', args: '--resume g1' })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
})

test('bind: invalid slug is ignored, no store change, no toast', async ($, on) => {
  const w = goalWorld(on, g1())
  await $.command.run({ command: GOAL, args: 'Bad;x' })
  expect(Object.keys(w.map).filter(k => k.startsWith('hudGoal'))).toEqual([])
  expect(w.toasts).toEqual([])
})

test('bind: Skill tool with slug input binds; another skill does not', async ($, on) => {
  const w = goalWorld(on, g1())
  on('tool.call', () => ({ result: { text: 'ok' } }) as any)
  await $.tool.call({ tool: 'Skill', skill: 'ping-personal:personal-handoff', args: 'g1' } as any)
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
  await $.tool.call({ tool: 'Skill', skill: 'ping-personal:personal-goal-next', args: 'g1' } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
})

test('bind: concurrent goal commands both land in pending', async ($, on) => {
  const w = goalWorld(on, g1())
  await Promise.all([$.command.run({ command: GOAL, args: 'g8' }), $.command.run({ command: GOAL, args: 'g9' })])
  expect((w.map['hudGoalPending:sid-a'] as any[]).map(p => p.slug).sort()).toEqual(['g8', 'g9'])
})

const doneEv = { answer: 'a', durationMs: 1, isAborted: false, turnId: 't1', reason: 'end_turn' }
const wr = (path: string) => ({ tool: 'Write', file_path: path, content: 'x' }) as any
// Bottom of tool.call: runs `effect` as the tool's work, so a test can make the file appear.
const toolDoes = (on: any, effect: () => void = () => {}) => on('tool.call', () => { effect(); return { result: { text: 'ok' } } as any })

test('pending binds when the tracker appears after a Write, and a tool re-check does not age it', async ($, on) => {
  const w = goalWorld(on, g1(), { 'hudGoalPending:sid-a': [{ slug: 'g9', turns: 0 }, { slug: 'zz', turns: 1 }] })
  toolDoes(on, () => { w.files[T('docs/x/g9-audit-tracker.md')] = file(trackerText('g9')) })
  await $.tool.call(wr(T('docs/x/g9-audit-tracker.md')))
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/x/g9-audit-tracker.md' }])
  expect(w.map['hudGoalPending:sid-a']).toEqual([{ slug: 'zz', turns: 1 }])
})

test('Now: a subagent tool call (agentId set) leaves Now alone; a main-session call sets it', async ($, on) => {
  const w = goalWorld(on, g1(), { 'hudNow:sid-a': 'waiting: 1 agent running, Agent (scan)' })
  toolDoes(on)
  await $.tool.call({ tool: 'Bash', command: 'ls', agentId: 'a1' } as any)
  expect(w.map['hudNow:sid-a']).toBe('waiting: 1 agent running, Agent (scan)')
  await $.tool.call({ tool: 'Bash', command: 'ls' } as any)
  expect(String(w.map['hudNow:sid-a'])).toContain('Bash')
})

test('pending binds after a Bash call once the tracker exists under its slug', async ($, on) => {
  const w = goalWorld(on, g1(), { 'hudGoalPending:sid-a': [{ slug: 'g9', turns: 0 }] })
  toolDoes(on, () => { w.files[T('docs/x/other-name-audit-tracker.md')] = file(trackerText('g9')) })
  await $.tool.call({ tool: 'Bash', command: 'python make.py' } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/x/other-name-audit-tracker.md' }])
  expect(w.map['hudGoalPending:sid-a']).toEqual([])
})

test('pending dropped after 3 turns with one toast', async ($, on) => {
  const w = goalWorld(on, g1(), { 'hudGoalPending:sid-a': [{ slug: 'g9', turns: 0 }] })
  on('turn.complete', () => ({ text: '' }))
  for (let i = 0; i < 2; i++) {
    await $.turn.complete(doneEv as any)
    expect(w.toasts).toEqual([])
  }
  await $.turn.complete(doneEv as any)
  expect(w.map['hudGoalPending:sid-a']).toEqual([])
  expect(w.toasts).toEqual(['goal g9 not found'])
})

test('pending binds on turn.complete when the tracker appeared outside a tool call', async ($, on) => {
  const w = goalWorld(on, g1(), { 'hudGoalPending:sid-a': [{ slug: 'g9', turns: 1 }] })
  on('turn.complete', () => ({ text: '' }))
  w.files[T('docs/x/g9-audit-tracker.md')] = file(trackerText('g9'))
  await $.turn.complete(doneEv as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/x/g9-audit-tracker.md' }])
  expect(w.map['hudGoalPending:sid-a']).toEqual([])
})

test('a subagent turn.complete does not age pending', async ($, on) => {
  const w = goalWorld(on, g1(), { 'hudGoalPending:sid-a': [{ slug: 'g9', turns: 2 }] })
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ ...doneEv, agentId: 'a1' } as any)
  expect(w.map['hudGoalPending:sid-a']).toEqual([{ slug: 'g9', turns: 2 }])
  expect(w.toasts).toEqual([])
})

test('a nested goal write during /personal-workflow binds the tracker (relative and absolute path, Edit too)', async ($, on) => {
  const w = goalWorld(on, { [T('docs/x/x-audit-tracker.md')]: file(trackerText('x')), [T('docs/y/y-audit-tracker.md')]: file(trackerText('y')) })
  toolDoes(on)
  await $.tool.call(wr('docs/x/x-audit-tracker.md'))
  await $.tool.call({ tool: 'Edit', file_path: T('docs/y/y-audit-tracker.md'), old_string: 'a', new_string: 'b' } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/x/x-audit-tracker.md' }, { root: ROOT, path: 'docs/y/y-audit-tracker.md' }])
})

test('tracker write binds each tracker once and ignores other files', async ($, on) => {
  const w = goalWorld(on, { [T('docs/x/x-audit-tracker.md')]: file(trackerText('x')), [T('docs/x/notes.md')]: file('n') })
  toolDoes(on)
  await $.tool.call(wr(T('docs/x/x-audit-tracker.md')))
  await $.tool.call(wr('docs/x/x-audit-tracker.md'))
  await $.tool.call(wr(T('docs/x/notes.md')))
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/x/x-audit-tracker.md' }])
})

test('Bash bind needs the path in the command and a newer mtime', async ($, on) => {
  const w = goalWorld(on, { [T('docs/x/x-audit-tracker.md')]: file(trackerText('x'), NOW - 5000) })
  toolDoes(on)
  await $.tool.call({ tool: 'Bash', command: 'cat docs/x/x-audit-tracker.md' } as any)
  expect(w.map['hudGoals:sid-a']).toBeUndefined() // read only: mtime is older than the call
  await $.tool.call({ tool: 'Bash', command: 'python finalize.py' } as any)
  expect(w.map['hudGoals:sid-a']).toBeUndefined() // no path in the command
  w.files[T('docs/x/x-audit-tracker.md')].mtimeMs = NOW + 10
  await $.tool.call({ tool: 'Bash', command: 'sed -i s/a/b/ docs/x/x-audit-tracker.md' } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/x/x-audit-tracker.md' }])
})

test('tracker-write bind ignores an archived path', async ($, on) => {
  const w = goalWorld(on, { [T('docs/archived/x-audit-tracker.md')]: file(trackerText('x')) })
  toolDoes(on)
  await $.tool.call(wr(T('docs/archived/x-audit-tracker.md')))
  await $.tool.call({ tool: 'Bash', command: 'touch docs/archived/x-audit-tracker.md' } as any)
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
})

const PROG = 'docs/progress/2026-10-08-x-progress.md'
const readOf = (path: string) => ({ tool: 'Read', file_path: path }) as any
const progressWith = (...lines: string[]) => file(['# Progress', ...lines].join('\n'))

test('resume binds every live Goal beacon in a read progress file, also one mid-line', async ($, on) => {
  const w = goalWorld(on, { ...g1(), [T(PROG)]: progressWith('Goal beacon: docs/a/g1-audit-tracker.md', 'also tracking Goal beacon: docs/b/other-audit-tracker.md today') })
  toolDoes(on)
  await $.tool.call(readOf(T(PROG)))
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }, { root: ROOT, path: 'docs/b/other-audit-tracker.md' }])
})

test('resume also reads a *-handoff.md and a relative file_path; other files are ignored', async ($, on) => {
  const w = goalWorld(on, { ...g1(), [T('docs/progress/2026-10-08-x-handoff.md')]: progressWith('Goal beacon: docs/a/g1-audit-tracker.md'), [T('docs/notes.md')]: progressWith('Goal beacon: docs/b/other-audit-tracker.md') })
  toolDoes(on)
  await $.tool.call(readOf('docs/notes.md'))
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
  await $.tool.call(readOf('docs/progress/2026-10-08-x-handoff.md'))
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
})

test('resume: a missing or archived beacon toasts once per file', async ($, on) => {
  const w = goalWorld(on, { [T(PROG)]: progressWith('Goal beacon: docs/gone/x-audit-tracker.md'), [T('docs/archived/y-audit-tracker.md')]: file(trackerText('y')) })
  toolDoes(on)
  await $.tool.call(readOf(T(PROG)))
  await $.tool.call(readOf(T(PROG)))
  expect(w.toasts).toEqual(['goal tracker x-audit-tracker.md moved or missing'])
  w.files[T(PROG)] = progressWith('Goal beacon: docs/archived/y-audit-tracker.md')
  await $.tool.call(readOf(T(PROG)))
  await $.tool.call(readOf(T(PROG)))
  expect(w.toasts).toEqual(['goal tracker x-audit-tracker.md moved or missing', 'goal tracker y-audit-tracker.md moved or missing'])
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
})

test('resume does nothing when a goal is already bound', async ($, on) => {
  const bound = [{ root: ROOT, path: 'docs/b/other-audit-tracker.md' }]
  const w = goalWorld(on, { ...g1(), [T(PROG)]: progressWith('Goal beacon: docs/a/g1-audit-tracker.md', 'Goal beacon: docs/gone/x-audit-tracker.md') }, { 'hudGoals:sid-a': bound })
  toolDoes(on)
  await $.tool.call(readOf(T(PROG)))
  expect(w.map['hudGoals:sid-a']).toEqual(bound)
  expect(w.toasts).toEqual([])
})

test('resume ignores beacon paths that fail the path rule, without a toast', async ($, on) => {
  const w = goalWorld(on, { ...g1(), [T(PROG)]: progressWith(`Goal beacon: ${T('docs/a/g1-audit-tracker.md')}`, 'Goal beacon: ../elsewhere/x-audit-tracker.md', 'Goal beacon: docs/a/../a/g1-audit-tracker.md', 'Goal beacon: docs/a/notes.md') })
  toolDoes(on)
  await $.tool.call(readOf(T(PROG)))
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
  expect(w.toasts).toEqual([])
})

const done2 = trackerText('fin', ['| 0 | ASK:x | A | OK Done | -- | -- |', '| 1 | ASK:x | B | OK Done | -- | -- |'])
const bound = (...paths: string[]) => ({ 'hudGoals:sid-a': paths.map(path => ({ root: ROOT, path })) })
const MSG = 'tracker moved, removed or finalized'

test('unbind on move, delete and finalize at turn.complete; an active tracker stays', async ($, on) => {
  const w = goalWorld(on, {
    [T('docs/live/live-audit-tracker.md')]: file(trackerText('live')),
    [T('docs/archived/moved-audit-tracker.md')]: file(trackerText('moved')),
    [T('docs/f/fin-audit-tracker.md')]: file(done2, NOW - 5000), [T('docs/f/fin-audit-tracker.md.accept-cache')]: file('{}', NOW - 1000),
  }, bound('docs/live/live-audit-tracker.md', 'docs/gone/del-audit-tracker.md'))
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete(doneEv as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/live/live-audit-tracker.md' }])
  expect(w.toasts).toEqual(['goal del cleared: ' + MSG])
  for (const path of ['docs/archived/moved-audit-tracker.md', 'docs/f/fin-audit-tracker.md']) {
    w.map['hudGoals:sid-a'] = [{ root: ROOT, path }]
    await $.turn.complete(doneEv as any)
    expect(w.map['hudGoals:sid-a']).toEqual([])
  }
  expect(w.toasts).toEqual(['goal del cleared: ' + MSG, 'goal moved cleared: ' + MSG, 'goal fin cleared: ' + MSG])
})

test('a finalized-looking tracker with a newer commit than its cache is re-opened work and stays bound', async ($, on) => {
  const w = goalWorld(on, { [T('docs/f/fin-audit-tracker.md')]: file(done2, NOW - 5000), [T('docs/f/fin-audit-tracker.md.accept-cache')]: file('{}', NOW - 1000) },
    bound('docs/f/fin-audit-tracker.md'), { value: `${Math.floor(NOW / 1000)}\ndocs/f/fin-audit-tracker.md\n` })
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete(doneEv as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/f/fin-audit-tracker.md' }])
  expect(w.gitRuns).toHaveLength(1)
  expect(w.gitRuns[0].argv.slice(0, 6)).toEqual(['git', '--literal-pathspecs', 'log', '--format=%ct', '--name-only', '--'])
  expect(w.gitRuns[0].argv.slice(6)).toEqual(['docs/f/fin-audit-tracker.md'])
  expect(w.gitRuns[0].init).toMatchObject({ timeoutMs: 5000 })
})

test('several unbinds in one check merge into one toast, and are not repeated', async ($, on) => {
  const w = goalWorld(on, {}, bound('docs/a/a-audit-tracker.md', 'docs/b/b-audit-tracker.md'))
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete(doneEv as any)
  expect(w.toasts).toEqual(['2 goals cleared: ' + MSG])
  await $.turn.complete(doneEv as any)
  expect(w.toasts).toHaveLength(1)
})

test('a subagent turn.complete does not unbind', async ($, on) => {
  const w = goalWorld(on, {}, bound('docs/a/a-audit-tracker.md'))
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ ...doneEv, agentId: 'a1' } as any)
  expect(w.map['hudGoals:sid-a']).toHaveLength(1)
})

test('unbind runs on session.start', async ($, on) => {
  const w = goalWorld(on, {}, bound('docs/a/a-audit-tracker.md'))
  on('session.start', () => ({ cwd: 'D:/x' }) as any)
  await $.session.start({ cwd: 'D:/x' } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([])
  expect(w.toasts).toEqual(['goal a cleared: ' + MSG])
})

test('unbind runs after a tool.call naming the bound path, not after an unrelated call', async ($, on) => {
  const p = 'docs/a/a-audit-tracker.md'
  const w = goalWorld(on, { [T(p)]: file(trackerText('a')) }, bound(p))
  toolDoes(on, () => { delete w.files[T(p)]; w.files[T('docs/archived/a-audit-tracker.md')] = file(trackerText('a')) })
  await $.tool.call({ tool: 'Bash', command: 'ls' } as any)
  expect(w.map['hudGoals:sid-a']).toHaveLength(1) // the move already happened but the call did not name the path
  await $.tool.call({ tool: 'Bash', command: `git mv ${p} docs/archived/` } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([])
  expect(w.toasts).toEqual(['goal a cleared: ' + MSG])
})

test('goalLastChange: commit time for unchanged files, newer of commit and mtime for modified ones; git failure falls back to mtime', async () => {
  const runs: any[] = []
  const mk = (run: (argv: string[]) => Promise<any>, status = '') => ({
    fs: { stat: async (p: string) => ({ mtimeMs: p.endsWith('a-audit-tracker.md') ? 5000 : 9000 }) },
    process: { run: async (argv: string[], init: any) => { runs.push({ argv, init }); return argv[2] === 'status' ? { exitCode: 0, stdout: status } : run(argv) } },
  })
  const log = async () => ({ exitCode: 0, stdout: '8\ndocs/a/a-audit-tracker.md\n\n3\ndocs/b/b-audit-tracker.md\n' })
  // b's mtime (9000) is newer than its commit (3000) but git reports it unchanged: a checkout touched it.
  const ok = mk(log)
  expect(await goalLastChange(ok, 'D:/r', ['docs/a/a-audit-tracker.md', 'docs/b/b-audit-tracker.md'])).toEqual({ 'docs/a/a-audit-tracker.md': 8000, 'docs/b/b-audit-tracker.md': 3000 })
  expect(runs.map(r => r.argv[2])).toEqual(['log', 'status'])
  expect(runs[0].argv).toEqual(['git', '--literal-pathspecs', 'log', '--format=%ct', '--name-only', '--', 'docs/a/a-audit-tracker.md', 'docs/b/b-audit-tracker.md'])
  expect(runs[0].init).toEqual({ cwd: 'D:/r', timeoutMs: 5000 })
  expect(runs[1].argv).toEqual(['git', '--literal-pathspecs', 'status', '--porcelain', '--', 'docs/a/a-audit-tracker.md', 'docs/b/b-audit-tracker.md'])
  // b really edited: git status lists it, so its newer mtime counts.
  const edited = mk(log, ' M docs/b/b-audit-tracker.md\n')
  expect(await goalLastChange(edited, 'D:/r', ['docs/b/b-audit-tracker.md'])).toEqual({ 'docs/b/b-audit-tracker.md': 9000 })
  const down = mk(async () => { throw new Error('no git') })
  expect(await goalLastChange(down, 'D:/r', ['docs/a/a-audit-tracker.md'])).toEqual({ 'docs/a/a-audit-tracker.md': 5000 })
  const bad = mk(async () => ({ exitCode: 128, stdout: '' }))
  expect(await goalLastChange(bad, 'D:/r', ['docs/a/a-audit-tracker.md'])).toEqual({ 'docs/a/a-audit-tracker.md': 5000 })
  const before = runs.length
  expect(await goalLastChange(ok, 'D:/r', [])).toEqual({})
  expect(runs.length).toBe(before) // the empty list ran no git
})

test('pruneStore drops the goal, queue and times keys of an old session', async () => {
  const day = 864e5
  const map: Record<string, unknown> = { 'hudSeen:old': NOW - 8 * day }
  for (const k of ['hudGoals', 'hudGoalPending', 'hudGoalToast', 'hudBg', 'hudQueue', 'hudTimes']) map[`${k}:old`] = []
  map['hudGoals:sid-a'] = []
  await pruneStore(fakeStore(map, 'sid-a'), NOW)
  expect(Object.keys(map).sort()).toEqual(['hudGoals:sid-a'])
})

test('one git call covers every finalized-looking bound tracker under a root', async ($, on) => {
  const a = 'docs/f/a-audit-tracker.md', b = 'docs/g/b-audit-tracker.md'
  const w = goalWorld(on, {
    [T(a)]: file(done2, NOW - 5000), [T(a + '.accept-cache')]: file('{}', NOW - 1000),
    [T(b)]: file(done2, NOW - 5000), [T(b + '.accept-cache')]: file('{}', NOW - 1000),
  }, bound(a, b), { value: `${Math.floor(NOW / 1000)}
${b}
` })
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete(doneEv as any)
  expect(w.statusRuns).toHaveLength(1) // one git status batch too
  expect(w.gitRuns).toHaveLength(1)
  expect(w.gitRuns[0].argv.slice(6)).toEqual([a, b])
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: b }]) // a finalized, b has a newer commit than its cache
})

test('a Glob tool.call does not touch the store or fs for goals', async ($, on) => {
  let storeReads = 0
  const map = new Proxy<Record<string, unknown>>({ 'hudGoals:sid-a': [{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }] }, { get: (t, k) => { if (/^hudGoal/.test(String(k))) storeReads++; return (t as any)[k] } })
  const w = goalWorld(on, g1(), map)
  toolDoes(on)
  await $.tool.call({ tool: 'Glob', pattern: '**/*.md' } as any)
  expect(storeReads).toBe(0)
  expect(w.fsCalls).toBe(0)
})

test('a step that throws inside the goal chain leaves it usable', async ($, on) => {
  const w = goalWorld(on, g1())
  w.failList = true
  await $.command.run({ command: GOAL, args: 'g1' }) // the scan throws and is swallowed
  expect(w.map['hudGoals:sid-a']).toBeUndefined()
  await $.command.run({ command: GOAL, args: 'g1' })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
})

test('PowerShell is treated like Bash: a newer tracker binds, a Move-Item to archived unbinds', async ($, on) => {
  const p = 'docs/a/a-audit-tracker.md'
  const w = goalWorld(on, { [T(p)]: file(trackerText('a'), NOW + 10) })
  toolDoes(on)
  await $.tool.call({ tool: 'PowerShell', command: `Set-Content ${p} x` } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: p }])
  await $.tool.call({ tool: 'PowerShell', command: `Move-Item ${p.replace(/\//g, String.fromCharCode(92))} docs/archived/` } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: p }]) // nothing moved yet: still bound
  delete w.files[T(p)]
  await $.tool.call({ tool: 'PowerShell', command: `Move-Item ${p} docs/archived/` } as any)
  expect(w.map['hudGoals:sid-a']).toEqual([])
})

// Text of the band mounted over a goal world.
async function bandText($: any, cols = 140) {
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: props(cols) })
  const t = (await ui.findAll({ type: 'Text' })).map((x: any) => String(x.text))
  await ui.unmount()
  return t
}
const rowsOf = (...phases: string[]) => phases.map((s, i) => `| ${i} | ASK:x | ${i === 1 ? '\x1b[31mB' : 'A' + i}${'\x1b[0m'.repeat(i === 1 ? 1 : 0)} | ${s} | -- | -- |`)

test('band shows the first bound goal and +N more; slug and title pass through clean()', async ($, on) => {
  const w = goalWorld(on, {
    [T('docs/a/g1-audit-tracker.md')]: file(trackerText('g1', rowsOf('OK Done', 'Pending', 'Pending', 'Pending'))),
    [T('docs/b/g2-audit-tracker.md')]: file(trackerText('g2')),
  })
  await $.command.run({ command: GOAL, args: 'g1' })
  await $.command.run({ command: GOAL, args: 'g2' })
  expect(w.map['hudGoalRows:sid-a']).toHaveLength(2)
  const all = await bandText($)
  expect(all).toContain('1/4') // row 1 is the first unfinished row (0-based)
  expect(all).toContain('  B') // the ESC sequences around the title are gone
  expect(all.join('')).toContain('Goal g1 ')
  expect(all).toContain('  +1 more')
  expect(all.join('')).not.toContain('\x1b')
})

test('band says Goal: none with nothing bound', async ($, on) => {
  goalWorld(on, g1())
  expect((await bandText($)).join('')).toContain('Goal: none')
})

test('band progress is re-read at turn.complete', async ($, on) => {
  const w = goalWorld(on, { [T('docs/a/g1-audit-tracker.md')]: file(trackerText('g1', rowsOf('OK Done', 'Pending'))) })
  on('turn.complete', () => ({ text: '' }))
  await $.command.run({ command: GOAL, args: 'g1' })
  expect((w.map['hudGoalRows:sid-a'] as any[])[0]).toMatchObject({ done: 1, total: 2 })
  w.files[T('docs/a/g1-audit-tracker.md')] = file(trackerText('g1', rowsOf('OK Done', 'OK Done')))
  await $.turn.complete(doneEv as any)
  expect((w.map['hudGoalRows:sid-a'] as any[])[0]).toMatchObject({ done: 2, total: 2, step: 'done' })
})

// ---- Goals pane ----
const DAY = 864e5
const rowsDone = (n: number, of: number) => Array.from({ length: of }, (_, i) => `| ${i} | ASK:x | P${i} | ${i < n ? 'OK Done' : 'Pending'} | -- | -- |`)
const PANE = { title: 'Goals', isFocused: false, bodyColumns: 80, placement: 'inline', scroll: { offset: 0, bodyRows: 12 }, view: {} } as any
// Bound g1 (1 of 4), active a2, idle i3, unreadable u4, finalized f5 (cache newer) and all-done d6 (no cache).
function paneWorld(on: any, map: Record<string, unknown> = { 'hudGoals:sid-a': [{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }] }) {
  const w = goalWorld(on, {
    [T('docs/a/g1-audit-tracker.md')]: file(trackerText('g1', rowsDone(1, 4))),
    [T('docs/b/a2-audit-tracker.md')]: file(trackerText('a2', rowsDone(2, 4))),
    [T('docs/c/i3-audit-tracker.md')]: file(trackerText('i3', rowsDone(0, 2)), NOW - 20 * DAY),
    [T('docs/d/u4-audit-tracker.md')]: file('no table here'),
    [T('docs/e/f5-audit-tracker.md')]: file(trackerText('f5', rowsDone(2, 2)), NOW - 5000),
    [T('docs/e/f5-audit-tracker.md.accept-cache')]: file('{}', NOW - 1000),
    [T('docs/f/d6-audit-tracker.md')]: file(trackerText('d6', rowsDone(1, 1))),
    [T('docs/archived/old-audit-tracker.md')]: file(trackerText('old')),
  }, map)
  const ui = { opened: [] as any[], closed: [] as any[] }
  on('ui.open', (_$: any, e: any) => { ui.opened.push(e); return { value: { isPlaced: true } } })
  on('ui.close', (_$: any, e: any) => { ui.closed.push(e); return { value: undefined } })
  return { w, ui }
}
const mountPane = ($: any) => $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'Pane', requestId: 'hud-goals', props: PANE })
const buttons = async (ui: any) => (await ui.findAll({ type: 'Button' })).map((b: any) => String(b.text))

test('Goals pane rows: bound first, [x]/[ ] labels, idle 14d+ and unreadable dim words, hidden line with [ show ]', async ($, on) => {
  const { w, ui } = paneWorld(on)
  expect((await $.command.run({ command: 'personal-hud', args: 'goals' })).text).toContain('Goals pane opened')
  expect(ui.opened).toEqual([{ id: 'hud-goals', title: 'Goals' }])
  const p = await mountPane($)
  const A = '[ archive ]'
  expect(await buttons(p)).toEqual([
    '[x] g1 1/4 25% 2026-10-08', A, '[ ] u4 -- 2026-10-08  unreadable', A, '[ ] a2 2/4 50% 2026-10-08', A, '[ ] i3 0/2 0% 2026-09-18  idle 14d+', A, '[ show ]', '[ clean up ]', '[ Close ]'])
  expect((await p.find({ type: 'Text', text: '  idle 14d+' }))?.props).toMatchObject({ dimColor: true })
  expect((await p.find({ type: 'Text', text: '  unreadable' }))?.props).toMatchObject({ dimColor: true })
  expect(await p.find({ type: 'Text', text: 'hidden: 2 finalized or done  ' })).toBeDefined()
  await p.press({ key: 'show' })
  expect(await buttons(p)).toEqual([
    '[x] g1 1/4 25% 2026-10-08', A, '[ ] u4 -- 2026-10-08  unreadable', A, '[ ] a2 2/4 50% 2026-10-08', A, '[ ] i3 0/2 0% 2026-09-18  idle 14d+', A, '[ hide ]',
    '[ ] d6 1/1 100% 2026-10-08', A, '[ ] f5 2/2 100% 2026-10-08', A, '[ clean up ]', '[ Close ]'])
  await p.press({ key: 'show' })
  expect(await buttons(p)).toContain('[ show ]')
  await p.unmount()
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
})

test('pressing a [ ] row binds it, [x] unbinds it, [ Close ] closes the pane', async ($, on) => {
  const { w, ui } = paneWorld(on)
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  await p.press({ key: 'g:'+ROOT+'/docs/b/a2-audit-tracker.md' })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }, { root: ROOT, path: 'docs/b/a2-audit-tracker.md' }])
  expect((await buttons(p))[2]).toBe('[x] a2 2/4 50% 2026-10-08') // bound rows move up, in bind order (each row is label + [ archive ])
  await p.press({ key: 'g:'+ROOT+'/docs/a/g1-audit-tracker.md' })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/b/a2-audit-tracker.md' }])
  expect((w.map['hudGoalRows:sid-a'] as any[]).map(g => g.slug)).toEqual(['a2'])
  expect((await buttons(p))[0]).toBe('[x] a2 2/4 50% 2026-10-08')
  await p.press({ key: 'close' })
  expect(ui.closed[0]).toMatchObject({ id: 'hud-goals' })
  await p.unmount()
})

test('archive asks first: [ archive ] turns into [ confirm ] [ cancel ]; cancel changes nothing', async ($, on) => {
  const { w } = paneWorld(on)
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  await p.press({ key: 'a:' + ROOT + '/docs/b/a2-audit-tracker.md' })
  const b = await buttons(p)
  expect(b.slice(4, 7)).toEqual(['[ ] a2 2/4 50% 2026-10-08', '[ confirm ]', '[ cancel ]'])
  expect(w.procRuns.some(a => a[1] === 'mv')).toBe(false) // nothing moved yet
  await p.press({ key: 'an:' + ROOT + '/docs/b/a2-audit-tracker.md' })
  expect((await buttons(p)).slice(4, 6)).toEqual(['[ ] a2 2/4 50% 2026-10-08', '[ archive ]'])
  expect(w.procRuns.some(a => a[1] === 'mv')).toBe(false)
  await p.unmount()
})

test('confirm git-mvs the tracker into <dir>/archived/, unbinds it, drops the row and toasts; nothing is committed', async ($, on) => {
  const { w } = paneWorld(on)
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  await p.press({ key: 'a:' + ROOT + '/docs/a/g1-audit-tracker.md' })
  await p.press({ key: 'ac:' + ROOT + '/docs/a/g1-audit-tracker.md' })
  expect(w.procRuns).toContainEqual(['git', 'mv', '--', 'docs/a/g1-audit-tracker.md', 'docs/a/archived/g1-audit-tracker.md'])
  expect(w.procRuns.some(a => a.join(' ').includes('mkdir') && a.join(' ').replace(/\\/g, '/').includes('docs/a/archived'))).toBe(true)
  expect(w.procRuns.some(a => a[0] === 'git' && a[1] === 'commit')).toBe(false)
  expect(w.map['hudGoals:sid-a']).toEqual([]) // it was bound; archiving unbinds it
  expect((await buttons(p)).some(t => t.includes(' g1 '))).toBe(false)
  expect(w.toasts.some(t => t.includes('archived g1') && t.includes('not committed'))).toBe(true)
  await p.unmount()
})

test('[ clean up ] confirms once, then archives only finalized goals; cancel moves nothing', async ($, on) => {
  const { w } = paneWorld(on)
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  await p.press({ key: 'clean' })
  expect(await p.find({ type: 'Text', text: 'archive 1 finalized: f5  ' })).toBeDefined()
  await p.press({ key: 'cn' })
  expect(w.procRuns.some(a => a[1] === 'mv')).toBe(false)
  await p.press({ key: 'clean' })
  await p.press({ key: 'cc' })
  expect(w.procRuns.filter(a => a[1] === 'mv')).toEqual([['git', 'mv', '--', 'docs/e/f5-audit-tracker.md', 'docs/e/archived/f5-audit-tracker.md']])
  expect(w.toasts.some(t => t.includes('clean up archived 1 of 1'))).toBe(true)
  expect(await buttons(p)).toContain('[ clean up ]')
  await p.unmount()
})

test('[ clean up ] with no finalized goal says so and moves nothing', async ($, on) => {
  const { w } = paneWorld(on)
  delete w.files[T('docs/e/f5-audit-tracker.md.accept-cache')]
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  await p.press({ key: 'clean' })
  expect(w.toasts).toContain('ping-hud: no finalized goals to clean up')
  expect(w.procRuns.some(a => a[1] === 'mv')).toBe(false)
  await p.unmount()
})

test('a failed git mv keeps the row and the binding and toasts the reason', async ($, on) => {
  const { w } = paneWorld(on)
  w.mvFail = true
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  await p.press({ key: 'a:' + ROOT + '/docs/a/g1-audit-tracker.md' })
  await p.press({ key: 'ac:' + ROOT + '/docs/a/g1-audit-tracker.md' })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
  expect((await buttons(p))[0]).toBe('[x] g1 1/4 25% 2026-10-08')
  expect(w.toasts.some(t => t.includes('could not archive g1') && t.includes('not under version control'))).toBe(true)
  await p.unmount()
})

test('archiveTracker refuses a path outside the tracker rule and runs nothing', async ($, on) => {
  const { w } = paneWorld(on)
  for (const bad of ['../x-audit-tracker.md', 'docs/a/archived/g1-audit-tracker.md', 'docs/a/notes.md', 'D:/abs/g-audit-tracker.md']) {
    const r = await archiveTracker($, ROOT, bad)
    expect(r.ok).toBe(false)
  }
  // cmd.exe re-parses mkdir's argument: a folder name with & | ^ < > % " ! or a space must never reach it.
  for (const [root, rel] of [['D:/evil&calc', 'docs/a/g1-audit-tracker.md'], [ROOT, 'docs/a&calc/g1-audit-tracker.md'],
    [ROOT, 'docs/a|b/g1-audit-tracker.md'], ['C:/Users/John Doe/repo', 'docs/a/g1-audit-tracker.md'], [ROOT, 'docs/a%PATH%/g1-audit-tracker.md']]) {
    const r = await archiveTracker($, root, rel)
    expect(r.ok).toBe(false)
    expect(r.text).toContain('unsafe')
  }
  expect(w.procRuns.some(a => a[1] === 'mv' || a.join(' ').includes('mkdir'))).toBe(false)
})

test('[ clean up ] archives when the session cwd uses Windows backslashes', async ($, on) => {
  // paneWorld answers session.cwd with ROOT; skip that one so the cwd can come back the way Windows reports it.
  const { w } = paneWorld((ev: string, ...r: any[]) => ev === 'session.cwd' ? undefined : on(ev, ...r))
  on('session.cwd', () => ({ value: ROOT.split('/').join('\\') }))
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  await p.press({ key: 'clean' })
  await p.press({ key: 'cc' })
  expect(w.toasts.some(t => t.includes('unsafe'))).toBe(false)
  expect(w.toasts.some(t => t.includes('clean up archived 1 of 1'))).toBe(true)
  await p.unmount()
})

test('the full docs scan runs only when the pane opens, never on turn.complete', async ($, on) => {
  const { w } = paneWorld(on)
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete(doneEv as any)
  await $.turn.complete(doneEv as any)
  expect(w.goalLists).toBe(0)
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  expect(w.goalLists).toBe(1)
  expect(w.gitRuns).toHaveLength(1) // one git batch for every scanned tracker
  expect(w.gitRuns[0].argv.slice(6)).toHaveLength(6) // archived is skipped
})

test('opening the pane unbinds a bound tracker that moved away', async ($, on) => {
  const { w } = paneWorld(on, { 'hudGoals:sid-a': [{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }, { root: ROOT, path: 'docs/z/gone-audit-tracker.md' }] })
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
  expect(w.toasts).toEqual(['goal gone cleared: tracker moved, removed or finalized'])
})

test('a bound tracker under another root has an [x] row in the pane and can be unbound there', async ($, on) => {
  const R2 = 'D:/other', rel = 'docs/x/z-audit-tracker.md'
  const { w } = paneWorld(on, { 'hudGoals:sid-a': [{ root: R2, path: rel }, { root: ROOT, path: 'docs/a/g1-audit-tracker.md' }] })
  w.files[`${R2}/${rel}`] = file(trackerText('z', rowsDone(3, 4)))
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  const p = await mountPane($)
  expect((await buttons(p)).slice(0, 4)).toEqual(['[x] z 3/4 75% 2026-10-08', '[ archive ]', '[x] g1 1/4 25% 2026-10-08', '[ archive ]'])
  await p.press({ key: `g:${R2}/${rel}` })
  expect(w.map['hudGoals:sid-a']).toEqual([{ root: ROOT, path: 'docs/a/g1-audit-tracker.md' }])
  await p.unmount()
})

test('band shows Goal <slug> unreadable (dim) for a bound tracker with no phase table', async ($, on) => {
  goalWorld(on, { [T('docs/a/bad-audit-tracker.md')]: file('no table here') }, { 'hudGoals:sid-a': [{ root: ROOT, path: 'docs/a/bad-audit-tracker.md' }] })
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete(doneEv as any)
  const all = await bandText($)
  expect(all.join('')).toContain('Goal bad unreadable')
  expect(all.join('')).not.toContain('Goal: none')
})

test('Close deletes hudPane; the pane stores parsed rows, not tracker text', async ($, on) => {
  const { w } = paneWorld(on)
  await $.command.run({ command: 'personal-hud', args: 'goals' })
  expect(JSON.stringify(w.map['hudPane:sid-a'])).not.toContain('Phase Status')
  const p = await mountPane($)
  await p.press({ key: 'close' })
  expect('hudPane:sid-a' in w.map).toBe(false)
  await p.unmount()
})

test('openGoals answers text instead of rejecting when $ is broken', async () => {
  expect((await openGoals({} as any)).text).toMatch(/^ping-hud:/)
})

const Q = (label: string, n: number) => ({ question: `${label}?`, header: label, multiSelect: false, options: Array.from({ length: n }, (_, i) => ({ label: `${label} opt ${i + 1}`, description: `d${i + 1}` })) })

test('withExplainOption appends the option once to the first question and never mutates input', () => {
  const input = [Q('A', 2), Q('B', 3)]
  const once = withExplainOption(input)
  expect(once[0].options.map((o: any) => o.label)).toEqual(['A opt 1', 'A opt 2', EXPLAIN_FIRST])
  expect(once[1]).toBe(input[1])
  expect(input[0].options.length).toBe(2)
  expect(withExplainOption(once)).toBe(once) // re-render of a rewritten list adds nothing
})

test('withExplainOption skips a first question already at 4 options, and an empty list', () => {
  const full = [Q('A', 4)]
  expect(withExplainOption(full)).toBe(full)
  expect(withExplainOption([])).toEqual([])
})

test('AskUserQuestion tool.call hook: the call gets the explain option once, original options kept', async () => {
  const handlers: any[] = []
  // Fake registrar: records the AskUserQuestion handler; every other call returns a chainable stub.
  const stub: any = new Proxy(function () {}, { apply: () => stub, get: (_t, k) => (k === 'then' ? undefined : stub) })
  register(((event: string, match: any, fn: any) => { if (event === 'tool.call' && match?.tool === 'AskUserQuestion') handlers.push(fn); return stub }) as any)
  expect(handlers.length).toBe(1)
  const e = { tool: 'AskUserQuestion', tool_use_id: 't1', questions: [Q('A', 2), Q('B', 2)] }
  const pass = async (x: any) => x
  const once: any = await handlers[0]({}, e, pass)
  const again: any = await handlers[0]({}, once, pass) // a retried call of the rewritten input
  expect(once.questions[0].options.map((o: any) => o.label)).toEqual(['A opt 1', 'A opt 2', EXPLAIN_FIRST])
  expect(again.questions[0].options.length).toBe(3)
  expect(once.questions[1]).toBe(e.questions[1])
  expect(once.tool_use_id).toBe('t1')
  expect(e.questions[0].options.length).toBe(2)
})

test('no ui.render hook rewrites the AskUserQuestion form any more', () => {
  const seen: string[] = []
  const stub: any = new Proxy(function () {}, { apply: () => stub, get: (_t, k) => (k === 'then' ? undefined : stub) })
  register(((event: string, match: any) => { if (event === 'ui.render') seen.push(String(match?.component)); return stub }) as any)
  expect(seen).not.toContain('AskUserQuestion')
})

test('Agents pane: spawn, tool calls and finish feed the rows; /personal-hud agents opens it; [ clear done ] drops finished', async ($, on) => {
  const map: Record<string, unknown> = {}
  memStore(on, map)
  mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  on('session.cwd', () => ({ value: 'D:/work/demo-repo' }))
  const opened: any[] = []
  on('ui.open', (_$: any, e: any) => { opened.push(e); return { value: { isPlaced: true } } })
  on('ui.close', () => ({ value: undefined }))
  let n = 0
  on('agent.spawn', () => ({ agentId: ['a1', 'w1'][n++], model: 'm' }) as any)
  on('tool.call', () => ({ result: { text: 'ok' } }) as any)
  on('turn.complete', () => ({ text: '' }))
  await $.agent.spawn({ ...spawnInput, description: 'Test agent A', tool_use_id: 'fg', background: false } as any)
  await $.agent.spawn({ ...spawnInput, description: 'list-1', tool_use_id: 'wf', background: true, workflow: { runId: 'wf_9', agentIndex: 1 } } as any)
  await $.tool.call({ tool: 'Glob', pattern: '*.ts', agentId: 'a1' } as any)
  await $.tool.call({ tool: 'Read', file_path: 'D:/x/hud-goals.ts', agentId: 'w1' } as any)
  await $.turn.complete({ ...done, agentId: 'a1' } as any)
  const rows = map['hudAgents:sid-a'] as any[]
  expect(rows.map(r => [r.id, r.tools, r.last, r.endMs !== undefined])).toEqual([['a1', 1, 'Glob (*.ts)', true], ['w1', 1, 'Read (hud-goals.ts)', false]])
  expect((await $.command.run({ command: 'personal-hud', args: 'agents' })).text).toContain('Agents pane opened')
  expect(opened).toEqual([{ id: 'hud-agents', title: 'Agents' }])
  const p = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'Pane', requestId: 'hud-agents', props: PANE })
  expect(await p.find({ type: 'Text', text: '1 running, 1 done' })).toBeDefined()
  expect(await p.find({ type: 'Text', text: 'Workflow wf_9' })).toBeDefined()
  expect(await p.find({ type: 'Text', text: '  done     general-purpose  Test agent A  -  finished  -  1 tool  0:00' })).toBeDefined()
  expect(await p.find({ type: 'Text', text: '  running  workflow agent 1  list-1  -  Read (hud-goals.ts)  -  1 tool  0:00' })).toBeDefined()
  await p.press({ key: 'aclear' })
  expect((map['hudAgents:sid-a'] as any[]).map(r => r.id)).toEqual(['w1'])
  await p.unmount()
})

// Agents world: memory store, a movable clock, ui.open/close recorded, an engine that starts agents a1, a2, ...
function agentsWorld(on: any, map: Record<string, unknown> = {}) {
  memStore(on, map)
  const clk = mock.clock(on, { now: NOW })
  on('session.id', () => ({ value: 'sid-a' }))
  on('session.cwd', () => ({ value: 'D:/work/demo-repo' }))
  const opened: any[] = []
  on('ui.open', (_$: any, e: any) => { opened.push(e); return { value: { isPlaced: true } } })
  on('ui.close', () => ({ value: undefined }))
  on('tool.call', () => ({ result: { text: 'ok' } }) as any)
  on('turn.complete', () => ({ text: '' }))
  return { map, clk, opened, rows: () => (map['hudAgents:sid-a'] as any[]) ?? [] }
}

test('Agents: a refused spawn adds no row and no band count', async ($, on) => {
  const w = agentsWorld(on)
  on('agent.spawn', () => ({ deny: 'blocked by policy' }) as any)
  await $.agent.spawn({ ...spawnInput, tool_use_id: 'bg', background: true } as any)
  expect(w.rows()).toEqual([])
  expect(w.map['hudBg:sid-a']).toBeUndefined()
})

test('Agents: a main-session tool call leaves the rows alone; the main turn end closes a foreground row only', async ($, on) => {
  const w = agentsWorld(on)
  let n = 0
  on('agent.spawn', () => ({ agentId: ['f1', 'b1'][n++], model: 'm' }) as any)
  await $.agent.spawn({ ...spawnInput, description: 'fg', tool_use_id: 'fg', background: false } as any)
  await $.agent.spawn({ ...spawnInput, description: 'bg', tool_use_id: 'bg', background: true } as any)
  await $.tool.call({ tool: 'Bash', command: 'ls' } as any)
  expect(w.rows().map(r => [r.id, r.tools])).toEqual([['f1', 0], ['b1', 0]])
  await $.turn.complete({ ...done } as any)
  expect(w.rows().map(r => [r.id, r.outcome ?? 'running'])).toEqual([['f1', 'stopped'], ['b1', 'running']])
})

test('Agents: a reload (session.start) keeps the rows of agents that are still running', async ($, on) => {
  const row = { id: 'b1', type: 'general-purpose', desc: 'bg', bg: true, tracked: true, startMs: NOW, lastMs: NOW, tools: 2, last: 'Read (x.ts)' }
  const w = agentsWorld(on, { 'hudAgents:sid-a': [row] })
  on('command.register', () => ({ value: undefined }))
  await $.session.start({} as any).catch(() => undefined)
  expect(w.rows().map(r => r.id)).toEqual(['b1'])
})

test('Agents: an interrupted agent shows stopped, and the elapsed time moves while the pane is open', async ($, on) => {
  const w = agentsWorld(on)
  on('agent.spawn', () => ({ agentId: 'b1', model: 'm' }) as any)
  await $.agent.spawn({ ...spawnInput, description: 'slow job', tool_use_id: 'bg', background: true } as any)
  await $.command.run({ command: 'personal-hud', args: 'agents' })
  const p = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'Pane', requestId: 'hud-agents', props: PANE })
  expect(await p.find({ type: 'Text', text: '  running  general-purpose  slow job  -  starting  -  0 tools  0:00' })).toBeDefined()
  await w.clk.advance(5000)
  expect(await p.find({ type: 'Text', text: '  running  general-purpose  slow job  -  starting  -  0 tools  0:05' })).toBeDefined()
  await $.turn.complete({ ...done, agentId: 'b1', reason: 'aborted', isAborted: true } as any)
  expect(w.rows()[0].outcome).toBe('stopped')
  await p.unmount()
})

import { test, expect, mock } from 'claude-code/testing'
import { cutSections, parsePath, sliceLines, startTopic, park, reopen, clearAll, addAnswer, buildPrompt, costOf, costLine, shouldLock, questionText, emptyData, filmUrl, motionPrompt, finishMotion, motionSubject, motionAsk, motionAskSubject, motionDispatch, EARLIER_MAX, QUICK_TIP, PANE_ID, SCROLL_HINT, paneScrollText } from './hud-explain'
import { EXPLAIN_FIRST, EXPLAIN_FIRST_CONTEXT, FILM_AGENT, FILM_AGENT_SPEC } from './register'

const NOW = Date.parse('2026-10-11T22:00:00Z')
const SKILL = '# htsw\n\n## Explaining sentences -- humanized\nRULE-A say who does what\n\n## Language switch -- --cantonese\nRULE-B spoken Cantonese\n\n## Other\nNOT-SENT'

// ---- pure logic ----

test('cutSections keeps only the named sections, each up to the next ## heading', () => {
  const out = cutSections(SKILL, ['Explaining sentences', 'Language switch'])
  expect(out).toContain('RULE-A')
  expect(out).toContain('RULE-B')
  expect(out).not.toContain('NOT-SENT')
  expect(cutSections(SKILL, ['Missing'])).toBe('')
})

test('parsePath: a file with an extension, optional line range; plain text is not a path', () => {
  expect(parsePath('docs/next-enchance/plan-v2.md')).toEqual({ path: 'docs/next-enchance/plan-v2.md', from: undefined, to: undefined })
  expect(parsePath('hooks/register.tsx:735-750')).toEqual({ path: 'hooks/register.tsx', from: 735, to: 750 })
  expect(parsePath('a.ts:12')).toEqual({ path: 'a.ts', from: 12, to: 12 })
  expect(parsePath('why is the spike first?')).toBeUndefined()
  expect(sliceLines('a\nb\nc\nd', 2, 3)).toBe('b\nc')
  expect(sliceLines('a\nb', undefined, undefined)).toBe('a\nb')
})

test('topics: a new topic parks an answered one in Earlier (newest first, at most 5); reopen swaps; clearAll empties', () => {
  let d = emptyData()
  d = startTopic(d, 'explain', 'first', 'en', 'quick')
  d = startTopic(d, 'kid', 'second', 'en', 'quick') // first had no answer: not kept
  expect(d.earlier).toEqual([])
  for (let i = 0; i < 7; i++) { d = addAnswer(d, 'q', 'a'); d = startTopic(d, 'simple', `t${i}`, 'en', 'quick') }
  expect(d.earlier.length).toBe(EARLIER_MAX)
  expect(d.earlier[0].subject).toBe('t5')
  d = addAnswer(d, 'q', 'a')
  const back = reopen(d, d.earlier[2].id)
  expect(back.topic!.subject).toBe('t3')
  expect(back.earlier[0].subject).toBe('t6') // the current one moved to Earlier
  expect(park(back).topic).toBeUndefined()
  expect(clearAll(back)).toMatchObject({ topic: undefined, earlier: [] })
})

test('buildPrompt quick: rules head from SKILL.md + mode file; body has the last question and reply, the subject and the language', () => {
  const { head, body } = buildPrompt({ mode: 'explain', lang: 'yue', scope: 'quick', subject: 'my last reply', skill: SKILL, ref: 'WALK-REF', ctx: { ask: 'ASK-1', reply: 'REPLY-1' }, qa: [] })
  expect(head).toContain('RULE-A')
  expect(head).toContain('WALK-REF')
  expect(head).not.toContain('NOT-SENT')
  expect(body).toContain('ASK-1')
  expect(body).toContain('REPLY-1')
  expect(body).toContain('--cantonese')
  expect(body).toContain('walk mode')
})

test('buildPrompt whole chat sends no copied reply; a follow-up carries the topic history; a question form and a file are included', () => {
  const p = buildPrompt({ mode: 'simple', lang: 'en', scope: 'chat', subject: 's', skill: SKILL, ref: 'R', ctx: { reply: 'REPLY-1' }, qa: [{ q: 'Q0', a: 'A0' }], follow: 'FOLLOW-1', question: 'QUESTION-1', file: { path: 'x.md', text: 'FILE-1' } })
  expect(p.body).not.toContain('REPLY-1')
  expect(p.body).toContain('Q: Q0\nA: A0')
  expect(p.body).toContain('Follow-up question: FOLLOW-1')
  expect(p.body).toContain('QUESTION-1')
  expect(p.body).toContain('FILE-1')
  expect(p.body).toContain('Language: English.')
})

test('cost line: new = uncached + cache writes, cached = cache reads', () => {
  const c = costOf({ input_tokens: 2000, cache_creation_input_tokens: 4000, cache_read_input_tokens: 250000, output_tokens: 900 }, 12300)
  expect(c).toEqual({ newTokens: 6000, cachedTokens: 250000, outTokens: 900, ms: 12300 })
  expect(costLine(c)).toBe('Last press: 6K new + 250K cached tokens in, 900 out, 12.3 s')
})

test('focus lock: only while the box has focus and text, and only for the person moving it out', () => {
  expect(shouldLock('xbox0', 'hi', 'person', 'xmexplain')).toBe(true)
  expect(shouldLock('xbox0', 'hi', 'person', undefined)).toBe(true) // an engine stop (close mark) is out too
  expect(shouldLock('xbox0', '  ', 'person', 'xmexplain')).toBe(false) // empty box: arrows move as usual
  expect(shouldLock('xmkid', 'hi', 'person', 'xmexplain')).toBe(false)
  expect(shouldLock('xbox0', 'hi', 'plugin', 'xmexplain')).toBe(false)
  expect(shouldLock('xbox0', 'hi', 'person', 'xbox1')).toBe(false)
})

test('filmUrl: the FILM line wins; only https claude.ai artifact links count', () => {
  expect(filmUrl('done\nFILM: https://claude.ai/artifact/abc123XYZ')).toBe('https://claude.ai/artifact/abc123XYZ')
  expect(filmUrl('see https://claude.ai/code/artifact/u-1 there')).toBe('https://claude.ai/code/artifact/u-1')
  expect(filmUrl('FILM: https://evil.example/artifact/x')).toBeUndefined()
  expect(filmUrl('NO FILM: no Motion type')).toBeUndefined()
})

test('motionPrompt: loads the tools, decides alone, carries the htsw rules, the context and the FILM line', () => {
  const s = motionPrompt({ lang: 'yue', subject: 'my last reply', skill: SKILL, ctx: { ask: 'ASK-1', reply: 'REPLY-1' }, file: { path: 'x.md', text: 'FILE-1' } })
  for (const x of ['select:Artifact,ArtifactData', 'ask nothing', '30 seconds', 'RULE-A', '--cantonese', 'ASK-1', 'REPLY-1', 'FILE-1', 'FILM: ']) expect(s).toContain(x)
  expect(s).not.toContain('NOT-SENT')
})

test('finishMotion: the link lands in its topic even after New topic; a failure carries the reason', () => {
  let d = startTopic(emptyData(), 'motion', 'the plan', 'en', 'quick')
  d = { ...d, motion: { agentId: 'a1', topicId: d.topic!.id, startMs: 0 } }
  d = park(d) // a pending film's topic is kept in Earlier, though it has no answer yet
  expect(d.earlier.length).toBe(1)
  const ok = finishMotion(d, 'FILM: https://claude.ai/artifact/F1')
  expect(ok.motion).toBeUndefined()
  expect(ok.earlier[0].film).toBe('https://claude.ai/artifact/F1')
  const bad = finishMotion(d, 'NO FILM: Motion type not listed')
  expect(bad.earlier[0].qa[0].a).toContain('Motion type not listed')
  expect(finishMotion(clearAll(d), 'FILM: https://claude.ai/artifact/F1').note).toContain('https://claude.ai/artifact/F1') // topic gone: the link still shows
})

test('questionText lists each question with its options', () => {
  expect(questionText([{ question: 'Which?', options: [{ label: 'A', description: 'da' }, { label: 'B', description: 'db' }] }])).toBe('Which?\n- A: da\n- B: db')
  expect(questionText(undefined)).toBe('')
})

// ---- the pane, through the real hooks ----

// Explanation world: store, clock, session, files (SKILL.md and the mode files), model calls and pane opens are faked.
function xw(on: any, store: Record<string, unknown> = {}, complete?: (w: any, e: any) => any, cwd = 'D:/x') {
  const w = { complete: [] as any[], fork: [] as any[], opened: [] as any[], runs: [] as any[][], toasts: [] as string[], writes: {} as Record<string, string>, skill: SKILL, answer: 'ANSWER-1' }
  on('ui.toast', (_$: any, e: any) => { w.toasts.push(e.text); return { value: undefined } })
  // A writable store, so a test can read what the hooks saved.
  on('store.get', (_$: any, e: any) => ({ value: store[e.key] }))
  on('store.set', (_$: any, e: any) => { store[e.key] = e.value; return { value: undefined } })
  on('store.delete', (_$: any, e: any) => { delete store[e.key]; return { value: undefined } })
  on('store.keys', () => ({ value: Object.keys(store) }))
  mock.clock(on, { now: NOW })
  on('session.cwd', () => ({ value: cwd }))
  on('session.id', () => ({ value: 'sid-a' }))
  on('ui.open', (_$: any, e: any) => { w.opened.push(e); return { value: { isPlaced: true } } })
  on('fs.read', (_$: any, e: any) => ({ value: String(e.path).endsWith('plugin.json') ? '{ "version": "9.8.7" }' : String(e.path).endsWith('SKILL.md') ? w.skill : String(e.path).endsWith('.md') && String(e.path).includes('references') ? `REF ${e.path}` : `FILE ${e.path}` }))
  on('fs.write', (_$: any, e: any) => { w.writes[e.path] = e.text; return { value: undefined } })
  on('fs.exists', () => ({ value: false }))
  on('process.run', (_$: any, e: any) => { w.runs.push(e.argv); return { value: { exitCode: 0, stdout: '', stderr: '' } } })
  on('model.complete', (_$: any, e: any) => { w.complete.push(e); return complete ? Promise.resolve(complete(w, e)).then(value => ({ value })) : { value: { isAnswered: true, text: w.answer, usage: { input_tokens: 3000, cache_read_input_tokens: 5000, output_tokens: 700 } } } })
  on('model.fork', (_$: any, e: any) => { w.fork.push(e); return { value: { isAnswered: true, text: 'FORK-ANSWER', usage: { input_tokens: 6000, cache_read_input_tokens: 250000, output_tokens: 900 } } } })
  return w
}
const mountX = ($: any) => $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'Pane', requestId: PANE_ID, props: { viewport: { rows: 40, columns: 120 } } as any })
// Hooks see the joined prompt text plus the caller's blocks (promptBlocks), where the cache marks are.
const headOf = (call: any) => String(call.promptBlocks[0].text)
const bodyOf = (call: any) => String(call.promptBlocks[1].text)

test('a level press answers in the pane through a quick Sonnet call with the last reply; nothing runs in the main chat', async ($, on) => {
  const w = xw(on, { 'hudExplainCtx:sid-a': { ask: 'ASK-1', reply: 'REPLY-1' } })
  expect((await $.command.run({ command: 'personal-hud', args: 'explain' })).text).toContain('Explanation pane opened')
  const p = await mountX($)
  expect(await p.find({ type: 'Text', text: QUICK_TIP })).toBeDefined() // Quick is the default and says so
  await p.press({ key: 'xmexplain' })
  expect(w.complete.length).toBe(1)
  expect(w.fork.length).toBe(0)
  expect(w.complete[0].model).toBe('sonnet')
  expect(w.complete[0].promptBlocks[0].cache).toBe(true) // the rules block is cached across presses
  expect(w.complete[0].promptBlocks[1].cache).toBeFalsy()
  expect(bodyOf(w.complete[0])).toContain('REPLY-1')
  expect(await p.find({ type: 'Markdown', text: 'ANSWER-1' } as any)).toBeDefined()
  expect(await p.find({ type: 'Text', text: 'Last press: 3K new + 5K cached tokens in, 700 out, 0.0 s' })).toBeDefined()
  await p.unmount()
})

test('drift guard: every press reads the htsw rules from SKILL.md at click time, never a copy', async ($, on) => {
  const w = xw(on)
  const p = await mountX($)
  await p.press({ key: 'xmsimple' })
  expect(headOf(w.complete[0])).toContain('RULE-A')
  w.skill = SKILL.replace('RULE-A', 'RULE-A2')
  await p.press({ key: 'xmkid' })
  expect(headOf(w.complete[1])).toContain('RULE-A2')
  expect(headOf(w.complete[1])).toContain('references/baby.md')
  await p.unmount()
})

test('Cantonese and Whole chat switches: the language line changes, and Whole chat forks the main session', async ($, on) => {
  const w = xw(on)
  const p = await mountX($)
  await p.press({ key: 'xlang' })
  await p.press({ key: 'xscope' })
  await p.press({ key: 'xmexplain' })
  expect(w.complete.length).toBe(0)
  expect(String(w.fork[0].prompt)).toContain('--cantonese')
  expect(await p.find({ type: 'Markdown', text: 'FORK-ANSWER' } as any)).toBeDefined()
  await p.unmount()
})

test('Enter after an answer is a follow-up carrying the topic history; a typed path is read and sent', async ($, on) => {
  const w = xw(on)
  const p = await mountX($)
  await p.input({ key: 'xbox0', text: 'docs/plan.md', kind: 'change' } as any)
  await p.press({ key: 'xmexplain' })
  expect(bodyOf(w.complete[0]).replace(/\\/g, '/')).toContain('FILE D:/x/docs/plan.md') // read from the repo root, not the process folder
  await p.input({ key: 'xbox1', text: 'why?', kind: 'submit' } as any)
  expect(bodyOf(w.complete[1])).toContain('Follow-up question: why?')
  expect(bodyOf(w.complete[1])).toContain('A: ANSWER-1')
  await p.unmount()
})

test('Clear text draws a fresh empty box (new key); New topic parks the answered topic in Earlier', async ($, on) => {
  const w = xw(on)
  const p = await mountX($)
  await p.press({ key: 'xmsimple' })
  await p.press({ key: 'xclear' })
  expect(await p.find({ key: 'xbox2' })).toBeDefined() // 1 after the level press, 2 after Clear text
  await p.press({ key: 'xnew' })
  expect(await p.find({ type: 'Text', text: 'Topic: none yet' })).toBeDefined()
  expect(await p.find({ key: `xr1` })).toBeDefined()
  expect(w.complete.length).toBe(1)
  await p.unmount()
})

test('Deep HTML is one press: one side call, then the page is saved and rendered, with Open in browser', async ($, on) => {
  const w = xw(on)
  const p = await mountX($)
  await p.press({ key: 'xmdeep' })
  expect(w.complete.length).toBe(1)
  const md = Object.keys(w.writes).find(k => k.endsWith('-deep.md'))!
  expect(md.replace(/\\/g, '/')).toContain('docs/explain/2026-10-11-1800-deep.md') // the engine hands paths over in the OS shape
  expect(w.writes[md]).toBe('ANSWER-1')
  expect(w.runs.some(a => a[0] === 'python' && String(a[1]).endsWith('md-to-html.py') && a.includes('--out'))).toBe(true)
  // Open in browser sits in the control row with New topic, not under the long answer.
  expect(JSON.stringify(await p.find({ key: 'xc' } as any))).toContain('xopen')
  await p.press({ key: 'xopen' })
  expect(w.runs.some(a => a[0] === 'cmd' && a[2] === 'start')).toBe(true)
  await p.unmount()
})

test('Open in browser and the Page link work when the repo path has a space', async ($, on) => {
  const w = xw(on, {}, undefined, 'D:/work/My Repo/app')
  const p = await mountX($)
  await p.press({ key: 'xmdeep' })
  const url = 'file:///D:/work/My%20Repo/app/docs/explain/2026-10-11-1800-deep.html'
  expect(JSON.stringify(await p.find({ key: 'xp' } as any))).toContain(url)
  await p.press({ key: 'xopen' })
  expect(w.toasts).toEqual([])
  expect(w.runs.some(a => a[0] === 'cmd' && a[2] === 'start' && a[4] === url)).toBe(true)
  await p.unmount()
})

test('Open in browser still refuses a path with a cmd.exe character such as &', async ($, on) => {
  const w = xw(on, {}, undefined, 'D:/work/R&D/app')
  const p = await mountX($)
  await p.press({ key: 'xmdeep' })
  await p.press({ key: 'xopen' })
  expect(w.toasts.some(t => t.includes('unusual characters'))).toBe(true)
  expect(w.runs.some(a => a[0] === 'cmd')).toBe(false)
  await p.unmount()
})

test('the control row shows the plugin version read from the manifest', async ($, on) => {
  xw(on)
  const p = await mountX($)
  expect(JSON.stringify(await p.find({ key: 'xc' } as any))).toContain('v9.8.7')
  await p.unmount()
})

test('busy lock: a second press while one runs makes no second call', async ($, on) => {
  let release: () => void = () => {}
  const w = xw(on, {}, async () => { await new Promise<void>(r => { release = r }); return { isAnswered: true, text: 'late', usage: {} } })
  const p = await mountX($)
  const first = p.press({ key: 'xmsimple' })
  await new Promise(r => setTimeout(r, 20))
  await p.press({ key: 'xmkid' })
  expect(w.complete.length).toBe(1)
  expect(await p.find({ key: 'xstop' })).toBeDefined()
  await p.press({ key: 'xstop' })
  release(); await first
  expect(await p.find({ type: 'Markdown', text: 'late' } as any)).toBeUndefined() // the stopped answer is thrown away
  await p.unmount()
})

test('band HTSW level opens the pane and explains the last reply at once', async ($, on) => {
  const w = xw(on, { 'hudCmds:sid-a': [], 'hudExplainCtx:sid-a': { reply: 'REPLY-2' } })
  on('ui.render', { component: 'AbovePrompt' }, ($: any, e: any) => { const { Box } = $.ui.resolve(e); return <Box key="engine" /> })
  const band = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: { hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 120, scroll: { offset: 0, bodyRows: 12 }, view: {} } as any })
  await band.press({ key: 'btnkid' })
  expect(w.opened).toContainEqual({ id: PANE_ID, title: 'Explanation' })
  expect(bodyOf(w.complete[0])).toContain('REPLY-2')
  expect(bodyOf(w.complete[0])).toContain('baby mode')
  await band.unmount()
})

test('turn hooks keep the last main question and reply for quick mode; a subagent turn is ignored', async ($, on) => {
  const map: Record<string, unknown> = {}
  xw(on, map)
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ answer: 'MAIN-REPLY', durationMs: 1, isAborted: false, turnId: 't1', reason: 'end_turn' } as any)
  await $.turn.complete({ answer: 'SUB-REPLY', durationMs: 1, isAborted: false, turnId: 't2', reason: 'end_turn', agentId: 'a1' } as any)
  expect((map['hudExplainCtx:sid-a'] as any).reply).toBe('MAIN-REPLY')
})

test('picking "Explain these questions first" explains them in the pane and tells the model to ask again', async ($, on) => {
  const w = xw(on)
  on('tool.call', () => ({ result: { answers: { q: EXPLAIN_FIRST } }, text: `User answered: ${EXPLAIN_FIRST}` }) as any)
  const r: any = await $.tool.call({ tool: 'AskUserQuestion', questions: [{ question: 'Which way?', header: 'h', multiSelect: false, options: [{ label: 'A', description: 'da' }, { label: 'B', description: 'db' }] }] } as any)
  expect(r.context).toContain(EXPLAIN_FIRST_CONTEXT)
  await new Promise(res => setTimeout(res, 20))
  expect(w.opened).toContainEqual({ id: PANE_ID, title: 'Explanation' })
  expect(bodyOf(w.complete[0])).toContain('Which way?')
})

test('a film subagent report brings the link into its topic, Open film opens it; one film at a time', async ($, on) => {
  const topic = { id: 1, mode: 'motion', subject: 'my last reply', lang: 'en', scope: 'quick', qa: [] }
  const st: Record<string, unknown> = { 'hudExplain:sid-a': { ...emptyData(), next: 2, topic, motion: { agentId: 'film-1', topicId: 1, startMs: 0 } } }
  const w = xw(on, st)
  const spawns: any[] = []
  on('agent.spawn', (_$: any, e: any) => { spawns.push(e); return { model: 'sonnet' } as any })
  on('turn.complete', () => ({ text: '' }))
  const p = await mountX($)
  await p.press({ key: 'xmmotion' })
  expect(spawns.length).toBe(0) // a film is still being made
  await $.turn.complete({ answer: 'Made it.\nFILM: https://claude.ai/artifact/Film123', durationMs: 1, isAborted: false, turnId: 't9', reason: 'end_turn', agentId: 'film-1' } as any)
  expect((st['hudExplain:sid-a'] as any).motion).toBeUndefined()
  expect(await p.find({ key: 'xfopen' })).toBeDefined()
  await p.press({ key: 'xfopen' })
  expect(w.runs.some(a => a[0] === 'cmd' && a[2] === 'start' && a[4] === 'https://claude.ai/artifact/Film123')).toBe(true)
  await p.unmount()
})

test('Open film launches only a claude.ai artifact link; any other link is refused before the browser', async ($, on) => {
  const topic = { id: 1, mode: 'motion', subject: 's', lang: 'en', scope: 'quick', qa: [{ q: 'q', a: 'a' }], film: 'https://claude.ai/settings/billing' }
  const w = xw(on, { 'hudExplain:sid-a': { ...emptyData(), next: 2, topic } })
  const p = await mountX($)
  await p.press({ key: 'xfopen' })
  expect(w.runs.some(a => a[0] === 'cmd')).toBe(false)
  await p.unmount()
})

test('a /personal-hud failure answers with its reason instead of falling through', async ($, on) => {
  on('store.set', () => { throw new Error('DISK-FULL') }) // the glyphs switch writes the store without a guard
  const r: any = await $.command.run({ command: 'personal-hud', args: 'glyphs ascii' })
  expect(String(r.text)).toContain('/personal-hud glyphs ascii failed')
  expect(String(r.text)).toContain('failed (throw')
})

// ---- Motion (DEC-8): a plain request the main model reads, so auto mode sees it was asked for ----

// Prompt box fakes: the box is empty unless a test says otherwise; every fill is recorded.
function boxW(on: any, draft = '') {
  const fills: any[] = []
  on('prompt.read', () => ({ value: { text: draft, cursor: draft.length } }) as any)
  on('prompt.fill', (_$: any, e: any) => { fills.push(e); return { isFilled: true } as any })
  return fills
}
const bandProps = { hasSurvey: false, isWorking: false, maxRows: 12, bodyColumns: 120, scroll: { offset: 0, bodyRows: 12 }, view: {} } as any

test('motionAsk / motionAskSubject / motionDispatch: the request round-trips; other prompts are not Motion', () => {
  expect(motionAsk('')).toBe('ping-hud Motion: make a 30-second film explaining my last reply')
  expect(motionAskSubject(motionAsk('docs/Plan.md'))).toBe('docs/Plan.md') // case kept
  expect(motionAskSubject('ping-hud Motion: the retry loop')).toBe('the retry loop')
  expect(motionAskSubject('please make a film')).toBeUndefined()
  expect(motionSubject('motion docs/Plan.md')).toBe('docs/Plan.md')
  const d = motionDispatch(FILM_AGENT)
  for (const x of [FILM_AGENT, 'run_in_background true', 'Do not explain the subject yourself']) expect(d).toContain(x)
})

test('pane Motion press fills the plain request into an empty prompt box and starts nothing itself', async ($, on) => {
  const w = xw(on)
  const fills = boxW(on)
  const spawns: any[] = []
  on('agent.spawn', (_$: any, e: any) => { spawns.push(e); return { model: 'sonnet' } as any })
  const p = await mountX($)
  await p.press({ key: 'xmmotion' })
  expect(fills[0]).toMatchObject({ text: 'ping-hud Motion: make a 30-second film explaining my last reply', mode: 'replace' })
  expect(spawns.length + w.complete.length + w.fork.length).toBe(0)
  await p.unmount()
})

test('band Motion button opens the pane and fills the same request', async ($, on) => {
  const w = xw(on, { 'hudCmds:sid-a': [] })
  const fills = boxW(on)
  on('ui.render', { component: 'AbovePrompt' }, ($: any, e: any) => { const { Box } = $.ui.resolve(e); return <Box key="engine" /> })
  const band = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AbovePrompt', props: bandProps })
  await band.press({ key: 'btnmotion' })
  expect(w.opened).toContainEqual({ id: PANE_ID, title: 'Explanation' })
  expect(fills[0]?.text).toContain('ping-hud Motion:')
  await band.unmount()
})

test('Motion never overwrites a draft in the prompt box; the red note gives the request to send', async ($, on) => {
  const st: Record<string, unknown> = {}
  xw(on, st)
  const fills = boxW(on, 'half-typed question')
  const p = await mountX($)
  await p.input({ key: 'xbox0', text: 'docs/plan.md', kind: 'change' } as any)
  await p.press({ key: 'xmmotion' })
  expect(fills.length).toBe(0)
  expect((st['hudExplain:sid-a'] as any).note).toContain('ping-hud Motion: make a 30-second film explaining docs/plan.md')
  await p.unmount()
})

test('typed /personal-hud motion <subject> puts the request in the prompt box', async ($, on) => {
  xw(on)
  const fills = boxW(on)
  const r: any = await $.command.run({ command: 'personal-hud', args: 'motion docs/Plan.md' })
  expect(fills[0]?.text).toBe('ping-hud Motion: make a 30-second film explaining docs/Plan.md')
  expect(String(r.text)).toContain('press Enter')
})

test('sending the request gives the main model the dispatch instruction and keeps the brief; a plain prompt gets nothing', async ($, on) => {
  const st: Record<string, unknown> = { 'hudExplainCtx:sid-a': { ask: 'ASK-1', reply: 'REPLY-1' } }
  xw(on, st)
  const seen: any[] = []
  on('prompt.submit', (_$: any, e: any) => { seen.push(e); return { text: e.text } as any })
  await $.prompt.submit({ text: 'what is a hook?', wait: false } as any)
  expect(JSON.stringify(seen[0].context ?? [])).not.toContain(FILM_AGENT)
  await $.prompt.submit({ text: motionAsk('docs/Plan.md'), wait: false } as any)
  expect(JSON.stringify(seen[1].context)).toContain(FILM_AGENT)
  const brief = String(st['hudMotionBrief:sid-a'])
  for (const x of ['REPLY-1', 'FILE D:/x/docs/Plan.md', 'FILM: ', 'select:Artifact,ArtifactData']) expect(brief.replace(/\\/g, '/')).toContain(x)
  expect((st['hudExplain:sid-a'] as any).topic).toMatchObject({ mode: 'motion', subject: 'docs/Plan.md' })
})

test('the film agent starts only for a pending request, with the stored brief as its prompt; other agents pass untouched', async ($, on) => {
  const st: Record<string, unknown> = { 'hudMotionBrief:sid-a': 'BRIEF-1' }
  xw(on, st)
  const spawns: any[] = []
  on('agent.spawn', (_$: any, e: any) => { spawns.push(e); return { model: 'sonnet' } as any })
  const base = { tool_use_id: 't1', description: 'htsw Motion film', provider: { plugin: 'engine', tier: 'core' }, parentModel: 'opus', background: true }
  await $.agent.spawn({ ...base, prompt: 'ping-hud Motion film', subagentType: FILM_AGENT } as any)
  expect(spawns[0].prompt).toBe('BRIEF-1') // the short prompt became the brief
  expect(st['hudMotionBrief:sid-a']).toBe('') // one film per request
  const again: any = await $.agent.spawn({ ...base, tool_use_id: 't2', prompt: 'x', subagentType: FILM_AGENT } as any)
  expect(again.deny).toContain('only from a ping-hud Motion request')
  expect(spawns.length).toBe(1)
  await $.agent.spawn({ ...base, tool_use_id: 't3', prompt: 'scan', subagentType: 'Explore' } as any)
  expect(spawns[1].prompt).toBe('scan')
})

test('a request the main chat did not act on clears at turn end and says so', async ($, on) => {
  const st: Record<string, unknown> = { 'hudMotionBrief:sid-a': 'BRIEF-1', 'hudExplain:sid-a': { ...emptyData(), motionTopic: 1 } }
  xw(on, st)
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ answer: 'I could not start it.', durationMs: 1, isAborted: false, turnId: 't1', reason: 'end_turn' } as any)
  expect(st['hudMotionBrief:sid-a']).toBe('')
  expect((st['hudExplain:sid-a'] as any).note).toContain('did not start the film agent')
})

test('session start registers the film agent locked to ToolSearch, Artifact and ArtifactData, on Sonnet, for Motion requests only', async ($, on) => {
  xw(on)
  const regs: any[] = []
  on('agent.register', (_$: any, e: any) => { regs.push(e); return { value: { agent: FILM_AGENT } } as any })
  await $.session.start({ cwd: 'D:/x' } as any).catch(() => undefined)
  const r = regs.find(x => x.name === 'film-maker')
  expect([...r.tools].sort()).toEqual(['Artifact', 'ArtifactData', 'ToolSearch'])
  expect(r).toMatchObject({ model: 'sonnet', background: true, omitClaudeMd: true })
  expect(FILM_AGENT_SPEC.description).toContain('"ping-hud Motion:" request')
})

test('paneScrollText: rows shown in a ping-hud pane; nothing for another plugin; cleared when it all fits', () => {
  expect(paneScrollText(PANE_ID, 40, 40, 210)).toBe('Explanation: rows 41-80 of 210')
  expect(paneScrollText('hud-goals', 170, 40, 210)).toBe('Goals: rows 171-210 of 210 (end)')
  expect(paneScrollText('hud-agents', 999, 40, 210)).toBe('Agents: rows 171-210 of 210 (end)') // past the end clamps
  expect(paneScrollText('hud-agents', 0, 40, 30)).toBeUndefined()
  expect(paneScrollText('other-plugin-pane', 0, 40, 210)).toBeNull()
})

test('every ping-hud pane shows the scroll hint; the Explanation pane lists the newest answer first', async ($, on) => {
  let d = startTopic(emptyData(), 'explain', 'my last reply', 'en', 'quick')
  d = addAnswer(addAnswer(d, 'Explain: one', 'ANS-OLD'), 'two', 'ANS-NEW')
  xw(on, { 'hudExplain:sid-a': d })
  const p = await mountX($)
  expect(await p.find({ type: 'Text', text: SCROLL_HINT })).toBeDefined()
  const tree = JSON.stringify(await p.find({ key: 'explain' } as any))
  expect(tree.indexOf('ANS-NEW')).toBeGreaterThan(-1)
  expect(tree.indexOf('ANS-NEW')).toBeLessThan(tree.indexOf('ANS-OLD'))
  await p.unmount()
  for (const id of ['hud-goals', 'hud-agents']) {
    const q = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'Pane', requestId: id, props: { viewport: { rows: 40, columns: 120 } } as any })
    expect(await q.find({ type: 'Text', text: SCROLL_HINT })).toBeDefined()
    await q.unmount()
  }
})

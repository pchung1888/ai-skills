import { test, expect, mock } from 'claude-code/testing'
import { etTime } from './hud-render'
import { addTime, findTime } from './hud-data'

const T0 = Date.parse('2026-10-08T18:41:00Z')

test('etTime formats New York time with daylight saving, ASCII only', () => {
  expect(etTime(T0)).toBe('Oct 8, 2:41 PM ET') // EDT
  expect(etTime(Date.parse('2026-12-08T19:41:00Z'))).toBe('Dec 8, 2:41 PM ET') // EST
  expect(etTime(Date.parse('2026-12-08T04:05:00Z'))).toBe('Dec 7, 11:05 PM ET') // New York's date, not UTC's
  expect(/^[\x20-\x7e]+$/.test(etTime(T0))).toBe(true) // no narrow no-break space from Intl
})

test('addTime / findTime: latest match wins, reply tail matches, garbage tolerated, list capped', () => {
  let t = addTime(undefined, 'user', '  hi  ', 1)
  t = addTime(t, 'user', 'hi', 2)
  expect(findTime(t, 'user', 'hi')).toBe(2) // same text twice: the newer time
  expect(findTime(t, 'user', 'other')).toBe(undefined)
  const long = 'x'.repeat(500) + ' the end of the reply'
  t = addTime(t, 'assistant', long, 3)
  expect(findTime(t, 'assistant', 'x'.repeat(500) + ' the end of another reply')).toBe(undefined)
  expect(findTime(t, 'assistant', long.slice(-260))).toBe(3) // the reply's last block ends like the answer
  expect(findTime({ user: 'bad' } as any, 'user', 'hi')).toBe(undefined)
  expect(addTime({ user: null } as any, 'user', '', 5)).toEqual({ user: [], assistant: [] }) // blank text: nothing stored
  let c: any
  for (let i = 0; i < 150; i++) c = addTime(c, 'user', `p${i}`, i)
  expect(c.user.length).toBe(100)
  expect(findTime(c, 'user', 'p149')).toBe(149)
})

// Times world: session sid-a, clock at T0, copies and the engine's own rows recorded.
function tw(on: any, store: Record<string, unknown> = {}) {
  const map: Record<string, any> = { ...store }
  on('store.get', (_$: any, e: any) => ({ value: map[e.key] }))
  on('store.set', (_$: any, e: any) => { map[e.key] = e.value; return { value: undefined } })
  mock.clock(on, { now: T0 })
  on('session.id', () => ({ value: 'sid-a' }))
  const w = { map, copies: [] as any[] }
  on('ui.copy', (_$: any, e: any) => { w.copies.push(e); return { value: undefined } })
  for (const component of ['UserMessage', 'AssistantMessage'])
    on('ui.render', { component }, ($: any, e: any) => { const { Box } = $.ui.resolve(e); return <Box key="engine" /> })
  return w
}
const userProps = (text: string) => ({ text, origin: { kind: 'user' }, isExpanded: false })
const replyProps = (text: string, x: object = {}) => ({ text, isFirstOfReply: true, ...x })

test('a typed prompt gets a dim New York time line under its row', async ($, on) => {
  tw(on)
  on('prompt.submit', (_$: any, e: any) => ({ text: e.text }))
  await $.prompt.submit({ text: 'can you reload the hud', wait: false } as any)
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'UserMessage', props: userProps('can you reload the hud') })
    const t = await ui.find({ type: 'Text', text: /PM ET$/ }) as any
    expect(t?.text).toBe('Oct 8, 2:41 PM ET')
    expect(t.props.dimColor).toBe(true)
    expect(await ui.find({ key: 'engine' })).toBeDefined() // the engine's row still draws
    // Desktop draws the prompt bubble on the right, so its time sits right too; the terminal prompt is left.
    expect(JSON.stringify(await ui.find({ key: 'hudmsg' })).includes('"alignSelf":"flex-end"')).toBe(surface === 'desktop')
    await ui.unmount()
  }
})

test('a row with no recorded time draws the engine row unchanged', async ($, on) => {
  tw(on)
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'UserMessage', props: userProps('typed before the mod loaded') })
  expect(await ui.find({ type: 'Text', text: /ET$/ })).toBeUndefined()
  expect(await ui.find({ key: 'engine' })).toBeDefined()
  await ui.unmount()
})

test('a finished reply gets its time and a copy button on terminal and Desktop', async ($, on) => {
  const w = tw(on)
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ answer: 'Phase 7 is built.', durationMs: 1, isAborted: false, turnId: 't1' } as any)
  expect(w.map['hudTimes:sid-a']?.assistant?.[0]).toEqual({ tail: 'Phase 7 is built.', ms: T0 })
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface, component: 'AssistantMessage', props: replyProps('Phase 7 is built.') })
    expect((await ui.find({ type: 'Text', text: /PM ET$/ }))?.text).toBe('Oct 8, 2:41 PM ET')
    await ui.press({ key: 'hudcopy' })
    await ui.unmount()
  }
  expect(w.copies).toEqual([{ text: 'Phase 7 is built.', surface: 'terminal' }, { text: 'Phase 7 is built.', surface: 'desktop' }])
})

test('a subagent turn end, a summary block and an unmatched block add nothing', async ($, on) => {
  tw(on)
  on('turn.complete', () => ({ text: '' }))
  await $.turn.complete({ answer: 'subagent text', durationMs: 1, isAborted: false, turnId: 't2', agentId: 'a1' } as any)
  await $.turn.complete({ answer: 'Main answer.', durationMs: 1, isAborted: false, turnId: 't3' } as any)
  for (const props of [replyProps('subagent text'), replyProps('Main answer.', { isSummary: true }), replyProps('an earlier block')]) {
    const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'AssistantMessage', props })
    expect(await ui.find({ type: 'Button' })).toBeUndefined()
    expect(await ui.find({ key: 'engine' })).toBeDefined()
    await ui.unmount()
  }
})

test('band off: no time lines and no copy buttons', async ($, on) => {
  tw(on, { hudMode: 'off' })
  on('prompt.submit', (_$: any, e: any) => ({ text: e.text }))
  await $.prompt.submit({ text: 'hi', wait: false } as any)
  const ui = await $.ui.mount({ plugin: 'ping-personal', surface: 'terminal', component: 'UserMessage', props: userProps('hi') })
  expect(await ui.find({ type: 'Text', text: /ET$/ })).toBeUndefined()
  await ui.unmount()
})

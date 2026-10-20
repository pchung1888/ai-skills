// Explanation pane: data and prompt building only (no $). register.tsx draws the pane and runs the calls.
import { BLUE, YELLOW, ORANGE, PURPLE, PINK } from './hud-actions'

export type Mode = 'simple' | 'explain' | 'kid' | 'deep' | 'motion'
export type Lang = 'en' | 'yue'
// quick = only the last question and reply go to the model; chat = the whole main chat (a fork).
export type Scope = 'quick' | 'chat'
export type QA = { q: string; a: string }
// page = the Deep HTML file; film = the Motion film's claude.ai link.
export type Topic = { id: number; mode: Mode; subject: string; lang: Lang; scope: Scope; qa: QA[]; page?: string; film?: string }
// The last question typed in the main chat and the last main reply, kept by the turn hooks.
export type Ctx = { ask?: string; reply?: string }
export type Cost = { newTokens: number; cachedTokens: number; outTokens: number; ms: number }
// motion = the film a background subagent is making now (one at a time); its turn.complete ends it.
// motionTopic = the topic of a sent Motion request whose film agent has not started yet.
export type Motion = { agentId: string; topicId: number; startMs: number }
export type ExplainData = { topic?: Topic; earlier: Topic[]; next: number; status: string; note?: string; cost?: Cost; boxKey: number; motion?: Motion; motionTopic?: number }

export const PANE_ID = 'hud-explain'
export const EARLIER_MAX = 5
// Number keys 1-5 press a mode button while a pane button holds the focus (the box takes typed keys).
// Motion is not a side call: a background subagent makes a Motion film (DEC-8); its follow-ups answer as Explain.
export const MODES: { key: Mode; label: string; color: string; hotkey: string; ref: string; how: string }[] = [
  { key: 'simple', label: 'Simple', color: YELLOW, hotkey: '1', ref: 'now.md', how: 'now mode (short: verdict, small flowchart, your-job table, why this shape, TL;DR)' },
  { key: 'explain', label: 'Explain', color: BLUE, hotkey: '2', ref: 'walk.md', how: 'walk mode (explain it fully, no verdict)' },
  { key: 'kid', label: 'Kid', color: ORANGE, hotkey: '3', ref: 'baby.md', how: 'baby mode (an everyday analogy next to every technical term)' },
  { key: 'deep', label: 'Deep HTML', color: PURPLE, hotkey: '4', ref: 'now.md', how: 'now --deep mode: write the Markdown of a Deep HTML page as now.md describes (interactive: true frontmatter, per-phase tables, Glossary, evidence labels, a flow block and the other html-plan blocks where they fit). Return only the Markdown; the pane saves and renders it' },
  { key: 'motion', label: 'Motion', color: PINK, hotkey: '5', ref: 'walk.md', how: 'walk mode (explain it fully, no verdict)' },
]
export const modeOf = (m: Mode) => MODES.find(x => x.key === m)!

// SKILL.md sections every pane answer follows; cut at click time so the pane never keeps its own copy.
export const RULE_SECTIONS = ['Explaining sentences', 'Language switch']
// The writing patterns a pane answer or film removes by default (personal-unslop SKILL.md).
export const UNSLOP_SECTIONS = ['Patterns to detect and fix']
const UNSLOP_HEAD = 'Writing patterns to remove before you answer (from personal-unslop SKILL.md):'
function unslopBlock(unslop?: string): string[] {
  const cut = unslop ? cutSections(unslop, UNSLOP_SECTIONS) : ''
  return cut ? [UNSLOP_HEAD, cut] : []
}

// Shown under the topic while Quick is on: Quick is the default and the cheap way, so the pane says so.
// A pane cannot draw a scroll bar (the engine owns its window), so every ping-hud pane shows this hint and
// the status line shows where the window sits while the person scrolls. A new pane adds its id here.
export const SCROLL_HINT = 'Scroll: mouse wheel, or click in the pane then arrows / PgUp / PgDn / Home / End.'
export const PANE_TITLES: Record<string, string> = { [PANE_ID]: 'Explanation', 'hud-goals': 'Goals', 'hud-agents': 'Agents' }
// Status-line text for a scroll in one of these panes: null for another plugin's pane, undefined (clear it) when all fits.
export function paneScrollText(id: string, offset: number, bodyRows: number, contentRows: number): string | null | undefined {
  const title = PANE_TITLES[id]
  if (!title) return null
  if (contentRows <= bodyRows) return undefined
  const first = Math.max(0, Math.min(offset, contentRows - bodyRows)) + 1, last = Math.min(first - 1 + bodyRows, contentRows)
  return `${title}: rows ${first}-${last} of ${contentRows}${last >= contentRows ? ' (end)' : ''}`
}
export const QUICK_TIP ='Tip: Quick (default) sends only your last message and my last reply, about 10-15K tokens a press. Use it first; switch Context to Whole chat only for questions about the whole session.'

export function emptyData(): ExplainData {
  return { earlier: [], next: 1, status: 'Ready. Press a level (1-5) to explain my last reply, or type what to explain first.', boxKey: 0 }
}

// The '## <title>' sections of a Markdown file, each up to the next '## ' heading; missing titles are skipped.
export function cutSections(md: string, titles: string[]): string {
  const lines = md.split(/\r?\n/), out: string[] = []
  for (const t of titles) {
    const i = lines.findIndex(l => l.startsWith(`## ${t}`))
    if (i < 0) continue
    let j = i + 1
    while (j < lines.length && !lines[j].startsWith('## ')) j++
    out.push(lines.slice(i, j).join('\n').trim())
  }
  return out.join('\n\n')
}

// A typed subject that names a file: one token with a file extension, optionally ':from-to' lines.
export function parsePath(s: string): { path: string; from?: number; to?: number } | undefined {
  const m = /^([^\s"'<>|]+\.[A-Za-z0-9]{1,6})(?::(\d+)(?:-(\d+))?)?$/.exec(s.trim())
  if (!m) return undefined
  const from = m[2] ? Number(m[2]) : undefined
  return { path: m[1], from, to: m[3] ? Number(m[3]) : from }
}

// Lines from..to (1-based, inclusive) of text; no range returns the text as is.
export function sliceLines(text: string, from?: number, to?: number): string {
  if (!from) return text
  return text.split(/\r?\n/).slice(from - 1, to ?? from).join('\n')
}

// Starts a new topic; the current one moves to Earlier when it has an answer (newest first, at most 5).
export function startTopic(d: ExplainData, mode: Mode, subject: string, lang: Lang, scope: Scope): ExplainData {
  return { ...park(d), topic: { id: d.next, mode, subject, lang, scope, qa: [] }, next: d.next + 1 }
}

// Puts the current topic away (New topic); nothing is current afterwards. A topic whose film is still being made
// is kept too, so the film's link has a topic to land in.
export function park(d: ExplainData): ExplainData {
  const keep = d.topic && (d.topic.qa.length || d.motion?.topicId === d.topic.id)
  const earlier = keep ? [d.topic!, ...d.earlier.filter(t => t.id !== d.topic!.id)].slice(0, EARLIER_MAX) : d.earlier
  return { ...d, topic: undefined, earlier }
}

// Brings an Earlier topic back as the current one; the current one moves to Earlier.
export function reopen(d: ExplainData, id: number): ExplainData {
  const t = d.earlier.find(x => x.id === id)
  if (!t) return d
  const parked = park(d)
  return { ...parked, topic: t, earlier: parked.earlier.filter(x => x.id !== id) }
}

export function clearAll(d: ExplainData): ExplainData {
  return { ...d, topic: undefined, earlier: [], cost: undefined, note: undefined }
}

export function addAnswer(d: ExplainData, q: string, a: string, page?: string): ExplainData {
  if (!d.topic) return d
  return { ...d, topic: { ...d.topic, qa: [...d.topic.qa, { q, a }], page: page ?? d.topic.page } }
}

export type PromptIn = {
  mode: Mode; lang: Lang; scope: Scope; subject: string
  skill: string; ref: string            // SKILL.md and the mode's reference file, as read at click time
  unslop?: string                       // personal-unslop SKILL.md, as read at click time
  ctx: Ctx; file?: { path: string; text: string }; question?: string
  qa: QA[]; follow?: string
}

// head = the htsw rules (the same every press, so it can be cached); body = this press.
export function buildPrompt(p: PromptIn): { head: string; body: string } {
  const m = modeOf(p.mode)
  const head = [
    'htsw rules for the Explanation pane (from personal-htsw SKILL.md):',
    cutSections(p.skill, RULE_SECTIONS),
    ...unslopBlock(p.unslop),
    `Mode reference (personal-htsw references/${m.ref}):`,
    p.ref,
  ].join('\n\n') + '\n\n' // blocks are joined with nothing between them, so the head ends its own paragraph
  const parts = [
    `You are the Explanation pane of the ping-hud band. Your answer is shown only in the pane, never in the main chat. Use htsw ${m.how}. Treat the context below as the conversation. Write no files and run nothing.`,
    p.lang === 'yue' ? 'Language: --cantonese. Write the whole answer in spoken Hong Kong Cantonese; keep code, paths, commands and technical terms in English; ASCII punctuation only.' : 'Language: English.',
    `What to explain: ${p.subject}`,
  ]
  if (p.question) parts.push(`The question form the user has open right now:\n${p.question}\nExplain what each question and option means and what each choice leads to, so the user can pick. Do not pick for the user.`)
  if (p.scope === 'quick') {
    if (p.ctx.ask) parts.push(`The user's last message in the main chat:\n${p.ctx.ask}`)
    parts.push(p.ctx.reply ? `The last reply in the main chat:\n${p.ctx.reply}` : 'The last main-chat reply is not known to the pane (it opened after it). If the subject needs it, say so and suggest the Whole chat switch.')
  }
  if (p.file) parts.push(`File ${p.file.path}:\n\`\`\`\n${p.file.text}\n\`\`\``)
  if (p.qa.length) parts.push('Earlier in this topic:\n' + p.qa.map(x => `Q: ${x.q}\nA: ${x.a}`).join('\n\n'))
  if (p.follow) parts.push(`Follow-up question: ${p.follow}`)
  return { head, body: parts.join('\n\n') }
}

export const FILM_PREFIX = 'FILM: '

// The task a background subagent gets for a Motion press. It cannot ask anyone, so it decides the
// film's style, colors and length itself; its last line carries the film's link for the pane.
export function motionPrompt(p: { lang: Lang; subject: string; skill: string; unslop?: string; ctx: Ctx; file?: { path: string; text: string } }): string {
  const parts = [
    'Make a 30-second Motion film that explains one subject, for the ping-hud Explanation pane. Nobody can answer questions while you work: decide everything yourself and ask nothing.',
    [
      'Steps:',
      '1. Load your tools: ToolSearch with query "select:Artifact,ArtifactData".',
      '2. Call Artifact with action "list" and scope "types"; find the type titled "Motion" and its type_url.',
      '3. Create the film: Artifact publish with that type_url, a short title that names the subject, and auto_open "after_first_write". Follow the instructions in the result exactly, as a run with nobody there to answer: pick the style and colors yourself, and make it 30 seconds long.',
      '4. The film explains the subject below in five or six scenes. Its on-screen words follow the htsw rules below. Use only facts from the context below; invent no numbers, names or results.',
      '5. Write no files on disk and run no commands; use only the Artifact, ArtifactData and ToolSearch tools.',
    ].join('\n'),
    p.lang === 'yue' ? 'Language: --cantonese. On-screen words in spoken Hong Kong Cantonese; keep code, paths, commands and technical terms in English.' : 'Language: English.',
    'htsw rules for the on-screen words (from personal-htsw SKILL.md):\n\n' + cutSections(p.skill, RULE_SECTIONS),
    ...unslopBlock(p.unslop),
    `What to explain: ${p.subject}`,
  ]
  if (p.ctx.ask) parts.push(`The user's last message in the main chat:\n${p.ctx.ask}`)
  if (p.ctx.reply) parts.push(`The last reply in the main chat:\n${p.ctx.reply}`)
  if (p.file) parts.push(`File ${p.file.path}:\n\`\`\`\n${p.file.text}\n\`\`\``)
  parts.push(`End your reply with one line exactly: ${FILM_PREFIX}<the film's url from the create result>. If you could not make it, end with: NO FILM: <one-line reason>`)
  return parts.join('\n\n')
}

// The film link in a subagent's report: the FILM line first, else any claude.ai artifact link; only https claude.ai links count.
// A whole film link: a claude.ai artifact page and nothing else (Open film checks it again before launching).
export const FILM_RE = /^https:\/\/claude\.ai\/(?:code\/)?artifact\/[\w-]+$/

export function filmUrl(answer: string): string | undefined {
  const ok = /https:\/\/claude\.ai\/(?:code\/)?artifact\/[\w-]+/
  const line = answer.split(/\r?\n/).reverse().find(l => l.trim().startsWith(FILM_PREFIX))
  return ok.exec(line ?? '')?.[0] ?? ok.exec(answer)?.[0]
}

// The plain request a Motion press puts in the prompt box; the main model reads it, so auto mode sees it asked for.
export const MOTION_ASK = 'ping-hud Motion:'
export function motionAsk(subject: string): string {
  return `${MOTION_ASK} make a 30-second film explaining ${subject.trim() || 'my last reply'}`
}

// What a sent prompt asks a film of: the words after the request's opening; undefined for any other prompt.
export function motionAskSubject(text: string): string | undefined {
  const m = /^\s*ping-hud Motion:\s*(?:make a 30-second film explaining\s*)?([\s\S]*)$/i.exec(text)
  return m ? m[1].trim() || 'my last reply' : undefined
}

// What the main model is told with a Motion request: start the film agent with a short prompt (the agent.spawn
// hook swaps in the brief), and do nothing else.
export function motionDispatch(agent: string): string {
  return `ping-hud: the person pressed the Motion button. Call the Agent tool once: subagent_type "${agent}", run_in_background true, description "htsw Motion film", prompt "ping-hud Motion film" (the plugin fills in the full film brief). Do not explain the subject yourself and do not wait for the film. Then reply in one line: the film is being made, and its link will appear in the ping-hud Explanation pane.`
}
export const MOTION_BUSY = 'ping-hud: the person pressed the Motion button, but a film is still being made. Do not start any agent; say in one line that the current film must finish first.'

// /personal-hud motion args -> what the film explains: the words after 'motion' as typed, case kept.
export function motionSubject(args: string): string {
  return String(args || '').trim().replace(/^motion\b\s*/i, '')
}

// The film subagent ended: its topic (current or Earlier) gets the link or the reason, and the pane is free again.
export function finishMotion(d: ExplainData, answer: string): ExplainData {
  const m = d.motion
  if (!m) return d
  const url = filmUrl(answer)
  const why = /NO FILM:\s*(.*)/.exec(answer)?.[1]?.trim()
  const a = url ? `Film ready: ${url}` : `No film. ${why || (answer.trim() ? answer.trim().slice(0, 1500) : 'The subagent ended without a report.')}`
  const fix = (t: Topic): Topic => (t.id === m.topicId ? { ...t, qa: [...t.qa, { q: `Motion: ${t.subject}`, a }], film: url ?? t.film } : t)
  return {
    ...d, motion: undefined, topic: d.topic && fix(d.topic), earlier: d.earlier.map(fix),
    status: url ? 'Film ready. Click the link, or press Open film.' : 'The film subagent ended without a film. See the reason below; press Motion to try again.',
    // Clear all removed the topic while the film was made: the link still reaches the user.
    note: [d.topic, ...d.earlier].some(t => t?.id === m.topicId) ? d.note : a,
  }
}

// Token use of one press from a model call's usage; missing numbers count as 0.
export function costOf(usage: any, ms: number): Cost {
  const n = (x: unknown) => (typeof x === 'number' ? x : 0)
  return { newTokens: n(usage?.input_tokens) + n(usage?.cache_creation_input_tokens), cachedTokens: n(usage?.cache_read_input_tokens), outTokens: n(usage?.output_tokens), ms }
}

export function costLine(c: Cost): string {
  const k = (x: number) => (x >= 1000 ? `${Math.round(x / 1000)}K` : String(x))
  return `Last press: ${k(c.newTokens)} new + ${k(c.cachedTokens)} cached tokens in, ${k(c.outTokens)} out, ${(c.ms / 1000).toFixed(1)} s`
}

// Focus lock: while the box has focus and text, the person's Tab / arrows / clicks may not move the ring
// out of it. A click on a Button still presses it (checked in the spike); Esc still leaves the pane.
export function shouldLock(focused: string, text: string, origin: string, to: string | undefined): boolean {
  return focused.startsWith('xbox') && !!text.trim() && origin === 'person' && !(to ?? '').startsWith('xbox')
}

// The first question of an AskUserQuestion call as readable text: question plus option labels and descriptions.
export function questionText(questions: unknown): string {
  const qs = Array.isArray(questions) ? questions : []
  return qs.map((q: any) => [String(q?.question ?? ''), ...(Array.isArray(q?.options) ? q.options : []).map((o: any) => `- ${o?.label ?? ''}: ${o?.description ?? ''}`)].join('\n')).join('\n\n')
}

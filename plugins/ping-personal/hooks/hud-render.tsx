// ping-hud render: state -> rows of styled spans (pure), then spans -> Box/Text tree.
import { chip as chipOf, type Tone, type Chip } from './hud-rules'
import { taskBar, type HudState, type Goal, type Status, type Step, type Task } from './hud-data'

// Every non-ASCII glyph lives here as an escape, each with an ASCII twin.
export const GLYPHS = {
  ascii: { bar: '#', empty: '.', div: '|', edge: '|' },
  unicode: { bar: '\u2588', empty: '\u2591', div: '\u2502', edge: '\u258c' },
}
export type GlyphSet = keyof typeof GLYPHS
// mini = the Hide state: one row, `ping-hud [ Show ]`, drawn by register.tsx.
export type Mode = 'on' | 'compact' | 'off' | 'mini'

// keep = never truncated; anything else may be cut with an ellipsis at the edge.
// k = stable key suffix (bars); svg = the desktop Svg is drawn right after this span.
export type Hue = Tone | 'calm' | 'blue' | 'time'
export type Span = { t: string; tone?: Hue; b?: boolean; d?: boolean; inv?: boolean; keep?: boolean; k?: string; svg?: boolean }
export type Row = { key: string; spans: Span[]; svg?: string }
export type RenderOpts = {
  surface: string; bodyColumns?: number; maxRows?: number; mode?: Mode; glyphs?: GlyphSet
  statusLinePresent?: boolean; nowMs: number; cwd?: string; now?: string; goals?: Goal[]
  status?: Status; step?: Step; tasks?: Task[] | null
  title?: string; buttons?: boolean // session name; buttons = add the Buttons row (drawn by register.tsx)
}

const WIDE = 120

// Right-aligned 4-char percent cell: '  5%', '100%', '  --' when unknown.
export function cell(pct?: number): string {
  return pct === undefined || !isFinite(pct) ? '  --' : `${Math.round(pct)}%`.padStart(4)
}

// Minutes -> '44m', '1h12' (clock style) or '1h12m' / '6d16h' (reset style).
export function dur(min: number, style: 'clock' | 'reset' = 'clock'): string {
  const m = Math.max(0, Math.round(min))
  if (m < 60) return `${m}m`
  if (style === 'reset' && m >= 1440) return `${Math.floor(m / 1440)}d${Math.floor((m % 1440) / 60)}h`
  const h = Math.floor(m / 60), mm = String(m % 60).padStart(2, '0')
  return style === 'reset' ? `${h}h${mm}m` : `${h}h${mm}`
}

function label(t: string): Span { return { t: t.padEnd(8) + ' ', d: true, keep: true } }

// Terminal number colors (ccstatusline style): green < 50, yellow 50-79, red >= 80.
function pctTone(pct?: number): Hue | undefined { return pct === undefined || !isFinite(pct) ? undefined : pct >= 80 ? 'bad' : pct >= 50 ? 'warn' : 'ok' }

// Cut to n characters with '...' so a long goal step never pushes the row off screen.
function cut(t: string, n: number): string { return t.length > n ? t.slice(0, n - 3) + '...' : t }

// Calm palette (decision 29): bars blue-gray < 60, amber 60-79, red >= 80.
export function level(pct: number): Hue { return pct >= 80 ? 'bad' : pct >= 60 ? 'warn' : 'calm' }

// [filled|empty] bar: filled cells colored, empty cells dim; id keys the two cell spans.
type G = (typeof GLYPHS)[GlyphSet]
function bar(id: string, pct: number | undefined, cells: number, g: G, tone: Hue): Span[] {
  const n = pct === undefined || !isFinite(pct) ? 0 : Math.max(0, Math.min(cells, Math.round((pct / 100) * cells)))
  const dim = tone === 'dim' || tone === 'default'
  return [{ t: '[', d: true, keep: true }, { t: g.bar.repeat(n), k: `${id}fill`, tone: dim ? undefined : tone, d: dim, keep: true },
    { t: g.empty.repeat(cells - n), k: `${id}empty`, d: true, keep: true }, { t: ']', d: true, keep: true }]
}

function shortPath(p: string): string {
  const parts = p.split(/[\\/]+/).filter(Boolean)
  if (parts.length <= 2) return p
  const sep = p.includes('\\') ? '\\' : '/'
  return `${parts[0]}${sep}...${sep}${parts[parts.length - 1]}`
}

function rate(s: HudState | undefined, kind: string) {
  return s?.usage.rateLimits.find(r => r.kind === kind)
}

// Desktop-only burn timeline (320x18). x=0 is now; S minutes span the width, capped at the 5h window.
// Solid = used %, dashed ghost = path to 100%, tick = reset; RUNS OUT colors the ghost-to-tick gap.
const TONE_CSS: Record<string, string> = { ok: 'green', warn: 'orange', bad: 'red' }
export function burnSvg({ usedPct, t100Min, resetMin, tone }: { usedPct: number; t100Min?: number; resetMin?: number; tone: Tone }): string {
  const W = 320, r1 = (n: number) => Math.round(n * 10) / 10
  const reset = Math.max(0, resetMin ?? 0), t100 = t100Min !== undefined && isFinite(t100Min) ? t100Min : undefined
  const S = Math.max(1, Math.min(300, Math.max(reset, t100 ?? 0) * 1.1))
  const x = (m: number) => r1(Math.min(W, (W * m) / S))
  const solid = r1((W * Math.min(100, Math.max(0, usedPct))) / 100)
  const parts = [
    `<rect x="0" y="6" width="${W}" height="6" rx="3" fill="currentColor" opacity=".15"/>`,
    `<rect x="0" y="6" width="${solid}" height="6" rx="3" fill="currentColor" opacity=".8"/>`,
  ]
  if (t100 !== undefined) {
    const end = x(t100)
    if (end > solid) parts.push(`<rect x="${solid}" y="6" width="${r1(end - solid)}" height="6" fill="none" stroke="currentColor" stroke-dasharray="3 3" opacity=".6"/>`)
    if ((W * t100) / S > W) parts.push(`<path d="M314,4 L320,9 L314,14" fill="none" stroke="currentColor"/>`)
    if (resetMin !== undefined && t100 < reset && TONE_CSS[tone])
      parts.push(`<rect data-gap="${tone}" x="${end}" y="6" width="${r1(x(reset) - end)}" height="6" fill="${TONE_CSS[tone]}"/>`)
  }
  if (resetMin !== undefined) parts.push(`<line x1="${x(reset)}" y1="1" x2="${x(reset)}" y2="17" stroke="currentColor" stroke-width="2"/>`)
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="18" viewBox="0 0 ${W} 18">${parts.join('')}</svg>`
}

// One plain sentence per verdict (decision 28); narrow keeps only the part before ' -- '.
export function forecastSpan(c: Chip, wide: boolean): Span {
  const t100 = c.t100Min, reset = c.resetMin
  const known = t100 !== undefined && reset !== undefined
  const pace = known ? `at this pace 100% in ${dur(t100!)}` : ''
  let t = '5h 100% in --', tone: Hue | undefined, b: boolean | undefined
  if (c.word === 'RUNS OUT' && known) { t = `5h will run out: ${pace}, ${dur(reset! - t100!)} BEFORE the reset in ${dur(reset!)} -- wrap up or pause`; tone = 'bad'; b = true }
  else if (c.word === 'TIGHT' && known) { t = `5h is close: ${pace}, only ${dur(t100! - reset!)} after the reset in ${dur(reset!)} -- slow down`; tone = 'warn' }
  else if (c.word === 'OK' && known) t = `5h won't run out: ${pace}, after the reset in ${dur(reset!)}`
  else if (c.word === 'LEARNING') t = '5h under 2% used -- no pace yet'
  return { t: ` ${wide ? t : t.split(' -- ')[0]}`, tone, b, keep: true }
}

// Two fixed layouts (wide >= 120 cols or unknown, narrow below); rows dropped by mode and maxRows.
export function layout(s: HudState | undefined, o: RenderOpts): Row[] | null {
  if (o.mode === 'off') return null
  if (o.mode === 'mini') return [{ key: 'mini', spans: [] }]
  const wide = o.bodyColumns === undefined || o.bodyColumns >= WIDE
  const g = GLYPHS[o.glyphs || 'unicode']
  const cells = wide ? 10 : 5
  const nowMs = o.nowMs
  const c = chipOf({ usage: s?.usage, measured: s?.lastRefreshMs !== undefined, nowMs, turnActive: s?.turnActive, lastRefreshMs: s?.lastRefreshMs, samples: s?.samples })
  const vTone: Hue = c.tone === 'ok' || c.tone === 'warn' || c.tone === 'bad' ? c.tone : 'dim'
  const alert = vTone === 'warn' || vTone === 'bad'
  const sevenR = rate(s, 'seven_day')
  const fivePct = c.usedPct
  const sevenPct = sevenR?.percentUsed
  const sevenResetMin = sevenR?.resetsAt ? (Date.parse(sevenR.resetsAt) - nowMs) / 60000 : undefined
  const ctxPct = s?.ctxPct

  // Terminal draws ' | ' between groups and colors its numbers; Desktop keeps its spaced cells.
  const desk = o.surface === 'desktop', term = !desk
  const gap = (t: string, keep = true): Span => ({ t: term ? `  | ${t}` : `  ${t}`, d: true, keep })
  const num = (t: string, pct?: number, tone?: Hue): Span => ({ t, tone: tone ?? (term ? pctTone(pct) : undefined), keep: true })
  const time = (t: string): Span => ({ t, tone: term ? 'time' : undefined, keep: true })

  // Model row: model name, its thinking level (the effort the last model step ran at), then ctx / 5h / 7d
  // as numbers with their resets -- no bars, so the 7d reset still fits at narrow widths.
  // ctx growth over the last turn sits right after the ctx percent. Desktop numbers use the calm levels.
  const sp = o.step
  const model: Span[] = [label('Model'), { t: s?.model || '--', b: true, keep: true }]
  if (sp?.thinking !== undefined) model.push({ t: ' think ', d: true, keep: true }, { t: String(sp.thinking), keep: true })
  const lvl = (pct?: number): Hue | undefined => pct === undefined || !isFinite(pct) || level(pct) === 'calm' ? undefined : level(pct)
  const pctNum = (pct?: number, tone?: Hue): Span => num(` ${cell(pct)}`, pct, tone ?? (desk ? lvl(pct) : undefined))
  model.push(gap('ctx', false), pctNum(ctxPct))
  if (ctxPct !== undefined && s) model.push({ t: ` ${s.ctxDeltaTok >= 0 ? '+' : '-'}${Math.round(Math.abs(s.ctxDeltaTok) / 1000)}k`, d: true })
  model.push(gap('5h'), pctNum(fivePct, alert ? vTone : undefined))
  if (c.resetMin !== undefined) model.push({ t: ' reset ', d: true, keep: true }, time(dur(c.resetMin)))
  model.push(gap('7d'), pctNum(sevenPct))
  if (sevenResetMin !== undefined) model.push({ t: ' reset ', d: true, keep: true }, time(dur(sevenResetMin, 'reset')))

  // Session row (key 'cwd'): session name, branch and the branch it came from, folder (wide only),
  // cache hit, memory (wide only), then Goal when Tasks is shown. Labels grey, values white.
  const st = o.status
  const cwd: Span[] = [label('Session')]
  if (o.title) cwd.push({ t: o.title, b: true }, { t: '  ' })
  cwd.push({ t: 'branch ', d: true }, { t: st?.branch || '-', b: true })
  if (st && st.defaultBranch !== '-' && st.defaultBranch !== st.branch) cwd.push({ t: ' from ', d: true }, { t: st.defaultBranch })
  if (wide) cwd.push({ t: '  dir ', d: true }, { t: o.cwd ? shortPath(o.cwd) : '-' })
  cwd.push({ t: '  cache', d: true }, { t: cell(sp?.cacheHitPct) }) // 4-char cell: a 3-char box truncates on desktop
  if (wide && st?.mem) cwd.push({ t: '  mem ', d: true }, { t: st.mem })

  // Now row: activity, then Claude's task list. Goal (audit tracker) follows on the Now row,
  // or ends the cwd row when Tasks already fill the Now row and the cwd row is shown.
  // Garbage in (not an array, null entries, non-numeric counts) is dropped, never drawn as NaN.
  const goals = Array.isArray(o.goals) ? o.goals.filter(x => x && Number.isFinite(x.done) && Number.isFinite(x.total) && x.total >= 0) : undefined
  const act = o.now || 'idle', gl = goals?.[0], tb = taskBar(o.tasks)
  const now: Span[] = [label('Now'), { t: act, d: act === 'idle', keep: act === 'idle' }]
  if (tb) now.push(term ? gap('Tasks ') : { t: '   Tasks ', keep: true }, ...bar('tasks', (100 * tb.done) / tb.total, cells, g, 'blue'), { t: ` ${tb.done}/${tb.total}: `, keep: true }, { t: tb.current, d: true })
  const cwdShown = !(o.mode === 'compact' || (o.surface === 'terminal' && o.statusLinePresent)) && (o.maxRows ?? 4) >= (o.buttons ? 6 : 4)
  // goals = bound trackers in bind order: the first shows, the rest count as '+N more'; [] shows 'Goal: none'.
  if (gl) {
    const at = tb && cwdShown ? cwd : now
    if (gl.total === 0) at.push({ t: `${term ? '  | ' : '   '}Goal ${gl.slug} unreadable`, d: true }) // bound tracker whose phase table cannot be read
    else if (term) {
      // Terminal: 'Goal <slug> 9/11  <step cut to 40>'; the Goals pane has the full text.
      const n = Math.min(gl.done + 1, gl.total)
      at.push(gap('Goal '), { t: `${gl.slug} `, keep: true }, { t: `${gl.phase ?? n}/${gl.total}${gl.blocked ? ' BLOCKED' : ''}`, b: true, tone: gl.blocked ? 'bad' : undefined, keep: true },
        { t: `  ${cut(String(gl.step ?? ''), 40)}`, d: true })
    } else {
      const n = Math.min(gl.done + 1, gl.total), p = Math.round((100 * gl.done) / gl.total)
      at.push({ t: `   Goal ${gl.slug} `, keep: true }, ...bar('goal', (100 * gl.done) / gl.total, cells, g, 'blue'),
        { t: ` phase ${gl.phase ?? n} of ${gl.total} (${p}%)${gl.blocked ? ' BLOCKED' : ''}: ${gl.step}` }) // one span: a fixed-width desktop cell would open a gap before the title
    }
    if (goals!.length > 1) at.push({ t: `  +${goals!.length - 1} more`, d: true })
  } else if (goals) (tb && cwdShown ? cwd : now).push({ t: `${term ? '  | ' : '   '}Goal: none`, d: true })

  // Forecast row: chip first, then one plain sentence; narrow drops the advice after ' -- '.
  const fc: Span[] = [label('Forecast')]
  const word = c.word === 'STALE' ? `STALE ${c.ageMin ?? 0}m` : c.word
  // OK is a plain green word; TIGHT / RUNS OUT / STALE are filled badges; neutral words dim.
  fc.push({ t: ` ${word} `, tone: alert || c.tone === 'ok' ? c.tone : undefined, b: c.tone !== 'dim', inv: alert, d: c.tone === 'dim', keep: true, svg: true })
  if (c.ageMin !== undefined && c.word !== 'STALE') fc.push({ t: ` ${c.ageMin}m ago`, d: true, keep: true })
  fc.push(forecastSpan(c, wide)) // Forecast is the 5h quota only; context lives on the Model row

  // Svg time base is the last refresh, so it only changes on turn.complete / session.measure.
  let svg: string | undefined
  if (desk) {
    const base = s?.lastRefreshMs !== undefined ? chipOf({ usage: s.usage, measured: true, nowMs: s.lastRefreshMs, samples: s.samples }) : c
    svg = burnSvg({ usedPct: base.usedPct ?? 0, t100Min: base.t100Min, resetMin: base.resetMin, tone: c.tone })
  }
  // Left edge only when it matters (amber / red); otherwise a blank of the same width.
  const edge = (): Span => alert ? { t: g.edge, tone: vTone, keep: true } : { t: ' ', keep: true }
  for (const r of [model, cwd, now, fc]) r.unshift(edge())
  let rows: Row[] = [{ key: 'model', spans: model }, { key: 'cwd', spans: cwd }, { key: 'now', spans: now }, { key: 'forecast', spans: fc, svg }]
  if (o.buttons) rows.push({ key: 'buttons', spans: [] }, { key: 'htsw', spans: [] }) // Action row, then HTSW row (register.tsx draws both)
  if (o.mode === 'compact') rows = rows.slice(2)
  else if (o.surface === 'terminal' && o.statusLinePresent) rows = rows.filter(r => r.key !== 'cwd') // statusLine shows cwd, not model / 5h / 7d bars
  // Drop order: cwd, then Model, then (with buttons) Forecast, then the HTSW row, then the Action row; Now always stays.
  const max = o.maxRows ?? 4, b = o.buttons ? 2 : 0
  if (max < 4 + b) rows = rows.filter(r => r.key !== 'cwd')
  if (max < 3 + b) rows = rows.filter(r => r.key !== 'model')
  if (b && max < 4) rows = rows.filter(r => r.key !== 'forecast')
  if (b && max < 3) rows = rows.filter(r => r.key !== 'htsw')
  if (b && max < 2) rows = rows.filter(r => r.key !== 'buttons')
  return rows
}

// Plain-text form of a row, used by tests and for width checks.
export function rowText(r: Row): string { return r.spans.map(s => s.t).join('') }

// Theme keys follow the person's theme; calm has no theme key, so it is a muted hex blue-gray.
const COLOR: Record<string, string> = { ok: 'success', warn: 'warning', bad: 'error', calm: '#7f93a8', blue: 'blue', time: 'suggestion' }

// Spans -> Box/Text tree; ui is what $.ui.resolve(e) returned for this surface.
// Where Svg resolves, each span sits in a fixed-width Box (proportional-font safe),
// desktop bars are solid cell Boxes, and the Svg follows the chip.
// buttons = the element register.tsx built for this row (it owns the onPress $ calls): the Action row, or the mini row.
// htsw = the HTSW row element, drawn where layout put the 'htsw' row.
export function drawRows(ui: any, rows: Row[], desktop = false, buttons?: any, htsw?: any) {
  const { Box, Text, Svg } = ui
  const text = (r: Row, s: Span, i: number) => (
    <Text key={`${r.key}${s.k ?? i}`} color={s.tone && COLOR[s.tone]} bold={s.b} dimColor={s.d} inverse={s.inv} wrap={s.keep ? undefined : 'truncate-end'}>{s.t}</Text>
  )
  // Desktop bars: one background-colored Box per cell (block glyphs render as a dotted hatch there).
  const cells = (r: Row, s: Span) => {
    const fill = s.k!.endsWith('fill'), bg = fill ? (s.tone && COLOR[s.tone]) || 'white' : 'subtle'
    return <Box key={`${r.key}${s.k}`} flexDirection="row" flexShrink={0}>
      {Array.from(s.t, (_, j) => <Box key={`${s.k}${j}`} width={1} height={1} backgroundColor={bg} />)}
    </Box>
  }
  const span = (r: Row, s: Span, i: number) => desktop && s.k && /(fill|empty)$/.test(s.k) ? cells(r, s) : Svg ? <Box key={`c${r.key}${i}`} width={s.t.length} flexShrink={s.keep ? 0 : 1}>{text(r, s, i)}</Box> : text(r, s, i)
  return (
    <Box key="hud" flexDirection="column">
      {rows.map(r => r.key === 'buttons' || r.key === 'mini' ? buttons ?? null : r.key === 'htsw' ? htsw ?? null : (
        <Box key={r.key} flexDirection="row">
          {r.spans.flatMap((s, i) => [span(r, s, i),
            Svg && r.svg && s.svg ? <Svg key={`${r.key}svg`} source={r.svg} alt="5h burn timeline: used so far, projected path to 100%, reset tick" width={160} height={9} /> : null])}
        </Box>
      ))}
    </Box>
  )
}

// 'Oct 8, 2:41 PM ET' in New York time; Intl's narrow no-break space becomes a plain one (ASCII only).
export function etTime(ms: number): string {
  const t = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }).format(ms)
  return `${t.replace(/\s/g, ' ')} ET`
}

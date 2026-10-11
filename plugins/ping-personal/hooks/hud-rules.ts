// Pure HUD rules. No $ access; every time-dependent function takes nowMs.
const LEARN_PTS = 2, TIGHT_MIN = 30, STALE_MIN = 10, WIN_MIN = 300, WARN_7D = 80

export type Tone = 'ok' | 'warn' | 'bad' | 'dim' | 'default'
export type Sample = { tMs: number; pct: number }
type RateLimit = { kind: string; percentUsed: number; resetsAt?: string }
type Usage = { rateLimits?: RateLimit[] } | undefined

// m = minutes to 100% minus minutes to reset. m <= 0 RUNS OUT, m < 30 TIGHT.
export function verdict(t100Min: number, resetMin: number): 'RUNS OUT' | 'TIGHT' | 'OK' {
  const m = Math.round(t100Min) - Math.round(resetMin)
  return m <= 0 ? 'RUNS OUT' : m < TIGHT_MIN ? 'TIGHT' : 'OK'
}

export function weather(ctxPct: number): { word: string; tone: Tone } {
  return ctxPct >= 80 ? { word: 'Storm', tone: 'bad' } : ctxPct >= 60 ? { word: 'Showers', tone: 'warn' }
    : ctxPct >= 40 ? { word: 'Cloudy', tone: 'default' } : { word: 'Clear', tone: 'default' }
}

// LEARNING while the window itself is under 2%. Pace = window average (percentUsed / minutes since
// window start), or the in-session slope once this session has seen 2+ points move.
export function pace({ usedPct, resetsAtMs, nowMs, samples }: { usedPct: number; resetsAtMs: number; nowMs: number; samples?: Sample[] }) {
  const resetMin = Math.max(0, (resetsAtMs - nowMs) / 60000)
  const startMs = resetsAtMs - WIN_MIN * 60000
  const elapsed = Math.max(1, (nowMs - startMs) / 60000)
  if (usedPct < LEARN_PTS) return { state: 'LEARNING' as const, pctPerMin: 0, t100Min: Infinity, resetMin }
  const inWin = (samples || []).filter(s => s.tMs >= startMs)
  const first = inWin[0], seenMin = first ? (nowMs - first.tMs) / 60000 : 0
  const pctPerMin = first && usedPct - first.pct >= LEARN_PTS && seenMin >= 1 ? (usedPct - first.pct) / seenMin : usedPct / elapsed
  return { state: 'READY' as const, pctPerMin, t100Min: (100 - usedPct) / pctPerMin, resetMin }
}

export type ChipIn = {
  usage: Usage; measured: boolean; nowMs: number; turnActive?: boolean
  lastRefreshMs?: number; lastTurnMs?: number; samples?: Sample[]
}
export type Chip = { word: string; tone: Tone; ageMin?: number; usedPct?: number; t100Min?: number; resetMin?: number }

// STALE is event-driven: a turn completed while the newest reading was already 10+ min old.
export function chip({ usage, measured, nowMs, turnActive, lastRefreshMs, lastTurnMs, samples }: ChipIn): Chip {
  const r = usage && usage.rateLimits && usage.rateLimits.find(x => x.kind === 'five_hour')
  if (!r) return measured ? { word: 'NO DATA', tone: 'dim' } : { word: '...', tone: 'dim' }
  const resetsAtMs = r.resetsAt ? Date.parse(r.resetsAt) : NaN
  if (!(resetsAtMs > nowMs)) return { word: 'LEARNING', tone: 'dim', usedPct: 0 } // past or missing reset: window restarted
  const refresh = lastRefreshMs ?? nowMs
  if (!turnActive && lastTurnMs !== undefined && lastTurnMs - refresh >= STALE_MIN * 60000)
    return { word: 'STALE', tone: 'warn', ageMin: Math.floor((nowMs - refresh) / 60000) }
  const p = pace({ usedPct: r.percentUsed, resetsAtMs, nowMs, samples })
  if (p.state === 'LEARNING') return { word: 'LEARNING', tone: 'dim', usedPct: r.percentUsed, resetMin: p.resetMin }
  const word = verdict(p.t100Min, p.resetMin)
  const ageMin = Math.floor((nowMs - refresh) / 60000)
  return {
    word, tone: word === 'OK' ? 'ok' : word === 'TIGHT' ? 'warn' : 'bad',
    ageMin: !turnActive && ageMin >= STALE_MIN ? ageMin : undefined,
    usedPct: r.percentUsed, t100Min: p.t100Min, resetMin: p.resetMin,
  }
}

export function pctTone(kind: string, pct: number, chipTone: Tone): Tone {
  if (kind === 'ctx') return weather(pct).tone
  if (kind === '7d' || kind === 'codex7d') return pct >= WARN_7D ? 'warn' : 'default'
  if (kind === '5h' || kind === 'codex5h') return chipTone === 'warn' || chipTone === 'bad' ? chipTone : 'default'
  return 'default' // cache and anything else: never colored
}

// One toast per resetsAt key, only on entering RUNS OUT.
export function shouldToast(prev: string | null, word: string, key: string, lastKey: string | null) {
  const fire = word === 'RUNS OUT' && prev !== 'RUNS OUT' && key !== lastKey
  return { fire, key: fire ? key : lastKey }
}

const MODEL_NAMES: Record<string, string> = {
  'claude-opus-5-5': 'Opus 5.5', 'claude-sonnet-5-5': 'Sonnet 5.5',
  'claude-haiku-5-5': 'Haiku 5.5', 'claude-fable-5-1': 'Fable 5.1',
}
export function modelName(id: string): string {
  return MODEL_NAMES[id.replace(/\[.*\]$/, '')] || id
}

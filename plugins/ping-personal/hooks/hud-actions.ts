// ping-hud band buttons: data only (label, label color, slash command, args). register.tsx draws and runs them.
import { slugOfPath } from './hud-goals'

// Label colors: hex so the four buttons stay distinct on every theme (DEC-5).
export const GREEN = '#3fb950', BLUE = '#58a6ff', YELLOW = '#d29922', ORANGE = '#f0883e', PURPLE = '#bc8cff', CYAN = '#39c5cf', GRAY = '#8b949e', PINK = '#f778ba'

// What args sees: bound tracker paths of this session, the clock, and this plugin's folder ($.plugin.root).
export type Ctx = { bound: string[]; nowMs: number; root: string }

// cmd = the command name without plugin prefix; null = no command (Goals / Agents open their pane instead).
// plugin = the plugin that owns cmd (default ping-personal). needs 'goal' = hidden until a goal is bound.
// mode = an HTSW-row button: 'pane' opens the Explanation pane, the others run that htsw mode in it.
export type Action = { key: string; label: string; color?: string; cmd: string | null; plugin?: string; needs?: 'goal'; mode?: 'pane' | 'simple' | 'explain' | 'kid' | 'deep' | 'motion'; args: (c: Ctx) => string }

// The band's Action row.
export const ACTIONS: Action[] = [
  { key: 'handoff', label: 'Handoff', color: GREEN, cmd: 'personal-handoff', args: c => ['--unattended', ...c.bound.filter(argSafe)].join(' ') },
  // Plan: html-plan page for the first bound goal, in the arc skin (DEC-12); pack only inlines files near the page.
  { key: 'plan', label: 'Plan', color: PURPLE, cmd: 'html-plan', plugin: 'html-plan', needs: 'goal',
    args: c => `${planSlug(c.bound)} -- plan for the goal tracker ${c.bound[0]}. Style: copy ${c.root}/assets/html-plan-arc.css next to the page and link it after htmlplan.css.` },
  // Next (DEC-10): one independent seat proposes next steps; the owner picks them by clicking.
  { key: 'next', label: 'Next', color: GREEN, cmd: 'personal-next', args: () => 'now' },
  { key: 'agents', label: 'Agents', color: PINK, cmd: null, args: () => '' },
  { key: 'goals', label: 'Goals', color: CYAN, cmd: null, args: () => '' },
]

// The band's HTSW row: the Explanation pane, the four explanation levels and Motion. Each level answers in the pane,
// from the last question and reply only (quick mode), so nothing is added to the main chat.
export const HTSW_ACTIONS: Action[] = [
  { key: 'pane', label: 'Pane', color: CYAN, cmd: null, mode: 'pane', args: () => '' },
  { key: 'simple', label: 'Simple', color: YELLOW, cmd: null, mode: 'simple', args: () => '' },
  { key: 'explain', label: 'Explain', color: BLUE, cmd: null, mode: 'explain', args: () => '' },
  { key: 'kid', label: 'Kid', color: ORANGE, cmd: null, mode: 'kid', args: () => '' },
  { key: 'deep', label: 'Deep HTML', color: PURPLE, cmd: null, mode: 'deep', args: () => '' },
  // Motion (DEC-8): a background subagent makes a 30-second Motion film; the pane shows its link.
  { key: 'motion', label: 'Motion', color: PINK, cmd: null, mode: 'motion', args: () => '' },
]

// A path passed as a command argument: plain path characters only, never starting with '-',
// so a crafted folder name cannot add arguments or flags.
export function argSafe(p: string): boolean { return /^[\w./-]+$/.test(p) && !p.startsWith('-') }

// The first bound goal's slug when its path and slug are plain names; else undefined (no Plan button).
export function planSlug(bound: string[]): string | undefined {
  const p = bound[0], s = p && argSafe(p) ? slugOfPath(p) : ''
  return /^\w[\w-]*$/.test(s) ? s : undefined
}

// Folder of the first bound tracker when its path is plain (e.g. docs/mod), else docs/explain.
export function workDir(bound: string[]): string {
  const p = bound[0], d = p && argSafe(p) ? p.split('/').slice(0, -1).join('/') : ''
  return d || 'docs/explain'
}

// Local time in New York as 'YYYY-MM-DD-HHMM', for file names.
export function stamp(ms: number): string {
  const f = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
  const p = Object.fromEntries(f.formatToParts(ms).map(x => [x.type, x.value]))
  return `${p.year}-${p.month}-${p.day}-${p.hour}${p.minute}`
}

// The listed command name for cmd: '<plugin>:<cmd>' (plugin defaults to ping-personal), else the bare name;
// any other plugin's '<x>:<cmd>' is never picked, so it cannot take over a button.
export function resolveCmd(names: string[], cmd: string, plugin = 'ping-personal'): string | undefined {
  return names.find(n => n === `${plugin}:${cmd}`) ?? names.find(n => n === cmd)
}

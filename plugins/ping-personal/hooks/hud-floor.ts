// The bypass floor: shell commands that stay denied while bypass is on, in every repo, whatever its deny
// rules say. Pure: no $ access. roots = the session's folders (cwd, repo root); deleting one of them or a
// folder above one is denied.
// ponytail: pattern match on the command text, not a sandbox. A command that hides its target (a variable,
// a pipe into a delete, a script file) gets past it; the repo's own deny rules and the user's eyes still apply.

// Targets that are never deleted recursively: filesystem and drive roots, home, the current or parent
// folder, a bare wildcard.
const ROOT = /^(\/|~|\$\{?home\}?|\$env:userprofile|%userprofile%|\.|\.\.|\*|[a-z]:|\/[a-z]|\/mnt\/[a-z]|\/home|\/users|[a-z]:\/users)$/i
// Folders that hold the repo's history or Claude's own install, config and plugins.
const SELF = /(^|\/)\.(git|claude)$/i
const DISK = /^(format|format\.com|diskpart|mkfs(\.\w+)?|format-volume|clear-disk|initialize-disk|remove-partition)$/i
const RM_UNIX = /^(rm|rmdir)$/i
const RM_PS = /^(remove-item|ri|del|erase|rd|rmdir|rm)$/i

// A path in one shape for comparing: forward slashes, lower case, no quotes, no trailing slash or wildcard,
// and Git Bash '/d/x' as 'd:/x'.
export function normTarget(t: string): string {
  let p = t.replace(/^['"]+|['"]+$/g, '').replace(/\\/g, '/').toLowerCase()
  p = p.replace(/\/+\*?$/, '') || '/'
  const m = /^\/([a-z])(\/.*)?$/.exec(p)
  if (m && p !== '/') p = `${m[1]}:${m[2] ?? ''}`
  return p
}

// Why a recursive delete of `target` is denied, or undefined when it is allowed.
function badTarget(target: string, roots: string[]): string | undefined {
  const t = normTarget(target)
  if (ROOT.test(t) || ROOT.test(target.replace(/^['"]+|['"]+$/g, ''))) return `deletes a root, home or whole folder (${target})`
  if (SELF.test(t)) return `deletes a .git or .claude folder (${target})`
  for (const r of roots.map(normTarget)) if (r && (r === t || r.startsWith(t + '/'))) return `deletes the repo or a folder above it (${target})`
  return undefined
}

// The reason a Bash or PowerShell command is denied under bypass, or undefined when the floor allows it.
export function floorReason(tool: string, input: unknown, roots: string[] = []): string | undefined {
  if (tool !== 'Bash' && tool !== 'PowerShell') return undefined
  const cmd = String((input as { command?: unknown } | null)?.command ?? '')
  for (const seg of cmd.split(/&&|\|\||[;|\n]/)) {
    const tok = seg.trim().split(/\s+/).filter(Boolean)
    if (!tok.length) continue
    const w = tok[0].replace(/^['"&]+|['"]+$/g, ''), rest = tok.slice(1), low = rest.map(x => x.toLowerCase())
    if (DISK.test(w)) return `formats or wipes a disk (${w})`
    if (/^dd$/i.test(w) && low.some(x => x.startsWith('of=/dev/'))) return 'writes over a raw disk (dd of=/dev/...)'
    if (/^gh$/i.test(w) && low[0] === 'repo' && low[1] === 'delete') return 'deletes a GitHub repo (gh repo delete)'
    if (/^git$/i.test(w) && low[0] === 'push' && low.some(x => /^(-f|--force|--force-with-lease(=.*)?|--mirror|--delete|-d)$/.test(x) || x.startsWith('+') || x.startsWith(':')))
      return 'force-pushes or deletes a remote branch (git push)'
    if (/^(npm|pnpm|yarn|bun)$/i.test(w) && low.some(x => /^(uninstall|remove|rm|un)$/.test(x)) && low.some(x => x.includes('@anthropic-ai/claude-code')))
      return 'uninstalls Claude Code'
    if (/^winget$/i.test(w) && low[0] === 'uninstall' && low.some(x => x.includes('claude'))) return 'uninstalls Claude'
    // A recursive delete: Unix rm -r / --recursive, PowerShell -Recurse (any abbreviation), cmd rd /s.
    const unix = RM_UNIX.test(w) && low.some(x => /^-[a-z]*r[a-z]*$/i.test(x) || x === '--recursive')
    const ps = RM_PS.test(w) && low.some(x => /^-r(e(c(u(r(s(e)?)?)?)?)?)?$/.test(x) || x === '/s')
    if (!unix && !ps) continue
    for (const t of rest.filter(x => !x.startsWith('-') && !/^\/[sq]$/i.test(x))) { // flags, and cmd's /s /q
      const why = badTarget(t, roots)
      if (why) return why
    }
  }
  return undefined
}

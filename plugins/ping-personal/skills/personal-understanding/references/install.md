# install mode -- full bootstrap procedure

This playbook covers everything install mode does. Follow the steps in order.
The skill runs the Bash steps; the USER runs the `/plugin` lines.

---

## Step 1 -- Prerequisite checks

Run each check via Bash and report the result:

```bash
node --version       # must be >= 22
pnpm --version       # must be >= 10
python3 --version    # any Python 3.x; needed for merge/validate scripts
git --version        # any recent git
```

If node is missing or < 22, print:
```
Node.js >= 22 is required. Install from https://nodejs.org/
```

If pnpm is missing or < 10, print:
```
pnpm >= 10 is required.
- Preferred (Node ships it): corepack enable pnpm
  (if corepack is present but pnpm still is not found, run: corepack prepare pnpm@latest --activate)
- Or global install: npm install -g pnpm
```
Note (Windows): pnpm may be installed but not on the Bash tool's PATH (Git Bash
sees a different PATH than PowerShell). Check `command -v corepack` first -- if
corepack is present, `corepack enable pnpm` is the fastest fix and needs no
network install.

If python3 is missing, print:
```
Python 3 is required. Install from https://www.python.org/
```

If git is missing, print:
```
git is required. Install from https://git-scm.com/
```

Do NOT proceed past this step until all four pass.

---

## Step 2 -- Layered install detection

Run the full detection sequence from `references/install-detection.md`.

If the plugin is found AND core is already built (`packages/core/dist/index.js`
exists), skip to Step 5 (verify) and report:
```
Plugin already installed and built. Nothing to do.
```

If the plugin is found but core is NOT built, skip to Step 4 (build).

If the plugin is NOT found anywhere, proceed to Step 3.

---

## Step 3 -- Install the plugin (USER must type these)

This skill cannot run `/plugin` commands -- they are Claude Code harness
commands. Print the following message verbatim and stop; wait for the user to
come back after installing.

### For Claude Code users

```
The understand-anything plugin is not installed. To install it, type these
two commands in your Claude Code session (not in the terminal -- in the chat):

  /plugin marketplace add Egonex-AI/Understand-Anything
  /plugin install understand-anything

(marketplace add takes the GitHub repo owner/name; install takes the plugin
name. Adding the marketplace is what triggers the clone.)

After both commands complete, run /personal-understanding install again to
build the core package and verify the install.
```

### For other agent CLIs (Codex, OpenCode, Pi, etc.)

```
The understand-anything plugin is not installed. To install it, run this
one-liner in PowerShell (or adapt for your shell):

  iwr -useb https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.ps1 | iex

After the install script completes, run /personal-understanding install again
to verify.
```

**STOP here. Do not attempt to run these commands via Bash.**

---

## Step 4 -- Build @understand-anything/core

Once the plugin is present (detected in Step 2 or after the user installed
it in Step 3), resolve the plugin root using the PLUGIN_ROOT resolution loop:

```bash
SKILL_REAL=$(realpath ~/.agents/skills/understand 2>/dev/null || readlink -f ~/.agents/skills/understand 2>/dev/null || echo "")
SELF_RELATIVE=$([ -n "$SKILL_REAL" ] && cd "$SKILL_REAL/../.." 2>/dev/null && pwd || echo "")
COPILOT_SKILL_REAL=$(realpath ~/.copilot/skills/understand 2>/dev/null || readlink -f ~/.copilot/skills/understand 2>/dev/null || echo "")
COPILOT_SELF_RELATIVE=$([ -n "$COPILOT_SKILL_REAL" ] && cd "$COPILOT_SKILL_REAL/../.." 2>/dev/null && pwd || echo "")

PLUGIN_ROOT=""
for candidate in \
  "${CLAUDE_PLUGIN_ROOT}" \
  "$HOME/.understand-anything-plugin" \
  "$SELF_RELATIVE" \
  "$COPILOT_SELF_RELATIVE" \
  "$HOME/.codex/understand-anything/understand-anything-plugin" \
  "$HOME/.opencode/understand-anything/understand-anything-plugin" \
  "$HOME/.pi/understand-anything/understand-anything-plugin" \
  "$HOME/understand-anything/understand-anything-plugin"; do
  if [ -n "$candidate" ] && [ -f "$candidate/package.json" ] && [ -f "$candidate/pnpm-workspace.yaml" ]; then
    PLUGIN_ROOT="$candidate"
    break
  fi
done

if [ -z "$PLUGIN_ROOT" ]; then
  echo "Error: Plugin root not found after install. Re-run /personal-understanding install."
  exit 1
fi
```

Then build core:

```bash
cd "$PLUGIN_ROOT" && (pnpm install --frozen-lockfile 2>/dev/null || pnpm install) && pnpm --filter @understand-anything/core build
```

If pnpm is missing at this point:
```
Install Node.js >= 22 and pnpm >= 10, then re-run /personal-understanding install.
```

---

## Step 5 -- Verify

```bash
test -f "$PLUGIN_ROOT/packages/core/dist/index.js" && echo "OK" || echo "FAIL"
```

If FAIL: report the error and suggest re-running install mode.
If OK: report success.

```
install complete
---------------
Plugin root:  <PLUGIN_ROOT>
Core built:   YES
Next step:    Run /personal-understanding onboard to create the knowledge graph.
```

---

## Disk space warning (AD-5)

The plugin cache and pnpm store both land on C:. Measured on a comparable
project: ~431 MB combined.

Before building, check free space on C::

```bash
# Git Bash / MINGW64 on Windows
df -h /c 2>/dev/null | tail -1
```

If C: free space is below 2 GB, print:
```
WARNING: C: drive has less than 2 GB free. The plugin cache and pnpm store
require ~431 MB. Proceeding, but watch for disk-full errors during the build.
```

This is advisory -- do not block the install on low disk space, just warn.

---

## Platform notes (AD-5)

All commands above are written for Git Bash (the Bash tool on Windows). They
work on macOS and Linux without modification.

On Windows, the Claude Code Bash tool runs in Git Bash / MINGW64. Do NOT use
PowerShell syntax (backtick continuation, `$env:VAR`, `Get-ChildItem`) in the
Bash blocks above -- they will fail in the Bash tool context.

ASCII-only rule: never use em-dashes, en-dashes, smart quotes, or Unicode
arrows in any output from this skill. PowerShell 5.1 reads UTF-8 files as
Windows-1252 without a BOM, and non-ASCII bytes produce garbage characters
that break scripts downstream.

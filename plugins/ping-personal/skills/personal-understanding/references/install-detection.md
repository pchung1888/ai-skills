# install-detection -- layered plugin detection (AD-4)

Run these four layers in order. Stop at the first layer that matches and report
which layer matched. If no layer matches, the plugin is not installed.

---

## Layer 1 -- skill resolution (cheapest)

Attempt to call the plugin skill via the Skill tool:

```
Skill(skill: "understand-anything:understand", args: "--version")
```

If the skill resolves without a "skill not found" error, the plugin is installed.
**This is the fastest check** -- it requires no filesystem access.

If this succeeds: report "Layer 1 match -- plugin skill resolves" and stop detection.

If this fails with a "skill not found" / "plugin not installed" error, move to Layer 2.

Note: a tool error (e.g. the plugin skill throws) is different from a resolution
error. A tool error means the plugin IS installed but something inside it failed --
treat that as Layer 1 match and report the error separately.

---

## Layer 2 -- environment variable and well-known paths

Check these paths in order:

```bash
# 1. CLAUDE_PLUGIN_ROOT env var (Claude Code sets this at runtime)
echo "${CLAUDE_PLUGIN_ROOT}"

# 2. Universal symlink created by the install.ps1 one-liner
ls "$HOME/.understand-anything-plugin/package.json" 2>/dev/null

# 3. Claude Code plugin cache glob (covers all installed versions)
ls "$HOME/.claude/plugins/cache/understand-anything/"*/package.json 2>/dev/null | head -1
```

For each path that exists, check that it has both `package.json` AND
`pnpm-workspace.yaml` (to confirm it is the plugin root, not a partial checkout):

```bash
for candidate in \
  "${CLAUDE_PLUGIN_ROOT}" \
  "$HOME/.understand-anything-plugin" \
  $(ls -d "$HOME/.claude/plugins/cache/understand-anything/"*/ 2>/dev/null | head -1); do
  if [ -n "$candidate" ] && [ -f "$candidate/package.json" ] && [ -f "$candidate/pnpm-workspace.yaml" ]; then
    echo "FOUND: $candidate"
    break
  fi
done
```

If a path matches: report "Layer 2 match -- <path>" and record `PLUGIN_ROOT`.
Move to Layer 3 to check build state.

If no path matches: move to Layer 3.

---

## Layer 3 -- package.json + pnpm-workspace.yaml presence

If Layer 2 did not find a result via the well-known paths, run the full
PLUGIN_ROOT resolution loop (same one used in the plugin's own SKILL.md):

```bash
SKILL_REAL=$(realpath ~/.agents/skills/understand 2>/dev/null || readlink -f ~/.agents/skills/understand 2>/dev/null || echo "")
SELF_RELATIVE=$([ -n "$SKILL_REAL" ] && cd "$SKILL_REAL/../.." 2>/dev/null && pwd || echo "")
COPILOT_SKILL_REAL=$(realpath ~/.copilot/skills/understand 2>/dev/null || readlink -f ~/.copilot/skills/understand 2>/dev/null || echo "")
COPILOT_SELF_RELATIVE=$([ -n "$COPILOT_SKILL_REAL" ] && cd "$COPILOT_SKILL_REAL/../.." 2>/dev/null && pwd || echo "")

for candidate in \
  "$SELF_RELATIVE" \
  "$COPILOT_SELF_RELATIVE" \
  "$HOME/.codex/understand-anything/understand-anything-plugin" \
  "$HOME/.opencode/understand-anything/understand-anything-plugin" \
  "$HOME/.pi/understand-anything/understand-anything-plugin" \
  "$HOME/understand-anything/understand-anything-plugin"; do
  if [ -n "$candidate" ] && [ -f "$candidate/package.json" ] && [ -f "$candidate/pnpm-workspace.yaml" ]; then
    echo "FOUND: $candidate"
    PLUGIN_ROOT="$candidate"
    break
  fi
done
```

If a path matches: report "Layer 3 match -- <path>". Move to Layer 4.
If no path matches: move to Layer 4 with `PLUGIN_ROOT` still unset.

---

## Layer 4 -- built vs. unbuilt (core dist check)

This layer checks whether the plugin is built. It is only meaningful if
`PLUGIN_ROOT` was set in Layer 2 or 3.

```bash
if [ -n "$PLUGIN_ROOT" ]; then
  if [ -f "$PLUGIN_ROOT/packages/core/dist/index.js" ]; then
    echo "BUILT: $PLUGIN_ROOT/packages/core/dist/index.js exists"
  else
    echo "UNBUILT: packages/core/dist/index.js missing -- need to run build step"
  fi
fi
```

Report the result:

| State | Report |
|---|---|
| `PLUGIN_ROOT` unset | Plugin NOT installed (no layer matched) |
| `PLUGIN_ROOT` set, dist present | Plugin installed and built |
| `PLUGIN_ROOT` set, dist absent | Plugin installed but NOT built -- needs build step |

---

## Summary output format

After running all layers, report:

```
install detection result
------------------------
Layer 1 (skill resolution): PASS / FAIL
Layer 2 (env/well-known paths): FOUND <path> / NOT FOUND
Layer 3 (resolution loop): FOUND <path> / NOT FOUND / SKIPPED
Layer 4 (core built): BUILT / UNBUILT / N/A

PLUGIN_ROOT: <resolved path or "not found">
Core built:  YES / NO / N/A
```

This output is the input to the install mode decision tree:
- Not found anywhere -> print `/plugin` install instructions (Step 3 of install.md)
- Found but not built -> run build step (Step 4 of install.md)
- Found and built -> report ready, skip to verification (Step 5 of install.md)

---
name: personal-lesson
model: haiku
description: Capture or browse lessons learned across all projects. Trigger on /personal-lesson or natural phrases like "lesson learned", "add a lesson", "capture lesson", "record lesson", "new lesson", "log this lesson", "lessons about". Routes the lesson to the correct domain skill (personal-lesson-ui, personal-lesson-parser, personal-lesson-data, personal-lesson-tooling) based on keyword classification. Browse mode reads both the user-scope lesson files under ~/.claude/lessons/ and the domain skill seed lessons.
user_invocable: true
---

# /personal-lesson -- Master Router

Entry point for the cross-project lessons-learned system. This skill handles
Step 0 (hard-rule gate) and Step 1 (classification) inline, then dispatches to
the correct domain skill for dedup-check and append. Zero lessons are stored
here -- this is a pure dispatcher and browse aggregator.

---

## Capture flow

When you receive a new lesson (user-typed, pasted, or injected by a Stop hook),
follow these steps. If any step says STOP, do not advance.

### Step 0 -- Hard-rule gate

Read the hard rules in the current session's CLAUDE.md and any .claude/rules/*.md
files (using Glob to find them). If the incoming lesson is semantically a
duplicate of a hard rule that already exists there -- for example "never skip
hooks", "never force-push main", "never write to the vault / read-only data
source", "never overwrite .env files" -- reply EXACTLY:

> This is already a hard rule in CLAUDE.md / .claude/rules/. Nothing appended.

Then STOP. Hard rules live in rules files, not lessons files.

The check is a fuzzy semantic match, not a literal string match. Read the rules
files and use judgment. If the lesson merely relates to a hard rule without
duplicating it (e.g. an "Example" or "Context" elaboration), proceed to Step 1.

### Step 1 -- Classify into a domain

Run the deterministic classifier instead of counting by hand:

```bash
python "${CLAUDE_PLUGIN_ROOT}/skills/personal-lesson/lib/classify.py" --text "<the full lesson text>"
# or pipe multi-line text on stdin:
#   printf '%s' "<lesson>" | python ".../lib/classify.py"
# add --explain to see the per-domain hit counts on stderr
```

It prints exactly one domain name (e.g. `personal-lesson-tooling`) -- use that
as the target for Step 2. The rule it encodes: highest count of distinct
case-insensitive substring keyword hits wins; ties break
`data` -> `parser` -> `ui` -> `tooling`; zero hits -> `personal-lesson-tooling`.

**The script parses the baseline keyword table BELOW out of this SKILL.md, so
this table is the single source of truth** -- edit the table here and the
classifier picks it up; there is no second copy to keep in sync.

**Baseline keyword table:**

| Domain skill | Keywords |
|---|---|
| `personal-lesson-ui` | `React`, `Next.js`, `tsx`, `component`, `CSS`, `layout`, `sidebar`, `chart`, `tailwind`, `hydration`, `app router`, `use client`, `server component`, `UI`, `frontend`, `styling`, `page.tsx`, `layout.tsx` |
| `personal-lesson-parser` | `PDF`, `CSV`, `parse`, `ingest`, `extract`, `line item`, `transaction`, `bank statement`, `statement`, `category`, `dedupe`, `scrape`, `cheerio`, `pdfjs`, `pdftotext`, `import`, `staging` |
| `personal-lesson-data` | `vault`, `OneDrive`, `file path`, `read-only`, `boundary`, `absolute path`, `encoding`, `Chinese character`, `gitignore`, `sensitive`, `secret`, `env`, `data contract`, `schema` |
| `personal-lesson-tooling` | `git`, `GitHub`, `gh cli`, `worktree`, `hook`, `settings.json`, `agent dispatch`, `subagent`, `Skill(`, `commit`, `PowerShell`, `pwsh`, `pre-commit`, `npm run`, `coordinator`, `pipeline`, `IIS`, `ASP`, `VB6`, `T-SQL`, `Windows` |

**Project-level keyword override (optional):**

The classifier automatically picks up `.claude/lessons-keywords.md` from the
current working directory (or pass `--keywords-file <path>` explicitly). It uses
the same table format as above: `| domain-skill-name | keyword1, keyword2, ... |`.
Rows for known domains ADD their keywords to that domain's baseline list (EXTEND,
not replace); rows for unknown domains are ignored. No manual merge step -- the
script handles it.

### Step 2 -- Dispatch to domain skill

Call `Skill(skill: "<domain>")` where `<domain>` is the target from Step 1.
Pass the full incoming lesson text as context so the domain skill can perform
its dedup-check and append.

The domain skill owns Step 2 (duplicate check) and Step 3 (append to
`~/.claude/lessons/<domain-short>.md`). Do not attempt to append directly from
this master router.

---

## Gotchas

- **Short-keyword over-match (known, accepted).** Substring matching means
  `ui` matches "g**ui**de", `git` matches "di**git**al" -- so "guide to digital
  transformation" routes to `ui` (tie-broken), not `tooling`. Low-harm: a
  misroute files the lesson under a neighbouring domain, recoverable.
  Word-boundary matching was tried and rejected (misses plurals like
  "transactions" -- a worse failure for this keyword set). If a short keyword
  misroutes often, add a more specific override in `.claude/lessons-keywords.md`
  or hand-correct the dispatch -- Step 1 is a suggestion, not a contract.
- **Step 0 stays model-owned.** Only Step 1 (classification) is scripted. The
  hard-rule gate is a genuine semantic judgment and is NOT delegated to the
  classifier.

---

## Browse mode

Triggered when the user asks "show me all lessons about X", "what lessons relate
to Y", or invokes `/personal-lesson lessons about <topic>`.

1. Glob `~/.claude/lessons/*.md` and read each file that exists.
2. Also read each domain skill's seed section (the Seed Lessons section in
   personal-lesson-ui, personal-lesson-parser, personal-lesson-data,
   personal-lesson-tooling).
3. Search all content for the user's term (case-insensitive substring + semantic
   relevance).
4. Present matching lessons grouped by domain. Quote the lesson text verbatim --
   do not paraphrase.

If `~/.claude/lessons/` does not exist yet (no lessons captured), report that
and show only the seed lessons from the domain skills.

---

## Standard lesson format (reference)

Domain skills append using this format. It is recorded here for reference so any
context that reads only this master skill knows the shape.

```markdown
---

## [SEVERITY] [Short Title]
**Domain:** [ui | parser | data | tooling]
**Discovered:** [YYYY-MM in America/New_York -- never UTC]
**Context:** [1-2 sentences -- when this surfaced]
**Problem:** [What goes wrong without this knowledge]
**Rule:** [Actionable imperative -- concrete thing to do or avoid]
**Example:** [Optional: wrong vs right snippet, error message, or file reference]
```

Severity choices:
- `NEVER` -- hard prohibition; violating causes data loss, security failure, or
  production breakage.
- `CAUTION` -- easy to get wrong; bites even experienced engineers.
- `NOTE` -- worth knowing but rarely catastrophic.

`Discovered` is always the current month in `YYYY-MM` form in **America/New_York**
(EST/EDT) timezone -- never UTC.

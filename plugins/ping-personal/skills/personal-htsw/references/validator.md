# htsw-check.py -- what the validator checks

Loaded from SKILL.md "Files and the validator". Run the script; read this only to understand a failure.

Exit 0 = pass. Exit 1 = fail with detail. The validator checks:
- First-line citation present and well-formed.
- Tier title (PR/QA) or descriptive title (walk) present in the first 15 lines and not a generic stock-template heading.
- **TL;DR section present right after the tier title with 2-4 icon-prefixed bullets** (PR/QA) **or descriptive-label TL;DR with navigation-icon bullets** (walk).
- **HOW-THIS-WORKS section present in PR, QA, AND walk renderings** at `###` level, with one of the allowed header variations. Walk mode may prefix with `⚙` (e.g. `### ⚙ How this shit works`).
- **Flowchart warnings (advisory, stderr-only, does NOT fail the build):**
  - Mermaid block found in a **persisted** doc → portability warning (mermaid renders only in mermaid-aware viewers; ASCII flowchart is the safer default).
  - HTML tags other than `<br/>` inside mermaid node labels → known-breaker warning (Confluence's plugin will fail; GitHub may render).
  - HTML inside mermaid edge labels (`|...|`) → known-breaker warning (edge-label parser is stricter than node-label parser).
  - `#` inside mermaid edge labels → known-breaker warning (mermaid treats `#` as a comment char).
- **Deeper-dive section ("Where to slow down" or variation) present when trigger fires** — ≥ 5 files in the diff, or any `.dll` / `.cache` / `.pdb` / `.exe` / `.bin` marker, or a `Bin N -> M` git-stat binary line. Trigger detection is structural; below the threshold the section is optional.
- **Evidence-and-suggestion contract**: every ⚠ / 🔴 in the body sections is paired with an evidence marker (file:line, RFC, quoted source, SQL/HTTP observation) and a suggestion-arrow (`→ fix:`, `→ suggestion:`, `→ optional:`, `→ next:`, `→ ask:`).
- Status icons present where required.
- Tables have Status columns where required.
- Boss output has NO icons, NO tacos, NO banned words.
- Length is under target (600 pr / 700 qa / 400 boss / 1800 baby inline / 3000 baby persisted).
- Baby output is story-first: Cast table appears in the last ~30% of the doc (byte offset >= 65%); every Cast term has a bold inline-intro in story body before the table; a vertical story-rhythm block is present (plain code fence, >= 5 pipe connectors, >= 5 parenthetical-analogy lines); audience declaration `_For: ..._` is present within 5 lines of citation; no sanitization smell words (`easy`, `simple`, `just`, `basic`, `don't worry`); no baby-talk words (`sweetie`, `honey`, `ok kiddo`, `buddy`, `lil'`).

This is what makes the contract real. Without the validator, the rules are aspirational; with it, the rules are checkable.

**Why Python and not PowerShell?** The earlier version was `.ps1` — Windows-only. The skill is now portable across OSes, so the validator is too. Python 3 is preinstalled on macOS and most Linux distros, and on Windows it's a one-line install. Single script, single command, every OS.

# Eval Plan: personal-htsw

> Follows `personal-dashboard/knowledge/wiki/concepts/agent-evals-playbook.md`.
> This is the **approved-shape teaching example** for the skill-evals goal. Every
> other ping-personal skill's `evals/` folder mirrors this structure.

## Target Behavior

Given a source (a file path, or the current conversation) and a mode
(`walk` / `pr` / `qa` / `boss` / `baby` / `code-explain` / `now`, default `walk`), personal-htsw produces an
**inline** explanation in the htsw voice that conforms to that mode's output
contract: a first-line citation (an `_Explaining: ... purpose: <mode>_` line), a
title, a TL;DR block with 2-4 icon bullets, the mode-appropriate body sections,
the evidence-and-suggestion rule on every WARN/BAD-tier bullet, the per-mode length cap,
and the boss-mode banned-word / icon-free rules. It never writes files.

The skill ships its own contract checker, `htsw-check.py`, which is the code
grader. This eval verifies (a) the skill is structurally intact and (b) the
checker still measures what it claims (accepts good output, rejects bad output).

## Failure Modes

| ID | Failure | Why It Matters | Grader |
| --- | --- | --- | --- |
| F01 | First-line citation missing or malformed | Downstream tooling + the checker key off it; breaks every mode | code |
| F02 | TL;DR missing or not 2-4 icon bullets | TL;DR is the scannable contract the owner relies on | code |
| F03 | Rendering exceeds the per-mode length cap | Long renderings defeat the "fast brief" purpose | code |
| F04 | Boss mode leaks engineering jargon or status icons | Boss output goes to clients; jargon/icons break the polish contract | code |
| F05 | A WARN/BAD-tier bullet has no evidence + no fix-arrow | Verdicts without evidence are guessing (Honesty Protocol) | code |
| F06 | A documented mode silently dropped from SKILL.md | Users lose a mode without warning | code (structural) |
| F07 | A mode's reference playbook missing from `references/` | The mode's full rules vanish | code (structural) |
| F08 | `htsw-check.py` regresses (passes bad output or rejects good) | A broken grader gives false confidence | code (calibration) |
| F09 | baby mode analogy *replaces* jargon instead of pairing with it | Reader never learns the real vocabulary (the whole point of baby) | judge |
| F10 | Explanation reads beginner-friendly but is technically wrong | Confident-but-wrong teaching is worse than blank | judge |
| F11 | walk mode launders the salt or adds a pr/qa-style verdict | Loses the memorable teaching tone / mislabels as a review | judge |

## Eval Cases

| ID | Input | Expected Behavior | Must Not Happen |
| --- | --- | --- | --- |
| E01 | `fixtures/good-baby.md` (real passing baby rendering) | `htsw-check.py` exits 0 | Grader rejects a conforming rendering |
| E02 | `fixtures/bad-no-citation.md` | `htsw-check.py` exits 1 (F01) | Grader accepts output with no citation |
| E03 | `fixtures/bad-boss-banned-word.md` | `htsw-check.py` exits 1 (F04) | Grader accepts boss output with banned jargon |
| E04 | `SKILL.md` frontmatter + body | name=personal-htsw, all 7 modes documented | A mode is missing from the docs |
| E05 | `references/` directory | walk/pr/qa/boss/baby/code-explain/now playbooks all present | A mode's playbook is absent |
| E06 | `htsw-check.py` | file exists and is runnable | Checker deleted/renamed without updating the eval |
| E07 (judge) | a fresh baby-mode rendering | analogy pairs with jargon; beginner-correct | analogy replaces jargon; factual error |
| E08 | `references/examples/code-explain-examples.md` | `htsw-check.py --examples-file` exits 0 | Checker rejects a conforming code-explain rendering |

## Graders

### Code Graders (`eval.ps1`)

- `skill_frontmatter`: SKILL.md has `name: personal-htsw` + a description line.
- `seven_modes_documented`: walk, pr, qa, boss, baby, code-explain, now all named in SKILL.md.
- `reference_playbooks_present`: walk/pr/qa/boss/baby/code-explain/now `.md` all exist in `references/`.
- `checker_present`: `htsw-check.py` exists.
- `checker_accepts_good`: `htsw-check.py` exits 0 on `fixtures/good-baby.md` (E01).
- `checker_rejects_bad`: `htsw-check.py` exits 1 on every `fixtures/bad-*.md` (E02, E03).
- `checker_accepts_code_explain_example`: `htsw-check.py --examples-file` exits 0 on `references/examples/code-explain-examples.md` (E08).

### Model Judge (`judge-rubric.md`)

- `baby_analogy_quality`: does baby-mode output pair every jargon term with an
  everyday analogy (not replace it), and is the explanation technically correct?
  Reason-first scoring, run only on `baby`/`walk` renderings (F09, F10, F11).

### Human Spot Checks

- Review a real baby-mode rendering for an unfamiliar audience (calibrates the judge).
- Confirm boss-mode output is genuinely client-safe before sending externally.

## Baseline Run

- date: 2026-05-31
- agent version: personal-htsw @ plugin 0.5.0
- model: n/a (code grader is deterministic)
- result summary: `eval.ps1` -> all code graders PASS; fixtures calibrated
  (good-baby exit 0, both bad fixtures exit 1).

## Ship Gate

- No code-grader failure (`eval.ps1` exits 0).
- Locked good fixture (`good-baby.md`) must keep passing `htsw-check.py` (no regression).
- Judge may flag taste issues for follow-up, but a code-grader red blocks ship.

## now mode (2026-10-09)

- seven_modes_documented: `now` named in SKILL.md (was six_modes_documented).
- reference_playbooks_present: references/now.md exists.
- now_playbook_present: now.md carries Verdict, Flowchart, the When / Your job / Time table, Why this shape, TL;DR.
- now_chat_only: the modes-table row for `now` says it writes no files.
- deep_html_documented: SKILL.md documents `now --deep --html <path>`; now.md asks for per-phase tables, a Glossary, EXTRACTED / INFERRED labels and a diagram.
- deep_writes_md_and_html: now.md says the Markdown goes next to `<path>`, is rendered with md-to-html.py `--out <path>`, and the link is printed.
- output_path_not_a_source: the source-table row for `now --deep --html <path>` says the source is the current conversation and `<path>` is never read as a source.
- now_stays_chat_only: the `now` modes-table row still says it writes no files, and now.md keeps plain now chat-only.

## Walk engine (2026-11-01)

The walk page engine is `walk/walk-build.py` (spec JSON to HTML) and `walk/walk-check.py` (scores the page).
Each case builds `fixtures/walk/phase0.walk.json` into a temp folder, changes one thing, and cleans up.

- walk_build_good: the unchanged spec builds, and `walk-check.py --spec` exits 0 with `SCORE brief N/N`, both N equal. Proves the good path is not rejected.
- walk_check_points_short: a point over 22 words makes `walk-check.py` exit 1 and print `FAIL points-short`.
- walk_check_no_semicolons: a semicolon in a point fails `no-semicolons`.
- walk_check_names_match: one menu label edited in the built HTML fails `names-match-4-places`.
- walk_check_walk_links: the Back link removed from step 1 in the built HTML fails `walk-links-every-step`.
- walk_check_ascii_only: a non-ASCII character added to the built HTML fails `ascii-only`.
- walk_check_answers_no_next: a Next link added to the answers section fails `answers-no-next`.
- walk_build_rejects_bad_id: a step id holding a quote makes `walk-build.py` exit non-zero with "must match".
- walk_build_rejects_svg_script: an `svg_file` containing `<script` makes `walk-build.py` exit non-zero, and the message names `<script`.
- walk_build_rejects_inline_svg_script: the same refusal for an inline `svg` block (not only `svg_file`).
- walk_build_rejects_svg_onload: `<svg/onload=` (slash instead of a space) is refused as an event handler.
- walk_build_rejects_svg_entity_js: `java&#115;cript:` in an attribute is decoded first, then refused as `javascript:`.
- walk_build_rejects_svg_external_href: an entity-encoded `javascript:` href on `<use>` is refused as an external href.
- walk_build_rejects_svg_foreignobject: `<foreignObject>` in an svg is refused.
- walk_build_rejects_duplicate_step_id: two steps with the same id exit non-zero with "duplicates".
- walk_build_rejects_reserved_id: a step id `flow` exits non-zero with "reserved id".
- walk_check_unique_ids: an id used twice in the built page fails `unique-ids`.
- walk_build_rejects_svg_escape: an `svg_file` path `../x.svg` makes `walk-build.py` exit non-zero (outside the spec folder).
- walk_hv_draw_keeps_dash: `walk.js` saves a hero path own stroke-dasharray/dashoffset and restores them on complete and in `bail()`.
- walk_hidden_rules_in_hid: every `.motion <sel>{opacity:0}` rule in `walk.css` is covered by the `HID` list in `walk.js`.
- walk_docs_wired: SKILL.md and `references/walk-page.md` name both scripts, and SKILL.md and `references/now.md` point at `walk-page.md`.
- walk_failsafe_reveal: walk.js keeps `bail()` (removes the motion class), the `rescue()` timer and the `an()` wrapper that calls `bail()` on an anime.js error.
- walk_no_default_when: a question with its `when` removed has no timing line and no "Final today"; question 2 keeps its own.
- walk_ba_options: a `ba` block with `"kind": "options"` renders `ba opts` and the `or` divider, with no arrow inside the block.
- walk_stats_static: the built `.stat .v` values equal the spec values, and walk.js has no count-up code.
- walk_hero_map_labels: the hero map has one `hm-lbl` per outcome, and its caption names the total step count and "1 decision".
- walk_lead_takeaway_short: a 25-word lead fails the must rule `lead-takeaway-short` (limit 22).
- walk_takeaway_reads_remember_card: an analogy that echoes the lead does not make `idea-takeaway-not-echo` MISS when the Remember takeaway is distinct (the rule reads the paragraph inside `.remember`).
- walk_takeaway_echo_misses: a Remember takeaway that repeats the lead makes `idea-takeaway-not-echo` MISS and name the step.
- walk_lead_claim_regex: the lead "The team is ready to ship on Friday." passes `idea-lead-is-claim`; "The log file is a list of changes." misses.
- walk_no_placeholder_text: a decision containing "to be set" fails the must rule `no-placeholder-text`.
- walk_no_decision_no_strip: an empty `decision` renders no "Decision needed" text box or note; the outcome pills stay under "Possible outcomes".
- walk_hero_visual_renders: a spec with `hero_visual` puts the svg (role img, its own aria-label, hv- classes) and the caption in the hero, drops the mini step map, and `idea-hero-visual` passes.
- walk_hero_visual_rejects_script: a `hero_visual` svg containing `<script` makes `walk-build.py` exit non-zero, and the message names `<script`.
- walk_hero_visual_rejects_no_role: a hero svg without `role="img"`, or with an aria-label under 8 characters, is refused.
- walk_hero_visual_rejects_onload: a hero svg with an `onload=` handler is refused.
- walk_hero_visual_rejects_external_href: a hero svg with `<image href="http://...">` is refused.
- walk_hero_visual_rejects_no_viewbox: a hero svg without a `viewBox` is refused.
- walk_hero_visual_clear_errors: a missing `svg_file` key, a missing file and a non-ASCII file each give one `walk-build: hero_visual ...` message and no traceback.
- walk_hero_text_size: hero svg text under 22 units (scaled by viewBox width / 560) is a MISS on `hero-text-size`; the shipped hero passes; an svg without role is a MISS on `idea-hero-visual`.
- walk_hero_visual_absent_keeps_map: without `hero_visual` the mini step map stays in the hero and `idea-hero-visual` is MISS.
- walk_alongside_dashed: a step with `alongside` gets a dashed box, a tag and the legend line in both charts; 5 words is refused; a lead saying "in parallel" without the field is a MISS on `alongside-stated`.
- walk_alongside_decision_refused: `alongside` on the decision step, or over 24 characters, is refused with one clear message.
- walk_alongside_edge_caption: the arrow out of an alongside box has class `al-edge`; the arrows caption (with the dashed-step line) comes before the chart; the legend has a dashed swatch; the rail item has class `al`; none of these show without an alongside step.
- walk_alongside_stated_regex: a lead saying "while others go on" without the field is a MISS; the word "alongside" only inside an inline svg block does not trigger it.
- walk_seen_toggle_markup: the built menu has one `seen-tog` button per step (aria-pressed, aria-label, not inside the link) and a `reset-prog` button.
- walk_seen_unmark_reset: walk.js unmark saves the seen key, reset removes only that key, and no `confirm(` or `alert(` appears.
- walk_seen_dwell_constant: `DWELL_MS` is 4000 and the dwell timer uses it.

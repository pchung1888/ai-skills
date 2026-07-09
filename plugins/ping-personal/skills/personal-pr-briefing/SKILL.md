---
name: personal-pr-briefing
model: sonnet
description: Update a PR/MR description with a reviewer briefing -- which files matter most and in what order, what each load-bearing change does, and what is safe to skim. Trigger on /personal-pr-briefing, "pr briefing", "update the PR description for reviewers", "show the reviewer what files to read first", "make the PR description reviewer-friendly". Works with gh (GitHub) and glab (GitLab); portable equivalent of the start-/sapi-pr-review-briefing host skills.
---

# /personal-pr-briefing

Give the reviewer a priority map, not a catalog. The deliverable is an
updated PR/MR description containing a briefing section that names the 1-3
load-bearing files first, explains why each matters in one sentence, and
tags mechanical churn as skim-eligible.

## Procedure

1. **Locate the PR.** `gh pr view --json number,url,body` (or `glab mr view`)
   for the current branch; if none exists, say so and stop -- this skill
   updates descriptions, it does not open PRs.
2. **Read the real diff** (`gh pr diff` / `git diff <base>...HEAD`), not the
   commit messages -- the briefing must be independent analysis of the
   change, not a paraphrase of the author's own writeup.
3. **Rank the files.** Load-bearing = logic, contracts, security boundaries,
   anything a wrong review would let a bug through. Skim-eligible = generated
   output, lockfiles, renames, formatting, version bumps. Cap the "read
   first" list at 3.
4. **Write the briefing section** between idempotency markers so re-runs
   replace rather than duplicate:

   ```markdown
   <!-- reviewer-briefing:start -->
   ## Reviewer briefing
   **Read these first:**
   1. `<file>` -- <why this file decides the review>
   2. `<file>` -- <one sentence>
   **Skim-eligible:** `<files>` -- <why (generated / mechanical)>
   **The one question to answer:** <the single judgment the reviewer is really being asked to make>
   <!-- reviewer-briefing:end -->
   ```

5. **Update the description** with `gh pr edit --body-file` / `glab mr update
   --description`, PRESERVING everything outside the markers. Quote the PR
   URL and confirm the section landed by re-reading the body.

## Boundaries

- Never overwrite the existing description body outside the markers.
- Never merge, approve, close, or comment-review -- description only.
- Claims in the briefing follow the honesty rules: a "why it matters"
  sentence must trace to the diff; if a file's purpose is unclear, say
  "purpose unclear from the diff" rather than inventing one.

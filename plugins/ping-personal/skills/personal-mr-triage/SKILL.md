---
name: personal-mr-triage
model: sonnet
description: Triages reviewer comments on a merge request or pull request - verifies each finding against the code with evidence, then fixes it or pushes back with reasons, and drafts plain-language replies addressed to the reviewer. Use when the user says /personal-mr-triage, "triage the review comments", "go through the MR feedback", "answer the reviewer", or "handle the PR review comments". Works with glab (GitLab) and gh (GitHub). Posts nothing until the user approves.
---

# /personal-mr-triage

Turn a pile of review comments into verified decisions. A reviewer finding is a
claim to check, not an order: verify it against the code, then fix it or explain
why not. Replies go to the reviewer, in plain language, and only after the user
approves them.

## Workflow

Copy this checklist and tick it off:

```text
MR triage:
- [ ] 1 Comments collected
- [ ] 2 Each finding verified with evidence
- [ ] 3 Each finding decided: fix or push back
- [ ] 4 Fixes made and checked
- [ ] 5 Replies drafted, shown to the user
- [ ] 6 User approved; replies posted
- [ ] 7 Fixes pushed; remote hash shown
```

1. **Collect.** List every open review comment with its author, file and line:
   `glab mr view <id> --comments` (GitLab) or `gh pr view <id> --comments` plus
   `gh api repos/{owner}/{repo}/pulls/<id>/comments` for line comments (GitHub).
   Done when each comment has an ID in a numbered list.
2. **Verify.** For each finding, open the cited code and check the claim. Record
   the evidence as `file:line` or quoted command output. A finding you cannot
   confirm or refute is UNKNOWN, not agreed. Done when every finding has
   CONFIRMED, REFUTED or UNKNOWN plus evidence.
3. **Decide.** CONFIRMED -> fix. REFUTED -> push back, with the evidence. UNKNOWN
   -> ask the reviewer one precise question. Style-only preferences are the
   reviewer's call unless they conflict with a project rule; then cite the rule.
4. **Fix.** Make the smallest change that resolves the finding, run the
   project's tests or checks, and quote the output.
   If the check fails, return to Step 2 for that finding: the first diagnosis was wrong.
5. **Draft replies.** One reply per comment, addressed to the reviewer:
   what you checked, what you found, what you changed (commit or file:line) or
   why you left it. Never mention the user's private chat or this assistant
   session, because the reviewer never saw it and it reads as hiding behind it.
   Show all drafts to the user in one list.
6. **Post only after approval.** The user may edit or drop any reply. Post with
   `glab mr note` / `gh pr comment` (or a review reply) exactly as approved.
7. **Push and prove.** Push the fixes, then show the remote commit hash from
   `git ls-remote origin <branch>` before saying "pushed".

## Reply shape

Illustrative, adapt the wording:

```text
Thanks - confirmed. `parseRate()` divided before the null check (rates.ts:42).
Fixed in a1b2c3d: the guard now runs first, and the new test covers a null rate.
```

```text
I checked this one: the value is clamped one level up in normalize() (rates.ts:17),
so it cannot be negative here. Happy to add a comment saying so if that helps.
```

## Boundaries

- Never post, resolve threads, approve or merge without the user's explicit OK,
  because a posted reply speaks for the user in front of their team.
- Never agree with a finding you have not verified, and never refute one
  without evidence - an unverified "fixed" costs the reviewer a second round.
- Never claim pushed or fixed without the remote hash and the check output.

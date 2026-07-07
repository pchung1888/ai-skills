---
name: personal-jira-sync
model: sonnet
description: Reflect finished work back into the Jira ticket -- update the description with what shipped, add a closeout comment, attach or reference evidence (screenshots, PR links), or split a progress doc into subtasks. Trigger on /personal-jira-sync, "update the ticket with what we changed", "sync ST-NNN", "put this on the Jira", "create subtasks from the progress file", "update the description to reflect what is done". Requires the Atlassian MCP connection; degrades to a paste-ready block when it is absent.
---

# /personal-jira-sync

Close the loop between the repo and the ticket so the Jira story reflects
what actually shipped, with evidence.

## Procedure

1. **Resolve the issue key.** From the argument, else the branch name
   (`topic/690-...` and `feature/ST-690-...` both mean `ST-690`), else ask.
2. **Preflight the MCP.** Check the Atlassian tools are reachable this
   session (ToolSearch for `getJiraIssue` / `editJiraIssue`). If absent:
   produce the full update as a PASTE-READY block (description text +
   comment text + evidence list) and stop -- degraded mode is a success
   mode, not a failure.
3. **Gather what shipped.** The active `docs/progress/*-progress.md`, the
   PR (`gh pr view` / `glab mr view`), and the diff stat. Claims that go on
   the ticket must trace to one of these -- the ticket is client-visible;
   nothing unverified goes on it.
4. **Read the issue first** (`getJiraIssue`), then apply the requested sync:
   - **Description update:** append/replace a "What shipped" section --
     summary, key file changes in plain English, PR link, verification
     evidence. Preserve the original requirement text; never clobber the
     description wholesale.
   - **Closeout comment:** shorter form of the same via
     `addCommentToJiraIssue`.
   - **Screenshots:** if a capture exists on disk, reference it and tell
     Ping which file to attach (MCP attachment support varies); do not
     claim an attachment happened unless the tool result confirms it.
   - **Subtask split:** parse the progress/plan doc's remaining items into
     `createJiraIssue` subtasks under the parent, one per actionable item,
     quoting each created key.
5. **Prove it.** Re-read the issue and quote the changed field/comment ID.

## Boundaries

- Never transition issue status (In Progress -> Done etc.) unless Ping
  explicitly asks -- status is a workflow decision, not a sync.
- Never create or edit issues outside the resolved key's project.
- Wording on the ticket is professional register (personal-htsw boss-mode
  rules: no icons, no slang) -- clients read Jira.

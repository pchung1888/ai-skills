---
name: personal-wayfinder
description: Plan a piece of work too big for one session as a shared map of decision tickets, then resolve them one at a time until the way to the destination is clear. Company work goes on Jira, personal work on GitHub issues, and anything else in local Markdown under docs/wayfinder/. Each ticket is research (personal-online-research), a prototype (personal-prototype), a grilling (personal-grill-me) or a task (personal-wizard for hands-on steps). Trigger on /personal-wayfinder <loose idea> to chart a map, or /personal-wayfinder <map> to work the next ticket.
disable-model-invocation: true
argument-hint: "A loose idea to chart, or a map to work through"
---

# Wayfinder

Adapted from Matt Pocock's `wayfinder` skill (MIT, see `THIRD-PARTY-NOTICES.md`). This version
picks Jira, GitHub or local Markdown by where the work lives, and calls ping-personal skills.

A loose idea has arrived. It is too big for one session, and the way from here to the
**destination** is not visible yet. Wayfinding finds that way before anyone charges at the
destination. It charts the way as a **map** of **decision tickets**: questions whose answer is
a decision, not a slice of the build. Then it works those tickets one at a time.

The destination can be a spec to hand off, a decision to lock before planning, or a change
made in place, such as a data migration. Name it first, because it fixes the scope.

## In your daily work

| Situation | Tracker | Example |
|---|---|---|
| A host-app change that touches pages, DLLs and stored procedures | Jira | "Move client X's report to the new pricing source" |
| A personal-plugin feature or a side project | GitHub issues | "Rebuild the ping-hud goals pane" |
| An idea with no repo yet, or the tracker is not reachable | Local Markdown | "Should I build a trade-journal app?" |

## Pick the tracker

Use the first rule that applies, then write the tracker's name in the map's **Notes**, so every
later session uses the same one.

1. The user names it in the request ("on Jira", "on GitHub", "local").
2. The repo's `origin` remote (`git remote get-url origin`) is on `github.com`: **GitHub**.
3. Any other remote, which is company work: **Jira**.
4. No repo, or the tracker's tools are not reachable this session: **local Markdown**.

## Plan, don't do

Wayfinder plans. Each ticket settles a decision. The map is done when nothing is left to decide
before someone builds the thing. The pull to start building usually means you reached the edge
of the map. Hand off then. A map's **Notes** can say otherwise, but only when the user writes that.

## Refer by name

Every map and ticket has a **name**: its title. In everything the user reads, refer to it by that
name, with the id or link inside it. Never write a bare list of ids such as `#42, #43, #44`.

## The map

The map is one issue, the canonical record. Its tickets are its children. The map is an
**index**, not a store: each decision lives in its own ticket, and the map gives a one-line gist
and a link.

### The map body

```markdown
## Destination

<what reaching the end of this map looks like: the spec, decision or change. One or two lines.>

## Notes

<tracker and project; domain; skills every session should load; standing preferences>

## Decisions so far

- [<closed ticket title>](link): <one-line gist of the answer>

## Not yet specified

<fog: in-scope questions you can see coming but cannot yet phrase sharply>

## Out of scope

<work ruled beyond the destination, one line each with the reason>
```

### Tickets

Each ticket is a child of the map. Its body is the question, sized to one session:

```markdown
## Question

<the decision or investigation this ticket resolves>
```

Each ticket carries one type label: `research`, `prototype`, `grilling` or `task` (see Ticket
types). The map carries the map label. Never add triage or ready-to-build labels: these are
decisions, not build work.

A session **claims** a ticket by assigning it to the user **before any work**, so a parallel session
skips it. An open, unassigned ticket is unclaimed.

A ticket is **unblocked** when every ticket blocking it is closed. The **frontier** is the open,
unblocked, unclaimed children: the edge of what is known. The answer is not in the body. It goes
in a resolution comment when the ticket closes.

## Tracker operations

### Jira (company work)

Jira tickets are visible to the company, and sometimes to clients. So:

- **Confirm before the first write in a session.** Show the user the map and tickets you will
  create, or the ticket you will close, and wait for their OK.
- **Ask for the project key** the first time, and record it in Notes. Never assume one.
- **Professional register** on every Jira text: no icons, no slang (htsw boss-mode rules).
- **Preflight the tools.** Look up the Atlassian Jira tools this session (in Claude Code,
  ToolSearch for `createJiraIssue`). If they are not reachable, use local Markdown and say so.

| Operation | How |
|---|---|
| Map | An Epic, if the project's issue types include one (check the project's issue-type metadata); label `wayfinder-map` |
| Ticket | A child of the Epic through the parent field; label `wayfinder-<type>`. With no Epic type, link the ticket to the map with a "relates to" link |
| Blocking | An issue link of the project's blocking type. Read the link types first and use the exact name shown |
| Claim | Set the assignee to the user's account id (from the Atlassian user-info tool) |
| Frontier | JQL: `parent = <MAP-KEY> AND statusCategory != Done AND assignee is EMPTY`, then drop tickets with an open blocker |
| Resolve | Add the resolution as a comment. Read the ticket's transitions and move it to the done status. Update the map's description |

### GitHub issues (personal work)

| Operation | How |
|---|---|
| Labels | Create once if missing: `gh label create wayfinder:map`, and `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task` |
| Map | `gh issue create --label wayfinder:map --title <name> --body-file <file>` |
| Ticket | `gh issue create --label wayfinder:<type> ...`, then make it a sub-issue of the map: `gh api -X POST repos/<owner>/<repo>/issues/<map-number>/sub_issues -F sub_issue_id=<ticket id>`. The id comes from `gh api repos/<owner>/<repo>/issues/<number> --jq .id`. If that call fails, write `Part of #<map-number>` in the ticket body |
| Blocking | Try `gh api -X POST repos/<owner>/<repo>/issues/<blocked-number>/dependencies/blocked_by -F issue_id=<blocker id>`. If that call fails, write `Blocked by: #<number>` lines in the body |
| Claim | `gh issue edit <number> --add-assignee @me` |
| Frontier | The map's open sub-issues with no assignee, minus any with an open blocker |
| Resolve | `gh issue comment <number> --body-file <file>`, then `gh issue close <number>`, then update the map body with `gh issue edit` |

The sub-issue and dependency API calls depend on the repo and the `gh` version. If either fails,
use the body lines and say so. Never report a link that the tool result did not confirm.

### Local Markdown (no tracker)

| Operation | How |
|---|---|
| Map | `docs/wayfinder/<map-slug>/MAP.md` |
| Ticket | `docs/wayfinder/<map-slug>/tickets/0001-<slug>.md`, with frontmatter `type`, `status: open`, `assignee:` and `blocked_by: [0002]` |
| Claim | Set `assignee: ping` |
| Frontier | Tickets with `status: open`, no assignee, and every `blocked_by` ticket closed |
| Resolve | Append `## Resolution`, set `status: closed`, add a line to Decisions so far |

## Ticket types

Every ticket is **with the user** (they answer for themselves, live) or **solo** (the agent drives it
alone). A with-user ticket resolves only through that exchange. Never answer the user's side yourself.

- **Research** (solo): find a fact a decision waits on. For web knowledge, a subagent calls the
  Skill tool with `ping-personal:personal-online-research`. For this repo or another local
  codebase, send a `ping-personal:iris` subagent. Put a short answer in the resolution comment.
  Put long findings in `docs/wayfinder/<map-slug>/research/<ticket>.md` and link them.
- **Prototype** (with the user): make a cheap, rough artifact to react to: an outline, a mockup or
  stub code. Call the Skill tool with `ping-personal:personal-prototype`. Link the artifact.
  Use it when "how should it look or behave" is the key question.
- **Grilling** (with the user): a conversation, and the default type. Call the Skill tool with
  `ping-personal:personal-grill-me`, with the words "with docs", so settled terms and decisions
  land in `docs/glossary/`.
- **Task** (solo or with the user): hands-on work that must happen before a decision can be made,
  such as getting access or moving sample data. Do it yourself when you can. When the steps are
  on a machine or screen you cannot reach, call the Skill tool with `ping-personal:personal-wizard`.
  The resolution records what was done and any facts later tickets need.

## Fog of war

The map is deliberately incomplete. Do not chart what you cannot yet see. **Not yet specified**
holds the dim view: questions you know are coming but cannot phrase sharply yet. Resolving a
ticket clears fog ahead of it, and newly sharp questions become tickets.

**Fog or ticket?** Ask whether you can state the question precisely now, not whether you can answer it.

- **Ticket** when the question is sharp, even if it is blocked.
- **Not yet specified** when you cannot phrase it that sharply yet. Do not pre-slice fog into
  ticket-sized pieces. One patch may become several tickets, or none.

## Out of scope

The destination fixes the scope. Work beyond it is **out of scope**: not fog, never a ticket.
When an existing ticket turns out to sit beyond the destination, close it and add one line to
**Out of scope** with the reason and a link. Keep it out of Decisions so far.

## Invocation

Two modes. Either way, **never resolve more than one ticket per session**, except research tickets.

### Chart the map (a loose idea)

1. **Name the destination.** Call the Skill tool with `ping-personal:personal-grill-me`, with
   "with docs", to pin down what this map is heading for.
2. **Map the frontier.** Grill again, breadth-first: fan out across the whole space to surface
   the open decisions and the first steps. If no fog appears and the whole job fits one session,
   you do not need a map. Stop and ask the user how to proceed.
3. **Pick the tracker** (see Pick the tracker). For Jira, confirm before writing.
4. **Create the map**: Destination and Notes filled in, Decisions so far empty, fog sketched.
   In Notes, name the tracker, the project or repo, and the skills every session should load.
5. **Create the tickets you can state now** as children of the map. Then wire blocking in a
   **second pass**, because tickets need ids before they can reference each other.
6. **Start the research.** For each research ticket, start a subagent as described in Ticket types.
7. Stop. Charting is one session's work. It resolves nothing by hand.

### Work through the map (a map)

1. Load the map: the low-detail view, not every ticket body.
2. Choose the ticket. Use the one the user named, or else the first frontier ticket. **Claim it
   before any work.**
3. Resolve it as its type label says. The body never states the type. Fetch any related ticket's
   body when you need it. Load the skills the map's Notes name.
4. Record the resolution: comment, close, and add a line to the map's Decisions so far.
5. Add newly surfaced tickets (create, then wire). Turn fog the answer made sharp into tickets,
   and remove it from Not yet specified. If a ticket now sits beyond the destination, rule it
   out of scope. If the decision invalidates other tickets, update or close them.

The user may run unblocked tickets in parallel sessions. Expect other sessions to edit the tracker too.

## Writing

Map and ticket prose follows the htsw Explaining sentences rules (20 words or fewer per
sentence, context first) and the personal-unslop pass. Jira text also follows boss-mode register.

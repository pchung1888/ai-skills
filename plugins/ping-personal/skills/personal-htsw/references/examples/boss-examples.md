# boss-examples.md — two scenarios, always clean, with presentation tables

Boss output is always professional. No quality tiers. Two distinct shapes depending on source:

```
Source = single feature spec     ──►  Feature pitch  (3-bullet + impact-at-a-glance table)
Source = multi-phase plan        ──►  Plan walkthrough  (phase-shape table + ASCII phase-bar)
```

Tables are the primary visual aid for boss output. They earn their place because sponsors scan tables in two seconds. No status icons (🔴/⚠/🟢), no 🌮, no emojis — boss is the only mode where visual structure comes from headings + tables, not iconography.

---

## Feature pitch (single-feature source) — with impact-at-a-glance table

**Source:**
> Add a session-timeout warning modal: at 13 min of inactivity, show "You'll be signed out in 2 min. Stay signed in?" with a button that resets the timer. If no response in 2 min, sign out + redirect to login with a "signed out due to inactivity" toast.
>
> Effort: 3d frontend + 1d backend + 1d QA.
> Today: ~40 inactivity-related support tickets/month. Average user spends 8-12 min reconstructing lost work after a silent timeout.

**Boss rendering:**

> This feature eliminates the leading category of "I lost my work" support tickets by giving users a clear two-minute heads-up before any session times out — turning an invisible system action into a visible, recoverable moment.
>
> **Impact at a glance:**
>
> | Metric | Today | After this feature |
> |---|---|---|
> | "I got logged out" support tickets | ~40 / month | Projected <10 / month |
> | Avg user time spent reconstructing lost work | 8-12 minutes | 0 minutes |
> | User survey score on perceived reliability | 7.2 | Projected 8.0+ |
>
> **What we're building:** Today, users are silently signed out after inactivity and don't know why. The fix adds a two-minute warning with a one-click "Stay signed in" action. Industry-standard pattern for banking and healthcare products.
>
> **Cost + unlock:**
> - **Cost:** ~one week (3d frontend + 1d backend + 1d QA).
> - **Unlocks:** measurable drop in inactivity tickets (above); foundation for a future session-activity dashboard that several enterprise customers have asked for; improved reliability score in customer surveys, which feeds into renewal conversations.
>
> **Ask:** approval to schedule in the next sprint.

---

## Plan walkthrough (multi-phase source) — with phase-shape table + ASCII phase-bar

**Source:**
> Replace the in-house image-resizing pipeline with a managed third-party service.
> - **Phase A** (~3 weeks): stand up the new service alongside the old one, feature-flagged traffic split (5/25/50/100%).
> - **Phase B** (~2 weeks): gradually shift traffic, monitor cost/latency/quality, rollback is a flag flip.
> - **Phase C** (~1 week, +30 days after Phase B): deprecate the in-house pipeline, remove legacy code, finalize savings.

**Boss rendering:**

> This plan migrates our image-resizing infrastructure from a self-built pipeline to a managed third-party service, in three phases designed to keep the switch reversible until we're confident.
>
> **Phase shape:**
>
> | Phase | Duration | What it delivers | Reversible? |
> |---|---|---|---|
> | A | 3 weeks | New service stood up alongside the old one; flag-controlled traffic split (5%, 25%, 50%, 100%). No customer-facing change. | Yes — single flag flip |
> | B | 2 weeks | Traffic gradually shifted; cost, latency, and quality monitored at each step. | Yes — single flag flip |
> | Soak | 30 days | 100% traffic on the new service; no regressions observed. | Yes — flip back if anything looks wrong |
> | C | 1 week | Legacy pipeline deprecated and removed; cost savings finalized. | **No — final commit** |
>
> **At a glance:**
>
> ```
> Phase A (3 wks) ─► Phase B (2 wks) ─► [30-day soak] ─► Phase C (1 wk)
>      ↑                  ↑                 ↑                 ↑
>      reversible         reversible        reversible        IRREVERSIBLE
> ```
>
> Every step before Phase C is reversible by a single configuration change. We only commit irreversibly after a month of production traffic on the new service with no regressions.
>
> **Cost + risk:** Six weeks total. No customer-facing disruption during Phases A and B. Cost savings realized at Phase C completion.
>
> **Ask:** approval for Phase A. Phases B and C will be re-scoped once Phase A is producing real data.

---

## How to read these

```
Feature pitch  ──►  outcome sentence  ──►  impact table  ──►  what/cost/unlock  ──►  ask
Plan walkthrough ─►  outcome + shape  ──►  phase table   ──►  ASCII phase-bar  ──►  cost/risk + ask
```

The **impact table** in the feature pitch is the single most useful presentation element — three rows showing today vs. after, with a measurable metric each. It is what a sponsor screenshots and forwards.

The **phase-shape table + ASCII phase-bar** in the plan walkthrough do complementary jobs: the table gives the detailed breakdown; the ASCII bar gives the at-a-glance "where can I still back out" view. Sponsors latch onto the ASCII bar; the table is what they refer back to in the follow-up meeting.

Banned words self-check: neither rendering uses `schema`, `validation`, `atomicity`, `hook`, `wrapper`, `JSON`, `PowerShell`, `regex`, `API`, `commit`, `merge`, `deploy`. Neither uses 🌮 or warm casual praise. No file paths. No code. No status icons. The visual structure comes from tables, ASCII flow-bars, and headings — not emoji decoration.

**There is no `--clean` variant** — boss is always clean by definition.

**Architecture note:** the session-timeout scenario assumes a web-session model; the pipeline scenario assumes a backend service. The **plan-walkthrough structure** (phase-by-phase, reversible-at-every-step) generalizes to any phased delivery — ML model migrations, schema migrations, vendor switches, framework upgrades. The **impact-at-a-glance table** generalizes too — pick 3 metrics relevant to the sponsor's actual decision (cost per month / users affected / risk reduction / etc.) and show today vs. after.

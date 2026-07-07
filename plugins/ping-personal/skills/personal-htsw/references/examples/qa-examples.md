# qa-examples — workflow flowchart + tables + icons + HOW-THIS-WORKS sections

The workflow:

```
[Jira story]  ──►  [Read spec carefully]  ──►  Has observed behavior?
                                                  │
                              ┌───────────────────┴───────────────────┐
                              │ no (pre-test)                         │ yes (post-test)
                              ▼                                       ▼
                  [Design test cases]                  [Jira vs. code reality-check table]
                  [Flag edge cases]                    [Hypothesis (labeled as guess)]
                  [Flag regressions to watch]          [Where to look / how to file]
                              │                                       │
                              └─────────► [Test brief output] ◄───────┘ [Bug writeup output]
```

**Icon legend (pre-test):**
- 🌮 GOOD spec — celebrate it
- 🟢 PASS spec — testable as-written, no celebration
- ⚠ WARNING spec — workable but with minor gaps to clarify with PM
- 🔴 spec gap that blocks a test (rare — usually you'd escalate, not test)

**Icon legend (post-test):**
- 🔴 violation / observed bug
- ⚠ hypothesis / risk / regression watch
- 🟢 already correct (rare in post-test)

**No clean variant.** Use `boss` mode if you need a polished version.

**Every ⚠ and 🔴 outside the TL;DR carries an evidence marker AND a suggestion-arrow.** This is the evidence-and-suggestion contract.

---

## Pre-test — well-written Jira story (GOOD spec, 🌮)

**Source:**

> **Story (ST-1234):** As a logged-in user, when I click "Log out", all my active sessions on every device should be terminated immediately.
>
> **Acceptance criteria:**
> - On logout, every session row for this user has `is_active = false`.
> - `/api/me` from any device returns 401 after logout.
> - Logout is idempotent (clicking twice → no error).
> - Expired sessions stay expired (no resurrection).

### Rendering:

_Explaining: ST-1234 · purpose: qa_

## 🌮 PM nailed this spec

**TL;DR — test against it:**

- 🟢 **All 4 ACs covered** by test cases #1–#4.
- 🟢 **No spec gaps** worth blocking on — DB row state + HTTP code both named.
- ⚠ **Cache atomicity** worth probing — confirm scope with PM.

### How this shit works

When a logged-in user clicks "Log out," the backend is supposed to flip `is_active=false` for every session row tied to that user (not just the one tied to the current request), and any subsequent call to `/api/me` from any device should return 401. The critical invariant — and where the spec earned its 🌮 — is the word *every*: the feature is explicitly multi-device, so any test that only exercises a one-session user proves nothing about the all-device behavior.

**Coverage at a glance:**

| AC # | Spec line | Covered by |
|---|---|---|
| 1 | All session rows → `is_active = false` | 🟢 Test cases #1, #2, #3 |
| 2 | `/api/me` returns 401 from any device | 🟢 Test cases #1, #2 |
| 3 | Logout is idempotent | 🟢 Test case #4 |
| 4 | Expired sessions stay expired | 🟢 Test case #3 |

**Test cases:**

| # | Status | Input | Expected |
|---|---|---|---|
| 1 | 🟢 | 1 active session, logout | row `is_active=false`; `/api/me` → 401 |
| 2 | 🟢 | 3 active sessions across 3 devices, logout from one | all 3 rows false; `/api/me` → 401 on all 3 |
| 3 | 🟢 | 2 active + 1 expired, logout | actives flip; expired stays expired |
| 4 | 🟢 | Logout twice quickly | idempotent — no error |
| 5 | ⚠ | Cache invalidation atomicity (if cache exists) | Confirm with PM — cache scope unclear |

**Edge cases worth probing:**
- ⚠ Concurrent in-flight request mid-logout. Evidence: the spec doesn't mention concurrent-request semantics; the AC list covers "after logout" but not "during". → ask: should an in-flight request started before logout see pre-logout or post-logout state?
- ⚠ JWT/cookie validity after logout. Evidence: the spec says `/api/me` returns 401, but doesn't say whether the middleware reads the session table or trusts the JWT signature alone. → next: trace the middleware path before writing test #5; if it trusts JWT only, the feature won't actually invalidate cross-device.

**Regressions to watch:**
- ⚠ Login flow unaffected. Evidence: logout and login share `sessions` table writes; a typo in a JOIN could break login. → next: add a smoke test for login after the logout change ships.
- ⚠ "Remember me" tokens stay in a separate code path. Evidence: the spec is silent on remember-me; assumption is it lives in a different table. → ask: PM should confirm remember-me is out of scope before tests are written.

---

## Post-test — bug found (Mode 2, Jira-vs-code table mandatory)

**Source:**

> **Story (ST-1234):** [same as above]
>
> **Observed:** After logout from Device A, Device B is still authenticated. `/api/me` from Device B → 200 with user data. Session row for Device B still `is_active = true`.

### Rendering:

_Explaining: bug against ST-1234 · purpose: qa_

## 🔴 Spec says ALL — code says one

**TL;DR — file it:**

- 🔴 **Logout only kills the initiating session** — spec says "all devices".
- 🔴 **Security implication** — clicking "log out" doesn't log you out elsewhere.
- ⚠ **Most likely cause** — `UPDATE` keys on `session_id` instead of `user_id`.

### What's actually happening

The logout endpoint is supposed to flip `is_active=false` for *every* session row belonging to the user — that's the all-device wording the spec is built around. Instead, the handler only flips the row for the session that initiated the logout request; the other devices' rows stay `is_active=true`, and the auth middleware on those devices keeps letting requests through. From a user's perspective, clicking "Log out" on their phone leaves them logged in on their laptop, which is the security bug.

**Jira vs. code — reality check:**

| Status | Spec says | Code does | Evidence |
|---|---|---|---|
| 🔴 | All session rows for the user → `is_active = false` | Only the initiating session's row flips | `SELECT user_id, is_active FROM sessions WHERE user_id = X` shows 1 of N rows updated |
| 🔴 | `/api/me` returns 401 from every device | Returns 200 from non-initiating devices | `GET /api/me` from Device B post-logout returns 200 + full payload |
| ⚠ | Logout is idempotent | Untested — primary defect blocks observation | Will test after the 🔴 rows are fixed |
| ⚠ | Cache invalidation atomicity | Untested — DB write itself is wrong | Will test after the 🔴 rows are fixed |

🔴 **What actually happened:** users who log out from one device remain authenticated on their other devices. `/api/me` happily hands over their data. The logout isn't logging anything out except the device that initiated the click — which is the whole damn point of having "all" in the spec. Security implication: clicking "log out" doesn't log you out.

⚠ **Most likely cause:** the logout handler's `UPDATE` keys on `session_id` (the current request's session) instead of `user_id` (every session for this user). Single-device logout instead of all-device. Classic — somebody read "logout" and implemented the obvious thing without re-reading the "all devices" part.

**Where to look:**
- 🔴 The logout endpoint handler — find the `UPDATE` statement, check the WHERE clause. Evidence: `SELECT user_id, is_active FROM sessions WHERE user_id = X` after logout shows 1 of N rows updated; the handler is at `handlers/logout.ts` per the routes table. → fix: change the `WHERE` clause from `session_id = :sid` to `user_id = :uid`.
- ⚠ The session-cache layer (if there is one). Evidence: didn't trace it yet; the DB write itself is wrong, so even if the cache works correctly it's broadcasting incorrect state. → next: after the DB fix lands, verify cache invalidates per-user, not per-session.
- ⚠ Auth middleware. Evidence: middleware that trusts JWT signature alone (and never reads `is_active`) would still let the bug bite even after the DB fix. → ask: does the middleware consult `sessions.is_active` on every request, or only at JWT-issue time?

**File the ticket:**

```
Title: "Logout invalidates only initiating session; spec requires all-device"

Reproduction:
1. Log in on Device A.
2. Log in on Device B as the same user.
3. Verify both can hit /api/me and get 200.
4. Log out on Device A.
5. On Device B, call /api/me.
6. Observed: 200 with user data. Expected: 401.

Severity: Security — users who log out aren't actually logged out.
```

**Test cases to add once fixed:**

| Input | Status |
|---|---|
| User with 1 session, logout → `/api/me` 401 | 🟢 covers the primary fix |
| User with 3 sessions, logout from one → all 3 → 401 | 🟢 covers the all-device requirement |
| Concurrent logout race | ⚠ regression watch |
| Logout when already inactive | ⚠ idempotency |

---

## How to read these

```
PRE-TEST  ──►  TL;DR "test against it" + HOW-THIS-WORKS + coverage table + test-case table + edge cases
               (Mode 3 + 🌮 if the spec earns it; PASS/WARNING also possible)

POST-TEST ──►  TL;DR "file it" + HOW-THIS-WORKS + Jira-vs-code table (Status as first column)
               + hypothesis (⚠ labeled as guess)
               + where-to-look + ticket draft + regression tests
               (Mode 2 voice; NO Mode 3, NO 🌮)
```

**The TL;DR at top is the load-bearing artifact.** PMs and devs read tier title → TL;DR → done; they only descend into the Jira-vs-code table when they need to fix the rows. The HOW-THIS-WORKS section is the bridge between the verdict and the substance — read three sentences, walk away knowing the shape of the feature or bug.

**Evidence-and-suggestion in action:** Every ⚠ and 🔴 in the body sections above pairs (evidence: SQL or HTTP observation, file path, quoted spec, or an explicit "the spec doesn't say") with (suggestion: a `→ fix:`, `→ suggestion:`, `→ next:`, or `→ ask:` arrow naming what to do). A bug-writeup without citations is gossip; a bug-writeup with citations is a ticket a dev can act on without playing detective.

**Honest protocol in action:** "Most likely cause" not "the cause." "Untested — primary defect blocks observation" not "this is also broken." Don't promote a guess to a fact, and don't claim coverage you don't have.

**For non-web sources** (event-sourced systems, mobile apps, ML pipelines): keep the table structure and the Status column; swap the row content for your domain (audit-log says X / kafka topic shows Y / inference latency was Z). The pattern is universal; the vocabulary is replaceable.

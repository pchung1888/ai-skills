# pr-examples — four quality tiers with icons, tables, annotated diffs, and HOW-THIS-WORKS sections

Same base scenario across all four tiers: a PR adds a rate-limit middleware against `ST-9999`. Implementation quality changes; voice, icon density, and tier title icon track it.

**Icon legend:**
- 🌮 GOOD — genuinely well-crafted, deserves a celebration line
- 🟢 PASS — works as advertised; no celebration, no problems
- ⚠ WARNING — minor problems; not critical, but worth fixing before merge
- 🔴 BAD — blocking issue; refuse the merge until fixed

**No clean variant.** If you want a polished version of any of these, use `boss` mode — same skill, different audience.

**Every ⚠ and 🔴 outside the TL;DR carries an evidence marker AND a suggestion-arrow.** This is the evidence-and-suggestion contract. The validator enforces the structural side of it; you (the author) are responsible for the factual side.

---

## Tier 1 — GOOD (🌮)

**The Jira ticket (ST-9999):**
> AC #1: Rate-limit at 100 req/min per IP. Return 429 with Retry-After header.
> AC #2: Document the new 429 in `docs/api.md`.
> AC #3: Tests cover the rate-limit boundary.

### Rendering:

_Explaining: PR-rate-limit-v1 · purpose: pr_

## 🌮 Whoever wrote this knew what they were doing

**TL;DR — ship it:**

- 🟢 **All 3 ACs delivered** — limiter, docs, tests.
- 🟢 **99/100/101 boundary triplet** — exactly where rate-limiter off-by-ones live.
- 🟢 **Single source of truth** for the constant; no duplication.

**Ticket vs. PR:**
- 🟢 AC #1 — `middleware/rate-limit.ts` delivers 100/min + 429 + Retry-After
- 🟢 AC #2 — `docs/api.md` updated in this PR
- 🟢 AC #3 — 24 tests including the 99/100/101 boundary triplet

**Impact at a glance:**

| File | What it does | Status |
|---|---|---|
| `middleware/rate-limit.ts` | New file — the limiter | 🟢 covers AC #1 |
| `middleware/rate-limit.test.ts` | 24 tests, boundary triplet included | 🟢 covers AC #3 |
| `config.ts` | One constant: `RATE_LIMIT_PER_IP = 100` | 🟢 single source of truth |
| `docs/api.md` | Documents the 429 response | 🟢 covers AC #2 |

**The diff:**

```diff
+ // middleware/rate-limit.ts (new, ~80 lines)                      ← 🟢 implements AC #1
+ // middleware/rate-limit.test.ts (24 tests)                       ← 🟢 covers AC #3
+ //   - 99th, 100th, 101st request                                 ← 🟢 boundary triplet
+ //   - IP-key isolation, Retry-After correctness, IPv6, bursts    ← 🟢 non-obvious cases
+ // docs/api.md                                                    ← 🟢 covers AC #2
```

### How this shit works

The new middleware reads the requesting IP from `req.ip`, looks it up in a shared rate-counter, and rejects with `429 Too Many Requests` plus a `Retry-After` header when the IP has made more than `config.RATE_LIMIT_PER_IP` requests in the rolling 60-second window. The counter resets per-IP each window; the response header is computed from the remaining-window time so clients can back off correctly.

**Watch out for:**
- ⚠ NAT-collision is intrinsic to IP-based limiting — every shared-NAT user counts as one IP. Evidence: `RFC 6585 §4` notes IP-based limiters disadvantage shared-NAT clients. → suggestion: add one sentence to `docs/api.md` flagging this as an expected limitation; no code change needed.

---

## Tier 2 — PASS (🟢)

A different PR against the same ticket: works, meets every AC, no special touches but also no problems. Tier 2 is a pass. The reviewer reads it, signs off, moves on.

### Rendering:

_Explaining: PR-rate-limit-v1-pass · purpose: pr_

## 🟢 Works as advertised

**TL;DR — ship it:**

- 🟢 **All 3 ACs delivered** — limiter, tests, docs.
- 🟢 **Boundary tested at 99/100/101** — no off-by-one risk.
- ⚠ **In-memory Map** for the counter — won't scale past 1 instance.

**Ticket vs. PR:**
- 🟢 AC #1 — `middleware/rate-limit.ts` returns 429 + Retry-After at 100/min/IP
- 🟢 AC #2 — `docs/api.md` documents the new 429
- 🟢 AC #3 — 8 tests, includes the 99/100/101 boundary triplet

**Impact at a glance:**

| File | What it does | Status |
|---|---|---|
| `middleware/rate-limit.ts` | New file — in-memory counter + 429 | 🟢 covers AC #1 |
| `middleware/rate-limit.test.ts` | 8 tests, boundary included | 🟢 covers AC #3 |
| `config.ts` | `RATE_LIMIT_PER_IP = 100` | 🟢 single constant |
| `docs/api.md` | Documents the 429 response | 🟢 covers AC #2 |

**The diff:**

```diff
+ const counts = new Map<string, { count: number, resetAt: number }>();   ← ⚠ module-scope Map
+ if ((counts.get(ip)?.count ?? 0) >= config.RATE_LIMIT_PER_IP) {         ← 🟢 reads config
+   return res.status(429).set('Retry-After', String(retryAfter)).end();   ← 🟢 covers AC #1
+ }
```

### What this actually does

The middleware keeps a per-IP request count in a module-scope `Map` and resets each entry on a rolling 60-second window. When the count for an IP crosses `config.RATE_LIMIT_PER_IP`, the request short-circuits with `429` plus a computed `Retry-After`. Tests exercise the 99/100/101 boundary plus IP-key isolation. Straightforward implementation, no surprises.

**Watch out for:**
- ⚠ The counter lives in `middleware/rate-limit.ts:12` as a module-scope `Map`. Evidence: searched for `redis|memcached|cache` in the diff — no shared store referenced. → next: this works fine for the current single-instance deploy; revisit when the service goes multi-instance and file a follow-up ticket then. Not blocking.

---

## Tier 3 — WARNING (⚠)

A different PR against the same ticket: the core works, but there are minor problems worth fixing before merge. Not blocking, but not ignorable either.

### Rendering:

_Explaining: PR-rate-limit-v1-warning · purpose: pr_

## ⚠ Solid bones, three things to fix

**TL;DR — address these and merge:**

- 🟢 **Core middleware works** — AC #1 delivered.
- ⚠ **Boundary tests missing** at 99/100/101 — AC #3 partial coverage.
- ⚠ **Constant duplicated** in two places + `docs/api.md` not updated.

**Ticket vs. PR:**
- 🟢 AC #1 — `middleware/rate-limit.ts` delivers 100/min + 429 + Retry-After
- ⚠ AC #2 — `docs/api.md` NOT updated; clients won't know about the new 429
- ⚠ AC #3 — 8 tests; **boundary triplet at 99/100/101 missing**

**Impact at a glance:**

| File | What it does | Status |
|---|---|---|
| `middleware/rate-limit.ts` | New file with the limiter | 🟢 core works; ⚠ has a hardcoded `100` |
| `middleware/rate-limit.test.ts` | 8 tests, no boundary cases | ⚠ AC #3 partial |
| `config.ts` | `RATE_LIMIT_PER_IP = 100` | ⚠ value duplicated inline in middleware |
| `docs/api.md` | NOT updated | ⚠ AC #2 missing |

**The diff:**

```diff
+ const RATE_LIMIT = 100;                                ← ⚠ hardcoded in middleware/rate-limit.ts:8
+ if (count > config.RATE_LIMIT_PER_IP) {                ← ⚠ reads from config AND the const above
+   return res.status(429).set('Retry-After', '60').end();  ← 🟢 covers AC #1
+ }
+ // middleware/rate-limit.test.ts: 8 tests              ← ⚠ NO boundary coverage at 99/100/101
```

### The flow

The middleware reads `req.ip`, increments a per-IP counter, and rejects with `429 + Retry-After: 60` once the count exceeds the limit. Implementation is functionally correct against AC #1, but the value `100` appears both as `config.RATE_LIMIT_PER_IP` (read on the comparison) and as `const RATE_LIMIT = 100` (declared but unused). Tests cover the basic accept/reject paths but not the exact boundary at 99/100/101 where off-by-one bugs hide. Docs untouched, so external clients hitting the new 429 won't know what changed.

**Watch out for:**
- ⚠ The value `100` is declared in two places. Evidence: `middleware/rate-limit.ts:8` declares `const RATE_LIMIT = 100`; the comparison on line 21 reads `config.RATE_LIMIT_PER_IP`. The local const is currently unused, but the next person who edits this file will assume both are wired. → fix: delete `const RATE_LIMIT = 100` from `middleware/rate-limit.ts:8`; the codebase already has one source of truth in `config.ts`.
- ⚠ No boundary tests. Evidence: searched `middleware/rate-limit.test.ts` for `99|100|101` — no matches. → suggestion: add the 99/100/101 triplet to `rate-limit.test.ts` (one test passing 99, one passing 100, one rejecting 101) before merge.
- ⚠ `docs/api.md` not updated. Evidence: file appears unchanged in the diff (`git diff --stat` lists no change to `docs/api.md`). Clients hitting the new 429 won't know what changed. → fix: add a short "429 Too Many Requests" entry to `docs/api.md` describing the limit and the `Retry-After` semantics.

---

## Tier 4 — BAD (🔴)

A different PR against the same ticket: blocking issues. Refuse the merge.

### Rendering:

_Explaining: PR-rate-limit-v1-bad · purpose: pr_

## 🔴 This shit ain't gonna work

**TL;DR — block this:**

- 🔴 **Zero tests** on a security gate — AC #3 not delivered.
- 🔴 **Retry-After hardcoded to 60** — wrong by RFC 6585.
- 🔴 **Unrelated auth test deleted** as "flaky" — scope creep + lost coverage.

**Ticket vs. PR:**
- 🟢 AC #1 — middleware exists; whether it works is unknowable without tests
- 🔴 AC #2 — `docs/api.md` NOT updated
- 🔴 AC #3 — **ZERO new tests** for the new middleware

**Impact at a glance:**

| File | What it does | Status |
|---|---|---|
| `middleware/rate-limit.ts` | New file, untested | ⚠ might work — no way to know |
| `middleware/auth.test.ts` | Unrelated test DELETED ("flaky") | 🔴 scope creep + lost coverage |
| `(no rate-limit.test.ts)` | — | 🔴 AC #3 not delivered |
| `docs/api.md` | NOT updated | 🔴 AC #2 not delivered |

**The diff:**

```diff
+ // middleware/rate-limit.ts (new, the implementation)
  res.set('Retry-After', '60');                             ← 🔴 always 60, should be remaining-window
- // middleware/auth.test.ts                                ← 🔴 UNRELATED file
- describe('auth-rejects-expired-token', () => { ... });       test DELETED, reason: "flaky"
+ // (no new test file for the new middleware)              ← 🔴 ZERO tests
```

### Behind the scenes

The middleware exists at `middleware/rate-limit.ts` and the basic 429-on-overflow path is wired up, but there is no test file for it and the `Retry-After` value is the literal string `'60'` rather than a value computed from the remaining window. Worse, the diff also deletes an unrelated `auth-rejects-expired-token` test from `middleware/auth.test.ts` with the commit-message reason "flaky" — scope creep on top of lost coverage. The middleware's behavior at the boundary is currently unfalsifiable.

**Watch out for:**
- 🔴 **No tests for the new middleware.** Evidence: searched `middleware/` for `rate-limit.test.ts` — no such file exists; the diff adds `rate-limit.ts` without a sibling test. A rate limiter gates every request — shipping it untested is bullshit. → fix: block until at minimum the 99/100/101 boundary + IP isolation + Retry-After correctness exist in a new `middleware/rate-limit.test.ts`.
- 🔴 **Retry-After is hardcoded to 60.** Evidence: `middleware/rate-limit.ts:24` reads `res.set('Retry-After', '60')`; `RFC 6585 §4` and `RFC 7231 §7.1.3` both specify the value as "the number of seconds until the client can retry," which depends on remaining-window time, not a constant. A client rejected 5 seconds into the window is told "retry in 60" when the budget resets in 55 — straight-up wrong. → fix: compute `Retry-After` from `(windowEnd - Date.now()) / 1000`, return as integer seconds.
- 🔴 **An unrelated auth test was deleted** with the reason "flaky." Evidence: the diff at `middleware/auth.test.ts` removes the `auth-rejects-expired-token` describe block; commit message says "flaky." That's bullshit on two axes: it's out of scope for a rate-limit PR, and "flaky" is a reason to fix the flake, not delete the test. → fix: restore the deleted block in a follow-up commit on this same branch and open a separate ticket for the flakiness if real.

---

## How to read these

| Tier | Title icon | TL;DR action verb | Dominant body icon | Voice |
|---|---|---|---|---|
| GOOD | 🌮 | `ship it` | 🟢 + 🌮 | Mode 3 + Mode 1 |
| PASS | 🟢 | `ship it` / `merge — no drama` | 🟢 + maybe one ⚠ | Mode 1 |
| WARNING | ⚠ | `address these and merge` | ⚠ + 🟢 | Mode 1 + a few ⚠ |
| BAD | 🔴 | `block this` | 🔴 dominant | Mode 2 + block call |

**The TL;DR at top is the load-bearing artifact.** A busy reviewer reads tier title → TL;DR → done; they only descend into HOW-THIS-WORKS / alignment / table / diff when they need to act on it. **No bottom "Verdict:" line** — the TL;DR at top already carried it.

**Evidence-and-suggestion in action:** Every ⚠ and 🔴 in the body sections above pairs (evidence: file path + line, RFC reference, or a search-and-found-none statement) with (suggestion: a `→ fix:`, `→ suggestion:`, `→ next:`, or `→ ask:` arrow naming what to do). A claim without a citation is a vibe; a claim with a citation is a fact a reviewer can verify. **You don't get to accuse a dev of doing their job wrong without showing your work.**

**Honest protocol in action:** If you don't know whether `requireRole` throws or returns, say "I can't tell from the diff — read `requireRole.ts` before approving." Don't make up the answer.

**For non-HTTP sources** (mobile app, batch job, ML pipeline): swap the rate-limit scenario for your domain's equivalent failure mode. The icon contract + voice rules + table patterns + HOW-THIS-WORKS section + evidence contract all stay; the vocabulary changes.

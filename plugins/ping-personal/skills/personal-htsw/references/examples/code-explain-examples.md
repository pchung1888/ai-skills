# code-explain examples — worked code-explain renderings

code-explain is the deep, file-by-file + line-by-line walkthrough mode. It leads with WHY the change
exists, maps every file touched, then walks the load-bearing code line by line in plain English.
These examples are validated as persisted docs (generous cap — line-by-line of real code needs room).

---

_Explaining: the null-safe AppVar coerce added to the TOB gate (commit a1b2c3d, 1 file) · purpose: code-explain_

## What changed in the TOB AppVar read — and why the HTTP 500 is gone

**TL;DR — the core idea:**

- 📍 **The bug** — `CBool(GetAppVar("EnforceTOB"))` threw an HTTP 500 whenever the AppVar was missing.
- ⚙ **The fix** — coerce the value to a string first, so a missing AppVar reads as empty, not `Null`.
- 🧠 **One file, two lines** — pure defensive coerce; behavior is identical when the AppVar exists.

### Why we did it (the problem)

When an AppVar is absent, `GetAppVar` returns `Null`. `CBool(Null)` raises a Type-mismatch error, which
ASP surfaces as a bare HTTP 500 — no useful message, on a page the operator can't easily debug. The gate
was meant to default to "off" when unconfigured, not to crash. So the read needed to survive a missing
value instead of throwing on it. That single failure mode is the whole reason for the change.

### File-by-file map

| File | Lines | Real change? | What it is |
|---|---|---|---|
| `Globals.asp` | 2 | ✅ yes | The TOB AppVar read — coerce to string before testing |

### How this shit works

The old line asked `CBool` to convert whatever `GetAppVar` returned straight into a Boolean. That's fine
for `"1"`/`"0"`, but a missing AppVar returns `Null`, and `CBool(Null)` throws. The new code appends `& ""`
first, which turns `Null` into an empty string, then tests `= "1"`. An empty string is simply not equal to
`"1"`, so a missing AppVar now reads as `False` — the intended "off" default — and the page never throws.
When the AppVar exists, `"1" & ""` is still `"1"`, so the result is unchanged.

### Globals.asp — line by line

```vb
- Return CBool(GetAppVar("EnforceTOB"))
+ Dim s As String = GetAppVar("EnforceTOB") & ""   ' Null becomes "" — never throws
+ Return s = "1"                                    ' "" is not "1" -> False (the safe default)
```

| Line | What it says | What it means |
|---|---|---|
| `Dim s ... & ""` | Read the AppVar, force it to a string | A missing value (`Null`) becomes `""` instead of staying `Null` |
| `Return s = "1"` | Compare the string to `"1"` | Only the literal `"1"` is true; everything else (incl. `""`) is `False` |

### Watch out for

- 🚧 The coerce relies on `"1"` being the only truthy value — if config ever stores `"true"`/`"yes"`, this read treats it as `False`. Today the seeder only ever writes `"1"`/`"0"`, so it holds.

### Where to look

1. `Globals.asp` — the TOB AppVar read (the two changed lines)
2. The AppVar seeder that writes `EnforceTOB` — confirm it only ever writes `"1"`/`"0"`

---

**Your setting works for this run.**

One more change comes after this step.

---

**Why one more change**

With `@ScrubClientSysUser = 0`, the sweep now checks `SysUser.Email` too. It will find the
6 client addresses and block DRYRUN and COMMIT.

Only if PREVIEW proves SysUser is the only blocker, we set the block switch to `0` next.

---

**Step 1: run PREVIEW again**

This step changes nothing. PREVIEW only reads.

1. Check that the file says `@RunMode = 'PREVIEW'`.
2. Save the file (Ctrl+S).
3. Press F5.

---

**If the sweep grid shows any row other than `SysUser | Email`**

Stop and tell me. Do not change the block switch.

---

**Later, in the repo**

The deliverable still has `@ScrubClientSysUser = 1`. We fix it after this run.

---

**Tell me:**

- How many rows are in the sweep grid?
- Is the only row `SysUser | Email | 6 | 6`?
- Is the `[LIVE] SysUser.Email` line gone?

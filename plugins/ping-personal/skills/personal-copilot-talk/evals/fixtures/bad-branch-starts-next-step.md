That works for this run. One more thing is needed.

---

**Why one more change**

With `@ScrubClientSysUser = 0`, the sweep now checks `SysUser.Email` too. It will find the
6 client addresses and block DRYRUN and COMMIT.

So you also set the block switch to `0`. Do that only after PREVIEW proves SysUser is the
only blocker.

---

**Step 1: run PREVIEW again**

1. Check `@RunMode = 'PREVIEW'`.
2. Save the file (Ctrl+S).
3. Press F5.

---

**Tell me:**

- Every row in the sweep grid (`Tbl | Col | ExtRows | ClientRows`).
- The `[LIVE] SysUser.Email` line. It should be gone.
- The `[SWEEP]` line.

---

**If the grid shows only `SysUser | Email | 6 | 6`**

Then change this line:

    DECLARE @FailOnUncoveredClient bit     = 0;

Then continue with DRYRUN.

If the grid shows any other row, stop and tell me.

---

**Later, in the repo**

The deliverable still has `@ScrubClientSysUser = 1`. We fix it after this run.

**Your decision: how do we clean it?**

**Fix the script (my recommendation)**
- I add `_StagingSysUser$.Email` to the scrub list in the repo.
- I rebuild the deliverable zip, test it, and commit it.
- You copy the new zip, rerun Step 1 (STOPALL), then redo Step 3a.
- About 20 minutes. The next client refresh gets the fix too.

**Clean it by hand on the box**
- You run one `UPDATE` on that table in SSMS.
- It is faster, but the deliverable stays wrong and there is no evidence trail.

Leave the box as it is. Everything is stopped, so it is safe to wait.

---

**Tell me:**

- "Fix the script", or "by hand".

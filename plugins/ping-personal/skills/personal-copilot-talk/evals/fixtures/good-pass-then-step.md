**Step 1a passed.**

- 5 of 5 services are stopped and disabled.
- 35 of 35 tasks are disabled.
- The app pool is stopped.
- `RESULT: STOPALL done and verified.` and `Exit code 0`.

---

**Step 1b: check that the database is quiet (SSMS)**

1. Open SSMS.
2. Server name: the QA SQL server from the runbook. Connect.
3. Open a new query and paste the session query from the runbook.
4. Press F5.
5. Wait 1 minute.
6. Press F5 again.

---

**Tell me (second run only):**

- Is the date the same both times?
- Which `host_name` values are in the second result? The host names are enough.

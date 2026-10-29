**STOP. Do not run DRYRUN.**

The PREVIEW found 1 client-domain address (<client-domain>) in a column the scrub does not
clean. DRYRUN and COMMIT will refuse to run until we deal with it.
PREVIEW changed nothing. The box is safe as it is.

---

**Step 1: find the column**

1. In SSMS, click the **Results** tab of the PREVIEW run.
2. Find the grid with these columns: `Class | Tbl | Col | ExtRows | ClientRows`

That grid shows only names and counts. It shows no addresses.

---

**Tell me:**

- The `Tbl`, `Col`, `ExtRows` and `ClientRows` values in that grid.

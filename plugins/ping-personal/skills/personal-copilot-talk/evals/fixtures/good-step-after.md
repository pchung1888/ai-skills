**Step 1a: stop the app services**

This step stops mail. The script asks you before it changes anything.

1. Right-click PowerShell.
2. Click **Run as administrator**.
3. Type these lines, one at a time:

   ```powershell
   cd D:\QAScrub
   Set-ExecutionPolicy -Scope Process Bypass -Force
   Unblock-File D:\QAScrub\*.ps1
   .\Scrub-QAConfigEmails.ps1 -Mode STOPALL
   ```

4. The **CONFIRM THIS IS THE QA BOX** screen opens. Stop here. Do **not** type YES yet.

---

**Tell me:**

- The machine name on the screen.
- Do the production IPs match your file?
- The list of service names.

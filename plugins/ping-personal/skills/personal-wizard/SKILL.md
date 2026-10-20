---
name: personal-wizard
description: Use PROACTIVELY whenever the next steps must be done by the user by hand, on a machine or screen the agent cannot reach - "deploy this to QA", "push the DLL to the client box", "roll it back", "run this script on the client's server", "I have to RDP in", "walk me through it", "give me the steps", "checklist for the deploy", IIS Manager or SSMS clicks, a vendor dashboard, or setting up credentials. Writes a PowerShell wizard that shows one step at a time, opens each tool, saves the values the user pastes back, and asks before any overwrite. Not for steps the agent can run itself. Also /personal-wizard.
---

# Wizard

Adapted from Matt Pocock's `wizard` skill (MIT, see `THIRD-PARTY-NOTICES.md`). This version
writes Windows PowerShell, not bash.

A **wizard** is a PowerShell script that walks a person through a manual procedure, one stage
at a time. It opens each URL or tool, says exactly what to click and copy, and saves the values
the person types back. It confirms before every irreversible action and shows how many stages
are left. Nobody has to re-explain the procedure to an AI next time.

The screen handling, prompts and value saving are already written in [template.ps1](template.ps1).
**Your job is only to scope the procedure and write its stages.** Never hand-edit the library
above the `STAGES` marker. Every wizard shares it, so every wizard behaves the same.

A wizard is single-use by default. Save it to the session scratchpad or a `scripts/` folder, and
delete it when the job is done. Commit it only when the owner wants a repeatable path in the repo.

## In your daily work

| Situation | What the wizard walks you through |
|---|---|
| Deploy a VB6 DLL or ASP page to the QA or DEV box | RDP in, back up the current file, copy the new one, register it, recycle the app pool, smoke-test the page |
| Run a T-SQL script on a client box | Open SSMS on that server, confirm the database name, run the script, paste the row counts back |
| Roll back a bad deploy | Restore the backup, re-register, recycle, confirm the page loads |
| Set up a new machine or credential | Each dashboard or settings screen, with the value saved where it belongs |

Shared servers come with a house rule. Survey read-only first, back up any DLL or config before
overwriting it, and get the owner's approval first. The wizard enforces that with a `Confirm-Step`
gate before each overwrite.

## Process

### 1. Scope the procedure

List every manual step and every value captured along the way. Read the repo first, do not ask
cold: deploy notes, config files (`web.config`, `global.asa`, `.udl`), README files, and past
progress files under `docs/progress/`.

Show the owner the ordered list of stages and the values each produces. Let them add, drop or reorder.

**Done when:** every stage is named in order. For each captured value you know where the person
finds it, where it is saved, and whether it is secret (hidden entry) or not.

### 2. Map each stage's path

For each stage, write the exact path a person follows. For example: "IIS Manager -> Application
Pools -> <pool name> -> Recycle". If you do not know the current screen or the exact command,
say so and ask, or check the docs. Never invent a step that may not exist.

**Done when:** a stranger could follow every stage.

### 3. Write the wizard

Copy `template.ps1` to the target path. Replace the example stages with one `Start-Stage` per
step, in order. Use the library helpers: `Start-Stage`, `Say`, `Step`, `Note`, `Warn`,
`Open-Target`, `Ask`, `Ask-Secret`, `Save-Value`, `Wait-Step` and `Confirm-Step`. Set
`$script:TotalStages` to the number of stages you wrote.

Keep the bar the template sets. Open the URL or tool before asking for its value. Use
`Ask-Secret` for anything secret. Put `Confirm-Step` before any irreversible action. Keep a
stage to one task, because each stage clears the screen.

Keep the script pure ASCII. Windows PowerShell 5.1 can misread non-ASCII characters in a file
saved without a byte order mark.

### 4. Verify and hand off

- Parse it in PowerShell. This must print nothing:
  `$e = $null; [void][System.Management.Automation.Language.Parser]::ParseFile('<script>', [ref]$null, [ref]$e); $e`
- Do not run it yourself. It opens tools and waits for a person.
- Trace it instead: every value from step 1 is asked for, and lands where step 1 said.
- Tell the owner how to run it: `powershell -ExecutionPolicy Bypass -File <script>`.

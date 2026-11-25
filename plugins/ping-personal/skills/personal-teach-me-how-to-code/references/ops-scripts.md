# Install, deploy and ops scripts

The person who runs an install script is an operator, not a code reader. They need to know what to
set up, what the script changes, how to see it worked, and how to undo it. So teach these scripts
from the operator view. Read code lines only to explain a failure or a side effect.

## Lead with the step table

Show this table first, at the top of the page or in the first reply, in run order. It is the map
for the whole part. The plan file alone is not enough.

| Step | File | Lines | Job |
|---|---|---|---|
| 14a | `prereq-check.ps1` | 1-60 | Check rights, tools and ports before anything changes. |
| 14c | `install.ps1` | 40-105 | Backup, SQL, build, publish, boot task, IIS virtual directory. |
| 14f | `rollback.ps1` | all | Undo everything the install changed. |

The rows are an example of the shape. Fill them from the real scripts.

## Four questions per script, in this order

1. **Before you run it.** What must exist first: accounts, rights such as elevation, certificates,
   connection strings, settings files, ports, tools and versions. Say where each value comes from.
   Give an `Example:` of each value's shape, never a real value (Example: `Server=10.12.34.56;
   Database=AppDb;Integrated Security=true`).
2. **What it changes on the box.** Every side effect in order: files, services, scheduled tasks,
   IIS sites or virtual directories, database objects, registry. Mark each step that is not
   reversible.
3. **How you know it worked.** The exact success line or exit code the script prints. Add one check
   the operator can run by hand: a URL, a command or a log line.
4. **When it fails.** Each FAIL message the script can print, what it means, the first thing to
   check, and whether the box is left half-changed.

## Rollback gets its own step

Rollback gets its own step, even when the script is short. Say what it undoes and in what order.
Say what it cannot undo, such as a dropped table or a sent mail. End with how to check that the box
is back to the old state.

## Troubleshooting table per part

| Symptom | Likely cause | Check | Fix |
|---|---|---|---|
| `FAIL: port 5443 in use` | Another service holds the port. | `Get-NetTCPConnection -LocalPort 5443` | Stop that service or change the port setting. |

Build each row only from messages and checks the scripts really contain. Label any other row
INFERRED.

## Code reading goes last

Line-level reading comes after the four questions, and only where a line explains a failure or a
side effect. A helper or the logging code gets one line, not a section.

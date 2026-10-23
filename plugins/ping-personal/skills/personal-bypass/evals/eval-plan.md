# personal-bypass eval plan

Deterministic grader: `eval.ps1` runs `Set-PermissionMode.ps1` against a temp repo and a temp
state folder, so it never touches a real repo or `~/.claude`.

| Failure mode | Check |
|---|---|
| bypass does not set the start mode | after `bypass`, defaultMode is bypassPermissions |
| ask rules still prompt in bypass | after `bypass`, local ask list is empty |
| rollback loses the original mode or rules | after `bypass`, `bypass`, `auto`, defaultMode and ask equal the original |
| other keys get rewritten | allow, deny and env are unchanged after the round trip |
| a repo with no settings.local.json | `bypass` creates it; `auto` leaves no defaultMode |
| status changes files | the file hash is the same before and after `status` |
| bypass ignores a policy that forbids it | `disableBypassPermissionsMode` in settings: `bypass` refuses, writes nothing |
| bypass lands in a commit | git tracks settings.local.json: `bypass` refuses, writes nothing |
| the model starts bypass on its own | SKILL.md keeps `disable-model-invocation: true` |
| skill drifts from the script | SKILL.md names the script and the three modes; files are ASCII |

Not covered: the live Bypass button. The mod tests cover it (`hooks/actions.test.tsx`).

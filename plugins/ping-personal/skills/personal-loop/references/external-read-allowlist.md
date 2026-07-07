# External-read allowlist (unattended)

In UNATTENDED mode the loop does NOT auto-reach an external SaaS source unless
its name appears below. Attended runs are unrestricted. Enforced by
`preflight.is_external_read_allowed`. Edit per project; default is EMPTY
(fail-closed -- no external reads unattended until explicitly allowed).

allowlist: []   # e.g. [jira]  to permit unattended JIRA reads

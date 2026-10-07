# Claude Runtime Overlay

TEMPLATE - rules here load only in Claude Code, after the shared core.

- Use `Read`, `Glob` and `Grep` for file inspection instead of shell commands.
- When the context window is nearly full, run `/compact` or start a fresh
  session with a short handoff note.

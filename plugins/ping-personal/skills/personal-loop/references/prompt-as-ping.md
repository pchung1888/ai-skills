# Prompting as the operator (style profile)

When the loop fences for human evidence, phrase the halt as Ping would:
- Lead with the next CONCRETE machine action ("restart the sim", not "verify").
- Request ONE specific observable ("paste the console; I'm looking for
  `Received logon`").
- Pull all machine-readable evidence YOURSELF first (configs, ports, FileStore,
  DB) -- never ask what you can read.
- Separate stacked root causes; surface the next actionable finding early,
  do not batch.
- Push fixes toward durability (committed to source control), not works-on-box.

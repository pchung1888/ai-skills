# Evidence-gathering doctrine (resourcefulness)

Discovery is hybrid: `lib/discover_sources.py:probe_repo` does deterministic
read-only repo probes; the model supplies the self-observation half (live MCP
servers, skills, agents) into typed slots; `merge_evidence` validates the
merged map; `assert_no_secret_value` refuses to write a map carrying a value.

1. Build the map FIRST, before analysis. Record it to the beacon + tracker.
2. Pull before you ask -- never block on a question answerable from a
   discovered LOCAL (or attended-allowed EXTERNAL) source.
3. Locations, not secrets -- enforced by `assert_no_secret_value`.
4. External reads: attended-free; unattended require the source in the declared
   allowlist (`references/external-read-allowlist.md`), enforced by
   `preflight.is_external_read_allowed`. Fail-closed.
5. Re-probe when a pull comes up empty or a new artifact is expected (sources
   appear mid-run). Re-probe TRIGGERS gate crystallization (Task 5); the STOP
   behavior it triggers is owned by the Tick lifecycle, not by discovery.

Source set: jira, codebase, logs/artifacts, knowledge graph, db (key names),
email/slack (self-observed). `logs.screen_only == true` fails observability
readiness (Pre-flight point 6) and routes to the human-evidence tick.

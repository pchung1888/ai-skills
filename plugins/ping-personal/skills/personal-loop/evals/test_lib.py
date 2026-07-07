import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

import progress_hash as ph

def test_identical_ticks_collapse():
    sig_a = ph.tick_signature("sha1", "tests: 3 failed", "TypeError x")
    sig_b = ph.tick_signature("sha1", "tests: 3 failed", "TypeError x")
    assert sig_a == sig_b

def test_changed_output_changes_signature():
    sig_a = ph.tick_signature("sha1", "tests: 3 failed", "")
    sig_b = ph.tick_signature("sha2", "tests: 0 failed", "")
    assert sig_a != sig_b

def test_no_progress_fires_after_k_identical():
    sigs = ["x", "a", "a"]
    assert ph.is_no_progress(sigs, k=2) is True

def test_no_progress_resets_on_change():
    sigs = ["a", "a", "b"]
    assert ph.is_no_progress(sigs, k=2) is False

def test_no_progress_needs_k_samples():
    assert ph.is_no_progress(["a"], k=2) is False

def test_progress_marker_changes_signature():
    a = ph.tick_signature("sha", "out", "", progress_marker="1")
    b = ph.tick_signature("sha", "out", "", progress_marker="2")
    assert a != b   # a campaign that advanced goals_done is NOT a stall

def test_same_marker_same_signature():
    a = ph.tick_signature("sha", "out", "", progress_marker="3")
    b = ph.tick_signature("sha", "out", "", progress_marker="3")
    assert a == b

import stop_eval as se

def _state(**kw):
    base = dict(accept_exit=None, goals_total=0, goals_done=0,
                signatures=[], no_progress_k=2, iters=0, max_iters=20,
                tokens_spent=0, token_ceiling=0)
    base.update(kw)
    return base

def test_accept_green_stops():
    stop, reason = se.evaluate_stop(_state(accept_exit=0))
    assert stop is True and reason == "accept_cmd-green"

def test_all_goals_done_stops():
    stop, reason = se.evaluate_stop(_state(goals_total=3, goals_done=3))
    assert stop is True and reason == "all-goals-done"

def test_no_progress_stops():
    stop, reason = se.evaluate_stop(_state(signatures=["a", "a"], no_progress_k=2))
    assert stop is True and reason == "no-progress"

def test_iter_ceiling_stops():
    stop, reason = se.evaluate_stop(_state(iters=20, max_iters=20))
    assert stop is True and reason == "iters"

def test_budget_spent_stops():
    stop, reason = se.evaluate_stop(_state(tokens_spent=500, token_ceiling=500))
    assert stop is True and reason == "budget-spent"

def test_budget_zero_means_no_cap():
    stop, reason = se.evaluate_stop(_state(tokens_spent=999999, token_ceiling=0))
    assert stop is False

def test_continue_when_nothing_met():
    stop, reason = se.evaluate_stop(_state(goals_total=3, goals_done=1, iters=2))
    assert stop is False and reason == "continue"

# --- THE GATE LAW: a green per-child accept_cmd must NOT complete a campaign ---
def test_campaign_accept_green_does_not_complete():
    # the production-stutter regression test: 1 of 5 done, accept_cmd green
    stop, reason = se.evaluate_stop(_state(accept_exit=0, goals_total=5, goals_done=1))
    assert stop is False and reason == "continue"

def test_campaign_completes_only_on_all_goals_done():
    stop, reason = se.evaluate_stop(_state(accept_exit=0, goals_total=5, goals_done=5))
    assert stop is True and reason == "all-goals-done"

# --- gate-error: a broken gate must fail loud, not burn the budget ---
def test_gate_error_fails_loud():
    stop, reason = se.evaluate_stop(_state(accept_exit=127))
    assert stop is True and reason == "gate-error"

def test_gate_error_skipped_in_campaign():
    stop, reason = se.evaluate_stop(_state(accept_exit=127, goals_total=5, goals_done=2))
    assert reason != "gate-error" and stop is False

def test_legit_not_done_continues():
    stop, reason = se.evaluate_stop(_state(accept_exit=1))
    assert stop is False and reason == "continue"

# --- fuzzy-judge STOP path (was vaporware: declared but never evaluated) ---
def test_fuzzy_judge_pass_stops():
    stop, reason = se.evaluate_stop(_state(fuzzy_verdict="pass"))
    assert stop is True and reason == "fuzzy-judge-pass"

def test_fuzzy_judge_continue_when_not_pass():
    stop, reason = se.evaluate_stop(_state(fuzzy_verdict="continue"))
    assert stop is False and reason == "continue"

# --- no-progress is judged from the signature history, not a mutable flag ---
def test_no_progress_continues_when_signatures_differ():
    # a campaign that folded its advancing goals_done into the marker has
    # distinct recent signatures, so it is not a stall
    stop, reason = se.evaluate_stop(_state(signatures=["a", "b"], no_progress_k=2,
                                           goals_total=5, goals_done=3))
    assert stop is False and reason == "continue"

def test_no_progress_default_k_is_three():
    stop, reason = se.evaluate_stop(dict(signatures=["a", "a"]))  # 2 < default k=3
    assert reason != "no-progress"

# --- campaign fails loud on a broken child gate ---
def test_campaign_child_gate_error():
    stop, reason = se.evaluate_stop(_state(goals_total=5, goals_done=2, child_accept_exit=127))
    assert stop is True and reason == "child-gate-error"

# --- long-horizon caps for the timer-cadence path (never-stop guard) ---
def test_deadline_stops():
    stop, reason = se.evaluate_stop(_state(deadline_passed=True))
    assert stop is True and reason == "deadline"

def test_run_ceiling_stops():
    stop, reason = se.evaluate_stop(_state(runs_total=10, runs_ceiling=10))
    assert stop is True and reason == "run-ceiling"

def test_stop_detail_carries_progress():
    d = se.stop_detail(_state(signatures=["a", "a"], no_progress_k=2,
                              goals_total=5, goals_done=2, next_pending="goal-c"))
    assert d["reason"] == "no-progress"
    assert d["goals_done"] == 2 and d["goals_total"] == 5
    assert d["remaining"] == 3 and d["next_pending"] == "goal-c"

import contract as ct

SAMPLE = """SLUG       : build-x
CAMPAIGN   : none
TRIGGER    : every 30m
UNATTENDED : false
ACTION     : goal-phase
BUDGET     : max_iters=20 | token_ceiling=0 | max_fanout=8
"""

def test_parse_basic_fields():
    fields = ct.parse_contract(SAMPLE)
    assert fields["SLUG"] == "build-x"
    assert fields["TRIGGER"] == "every 30m"
    assert fields["UNATTENDED"] == "false"

def test_parse_ignores_blank_and_nonkv():
    fields = ct.parse_contract("SLUG : x\n\n# comment\nACTION : goal-phase\n")
    assert fields["SLUG"] == "x"
    assert fields["ACTION"] == "goal-phase"

def test_render_roundtrip():
    fields = ct.parse_contract(SAMPLE)
    rendered = ct.render_contract(fields)
    assert ct.parse_contract(rendered) == fields

def test_validate_full_ok():
    assert ct.validate_contract({"SLUG": "x", "ACTION": "goal-phase", "STOP": "all-goals-done"}) == []

def test_validate_flags_missing():
    assert ct.validate_contract({"ACTION": "goal-phase"}) == ["missing-slug", "missing-stop"]

def test_validate_illegal_action():
    assert ct.validate_contract({"SLUG": "x", "ACTION": "bogus", "STOP": "iters"}) == ["illegal-action"]

def test_validate_skill_action_ok():
    assert ct.validate_contract({"SLUG": "x", "ACTION": "skill:foo", "STOP": "iters"}) == []

import preflight as pf

def test_missing_accept_cmd_fails_condition2():
    contract = {"BUDGET": "max_iters=20", "STOP": "iters"}
    beacon = {}
    failures = pf.check_readiness(contract, beacon)
    assert "condition-2-no-gate" in failures

def test_fully_specified_passes():
    contract = {"BUDGET": "max_iters=20", "STOP": "accept_cmd-green"}
    beacon = {"accept_cmd": "pwsh run-all.ps1"}
    failures = pf.check_readiness(contract, beacon)
    assert failures == []

def test_exclusion_flags_auth():
    hits = pf.flag_excluded("refactor the auth module login flow")
    assert "auth" in hits

def test_exclusion_clean_goal():
    hits = pf.flag_excluded("fix flaky tests in the parser module")
    assert hits == []

def test_fuzzy_judge_stop_satisfies_condition2():
    contract = {"STOP": "fuzzy-judge"}
    beacon = {}
    failures = pf.check_readiness(contract, beacon)
    assert "condition-2-no-gate" not in failures

# --- word-boundary exclusion: no substring false positives ---
def test_exclusion_author_not_flagged():
    assert pf.flag_excluded("document the author notes") == []

def test_exclusion_schematic_not_flagged():
    assert pf.flag_excluded("draw the schematic diagram") == []

def test_exclusion_destructive_verb():
    hits = pf.flag_excluded("deploy to production")
    assert "deploy" in hits and "production" in hits

# --- THE GATE LAW scope check ---
def test_scope_warns_single_file_gate():
    w = pf.scope_warnings("document all FIX messages",
                          {"accept_cmd": "Select-String -Path 'docs/ae.md' -Pattern 'x'"})
    assert w == ["gate-scope-narrow"]

def test_scope_ok_aggregating_gate():
    w = pf.scope_warnings("document all FIX messages",
                          {"accept_cmd": "$r=gci *.md; $r | Where-Object { $_ }"})
    assert w == []

def test_scope_ok_single_goal():
    w = pf.scope_warnings("document the AE message",
                          {"accept_cmd": "Select-String -Path 'ae.md' -Pattern x"})
    assert w == []

def test_scope_ok_campaign():
    w = pf.scope_warnings("document all FIX messages",
                          {"accept_cmd": "Select-String -Path 'ae.md' -Pattern x"}, campaign=True)
    assert w == []

def test_scope_warns_undeclared():
    assert pf.scope_warnings("document every message", {}) == ["gate-scope-undeclared"]

# --- scope check must NOT fire on the canonical green-list test-runner gate ---
def test_scope_ok_test_runner():
    assert pf.scope_warnings("fix all flaky tests", {"accept_cmd": "pwsh run-all.ps1"}) == []

def test_scope_ok_fuzzy_stop():
    assert pf.scope_warnings("summarize every chapter", {}, stop="fuzzy-judge") == []

def test_scope_ok_all_goals_done_stop():
    assert pf.scope_warnings("document all messages",
                             {"accept_cmd": "Select-String -Path 'ae.md' -Pattern x"},
                             stop="all-goals-done") == []

def test_scope_no_fp_on_one_item():
    assert pf.scope_warnings("fix 1 broken test",
                             {"accept_cmd": "Select-String -Path 'ae.md' -Pattern x"}) == []

def test_scope_no_fp_on_both():
    assert pf.scope_warnings("refactor both helper and caller",
                             {"accept_cmd": "Select-String -Path 'ae.md' -Pattern x"}) == []

# --- gate_is_single_artifact heuristics (direct, not just via scope_warnings) ---
def test_gate_single_one_file():
    assert pf.gate_is_single_artifact("Select-String -Path 'ae.md' -Pattern x") is True

def test_gate_single_dotted_pattern():
    # a dotted -Pattern arg must NOT be miscounted as a second file
    assert pf.gate_is_single_artifact("Select-String -Path 'docs/ae.md' -Pattern 'FIX.msg'") is True

def test_gate_not_single_two_files():
    assert pf.gate_is_single_artifact("type a.md b.md") is False

def test_gate_not_single_test_runner():
    assert pf.gate_is_single_artifact("pwsh run-all.ps1") is False

def test_gate_not_single_aggregating():
    assert pf.gate_is_single_artifact("$r | Where-Object { $_ }") is False

# --- untrusted-input validators ---
def test_beacon_cell_rejects_traversal():
    assert pf.validate_beacon_cell("../../etc/passwd") == ["unsafe-beacon-cell"]

def test_beacon_cell_clean():
    assert pf.validate_beacon_cell("docs/goal-a-audit-tracker.md") == []

def test_skill_ref_clean():
    assert pf.validate_skill_ref("personal-workflow") == []

def test_skill_ref_rejects_injection():
    assert pf.validate_skill_ref("foo; rm -rf /") == ["unsafe-skill-ref"]

def test_exclusion_destructive_extended():
    hits = pf.flag_excluded("rm the build dir then force push to main")
    assert "rm" in hits and "force push" in hits

# --- external-action detector: external-world steps auto-select goal-phase ---
def test_external_action_start_service():
    assert "external-action" in pf.detect_external_actions("start the background worker service")

def test_external_action_click():
    assert "external-action" in pf.detect_external_actions("click Send TradeReportAck")

def test_external_action_observe_request():
    hits = pf.detect_external_actions("restart the sim and paste the console")
    assert "external-action" in hits and "human-observation" in hits

def test_external_action_clean_autonomous():
    # a green-list autonomous goal must NOT false-trigger (the over-fence FP guard)
    assert pf.detect_external_actions("fix all flaky tests in the parser module") == []

def test_external_action_run_tests_not_flagged():
    assert pf.detect_external_actions("run the unit tests and lint the diff") == []

def test_external_action_service_layer_not_flagged():
    assert pf.detect_external_actions("refactor the service layer module") == []

def test_deployed_config_program_files():
    assert pf.is_deployed_config_path(r"C:\Program Files (x86)\SomeVendor\App_Setup\App.exe.config") is True

def test_deployed_config_programdata():
    assert pf.is_deployed_config_path(r"C:\ProgramData\SomeApp\config.txt") is True

def test_deployed_config_repo_file_is_not():
    assert pf.is_deployed_config_path("plugins/ping-personal/skills/personal-loop/SKILL.md") is False

def test_deployed_config_declared_root():
    assert pf.is_deployed_config_path("/opt/myapp/app.config", deploy_roots=["/opt/myapp"]) is True

import campaign as cmp

CAMPAIGN_MD = """# Campaign: big-task

| goal | state | beacon |
|---|---|---|
| goal-a | done | docs/goal-a-audit-tracker.md |
| goal-b | pending | docs/goal-b-audit-tracker.md |
| goal-c | pending | docs/goal-c-audit-tracker.md |
"""

def test_parse_children():
    children = cmp.parse_children(CAMPAIGN_MD)
    assert len(children) == 3
    assert children[0] == {"goal": "goal-a", "state": "done", "beacon": "docs/goal-a-audit-tracker.md"}

def test_next_pending_skips_done():
    children = cmp.parse_children(CAMPAIGN_MD)
    assert cmp.next_pending_goal(children) == "goal-b"

def test_next_pending_none_when_all_done():
    children = [{"goal": "g", "state": "done", "beacon": "x"}]
    assert cmp.next_pending_goal(children) is None

def test_mark_done_flips_state():
    updated = cmp.mark_goal_done(CAMPAIGN_MD, "goal-b")
    children = cmp.parse_children(updated)
    states = {c["goal"]: c["state"] for c in children}
    assert states["goal-b"] == "done"
    assert states["goal-c"] == "pending"

def test_goal_exists_true_and_false():
    children = cmp.parse_children(CAMPAIGN_MD)
    assert cmp.goal_exists(children, "goal-b") is True
    assert cmp.goal_exists(children, "goal-z") is False

def test_mark_missing_slug_is_noop():
    updated = cmp.mark_goal_done(CAMPAIGN_MD, "goal-z")
    assert updated == CAMPAIGN_MD   # silent no-op must not corrupt the table

def test_mark_idempotent_on_done():
    updated = cmp.mark_goal_done(CAMPAIGN_MD, "goal-a")
    states = {c["goal"]: c["state"] for c in cmp.parse_children(updated)}
    assert states["goal-a"] == "done" and states["goal-b"] == "pending"

import secrets_scan as ss

def test_aws_key_caught():
    assert len(ss.scan("export AWS_KEY=AKIAIOSFODNN7EXAMPLE")) > 0

def test_github_pat_caught():
    assert len(ss.scan("token: ghp_" + "A" * 36)) > 0

def test_bearer_token_caught():
    assert len(ss.scan("Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9" + "x" * 40)) > 0

def test_tsql_connstring_caught():
    assert len(ss.scan("Data Source=SQLDEV01;Initial Catalog=AppDb;Password=hunter2")) > 0

def test_clean_diff_returns_empty():
    assert ss.scan("def get_token(): return os.environ['API_TOKEN']") == []

def test_fp_env_var_ignored():
    assert ss.scan("password = os.getenv('DB_PASSWORD')") == []

def test_fp_placeholder_ignored():
    assert ss.scan("secret: <your-secret-here>") == []

# --- hardening: an adjacent env-var must NOT suppress a real secret ---
def test_adjacent_envvar_does_not_suppress():
    leak = "config: ${LOG_LEVEL} Data Source=PRODDB;Initial Catalog=X;Password=RealSecret123;"
    assert len(ss.scan(leak)) > 0

def test_isfp_inspects_match_only():
    assert ss._is_fp("${MY_TOKEN}") is True
    assert ss._is_fp("AKIAIOSFODNN7EXAMPLE") is False

def test_stripe_key_caught():
    assert len(ss.scan("key=sk_live_" + "a" * 24)) > 0

def test_redaction_leaks_no_prefix():
    red = ss.scan("AKIAIOSFODNN7EXAMPLE")[0]
    assert "AKIA" not in red and "REDACTED" in red

def test_connstring_envhost_literal_pw_caught():
    # an env-var host must NOT mask a literal password elsewhere in the span
    leak = "Data Source=${HOST};Initial Catalog=X;Password=RealSecret123;"
    assert len(ss.scan(leak)) > 0

def test_connstring_env_password_is_fp():
    # but a connstring whose password VALUE is itself an env ref is a true FP
    assert ss.scan("Data Source=${HOST};Initial Catalog=X;Password=${DB_PW};") == []

import halt as hl

def test_sentinel_and_block():
    assert hl.sentinel("secret-detected") == "BLOCKED: secret-detected"
    assert hl.is_blocked("child-state: BLOCKED: secret-detected") is True
    assert hl.is_blocked("child-state: ok") is False

def test_write_halt_creates_status():
    d = tempfile.mkdtemp()
    p = hl.write_halt(d, "secret-detected", "leak in app.config", "2026-06-17T00:00")
    assert os.path.exists(p)
    txt = open(p, encoding="utf-8").read()
    assert "secret-detected" in txt and "force-resume" in txt

import discover_sources as ds

def _full_map():
    return {"jira": {}, "codebase": {}, "logs": {}, "graph": {}, "db": {}}

def test_probe_finds_ticket_in_goal():
    m = ds.probe_repo(os.path.dirname(__file__), goal_text="re-verify ST-690 round trip")
    assert m["jira"]["ticket"] == "ST-690"

def test_probe_no_ticket_is_none():
    m = ds.probe_repo(os.path.dirname(__file__), goal_text="fix the parser")
    assert m["jira"]["ticket"] is None

def test_probe_has_required_slots():
    m = ds.probe_repo(os.path.dirname(__file__))
    for slot in ("jira", "codebase", "logs", "graph", "db"):
        assert slot in m

def test_merge_rejects_unknown_key():
    try:
        ds.merge_evidence(_full_map(), {"bogus": {}})
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_merge_requires_required_slots():
    try:
        ds.merge_evidence({"jira": {}}, {})  # missing codebase/logs/graph/db
        assert False, "expected ValueError"
    except ValueError:
        pass

def test_merge_folds_observed_into_slot():
    merged = ds.merge_evidence(_full_map(), {"jira": {"server": "live"}, "email": {"server": "live"}})
    assert merged["jira"]["server"] == "live" and merged["email"]["server"] == "live"

def test_assert_no_secret_value_ok_on_locations():
    ds.assert_no_secret_value({"db": {"creds_at": ".env:SAPIDF_CONNECTION"}})  # no raise

def test_assert_no_secret_value_raises_on_value():
    try:
        ds.assert_no_secret_value(
            {"db": {"conn": "Data Source=PRODDB;Initial Catalog=X;Password=hunter2"}})
        assert False, "expected ValueError"
    except ValueError:
        pass

import orchestrate as orch

def test_route_single_shot():
    assert orch.route({"n_steps": 1})["target"] == "subagent"

def test_route_multi_step_single_domain():
    assert orch.route({"n_steps": 3, "n_domains": 1})["target"] == "personal-goal"

def test_route_multi_domain():
    assert orch.route({"n_domains": 2})["target"] == "personal-workflow"

def test_route_multi_phase():
    assert orch.route({"n_steps": 4, "multi_phase": True})["target"] == "personal-workflow"

def test_route_nested_loop():
    assert orch.route({"has_own_gate": True, "long_horizon": True})["target"] == "personal-loop"

def test_depth_cap_refuses_at_2():
    assert orch.check_depth(2) == ["depth-cap"]

def test_depth_ok_at_1():
    assert orch.check_depth(1) == []

def test_width_free_normal():
    assert orch.check_width(3) == "free"

def test_width_confirm_normal():
    assert orch.check_width(5) == "confirm"

def test_width_stop_normal():
    assert orch.check_width(7) == "stop"

def test_width_concurrent_session_tightens():
    assert orch.check_width(2, other_session=True) == "confirm"
    assert orch.check_width(4, other_session=True) == "stop"

def test_external_read_local_always_ok():
    assert pf.is_external_read_allowed("codebase", True, set()) == []

def test_external_read_attended_ok():
    assert pf.is_external_read_allowed("jira", False, set()) == []

def test_external_read_unattended_refused():
    assert pf.is_external_read_allowed("jira", True, set()) == ["external-read-refused"]

def test_external_read_unattended_allowlisted():
    assert pf.is_external_read_allowed("jira", True, {"jira"}) == []

if __name__ == "__main__":
    test_identical_ticks_collapse()
    test_changed_output_changes_signature()
    test_no_progress_fires_after_k_identical()
    test_no_progress_resets_on_change()
    test_no_progress_needs_k_samples()
    test_progress_marker_changes_signature()
    test_same_marker_same_signature()
    print("progress_hash: ALL PASS")

    test_accept_green_stops()
    test_all_goals_done_stops()
    test_no_progress_stops()
    test_iter_ceiling_stops()
    test_budget_spent_stops()
    test_budget_zero_means_no_cap()
    test_continue_when_nothing_met()
    test_campaign_accept_green_does_not_complete()
    test_campaign_completes_only_on_all_goals_done()
    test_gate_error_fails_loud()
    test_gate_error_skipped_in_campaign()
    test_legit_not_done_continues()
    test_fuzzy_judge_pass_stops()
    test_fuzzy_judge_continue_when_not_pass()
    test_no_progress_continues_when_signatures_differ()
    test_no_progress_default_k_is_three()
    test_campaign_child_gate_error()
    test_deadline_stops()
    test_run_ceiling_stops()
    test_stop_detail_carries_progress()
    print("stop_eval: ALL PASS")

    test_parse_basic_fields()
    test_parse_ignores_blank_and_nonkv()
    test_render_roundtrip()
    test_validate_full_ok()
    test_validate_flags_missing()
    test_validate_illegal_action()
    test_validate_skill_action_ok()
    print("contract: ALL PASS")

    test_missing_accept_cmd_fails_condition2()
    test_fully_specified_passes()
    test_exclusion_flags_auth()
    test_exclusion_clean_goal()
    test_fuzzy_judge_stop_satisfies_condition2()
    test_exclusion_author_not_flagged()
    test_exclusion_schematic_not_flagged()
    test_exclusion_destructive_verb()
    test_scope_warns_single_file_gate()
    test_scope_ok_aggregating_gate()
    test_scope_ok_single_goal()
    test_scope_ok_campaign()
    test_scope_warns_undeclared()
    test_scope_ok_test_runner()
    test_scope_ok_fuzzy_stop()
    test_scope_ok_all_goals_done_stop()
    test_scope_no_fp_on_one_item()
    test_scope_no_fp_on_both()
    test_gate_single_one_file()
    test_gate_single_dotted_pattern()
    test_gate_not_single_two_files()
    test_gate_not_single_test_runner()
    test_gate_not_single_aggregating()
    test_beacon_cell_rejects_traversal()
    test_beacon_cell_clean()
    test_skill_ref_clean()
    test_skill_ref_rejects_injection()
    test_exclusion_destructive_extended()
    test_external_action_start_service()
    test_external_action_click()
    test_external_action_observe_request()
    test_external_action_clean_autonomous()
    test_external_action_run_tests_not_flagged()
    test_external_action_service_layer_not_flagged()
    test_deployed_config_program_files()
    test_deployed_config_programdata()
    test_deployed_config_repo_file_is_not()
    test_deployed_config_declared_root()
    print("preflight: ALL PASS")

    test_parse_children()
    test_next_pending_skips_done()
    test_next_pending_none_when_all_done()
    test_mark_done_flips_state()
    test_goal_exists_true_and_false()
    test_mark_missing_slug_is_noop()
    test_mark_idempotent_on_done()
    print("campaign: ALL PASS")

    test_aws_key_caught()
    test_github_pat_caught()
    test_bearer_token_caught()
    test_tsql_connstring_caught()
    test_clean_diff_returns_empty()
    test_fp_env_var_ignored()
    test_fp_placeholder_ignored()
    test_adjacent_envvar_does_not_suppress()
    test_isfp_inspects_match_only()
    test_stripe_key_caught()
    test_redaction_leaks_no_prefix()
    test_connstring_envhost_literal_pw_caught()
    test_connstring_env_password_is_fp()
    print("secrets_scan: ALL PASS")

    test_sentinel_and_block()
    test_write_halt_creates_status()
    print("halt: ALL PASS")

    test_probe_finds_ticket_in_goal()
    test_probe_no_ticket_is_none()
    test_probe_has_required_slots()
    test_merge_rejects_unknown_key()
    test_merge_requires_required_slots()
    test_merge_folds_observed_into_slot()
    test_assert_no_secret_value_ok_on_locations()
    test_assert_no_secret_value_raises_on_value()
    print("discover_sources: ALL PASS")

    test_route_single_shot()
    test_route_multi_step_single_domain()
    test_route_multi_domain()
    test_route_multi_phase()
    test_route_nested_loop()
    test_depth_cap_refuses_at_2()
    test_depth_ok_at_1()
    test_width_free_normal()
    test_width_confirm_normal()
    test_width_stop_normal()
    test_width_concurrent_session_tightens()
    print("orchestrate: ALL PASS")

    test_external_read_local_always_ok()
    test_external_read_attended_ok()
    test_external_read_unattended_refused()
    test_external_read_unattended_allowlisted()
    print("preflight (external-read): ALL PASS")

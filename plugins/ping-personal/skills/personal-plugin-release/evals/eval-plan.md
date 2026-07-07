# Eval plan: personal-plugin-release

## Target behavior (the contract)
Given a release request, the skill must drive bump -> PR -> merge -> local
install -> reload -> VERIFY-LOADED, keeping the three version files coupled
(plugin.json, root marketplace.json, user-scope installed_plugins.json) and
never claiming success without quoting the observed installed version. It
must NOT bump unasked, push main directly, or hand-edit installed_plugins.json.

## Failure modes -> graders
| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift stops triggering | code: frontmatter check |
| 2 | A version file drops out of the documented coupling | code: three_file_coupling |
| 3 | Wrong install key (ping-personal@personal-plugin) creeps back | code: wrong-key warning check |
| 4 | Verify-loaded gate weakened or removed | code: verify_loaded_gate |
| 5 | Eval-suite ship gate or never-push-main boundary lost | code: verify_loaded_gate |
| 6 | Grader goes dead (matches anything) | code: calibration (mutated copy must FAIL) |

## Eval cases
- Baseline: eval.ps1 green on the shipped SKILL.md.
- Calibration: copy with installed_plugins.json removed must fail coupling.

## Ship gate
eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.

# Eval plan: personal-fix-decode

## Target behavior (the contract)
Given a raw FIX 4.4 message (SOH / | / ^A delimited), lib/fix_decode.py
prints a tag/name/value table with message-type and enum decoding, warns on
BodyLength/CheckSum mismatch, exits 2 with DECODE-FAIL on non-FIX input, and
never invents names for unknown tags. --json emits a parseable object.

## Failure modes -> graders
| # | Failure | Grader |
|---|---|---|
| 1 | Frontmatter drift | code: frontmatter check |
| 2 | Script referenced but missing on disk | code: referential_integrity |
| 3 | AE decode regresses (msg type, party fields, enums) | code: decode_good_ae on locked fixture |
| 4 | Reject analysis regresses (371/373 decode) | code: decode_reject on locked fixture |
| 5 | Decoder accepts garbage (silent success) | code: calibration_bad (exit != 0 + DECODE-FAIL) |
| 6 | --json shape drift breaks diff mode | code: json_mode |

## Eval cases
Fixtures: good-ae-message.txt (TradeCaptureReport with 448/447/452),
good-reject-message.txt (35=3 with 371/372/373), bad-not-fix.txt (prose).

## Ship gate
eval.ps1 exits 0 AND run-all.ps1 prints ALL EVALS PASS.

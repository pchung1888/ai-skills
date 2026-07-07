---
name: personal-fix-decode
model: sonnet
description: Decode raw FIX 4.4 protocol messages into a readable tag table and explain what is wrong -- tag meanings, message type, reject causes, incoming-vs-outgoing diffs. Trigger on /personal-fix-decode, any pasted raw FIX stream ("8=FIX.4.4..."), "what is tag 448", "why is this AE message rejected", "decode this FIX message", "walk the incoming vs outgoing message". Ships with lib/fix_decode.py (deterministic decoder, common-tag dictionary).
---

# /personal-fix-decode

Turn a pasted `8=FIX.4.4...` stream into something a human can reason about,
then answer the actual question (usually: why was it rejected, or where does
a field land downstream).

## Procedure

1. **Decode deterministically first.** Save the raw message to a temp file
   and run the bundled decoder rather than eyeballing tags:

   ```
   python "${CLAUDE_PLUGIN_ROOT}/skills/personal-fix-decode/lib/fix_decode.py" <file>
   python .../fix_decode.py <file> --json        # machine-readable
   printf '%s' "<msg>" | python .../fix_decode.py -
   ```

   It accepts SOH (\x01), `|`, or `^A` delimiters, prints
   `tag  name  value  [decoded enum]` per field in wire order, names the
   message type (35=AE TradeCaptureReport, 35=J AllocationInstruction,
   35=3 SessionReject, 35=8 ExecutionReport, ...), expands repeating-group
   party fields (448/447/452), and warns on BodyLength(9)/CheckSum(10)
   mismatches. Unknown tags print as `tag <n> (unknown)` -- never invent a
   name for one.
2. **Answer the question against the decode.** Reject analysis: for 35=3 read
   371/372/373 (RefTagID / RefMsgType / SessionRejectReason) + 58 Text; for
   business rejects (35=j or an app-level reject) read 380 and 58. Quote the
   decoded lines that carry the answer.
3. **Diff mode.** For "incoming vs outgoing" walks, decode both with
   `--json`, diff tag-by-tag, and present only the differing tags plus any
   tag present on one side only.
4. **Downstream mapping questions** ("where does tag 448 land in the host
   app's Trade table?") are host-repo facts, not protocol facts: grep the host
   repo's FIX engine / stored procedures for the tag number and answer with
   file:line evidence, or say the mapping is not in reach of this repo.

## Boundaries

- Decode-and-explain only: never send, replay, or modify messages on any
  FIX session.
- Raw messages can contain account identifiers -- keep temp files in
  `.claude/tmp/` or the session scratchpad, never commit them.
- Enum meanings come from the dictionary in `lib/fix_decode.py`; if a value
  is not in the dictionary, say so instead of guessing (the FIX spec allows
  custom values above 5000 and bilateral meanings).

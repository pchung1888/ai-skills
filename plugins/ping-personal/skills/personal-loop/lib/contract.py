#!/usr/bin/env python3
"""contract.py -- parse/render the loop-contract block."""
import argparse, json, sys

FIELD_ORDER = ["SLUG","CAMPAIGN","TRIGGER","UNATTENDED","SCOPE","ACTION",
               "BUDGET","STOP","GATE","GATE_SCOPE","ENDING_CONDITIONS",
               "CRITIC","REPORT","VISION","START_REF"]

LEGAL_ACTION = {"inner-goal", "goal-phase", "skill"}
REQUIRED_FIELDS = ("SLUG", "ACTION", "STOP")

def validate_contract(fields: dict) -> list[str]:
    """Return a list of failures (empty = valid). Catches a contract that
    parses cleanly but is missing a required field or has an illegal ACTION --
    today such a contract sails through parse and only fails far downstream."""
    failures = [f"missing-{k.lower()}" for k in REQUIRED_FIELDS if not fields.get(k)]
    action = fields.get("ACTION", "")
    base = action.split(":", 1)[0].strip()  # "skill:foo" -> "skill"
    if action and base not in LEGAL_ACTION:
        failures.append("illegal-action")
    return failures

def parse_contract(text: str) -> dict:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or ":" not in s:
            continue
        key, _, value = s.partition(":")
        key = key.strip()
        if not key or not key.isupper():
            continue
        fields[key] = value.strip()
    return fields

def render_contract(fields: dict) -> str:
    ordered = [k for k in FIELD_ORDER if k in fields]
    extras = [k for k in fields if k not in FIELD_ORDER]
    return "\n".join(f"{k:<10} : {fields[k]}" for k in ordered + extras) + "\n"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parse", required=True)
    a = ap.parse_args()
    with open(a.parse, encoding="utf-8") as fh:
        print(json.dumps(parse_contract(fh.read()), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())

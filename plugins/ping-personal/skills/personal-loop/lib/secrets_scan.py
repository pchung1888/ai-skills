#!/usr/bin/env python3
"""secrets_scan.py -- credential pattern scanner for unattended loop ticks.

Hardened after audit:
  - _is_fp now inspects ONLY the matched text, not a +/-40-char window. The old
    window let a benign ${ENV} ref within ~80 chars silently SUPPRESS a real
    adjacent secret (proven: 'config: ${LOG_LEVEL} Data Source=...;Password=X'
    returned clean). Under-blocking is the dangerous direction for a gate that
    stands between an unattended loop and a committed credential.
  - redaction never echoes a raw prefix into the status/REPORT artifacts; it
    emits a non-reversible short hash instead.
  - pattern vocabulary widened (Stripe / OpenAI / Google / generic api-key).
"""
import argparse, hashlib, json, re, sys

PATTERNS = [
    r'AKIA[0-9A-Z]{16}',
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----',
    r'xox[baprse]-[0-9A-Za-z\-]{10,}',
    r'ghp_[A-Za-z0-9]{36}',
    r'gho_[A-Za-z0-9]{36}',
    r'ghs_[A-Za-z0-9]{36}',
    r'ghu_[A-Za-z0-9]{36}',
    r'sk_live_[0-9A-Za-z]{16,}',
    r'sk-[A-Za-z0-9]{20,}',
    r'AIza[0-9A-Za-z\-_]{35}',
    r'(?i)api[_-]?key\s*[:=]\s*["\'][A-Za-z0-9_\-]{16,}["\']',
    r'(?i)(password|pwd|secret)\s*=\s*["\'][^"\'$<\{]{6,}["\']',
    r'(?i)User\s+ID\s*=\s*[^;]+;\s*(?:Pwd|Password)\s*=\s*[^;]+',
    r'(?i)Data\s+Source\s*=\s*[^;]+;\s*.*Password\s*=\s*[^;]+',
    r'(?i)Authorization\s*:\s*Bearer\s+[A-Za-z0-9\-._~+/]{20,}',
]
FP_PATTERNS = [
    r'\$\{?[A-Z_][A-Z0-9_]*\}?',
    r'<[a-z][a-z_-]*>',
    r'os\.environ',
    r'os\.getenv',
    r'process\.env\.',
]
# For credential-bearing connection strings, judge ONLY the password VALUE, not
# the whole "Data Source=...;Password=..." span -- otherwise a ${ENV} host
# elsewhere in the span would mask a real literal password (silent under-block).
_CRED_VALUE = re.compile(r'(?i)(?:password|pwd)\s*=\s*([^;"\']+)')


def _is_fp(match_text: str) -> bool:
    """A match is a false positive only if the credential VALUE itself is a
    placeholder / env-var reference -- never because something benign sits
    elsewhere in a multi-field match."""
    m = _CRED_VALUE.search(match_text)
    target = m.group(1) if m else match_text
    return any(re.search(fp, target) for fp in FP_PATTERNS)


def _redact(match_text: str) -> str:
    return "***REDACTED:" + hashlib.sha256(match_text.encode("utf-8")).hexdigest()[:6] + "***"


def scan(text: str) -> list[str]:
    matches = []
    for pat in PATTERNS:
        for m in re.finditer(pat, text):
            if not _is_fp(m.group()):
                matches.append(_redact(m.group()))
    return matches


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    a = ap.parse_args()
    results = scan(a.text)
    print(json.dumps({"matches": results, "clean": len(results) == 0}))
    return 1 if results else 0


if __name__ == "__main__":
    sys.exit(main())

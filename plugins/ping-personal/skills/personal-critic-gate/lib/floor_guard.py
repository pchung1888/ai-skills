#!/usr/bin/env python3
"""floor_guard: flag lowered-bar signals in `git diff <base>`.

Usage (run inside the git repo): python floor_guard.py [--base REF]   (default HEAD~1)
Prints one row per hit: <file>:<line> <signal> | <line text>
Last line: FLOOR PASS (exit 0) or FLOOR FAIL <n> (exit 1).
Scans code and test files only; skips *.md, this script, its own test, and evals|tests/fixtures folders.
"""
import argparse, re, subprocess, sys

CODE = {'.py', '.ps1', '.psm1', '.ts', '.tsx', '.js', '.jsx', '.vb', '.cs', '.sql', '.sh', '.asp', '.json'}
_D = 'plugins/ping-personal/skills/personal-critic-gate/'
SKIP_PATHS = {_D + 'lib/floor_guard.py', _D + 'evals/test_floor_guard.py'}
FIXTURES = re.compile(r'(^|/)(evals|tests?)/fixtures/')
TESTY = re.compile(r'test|eval|spec', re.I)
DEL_TEST = re.compile(r'^\s*(def test_|async def test_|(it|test|describe)\(|@Test\b|Describe\s|It\s+[\'"])')
SKIP_ADD = re.compile(r'pytest\.mark\.(skip|xfail)|pytest\.skip\(|unittest\.skip|\b(it|test|describe)\.(skip|todo)\b|\bx(it|describe)\(|^\s*(It|Describe|Context)\b.*-Skip\b|-Pending\b')
LINT_ADD = re.compile(r'eslint-disable|@ts-ignore|@ts-nocheck|#\s*noqa(?!:\s*E402\s*$)|//\s*noqa|type:\s*ignore|pylint:\s*disable|SuppressMessage')
STUB_ADD = re.compile(r'catch\s*(\([^)]*\))?\s*\{\s*\}|except[^:\n]*:\s*pass\b|^\s*pass\s*$|NotImplementedError|catch\s*\{\s*\}')
ASSERT_DEL = re.compile(r'\bassert\b|\bexpect\(|\.Should\b|\bthrow\s+["\']|self\.assert')
THRESH = re.compile(r'>=|<=|-ge\b|-gt\b|\bmin|thresh|coverage|score|[^=!<>]>[^=>]|-lt\b', re.I)
NUM = re.compile(r'\d+(?:\.\d+)?')


def scanned(path):
    name = path.rsplit('/', 1)[-1]
    if path in SKIP_PATHS or FIXTURES.search(path):
        return False
    return '.' + name.rsplit('.', 1)[-1].lower() in CODE if '.' in name else False


def hunk_hits(path, line, rem, add):
    out = []
    testy = bool(TESTY.search(path))
    for t in rem:
        if DEL_TEST.match(t) and testy:
            out.append((line, 'deleted test', t))
        if ASSERT_DEL.search(t) and testy:
            out.append((line, 'assertion removed', t))
    for n, t in add:
        for rx, sig in ((SKIP_ADD, 'skip/xfail added'), (LINT_ADD, 'lint/type suppression added'), (STUB_ADD, 'empty catch or stub added')):
            if rx.search(t):
                out.append((n, sig, t))
    if testy:  # a threshold line rewritten with a smaller number
        for r, (n, a) in zip(rem, add):
            skel = lambda s: NUM.sub('#', s).strip()
            rn, an = [float(x) for x in NUM.findall(r)], [float(x) for x in NUM.findall(a)]
            if skel(r) == skel(a) and THRESH.search(a) and len(rn) == len(an) and any(y < x for x, y in zip(rn, an)):
                out.append((n, 'threshold lowered', a))
    return out


def unquote(tok):
    """Decode git's C-style quoted path (octal bytes, \\n, \\t, \\", \\\\)."""
    out, body, k = bytearray(), tok[1:-1], 0
    esc = {'n': 10, 't': 9, '"': 34, '\\': 92}
    while k < len(body):
        c = body[k]
        if c == '\\' and k + 1 < len(body):
            m = re.match(r'[0-7]{3}', body[k + 1:])
            if m:
                out.append(int(m.group(), 8)); k += 4; continue
            out.append(esc.get(body[k + 1], ord(body[k + 1]))); k += 2; continue
        out += c.encode('utf-8'); k += 1
    return out.decode('utf-8', errors='replace')


def header_path(h):
    """Path from a 'diff --git a/P b/P' header (no renames), or None."""
    q = re.findall(r'"(?:[^"\\]|\\.)*"', h)
    if len(q) == 2:
        a, b = unquote(q[0]), unquote(q[1])
    else:
        r = h[len('diff --git '):]
        n = (len(r) - 4) // 2  # 'a/P b/P' is 2P+4 long
        a, b = r[:n + 2], r[n + 3:]
    return b[2:] if a[:2] == 'a/' and b[:2] == 'b/' and a[2:] == b[2:] else None


def scan(diff):
    hits, path, line, rem, add, ok, hdr = [], None, 0, [], [], False, False

    def flush():
        if ok and (rem or add):
            hits.extend((path,) + h for h in hunk_hits(path, line0, rem, add))

    line0 = 0
    for raw in diff.splitlines():
        if raw.startswith('diff --git '):
            flush(); rem, add, hdr = [], [], True
            path = header_path(raw)
            ok = bool(path) and scanned(path)
        elif hdr and raw.startswith('+++ '):
            if raw.rstrip() == '+++ /dev/null' and ok and TESTY.search(path):
                hits.append((path, 1, 'deleted test', 'test or eval file deleted'))
        elif raw.startswith('@@'):
            flush(); rem, add, hdr = [], [], False
            if path is None:
                raise ValueError('hunk with no resolvable path: ' + raw[:80])
            m = re.search(r'\+(\d+)', raw)
            line = line0 = int(m.group(1))
        elif hdr:
            continue
        elif raw.startswith('-'):
            rem.append(raw[1:])
        elif raw.startswith('+'):
            add.append((line, raw[1:])); line += 1
    flush()
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='HEAD~1')
    base = ap.parse_args().base
    sys.stdout.reconfigure(encoding='utf-8')
    if base.startswith('-'):
        print('base must not start with "-"'); print('FLOOR FAIL bad-base'); return 1
    r = subprocess.run(['git', 'rev-parse', '--verify', base + '^{commit}'], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr.strip()); print('FLOOR FAIL bad-base'); return 1
    p = subprocess.run(['git', 'diff', '-U0', '--no-color', '--no-renames', r.stdout.strip(), '--'], capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        print(p.stderr.strip()); print('FLOOR FAIL git-diff-error'); return 1
    try:
        hits = scan(p.stdout)
    except ValueError as e:
        print(e); print('FLOOR FAIL unresolved-path'); return 1
    for f, n, sig, t in hits:
        print(f'{f}:{n} {sig} | {t.strip()[:100]}')
    print(f'FLOOR FAIL {len(hits)}' if hits else 'FLOOR PASS')
    return 1 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
